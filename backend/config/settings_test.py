"""
Réglages de test — JAMAIS utiliser en production.

Commande recommandée (première exécution ou après migration) :
    python manage.py test --settings=config.settings_test --parallel
      commun referentiels offres candidatures suivi stages comptes

Commande recommandée (runs suivants, base conservée) :
    python manage.py test --settings=config.settings_test --keepdb --parallel
      commun referentiels offres candidatures suivi stages comptes

Règle de développement :
    - Pendant un lot : ne tester que les apps modifiées (ex. candidatures stages).
    - Suite COMPLÈTE uniquement une fois, juste avant le commit final du lot.
"""

import atexit
import os
import shutil
import tempfile
from pathlib import Path

from config.settings import *  # noqa: F401, F403

# ── Hachage rapide ────────────────────────────────────────────────────────────
# MD5 remplace PBKDF2 (870 000 itérations) → create_user() ~1000× plus rapide.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# ── Connexions BD ─────────────────────────────────────────────────────────────
# CONN_MAX_AGE=0 évite les conflits de connexions entre workers parallèles.
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405

# ── Fichiers privés ───────────────────────────────────────────────────────────
# Les tests n'écrivent JAMAIS dans le vrai dossier : dossier temporaire supprimé en fin
# de suite. Transmis par variable d'environnement aux workers --parallel (processus
# enfants qui rechargent ces settings) pour qu'ils partagent le même dossier.
_VAR_FICHIERS_TESTS = "STAGETRACK_FICHIERS_TESTS"
if _VAR_FICHIERS_TESTS not in os.environ:
    os.environ[_VAR_FICHIERS_TESTS] = tempfile.mkdtemp(prefix="stagetrack_tests_")
    atexit.register(shutil.rmtree, os.environ[_VAR_FICHIERS_TESTS], True)
FICHIERS_PRIVES_ROOT_REEL = FICHIERS_PRIVES_ROOT  # noqa: F405
FICHIERS_PRIVES_ROOT = Path(os.environ[_VAR_FICHIERS_TESTS])

# Échoue si un fichier apparaît dans FICHIERS_PRIVES_ROOT_REEL pendant la suite.
TEST_RUNNER = "commun.test_runner.StageTrackTestRunner"
