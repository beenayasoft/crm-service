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
    """Sérialiseur optimisé pour les listes d'opportunités - Format camelCase unifié"""
    
    # Format unifié camelCase
    tierId = serializers.CharField(source='tier.id', read_only=True)
    tierName = serializers.CharField(source='tier.nom', read_only=True)
    estimatedAmount = serializers.DecimalField(source='estimated_amount', max_digits=12, decimal_places=2, read_only=True)
    expectedCloseDate = serializers.DateField(source='expected_close_date', read_only=True)
    assignedTo = serializers.CharField(source='assigned_to', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    closedAt = serializers.DateTimeField(source='closed_at', read_only=True)
    daysInPipeline = serializers.IntegerField(source='days_in_pipeline', read_only=True)
    weightedAmount = serializers.DecimalField(
        source='weighted_amount',
        max_digits=12, 
        decimal_places=2, 
        read_only=True
    )

    class Meta:
        model = Opportunity
        fields = [
            'id', 'name', 'tierId', 'tierName', 'stage', 'estimatedAmount', 
            'probability', 'weightedAmount', 'expectedCloseDate', 'source',
            'assignedTo', 'daysInPipeline', 'createdAt', 'closedAt'
        ]
        read_only_fields = ['id', 'probability', 'createdAt', 'closedAt', 'daysInPipeline', 'weightedAmount']

class OpportunityDetailSerializer(serializers.ModelSerializer):
    """Sérialiseur complet pour les détails d'une opportunité - Format camelCase unifié"""
    
    # Champs formatés camelCase
    tierId = serializers.CharField(source='tier.id', read_only=True)
    tierName = serializers.CharField(source='tier.nom', read_only=True)
    tierType = serializers.SerializerMethodField()
    estimatedAmount = serializers.DecimalField(source='estimated_amount', max_digits=12, decimal_places=2, read_only=True)
    expectedCloseDate = serializers.DateField(source='expected_close_date', read_only=True)
    assignedTo = serializers.CharField(source='assigned_to', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    closedAt = serializers.DateTimeField(source='closed_at', read_only=True)
    lossReason = serializers.CharField(source='loss_reason', read_only=True)
    lossDescription = serializers.CharField(source='loss_description', read_only=True)
    projectId = serializers.CharField(source='project_id', read_only=True)
    
    # Champs calculés
    daysInPipeline = serializers.IntegerField(source='days_in_pipeline', read_only=True)
    weightedAmount = serializers.DecimalField(
        source='weighted_amount',
        max_digits=12, 
        decimal_places=2, 
        read_only=True
    )

    class Meta:
        model = Opportunity
        fields = [
            'id', 'name', 'tierId', 'tierName', 'tierType', 'stage', 
            'estimatedAmount', 'probability', 'expectedCloseDate', 'source',
            'description', 'assignedTo', 'createdAt', 'updatedAt', 'closedAt',
            'lossReason', 'lossDescription', 'projectId', 'daysInPipeline', 'weightedAmount'
        ]
        read_only_fields = ['id', 'probability', 'createdAt', 'updatedAt', 'closedAt', 'daysInPipeline', 'weightedAmount']
    
    def get_tierType(self, obj):
        """Retourne les types du tier sous forme de liste"""
        if hasattr(obj.tier, 'get_type_list'):
            return obj.tier.get_type_list()
        return []
    

class OpportunityCreateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la création d'une opportunité avec validation"""
    
    # Format unifié camelCase SEULEMENT
    tierId = serializers.CharField(source='tier', required=True)
    estimatedAmount = serializers.DecimalField(
        source='estimated_amount', 
        max_digits=12, 
        decimal_places=2, 
        required=True
    )
    expectedCloseDate = serializers.DateField(
        source='expected_close_date', 
        required=True
    )
    assignedTo = serializers.CharField(
        source='assigned_to',
        required=False,
        allow_blank=True,
        allow_null=True
    )
    
    class Meta:
        model = Opportunity
        fields = [
            'id', 'name', 'tierId', 'stage', 'estimatedAmount',
            'expectedCloseDate', 'source', 'description', 'assignedTo'
        ]
        read_only_fields = ['id', 'probability']

    def validate_estimatedAmount(self, value):
        """Validation du montant estimé"""
        if value <= 0:
            raise serializers.ValidationError(
                _("Le montant estimé doit être supérieur à 0.")
            )
        return value
    
    def validate_tierId(self, value):
        """Validation et résolution du tier"""
        from ..models import Tiers  # Import depuis models
        try:
            tier = Tiers.objects.get(id=value)
            return tier  # Retourner l'objet Tiers, pas juste l'UUID
        except Tiers.DoesNotExist:
            raise serializers.ValidationError(
                _("Le tier avec l'ID {} n'existe pas.").format(value)
            )

    def validate(self, data):
        """Validation globale"""
        # La probabilité sera gérée automatiquement par le modèle
        # Pas besoin de la définir ici
        return data

class OpportunityUpdateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la mise à jour d'une opportunité - Format camelCase unifié"""
    
    # Format unifié camelCase SEULEMENT
    estimatedAmount = serializers.DecimalField(
        source='estimated_amount', 
        max_digits=12, 
        decimal_places=2, 
        required=False
    )
    expectedCloseDate = serializers.DateField(
        source='expected_close_date', 
        required=False
    )
    assignedTo = serializers.CharField(
        source='assigned_to',
        required=False,
        allow_blank=True,
        allow_null=True
    )
    lossReason = serializers.CharField(
        source='loss_reason',
        required=False,
        allow_blank=True,
        allow_null=True
    )
    lossDescription = serializers.CharField(
        source='loss_description',
        required=False,
        allow_blank=True,
        allow_null=True
    )
    
    class Meta:
        model = Opportunity
        fields = [
            'name', 'stage', 'estimatedAmount', 'expectedCloseDate', 
            'source', 'description', 'assignedTo', 'lossReason', 'lossDescription'
        ]
        read_only_fields = ['probability']

    def validate_estimatedAmount(self, value):
        """Validation du montant estimé"""
        if value <= 0:
            raise serializers.ValidationError(
                _("Le montant estimé doit être supérieur à 0.")
            )
        return value

    def validate(self, data):
        """Validation globale simplifiée"""
        # La gestion de la probabilité se fait automatiquement dans le modèle
        # Pas besoin de la gérer ici pour éviter les conflits
        return data

class OpportunityStageUpdateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la mise à jour du statut uniquement"""
    loss_reason = serializers.ChoiceField(
        choices=LossReason.choices, 
        required=False
    )
    loss_description = serializers.CharField(required=False, allow_null=True, allow_blank=True)

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