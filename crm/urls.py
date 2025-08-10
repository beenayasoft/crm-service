"""
Configuration des URLs pour l'API CRM
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_nested import routers

from .api.tiers import (
    TiersViewSet,
    ContactViewSet,
    AdresseViewSet,
    ActiviteTiersViewSet
)
from .api.opportunities import OpportunityViewSet

# Router principal
router = DefaultRouter()
router.register(r'tiers', TiersViewSet, basename='tiers')
router.register(r'contacts', ContactViewSet, basename='contacts')
router.register(r'adresses', AdresseViewSet, basename='adresses')
router.register(r'opportunities', OpportunityViewSet, basename='opportunities')

# Routers imbriqués pour les sous-ressources des tiers
tiers_router = routers.NestedDefaultRouter(router, r'tiers', lookup='tier')
tiers_router.register(r'contacts', ContactViewSet, basename='tier-contacts')
tiers_router.register(r'adresses', AdresseViewSet, basename='tier-adresses')
tiers_router.register(r'activites', ActiviteTiersViewSet, basename='tier-activites')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(tiers_router.urls)),
] 