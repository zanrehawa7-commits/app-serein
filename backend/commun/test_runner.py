import sys
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test.runner import DiscoverRunner


def _fichiers(dossier):
    dossier = Path(dossier)
    return {p for p in dossier.rglob("*") if p.is_file()} if dossier.exists() else set()


class StageTrackTestRunner(DiscoverRunner):
    """Fait échouer la suite si un test écrit dans le vrai dossier des fichiers privés."""

    def run_tests(self, *args, **kwargs):
        reel = Path(settings.FICHIERS_PRIVES_ROOT_REEL).resolve()
        test = Path(settings.FICHIERS_PRIVES_ROOT).resolve()
        if test == reel or reel in test.parents:
            raise ImproperlyConfigured(
                "FICHIERS_PRIVES_ROOT des tests ne doit pas être le vrai dossier des fichiers privés."
            )

        avant = _fichiers(reel)
        echecs = super().run_tests(*args, **kwargs)
        nouveaux = sorted(_fichiers(reel) - avant)
        if nouveaux:
            print(
                f"\nÉCHEC : {len(nouveaux)} fichier(s) écrit(s) dans le vrai dossier {reel} :",
                *(f"  {p}" for p in nouveaux[:10]),
                sep="\n",
                file=sys.stderr,
            )
            echecs += 1
        return echecs
