import os
import django
import pandas as pd
from shop.models import Catagory, Product

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'epicoutlet.settings')  # Replace with your project.settings
django.setup()


# Read Excel file
df = pd.read_excel('shop/Datas.xlsx', sheet_name='Products')


def str_to_bool(val):
    if str(val).strip().lower() in ['true', '1', 'show']:
        return True
    else:
        return False

for index, row in df.iterrows():
    cat, created = Catagory.objects.get_or_create(name=row['Category'])
    Product.objects.create(
        catagory=cat,
        name=row['Name'],
        vendor=row['Vendor'],
        quantity=row['Quantity'],
        orginal_price=row['Original Price'],
        selling_price=row['Selling Price'],
        description=row['Description'],
        status=str_to_bool(row['Status']),
        Trending=str_to_bool(row['Trending'])
    )
