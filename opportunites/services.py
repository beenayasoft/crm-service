from django.db.models import Count, Q, Sum
from decimal import Decimal
from .models import Opportunity, OpportunityStatus

class OpportunityStatsService:
    def get_stats(self, tenant_id=None):
        """
        Calcule les statistiques des opportunités pour un tenant donné
        Note: tenant_id n'est plus nécessaire car nous utilisons des schémas séparés
        """
        # Requête de base (pas besoin de filtrer par tenant car nous sommes dans le bon schéma)
        queryset = Opportunity.objects.all()
        
        # Statistique totale
        total = queryset.count()
        
        # Statistiques par étape - format simplifié pour le frontend
        by_stage = {}
        stage_stats = queryset.values('stage').annotate(count=Count('id'))
        
        # Initialiser toutes les étapes possibles à 0
        for stage_choice in OpportunityStatus.choices:
            by_stage[stage_choice[0]] = 0
            
        # Remplir avec les valeurs réelles
        for stat in stage_stats:
            stage = stat['stage']
            by_stage[stage] = stat['count']
        
        # Calcul du montant total
        total_amount = queryset.aggregate(total=Sum('estimated_amount'))['total'] or 0
        
        # Calcul des opportunités en cours (logique métier centralisée ici)
        in_progress_statuses = [OpportunityStatus.NEW, OpportunityStatus.NEEDS_ANALYSIS, OpportunityStatus.NEGOTIATION]
        in_progress_count = queryset.filter(stage__in=in_progress_statuses).count()
        
        # Calcul du taux de conversion
        won_count = by_stage.get(OpportunityStatus.WON, 0)
        lost_count = by_stage.get(OpportunityStatus.LOST, 0)
        closed_count = won_count + lost_count
        conversion_rate = round((won_count / closed_count * 100), 1) if closed_count > 0 else 0
        
        # Calculer les montants pondérés et gagnés pour le frontend
        won_amount = queryset.filter(stage=OpportunityStatus.WON).aggregate(total=Sum('estimated_amount'))['total'] or Decimal('0')
        weighted_amount = Decimal('0')
        for status in in_progress_statuses:
            # Pondération selon la probabilité associée à chaque statut
            if status == OpportunityStatus.NEW:
                weight = 0.1  # 10%
            elif status == OpportunityStatus.NEEDS_ANALYSIS:
                weight = 0.3  # 30%
            elif status == OpportunityStatus.NEGOTIATION:
                weight = 0.6  # 60%
            else:
                weight = 0
                
            status_amount = queryset.filter(stage=status).aggregate(total=Sum('estimated_amount'))['total'] or Decimal('0')
            weighted_amount += status_amount * Decimal(str(weight))
        
        # Format adapté pour le frontend
        return {
            'total': total,
            'byStage': by_stage,  # camelCase pour le frontend
            'totalAmount': float(total_amount),  # Convertir en float pour JSON
            'weightedAmount': float(weighted_amount),  # Nouveau champ pour le frontend
            'wonAmount': float(won_amount),  # Nouveau champ pour le frontend
            'inProgressCount': in_progress_count,  # camelCase pour le frontend
            'conversionRate': conversion_rate  # camelCase pour le frontend
        }