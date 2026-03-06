import json
from django.http import JsonResponse
from django.shortcuts import render, redirect
from . models import Catagory,Product, cart, fav
from django.contrib import messages
from . form import CustomUserForm
from django.contrib.auth import authenticate, login, logout
import os
from dotenv import load_dotenv
from django.db.models import Q
from api.chat_service import chat_with_ai
from django.views.decorators.csrf import csrf_exempt
load_dotenv()

API_KEY = os.getenv('GOOGLE_API_KEY')

if not API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables. Please check your .env file.")

def home(request):
    products = Product.objects.filter(status=False).select_related('catagory')
    vendors = products.values_list('vendor', flat=True).distinct().order_by('vendor')
    
    #  Get Filter value url
    category = request.GET.get('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    vendor = request.GET.get('vendor')
    trending = request.GET.get('trending')
    sort = request.GET.get('sort')
    search = request.GET.get('search')

    # FILTER SECTION
    # Filter by category
    if category:
        products = products.filter(catagory__name__iexact=category)
    # Filter by price range
    if min_price:
        products = products.filter(selling_price__gte=min_price)
    if max_price:
        products = products.filter(selling_price__lte=max_price)
    # Filter by vendor
    if vendor:
        products = products.filter(vendor=vendor)
    # Filter by trending
    if trending == "1":
        products = products.filter(Trending=True)
    # Filter by search
    if search:
        search = search.strip().lower()
        if search.endswith('ies'):
            search = search[:-3] + 'y'
        elif search.endswith('es'):
            search = search[:-2]
        elif search.endswith('s'):
            search = search[:-1]
        products = products.filter(
                                    Q(name__icontains=search) | 
                                    Q(description__icontains=search) | 
                                    Q(catagory__name__icontains=search) | 
                                    Q(vendor__icontains=search)).distinct()


    # ORDERING 
    if sort == "low_high":
        products = products.order_by('selling_price')
    elif sort == 'high_low':
        products = products.order_by('-selling_price')
    elif sort == 'vendor':
        products = products.order_by('vendor')
    
    context = {
        "protrend": products,
        "categories": Catagory.objects.filter(status=False),
        "selected_vendor": vendor,
        "selected_category": category,
        "min_price": min_price,
        "max_price": max_price,
        "vendors": vendors,
        "trending": trending,
        "sort": sort,
        "search": search,
    }

    # For Debugging
    print("FULL URL:", request.get_full_path())
    # print("Category:", category)
    # print("Min:", min_price)
    # print("Max:", max_price)
    # print("Vendor:", vendor)
    # print("Trending:", trending)
    # print("Sort:", sort)
    # print("Count:", products.count())

    return render(request, "shop/index.html", context)

def login_page(request):
    if request.user.is_authenticated:
        return redirect('home')
    else:
        if request.method  == "POST":
            name = request.POST.get('username')
            pwd = request.POST.get('password')
            user=authenticate(request, username=name, password=pwd)
            if user is not None:
                login(request, user)
                messages.success(request, "Login Successfully..!")
                return redirect('home')
            else:
                messages.error(request, "Invalid User Name or Password")
                return redirect('login')
        return render(request, "shop/login.html")

def logout_page(request):
    if request.user.is_authenticated:
        logout(request)
        messages.success(request, "Logout Successfully..!")
    return redirect('home')

def register(request):
    form = CustomUserForm()
    if request.method=='POST':
        form = CustomUserForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "User Register Successfully..!")
            return redirect('login')
    return render(request, "shop/register.html", {"form":form})

def collection(request):
    category = Catagory.objects.filter(status=0)
    return render(request, "shop/collection.html", {"category":category})

