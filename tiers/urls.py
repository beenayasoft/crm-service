"""
URLs pour l'API CRM
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .views import TiersViewSet, AdresseViewSet, ContactViewSet, ActiviteViewSet

# Router principal
router = DefaultRouter()
router.register(r'tiers', TiersViewSet, basename='tiers')

# Routers imbriqués pour les sous-ressources
tiers_router = routers.NestedDefaultRouter(router, r'tiers', lookup='tier')
tiers_router.register(r'adresses', AdresseViewSet, basename='tier-adresses')
tiers_router.register(r'contacts', ContactViewSet, basename='tier-contacts')
tiers_router.register(r'activites', ActiviteViewSet, basename='tier-activites')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(tiers_router.urls)),
]
