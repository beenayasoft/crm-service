"""
Modèles métier pour la gestion des tiers - Isolés par schéma tenant
Ces modèles sont dans TENANT_APPS et donc isolés par schéma PostgreSQL
"""
import uuid
from django.db import models
from django.utils.translation import gettext_lazy as _


class Tiers(models.Model):
    """
    Modèle principal pour gérer les tiers (clients, prospects, fournisseurs, sous-traitants)
    Isolé par schéma tenant (plus besoin de tenant_id)
    """
    
    # Types de tiers
    TYPE_ENTREPRISE = 'entreprise'
    TYPE_PARTICULIER = 'particulier'
    TYPE_CHOICES = [
        (TYPE_ENTREPRISE, _('Entreprise')),
        (TYPE_PARTICULIER, _('Particulier')),
    ]
    
    # Relations pour catégoriser les tiers
    RELATION_PROSPECT = 'prospect'
    RELATION_CLIENT = 'client'
    RELATION_FOURNISSEUR = 'fournisseur'
    RELATION_SOUS_TRAITANT = 'sous_traitant'
    RELATION_CHOICES = [
        (RELATION_CLIENT, _('Client')),
        (RELATION_PROSPECT, _('Prospect')),
        (RELATION_FOURNISSEUR, _('Fournisseur')),
        (RELATION_SOUS_TRAITANT, _('Sous-traitant')),
    ]
    
    # Champs principaux (PLUS de tenant_id - isolé par schéma)
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default=TYPE_ENTREPRISE)
    nom = models.CharField(max_length=255, verbose_name=_('Nom'), unique=True)  # Unique par schéma
    
    # Informations légales (pour entreprises)
    siret = models.CharField(max_length=14, blank=True, null=True, verbose_name=_('SIRET'))
    tva = models.CharField(max_length=20, blank=True, null=True, verbose_name=_('Numéro TVA'))
    
    # Catégorisation
    relation = models.CharField(
        max_length=20, 
        choices=RELATION_CHOICES, 
        default=RELATION_PROSPECT,
        verbose_name=_('Relation'),
        help_text=_('Type de relation principale avec ce tier')
    )
    
    # Gestion du cycle de vie
    is_deleted = models.BooleanField(default=False, verbose_name=_('Archivé'))
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name=_('Date de création'))
    date_modification = models.DateTimeField(auto_now=True, verbose_name=_('Date de modification'))
    date_archivage = models.DateTimeField(null=True, blank=True, verbose_name=_('Date d\'archivage'))
    
    class Meta:
        verbose_name = _('Tier')
        verbose_name_plural = _('Tiers')
        ordering = ['-date_creation']
        db_table = 'tenant_metier_tiers'  # Nom de table explicite
        indexes = [
            models.Index(fields=['type']),
            models.Index(fields=['relation']),
            models.Index(fields=['is_deleted']),
            models.Index(fields=['date_creation']),
        ]
    
    def __str__(self):
        return f"{self.nom} ({self.get_type_display()})"
    
    @property
    def relation_display(self):
        """Retourne l'affichage de la relation principale"""
        return self.get_relation_display()
    
    @property
    def is_client(self):
        """Vérifie si le tier est un client"""
        return self.relation == self.RELATION_CLIENT
    
    @property 
    def is_prospect(self):
        """Vérifie si le tier est un prospect"""
        return self.relation == self.RELATION_PROSPECT
    
    @property
    def is_fournisseur(self):
        """Vérifie si le tier est un fournisseur"""
        return self.relation == self.RELATION_FOURNISSEUR
    
    @property
    def is_sous_traitant(self):
        """Vérifie si le tier est un sous-traitant"""
        return self.relation == self.RELATION_SOUS_TRAITANT
    
    def delete(self, using=None, keep_parents=False):
        """Soft delete - marquer comme archivé au lieu de supprimer"""
        self.is_deleted = True
        from django.utils import timezone
        self.date_archivage = timezone.now()
        self.save()
    
    def restore(self):
        """Restaurer un tier archivé"""
        self.is_deleted = False
        self.date_archivage = None
        self.save()


