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

from config.settings import *  # noqa: F401, F403

# ── Hachage rapide ────────────────────────────────────────────────────────────
# MD5 remplace PBKDF2 (870 000 itérations) → create_user() ~1000× plus rapide.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# ── Connexions BD ─────────────────────────────────────────────────────────────
# CONN_MAX_AGE=0 évite les conflits de connexions entre workers parallèles.
DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405
