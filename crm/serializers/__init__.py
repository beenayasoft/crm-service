"""
Exports des sérialiseurs
"""
from .tiers import (
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
from .opportunities import (
    OpportunityListSerializer,
    OpportunityDetailSerializer,
    OpportunityCreateSerializer,
    OpportunityUpdateSerializer,
    OpportunityStageUpdateSerializer
)

__all__ = [
    'TiersListSerializer',
    'TiersDetailSerializer',
    'TiersCreateSerializer',
    'TiersUpdateSerializer',
    'ContactListSerializer',
    'ContactDetailSerializer',
    'AdresseListSerializer',
    'AdresseDetailSerializer',
    'ActiviteTiersSerializer',
    'OpportunityListSerializer',
    'OpportunityDetailSerializer',
    'OpportunityCreateSerializer',
    'OpportunityUpdateSerializer',
    'OpportunityStageUpdateSerializer',
] 