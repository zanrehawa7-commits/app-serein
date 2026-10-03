import os

from django.conf import settings
from django.core.files.storage import FileSystemStorage


class StockagePrive(FileSystemStorage):
    """
    Stockage des fichiers privés (pièces jointes, rapports), hors MEDIA_ROOT.

    FICHIERS_PRIVES_ROOT est relu à chaque accès : un FileSystemStorage construit avec
    location=... fige le chemin au chargement des modèles, si bien que les tests
    écrivaient dans le vrai dossier malgré settings_test / override_settings.
    """

    def __init__(self):
        super().__init__(base_url=None)

    @property
    def base_location(self):
        return settings.FICHIERS_PRIVES_ROOT

    @property
    def location(self):
        return os.path.abspath(self.base_location)
