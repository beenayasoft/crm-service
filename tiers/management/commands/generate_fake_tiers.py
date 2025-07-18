from django.core.management.base import BaseCommand
from django.db import connection
from faker import Faker
import uuid
import random
from datetime import datetime, timezone

fake = Faker(['fr_FR'])  # Utiliser le locale français

def truncate(text, length):
    """Tronque le texte à la longueur spécifiée"""
    return text[:length] if text else ''

def generate_unique_name(base_name, index):
    """Génère un nom unique en ajoutant un suffixe si nécessaire"""
    suffix = f" #{index:04d}" if index > 0 else ""
    return truncate(f"{base_name}{suffix}", 255)

class Command(BaseCommand):
    help = 'Génère des tiers factices pour les tests de performance'

    def add_arguments(self, parser):
        parser.add_argument('tenant_id', type=str, help='ID du tenant')
        parser.add_argument('count', type=int, help='Nombre de tiers à générer')

    def handle(self, *args, **options):
        tenant_id = options['tenant_id']
        count = options['count']
        schema_name = f"tenant_{tenant_id.replace('-', '_')}"

        self.stdout.write(f"Génération de {count} tiers pour le tenant {tenant_id} (schema: {schema_name})")

        # Relations possibles (selon le modèle Tiers)
        relations = [
            'client',     # RELATION_CLIENT
            'prospect',   # RELATION_PROSPECT
            'fournisseur', # RELATION_FOURNISSEUR
            'sous_traitant'  # RELATION_SOUS_TRAITANT
        ]

        # Types possibles (selon le modèle Tiers)
        entity_types = [
            'entreprise',    # TYPE_ENTREPRISE
            'particulier'    # TYPE_PARTICULIER
        ]

        with connection.cursor() as cursor:
            for i in range(count):
                # Générer un tiers
                tier_id = str(uuid.uuid4())
                entity_type = random.choice(entity_types)
                relation = random.choice(relations)

                # Générer un nom unique
                base_name = fake.company() if entity_type == 'entreprise' else fake.name()
                unique_name = generate_unique_name(base_name, i)

                # Insertion du tiers avec des valeurs tronquées
                cursor.execute(f"""
                    INSERT INTO {schema_name}.tiers_tiers (
                        id, nom, type, relation, siret, tva, 
                        date_creation, date_modification, is_deleted
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, 
                        %s, %s, %s
                    )
                """, [
                    tier_id,
                    unique_name,
                    entity_type,
                    relation,
                    truncate(fake.numerify('#' * 14), 14) if entity_type == 'entreprise' else None,  # SIRET seulement pour entreprises
                    truncate(f"FR{fake.numerify('#' * 11)}", 20) if entity_type == 'entreprise' else None,  # TVA seulement pour entreprises
                    datetime.now(timezone.utc),
                    datetime.now(timezone.utc),
                    False
                ])

                # Générer 1 à 3 adresses
                for _ in range(random.randint(1, 3)):
                    cursor.execute(f"""
                        INSERT INTO {schema_name}.tiers_adresse (
                            tier_id, libelle, rue, ville, code_postal, pays, facturation
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s
                        )
                    """, [
                        tier_id,
                        truncate(fake.word(), 50),  # libelle max 50
                        truncate(fake.street_address(), 100),  # rue max 100
                        truncate(fake.city(), 100),  # ville max 100
                        truncate(fake.postcode(), 10),  # code_postal max 10
                        'France',
                        random.random() < 0.3  # 30% de chance d'être adresse de facturation
                    ])

                # Générer 1 à 5 contacts
                for _ in range(random.randint(1, 5)):
                    cursor.execute(f"""
                        INSERT INTO {schema_name}.tiers_contact (
                            tier_id, nom, prenom, fonction, email, telephone,
                            contact_principal_devis, contact_principal_facture
                        ) VALUES (
                            %s, %s, %s, %s, %s, %s, %s, %s
                        )
                    """, [
                        tier_id,
                        truncate(fake.last_name(), 100),  # nom max 100
                        truncate(fake.first_name(), 100),  # prenom max 100
                        truncate(fake.job(), 100),  # fonction max 100
                        truncate(fake.email(), 100),  # email max 100
                        truncate(fake.phone_number(), 20),  # telephone max 20
                        random.random() < 0.2,  # 20% de chance d'être contact principal devis
                        random.random() < 0.2   # 20% de chance d'être contact principal facture
                    ])

                if (i + 1) % 100 == 0:
                    self.stdout.write(f"Progress: {i + 1}/{count} tiers générés")

        self.stdout.write(self.style.SUCCESS(f'Successfully generated {count} tiers'))
