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

## Module commun (`backend/commun/`)

Utilitaires partagés entre toutes les apps.

- **`commun/mixins.py` — `ListeMixin`** : à hériter sur toute `ListView`. Gère pagination (20/page), recherche texte (`champs_recherche = [...]`), filtre actif/inactif (`champ_actif = "actif"`, surcharger avec `"is_active"` pour `Utilisateur`), tri par colonne. Injecte `params_paginateur`, `q`, `actif_filtre`, `tri_actuel` dans le contexte.
- **`commun/services.py` — `supprimer_ou_desactiver(instance, request=None)`** : tente `delete()`, intercepte `ProtectedError` → met `actif = False`. Affiche `messages.success` ou `messages.warning`.
- **`templates/commun/formulaire.html`** : gabarit générique pour Create/Update (utilise `{% crispy form %}`, requiert `titre` et `url_retour` dans le contexte).
- **`templates/commun/_pagination.html`** : partiel Bootstrap 5 préservant les paramètres GET.
- **`templates/commun/_modal_confirmer.html`** : modal Bootstrap 5 avec formulaire POST + `{% csrf_token %}`. Le JS est inline (pas dans un `{% block %}`). Alimenté par `data-nom`, `data-url`, `data-action`, `data-info`, `data-btn-class`, `data-btn-label` sur le bouton déclencheur.

## Étape 4 — Module Administrateur (F02–F07)

### F02 — Rôles & permissions
- Vue `PermissionsRoleView` : affiche/modifie les permissions Django d'un groupe via des cases à cocher.
- Les permissions `comptes` de l'Administrateur sont toujours cochées et désactivées (cases grises + input hidden).
- Garde-fou POST : les permissions `comptes` sont toujours réinjectées pour Administrateur même si absentes du POST.
- `APPS_PERMISSIONS` et `ACTIONS_ORDRE` définis dans `comptes/views.py`.

### F03 — Utilisateurs
- `UtilisateurListView` : hérite de `RolePermMixin + ListeMixin`. `champ_actif = "is_active"`.
- `UtilisateurCreateView / UpdateView` : formulaires `UtilisateurCreerForm / UtilisateurModifierForm`. Le rôle est un `ChoiceField` (pas un FK direct vers Group).
- `UtilisateurActiverView` : refuse l'auto-désactivation (RG33).
- Si rôle change DE Responsable → autre : `user.membre = None; user.save(update_fields=["membre"])`.
- `UtilisateurReinitMdpView` : réinitialise le mot de passe sans connaître l'ancien.

### F04–F07 — Référentiels
- CRUD complet : Département, Établissement, TypeStage, CanalPublication.
- Membres gérés uniquement depuis la page détail d'un département (`MembreCreateView` prend `dept_pk` dans l'URL).
- Suppression via modal POST (pas de page de confirmation dédiée). Les vues delete sont de simples `View` (POST uniquement).
- `DepartementModifierForm` filtre le queryset du responsable aux membres actifs du département (RG31).
- `EtablissementTogglePartenaireView` : bascule le champ `partenaire` en POST.

### Permissions et contrôle d'accès (F02–F07)
- **`RolePermMixin`** (dans `comptes/permissions.py`) : combine `RoleRequisMixin(roles=["Administrateur"])` + `PermissionRequiredMixin`. Les superusers bypasse la vérification des permissions Django.
- Les templates utilisent `{% if perms.app.action_model %}` pour afficher/masquer boutons.
- Retirer une permission d'un rôle → bouton masqué ET vue retourne 403.

### Relation Utilisateur ↔ Membre
- `Utilisateur.membre` est un `OneToOneField` avec `related_name="compte"`.
- Pour accéder à l'utilisateur depuis un membre : `membre.compte` (pas `membre.utilisateur`).
- Dans les QuerySets : `Membre.objects.filter(compte__isnull=True)` (pas `utilisateur__isnull`).

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

## Étape 5 — Besoins, offres et publications (F08, F09) + socle suivi (F14, F17)

### Socle suivi (`suivi/services.py`)
- **`enregistrer_historique(objet, utilisateur, ancien_statut, nouveau_statut, commentaire)`** : enregistre via GenericFK (ContentType + object_id). À appeler dans chaque transition.
- **`notifier(destinataires, message, lien="")`** : bulk_create des `Notification`. `destinataires` est une liste d'objets Utilisateur.
- **`templates/commun/_historique.html`** : partiel à inclure dans tout détail (besoin, offre, etc.). Attend `historiques` en contexte.

### Vues notifications (`suivi/`)
- `NotificationListView` : liste paginée des notifs de l'utilisateur connecté (toutes les 3 rôles).
- `NotificationLireView` : GET ou POST, marque comme lue puis redirige vers `notif.lien` si présent.
- `NotificationToutLireView` : POST uniquement, bulk update.
- Dropdown dans `base.html` : affiche les 5 dernières (`dernieres_notifications` injecté par context processor), bouton "Tout marquer comme lu", lien "Voir toutes".

### Context processor (`comptes/context_processors.py`)
Injecte dans tous les templates : `role_utilisateur`, `nb_notifications`, `dernieres_notifications` (5 dernières).

### Transitions Besoin (`offres/services.py`)
- `TransitionInterdite(Exception)` : levée par toute transition invalide.
- `creer_besoin(...)` : statut ENVOYE, historique + notif aux Secrétaires actives.
- `annuler_besoin(besoin, utilisateur)` : depuis ENVOYE ou PRIS_EN_CHARGE → ANNULE. Notifie les Secrétaires actives.
- Machine d'état : ENVOYE → PRIS_EN_CHARGE (via `creer_offre`) → CLOTURE (future étape) ; ou ANNULE depuis ENVOYE/PRIS_EN_CHARGE.

### Transitions Offre (`offres/services.py`)
- `creer_offre(..., besoin=None)` : si besoin fourni, `select_for_update()` vérifie ENVOYE + pas d'offre existante → `TransitionInterdite`. Passe le besoin en PRIS_EN_CHARGE.
- `ouvrir_offre` : BROUILLON → OUVERTE.
- `suspendre_offre` : OUVERTE → SUSPENDUE.
- `rouvrir_offre` : SUSPENDUE → OUVERTE.
- `fermer_offre` : OUVERTE ou SUSPENDUE → FERMEE.
- `supprimer_offre` : BROUILLON seulement → delete().
- Toutes les transitions sont `@transaction.atomic` et enregistrent l'historique.
- En cas de `TransitionInterdite` dans les vues : redirect vers la page détail + `messages.error()` (pattern PRG).

### Vues offres (`offres/views.py`)
- `BesoinListView / OffreListView` : 3 rôles, filtrage côté serveur dans `get_queryset()`.
  - Responsable : uniquement besoins/offres de son département.
  - Admin : lecture seule (pas de boutons de création/modification).
- `BesoinCreateView` : Responsable uniquement. Lève `PermissionDenied` si `request.user.membre is None`.
- `OffreCreateFromBesoinView` : Secrétaire uniquement. Utilise `creer_offre(..., besoin=besoin)`.
- Toutes les vues de transition (ouvrir, suspendre, rouvrir, fermer) héritent de `_OffreTransitionView`.

### `init_donnees.py` — Format étendu
Support de la notation `"app.modele": [actions]` pour permissions par modèle. Secrétaire : `view_besoin` uniquement (pas add/change/delete Besoin). Responsable : `add/change/view_besoin`, `view_offre` uniquement.

### `commun/_historique.html`
Partiel timeline à inclure dans tout détail d'objet suivi. Attend la variable `historiques` (QuerySet Historique ordonné par `-date_action`).

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