def collectionview(request, name):
    # if(Catagory.objects.filter(name=name, status=0)):
    #     products = Product.objects.filter(catagory__name=name)
    #     return render(request, "shop/products/products.html", {"products":products, "category_name":name})
    # else:
    #     messages.warning(request, "No such Category Found")
    #     return redirect('collection')
    if not Catagory.objects.filter(name=name, status=0).exists():
        messages.error(request, "No such Category Found")
        return redirect('collection')

    products = Product.objects.filter(catagory__name=name, status=False)

    vendors = products.values_list('vendor', flat=True).distinct().order_by('vendor')

    # Get values
    vendor = request.GET.get('vendor') 
    trending = request.GET.get('trending')
    sort = request.GET.get('sort')

    # Filters
    if vendor:
         products = products.filter(vendor=vendor)
    if trending == '1':
        products = products.filter(Trending=True)
    
    # Ordering
    if sort == 'low_high':
        products = products.order_by('selling_price')
    elif sort == 'high_low':
        products = products.order_by('-selling_price')
    elif sort == 'vendor':
        products = products.order_by('vendor')

    context = {
        'products': products,
        'category_name': name,
        'vendors': vendors,
        'selected_vendor': vendor,
        'trending': trending,
        'sort': sort,
    }
    return render(request, "shop/products/products.html", context)

def product_details(request, cname, pname):
    if Catagory.objects.filter(name=cname, status=0).exists():
        product = Product.objects.filter(catagory__name=cname, name=pname, status=0).first()
        if product:
            return render(request, "shop/products/productview.html", {"product": product})
        else:
            messages.error(request, "No Such Product Found")
            return redirect('collection')
    else:
        messages.error(request, "No Such Category Found")
        return redirect('collections')
    
def add_to_cart(request):
    if request.headers.get('X-Requested-With')=='XMLHttpRequest':
        if request.user.is_authenticated:
            data = json.loads(request.body)
            product_qty = int(data['product_qty'])
            product_id = data['pid']
            product_status = Product.objects.get(id=product_id)
            if product_status:
                if cart.objects.filter(user=request.user, product_id=product_id).exists():
                    return JsonResponse({'status':'Product Already added'}, status=200)
                else:
                        if product_status.quantity>=product_qty:
                            cart.objects.create(user=request.user, product_id=product_id, product_qty=product_qty)
                            return JsonResponse({'status':'Product Added to cart'}, status=200)
                        else:
                            return JsonResponse({'status':f"Only {product_status.quantity} items left in stock"}, status=200)
            else:
                return JsonResponse({'status':'No such product'}, status=404)
        else:
            return JsonResponse({'status':'Login to Continue'}, status=200)
    else:
        return JsonResponse({'status': 'Invalid Access'}, status=200)
    
def cart_view(request):
    if request.user.is_authenticated:
        ucart = cart.objects.filter(user=request.user) 
        return render(request, "shop/cart.html", {"ucart":ucart})
    else:
        return redirect('/')

def remove_cart(request, cid):
    cartitem = cart.objects.get(id=cid)
    cartitem.delete()
    return redirect('/cart')

def profile(request):
    from .models import get_ava_url
    profile_url = get_ava_url(request.user.email, size=200)
    return render(request, "shop/profile.html", {"profile_url":profile_url})

def faviteam(request):
    if request.headers.get('X-Requested-With')=='XMLHttpRequest':
        if request.user.is_authenticated:
            data = json.loads(request.body)
            product_id = data['pid']
            product_status = Product.objects.get(id=product_id)
            if product_status:
                if fav.objects.filter(user=request.user, product_id=product_id).exists():
                    return JsonResponse({'status':'Product Already in Favourite'}, status=200)
                else:
                    fav.objects.create(user=request.user, product_id=product_id)
                    return JsonResponse({'status':'Favourite Added'}, status=200)
        else:
            return JsonResponse({'status':'Login to Add Favourite'}, status=200)
    else:
        return JsonResponse({'status': 'Invalid Access'}, status=200)
    
def remove_fav(request, fid):
    favitem = fav.objects.get(id=fid)
    favitem.delete()
    return redirect('/fav_page')

def favpage(request):
    if request.user.is_authenticated:
        favitm = fav.objects.filter(user=request.user) 
        return render(request, "shop/fav.html", {"favitm":favitm})
    else:
        return redirect('/')

def chat_page(request):
    return render(request, "shop/chat.html")

@csrf_exempt
def ai_chat_api(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            message = data.get("message", "")
            
            if not request.session.session_key:
                request.session.create()
            conversation_id = request.session.session_key
            
            is_admin = request.user.is_authenticated and request.user.is_superuser
            reply = chat_with_ai(message, conversation_id=conversation_id, is_admin=is_admin)
            return JsonResponse({"reply": reply})
        except Exception as e:
            return JsonResponse({"reply": f"Error: {str(e)}"}, status=500)
    return JsonResponse({"error": "Invalid method"}, status=405)
