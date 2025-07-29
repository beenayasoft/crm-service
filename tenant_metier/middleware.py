import uuid
import logging
from django.db import connection, transaction, IntegrityError
import requests
from django.conf import settings
from django.core.cache import cache
from django.http import JsonResponse
from django_tenants.utils import get_tenant_model, schema_context
from django.core.management import call_command
from .models import Client, Domain

logger = logging.getLogger(__name__)

class HeaderTenantMiddleware:
    """
    Middleware unifié pour la gestion des tenants via headers HTTP.
    Remplace le middleware django-tenants standard pour plus de flexibilité.
    
    Fonctionnalités:
    1. Extraction du tenant_id depuis le header X-Tenant-ID
    2. Vérification de l'existence du tenant via le service tenant
    3. Création automatique du schéma si nécessaire
    4. Migration automatique des tables dans le schéma
    5. Sélection du schéma pour la requête
    """
    
    # Endpoints qui ne nécessitent pas de X-Tenant-ID header
    PUBLIC_ENDPOINTS = [
        '/health/',
        '/admin/',
        '/static/',
        '/favicon.ico',
    ]
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Vérifier si l'endpoint est public
        if any(request.path.startswith(endpoint) for endpoint in self.PUBLIC_ENDPOINTS):
            return self.get_response(request)
            
        tenant_id = request.headers.get('X-Tenant-ID')
        
        if not tenant_id:
            return JsonResponse({
                'error': 'Missing X-Tenant-ID header',
                'code': 'missing_tenant_id'
            }, status=400)

        try:
            # Valider que c'est un UUID valide
            try:
                tenant_uuid = uuid.UUID(tenant_id)
            except ValueError:
                return JsonResponse({
                    'error': 'X-Tenant-ID doit être un UUID valide',
                    'code': 'invalid_uuid_format'
                }, status=400)
            
            # Vérifier le cache d'abord
            cache_key = f'tenant_schema:{tenant_id}'
            schema_info = cache.get(cache_key)
            
            if not schema_info:
                # Appeler le service tenant
                tenant_service_url = getattr(settings, 'TENANT_SERVICE_URL', 'http://localhost:8001')
                response = requests.get(
                    f"{tenant_service_url}/api/tenants/{tenant_id}/",
                    headers={'Accept': 'application/json'},
                    timeout=5  # 5 secondes timeout
                )
                
                if not response.ok:
                    logger.error(f"Erreur lors de la récupération du tenant {tenant_id}: {response.status_code}")
                    return JsonResponse({
                        'error': 'Invalid tenant ID',
                        'code': 'invalid_tenant_id'
                    }, status=401)

                tenant_data = response.json()
                schema_info = {
                    'schema_name': tenant_data.get('schema_name', f"tenant_{str(tenant_uuid).replace('-', '_')}"),
                    'is_active': tenant_data.get('is_active', True),
                    'name': tenant_data.get('name', f"Tenant {tenant_id}")
                }
                
                # Mettre en cache pour 5 minutes
                cache.set(cache_key, schema_info, 300)
            
            if not schema_info.get('is_active'):
                return JsonResponse({
                    'error': 'Tenant is inactive',
                    'code': 'inactive_tenant'
                }, status=403)

            schema_name = schema_info.get('schema_name')
            if not schema_name:
                logger.error(f"Schéma manquant pour le tenant {tenant_id}")
                return JsonResponse({
                    'error': 'Missing schema configuration',
                    'code': 'missing_schema'
                }, status=500)

            # Récupérer ou créer le tenant dans notre base
            tenant = self._get_or_create_tenant(tenant_uuid, schema_name, schema_info.get('name'))
            
            # Définir le schéma PostgreSQL pour cette requête
            connection.set_tenant(tenant)
            
            # Ajouter les informations du tenant à la requête
            request.tenant = tenant
            request.tenant_id = tenant_id
            request.tenant_schema = schema_name
            request.tenant_name = schema_info.get('name')
            
            # Log pour le débogage
            logger.debug(f"Tenant activé: {tenant_id} (schema: {schema_name})")
            
            response = self.get_response(request)
            
            # Réinitialiser le schéma après la requête
            connection.set_schema_to_public()
            
            return response
            
        except requests.RequestException as e:
            logger.error(f"Erreur de connexion au service tenant: {str(e)}")
            return JsonResponse({
                'error': 'Tenant service unavailable',
                'code': 'tenant_service_error'
            }, status=503)
            
        except Exception as e:
            logger.error(f"Erreur inattendue dans le middleware tenant: {str(e)}")
            return JsonResponse({
                'error': 'Internal server error',
                'code': 'internal_error'
            }, status=500)
    
    def _get_or_create_tenant(self, tenant_uuid, schema_name, tenant_name):
        """
        Récupère un tenant par son UUID, ou le crée s'il n'existe pas.
        Gère les race conditions lors de créations simultanées.
        """
        try:
            # Essayer de trouver le tenant existant
            tenant = Client.objects.get(tenant_uuid=tenant_uuid)
            logger.debug(f"Tenant trouvé: {tenant.name}")
            return tenant
            
        except Client.DoesNotExist:
            # Le tenant n'existe pas, tenter de le créer
            logger.info(f"Création automatique du tenant {tenant_uuid}")
            try:
                return self._create_new_tenant(tenant_uuid, schema_name, tenant_name)
            except IntegrityError:
                # Race condition - le tenant a été créé entre temps par un autre thread
                logger.info(f"Tenant {tenant_uuid} créé par un autre thread, récupération...")
                return Client.objects.get(tenant_uuid=tenant_uuid)
    
    def _create_new_tenant(self, tenant_uuid, schema_name, tenant_name):
        """
        Crée un nouveau tenant avec son schéma et effectue les migrations.
        """
        # Utiliser une transaction atomique pour éviter les conflits
        with transaction.atomic():
            # Créer le tenant (auto_create_schema=True va créer le schéma)
            tenant = Client.objects.create(
                tenant_uuid=tenant_uuid,
                schema_name=schema_name,
                name=tenant_name,
            )
            
            # Créer un domaine par défaut pour le tenant (requis par django-tenants)
            Domain.objects.create(
                domain=f"{schema_name}.beenaya.app",
                tenant=tenant,
                is_primary=True
            )
            
            # Exécuter les migrations pour le nouveau schéma
            self._migrate_tenant_schema(tenant)
            
            logger.info(f"Nouveau tenant créé: {tenant.name} (schéma: {schema_name})")
            return tenant
    
    def _migrate_tenant_schema(self, tenant):
        """
        Exécute les migrations pour le schéma du tenant.
        """
        try:
            # Utiliser call_command qui gère automatiquement tous les paramètres
            call_command(
                'migrate_schemas',
                schema_name=tenant.schema_name,
                verbosity=0,  # Réduire le bruit dans les logs
                interactive=False
            )
            logger.info(f"Migrations exécutées pour le tenant {tenant.name}")
                
        except Exception as e:
            logger.error(f"Erreur lors des migrations pour {tenant.name}: {str(e)}")
            # Ne pas faire échouer la création du tenant pour une erreur de migration
            pass 