"""
Configuration de l'interface d'administration pour les modèles tenant
"""
from django.contrib import admin
from .models import Client, Domain

@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ('name', 'schema_name', 'tenant_uuid', 'created_on')
    search_fields = ('name', 'schema_name', 'tenant_uuid')
    readonly_fields = ('created_on',)

@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    list_display = ('domain', 'tenant', 'is_primary')
    list_filter = ('is_primary',)
    search_fields = ('domain', 'tenant__name')
