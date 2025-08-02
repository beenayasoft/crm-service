"""
Sérialiseurs pour les modèles de tiers
"""
from rest_framework import serializers
from django.utils.translation import gettext_lazy as _
from ..models import Tiers, Contact, Adresse, ActiviteTiers

class ContactListSerializer(serializers.ModelSerializer):
    """Sérialiseur optimisé pour les listes de contacts"""
    class Meta:
        model = Contact
        fields = ['id', 'nom', 'prenom', 'email', 'telephone', 'fonction',
                 'is_contact_principal_devis', 'is_contact_principal_facture']

class ContactDetailSerializer(serializers.ModelSerializer):
    """Sérialiseur complet pour les détails d'un contact"""
    nom_complet = serializers.CharField(read_only=True)
    
    class Meta:
        model = Contact
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
        # Rendre le champ tier optionnel pour la validation
        extra_kwargs = {
            'tier': {'required': False}
        }

class AdresseListSerializer(serializers.ModelSerializer):
    """Sérialiseur optimisé pour les listes d'adresses"""
    class Meta:
        model = Adresse
        fields = ['id', 'libelle', 'ville', 'code_postal', 'is_facturation']

class AdresseDetailSerializer(serializers.ModelSerializer):
    """Sérialiseur complet pour les détails d'une adresse"""
    class Meta:
        model = Adresse
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at']
        # Rendre le champ tier optionnel pour la validation
        extra_kwargs = {
            'tier': {'required': False}
        }

class ActiviteTiersSerializer(serializers.ModelSerializer):
    """Sérialiseur pour les activités des tiers"""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    
    class Meta:
        model = ActiviteTiers
        fields = ['id', 'type', 'type_display', 'content', 'user_id', 'created_at']
        read_only_fields = ['created_at']

class TiersListSerializer(serializers.ModelSerializer):
    """Sérialiseur optimisé pour les listes de tiers"""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    relation_display = serializers.CharField(source='get_relation_display', read_only=True)
    contacts_count = serializers.SerializerMethodField()
    opportunities_count = serializers.SerializerMethodField()
    adresse_facturation = serializers.SerializerMethodField()

    class Meta:
        model = Tiers
        fields = [
            'id', 'nom', 'type', 'type_display', 'relation', 'relation_display',
            'siret', 'contacts_count', 'opportunities_count', 'adresse_facturation',
            'is_deleted', 'created_at'
        ]
        read_only_fields = ['created_at']

    def get_contacts_count(self, obj):
        """
        Compte optimisé des contacts utilisant les données préchargées
        """
        # Vérifier si les contacts sont préchargés
        if hasattr(obj, '_prefetched_objects_cache') and 'contacts' in obj._prefetched_objects_cache:
            # Utiliser les données préchargées (0 requête DB)
            return len(obj._prefetched_objects_cache['contacts'])
        else:
            # Fallback: comportement original (1 requête DB)
            return obj.contacts.count()
    
    def get_opportunities_count(self, obj):
        """
        Compte optimisé des opportunités utilisant les données préchargées
        """
        # Vérifier si les opportunités sont préchargées
        if hasattr(obj, '_prefetched_objects_cache') and 'opportunities' in obj._prefetched_objects_cache:
            # Utiliser les données préchargées (0 requête DB)
            return len(obj._prefetched_objects_cache['opportunities'])
        else:
            # Fallback: comportement original (1 requête DB)
            return obj.opportunities.count()

    def get_adresse_facturation(self, obj):
        """
        Récupère l'adresse de facturation optimisée avec les données préchargées
        """
        # Vérifier si les adresses sont préchargées
        if hasattr(obj, '_prefetched_objects_cache') and 'adresses' in obj._prefetched_objects_cache:
            # Utiliser les données préchargées (0 requête DB)
            adresses = obj._prefetched_objects_cache['adresses']
            for adresse in adresses:
                if adresse.is_facturation:
                    return AdresseListSerializer(adresse).data
            return None
        else:
            # Fallback: comportement original (1 requête DB)
            adresse = obj.adresses.filter(is_facturation=True).first()
            if adresse:
                return AdresseListSerializer(adresse).data
            return None

