"""
Sérialiseurs pour les modèles d'opportunités
"""
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from ..models import (
    Opportunity, 
    OpportunityStatus, 
    OpportunitySource, 
    LossReason
)
from .tiers import TiersListSerializer

class OpportunityListSerializer(serializers.ModelSerializer):
    """Sérialiseur optimisé pour les listes d'opportunités"""
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    tier_nom = serializers.CharField(source='tier.nom', read_only=True)
    days_in_pipeline = serializers.IntegerField(read_only=True)
    weighted_amount = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        read_only=True
    )

    class Meta:
        model = Opportunity
        fields = [
            'id', 'name', 'tier_nom', 'stage', 'stage_display',
            'estimated_amount', 'probability', 'weighted_amount',
            'expected_close_date', 'source', 'source_display',
            'days_in_pipeline', 'created_at', 'closed_at'
        ]
        read_only_fields = ['created_at', 'closed_at']

class OpportunityDetailSerializer(serializers.ModelSerializer):
    """Sérialiseur complet pour les détails d'une opportunité"""
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    loss_reason_display = serializers.CharField(source='get_loss_reason_display', read_only=True)
    tier = TiersListSerializer(read_only=True)
    days_in_pipeline = serializers.IntegerField(read_only=True)
    weighted_amount = serializers.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        read_only=True
    )

    class Meta:
        model = Opportunity
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'closed_at']

class OpportunityCreateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la création d'une opportunité avec validation"""
    class Meta:
        model = Opportunity
        fields = [
            'name', 'tier', 'stage', 'estimated_amount',
            'probability', 'expected_close_date', 'source',
            'description', 'assigned_to'
        ]

    def validate_estimated_amount(self, value):
        """Validation du montant estimé"""
        if value <= 0:
            raise serializers.ValidationError(
                _("Le montant estimé doit être supérieur à 0.")
            )
        return value

    def validate_probability(self, value):
        """Validation de la probabilité"""
        if not 0 <= value <= 100:
            raise serializers.ValidationError(
                _("La probabilité doit être comprise entre 0 et 100.")
            )
        return value

    def validate(self, data):
        """Validation globale"""
        if data.get('stage') == OpportunityStatus.WON and data.get('probability', 100) != 100:
            data['probability'] = 100
        elif data.get('stage') == OpportunityStatus.LOST and data.get('probability', 0) != 0:
            data['probability'] = 0
        return data

class OpportunityUpdateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la mise à jour d'une opportunité"""
    class Meta:
        model = Opportunity
        fields = [
            'name', 'stage', 'estimated_amount', 'probability',
            'expected_close_date', 'source', 'description',
            'assigned_to'
        ]
        read_only_fields = ['created_at', 'updated_at', 'closed_at']

    def validate_estimated_amount(self, value):
        """Validation du montant estimé"""
        if value <= 0:
            raise serializers.ValidationError(
                _("Le montant estimé doit être supérieur à 0.")
            )
        return value

    def validate(self, data):
        """Validation globale avec gestion des statuts"""
        if 'stage' in data:
            current_stage = self.instance.stage if self.instance else None
            new_stage = data['stage']
            
            # Si passage à gagné
            if new_stage == OpportunityStatus.WON:
                data['probability'] = 100
                if self.instance.tier.is_prospect:
                    self.instance.tier.convert_to_client()
            
            # Si passage à perdu
            elif new_stage == OpportunityStatus.LOST:
                data['probability'] = 0
                
            # Si retour en pipeline depuis gagné/perdu
            elif current_stage in [OpportunityStatus.WON, OpportunityStatus.LOST]:
                if new_stage == OpportunityStatus.NEW:
                    data['probability'] = 10
                elif new_stage == OpportunityStatus.NEEDS_ANALYSIS:
                    data['probability'] = 30
                elif new_stage == OpportunityStatus.NEGOTIATION:
                    data['probability'] = 60
        
        return data

class OpportunityStageUpdateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la mise à jour du statut uniquement"""
    loss_reason = serializers.ChoiceField(
        choices=LossReason.choices, 
        required=False
    )
    loss_description = serializers.CharField(required=False)

    class Meta:
        model = Opportunity
        fields = ['stage', 'loss_reason', 'loss_description']

    def validate(self, data):
        """Validation du changement de statut"""
        if data['stage'] == OpportunityStatus.LOST:
            if not data.get('loss_reason'):
                raise serializers.ValidationError(
                    _("Une raison de perte est requise.")
                )
        return data 