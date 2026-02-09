# export_fixed.py
import os
import django
import json

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'epicoutlet.settings')
django.setup()

from shop.models import Catagory, Product, cart, fav
from django.contrib.auth.models import User

def export_data_safely():
    print("Starting safe data export...")
    
    all_data = []
    
    # Export Users
    try:
        users = User.objects.all()
        for user in users:
            user_data = {
                'model': 'auth.user',
                'pk': user.pk,
                'fields': {
                    'password': user.password,
                    'last_login': user.last_login.isoformat() if user.last_login else None,
                    'is_superuser': user.is_superuser,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'is_staff': user.is_staff,
                    'is_active': user.is_active,
                    'date_joined': user.date_joined.isoformat(),
                }
            }
            all_data.append(user_data)
        print(f"✓ Exported {len(users)} users")
    except Exception as e:
        print(f"✗ Failed to export users: {e}")

    # Export Categories
    try:
        categories = Catagory.objects.all()
        for category in categories:
            category_data = {
                'model': 'shop.catagory',
                'pk': category.pk,
                'fields': {
                    'name': category.name.encode('utf-8', 'ignore').decode('utf-8'),
                    'description': category.description.encode('utf-8', 'ignore').decode('utf-8'),
                    'image': str(category.image),
                    'status': category.status,
                    'Created_at': category.Created_at.isoformat(),
                    'order': category.order,
                }
            }
            all_data.append(category_data)
        print(f"✓ Exported {len(categories)} categories")
    except Exception as e:
        print(f"✗ Failed to export categories: {e}")

    # Export Products
    try:
        products = Product.objects.all()
        for product in products:
            product_data = {
                'model': 'shop.product',
                'pk': product.pk,
                'fields': {
                    'catagory': product.catagory.pk,
                    'name': product.name.encode('utf-8', 'ignore').decode('utf-8'),
                    'vendor': product.vendor.encode('utf-8', 'ignore').decode('utf-8'),
                    'product_image': str(product.product_image),
                    'quantity': product.quantity,
                    'orginal_price': product.orginal_price,
                    'selling_price': product.selling_price,
                    'description': product.description.encode('utf-8', 'ignore').decode('utf-8'),
                    'status': product.status,
                    'Trending': product.Trending,
                    'Created_at': product.Created_at.isoformat(),
                }
            }
            all_data.append(product_data)
        print(f"✓ Exported {len(products)} products")
    except Exception as e:
        print(f"✗ Failed to export products: {e}")

    # Save to file
    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(all_data, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Export completed!")
    print(f"📊 Total objects exported: {len(all_data)}")
    print(f"💾 Saved to: data.json")

if __name__ == '__main__':
    export_data_safely()