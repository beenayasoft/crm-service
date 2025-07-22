"""
Modèles pour la gestion des tiers
"""
import uuid
from django.db import models
from django.core.validators import EmailValidator, RegexValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

class Tiers(models.Model):
    """
    Modèle principal pour gérer les tiers (clients, prospects, fournisseurs, sous-traitants)
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
    
    # Champs principaux
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    type = models.CharField(
        max_length=20, 
        choices=TYPE_CHOICES, 
        default=TYPE_ENTREPRISE,
        db_index=True
    )
    nom = models.CharField(
        max_length=255, 
        verbose_name=_('Nom'), 
        unique=True,
        db_index=True
    )
    
    # Informations légales (pour entreprises)
    siret = models.CharField(
        max_length=14, 
        blank=True, 
        null=True, 
        verbose_name=_('SIRET'),
        validators=[RegexValidator(regex=r'^\d{14}$')],
        db_index=True
    )
    tva = models.CharField(
        max_length=20, 
        blank=True, 
        null=True, 
        verbose_name=_('Numéro TVA'),
        validators=[RegexValidator(regex=r'^[A-Z]{2}\d{9,13}$')]
    )
    
    # Catégorisation
    relation = models.CharField(
        max_length=20, 
        choices=RELATION_CHOICES, 
        default=RELATION_PROSPECT,
        verbose_name=_('Relation'),
        help_text=_('Type de relation principale avec ce tier'),
        db_index=True
    )
    
    # Gestion du cycle de vie
    is_deleted = models.BooleanField(
        default=False, 
        verbose_name=_('Archivé'),
        db_index=True
    )
    created_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name=_('Date de création'),
        db_index=True
    )
    updated_at = models.DateTimeField(
        auto_now=True, 
        verbose_name=_('Date de modification'),
        db_index=True
    )
    deleted_at = models.DateTimeField(
        null=True, 
        blank=True, 
        verbose_name=_('Date d\'archivage')
    )
    
    class Meta:
        verbose_name = _('Tier')
        verbose_name_plural = _('Tiers')
        ordering = ['-created_at']
        indexes = [
            # Index simples déjà définis via db_index=True
            
            # Index composites pour les requêtes courantes
            models.Index(fields=['type', 'relation']),
            models.Index(fields=['relation', 'created_at']),
            models.Index(fields=['is_deleted', 'relation']),
            models.Index(fields=['type', 'is_deleted']),
            # Index pour la recherche
            models.Index(fields=['nom', 'siret']),
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
        self.deleted_at = timezone.now()
        self.save()
    
    def restore(self):
        """Restaurer un tier archivé"""
        self.is_deleted = False
        self.deleted_at = None
        self.save()

    def convert_to_client(self):
        """Convertir un prospect en client"""
        if self.relation == self.RELATION_PROSPECT:
            self.relation = self.RELATION_CLIENT
            self.save()
            return True
        return False

class Adresse(models.Model):
    """
    Modèle pour gérer les adresses des tiers
    """
    tier = models.ForeignKey(
        Tiers, 
        on_delete=models.CASCADE, 
        related_name='adresses',
        verbose_name=_('Tier'),
        db_index=True
    )
    libelle = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name=_('Libellé')
    )
    rue = models.CharField(
        max_length=255, 
        blank=True, 
        verbose_name=_('Rue')
    )
    ville = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name=_('Ville'),
        db_index=True
    )
    code_postal = models.CharField(
        max_length=10, 
        blank=True, 
        verbose_name=_('Code postal'),
        validators=[RegexValidator(regex=r'^\d{5}$')],
        db_index=True
    )
    pays = models.CharField(
        max_length=100, 
        default='France', 
        verbose_name=_('Pays')
    )
    is_facturation = models.BooleanField(
        default=False, 
        verbose_name=_('Adresse de facturation'),
        db_index=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Adresse')
        verbose_name_plural = _('Adresses')
        ordering = ['-is_facturation', 'libelle']
        indexes = [
            # Index composites pour les requêtes courantes
            models.Index(fields=['tier', 'is_facturation']),
            models.Index(fields=['ville', 'code_postal']),
        ]
    
    def __str__(self):
        return f"{self.libelle} - {self.rue}, {self.code_postal} {self.ville}"
    
    def save(self, *args, **kwargs):
        # Si cette adresse est marquée comme facturation, désactiver les autres
        if self.is_facturation:
            Adresse.objects.filter(
                tier=self.tier, 
                is_facturation=True
            ).exclude(pk=self.pk).update(is_facturation=False)
        super().save(*args, **kwargs)

class Contact(models.Model):
    """
    Modèle pour gérer les contacts des tiers
    """
    tier = models.ForeignKey(
        Tiers, 
        on_delete=models.CASCADE, 
        related_name='contacts',
        verbose_name=_('Tier'),
        db_index=True
    )
    nom = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name=_('Nom'),
        db_index=True
    )
    prenom = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name=_('Prénom')
    )
    fonction = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name=_('Fonction')
    )
    email = models.EmailField(
        blank=True, 
        verbose_name=_('Email'),
        validators=[EmailValidator()],
        db_index=True
    )
    telephone = models.CharField(
        max_length=20, 
        blank=True, 
        verbose_name=_('Téléphone'),
        validators=[RegexValidator(regex=r'^\+?[0-9]{10,15}$')],
        db_index=True
    )
    
    # Rôles spécifiques
    is_contact_principal_devis = models.BooleanField(
        default=False, 
        verbose_name=_('Contact principal devis'),
        db_index=True
    )
    is_contact_principal_facture = models.BooleanField(
        default=False, 
        verbose_name=_('Contact principal facture'),
        db_index=True
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('Contact')
        verbose_name_plural = _('Contacts')
        ordering = ['nom', 'prenom']
        indexes = [
            # Index composites pour les requêtes courantes
            models.Index(fields=['tier', 'is_contact_principal_devis']),
            models.Index(fields=['tier', 'is_contact_principal_facture']),
            models.Index(fields=['nom', 'prenom']),
        ]
    
    def __str__(self):
        return f"{self.prenom} {self.nom} - {self.tier.nom}"
    
    @property
    def nom_complet(self):
        """Retourne le nom complet du contact"""
        return f"{self.prenom} {self.nom}".strip()
    
    def save(self, *args, **kwargs):
        # Gestion des contacts principaux uniques
        if self.is_contact_principal_devis:
            Contact.objects.filter(
                tier=self.tier, 
                is_contact_principal_devis=True
            ).exclude(pk=self.pk).update(is_contact_principal_devis=False)
        
        if self.is_contact_principal_facture:
            Contact.objects.filter(
                tier=self.tier, 
                is_contact_principal_facture=True
            ).exclude(pk=self.pk).update(is_contact_principal_facture=False)
        
        super().save(*args, **kwargs)

class ActiviteTiers(models.Model):
    """
    Modèle pour gérer le journal d'activités des tiers
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
        verbose_name=_('Tier'),
        db_index=True
    )
    type = models.CharField(
        max_length=20, 
        choices=TYPE_CHOICES, 
        verbose_name=_('Type d\'activité'),
        db_index=True
    )
    user_id = models.UUIDField(
        verbose_name=_('Utilisateur ID'),
        db_index=True
    )  # Référence vers auth-service
    content = models.TextField(verbose_name=_('Contenu'))
    created_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name=_('Date'),
        db_index=True
    )
    
    class Meta:
        verbose_name = _('Activité Tier')
        verbose_name_plural = _('Activités Tiers')
        ordering = ['-created_at']
        indexes = [
            # Index composites pour les requêtes courantes
            models.Index(fields=['tier', 'type']),
            models.Index(fields=['tier', 'created_at']),
            models.Index(fields=['type', 'created_at']),
            models.Index(fields=['user_id', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.get_type_display()} - {self.tier.nom} - {self.created_at.strftime('%d/%m/%Y')}" 