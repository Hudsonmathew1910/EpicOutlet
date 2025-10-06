import json
from django.http import JsonResponse
from django.shortcuts import render, redirect
from . models import Catagory,Product, cart, fav
from django.contrib import messages
from . form import CustomUserForm
from django.contrib.auth import authenticate, login, logout


def home(request):
    protrend= Product.objects.filter(Trending=1)
    return render(request, "shop/index.html", {"protrend":protrend})

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
    if(Catagory.objects.filter(name=name, status=0)):
        products = Product.objects.filter(catagory__name=name)
        return render(request, "shop/products/products.html", {"products":products, "category_name":name})
    else:
        messages.warning(request, "No such Category Found")
        return redirect('collection')
    
    
def product_details(request, cname, pname):
    if Catagory.objects.filter(name=cname, status=0).exists():
        product = Product.objects.filter(name=pname, status=0).first()
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
            # print(request.user.id)
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