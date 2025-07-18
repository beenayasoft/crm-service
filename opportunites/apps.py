from django.apps import AppConfig


class OpportunitesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "opportunites"
    verbose_name = "Gestion des opportunités"
    
    def ready(self):
        """
        Initialisation de l'application
        Importer les signaux si nécessaire
        """
        # import opportunites.signals  # Décommenter si vous ajoutez des signaux
        pass
