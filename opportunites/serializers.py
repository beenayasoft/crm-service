from rest_framework import serializers
from django.utils import timezone
from .models import Opportunity, OpportunityStatus, OpportunitySource, LossReason
from tenant_metier.models import Tiers


class OpportunitySerializer(serializers.ModelSerializer):
    """Serializer principal pour les opportunités avec logique métier"""
    
    # Champs calculés
    tier_name = serializers.CharField(source='tier.nom', read_only=True)
    tier_type = serializers.CharField(source='tier.type', read_only=True)
    days_open = serializers.SerializerMethodField()
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    source_display = serializers.CharField(source='get_source_display', read_only=True)
    loss_reason_display = serializers.CharField(source='get_loss_reason_display', read_only=True)
    
    class Meta:
        model = Opportunity
        fields = [
            'id', 'name', 'tier', 'tier_name', 'tier_type', 'stage', 'stage_display',
            'estimated_amount', 'probability', 'expected_close_date', 'source', 
            'source_display', 'description', 'assigned_to', 'created_at', 
            'updated_at', 'closed_at', 'loss_reason', 'loss_reason_display', 
            'loss_description', 'project_id', 'days_open'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at', 'closed_at', 'probability']
    
    def get_days_open(self, obj):
        """Calcule le nombre de jours depuis l'ouverture"""
        if obj.closed_at:
            return (obj.closed_at.date() - obj.created_at.date()).days
        return (timezone.now().date() - obj.created_at.date()).days
    
    def validate(self, data):
        """Validation métier"""
        # Vérification des champs requis pour les opportunités perdues
        if data.get('stage') == OpportunityStatus.LOST:
            if not data.get('loss_reason'):
                raise serializers.ValidationError({
                    'loss_reason': 'La raison de perte est obligatoire pour une opportunité perdue.'
                })
        
        # Vérification de la date de clôture
        expected_close_date = data.get('expected_close_date')
        if expected_close_date and expected_close_date < timezone.now().date():
            if data.get('stage') not in [OpportunityStatus.WON, OpportunityStatus.LOST]:
                raise serializers.ValidationError({
                    'expected_close_date': 'La date de clôture ne peut pas être dans le passé pour une opportunité active.'
                })
        
        return data


class OpportunityListSerializer(serializers.ModelSerializer):
    """Serializer optimisé pour les listes d'opportunités"""
    
    tier_name = serializers.CharField(source='tier.nom', read_only=True)
    tier_type = serializers.CharField(source='tier.type', read_only=True)
    stage_display = serializers.CharField(source='get_stage_display', read_only=True)
    days_open = serializers.SerializerMethodField()
    
    class Meta:
        model = Opportunity
        fields = [
            'id', 'name', 'tier', 'tier_name', 'tier_type', 'stage', 'stage_display',
            'estimated_amount', 'probability', 'expected_close_date', 
            'created_at', 'days_open', 'assigned_to'
        ]
    
    def get_days_open(self, obj):
        if obj.closed_at:
            return (obj.closed_at.date() - obj.created_at.date()).days
        return (timezone.now().date() - obj.created_at.date()).days


class OpportunityKanbanSerializer(serializers.ModelSerializer):
    """Serializer spécialisé pour la vue Kanban"""
    
    tier_name = serializers.CharField(source='tier.nom', read_only=True)
    tier_email = serializers.SerializerMethodField()
    tier_telephone = serializers.SerializerMethodField()
    days_open = serializers.SerializerMethodField()
    
    class Meta:
        model = Opportunity
        fields = [
            'id', 'name', 'tier', 'tier_name', 'tier_email', 'tier_telephone',
            'stage', 'estimated_amount', 'probability', 'expected_close_date',
            'description', 'assigned_to', 'created_at', 'days_open',
        ]
    
    def get_days_open(self, obj):
        if obj.closed_at:
            return (obj.closed_at.date() - obj.created_at.date()).days
        return (timezone.now().date() - obj.created_at.date()).days
    
    def get_tier_email(self, obj):
        """Récupère l'email du contact principal ou le premier contact"""
        if obj.tier and obj.tier.contacts.exists():
            contact = obj.tier.contacts.filter(contact_principal_devis=True).first()
            if not contact:
                contact = obj.tier.contacts.first()
            return contact.email if contact else ''
        return ''
    
    def get_tier_telephone(self, obj):
        """Récupère le téléphone du contact principal ou le premier contact"""
        if obj.tier and obj.tier.contacts.exists():
            contact = obj.tier.contacts.filter(contact_principal_devis=True).first()
            if not contact:
                contact = obj.tier.contacts.first()
            return contact.telephone if contact else ''
        return ''


class OpportunityStageUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour les mises à jour de statut avec validation métier"""
    
    class Meta:
        model = Opportunity
        fields = ['stage', 'loss_reason', 'loss_description', 'project_id']
    
    def validate(self, data):
        stage = data.get('stage')
        
        if stage == OpportunityStatus.LOST:
            if not data.get('loss_reason'):
                raise serializers.ValidationError({
                    'loss_reason': 'La raison de perte est obligatoire.'
                })
        
        if stage == OpportunityStatus.WON:
            if not data.get('project_id'):
                # Générer automatiquement un ID de projet si pas fourni
                data['project_id'] = f"PROJ-{timezone.now().strftime('%Y%m%d')}-{self.instance.id.hex[:8]}"
        
        return data


class OpportunityCreateSerializer(serializers.ModelSerializer):
    """Serializer pour la création d'opportunités avec validation spécifique"""
    
    class Meta:
        model = Opportunity
        fields = [
            'name', 'tier', 'stage', 'estimated_amount', 'expected_close_date',
            'source', 'description', 'assigned_to'
        ]
    
    def validate_tier(self, value):
        """Validation du tier"""
        try:
            tier = Tiers.objects.get(id=value.id)
            return tier
        except Tiers.DoesNotExist:
            raise serializers.ValidationError("Le tier spécifié n'existe pas.")


class OpportunityStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    by_stage = serializers.DictField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    in_progress_count = serializers.IntegerField()
    conversion_rate = serializers.FloatField()