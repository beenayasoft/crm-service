"""
Serializers pour l'API REST du service CRM
"""
from rest_framework import serializers
from tenant_metier.models import Tiers, Adresse, Contact, ActiviteTiers

class AdresseSerializer(serializers.ModelSerializer):
    """Serializer pour les adresses"""
    
    class Meta:
        model = Adresse
        fields = [
            'id', 'libelle', 'rue', 'ville', 'code_postal', 
            'pays', 'facturation', 'date_creation', 'date_modification'
        ]
        read_only_fields = ['id', 'date_creation', 'date_modification']

class ContactSerializer(serializers.ModelSerializer):
    """Serializer pour les contacts"""
    
    nom_complet = serializers.ReadOnlyField()
    
    class Meta:
        model = Contact
        fields = [
            'id', 'nom', 'prenom', 'nom_complet', 'fonction', 
            'email', 'telephone', 'contact_principal_devis', 
            'contact_principal_facture', 'date_creation', 'date_modification'
        ]
        read_only_fields = ['id', 'nom_complet', 'date_creation', 'date_modification']

class ActiviteSerializer(serializers.ModelSerializer):
    """Serializer pour les activités"""
    
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    
    class Meta:
        model = ActiviteTiers
        fields = [
            'id', 'type', 'type_display', 'utilisateur_id', 
            'contenu', 'date'
        ]
        read_only_fields = ['id', 'type_display', 'date']

class TiersListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des tiers (vue allégée)"""
    
    relation_display = serializers.ReadOnlyField()
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    
    class Meta:
        model = Tiers
        fields = [
            'id', 'nom', 'type', 'type_display', 'relation', 
            'relation_display', 'siret', 'is_deleted', 'date_creation'
        ]
        read_only_fields = ['id', 'relation_display', 'type_display', 'date_creation']

class TiersDetailSerializer(serializers.ModelSerializer):
    """Serializer détaillé pour un tier avec ses relations"""
    
    adresses = AdresseSerializer(many=True, read_only=True)
    contacts = ContactSerializer(many=True, read_only=True)
    activites = ActiviteSerializer(many=True, read_only=True)
    relation_display = serializers.ReadOnlyField()
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    
    # Propriétés calculées
    is_client = serializers.ReadOnlyField()
    is_prospect = serializers.ReadOnlyField()
    is_fournisseur = serializers.ReadOnlyField()
    is_sous_traitant = serializers.ReadOnlyField()
    
    class Meta:
        model = Tiers
        fields = [
            'id', 'nom', 'type', 'type_display', 'relation', 'relation_display',
            'siret', 'tva', 'is_deleted', 'date_creation', 'date_modification',
            'is_client', 'is_prospect', 'is_fournisseur', 'is_sous_traitant',
            'adresses', 'contacts', 'activites'
        ]
        read_only_fields = [
            'id', 'relation_display', 'type_display', 'date_creation', 
            'date_modification', 'is_client', 'is_prospect', 
            'is_fournisseur', 'is_sous_traitant'
        ]

class TiersCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer pour la création et mise à jour des tiers"""
    
    class Meta:
        model = Tiers
        fields = [
            'nom', 'type', 'relation', 'siret', 'tva'
        ]
    
    def validate_siret(self, value):
        """Validation du SIRET"""
        if value and len(value) not in [0, 14]:
            raise serializers.ValidationError("Le SIRET doit contenir exactement 14 chiffres")
        return value
    
    def validate(self, data):
        """Validation globale"""
        # Si c'est une entreprise, le SIRET est recommandé
        if data.get('type') == Tiers.TYPE_ENTREPRISE and not data.get('siret'):
            # Pas d'erreur, juste un warning en logs
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Entreprise '{data.get('nom')}' créée sans SIRET")
        
        return data
