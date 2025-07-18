# Service CRM - Architecture Multi-tenant par Schémas

## Vue d'ensemble

Le service CRM de Beenaya utilise une architecture multi-tenant avancée avec **schémas PostgreSQL séparés** pour chaque tenant. Cette approche garantit une isolation complète des données entre les clients tout en permettant une gestion simplifiée et des performances optimales.

## Architecture Multi-tenant

### Principe de fonctionnement

- **Un schéma PostgreSQL par tenant** : `tenant_<tenant_id>`
- **Isolation complète** : Chaque tenant a ses propres tables
- **Routage automatique** : Middleware qui bascule automatiquement vers le bon schéma
- **Gestion automatique** : Création de schémas à la volée lors de la première requête

### Structure des schémas

```sql
-- Schéma public (migrations Django classiques)
public.django_migrations
public.auth_user
public.django_content_type
-- etc.

-- Schéma tenant (données métier isolées)
tenant_f0e6399b_fc83_4ea9_87b5_5d0b6c1e5d2b.tiers_tiers
tenant_f0e6399b_fc83_4ea9_87b5_5d0b6c1e5d2b.tiers_adresse
tenant_f0e6399b_fc83_4ea9_87b5_5d0b6c1e5d2b.tiers_contact
tenant_f0e6399b_fc83_4ea9_87b5_5d0b6c1e5d2b.opportunites_opportunity
-- etc.
```

## Applications incluses

### 1. **Tiers** (`tiers/`)
- **Modèles** : Tiers, Adresse, Contact, ActiviteTiers
- **Fonctionnalités** : Gestion des clients, prospects, fournisseurs
- **API** : ViewSet complet avec filtres, recherche, pagination

### 2. **Opportunités** (`opportunites/`)
- **Modèles** : Opportunity
- **Fonctionnalités** : Pipeline commercial, Kanban, statistiques
- **API** : ViewSet avec actions métier (mark_won, mark_lost, etc.)

## Middleware Multi-tenant

Le cœur de l'architecture repose sur deux middleware :

### 1. **TenantSchemaMiddleware**
```python
# tiers/middleware.py
class TenantSchemaMiddleware(MiddlewareMixin):
    def process_request(self, request):
        tenant_id = request.META.get('HTTP_X_TENANT_ID')
        schema_name = f"tenant_{tenant_id.replace('-', '_')}"
        
        # Créer le schéma si nécessaire
        if not self._schema_exists(schema_name):
            self._create_tenant_schema(schema_name, tenant_id)
        
        # Basculer vers le schéma
        self._set_schema(schema_name)
```

### 2. **TenantSchemaRoutingMiddleware**
```python
class TenantSchemaRoutingMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # Remettre le schéma public par défaut
        with connection.cursor() as cursor:
            cursor.execute("SET search_path TO public")
        return response
```

## Gestion des migrations

### Migrations classiques (schéma public)
```bash
# Migrations Django standard
python manage.py makemigrations
python manage.py migrate
```

### Migrations multi-tenant (schémas tenant)

#### 🚨 **Problème** : Nouveaux modèles dans schémas existants

Quand vous ajoutez une nouvelle application (comme `opportunites`) à un service existant, les schémas tenant déjà créés **ne contiennent pas** les nouvelles tables.

#### ✅ **Solution** : Commande personnalisée

```bash
# Voir les actions qui seront effectuées (dry-run)
python manage.py migrate_tenant_schemas --dry-run

# Appliquer les migrations à tous les schémas tenant
python manage.py migrate_tenant_schemas

# Appliquer les migrations à un tenant spécifique
python manage.py migrate_tenant_schemas --tenant-id f0e6399b-fc83-4ea9-87b5-5d0b6c1e5d2b
```

### Commande `migrate_tenant_schemas`

Cette commande personnalisée :

1. **Découvre** tous les schémas tenant existants
2. **Vérifie** quelles tables sont manquantes
3. **Crée** les tables manquantes avec leurs index
4. **Marque** les migrations comme appliquées

