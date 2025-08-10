"""
API pour la gestion des tiers
"""
import logging
from django.shortcuts import get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from ..models import Tiers, Contact, Adresse, ActiviteTiers
from ..serializers import (
    TiersListSerializer,
    TiersDetailSerializer,
    TiersCreateSerializer,
    TiersUpdateSerializer,
    ContactListSerializer,
    ContactDetailSerializer,
    AdresseListSerializer,
    AdresseDetailSerializer,
    ActiviteTiersSerializer
)

logger = logging.getLogger(__name__)

class TiersViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des tiers"""
    queryset = Tiers.objects.filter(is_deleted=False)
    serializer_class = TiersListSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'relation']
    search_fields = ['nom', 'siret']
    ordering_fields = ['nom', 'created_at', 'updated_at']
    ordering = ['-created_at']



    def get_serializer_class(self):
        """Sélectionne le serializer approprié selon l'action"""
        if self.action == 'list':
            return TiersListSerializer
        elif self.action == 'retrieve':
            return TiersDetailSerializer
        elif self.action == 'create':
            return TiersCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return TiersUpdateSerializer
        return TiersListSerializer

    def get_queryset(self):
        queryset = Tiers.objects.filter(is_deleted=False)
        logger.info(f"=== GET_QUERYSET DEBUG ===")
        logger.info(f"Queryset count: {queryset.count()}")
        return queryset
    
    def list(self, request, *args, **kwargs):
        """Override list pour ajouter des logs de débogage"""
        logger.info(f"=== DEBUG LIST ENDPOINT ===")
        logger.info(f"Tenant ID: {getattr(request, 'tenant_id', 'None')}")
        
        queryset = self.filter_queryset(self.get_queryset())
        logger.info(f"Filtered queryset count: {queryset.count()}")
        logger.info(f"Query parameters: {dict(request.GET)}")
        
        # Lister quelques tiers pour débugger
        for tier in queryset[:5]:  # Limité à 5 pour éviter trop de logs
            logger.info(f"Tier dans list: {tier.id} - {tier.nom} - relation: {tier.relation} - deleted: {tier.is_deleted}")
        
        logger.info(f"=== FIN DEBUG LIST ENDPOINT ===")
        
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Actions à effectuer après création d'un tier"""
        instance = serializer.save()
        logger.info(f"Tier créé avec succès: {instance.id} - {instance.nom}")

    def perform_update(self, serializer):
        """Actions à effectuer après mise à jour d'un tier"""
        instance = serializer.save()
        logger.info(f"Tier mis à jour: {instance.id} - {instance.nom}")

    def perform_destroy(self, instance):
        """Soft delete d'un tier"""
        instance.delete()  # Utilise la méthode soft delete du modèle
        logger.info(f"Tier archivé: {instance.id} - {instance.nom}")

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Retourne les statistiques des tiers"""
        try:
            # Utiliser EXACTEMENT le même queryset filtré que l'endpoint list
            # Cela applique tous les filtres DRF (filterset_fields, search, etc.)
            base_queryset = self.get_queryset()
            filtered_queryset = self.filter_queryset(base_queryset)
            
            # DEBUG: Logs pour comparer avec l'endpoint list
            logger.info(f"=== DEBUG STATS ENDPOINT ===")
            logger.info(f"Tenant ID: {getattr(request, 'tenant_id', 'None')}")
            logger.info(f"Base queryset count: {base_queryset.count()}")
            logger.info(f"Filtered queryset count: {filtered_queryset.count()}")
            logger.info(f"Query parameters: {dict(request.GET)}")
            
            # Lister tous les tiers dans le queryset filtré pour débugger
            for tier in filtered_queryset:
                logger.info(f"Tier dans stats: {tier.id} - {tier.nom} - relation: {tier.relation} - deleted: {tier.is_deleted}")
            
            stats = filtered_queryset.aggregate(
                total=Count('id', distinct=True),
                prospects=Count('id', filter=Q(relation='prospect'), distinct=True),
                clients=Count('id', filter=Q(relation='client'), distinct=True),
                fournisseurs=Count('id', filter=Q(relation='fournisseur'), distinct=True),
                sous_traitants=Count('id', filter=Q(relation='sous_traitant'), distinct=True),
                opportunities_total=Count('opportunities', distinct=True),
                opportunities_amount=Sum('opportunities__estimated_amount')
            )
            
            logger.info(f"Stats calculées: {stats}")
            logger.info(f"=== FIN DEBUG STATS ENDPOINT ===")
            
            return Response(stats)
        except Exception as e:
            logger.error(f"Erreur dans l'endpoint stats: {str(e)}")
            return Response(
                {'error': 'Erreur lors du calcul des statistiques'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['get'])
    def frontend_format(self, request):
        """Retourne la liste des tiers dans un format optimisé pour le frontend"""
        try:
                
            queryset = self.filter_queryset(self.get_queryset())
            
            # Utiliser la pagination Django REST
            page = self.paginate_queryset(queryset)
            
            if page is not None:
                # Format optimisé pour les selects du frontend
                formatted_data = []
                for tier in page:
                    formatted_data.append({
                        'id': str(tier.id),
                        'label': tier.nom,
                        'value': str(tier.id),
                        'type': tier.type,
                        'relation': tier.relation,
                        'relation_display': dict(Tiers.RELATION_CHOICES).get(tier.relation, tier.relation),
                        'siret': tier.siret or '',
                        'created_at': tier.created_at
                    })
                
                # Retourner avec pagination
                paginated_response = self.get_paginated_response(formatted_data)
                
                return paginated_response
            
            # Si pas de pagination, format simple
            formatted_data = []
            for tier in queryset:
                formatted_data.append({
                    'id': str(tier.id),
                    'label': tier.nom,
                    'value': str(tier.id),
                    'type': tier.type,
                    'relation': tier.relation,
                    'relation_display': dict(Tiers.RELATION_CHOICES).get(tier.relation, tier.relation),
                    'siret': tier.siret or '',
                    'created_at': tier.created_at
                })
            
            response_data = {
                'count': len(formatted_data),
                'next': None,
                'previous': None,
                'results': formatted_data
            }
            
            return Response(response_data)
        except Exception as e:
            logger.error(f"Erreur dans l'endpoint frontend_format: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la récupération des données'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def vue_360(self, request, pk=None):
        """Vue 360° d'un tier avec toutes ses données associées"""
        try:
            logger.info(f"Récupération vue_360 pour le tier {pk}")
            tier = get_object_or_404(Tiers, pk=pk)
            
            # Utiliser le serializer détaillé pour toutes les données
            serializer = TiersDetailSerializer(tier)
            data = serializer.data
            
            # Réorganiser les données dans le format attendu par le frontend
            response_data = {
                'id': data['id'],
                'nom': data['nom'],
                'type': data['type'],
                'relation': data['relation'],
                'siret': data['siret'],
                'tva': data['tva'],
                'is_deleted': data['is_deleted'],
                'created_at': data['created_at'],
                'updated_at': data['updated_at'],
                'onglets': {
                    'infos': {
                        'adresses': data['adresses'] or []
                    },
                    'contacts': data['contacts'] or [],
                    'activites': data['activites'] or []
                }
            }
            
            logger.info(f"Vue_360 récupérée avec succès pour le tier {pk}")
            return Response(response_data)
            
        except Exception as e:
            logger.error(f"Erreur dans vue_360 pour le tier {pk}: {str(e)}")
            return Response(
                {'error': f'Erreur lors de la récupération du tier {pk}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restaurer un tier archivé"""
        try:
            tier = get_object_or_404(Tiers, pk=pk)
            tier.restore()
            
            serializer = TiersDetailSerializer(tier)
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Erreur lors de la restauration du tier {pk}: {str(e)}")
            return Response(
                {'error': 'Erreur lors de la restauration'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class ContactViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des contacts"""
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['tier', 'is_contact_principal_devis', 'is_contact_principal_facture']
    search_fields = ['nom', 'prenom', 'email', 'telephone']

    def get_queryset(self):
        return Contact.objects.select_related('tier')

    def get_serializer_class(self):
        if self.action == 'list':
            return ContactListSerializer
        return ContactDetailSerializer

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.delete()

class AdresseViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des adresses"""
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['tier', 'is_facturation']
    search_fields = ['rue', 'ville', 'code_postal']

    def get_queryset(self):
        return Adresse.objects.select_related('tier')

    def get_serializer_class(self):
        if self.action == 'list':
            return AdresseListSerializer
        return AdresseDetailSerializer

    def perform_create(self, serializer):
        serializer.save()

    def perform_update(self, serializer):
        serializer.save()

    def perform_destroy(self, instance):
        instance.delete()

class ActiviteTiersViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des activités"""
    serializer_class = ActiviteTiersSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['tier', 'type']
    ordering = ['-created_at']

    def get_queryset(self):
        return ActiviteTiers.objects.select_related('tier') 