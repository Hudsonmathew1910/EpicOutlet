import os
import sys
import django
from django.core.management import call_command

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'epicoutlet.settings')
django.setup()

# Export data
with open('datadump.json', 'w', encoding='utf-8') as f:
    call_command('dumpdata', 
                 exclude=['auth.permission', 'contenttypes'],
                 stdout=f,
                 indent=2)
print("Data exported successfully to datadump.json")