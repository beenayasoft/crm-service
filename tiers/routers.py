"""
Router de base de données pour gérer les schémas multiples
"""

class TenantSchemaRouter:
    """
    Router qui gère le routage des requêtes vers le bon schéma
    """
    
    def db_for_read(self, model, **hints):
        """Détermine quelle DB utiliser pour la lecture"""
        return 'default'
    
    def db_for_write(self, model, **hints):
        """Détermine quelle DB utiliser pour l'écriture"""
        return 'default'
    
    def allow_relation(self, obj1, obj2, **hints):
        """Autorise les relations entre objets"""
        return True
    
    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """Contrôle quelles migrations appliquer"""
        # Permettre les migrations sur la DB par défaut
        return db == 'default'
