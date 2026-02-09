import os
import sys
import django
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'epicoutlet.settings')
django.setup()

# Export with UTF-8 encoding
with open('data.json', 'w', encoding='utf-8') as f:
    sys.stdout = f
    call_command('dumpdata', 
                 '--exclude', 'auth.permission',
                 '--exclude', 'contenttypes',
                 '--indent', '2')
    sys.stdout = sys.__stdout__

print("✅ Data exported to data.json with UTF-8 encoding")