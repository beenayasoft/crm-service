"""
Vues pour l'API REST du service CRM avec schémas séparés
Plus besoin de MultiTenantMixin - l'isolation est automatique !
"""
import logging
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.paginator import Paginator
from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from tenant_metier.models import Tiers, Adresse, Contact, ActiviteTiers
from .serializers import (
    TiersListSerializer, TiersDetailSerializer, TiersCreateUpdateSerializer,
    AdresseSerializer, ContactSerializer, ActiviteSerializer
)

logger = logging.getLogger(__name__)

class TiersViewSet(viewsets.ModelViewSet):
    """
    ViewSet pour la gestion des tiers avec isolation automatique par schéma
    Plus besoin de filtrer par tenant_id !
    """
    
    queryset = Tiers.objects.filter(is_deleted=False)
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'relation']
    search_fields = ['nom', 'siret']
    ordering_fields = ['nom', 'date_creation', 'date_modification']
    ordering = ['-date_creation']
    
    def get_serializer_class(self):
        """Choisit le serializer selon l'action"""
        if self.action == 'list':
            return TiersListSerializer
        elif self.action == 'retrieve':
            return TiersDetailSerializer
        elif self.action in ['create', 'update', 'partial_update']:
            return TiersCreateUpdateSerializer
        return TiersListSerializer
    
    def perform_create(self, serializer):
        """Création avec log d'activité"""
        serializer.save()
        
        # Log de création
        user_id = self.request.META.get('HTTP_X_USER_ID')
        if user_id:
            ActiviteTiers.objects.create(
                tier=serializer.instance,
                type=ActiviteTiers.TYPE_CREATION,
                utilisateur_id=user_id,
                contenu=f"Tier '{serializer.instance.nom}' créé"
            )
        
        logger.info(f"Tier créé: {serializer.instance.nom} (schéma: {self.request.schema_name})")
    
    def perform_update(self, serializer):
        """Mise à jour avec log d'activité"""
        old_nom = serializer.instance.nom
        serializer.save()
        
        # Log de modification
        user_id = self.request.META.get('HTTP_X_USER_ID')
        if user_id:
            ActiviteTiers.objects.create(
                tier=serializer.instance,
                type=ActiviteTiers.TYPE_MODIFICATION,
                utilisateur_id=user_id,
                contenu=f"Tier modifié (ancien nom: {old_nom})"
            )
        
        logger.info(f"Tier modifié: {serializer.instance.nom}")
    
    def perform_destroy(self, instance):
        """Soft delete au lieu de suppression"""
        instance.delete()  # Utilise notre méthode de soft delete
        
        # Log d'archivage
        user_id = self.request.META.get('HTTP_X_USER_ID')
        if user_id:
            ActiviteTiers.objects.create(
                tier=instance,
                type=ActiviteTiers.TYPE_AUTRE,
                utilisateur_id=user_id,
                contenu=f"Tier '{instance.nom}' archivé"
            )
        
        logger.info(f"Tier archivé: {instance.nom}")
    
    @action(detail=True, methods=['post'])
    def restore(self, request, pk=None):
        """Restaurer un tier archivé"""
        tier = get_object_or_404(Tiers, pk=pk)  # Plus besoin de filtrer par tenant
        
        if not tier.is_deleted:
            return Response(
                {'error': 'Ce tier n\'est pas archivé'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        tier.restore()
        
        # Log de restauration
        user_id = self.request.META.get('HTTP_X_USER_ID')
        if user_id:
            ActiviteTiers.objects.create(
                tier=tier,
                type=ActiviteTiers.TYPE_AUTRE,
                utilisateur_id=user_id,
                contenu=f"Tier '{tier.nom}' restauré"
            )
        
        logger.info(f"Tier restauré: {tier.nom}")
        
        serializer = TiersDetailSerializer(tier)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def archived(self, request):
        """Lister les tiers archivés"""
        archived_tiers = Tiers.objects.filter(is_deleted=True)  # Automatiquement dans le bon schéma
        
        serializer = TiersListSerializer(archived_tiers, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Statistiques des tiers - Format compatible frontend"""
        queryset = self.get_queryset()
        
        # Filtrer si nécessaire
        if 'search' in request.query_params:
            queryset = self.filter_queryset(queryset)
        
        # Calculer les statistiques
        stats = {
            'total': queryset.count(),
            'client': queryset.filter(relation=Tiers.RELATION_CLIENT).count(),
            'prospect': queryset.filter(relation=Tiers.RELATION_PROSPECT).count(),
            'fournisseur': queryset.filter(relation=Tiers.RELATION_FOURNISSEUR).count(),
            'sous_traitant': queryset.filter(relation=Tiers.RELATION_SOUS_TRAITANT).count(),
        }
        
        return Response(stats)
        
    @action(detail=False, methods=['get'])
    def health(self, request):
        """Health check du service tiers"""
        import time
        import redis
        from django.conf import settings
        
        start_time = time.time()
        
        # Vérifier l'accès à la base de données
        db_status = 'healthy'
        db_error = None
        try:
            # Simple requête pour vérifier la connexion à la base de données
            count = Tiers.objects.count()
        except Exception as e:
            db_status = 'unhealthy'
            db_error = str(e)
        
        # Vérifier l'accès au cache Redis si configuré
        cache_status = 'not_configured'
        cache_error = None
        if hasattr(settings, 'CACHES') and settings.CACHES.get('default', {}).get('BACKEND', '').endswith('RedisCache'):
            try:
                redis_client = redis.Redis.from_url(settings.CACHES['default']['LOCATION'])
                redis_client.ping()
                cache_status = 'healthy'
            except Exception as e:
                cache_status = 'unhealthy'
                cache_error = str(e)
        
        # Déterminer le statut global
        if db_status == 'unhealthy':
            status = 'unhealthy'
        elif cache_status == 'unhealthy':
            status = 'degraded'
        else:
            status = 'healthy'
        
        # Calculer le temps de réponse
        response_time = time.time() - start_time
        
        return Response({
            'status': status,
            'details': {
                'database': {
                    'status': db_status,
                    'error': db_error
                },
                'cache': {
                    'status': cache_status,
                    'error': cache_error
                },
                'response_time': response_time,
                'tiers_count': Tiers.objects.count() if db_status == 'healthy' else None
            }
        })

    @action(detail=False, methods=['get'])
    def frontend_format(self, request):
        """Format spécial pour le frontend avec pagination et filtrage avancé"""

        # Récupérer les paramètres de pagination et filtrage
        page = int(request.query_params.get('page', 1))
        page_size = int(request.query_params.get('page_size', 20))
        search = request.query_params.get('search', '')
        type_filter = request.query_params.get('type', '')
        sort_by = request.query_params.get('sort', '-date_creation')  # Tri par défaut: date de création descendante
        status = request.query_params.get('status', 'active')  # Filtre par statut (active/inactive)

        # Filtrage initial par statut
        if status == 'inactive':
            queryset = Tiers.objects.filter(is_deleted=True)
        else:  # Par défaut, actifs seulement
            queryset = Tiers.objects.filter(is_deleted=False)

        # Recherche améliorée
        if search:
            from django.db.models import Q
            # Recherche sur plusieurs champs pour plus de flexibilité
            queryset = queryset.filter(
                Q(nom__icontains=search) |
                Q(siret__icontains=search) |
                Q(contacts__nom__icontains=search) |
                Q(contacts__prenom__icontains=search) |
                Q(contacts__email__icontains=search) |
                Q(contacts__telephone__icontains=search) |
                Q(adresses__ville__icontains=search)
            ).distinct()

        # Filtre par type avec logique plus claire
        if type_filter and type_filter != 'tous':
            # Mapping standardisé des noms
            type_mapping = {
                # Pluriels
                'clients': 'client',
                'fournisseurs': 'fournisseur',
                'prospects': 'prospect',
                'sous_traitants': 'sous_traitant',
                # Singuliers (pour être robuste aux deux formats)
                'client': 'client',
                'fournisseur': 'fournisseur',
                'prospect': 'prospect',
                'sous_traitant': 'sous_traitant'
            }
            # Utiliser le mapping ou la valeur originale si non trouvée
            relation_value = type_mapping.get(type_filter.lower(), type_filter)
            queryset = queryset.filter(relation=relation_value)

        # Tri personnalisé
        if sort_by:
            # Mapping des champs de tri frontend vers backend
            sort_mapping = {
                'name': 'nom',
                'date': 'date_creation',
                '-name': '-nom',
                '-date': '-date_creation'
            }
            # Utiliser le mapping ou la valeur originale
            db_sort = sort_mapping.get(sort_by, sort_by)
            queryset = queryset.order_by(db_sort)

        # OPTIMISATION: Précharger les relations pour éviter les requêtes N+1
        queryset = queryset.prefetch_related('adresses', 'contacts')

        # Pagination avec optimisations
        paginator = Paginator(queryset, page_size)
        current_page = paginator.get_page(page)

        # Adapter les données pour le frontend
        tiers_data = []
        for tier in current_page:
            # Récupérer l'adresse principale
            adresse_principale = tier.adresses.filter(facturation=True).first() or tier.adresses.first()

            # Récupérer le contact principal
            contact_principal = tier.contacts.filter(contact_principal_devis=True).first() or tier.contacts.first()

            # Construire l'adresse formatée
            address = ''
            if adresse_principale:
                parts = []
                if adresse_principale.rue:
                    parts.append(adresse_principale.rue)
                if adresse_principale.code_postal and adresse_principale.ville:
                    parts.append(f"{adresse_principale.code_postal} {adresse_principale.ville}")
                address = ', '.join(parts)

            # Construire le nom du contact
            contact = ''
            if contact_principal:
                if contact_principal.prenom and contact_principal.nom:
                    contact = f"{contact_principal.prenom} {contact_principal.nom}"
                elif contact_principal.prenom:
                    contact = contact_principal.prenom
                elif contact_principal.nom:
                    contact = contact_principal.nom

            tiers_data.append({
                'id': str(tier.id),
                'name': tier.nom,
                'type': [tier.relation],
                'contact': contact,
                'email': contact_principal.email if contact_principal else '',
                'phone': contact_principal.telephone if contact_principal else '',
                'address': address,
                'siret': tier.siret or '',
                'status': 'active' if not tier.is_deleted else 'inactive'
            })

        # Informations de pagination
        pagination = {
            'count': paginator.count,
            'num_pages': paginator.num_pages,
            'current_page': page,
            'page_size': page_size,
            'has_next': current_page.has_next(),
            'has_previous': current_page.has_previous(),
            'next_page': current_page.next_page_number() if current_page.has_next() else None,
            'previous_page': current_page.previous_page_number() if current_page.has_previous() else None,
        }
        
        return Response({
            'results': tiers_data,
            'pagination': pagination
        })

    @action(detail=True, methods=['get'])
    def vue_360(self, request, pk=None):
        """Vue 360° d'un tier avec toutes les informations groupées"""
        try:
            tier = self.get_object()
            serializer = TiersDetailSerializer(tier)

            # Structurer la réponse avec des onglets
            data = serializer.data.copy()  # Créer une copie pour éviter de modifier l'original
            data['onglets'] = {
                'infos': {
                    'adresses': data.pop('adresses', [])
                },
                'contacts': data.pop('contacts', []),
                'activites': data.pop('activites', [])
            }

            return Response(data)

        except Exception as e:
            # Journaliser l'erreur pour faciliter le débogage
            logger.error(f"Erreur dans vue_360 pour le tier {pk}: {str(e)}")
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

# Les autres ViewSets restent identiques car l'isolation est automatique
class AdresseViewSet(viewsets.ModelViewSet):
    serializer_class = AdresseSerializer
    
    def get_queryset(self):
        tier_id = self.kwargs.get('tier_pk')
        if tier_id:
            return Adresse.objects.filter(tier_id=tier_id)
        return Adresse.objects.none()
    
    def perform_create(self, serializer):
        tier_id = self.kwargs.get('tier_pk')
        tier = get_object_or_404(Tiers, pk=tier_id)
        serializer.save(tier=tier)

class ContactViewSet(viewsets.ModelViewSet):
    serializer_class = ContactSerializer
    
    def get_queryset(self):
        tier_id = self.kwargs.get('tier_pk')
        if tier_id:
            return Contact.objects.filter(tier_id=tier_id)
        return Contact.objects.none()
    
    def perform_create(self, serializer):
        tier_id = self.kwargs.get('tier_pk')
        tier = get_object_or_404(Tiers, pk=tier_id)
        serializer.save(tier=tier)

class ActiviteViewSet(viewsets.ModelViewSet):
    serializer_class = ActiviteSerializer
    http_method_names = ['get', 'post', 'put', 'patch']
    
    def get_queryset(self):
        tier_id = self.kwargs.get('tier_pk')
        if tier_id:
            return ActiviteTiers.objects.filter(tier_id=tier_id)
        return ActiviteTiers.objects.none()
    
    def perform_create(self, serializer):
        tier_id = self.kwargs.get('tier_pk')
        tier = get_object_or_404(Tiers, pk=tier_id)
        
        user_id = self.request.META.get('HTTP_X_USER_ID')
        if not user_id:
            from rest_framework.exceptions import ValidationError
            raise ValidationError({'error': 'Header X-User-ID requis pour créer une activité'})
        
        serializer.save(tier=tier, utilisateur_id=user_id)