class Adresse(models.Model):
    """
    Modèle pour gérer les adresses des tiers
    """
    tier = models.ForeignKey(
        Tiers, 
        on_delete=models.CASCADE, 
        related_name='adresses',
        verbose_name=_('Tier')
    )
    libelle = models.CharField(max_length=100, blank=True, verbose_name=_('Libellé'))
    rue = models.CharField(max_length=255, blank=True, verbose_name=_('Rue'))
    ville = models.CharField(max_length=100, blank=True, verbose_name=_('Ville'))
    code_postal = models.CharField(max_length=10, blank=True, verbose_name=_('Code postal'))
    pays = models.CharField(max_length=100, default='France', verbose_name=_('Pays'))
    facturation = models.BooleanField(default=False, verbose_name=_('Adresse de facturation'))
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Adresse')
        verbose_name_plural = _('Adresses')
        ordering = ['-facturation', 'libelle']
        db_table = 'tenant_metier_adresse'
        indexes = [
            models.Index(fields=['tier']),
            models.Index(fields=['facturation']),
        ]
    
    def __str__(self):
        return f"{self.libelle} - {self.rue}, {self.code_postal} {self.ville}"
    
    def save(self, *args, **kwargs):
        # Si cette adresse est marquée comme facturation, désactiver les autres
        if self.facturation:
            Adresse.objects.filter(tier=self.tier, facturation=True).exclude(pk=self.pk).update(facturation=False)
        super().save(*args, **kwargs)


class Contact(models.Model):
    """
    Modèle pour gérer les contacts des tiers
    """
    tier = models.ForeignKey(
        Tiers, 
        on_delete=models.CASCADE, 
        related_name='contacts',
        verbose_name=_('Tier')
    )
    nom = models.CharField(max_length=100, blank=True, verbose_name=_('Nom'))
    prenom = models.CharField(max_length=100, blank=True, verbose_name=_('Prénom'))
    fonction = models.CharField(max_length=100, blank=True, verbose_name=_('Fonction'))
    email = models.EmailField(blank=True, verbose_name=_('Email'))
    telephone = models.CharField(max_length=20, blank=True, verbose_name=_('Téléphone'))
    
    # Rôles spécifiques
    contact_principal_devis = models.BooleanField(default=False, verbose_name=_('Contact principal devis'))
    contact_principal_facture = models.BooleanField(default=False, verbose_name=_('Contact principal facture'))
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Contact')
        verbose_name_plural = _('Contacts')
        ordering = ['nom', 'prenom']
        db_table = 'tenant_metier_contact'
        indexes = [
            models.Index(fields=['tier']),
            models.Index(fields=['email']),
        ]
    
    def __str__(self):
        return f"{self.prenom} {self.nom} - {self.tier.nom}"
    
    @property
    def nom_complet(self):
        """Retourne le nom complet du contact"""
        return f"{self.prenom} {self.nom}".strip()
    
    def save(self, *args, **kwargs):
        # Gestion des contacts principaux uniques
        if self.contact_principal_devis:
            Contact.objects.filter(tier=self.tier, contact_principal_devis=True).exclude(pk=self.pk).update(contact_principal_devis=False)
        
        if self.contact_principal_facture:
            Contact.objects.filter(tier=self.tier, contact_principal_facture=True).exclude(pk=self.pk).update(contact_principal_facture=False)
        
        super().save(*args, **kwargs)


class ActiviteTiers(models.Model):
    """
    Modèle pour gérer le journal d'activités des tiers
    Garde la référence utilisateur_id vers auth-service (logique inchangée)
    """
    
    # Types d'activités
    TYPE_CREATION = 'creation'
    TYPE_MODIFICATION = 'modification'
    TYPE_APPEL = 'appel'
    TYPE_EMAIL = 'email'
    TYPE_RENDEZ_VOUS = 'rendez_vous'
    TYPE_DEVIS = 'devis'
    TYPE_FACTURE = 'facture'
    TYPE_AUTRE = 'autre'
    
    TYPE_CHOICES = [
        (TYPE_CREATION, _('Création')),
        (TYPE_MODIFICATION, _('Modification')),
        (TYPE_APPEL, _('Appel')),
        (TYPE_EMAIL, _('Email')),
        (TYPE_RENDEZ_VOUS, _('Rendez-vous')),
        (TYPE_DEVIS, _('Devis')),
        (TYPE_FACTURE, _('Facture')),
        (TYPE_AUTRE, _('Autre')),
    ]
    
    tier = models.ForeignKey(
        Tiers, 
        on_delete=models.CASCADE, 
        related_name='activites',
        verbose_name=_('Tier')
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name=_('Type d\'activité'))
    utilisateur_id = models.UUIDField(verbose_name=_('Utilisateur ID'))  # Référence vers auth-service
    contenu = models.TextField(verbose_name=_('Contenu'))
    date = models.DateTimeField(auto_now_add=True, verbose_name=_('Date'))
    
    class Meta:
        verbose_name = _('Activité Tier')
        verbose_name_plural = _('Activités Tiers')
        ordering = ['-date']
        db_table = 'tenant_metier_activitetiers'
        indexes = [
            models.Index(fields=['tier']),
            models.Index(fields=['type']),
            models.Index(fields=['date']),
            models.Index(fields=['utilisateur_id']),
        ]
    
    def __str__(self):
        return f"{self.get_type_display()} - {self.tier.nom} - {self.date.strftime('%d/%m/%Y')}"
