"""
URL configuration for epicoutlet project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from shop.views import admin_dashboard, staff_assistant_api

admin.site.site_header = 'EpicOutlet'
admin.site.site_title = 'EpicOutlet Admin'
admin.site.index_title = 'Store administration'

urlpatterns = [
    path('admin/dashboard/', admin_dashboard, name='admin_dashboard'),
    path('admin/assistant/', staff_assistant_api, name='staff_assistant_api'),
    path('admin/', admin.site.urls),
    path('', include('shop.urls'))
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
