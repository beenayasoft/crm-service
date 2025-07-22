"""
Modèles pour la gestion des opportunités
"""
import uuid
from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from .tiers import Tiers

class OpportunityStatus(models.TextChoices):
    """Statuts possibles d'une opportunité"""
    NEW = "new", _("Nouvelle")
    NEEDS_ANALYSIS = "needs_analysis", _("Analyse des besoins")
    NEGOTIATION = "negotiation", _("Négociation")
    WON = "won", _("Gagnée")
    LOST = "lost", _("Perdue")

class OpportunitySource(models.TextChoices):
    """Sources possibles d'une opportunité"""
    WEBSITE = "website", _("Site web")
    REFERRAL = "referral", _("Recommandation")
    PARTNER = "partner", _("Partenaire")
    COLD_CALL = "cold_call", _("Démarchage")
    EXHIBITION = "exhibition", _("Salon/Exposition")
    OTHER = "other", _("Autre")

class LossReason(models.TextChoices):
    """Raisons possibles de perte d'une opportunité"""
    PRICE = "price", _("Prix")
    COMPETITOR = "competitor", _("Concurrent")
    TIMING = "timing", _("Timing")
    NO_BUDGET = "no_budget", _("Pas de budget")
    NO_NEED = "no_need", _("Pas de besoin")
    NO_DECISION = "no_decision", _("Pas de décision")
    OTHER = "other", _("Autre")

class Opportunity(models.Model):
    """
    Modèle principal pour gérer les opportunités commerciales
    """
    id = models.UUIDField(
        primary_key=True, 
        default=uuid.uuid4, 
        editable=False
    )
    name = models.CharField(
        max_length=255, 
        verbose_name=_("Nom"),
        db_index=True
    )
    tier = models.ForeignKey(
        Tiers, 
        on_delete=models.CASCADE, 
        related_name="opportunities", 
        verbose_name=_("Tiers"),
        db_index=True
    )
    stage = models.CharField(
        max_length=20,
        choices=OpportunityStatus.choices,
        default=OpportunityStatus.NEW,
        verbose_name=_("Étape"),
        db_index=True
    )
    estimated_amount = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        verbose_name=_("Montant estimé"),
        validators=[MinValueValidator(0)],
        db_index=True
    )
    probability = models.IntegerField(
        default=10, 
        verbose_name=_("Probabilité (%)"),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        db_index=True
    )
    expected_close_date = models.DateField(
        verbose_name=_("Date de clôture prévue"),
        db_index=True
    )
    source = models.CharField(
        max_length=20,
        choices=OpportunitySource.choices,
        default=OpportunitySource.OTHER,
        verbose_name=_("Source"),
        db_index=True
    )
    description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Description")
    )
    assigned_to = models.UUIDField(
        blank=True, 
        null=True, 
        verbose_name=_("Assigné à (user_id)"),
        db_index=True
    )
    
    # Dates
    created_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name=_("Créé le"),
        db_index=True
    )
    updated_at = models.DateTimeField(
        auto_now=True, 
        verbose_name=_("Mis à jour le"),
        db_index=True
    )
    closed_at = models.DateTimeField(
        blank=True, 
        null=True, 
        verbose_name=_("Clôturé le"),
        db_index=True
    )
    
    # Champs pour les opportunités perdues
    loss_reason = models.CharField(
        max_length=20,
        choices=LossReason.choices,
        blank=True,
        null=True,
        verbose_name=_("Raison de perte"),
        db_index=True
    )
    loss_description = models.TextField(
        blank=True, 
        null=True, 
        verbose_name=_("Description de la perte")
    )
    
    # Champs pour les opportunités gagnées
    project_id = models.CharField(
        max_length=50, 
        blank=True, 
        null=True, 
        verbose_name=_("ID du projet")
    )
    
    class Meta:
        verbose_name = _("Opportunité")
        verbose_name_plural = _("Opportunités")
        ordering = ["-created_at"]
        indexes = [
            # Index composites pour les requêtes courantes
            models.Index(fields=['stage', 'tier']),
            models.Index(fields=['stage', 'created_at']),
            models.Index(fields=['stage', 'source']),
            models.Index(fields=['stage', 'assigned_to']),
            models.Index(fields=['stage', 'probability']),
            models.Index(fields=['tier', 'created_at']),
            models.Index(fields=['tier', 'stage']),
            models.Index(fields=['source', 'created_at']),
            models.Index(fields=['assigned_to', 'created_at']),
            models.Index(fields=['stage', 'tier', 'created_at']),
            models.Index(fields=['stage', 'source', 'created_at']),
            models.Index(fields=['stage', 'assigned_to', 'created_at']),
            # Nouveaux index pour les requêtes de reporting
            models.Index(fields=['probability', 'estimated_amount']),
            models.Index(fields=['expected_close_date', 'probability']),
            models.Index(fields=['stage', 'expected_close_date']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.tier.nom}"
    
    def save(self, *args, **kwargs):
        # Mettre à jour la probabilité en fonction du statut
        if self.stage == OpportunityStatus.NEW:
            self.probability = 10
        elif self.stage == OpportunityStatus.NEEDS_ANALYSIS:
            self.probability = 30
        elif self.stage == OpportunityStatus.NEGOTIATION:
            self.probability = 60
        elif self.stage == OpportunityStatus.WON:
            self.probability = 100
            if not self.closed_at:
                self.closed_at = timezone.now()
                # Si c'est une opportunité gagnée et que le tier est un prospect,
                # le convertir en client
                if self.tier.is_prospect:
                    self.tier.convert_to_client()
        elif self.stage == OpportunityStatus.LOST:
            self.probability = 0
            if not self.closed_at:
                self.closed_at = timezone.now()
        
        super().save(*args, **kwargs)
        
    def mark_as_won(self, project_id=None):
        """Marquer l'opportunité comme gagnée"""
        self.stage = OpportunityStatus.WON
        self.probability = 100
        self.closed_at = timezone.now()
        if project_id:
            self.project_id = project_id
        self.save()
        
    def mark_as_lost(self, reason, description=None):
        """Marquer l'opportunité comme perdue"""
        self.stage = OpportunityStatus.LOST
        self.probability = 0
        self.closed_at = timezone.now()
        self.loss_reason = reason
        if description:
            self.loss_description = description
        self.save()

    @property
    def days_in_pipeline(self):
        """Retourne le nombre de jours depuis la création"""
        if self.closed_at:
            return (self.closed_at.date() - self.created_at.date()).days
        return (timezone.now().date() - self.created_at.date()).days

    @property
    def weighted_amount(self):
        """Retourne le montant pondéré par la probabilité"""
        return (self.estimated_amount * self.probability) / 100 