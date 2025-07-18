"""
Commande Django pour appliquer les migrations manquantes aux schémas tenant existants
"""

import logging
from django.core.management.base import BaseCommand
from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Applique les migrations manquantes aux schémas tenant existants'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Affiche les actions sans les exécuter',
        )
        parser.add_argument(
            '--tenant-id',
            type=str,
            help='Appliquer les migrations à un tenant spécifique seulement',
        )

    def handle(self, *args, **options):
        self.dry_run = options['dry_run']
        self.specific_tenant = options['tenant_id']
        
        if self.dry_run:
            self.stdout.write(self.style.WARNING('Mode DRY-RUN activé - aucune modification ne sera effectuée'))
        
        # Obtenir la liste des schémas tenant
        tenant_schemas = self._get_tenant_schemas()
        
        if not tenant_schemas:
            self.stdout.write(self.style.WARNING('Aucun schéma tenant trouvé'))
            return
        
        self.stdout.write(f'Trouvé {len(tenant_schemas)} schéma(s) tenant à traiter')
        
        # Traiter chaque schéma tenant
        for schema_name in tenant_schemas:
            if self.specific_tenant:
                # Vérifier si ce schéma correspond au tenant spécifié
                tenant_id = schema_name.replace('tenant_', '').replace('_', '-')
                if tenant_id != self.specific_tenant:
                    continue
            
            try:
                self._migrate_tenant_schema(schema_name)
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'Erreur lors de la migration du schéma {schema_name}: {e}')
                )
                continue
        
        self.stdout.write(self.style.SUCCESS('✅ Migration des schémas tenant terminée'))

    def _get_tenant_schemas(self):
        """Récupère la liste des schémas tenant existants"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT schema_name 
                FROM information_schema.schemata 
                WHERE schema_name LIKE 'tenant_%'
                ORDER BY schema_name
            """)
            return [row[0] for row in cursor.fetchall()]

    def _migrate_tenant_schema(self, schema_name):
        """Applique les migrations manquantes à un schéma tenant"""
        self.stdout.write(f'🔄 Traitement du schéma: {schema_name}')
        
        with connection.cursor() as cursor:
            # Basculer vers le schéma tenant
            cursor.execute(f"SET search_path TO {schema_name}, public")
            
            # Vérifier quelles tables manquent
            missing_tables = self._check_missing_tables(cursor, schema_name)
            
            if not missing_tables:
                self.stdout.write(f'  ✅ Toutes les tables sont déjà présentes dans {schema_name}')
                return
            
            self.stdout.write(f'  📋 Tables manquantes: {", ".join(missing_tables)}')
            
            if not self.dry_run:
                # Créer les tables manquantes
                for table_name in missing_tables:
                    self._create_missing_table(cursor, schema_name, table_name)
                    self.stdout.write(f'  ✅ Table {table_name} créée')
            
            # Enregistrer les migrations comme appliquées
            if not self.dry_run:
                self._mark_migrations_applied(cursor, schema_name)

    def _check_missing_tables(self, cursor, schema_name):
        """Vérifie quelles tables sont manquantes dans le schéma"""
        # Tables attendues pour toutes les apps
        expected_tables = {
            'tiers_tiers',
            'tiers_adresse', 
            'tiers_contact',
            'tiers_activitetiers',
            'opportunites_opportunity',  # Nouvelle table ajoutée
        }
        
        # Obtenir les tables existantes
        cursor.execute(f"""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = %s
        """, [schema_name])
        
        existing_tables = {row[0] for row in cursor.fetchall()}
        
        # Retourner les tables manquantes
        return expected_tables - existing_tables

    def _create_missing_table(self, cursor, schema_name, table_name):
        """Crée une table manquante dans le schéma"""
        
        if table_name == 'opportunites_opportunity':
            self._create_opportunities_table(cursor, schema_name)
        else:
            self.stdout.write(
                self.style.WARNING(f'  ⚠️  Table {table_name} inconnue - création ignorée')
            )

    def _create_opportunities_table(self, cursor, schema_name):
        """Crée la table des opportunités dans le schéma"""
        
        # Table principale des opportunités
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.opportunites_opportunity (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                name VARCHAR(255) NOT NULL,
                tier_id UUID NOT NULL REFERENCES {schema_name}.tiers_tiers(id) ON DELETE CASCADE,
                stage VARCHAR(20) NOT NULL DEFAULT 'new',
                estimated_amount DECIMAL(12, 2) NOT NULL,
                probability INTEGER NOT NULL DEFAULT 10,
                expected_close_date DATE NOT NULL,
                source VARCHAR(20) NOT NULL DEFAULT 'other',
                description TEXT,
                assigned_to UUID,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                closed_at TIMESTAMP WITH TIME ZONE,
                loss_reason VARCHAR(20),
                loss_description TEXT,
                project_id VARCHAR(50)
            )
        """)
        
        # Index pour performance (repris du modèle Django)
        indexes = [
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_stage ON {schema_name}.opportunites_opportunity (stage)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_source ON {schema_name}.opportunites_opportunity (source)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_tier ON {schema_name}.opportunites_opportunity (tier_id)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_assigned ON {schema_name}.opportunites_opportunity (assigned_to)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_created ON {schema_name}.opportunites_opportunity (created_at)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_updated ON {schema_name}.opportunites_opportunity (updated_at)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_closed ON {schema_name}.opportunites_opportunity (closed_at)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_probability ON {schema_name}.opportunites_opportunity (probability)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_expected_close ON {schema_name}.opportunites_opportunity (expected_close_date)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_estimated_amount ON {schema_name}.opportunites_opportunity (estimated_amount)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_loss_reason ON {schema_name}.opportunites_opportunity (loss_reason)",
            
            # Index composites pour optimiser les requêtes complexes
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_stage_tier ON {schema_name}.opportunites_opportunity (stage, tier_id)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_stage_created ON {schema_name}.opportunites_opportunity (stage, created_at)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_stage_source ON {schema_name}.opportunites_opportunity (stage, source)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_stage_assigned ON {schema_name}.opportunites_opportunity (stage, assigned_to)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_stage_probability ON {schema_name}.opportunites_opportunity (stage, probability)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_tier_created ON {schema_name}.opportunites_opportunity (tier_id, created_at)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_tier_stage ON {schema_name}.opportunites_opportunity (tier_id, stage)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_source_created ON {schema_name}.opportunites_opportunity (source, created_at)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_assigned_created ON {schema_name}.opportunites_opportunity (assigned_to, created_at)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_stage_tier_created ON {schema_name}.opportunites_opportunity (stage, tier_id, created_at)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_stage_source_created ON {schema_name}.opportunites_opportunity (stage, source, created_at)",
            f"CREATE INDEX IF NOT EXISTS idx_{schema_name}_opp_stage_assigned_created ON {schema_name}.opportunites_opportunity (stage, assigned_to, created_at)",
        ]
        
        for index_sql in indexes:
            cursor.execute(index_sql)
        
        logger.info(f"Table opportunites_opportunity créée dans le schéma {schema_name}")

    def _mark_migrations_applied(self, cursor, schema_name):
        """Marque les migrations comme appliquées dans le schéma"""
        
        # Assurer que la table django_migrations existe
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {schema_name}.django_migrations (
                id SERIAL PRIMARY KEY,
                app VARCHAR(255) NOT NULL,
                name VARCHAR(255) NOT NULL,
                applied TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
            )
        """)
        
        # Marquer les migrations opportunites comme appliquées
        cursor.execute(f"""
            INSERT INTO {schema_name}.django_migrations (app, name, applied)
            SELECT 'opportunites', '0001_initial', NOW()
            WHERE NOT EXISTS (
                SELECT 1 FROM {schema_name}.django_migrations 
                WHERE app = 'opportunites' AND name = '0001_initial'
            )
        """)
        
        logger.info(f"Migrations marquées comme appliquées dans le schéma {schema_name}") 