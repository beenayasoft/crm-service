"""
API pour la gestion des opportunités
"""
import logging
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.core.cache import cache
from django.db import models
from django.db.models import Count, Sum, Avg, Q
import hashlib
import json

from ..models import Opportunity, OpportunityStatus
from ..serializers import (
    OpportunityListSerializer,
    OpportunityDetailSerializer,
    OpportunityCreateSerializer,
    OpportunityUpdateSerializer,
    OpportunityStageUpdateSerializer
)

logger = logging.getLogger(__name__)

class OpportunityViewSet(viewsets.ModelViewSet):
    """ViewSet pour la gestion des opportunités"""
    queryset = Opportunity.objects.select_related('tier').order_by('-created_at')
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['stage', 'source', 'tier', 'assigned_to']
    search_fields = ['name', 'description', 'tier__nom']
    ordering_fields = ['created_at', 'updated_at', 'expected_close_date', 'estimated_amount', 'probability']
    ordering = ['-created_at']

    def _get_cache_key(self, action, **kwargs):
        """Génère une clé de cache unique"""
        tenant_id = getattr(self.request, 'tenant_id', 'public')
        params_hash = hashlib.md5(
            json.dumps(kwargs, sort_keys=True, default=str).encode()
        ).hexdigest()[:8]
        return f"opportunities_{action}_{tenant_id}_{params_hash}"

    def _invalidate_cache(self):
        """Invalide le cache pour ce tenant"""
        tenant_id = getattr(self.request, 'tenant_id', 'public')
        common_keys = [
            f"opportunities_list_{tenant_id}_",
            f"opportunities_kanban_{tenant_id}_",
            f"opportunities_stats_{tenant_id}_"
        ]
        cache.delete_many(common_keys)
        logger.info(f"Cache invalidé pour tenant {tenant_id}")

    def get_queryset(self):
        """QuerySet optimisé selon l'action"""
        base_queryset = Opportunity.objects.all()
        
        if hasattr(self, 'action'):
            if self.action == 'list':
                return base_queryset.select_related('tier').defer(
                    'description', 'loss_description'
                ).order_by('-created_at')
            
            elif self.action == 'kanban':
                return base_queryset.select_related('tier').order_by('-created_at')
            
            elif self.action == 'stats':
                return base_queryset.only(
                    'id', 'stage', 'estimated_amount', 'probability',
                    'closed_at', 'created_at'
                )
            
            elif self.action == 'retrieve':
                return base_queryset.select_related('tier')
        
        return base_queryset.select_related('tier').order_by('-created_at')

    def get_serializer_class(self):
        """Sélectionne le serializer approprié selon l'action"""
        if self.action == 'list':
            return OpportunityListSerializer
        elif self.action == 'retrieve':
            return OpportunityDetailSerializer
        elif self.action == 'create':
            return OpportunityCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return OpportunityUpdateSerializer
        elif self.action in ['update_stage', 'mark_won', 'mark_lost']:
            return OpportunityStageUpdateSerializer
        return OpportunityDetailSerializer

    def list(self, request, *args, **kwargs):
        """Liste des opportunités avec cache"""
        cache_key = self._get_cache_key('list',
            filters=request.GET.dict(),
            page=request.GET.get('page', 1)
        )
        
        cached_data = cache.get(cache_key)
        if cached_data:
            response = Response(cached_data)
            response['X-Cache-Status'] = 'HIT'
            return response
        
        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, 30)
        response['X-Cache-Status'] = 'MISS'
        return response

    def perform_create(self, serializer):
        """Logique métier lors de la création"""
        serializer.save()
        self._invalidate_cache()

    def perform_update(self, serializer):
        """Logique métier lors de la mise à jour"""
        instance = serializer.save()
        self._invalidate_cache()
        logger.info(f"Opportunité {instance.id} mise à jour - Statut: {instance.stage}")

    def perform_destroy(self, instance):
        """Logique métier lors de la suppression"""
        instance.delete()
        self._invalidate_cache()

    @action(detail=False, methods=['get'])
    def kanban(self, request):
        """Vue spéciale pour l'interface Kanban avec cache"""
        cache_key = self._get_cache_key('kanban', filters=request.GET.dict())
        
        cached_data = cache.get(cache_key)
        if cached_data:
            response = Response(cached_data)
            response['X-Cache-Status'] = 'HIT'
            return response
        
        opportunities = self.get_queryset()
        
        # Organiser par statut pour le Kanban
        kanban_data = {}
        
        # Pré-charger les statistiques par stage
        stage_counts = opportunities.values('stage').annotate(
            count=Count('id'),
            total_amount=Sum('estimated_amount')
        )
        stage_stats = {item['stage']: item for item in stage_counts}
        
        for stage_choice in OpportunityStatus.choices:
            stage_code, stage_label = stage_choice
            stage_opportunities = opportunities.filter(stage=stage_code)
            
            stage_stat = stage_stats.get(stage_code, {'count': 0, 'total_amount': 0})
            
            kanban_data[stage_code] = {
                'label': stage_label,
                'count': stage_stat['count'],
                'total_amount': float(stage_stat['total_amount'] or 0),
                'opportunities': OpportunityListSerializer(stage_opportunities, many=True).data
            }
        
        cache.set(cache_key, kanban_data, 30)
        response = Response(kanban_data)
        response['X-Cache-Status'] = 'MISS'
        return response

    @action(detail=True, methods=['patch'])
    def update_stage(self, request, pk=None):
        """Mise à jour du statut d'une opportunité"""
        opportunity = self.get_object()
        
        new_stage = request.data.get('stage')
        if not new_stage:
            return Response(
                {"error": "Le statut est obligatoire"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not self._validate_stage_transition(opportunity, new_stage):
            return Response(
                {"error": "Transition de statut non autorisée"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = OpportunityStageUpdateSerializer(
            opportunity,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        self._invalidate_cache()
        return Response(serializer.data)

    def _validate_stage_transition(self, opportunity, new_stage):
        """Valide si une transition de statut est autorisée"""
        current_stage = opportunity.stage
        
        if current_stage == OpportunityStatus.WON:
            return new_stage == OpportunityStatus.NEGOTIATION
        
        elif current_stage == OpportunityStatus.LOST:
            return new_stage == OpportunityStatus.NEGOTIATION
        
        return True

    @action(detail=True, methods=['post'])
    def mark_won(self, request, pk=None):
        """Marquer une opportunité comme gagnée"""
        opportunity = self.get_object()
        
        if opportunity.stage == OpportunityStatus.WON:
            return Response(
                {"message": "Cette opportunité est déjà marquée comme gagnée"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if opportunity.stage == OpportunityStatus.LOST:
            return Response(
                {"error": "Impossible de marquer une opportunité perdue comme gagnée. Remettez-la d'abord en négociation."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = {
            'stage': OpportunityStatus.WON,
            'project_id': request.data.get('project_id')
        }
        
        serializer = self.get_serializer(opportunity, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            "message": "Opportunité marquée comme gagnée",
            "opportunity": serializer.data
        })

    @action(detail=True, methods=['post'])
    def mark_lost(self, request, pk=None):
        """Marquer une opportunité comme perdue"""
        opportunity = self.get_object()
        
        if opportunity.stage == OpportunityStatus.LOST:
            return Response(
                {"message": "Cette opportunité est déjà marquée comme perdue"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if opportunity.stage == OpportunityStatus.WON:
            return Response(
                {"error": "Impossible de marquer une opportunité gagnée comme perdue. Remettez-la d'abord en négociation."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not request.data.get('loss_reason'):
            return Response(
                {"error": "La raison de perte est obligatoire"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        data = {
            'stage': OpportunityStatus.LOST,
            'loss_reason': request.data.get('loss_reason'),
            'loss_description': request.data.get('loss_description')
        }
        
        serializer = self.get_serializer(opportunity, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        
        return Response({
            "message": "Opportunité marquée comme perdue",
            "opportunity": serializer.data
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques sur les opportunités avec cache"""
        cache_key = self._get_cache_key('stats')
        
        cached_data = cache.get(cache_key)
        if cached_data:
            response = Response(cached_data)
            response['X-Cache-Status'] = 'HIT'
            return response
        
        queryset = self.get_queryset()
        
        # Statistiques globales
        total_stats = queryset.aggregate(
            count=Count('id'),
            total_amount=Sum('estimated_amount'),
            avg_amount=Avg('estimated_amount'),
            avg_probability=Avg('probability')
        )
        
        # Statistiques par stage
        stage_stats = queryset.values(
            'stage'
        ).annotate(
            count=Count('id'),
            total_amount=Sum('estimated_amount'),
            avg_probability=Avg('probability')
        )
        
        # Pipeline pondéré
        weighted_pipeline = queryset.exclude(
            stage__in=[OpportunityStatus.WON, OpportunityStatus.LOST]
        ).aggregate(
            total=Sum('estimated_amount'),
            weighted_total=Sum(
                'estimated_amount', 
                filter=Q(probability__gt=0),
                output_field=models.DecimalField(max_digits=12, decimal_places=2)
            ) * models.Value(0.01, output_field=models.DecimalField(max_digits=5, decimal_places=2))
        )
        
        stats_data = {
            'total_stats': total_stats,
            'stage_stats': stage_stats,
            'weighted_pipeline': weighted_pipeline
        }
        
        cache.set(cache_key, stats_data, 10)  # Cache plus court pour les stats
        
        response = Response(stats_data)
        response['X-Cache-Status'] = 'MISS'
        return response 