import json
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from . models import Catagory,Product, cart, fav
from django.contrib import messages
from . form import CustomUserForm
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.csrf import csrf_exempt
import os


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
    
@csrf_exempt
def one_click_import(request):
    if request.method == 'POST':
        try:
            # PASTE YOUR ENTIRE data.json CONTENT HERE
            data_json = """
            [
  {
    "model": "auth.user",
    "pk": 1,
    "fields": {
      "password": "pbkdf2_sha256$1000000$UNF4DgxcVA9obETlOYspm5$LZdtaoO7GzNxudrNyYQ1c+yJUOp0XzbnO3Ac7uSNzPU=",
      "last_login": "2025-10-11T08:14:33.211935+00:00",
      "is_superuser": true,
      "username": "huddy",
      "first_name": "",
      "last_name": "",
      "email": "hudsonmathew2004@gmail.com",
      "is_staff": true,
      "is_active": true,
      "date_joined": "2025-09-16T13:53:53.584000+00:00"
    }
  },
  {
    "model": "auth.user",
    "pk": 3,
    "fields": {
      "password": "pbkdf2_sha256$1000000$KTsUadkO0D9eBujU3LPU8R$nxo4f8jh6B8b1vWWI+1NBTtRCHtLi2EPUYv5YHX++Dw=",
      "last_login": "2025-10-11T08:10:49.320438+00:00",
      "is_superuser": false,
      "username": "ravi",
      "first_name": "",
      "last_name": "",
      "email": "raviabc861@gmail.com",
      "is_staff": false,
      "is_active": true,
      "date_joined": "2025-10-11T08:10:14.998155+00:00"
    }
  },
  {
    "model": "auth.user",
    "pk": 4,
    "fields": {
      "password": "pbkdf2_sha256$1000000$t1SOok3k4kiYbsZTllrEHU$9zOwB15/OS85ntwJM/k443wTxksrtMEZDPtozfaj7vE=",
      "last_login": "2025-10-11T08:12:22.630231+00:00",
      "is_superuser": false,
      "username": "Buddy",
      "first_name": "",
      "last_name": "",
      "email": "Susilajames1971@gmail.com",
      "is_staff": false,
      "is_active": true,
      "date_joined": "2025-10-11T08:12:14.063704+00:00"
    }
  },
  {
    "model": "auth.user",
    "pk": 5,
    "fields": {
      "password": "pbkdf2_sha256$1000000$ixqpUm7S8SuBMcldL6IEdi$Rlinvx6H+eRq7umHQf+Ye0exlW3yNFlM/6HKxtwzXXA=",
      "last_login": "2025-10-11T08:14:25.188662+00:00",
      "is_superuser": false,
      "username": "hudson",
      "first_name": "",
      "last_name": "",
      "email": "huddy1910@gmail.com",
      "is_staff": false,
      "is_active": true,
      "date_joined": "2025-10-11T08:14:17.551352+00:00"
    }
  },
  {
    "model": "shop.catagory",
    "pk": 5,
    "fields": {
      "name": "Mobile",
      "description": "Stay connected with the latest smartphones, feature-devices, and unbeatable deals - all in one place",
      "image": "Epicoutlte/catagory/cqujsbmw5o6hie4xt2gi",
      "status": false,
      "Created_at": "2025-09-16T15:28:31.181000+00:00",
      "order": 1
    }
  },
  {
    "model": "shop.catagory",
    "pk": 7,
    "fields": {
      "name": "Home",
      "description": "Everything you need to make your house a home ù from dΘcor to essentials, delivered to your doorstep",
      "image": "Epicoutlte/catagory/nyvntdvg65bvfbrrm9mm",
      "status": false,
      "Created_at": "2025-09-16T16:17:17.721000+00:00",
      "order": 2
    }
  },
  {
    "model": "shop.catagory",
    "pk": 9,
    "fields": {
      "name": "Electronic",
      "description": "Shop top-quality gadgets, appliances, and accessories to make life smarter, easier, and more fun",
      "image": "Epicoutlte/catagory/vym9fkh7it8xqtst9t7b",
      "status": false,
      "Created_at": "2025-09-16T16:17:17.757000+00:00",
      "order": 3
    }
  },
  {
    "model": "shop.catagory",
    "pk": 6,
    "fields": {
      "name": "Grocery",
      "description": "Fresh, fast, and affordable ù get daily essentials and pantry favorites delivered straight to you",
      "image": "Epicoutlte/catagory/gunchyk2zfjqessn70fh",
      "status": false,
      "Created_at": "2025-09-16T16:16:06.430000+00:00",
      "order": 4
    }
  },
  {
    "model": "shop.catagory",
    "pk": 8,
    "fields": {
      "name": "Fashion",
      "description": "Discover trendy styles, modern, timeless classics, and everything you need to look your best every day",
      "image": "Epicoutlte/catagory/aoae5axn1fifpvheqjvn",
      "status": false,
      "Created_at": "2025-09-16T16:17:17.741000+00:00",
      "order": 5
    }
  },
  {
    "model": "shop.product",
    "pk": 2,
    "fields": {
      "catagory": 9,
      "name": "HP Laptop",
      "vendor": "HP",
      "product_image": "Epicoutlte/products/ugsxlwd1ivxoz46asxj2",
      "quantity": 169,
      "orginal_price": 45915,
      "selling_price": 38367,
      "description": "Budget-friendly",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-16T16:17:17.713000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 3,
    "fields": {
      "catagory": 8,
      "name": "Levi's T-Shirt",
      "vendor": "Levi's",
      "product_image": "Epicoutlte/products/p6cd8txcrbu9koqitdcq",
      "quantity": 98,
      "orginal_price": 33141,
      "selling_price": 27233,
      "description": "Latest model",
      "status": false,
      "Trending": false,
      "Created_at": "2025-09-16T16:17:17.728000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 4,
    "fields": {
      "catagory": 8,
      "name": "H&M Jeans",
      "vendor": "H&M",
      "product_image": "Epicoutlte/products/onhyhif5io3arhud62cw",
      "quantity": 132,
      "orginal_price": 40017,
      "selling_price": 37066,
      "description": "Top rated",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-16T16:17:17.732000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 5,
    "fields": {
      "catagory": 5,
      "name": "Samsung Galaxy 4",
      "vendor": "Samsung",
      "product_image": "Epicoutlte/products/cfmquznnwcgbvvr5luit",
      "quantity": 1,
      "orginal_price": 4280,
      "selling_price": 3609,
      "description": "Premium product",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-16T16:17:17.737000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 6,
    "fields": {
      "catagory": 5,
      "name": "Samsung Galaxy 5",
      "vendor": "Samsung",
      "product_image": "Epicoutlte/products/gfxhpqu11zojtpulwjpp",
      "quantity": 23,
      "orginal_price": 74338,
      "selling_price": 67383,
      "description": "Latest model",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-16T16:17:17.744000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 7,
    "fields": {
      "catagory": 7,
      "name": "VanAcc Sofa",
      "vendor": "VanAcc",
      "product_image": "Epicoutlte/products/zmvxcn41p9kcv3csj0ym",
      "quantity": 72,
      "orginal_price": 37788,
      "selling_price": 30733,
      "description": "VanAcc 124 Inches Modular Sectional Sofa, 6 Seats U Shaped sofa with Chaise, Oversized Sectional Sofa with Storage, Ottomans- Chenille Gray",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-16T16:17:17.748000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 8,
    "fields": {
      "catagory": 9,
      "name": "Samsung Laptop",
      "vendor": "Samsung",
      "product_image": "Epicoutlte/products/xqh7n4muodjelgfjnknt",
      "quantity": 0,
      "orginal_price": 70728,
      "selling_price": 64989,
      "description": "Durable",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-16T16:17:17.753000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 9,
    "fields": {
      "catagory": 7,
      "name": "Dining Table IKEA",
      "vendor": "IKEA",
      "product_image": "Epicoutlte/products/j1dx1rmolgcmxdd7ykej",
      "quantity": 11,
      "orginal_price": 58002,
      "selling_price": 50249,
      "description": "Durable",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-16T16:17:17.760000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 10,
    "fields": {
      "catagory": 8,
      "name": "Levi's Jeans 9",
      "vendor": "Levis",
      "product_image": "Epicoutlte/products/kk5txkemqcyvr7vyeaqi",
      "quantity": 43,
      "orginal_price": 66466,
      "selling_price": 54244,
      "description": "Premium product",
      "status": false,
      "Trending": false,
      "Created_at": "2025-09-16T16:17:17.764000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 11,
    "fields": {
      "catagory": 6,
      "name": "Milma Curd",
      "vendor": "Milma",
      "product_image": "Epicoutlte/products/gksdqtstru2r6iwnqgpu",
      "quantity": 96,
      "orginal_price": 32,
      "selling_price": 24,
      "description": "Durable",
      "status": false,
      "Trending": false,
      "Created_at": "2025-09-16T16:17:17.768000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 12,
    "fields": {
      "catagory": 8,
      "name": "Amorina T-Shirt",
      "vendor": "Amorina",
      "product_image": "Epicoutlte/products/usjr9cvjijmjfuadhkid",
      "quantity": 152,
      "orginal_price": 31748,
      "selling_price": 25566,
      "description": "Premium product",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-16T16:17:17.772000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 13,
    "fields": {
      "catagory": 8,
      "name": "Wrangler Jeans",
      "vendor": "Wrangler",
      "product_image": "Epicoutlte/products/sogknsq6hrwjsjqvvtwm",
      "quantity": 96,
      "orginal_price": 33746,
      "selling_price": 29390,
      "description": "High quality",
      "status": false,
      "Trending": false,
      "Created_at": "2025-09-16T16:17:17.775000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 14,
    "fields": {
      "catagory": 8,
      "name": "Levi's Jeans",
      "vendor": "Levi's",
      "product_image": "Epicoutlte/products/tckkil5hpakprsbjbefp",
      "quantity": 179,
      "orginal_price": 41131,
      "selling_price": 35810,
      "description": "Budget-friendly",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-16T16:17:17.779000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 15,
    "fields": {
      "catagory": 5,
      "name": "iPhone 15",
      "vendor": "Samsung",
      "product_image": "Epicoutlte/products/uolhku7mxl59tu2nw9ea",
      "quantity": 17,
      "orginal_price": 36098,
      "selling_price": 29136,
      "description": "Durable",
      "status": false,
      "Trending": false,
      "Created_at": "2025-09-16T16:17:17.783000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 16,
    "fields": {
      "catagory": 6,
      "name": "Hatsun Milk Pack",
      "vendor": "Hatsun",
      "product_image": "Epicoutlte/products/g0besaq1krhyffvzuybb",
      "quantity": 22,
      "orginal_price": 30,
      "selling_price": 20,
      "description": "people's choice",
      "status": false,
      "Trending": false,
      "Created_at": "2025-09-16T16:17:17.787000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 17,
    "fields": {
      "catagory": 8,
      "name": "Jeans Local Farm",
      "vendor": "Local Farm",
      "product_image": "Epicoutlte/products/zvtxd70zczd6owodywcf",
      "quantity": 13,
      "orginal_price": 48293,
      "selling_price": 45703,
      "description": "Top rated",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-16T16:17:17.791000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 18,
    "fields": {
      "catagory": 5,
      "name": "Samsung Galaxy 17",
      "vendor": "Samsung",
      "product_image": "Epicoutlte/products/d6u38zjakp2o8oe2btyj",
      "quantity": 148,
      "orginal_price": 18435,
      "selling_price": 17153,
      "description": "Durable",
      "status": false,
      "Trending": false,
      "Created_at": "2025-09-16T16:17:17.795000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 19,
    "fields": {
      "catagory": 9,
      "name": "Apple Headphones",
      "vendor": "Apple",
      "product_image": "Epicoutlte/products/y17u6o07qrva3v9iyb7w",
      "quantity": 60,
      "orginal_price": 69784,
      "selling_price": 57902,
      "description": "Popular choice",
      "status": false,
      "Trending": false,
      "Created_at": "2025-09-16T16:17:17.799000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 20,
    "fields": {
      "catagory": 9,
      "name": "Dell Headphones",
      "vendor": "Dell",
      "product_image": "Epicoutlte/products/qfkdkpv1z9pgi0ulrjjg",
      "quantity": 86,
      "orginal_price": 50496,
      "selling_price": 43569,
      "description": "Budget-friendly",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-16T16:17:17.802000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 21,
    "fields": {
      "catagory": 8,
      "name": "T-Shirt UrbanLadder",
      "vendor": "UrbanLadder",
      "product_image": "Epicoutlte/products/frgdvc7l2vibtxct2nkb",
      "quantity": 107,
      "orginal_price": 25074,
      "selling_price": 21062,
      "description": "Durable",
      "status": false,
      "Trending": false,
      "Created_at": "2025-09-16T16:17:17.806000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 22,
    "fields": {
      "catagory": 8,
      "name": "Glamood Jeans 21",
      "vendor": "Glamood",
      "product_image": "Epicoutlte/products/pfhatqqxpurkgvufbjoz",
      "quantity": 91,
      "orginal_price": 40821,
      "selling_price": 35005,
      "description": "Regular Fit Jeans men",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-16T16:17:17.810000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 23,
    "fields": {
      "catagory": 8,
      "name": "Kimjeans Jeans",
      "vendor": "Kimjeans",
      "product_image": "Epicoutlte/products/ykm22gvsldmc1wwgxdxb",
      "quantity": 187,
      "orginal_price": 51724,
      "selling_price": 41921,
      "description": "Stylein",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-16T16:17:17.814000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 24,
    "fields": {
      "catagory": 7,
      "name": "Evermotion Sofa",
      "vendor": "Evermotion",
      "product_image": "Epicoutlte/products/in0t9ygratnd93vaomsm",
      "quantity": 188,
      "orginal_price": 55904,
      "selling_price": 45769,
      "description": "Latest model",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-16T16:17:17.818000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 25,
    "fields": {
      "catagory": 5,
      "name": "Samsung Galaxy 24",
      "vendor": "Samsung",
      "product_image": "Epicoutlte/products/euj94ssmd69nhpk1syvn",
      "quantity": 6,
      "orginal_price": 13664,
      "selling_price": 12223,
      "description": "Popular choice",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-16T16:17:17.823000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 26,
    "fields": {
      "catagory": 7,
      "name": "IKEA Bed (King Size)",
      "vendor": "IKEA",
      "product_image": "Epicoutlte/products/pq10tzyt3joukoxmjxzx",
      "quantity": 10,
      "orginal_price": 55000,
      "selling_price": 47500,
      "description": "Comfortable wooden king bed.",
      "status": false,
      "Trending": false,
      "Created_at": "2025-09-18T14:56:28.896000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 27,
    "fields": {
      "catagory": 7,
      "name": "Wardrobe 4-Door",
      "vendor": "Godrej",
      "product_image": "Epicoutlte/products/tvimaogh1op4tsqngq1k",
      "quantity": 22,
      "orginal_price": 38000,
      "selling_price": 34200,
      "description": "Spacious steel wardrobe.",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-18T14:57:39.265000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 28,
    "fields": {
      "catagory": 7,
      "name": "DiningTable UL",
      "vendor": "UrbanLadder",
      "product_image": "Epicoutlte/products/mwgvg2lbdshq6hznjso1",
      "quantity": 12,
      "orginal_price": 9500,
      "selling_price": 8000,
      "description": "Stylish wooden table.",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-18T14:58:50.479000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 29,
    "fields": {
      "catagory": 6,
      "name": "India Gate Rice Bag",
      "vendor": "India Gate",
      "product_image": "Epicoutlte/products/u97whk9jmh1ctetzermu",
      "quantity": 12,
      "orginal_price": 185,
      "selling_price": 160,
      "description": "Premium basmati rice.",
      "status": false,
      "Trending": false,
      "Created_at": "2025-09-18T15:00:07.287000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 30,
    "fields": {
      "catagory": 6,
      "name": "Aashirvaad Wheat Flour",
      "vendor": "Aashirvaad",
      "product_image": "Epicoutlte/products/usgqnpy1rdseh8kh6emf",
      "quantity": 22,
      "orginal_price": 560,
      "selling_price": 480,
      "description": "High-quality atta.",
      "status": false,
      "Trending": false,
      "Created_at": "2025-09-18T15:01:20.258000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 31,
    "fields": {
      "catagory": 6,
      "name": "Tata Sugar 5kg",
      "vendor": "Tata",
      "product_image": "Epicoutlte/products/igj7d1cp0ujwbysb1ed1",
      "quantity": 22,
      "orginal_price": 280,
      "selling_price": 250,
      "description": "Refined white sugar.",
      "status": false,
      "Trending": false,
      "Created_at": "2025-09-18T15:02:30.662000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 32,
    "fields": {
      "catagory": 6,
      "name": "Sunflower Oil 1L",
      "vendor": "Fortune",
      "product_image": "Epicoutlte/products/imrnh97har6nr44yi8dm",
      "quantity": 22,
      "orginal_price": 180,
      "selling_price": 160,
      "description": "Healthy cooking oil.",
      "status": false,
      "Trending": false,
      "Created_at": "2025-09-18T15:03:45.055000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 33,
    "fields": {
      "catagory": 5,
      "name": "OnePlus Nord 3",
      "vendor": "OnePlus",
      "product_image": "Epicoutlte/products/pkzniiekvms4qofyeob2",
      "quantity": 22,
      "orginal_price": 35000,
      "selling_price": 32000,
      "description": "Smooth performance phone.",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-18T15:07:39.566000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 34,
    "fields": {
      "catagory": 5,
      "name": "iPhone 14",
      "vendor": "Apple",
      "product_image": "Epicoutlte/products/vcibg0pfxodfhc7thvxx",
      "quantity": 22,
      "orginal_price": 79000,
      "selling_price": 74000,
      "description": "Latest Apple flagship",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-18T15:08:56.017000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 35,
    "fields": {
      "catagory": 9,
      "name": "Sony PlayStation",
      "vendor": "Sony",
      "product_image": "Epicoutlte/products/eiustocmhxqu2lgl2klu",
      "quantity": 23,
      "orginal_price": 55000,
      "selling_price": 50000,
      "description": "PlayStation 5",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-18T15:09:59.636000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 36,
    "fields": {
      "catagory": 9,
      "name": "Air Conditioner",
      "vendor": "Voltas",
      "product_image": "Epicoutlte/products/u1tsrayjnmppp4n9jfix",
      "quantity": 2,
      "orginal_price": 38000,
      "selling_price": 35000,
      "description": "Energy-saving AC.",
      "status": false,
      "Trending": false,
      "Created_at": "2025-09-18T15:10:51.278000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 37,
    "fields": {
      "catagory": 9,
      "name": "LG Smart TV 43",
      "vendor": "LG",
      "product_image": "Epicoutlte/products/ycc05vq3qkwgmfxbyq9c",
      "quantity": 0,
      "orginal_price": 42000,
      "selling_price": 38000,
      "description": "4K UHD Smart TV.",
      "status": false,
      "Trending": true,
      "Created_at": "2025-09-18T15:11:57.389000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 38,
    "fields": {
      "catagory": 9,
      "name": "Xbox Series-X-Gaming-Console",
      "vendor": "Xbox",
      "product_image": "Epicoutlte/products/pjnohcjhawb1mth7ojax",
      "quantity": 5,
      "orginal_price": 60000,
      "selling_price": 55000,
      "description": "Newest-Microsoft-Xbox-Series-X-Gaming-Console-1TB-SSD-Black-X-Version-with-Disc-Drive",
      "status": false,
      "Trending": true,
      "Created_at": "2025-10-07T07:55:58.042000+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 39,
    "fields": {
      "catagory": 8,
      "name": "RX T-shirt",
      "vendor": "RX",
      "product_image": "Epicoutlte/products/linklaprddozrr6ffyaf",
      "quantity": 15,
      "orginal_price": 15000,
      "selling_price": 8000,
      "description": "Stylish, comfortable, and uniquely you – our brand T-shirt makes every look effortless.",
      "status": false,
      "Trending": true,
      "Created_at": "2025-10-10T09:15:05.869540+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 40,
    "fields": {
      "catagory": 8,
      "name": "RX Formal's",
      "vendor": "RX",
      "product_image": "Epicoutlte/products/lcvwfyepyseczvxidbnt",
      "quantity": 24,
      "orginal_price": 20000,
      "selling_price": 12000,
      "description": "Stylish, comfortable, and uniquely you – our brand Formal shirt makes every look effortless.",
      "status": false,
      "Trending": true,
      "Created_at": "2025-10-10T09:18:17.882708+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 41,
    "fields": {
      "catagory": 9,
      "name": "Fridge",
      "vendor": "Whirlpool",
      "product_image": "Epicoutlte/products/i9kmnjrydqnovdgjo5q0",
      "quantity": 19,
      "orginal_price": 25000,
      "selling_price": 23000,
      "description": "Keep your food fresh and drinks cool with our energy-efficient, spacious fridge.",
      "status": false,
      "Trending": true,
      "Created_at": "2025-10-10T09:32:23.434531+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 42,
    "fields": {
      "catagory": 5,
      "name": "Vivo Y300",
      "vendor": "Vivo",
      "product_image": "Epicoutlte/products/slgjkvuceaxeso4ulzdb",
      "quantity": 18,
      "orginal_price": 25000,
      "selling_price": 23000,
      "description": "Vivo mobile – sleek design, powerful performance, and smart features in your hand.",
      "status": false,
      "Trending": true,
      "Created_at": "2025-10-10T09:34:50.515975+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 43,
    "fields": {
      "catagory": 7,
      "name": "BELLEZE TV stand",
      "vendor": "BELLEZE",
      "product_image": "Epicoutlte/products/z8zszwhshreknq0ifq0x",
      "quantity": 20,
      "orginal_price": 20000,
      "selling_price": 15000,
      "description": "Sturdy and stylish TV stand – the perfect blend of storage and elegance for your living room.",
      "status": false,
      "Trending": true,
      "Created_at": "2025-10-10T09:36:44.600797+00:00"
    }
  },
  {
    "model": "shop.product",
    "pk": 44,
    "fields": {
      "catagory": 7,
      "name": "Computer table",
      "vendor": "Pepperfry",
      "product_image": "Epicoutlte/products/mw9zsukpm2fxlcmyi16v",
      "quantity": 10,
      "orginal_price": 18000,
      "selling_price": 13000,
      "description": "Compact and durable computer table – organized workspace for productivity and comfort.",
      "status": false,
      "Trending": true,
      "Created_at": "2025-10-10T09:39:07.102945+00:00"
    }
  }
]
            """
            
            import json
            from django.core import serializers
            
            data = json.loads(data_json)
            count = 0
            
            for item in data:
                try:
                    # Skip users (you already have admin)
                    if item['model'] == 'auth.user':
                        continue
                    
                    # Import everything else
                    for obj in serializers.deserialize('json', json.dumps([item])):
                        obj.save()
                    count += 1
                except:
                    continue
            
            return HttpResponse(f"✅ DONE! Imported {count} items in 2 seconds!")
            
        except Exception as e:
            return HttpResponse(f"Error: {str(e)}")
    
    # FIXED: Use HttpResponse instead of render
    return HttpResponse('''
    <html>
    <body style="font-family: Arial; margin: 40px;">
        <h1>🚀 One-Click Data Import</h1>
        <p>Click below to import all your categories and products instantly!</p>
        <form method="post">
            <button type="submit" style="padding: 15px 30px; background: green; color: white; border: none; cursor: pointer; font-size: 18px;">
                📤 IMPORT ALL DATA NOW
            </button>
        </form>
    </body>
    </html>
    ''')