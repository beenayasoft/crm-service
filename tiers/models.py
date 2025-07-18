"""
Modèles pour la gestion des tiers avec django-tenants
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_tenants.models import TenantMixin, DomainMixin


class Client(TenantMixin):
    """
    Modèle tenant pour django-tenants
    Remplace la logique de tenant_id par les schémas automatiques
    """
    name = models.CharField(max_length=100, verbose_name=_('Nom du client'))
    tenant_uuid = models.UUIDField(unique=True, help_text=_('UUID original du tenant'))
    created_on = models.DateTimeField(auto_now_add=True, verbose_name=_('Date de création'))
    
    # Configuration automatique des schémas
    auto_create_schema = True
    auto_drop_schema = True
    
    class Meta:
        verbose_name = _('Client Tenant')
        verbose_name_plural = _('Clients Tenants')
    
    def __str__(self):
        return f"{self.name} ({self.schema_name})"


class Domain(DomainMixin):
    """
    Modèle domaine pour django-tenants
    Gère l'association domaine/tenant
    """
    class Meta:
        verbose_name = _('Domaine')
        verbose_name_plural = _('Domaines')
    
    def __str__(self):
        return f"{self.domain} -> {self.tenant.name}"


# Les modèles métier Tiers, Adresse, Contact et ActiviteTiers 
# ont été déplacés vers l'app tenant_metier pour isoler les données par schéma
