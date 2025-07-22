"""
Configuration de l'interface d'administration pour les modèles CRM
"""
from django.contrib import admin
from .models import (
    Tiers, Contact, Adresse, ActiviteTiers,
    Opportunity
)

@admin.register(Tiers)
class TiersAdmin(admin.ModelAdmin):
    list_display = ('nom', 'type', 'relation', 'siret', 'is_deleted', 'created_at')
    list_filter = ('type', 'relation', 'is_deleted')
    search_fields = ('nom', 'siret')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at', 'deleted_at')
    fieldsets = (
        ('Informations principales', {
            'fields': ('nom', 'type', 'relation')
        }),
        ('Informations légales', {
            'fields': ('siret', 'tva')
        }),
        ('Gestion', {
            'fields': ('is_deleted', 'created_at', 'updated_at', 'deleted_at')
        }),
    )

@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    list_display = ('nom_complet', 'tier', 'email', 'telephone', 'is_contact_principal_devis')
    list_filter = ('is_contact_principal_devis', 'is_contact_principal_facture')
    search_fields = ('nom', 'prenom', 'email', 'telephone', 'tier__nom')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(Adresse)
class AdresseAdmin(admin.ModelAdmin):
    list_display = ('libelle', 'tier', 'ville', 'code_postal', 'is_facturation')
    list_filter = ('is_facturation', 'pays')
    search_fields = ('libelle', 'rue', 'ville', 'code_postal', 'tier__nom')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(ActiviteTiers)
class ActiviteTiersAdmin(admin.ModelAdmin):
    list_display = ('tier', 'type', 'user_id', 'created_at')
    list_filter = ('type',)
    search_fields = ('tier__nom', 'content')
    readonly_fields = ('created_at',)

@admin.register(Opportunity)
class OpportunityAdmin(admin.ModelAdmin):
    list_display = ('name', 'tier', 'stage', 'estimated_amount', 'probability', 'expected_close_date', 'created_at')
    list_filter = ('stage', 'source', 'created_at')
    search_fields = ('name', 'description', 'tier__nom')
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at', 'updated_at', 'closed_at')
    fieldsets = (
        ('Informations principales', {
            'fields': ('name', 'tier', 'stage', 'estimated_amount', 'probability', 'expected_close_date')
        }),
        ('Détails', {
            'fields': ('source', 'description', 'assigned_to')
        }),
        ('Opportunité gagnée', {
            'fields': ('project_id',),
            'classes': ('collapse',),
        }),
        ('Opportunité perdue', {
            'fields': ('loss_reason', 'loss_description'),
            'classes': ('collapse',),
        }),
        ('Dates', {
            'fields': ('created_at', 'updated_at', 'closed_at'),
            'classes': ('collapse',),
        }),
    )
