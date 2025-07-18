from django.shortcuts import render
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from django.db.models import Count, Sum, Avg, Q, F
from .services import OpportunityStatsService
from django.db import models
import hashlib
import json
import logging

from .models import Opportunity, OpportunityStatus
from .serializers import (
    OpportunitySerializer, 
    OpportunityListSerializer,
    OpportunityKanbanSerializer,
    OpportunityStageUpdateSerializer,
    OpportunityCreateSerializer,
    OpportunityStatsSerializer
)
from tenant_metier.models import Tiers

logger = logging.getLogger(__name__)

class OpportunityViewSet(viewsets.ModelViewSet):
    """ViewSet complet pour la gestion des opportunités avec actions métier"""
    
    queryset = Opportunity.objects.select_related('tier').order_by('-created_at')
    permission_classes = [AllowAny]  # La sécurité est gérée par l'API Gateway et le middleware tenant
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['stage', 'source', 'tier', 'assigned_to']
    search_fields = ['name', 'description', 'tier__nom']
    ordering_fields = ['created_at', 'updated_at', 'expected_close_date', 'estimated_amount', 'probability']
    ordering = ['-created_at']

    def _get_cache_key(self, action, **kwargs):
        """Génère une clé de cache unique basée sur l'action et les paramètres"""
        # Utiliser le tenant_id du schéma actuel comme partie de la clé
        tenant_id = getattr(self.request, 'tenant_id', 'public')
        
        # Créer un hash des paramètres pour une clé unique
        params_hash = hashlib.md5(
            json.dumps(kwargs, sort_keys=True, default=str).encode()
        ).hexdigest()[:8]
        
        return f"opportunities_{action}_{tenant_id}_{params_hash}"
    
    def _invalidate_cache(self):
        """Invalide le cache pour ce tenant"""
        tenant_id = getattr(self.request, 'tenant_id', 'public')
        
        # Patterns de clés à invalider
        cache_patterns = [
            f"opportunities_list_{tenant_id}_*",
            f"opportunities_kanban_{tenant_id}_*", 
            f"opportunities_stats_{tenant_id}_*"
        ]
        
        # Note: Django cache ne supporte pas les wildcards nativement
        # On invalide les clés communes avec et sans hash
        common_keys = [
            f"opportunities_list_{tenant_id}_",
            f"opportunities_kanban_{tenant_id}_",
            f"opportunities_stats_{tenant_id}_"
        ]
        
        # Ajouter des clés avec des hash courants pour assurer l'invalidation complète
        for i in range(10):
            common_keys.append(f"opportunities_stats_{tenant_id}_{i}")
        
        # Supprimer explicitement la clé des stats qui est la plus importante pour l'UI
        cache.delete(f"opportunities_stats_{tenant_id}_")
        
        # Supprimer toutes les clés identifiées
        cache.delete_many(common_keys)
        
        logger.info(f"Cache invalidé pour tenant {tenant_id}")

    def get_queryset(self):
        """QuerySet optimisé selon l'action"""
        base_queryset = Opportunity.objects.all()
        
        # Optimisations spécifiques par action
        if hasattr(self, 'action'):
            if self.action == 'list':
                # Pour la liste, on évite les gros champs et on optimise les relations
                return base_queryset.select_related('tier').defer(
                    'description', 'loss_description'
                ).order_by('-created_at')
            
            elif self.action == 'kanban':
                # Pour le kanban, on a besoin des données complètes mais optimisées
                return base_queryset.select_related('tier').order_by('-created_at')
            
            elif self.action == 'stats':
                # Pour les stats, on n'a besoin que des champs de calcul
                return base_queryset.only(
                    'id', 'stage', 'estimated_amount', 'probability', 
                    'closed_at', 'created_at'
                )
            
            elif self.action == 'retrieve':
                # Pour le détail, on charge tout avec les relations
                return base_queryset.select_related('tier')
        
        # QuerySet par défaut
        return base_queryset.select_related('tier').order_by('-created_at')

    def list(self, request, *args, **kwargs):
        """Liste des opportunités avec cache Redis"""
        # Générer la clé de cache
        cache_key = self._get_cache_key('list', 
            filters=request.GET.dict(),
            page=request.GET.get('page', 1)
        )
        
        # Essayer de récupérer depuis le cache
        cached_data = cache.get(cache_key)
        if cached_data:
            response = Response(cached_data)
            response['X-Cache-Status'] = 'HIT'
            return response
        
        # Si pas en cache, utiliser la méthode parent
        response = super().list(request, *args, **kwargs)
        
        # Mettre en cache pour 30 secondes
        cache.set(cache_key, response.data, 30)
        
        response['X-Cache-Status'] = 'MISS'
        return response

    def get_serializer_class(self):
        """Sélectionne le serializer approprié selon l'action"""
        if self.action == 'list':
            return OpportunityListSerializer
        elif self.action == 'kanban':
            return OpportunityKanbanSerializer
        elif self.action == 'create':
            return OpportunityCreateSerializer
        elif self.action in ['update_stage', 'mark_won', 'mark_lost']:
            return OpportunityStageUpdateSerializer
        return OpportunitySerializer

    def perform_create(self, serializer):
        """Logique métier lors de la création"""
        serializer.save()
        # Invalider le cache après création
        self._invalidate_cache()

    def perform_update(self, serializer):
        """Logique métier lors de la mise à jour"""
        # Sauvegarder les modifications
        instance = serializer.save()
        
        # Invalider le cache pour assurer la cohérence des données
        self._invalidate_cache()
        
        # Log pour débogage
        logger.info(f"Opportunité {instance.id} mise à jour - Statut: {instance.stage}")

    def perform_destroy(self, instance):
        """Logique métier lors de la suppression"""
        instance.delete()
        # Invalider le cache après suppression
        self._invalidate_cache()

    @action(detail=False, methods=['get'])
    def kanban(self, request):
        """Vue spéciale pour l'interface Kanban avec cache Redis"""
        # Générer la clé de cache
        cache_key = self._get_cache_key('kanban', filters=request.GET.dict())
        
        # Essayer de récupérer depuis le cache
        cached_data = cache.get(cache_key)
        if cached_data:
            response = Response(cached_data)
            response['X-Cache-Status'] = 'HIT'
            return response
        
        # Si pas en cache, calculer les données
        opportunities = self.get_queryset()
        
        # Organiser par statut pour le Kanban avec une seule requête optimisée
        kanban_data = {}
        
        # Pré-charger toutes les données par stage en une fois
        stage_counts = opportunities.values('stage').annotate(
            count=Count('id'),
            total_amount=Sum('estimated_amount')
        )
        
        # Créer un dictionnaire pour les compteurs
        stage_stats = {item['stage']: item for item in stage_counts}
        
        for stage_choice in OpportunityStatus.choices:
            stage_code, stage_label = stage_choice
            stage_opportunities = opportunities.filter(stage=stage_code)
            
            # Utiliser les stats pré-calculées
            stage_stat = stage_stats.get(stage_code, {'count': 0, 'total_amount': 0})
            
            kanban_data[stage_code] = {
                'label': stage_label,
                'count': stage_stat['count'],
                'total_amount': float(stage_stat['total_amount'] or 0),
                'opportunities': OpportunityKanbanSerializer(stage_opportunities, many=True).data
            }
        
        # Mettre en cache pour 30 secondes
        cache.set(cache_key, kanban_data, 30)
        
        response = Response(kanban_data)
        response['X-Cache-Status'] = 'MISS'
        return response

    @action(detail=True, methods=['patch'])
    def update_stage(self, request, pk=None):
        """Mise à jour du statut d'une opportunité avec validation métier"""
        opportunity = self.get_object()
        
        # Récupérer le nouveau statut
        new_stage = request.data.get('stage')
        if not new_stage:
            return Response({"error": "Le statut est obligatoire"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Valider la transition de statut
        if not self._validate_stage_transition(opportunity, new_stage):
            return Response({"error": "Transition de statut non autorisée"}, status=status.HTTP_400_BAD_REQUEST)
        
        # Utiliser le serializer spécifique pour les mises à jour de statut
        serializer = OpportunityStageUpdateSerializer(opportunity, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        # Invalider le cache après la mise à jour du statut
        self._invalidate_cache()
        
        return Response(serializer.data)

    def _validate_stage_transition(self, opportunity, new_stage):
        """Valide si une transition de statut est autorisée selon les règles métier"""
        current_stage = opportunity.stage
        
        # Règles de transition
        if current_stage == OpportunityStatus.WON:
            # Une opportunité gagnée ne peut être remise qu'en négociation
            return new_stage == OpportunityStatus.NEGOTIATION
        
        elif current_stage == OpportunityStatus.LOST:
            # Une opportunité perdue ne peut être remise qu'en négociation
            return new_stage == OpportunityStatus.NEGOTIATION
        
        # Toutes les autres transitions sont autorisées
        return True

    @action(detail=True, methods=['post'])
    def mark_won(self, request, pk=None):
        """Marquer une opportunité comme gagnée"""
        opportunity = self.get_object()
        
        # Vérifier si l'opportunité est déjà gagnée
        if opportunity.stage == OpportunityStatus.WON:
            return Response(
                {"message": "Cette opportunité est déjà marquée comme gagnée"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Vérifier si l'opportunité est perdue
        if opportunity.stage == OpportunityStatus.LOST:
            return Response(
                {"error": "Impossible de marquer une opportunité perdue comme gagnée. Remettez-la d'abord en négociation."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Préparer les données pour la mise à jour
        data = {
            'stage': OpportunityStatus.WON,
            'project_id': request.data.get('project_id')
        }
        
        # Utiliser le serializer pour validation et mise à jour
        serializer = self.get_serializer(opportunity, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Invalider explicitement le cache des statistiques
        self._invalidate_cache()
        
        return Response({
            "message": "Opportunité marquée comme gagnée",
            "opportunity": serializer.data
        })

    @action(detail=True, methods=['post'])
    def mark_lost(self, request, pk=None):
        """Marquer une opportunité comme perdue"""
        opportunity = self.get_object()
        
        # Vérifier si l'opportunité est déjà perdue
        if opportunity.stage == OpportunityStatus.LOST:
            return Response(
                {"message": "Cette opportunité est déjà marquée comme perdue"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Vérifier si l'opportunité est gagnée
        if opportunity.stage == OpportunityStatus.WON:
            return Response(
                {"error": "Impossible de marquer une opportunité gagnée comme perdue. Remettez-la d'abord en négociation."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Vérifier si la raison de perte est fournie
        if not request.data.get('loss_reason'):
            return Response(
                {"error": "La raison de perte est obligatoire"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Préparer les données pour la mise à jour
        data = {
            'stage': OpportunityStatus.LOST,
            'loss_reason': request.data.get('loss_reason'),
            'loss_description': request.data.get('loss_description')
        }
        
        # Utiliser le serializer pour validation et mise à jour
        serializer = self.get_serializer(opportunity, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        # Invalider explicitement le cache des statistiques
        self._invalidate_cache()
        
        return Response({
            "message": "Opportunité marquée comme perdue",
            "opportunity": serializer.data
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques sur les opportunités avec cache Redis"""
        # Générer la clé de cache
        cache_key = self._get_cache_key('stats')
        
        # Essayer de récupérer depuis le cache
        cached_data = cache.get(cache_key)
        if cached_data:
            response = Response(cached_data)
            response['X-Cache-Status'] = 'HIT'
            return response
        
        # Si pas en cache, calculer les statistiques
        stats_service = OpportunityStatsService()
        stats_data = stats_service.get_stats()
        
        # Pas besoin de serializer car le format est déjà adapté pour le frontend
        # Le service retourne directement le bon format
    
        # Mettre en cache pour 10 secondes (réduit pour plus de réactivité)
        cache.set(cache_key, stats_data, 10)

        response = Response(stats_data)
        response['X-Cache-Status'] = 'MISS'
        return response