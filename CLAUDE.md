# Stage_App — Contexte projet pour Claude Code

## Présentation
Application web Django de gestion des stages pour l'entreprise **Serein-GE**.
Permet de gérer le cycle complet : besoins → offres → candidatures → stages → suivi.

## Stack technique
- Python 3.12 / Django 5.x
- PostgreSQL (base locale : `serein_db`)
- Bootstrap 5 + Bootstrap Icons (templates serveur)
- Django REST Framework + SimpleJWT (API future)
- `python-decouple` pour la lecture du `.env`
- Déploiement prévu via Docker Compose + Nginx

## Structure des apps (ordre de dépendance)

| App | Responsabilité |
|---|---|
| `referentiels` | Données de base : Departement, Membre, Etablissement, TypeStage, CanalPublication |
| `comptes` | Utilisateur personnalisé (email), rôles via Django Groups |
| `offres` | Besoin, Offre, Publication |
| `candidatures` | Candidat, Candidature, PieceJointe |
| `stages` | Stage |
| `suivi` | Historique (GenericFK), Notification |

## Conventions de code
- **Langue** : noms de modèles, champs, verbose_name, commentaires → **français** (sans accents dans les identifiants Python).
- **Logique métier** dans `services.py` de chaque app. Jamais dans les vues ni les modèles (sauf `clean()`).
- `TextChoices` pour toutes les énumérations.
- `__str__`, `class Meta` (verbose_name, verbose_name_plural, ordering) sur chaque modèle.
- `on_delete=PROTECT` vers les référentiels ; `CASCADE` seulement pour les compositions.
- Pas de `null=True` sur les CharField/TextField : utiliser `blank=True` avec valeur vide.

## Modèle utilisateur
- `AUTH_USER_MODEL = "comptes.Utilisateur"`
- Connexion par email (`USERNAME_FIELD = "email"`, champ `username` supprimé).
- Rôles = **Groups Django** : `Administrateur`, `Secrétaire`, `Responsable`.
- Propriété `utilisateur.role` → renvoie le nom du groupe (ou `None`).

## Contrôle d'accès (étape 3)

- **Protection globale** : `LoginRequiredMiddleware` natif Django 5.1+ — toutes les vues exigent la connexion sauf celles décorées `@login_not_required`.
- **Mixins et décorateurs** : définis dans `comptes/permissions.py`.
  - `RoleRequisMixin(roles=[...])` → CBV
  - `@role_requis("Rôle1", "Rôle2")` → FBV
  - `DepartementResponsableMixin` → filtre les objets par département du responsable (RG13). Surcharger `get_departement_objet()`.
- **Superuser sans groupe** → traité comme Administrateur dans `_role_utilisateur()`.
- **Context processor** `comptes/context_processors.py` → injecte `role_utilisateur` et `nb_notifications` dans tous les templates.
- **Session** : déconnexion automatique après 30 min (`SESSION_COOKIE_AGE=1800`, `SESSION_SAVE_EVERY_REQUEST=True`).
- **Formulaires** : `django-crispy-forms` + `crispy-bootstrap5`. Utiliser `{{ form|crispy }}` dans les templates.

## Règles de gestion clés
- **RG07** : un candidat ne peut avoir qu'une seule candidature active (statut RECUE ou EN_TRAITEMENT).
- **RG09** : si `type_demande = SUITE_OFFRE`, le champ `offre` est obligatoire ; si `SPONTANEE`, il doit être vide.
- **RG11** : pièces jointes acceptées : pdf, jpg, jpeg, png ; taille max 5 Mo.
- **RG22** : le maître de stage doit appartenir au département de la candidature.
- Un référentiel utilisé ne peut pas être supprimé (`PROTECT`).
- Le responsable d'un département doit être membre de ce département (`clean()`).

## Commandes utiles
```bash
# Activer le venv (PowerShell)
.\.venv\Scripts\Activate.ps1

# Lancer le serveur
cd backend && python manage.py runserver

# Charger les données initiales (groupes, permissions, types de stage)
python manage.py init_donnees

# Créer un superutilisateur
python manage.py createsuperuser
```

## Variables d'environnement
Copier `.env.example` → `.env` et remplir les valeurs. Ne jamais commiter `.env`.
Le `.env` est à la racine du projet (`app-serein/`), lu par `python-decouple` depuis `backend/`.
