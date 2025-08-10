"""
API pour la gestion des opportunités
"""
import logging
import requests
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from django.db import models
from django.db.models import Count, Sum, Avg, Q
from django.conf import settings

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
        """Liste des opportunités"""
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        """Logique métier lors de la création"""
        serializer.save()

    def perform_update(self, serializer):
        """Logique métier lors de la mise à jour"""
        instance = serializer.save()
        logger.info(f"Opportunité {instance.id} mise à jour - Statut: {instance.stage}")

    def perform_destroy(self, instance):
        """Logique métier lors de la suppression"""
        instance.delete()

    @action(detail=False, methods=['get'])
    def kanban(self, request):
        """Vue spéciale pour l'interface Kanban"""
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
        
        return Response(kanban_data)

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
        
        try:
            # Validation de la transition (peut lever ValidationError)
            # Possibilité de forcer la transition avec le paramètre 'force'
            force_transition = request.data.get('force', False)
            self._validate_stage_transition(opportunity, new_stage, force=force_transition)
        except ValidationError as e:
            # Retourner l'erreur de validation avec le bon format
            if isinstance(e.detail, dict):
                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response(
                    {"error": str(e.detail)},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        serializer = OpportunityStageUpdateSerializer(
            opportunity,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(serializer.data)

    def _validate_stage_transition(self, opportunity, new_stage, force=False):
        """Valide si une transition de statut est autorisée"""
        current_stage = opportunity.stage
        
        # Validations existantes pour les opportunités fermées
        if current_stage == OpportunityStatus.WON:
            if new_stage != OpportunityStatus.NEGOTIATION:
                raise ValidationError("Une opportunité gagnée ne peut être modifiée qu'en négociation.")
        
        elif current_stage == OpportunityStatus.LOST:
            if new_stage != OpportunityStatus.NEGOTIATION:
                raise ValidationError("Une opportunité perdue ne peut être modifiée qu'en négociation.")
        
        # VALIDATION 1 : Transition vers négociation nécessite un devis envoyé
        # (sauf si force=True)
        if new_stage == OpportunityStatus.NEGOTIATION and current_stage != OpportunityStatus.NEGOTIATION:
            if not force and not self._has_sent_quote(opportunity.id):
                raise ValidationError({
                    "detail": "Un devis doit être envoyé avant de passer en négociation.",
                    "code": "QUOTE_REQUIRED_FOR_NEGOTIATION",
                    "suggestion": "Créez et envoyez un devis pour cette opportunité avant de la faire passer en négociation."
                })
        
        # VALIDATION 2 : Transition vers "gagnée" nécessite d'être passé par la négociation
        if new_stage == OpportunityStatus.WON and current_stage != OpportunityStatus.NEGOTIATION:
            raise ValidationError({
                "detail": "Une opportunité doit passer par l'étape négociation avant d'être marquée comme gagnée.",
                "code": "NEGOTIATION_REQUIRED_FOR_WON",
                "suggestion": "Faites d'abord passer cette opportunité en négociation, puis marquez-la comme gagnée."
            })
        
        return True

    def _has_sent_quote(self, opportunity_id):
        """Vérifie si cette opportunité a au moins un devis envoyé - SOA 100%"""
        logger.info(f"🔄 Migration SOA: vérification devis envoyés pour opportunité {opportunity_id} via API Gateway")
        
        try:
            # Import local pour éviter les imports circulaires
            from ..utils_soa import has_sent_quote_sync
            
            # Récupérer le tenant_id depuis la requête
            tenant_id = getattr(self.request, 'tenant_id', None)
            
            # SOA 100% - Communication via API Gateway
            return has_sent_quote_sync(
                opportunity_id=str(opportunity_id),
                tenant_id=tenant_id
            )
            
        except Exception as e:
            logger.error(f"❌ Erreur SOA lors de la vérification des devis pour opportunité {opportunity_id}: {e}")
            logger.info("🔄 Fallback: tentative avec l'ancienne méthode directe")
            
            # Fallback temporaire en cas d'erreur SOA
            try:
                # URL du service Documents
                documents_service_url = getattr(settings, 'DOCUMENTS_SERVICE_URL', 'http://localhost:8004')
                
                # Appel direct au service Documents (fallback)
                response = requests.get(
                    f"{documents_service_url}/api/quotes/",
                    params={
                        'opportunity_id': str(opportunity_id),
                        'status': 'sent'  # Statut "envoyé"
                    },
                    headers={
                        'X-Tenant-ID': getattr(self.request, 'tenant_id', None),
                        'Content-Type': 'application/json'
                    },
                    timeout=1  # Timeout réduit à 1 seconde
                )
                
                if response.status_code == 200:
                    data = response.json()
                    # Vérifier s'il y a au moins un devis envoyé
                    if isinstance(data, dict) and 'results' in data:
                        return len(data['results']) > 0
                    elif isinstance(data, list):
                        return len(data) > 0
                        
                return False
                
            except (requests.RequestException, requests.Timeout) as fallback_error:
                logger.warning(f"❌ Erreur fallback lors de la vérification des devis pour l'opportunité {opportunity_id}: {fallback_error}")
                # En cas d'erreur de communication, on autorise la transition (fail-safe)
                # pour éviter de bloquer complètement l'application
            return True
        except Exception as e:
            logger.error(f"Erreur inattendue lors de la vérification des devis: {e}")
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
        
        try:
            # Utiliser la validation standard pour s'assurer que toutes les règles sont respectées
            self._validate_stage_transition(opportunity, OpportunityStatus.WON)
        except ValidationError as e:
            # Retourner l'erreur de validation avec le bon format
            if isinstance(e.detail, dict):
                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)
            else:
                return Response(
                    {"error": str(e.detail)},
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
        
        # Debug: Afficher les données reçues
        logger.info(f"Backend - request.data recu: {request.data}")
        logger.info(f"Backend - Type de request.data: {type(request.data)}")
        logger.info(f"Backend - loss_description: {request.data.get('loss_description')} (type: {type(request.data.get('loss_description'))})")
        
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
        
        logger.info(f"Backend - Data prepare pour serializer: {data}")
        
        serializer = self.get_serializer(opportunity, data=data, partial=True)
        logger.info(f"Backend - Serializer cree, validation en cours...")
        
        if not serializer.is_valid():
            logger.error(f"Backend - Erreurs de validation: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        logger.info(f"Backend - Validation OK, mise a jour en cours...")
        serializer.save()
        logger.info(f"Backend - Mise a jour reussie!")
        
        return Response({
            "message": "Opportunité marquée comme perdue",
            "opportunity": serializer.data
        })

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques sur les opportunités"""
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
        
        return Response(stats_data) 