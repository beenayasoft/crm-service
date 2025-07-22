"""
URLs principaux du service CRM
"""
from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

@require_http_methods(["GET"])
def health_check(request):
    """Endpoint de health check simple"""
    return JsonResponse({
        'status': 'healthy',
        'service': 'crm',
        'version': '1.0.0'
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('crm.urls')),  # Nouvelle app CRM unifiée
    path('health/', health_check, name='health_check'),
]
