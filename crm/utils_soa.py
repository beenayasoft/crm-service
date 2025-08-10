"""
SOA-compliant utilities for crm-service
Communication via API Gateway uniquement - SOA 100%
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List
from django.conf import settings

logger = logging.getLogger(__name__)


def get_service_client():
    """Factory pour créer un ServiceClient configuré pour crm-service"""
    try:
        from soa.shared.service_client import create_crm_client
        return create_crm_client()
    except ImportError as e:
        logger.error(f"❌ ServiceClient non disponible: {e}")
        raise ImportError("ServiceClient requis pour SOA 100%. Vérifiez l'installation.")


async def get_quotes_for_opportunity_soa(
    opportunity_id: str, 
    status: Optional[str] = None,
    tenant_id: Optional[str] = None,
    auth_token: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Récupère les devis associés à une opportunité - VERSION SOA 100%
    Communication via API Gateway uniquement
    
    Args:
        opportunity_id: ID de l'opportunité
        status: Statut des devis à filtrer (optionnel)
        tenant_id: ID du tenant
        auth_token: Token JWT pour l'authentification
        
    Returns:
        List[Dict]: Liste des devis ou liste vide si erreur
    """
    try:
        client = get_service_client()
        
        # Construire les paramètres de la requête
        params = {'opportunity_id': str(opportunity_id)}
        if status:
            params['status'] = status
        
        # Communication via API Gateway
        response = await client.get(
            "/api/quotes/",
            params=params,
            tenant_id=tenant_id,
            auth_token=auth_token
        )
        
        if response.status_code == 200:
            quotes_data = response.json()
            logger.info(f"✅ Devis récupérés pour opportunité {opportunity_id} via API Gateway")
            return quotes_data.get('results', []) if isinstance(quotes_data, dict) else quotes_data
        else:
            logger.warning(f"⚠️  Erreur récupération devis via API Gateway (status: {response.status_code})")
            return []
            
    except Exception as e:
        logger.error(f"❌ Erreur lors de la récupération SOA des devis pour opportunité {opportunity_id}: {e}")
        return []


async def has_sent_quote_soa(
    opportunity_id: str, 
    tenant_id: Optional[str] = None,
    auth_token: Optional[str] = None
) -> bool:
    """
    Vérifie si une opportunité a au moins un devis envoyé - VERSION SOA 100%
    Communication via API Gateway uniquement
    
    Args:
        opportunity_id: ID de l'opportunité
        tenant_id: ID du tenant
        auth_token: Token JWT pour l'authentification
        
    Returns:
        bool: True si au moins un devis envoyé existe, False sinon
    """
    try:
        quotes = await get_quotes_for_opportunity_soa(
            opportunity_id, 
            status='sent',
            tenant_id=tenant_id,
            auth_token=auth_token
        )
        
        has_sent = len(quotes) > 0
        logger.info(f"✅ Vérification devis envoyés pour opportunité {opportunity_id}: {'Oui' if has_sent else 'Non'}")
        return has_sent
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de la vérification SOA des devis envoyés pour opportunité {opportunity_id}: {e}")
        return False


async def get_quote_statistics_soa(
    opportunity_id: str,
    tenant_id: Optional[str] = None,
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Récupère les statistiques des devis pour une opportunité - VERSION SOA 100%
    Communication via API Gateway uniquement
    
    Args:
        opportunity_id: ID de l'opportunité
        tenant_id: ID du tenant
        auth_token: Token JWT pour l'authentification
        
    Returns:
        Dict: Statistiques des devis
    """
    try:
        quotes = await get_quotes_for_opportunity_soa(
            opportunity_id,
            tenant_id=tenant_id,
            auth_token=auth_token
        )
        
        # Calculer les statistiques
        total_quotes = len(quotes)
        sent_quotes = len([q for q in quotes if q.get('status') == 'sent'])
        accepted_quotes = len([q for q in quotes if q.get('status') == 'accepted'])
        rejected_quotes = len([q for q in quotes if q.get('status') == 'rejected'])
        
        stats = {
            'total_quotes': total_quotes,
            'sent_quotes': sent_quotes,
            'accepted_quotes': accepted_quotes,
            'rejected_quotes': rejected_quotes,
            'has_sent_quote': sent_quotes > 0,
            'has_accepted_quote': accepted_quotes > 0
        }
        
        logger.info(f"✅ Statistiques devis calculées pour opportunité {opportunity_id}: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"❌ Erreur lors du calcul SOA des statistiques devis pour opportunité {opportunity_id}: {e}")
        return {
            'total_quotes': 0,
            'sent_quotes': 0,
            'accepted_quotes': 0,
            'rejected_quotes': 0,
            'has_sent_quote': False,
            'has_accepted_quote': False
        }


def run_async_in_sync(async_func, *args, **kwargs):
    """
    Utilitaire pour exécuter une fonction async dans un contexte synchrone Django
    Nécessaire pour la migration progressive des fonctions sync vers async
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(async_func(*args, **kwargs))


# ===== Fonctions de transition (Sync → Async) =====
# Ces fonctions permettent une migration progressive

def get_quotes_for_opportunity_sync(
    opportunity_id: str, 
    status: Optional[str] = None,
    tenant_id: Optional[str] = None,
    auth_token: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Version synchrone transitoire pour get_quotes_for_opportunity_soa"""
    return run_async_in_sync(get_quotes_for_opportunity_soa, opportunity_id, status, tenant_id, auth_token)


def has_sent_quote_sync(
    opportunity_id: str, 
    tenant_id: Optional[str] = None,
    auth_token: Optional[str] = None
) -> bool:
    """Version synchrone transitoire pour has_sent_quote_soa"""
    return run_async_in_sync(has_sent_quote_soa, opportunity_id, tenant_id, auth_token)


def get_quote_statistics_sync(
    opportunity_id: str,
    tenant_id: Optional[str] = None,
    auth_token: Optional[str] = None
) -> Dict[str, Any]:
    """Version synchrone transitoire pour get_quote_statistics_soa"""
    return run_async_in_sync(get_quote_statistics_soa, opportunity_id, tenant_id, auth_token)