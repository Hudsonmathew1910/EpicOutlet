import json
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from . models import Catagory,Product, cart, fav
from django.contrib import messages
from . form import CustomUserForm
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_exempt
import os
from dotenv import load_dotenv
import google.generativeai as genai

# Load environment variables
load_dotenv()

# Initialize Gemini AI (but don't start chat loop here)
API_KEY = os.getenv('GOOGLE_API_KEY')

if not API_KEY:
    raise ValueError("GOOGLE_API_KEY not found in environment variables. Please check your .env file.")

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel("gemini-2.0-flash")

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

# New AI Chat Views
def ai_chat_page(request):
    """Render the chat interface page"""
    return render(request, "shop/ai_chat.html")

@csrf_exempt
def ai_chat_api(request):
    """Handle AI chat messages via API"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            
            if not user_message:
                return JsonResponse({'error': 'Empty message'}, status=400)
            
            # Start a new chat session for each request
            chat = model.start_chat(history=[
                {
                    "role": "user",
                    "parts": ["""You are an AI assistant for Epicoutlet, an e-commerce platform. Your role is to ONLY discuss topics related to Epicoutlet products, categories, shopping, and customer service.

EPICOUTLET PRODUCT INFORMATION:
- We have product categories with images and descriptions
- Products belong to categories and have: name, vendor, product images, quantity, original price, selling price, descriptions
- Users can add products to cart and favorites
- Shopping features: cart management, favorite items, user accounts

RULES:
1. ONLY answer questions about Epicoutlet products, categories, shopping, prices, availability, or related e-commerce topics
2. If asked about other topics, politely decline and redirect to Epicoutlet products
3. Help users with product information, shopping guidance, and general e-commerce queries within Epicoutlet
4. Do not provide information about competitors or other websites
5. If unsure about product availability or specific details, suggest checking the website or contacting customer service

How can I help you with Epicoutlet products today?"""]
                }
            ])
            
            # Get AI response
            response = chat.send_message(user_message)
            
            return JsonResponse({
                'response': response.text,
                'status': 'success'
            })
            
        except Exception as e:
            return JsonResponse({
                'error': 'I apologize, but I\'m having trouble responding. Please try again or visit our website directly.',
                'status': 'error'
            }, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)