class TiersDetailSerializer(serializers.ModelSerializer):
    """Sérialiseur complet pour les détails d'un tier"""
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    relation_display = serializers.CharField(source='get_relation_display', read_only=True)
    contacts = ContactListSerializer(many=True, read_only=True)
    adresses = AdresseListSerializer(many=True, read_only=True)
    activites = ActiviteTiersSerializer(many=True, read_only=True)
    opportunities_stats = serializers.SerializerMethodField()

    class Meta:
        model = Tiers
        fields = '__all__'
        read_only_fields = ['created_at', 'updated_at', 'deleted_at']

    def get_opportunities_stats(self, obj):
        """
        Calcule les statistiques des opportunités avec données préchargées
        """
        # Vérifier si les opportunités sont préchargées
        if hasattr(obj, '_prefetched_objects_cache') and 'opportunities' in obj._prefetched_objects_cache:
            # Utiliser les données préchargées (0 requête DB)
            opportunities = obj._prefetched_objects_cache['opportunities']
        else:
            # Fallback: comportement original (1 requête DB)
            opportunities = obj.opportunities.all()
        
        # Calculs optimisés sur les données en mémoire
        total_amount = 0
        weighted_amount = 0
        won_count = 0
        active_count = 0
        
        for opp in opportunities:
            total_amount += opp.estimated_amount or 0
            weighted_amount += opp.weighted_amount or 0
            if opp.stage == 'won':
                won_count += 1
            elif opp.stage not in ['won', 'lost']:
                active_count += 1
        
        return {
            'count': len(opportunities),
            'total_amount': total_amount,
            'weighted_amount': weighted_amount,
            'won_count': won_count,
            'active_count': active_count,
        }

class TiersCreateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la création d'un tier avec validation spécifique"""
    adresses = AdresseDetailSerializer(many=True, required=False)
    contacts = ContactDetailSerializer(many=True, required=False)
    
    class Meta:
        model = Tiers
        fields = ['id', 'nom', 'type', 'relation', 'siret', 'tva', 'adresses', 'contacts']
        read_only_fields = ['id']

    def validate_siret(self, value):
        """Validation du numéro SIRET"""
        if value:
            if not value.isdigit() or len(value) != 14:
                raise serializers.ValidationError(_("Le numéro SIRET doit contenir 14 chiffres."))
            if Tiers.objects.filter(siret=value).exists():
                raise serializers.ValidationError(_("Ce numéro SIRET existe déjà."))
        return value

    def create(self, validated_data):
        """Création d'un tier avec adresses et contacts associés"""
        adresses_data = validated_data.pop('adresses', [])
        contacts_data = validated_data.pop('contacts', [])
        
        # Créer le tier principal
        tier = Tiers.objects.create(**validated_data)
        
        # Créer les adresses associées
        for adresse_data in adresses_data:
            Adresse.objects.create(tier=tier, **adresse_data)
        
        # Créer les contacts associés
        for contact_data in contacts_data:
            Contact.objects.create(tier=tier, **contact_data)
        
        return tier

class TiersUpdateSerializer(serializers.ModelSerializer):
    """Sérialiseur pour la mise à jour d'un tier"""
    class Meta:
        model = Tiers
        fields = ['nom', 'type', 'relation', 'siret', 'tva']
        read_only_fields = ['created_at', 'updated_at', 'deleted_at']

    def validate_siret(self, value):
        """Validation du numéro SIRET"""
        if value:
            if not value.isdigit() or len(value) != 14:
                raise serializers.ValidationError(_("Le numéro SIRET doit contenir 14 chiffres."))
            # Vérifier si le SIRET existe déjà pour un autre tier
            if Tiers.objects.exclude(pk=self.instance.pk).filter(siret=value).exists():
                raise serializers.ValidationError(_("Ce numéro SIRET existe déjà."))
        return value 