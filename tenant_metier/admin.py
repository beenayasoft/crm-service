"""
Interface d'administration pour les modèles métier des tiers
"""
from django.contrib import admin
from .models import Tiers, Adresse, Contact, ActiviteTiers

@admin.register(Tiers)
class TiersAdmin(admin.ModelAdmin):
    list_display = ['nom', 'type', 'relation', 'is_deleted', 'date_creation']
    list_filter = ['type', 'relation', 'is_deleted', 'date_creation']
    search_fields = ['nom', 'siret']
    readonly_fields = ['date_creation', 'date_modification']

@admin.register(Adresse)
class AdresseAdmin(admin.ModelAdmin):
    list_display = ['tier', 'libelle', 'ville', 'facturation']
    list_filter = ['facturation', 'pays']

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ['tier', 'nom', 'prenom', 'email', 'telephone']
    search_fields = ['nom', 'prenom', 'email']

@admin.register(ActiviteTiers)
class ActiviteAdmin(admin.ModelAdmin):
    list_display = ['tier', 'type', 'utilisateur_id', 'date']
    list_filter = ['type', 'date']
    readonly_fields = ['date']