```bash
# Exemple de sortie
python manage.py migrate_tenant_schemas

Trouvé 3 schéma(s) tenant à traiter
🔄 Traitement du schéma: tenant_f0e6399b_fc83_4ea9_87b5_5d0b6c1e5d2b
  📋 Tables manquantes: opportunites_opportunity
  ✅ Table opportunites_opportunity créée
🔄 Traitement du schéma: tenant_df713d5e_00d9_41a4_843f_40a2bfd94424
  ✅ Toutes les tables sont déjà présentes
✅ Migration des schémas tenant terminée
```

## Ajout d'une nouvelle application

### 1. **Créer l'application Django**
```bash
python manage.py startapp nouvelle_app
```

### 2. **Ajouter à INSTALLED_APPS**
```python
# crm_service/settings.py
INSTALLED_APPS = [
    # ...
    'tiers',
    'opportunites',
    'nouvelle_app',  # ← Ajouter ici
]
```

### 3. **Configurer les URLs**
```python
# crm_service/urls.py
urlpatterns = [
    path('admin/', admin.site.urls),
    path('health/', health_check, name='health_check'),
    path('api/', include('tiers.urls')),
    path('api/', include('opportunites.urls')),
    path('api/', include('nouvelle_app.urls')),  # ← Ajouter ici
]
```

### 4. **Créer les modèles (sans tenant_id)**
```python
# nouvelle_app/models.py
class MonModele(models.Model):
    # PAS de tenant_id - l'isolation est gérée par le schéma
    nom = models.CharField(max_length=255)
    # ...
    
    class Meta:
        db_table = 'nouvelle_app_monmodele'
```

### 5. **Étendre le middleware**
```python
# tiers/middleware.py
def _create_tenant_schema(self, schema_name, tenant_id):
    # ...
    # Créer les tables de notre app tiers
    self._create_tiers_tables(cursor, schema_name)
    
    # Créer les tables de notre app opportunites
    self._create_opportunities_tables(cursor, schema_name)
    
    # Créer les tables de la nouvelle app
    self._create_nouvelle_app_tables(cursor, schema_name)  # ← Ajouter ici
```

### 6. **Étendre la commande de migration**
```python
# tiers/management/commands/migrate_tenant_schemas.py
def _check_missing_tables(self, cursor, schema_name):
    expected_tables = {
        'tiers_tiers',
        'tiers_adresse', 
        'tiers_contact',
        'tiers_activitetiers',
        'opportunites_opportunity',
        'nouvelle_app_monmodele',  # ← Ajouter ici
    }
    # ...
```

### 7. **Appliquer les migrations**
```bash
# Migrations classiques
python manage.py makemigrations nouvelle_app
python manage.py migrate

# Migrations multi-tenant
python manage.py migrate_tenant_schemas
```

## API Gateway

### Configuration des routes

```python
# soa/api-gateway/config.py
SERVICES = {
    "crm": {
        "url": "http://localhost:8003",
        "health": "/health/",
        "routes": [
            "/api/tiers/", 
            "/api/opportunites/",
            "/api/nouvelle_app/"  # ← Ajouter ici
        ]
    }
}

LEGACY_ROUTE_MAPPING = {
    # Routes opportunités
    "/api/opportunites/": ("crm", "/api/opportunites/"),
    "/api/opportunites/{id}/": ("crm", "/api/opportunites/{id}/"),
    "/api/opportunites/stats/": ("crm", "/api/opportunites/stats/"),
    "/api/opportunites/kanban/": ("crm", "/api/opportunites/kanban/"),
    # ...
}
```

## Optimisations de performance

### Cache Redis
Toutes les ViewSets utilisent le cache Redis pour optimiser les performances :

```python
# Exemple dans OpportunityViewSet
def list(self, request, *args, **kwargs):
    cache_key = self._get_cache_key('list', filters=request.GET.dict())
    cached_data = cache.get(cache_key)
    if cached_data:
        response = Response(cached_data)
        response['X-Cache-Status'] = 'HIT'
        return response
    
    # Si pas en cache, traiter normalement
    response = super().list(request, *args, **kwargs)
    cache.set(cache_key, response.data, 30)  # TTL 30 secondes
    response['X-Cache-Status'] = 'MISS'
    return response
```

### Index de base de données
Les modèles incluent de nombreux index pour optimiser les requêtes :

```python
# models.py
class Opportunity(models.Model):
    # ...
    class Meta:
        indexes = [
            models.Index(fields=['stage']),
            models.Index(fields=['tier']),
            models.Index(fields=['stage', 'tier']),
            models.Index(fields=['stage', 'created_at']),
            # ... 23 index au total
        ]
```

## Développement et tests

### Démarrage du service
```bash
cd soa/services/crm-service

# Installer les dépendances
pip install -r requirements.txt

# Appliquer les migrations
python manage.py migrate

# Démarrer le serveur
python manage.py runserver 0.0.0.0:8003
```

### Tests avec curl
```bash
# Tester la santé du service
curl http://localhost:8003/health/

# Tester les tiers (avec authentification)
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -H "X-Tenant-ID: f0e6399b-fc83-4ea9-87b5-5d0b6c1e5d2b" \
     http://localhost:8003/api/tiers/

# Tester les opportunités
curl -H "Authorization: Bearer YOUR_TOKEN" \
     -H "X-Tenant-ID: f0e6399b-fc83-4ea9-87b5-5d0b6c1e5d2b" \
     http://localhost:8003/api/opportunites/
```

### Génération de données de test
```bash
# Générer des tiers factices pour un tenant
python manage.py generate_fake_tiers f0e6399b-fc83-4ea9-87b5-5d0b6c1e5d2b 100
```

## Surveillance et logs

### Logs du service
```bash
# Voir les logs en temps réel
tail -f logs/crm.log

# Rechercher des erreurs
grep ERROR logs/crm.log

# Voir les schémas créés
grep "Schéma.*créé" logs/crm.log
```

### Monitoring des performances
- **Cache hit ratio** : Vérifier les headers `X-Cache-Status`
- **Requêtes SQL** : Utiliser Django Debug Toolbar en développement
- **Temps de réponse** : Surveiller les logs de l'API Gateway

## Dépannage

### Problème : Table manquante dans un schéma tenant

**Symptôme** : Erreur `relation "tenant_xxx.app_model" does not exist`

**Solution** :
```bash
# Voir les tables manquantes
python manage.py migrate_tenant_schemas --dry-run

# Appliquer les migrations
python manage.py migrate_tenant_schemas
```

### Problème : Schéma tenant corrompu

**Symptôme** : Erreurs multiples dans un schéma spécifique

**Solution** :
```sql
-- Se connecter à PostgreSQL
psql -U postgres -d crm_db

-- Supprimer le schéma
DROP SCHEMA tenant_f0e6399b_fc83_4ea9_87b5_5d0b6c1e5d2b CASCADE;

-- Le schéma sera recréé automatiquement à la prochaine requête
```

### Problème : Migrations Django bloquées

**Symptôme** : `django.db.migrations.exceptions.InconsistentMigrationHistory`

**Solution** :
```bash
# Voir l'état des migrations
python manage.py showmigrations

# Réinitialiser les migrations si nécessaire
python manage.py migrate --fake-initial
```

## Roadmap

### Fonctionnalités à venir
- [ ] Sauvegarde automatique des schémas tenant
- [ ] Monitoring des performances par tenant
- [ ] Interface d'administration des schémas
- [ ] Migration automatique lors des déploiements

### Améliorations techniques
- [ ] Pool de connexions optimisé
- [ ] Compression des données anciennes
- [ ] Réplication read-only pour les rapports
- [ ] Audit trail des modifications

## Conclusion

Cette architecture multi-tenant par schémas offre :

- **Isolation parfaite** des données entre tenants
- **Performances optimales** (pas de filtres tenant_id)
- **Simplicité de développement** (modèles sans tenant_id)
- **Flexibilité** (schémas indépendants)
- **Sécurité** (isolation au niveau base de données)

Pour toute question ou amélioration, consultez les logs du service ou contactez l'équipe de développement. 