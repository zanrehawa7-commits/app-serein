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

## Tests — stratégie de vitesse

### Réglage de test rapide (`config/settings_test.py`)
Utilise `MD5PasswordHasher` (au lieu de PBKDF2 × 870 000 itérations) → `create_user()` ×1000 plus rapide.

```bash
# Premier run (ou après migration) — recrée la base de test
python manage.py test --settings=config.settings_test --parallel=auto \
  commun referentiels offres candidatures suivi stages comptes

# Runs suivants — conserve la base (plus rapide)
python manage.py test --settings=config.settings_test --keepdb --parallel=auto \
  commun referentiels offres candidatures suivi stages comptes

# Tests d'un seul lot (pendant le développement)
python manage.py test --settings=config.settings_test --keepdb --parallel=auto \
  candidatures stages
```

### Règle de développement par lot
- **Pendant le développement** : ne lancer que les tests des apps modifiées (ex. `candidatures stages`).
- **Suite complète** (`commun referentiels offres candidatures suivi stages comptes`) : une seule fois, juste avant le commit final du lot.
- Ne jamais commiter avec des tests qui échouent, même partiels.

## Étape 6 — Candidatures (F10)

### Workflow de saisie
1. Secrétaire → Rechercher un candidat (par nom/prénom/tél/email)
2. Sélectionner un candidat existant ou créer un nouveau
3. Créer la candidature avec au moins un CV (RG11 : pdf/jpg/jpeg/png, 5 Mo max)

### Stockage privé des fichiers (`FICHIERS_PRIVES_ROOT`)
- Les pièces jointes sont stockées dans `backend/fichiers_prives/` (hors `MEDIA_ROOT`).
- `FileSystemStorage(location=FICHIERS_PRIVES_ROOT, base_url=None)` — `base_url=None` empêche toute URL publique.
- **Interdiction absolue** d'utiliser `piece.fichier.url` dans les templates.
- Tous les téléchargements passent par `PieceJointeTelechargerView` (URL `/candidatures/pieces/<pk>/telecharger/`).
- **En production** : Nginx ne sert jamais `fichiers_prives/` directement. La vue Django envoie l'en-tête `X-Accel-Redirect` vers une location interne Nginx (ex. `location /protected/ { internal; alias /path/to/fichiers_prives/; }`) et renvoie un `FileResponse` vide en dev.

### RG clés
- **RG07** : un candidat ne peut avoir qu'une seule candidature active (RECUE ou EN_TRAITEMENT) — contrôle dans `creer_candidature()`.
- **RG09** : offre obligatoire si `SUITE_OFFRE`, interdite si `SPONTANEE` — contrôle dans le formulaire et dans `Candidature.clean()`.
- **RG12** : notifier le Responsable du département ; si absent → notifier tous les Administrateurs.
- **RG19** : liste "Candidats à informer" = `candidat_informe=False` et statut ACCORDEE ou REFUSEE.
- `Offre.places_restantes()` = `nombre_places − candidatures.filter(statut="ACCORDEE").count()`.

### Permissions
- Secrétaire : CRUD Candidat, CRU Candidature, CRUD PieceJointe.
- Responsable : lecture seule (présélection/accord/refus à l'étape 7).
- Administrateur : lecture seule.

### Normalisation téléphone (`normaliser_telephone`)
Supprime espaces/points/tirets, retire préfixe `+226`/`00226` → résultat 8 chiffres burkinabè. Appliqué à la saisie ET à la recherche pour détecter les doublons.

## Étape 7 — Traitement des candidatures par le Responsable (F11)

### Transitions (`candidatures/services.py`)
- `TransitionInterdite(Exception)` / `QuotaAtteint(Exception)` : exceptions métier.
- `preselectionner(candidature, utilisateur, commentaire="")` : RECUE → EN_TRAITEMENT. Reset `candidat_informe=False`, `date_information=None`. Notifie les Secrétaires.
- `planifier_entretien(candidature, date_entretien, utilisateur)` : EN_TRAITEMENT uniquement, date future obligatoire. Reset informe. Notifie Secrétaires : "Entretien planifié le <date> pour CAND-XXXX : prévenir le candidat."
- `accorder(candidature, utilisateur, commentaire="", confirmer_depassement=False)` : EN_TRAITEMENT → ACCORDEE. Si offre liée et quota = 0 sans `confirmer_depassement=True` → `QuotaAtteint`. Reset informe. Notifie Secrétaires.
- `refuser(candidature, motif, precision_motif, utilisateur, commentaire="")` : RECUE ou EN_TRAITEMENT → REFUSEE. Motif obligatoire. Si `AUTRE`, precision_motif requis. Reset informe. Notifie Secrétaires.
- `rediriger(candidature, nouveau_departement, motif, utilisateur)` : RECUE uniquement, statut reste RECUE, département change. Notifie responsable du nouveau dept (ou admins si absent) + Secrétaires.

### Vues (`candidatures/views.py`)
- `_DecisionView` (base) : `roles = ["Responsable"]`, vérifie que `candidature.departement == user.membre.departement`.
- `PreselectionnerView`, `PlanifierEntretienView` : POST-only (redirect vers detail).
- `AccorderView` (GET+POST) : deux passes pour quota — premier POST raise `QuotaAtteint` → re-render avec `quota_atteint=True` → second POST avec `confirmer_depassement=True`.
- `RefuserView` (GET+POST) : JS masque/affiche le champ `precision_motif` si motif = `AUTRE`.
- `RedirigerView` (GET+POST) : `RedirigerForm` exclut le département actuel du queryset.

### Formulaires (`candidatures/forms.py`)
- `EntretienForm` : `DateTimeInput(type=datetime-local)`, `clean_date_entretien()` valide que la date est dans le futur.
- `AccorderForm` : `confirmer_depassement = HiddenInput` (BooleanField, required=False).
- `RefuserForm` : `clean()` → AUTRE requiert precision non vide.
- `RedirigerForm` : `__init__(departement_actuel=...)` exclut le dept courant du queryset.

### Permissions (`init_donnees.py`)
- Responsable : `"candidatures.candidature": ["change", "view"]`, `"candidatures.candidat": ["view"]`.
- `CandidatureModifierView` reste protégée par `roles = ["Secrétaire"]` → Responsable → 403.

### Templates
- `candidature_detail.html` : panel « Actions — Responsable » (inline presel + lien entretien/accord/refus/redirection).
- `candidature_accorder_form.html` : commentaire + zone quota avec `confirmer_depassement`.
- `candidature_refuser_form.html` : select motif + zone precision (JS toggle si AUTRE).
- `candidature_rediriger_form.html` : select dept + motif.
- `candidature_list.html` : onglets Bootstrap 5 par statut (Responsable uniquement) avec compteurs.
- `candidats_informer.html` : colonnes enrichies : téléphone, motif de refus, date entretien, date décision.
- `tableau_bord_responsable.html` : 4 cartes candidatures (Reçues/En traitement/Accordées/Refusées) + tableau 5 dernières reçues.

## Étape 8 — Gestion des stages (F12)

### Modèle `stages/models.py`
- `StatutStage` : A_VENIR, EN_COURS, TERMINE, INTERROMPU.
- Cycle : A_VENIR → EN_COURS → TERMINE ; A_VENIR/EN_COURS → INTERROMPU.
- Statut calculé à la création selon la date de début (≤ aujourd'hui → EN_COURS, sinon A_VENIR).
- Champs évaluation (note, vivier, rapport) réservés à l'étape 9 — NE PAS TOUCHER.

### Transitions (`stages/services.py`)
- `TransitionInterdite(Exception)` : exception métier.
- `constituer_stage(candidature, date_debut, date_fin_prevue, maitre_stage, utilisateur)` : candidature doit être ACCORDEE, aucun stage existant, maître actif du même département. Reset `candidat_informe`. Notifie Secrétaires.
- `modifier_stage(stage, date_fin_prevue, maitre_stage, utilisateur, date_debut=None)` : A_VENIR ou EN_COURS. `date_debut` modifiable seulement si A_VENIR.
- `terminer_stage(stage, date_fin_reelle, utilisateur)` : EN_COURS → TERMINE. Date réelle ≥ début et ≤ aujourd'hui.
- `interrompre_stage(stage, date_fin_reelle, motif, utilisateur)` : A_VENIR/EN_COURS → INTERROMPU. Motif obligatoire.
- `demarrer_stage_auto(stage, aujourd_hui)` : A_VENIR → EN_COURS si date_debut ≤ aujourd_hui.
- `cloturer_stage_auto(stage, aujourd_hui)` : EN_COURS → TERMINE si date_fin_prevue < aujourd_hui. Notifie le Responsable du département.

### Commande de maintenance (`python manage.py mettre_a_jour_stages`)
- Option `--date AAAA-MM-JJ` pour simuler une date passée (serveur arrêté).
- Ordre : **démarrages d'abord** (A_VENIR → EN_COURS) puis **clôtures** (EN_COURS → TERMINE).
- Idempotente — sans danger à relancer.

### Vues (`stages/views.py`) + URLs (`stages/urls.py`)
- `StageListView` : 3 rôles, filtres (statut, date, type de stage, département, recherche).
- `StageDetailView` : 3 rôles, historique inclus.
- `ConstituerStageView` : Secrétaire uniquement.
- `ModifierStageView` : Secrétaire uniquement.
- `TerminerStageView` : Responsable uniquement, vérifie que le stage est dans son département.
- `InterrompreStageView` : Responsable uniquement, idem.

### Permissions (`init_donnees.py`)
- Secrétaire : `"stages.stage": ["add", "change", "view"]`.
- Responsable : `"stages": ["add", "change", "view"]` (terminer/interrompre passent par `change`).
- Administrateur : accès complet.

### Templates (`backend/templates/stages/`)
- `stage_list.html` : onglets par statut + filtres + tableau.
- `stage_detail.html` : fiche + historique + boutons selon rôle/statut.
- `stage_constituer_form.html` : formulaire + avertissement JS si disponibilité manquante.
- `stage_modifier_form.html` : idem, date_debut grisée si EN_COURS.
- `stage_terminer_form.html` : date de fin réelle (≤ aujourd'hui).
- `stage_interrompre_form.html` : date + motif.

### Règle Complément 5 — `referentiels/services.py`
`desactiver_membre()` refuse si le membre est maître de stage d'un stage A_VENIR ou EN_COURS (message : "changer d'abord le maître de stage").

### Mise à jour `candidature_detail.html`
- Si statut ACCORDEE : bouton "Constituer le stage" (Secrétaire) ou "Voir le stage" si déjà constitué.

### Mise à jour `candidature_list.html`
- Onglet Accordées : badge mortarboard bleu si stage constitué, badge ! orange si à compléter.

## Étape 9 — Évaluation des stagiaires et Vivier de talents (F13)

### Modèle (`stages/models.py`)
- Champ `rapport` migré vers stockage privé (`_get_stockage_rapport` → `FICHIERS_PRIVES_ROOT`).
- Champ `rappel_evaluation_envoye = BooleanField(default=False)` : passe à True après envoi du rappel.

### Services (`stages/services.py`)
- `peut_evaluer(stage, aujourd_hui=None)` → `(bool, date_verrou|None)`.
- `evaluer_stage(...)` : note [1-20], vivier requiert note ≥ 12, verrouillage 30j après 1ère évaluation.

### Vues (`stages/views.py`)
- `EvaluerStageView` : Responsable même département uniquement.
- `StagesAEvaluerListView` : TERMINÉ + sans note + fin ≤ today-7j.
- `VivierListView` + `VivierExportCsvView` (CSV UTF-8-BOM).
- `RapportTelechargerView` : Responsable même dept → OK ; autre dept → seulement si `vivier=True` ; Secrétaire → 403.

### URLs ajoutées
`stages/a-evaluer/`, `stages/vivier/`, `stages/vivier/export/`, `stages/<pk>/evaluer/`, `stages/<pk>/rapport/`

### Commande `mettre_a_jour_stages`
3e passe : rappel évaluation 7j, idempotent (`rappel_evaluation_envoye`).

### Badge vivier
Affiché sur la fiche candidat (tous rôles, sans la note). Secrétaire → 403 sur vivier et rapport.

## Variables d'environnement
Copier `.env.example` → `.env` et remplir les valeurs. Ne jamais commiter `.env`.
Le `.env` est à la racine du projet (`app-serein/`), lu par `python-decouple` depuis `backend/`.


## Règles de revue (à vérifier AVANT chaque commit)

### Données et migrations
- Ne jamais réécrire un modèle existant : uniquement des ajouts/modifications par migration.
- Ne jamais modifier une migration déjà appliquée : créer une nouvelle migration.
- Renommages : RenameModel / RenameField (jamais suppression + recréation). Après un RenameModel,
  mettre à jour GROUPES_PERMISSIONS, supprimer les permissions orphelines, relancer init_donnees.
- Avant une contrainte d'unicité ou un CHECK : vérifier que les données existantes la respectent.
- Après chaque lot : `makemigrations --check --dry-run` doit répondre "No changes detected".
- Ne jamais inventer de données métier (durées, motifs, listes de choix, textes officiels) :
  reprendre le cahier des charges ; sinon proposer une valeur marquée "À VALIDER PAR SEREIN-GE".
- Une seule source de vérité : ne pas créer de champ qui duplique une information existante
  (ex. pas de booléen est_responsable : Departement.responsable fait foi).

### Logique métier
- Toute règle métier vit dans services.py ET est contrôlée dans le formulaire (les deux).
- Services : transaction.atomic + select_for_update sur l'objet modifié.
- Vérifier TOUTES les préconditions AVANT la moindre écriture en base (pas d'exception levée
  après un changement partiel).
- Chaque transition de statut : contrôle de la transition, historique, notifications prévues.
- Dates : utiliser commun.utils.ajouter_mois() ; jamais de calcul de mois approximatif.
- Penser aux cas limites : désactivation d'un élément encore utilisé (responsable, maître de
  stage…), double clic / accès concurrent, données anciennes qui ne respectent pas une nouvelle règle.

### Sécurité et accès
- Administrateur : TOUTES permissions sur comptes et referentiels, LECTURE SEULE partout ailleurs.
- Les contrôles d'accès se font côté serveur (rôle + permission + département dans get_queryset
  et dans les vues d'action), jamais seulement en masquant un bouton.
- Actions en POST uniquement, schéma Post/Redirect/Get, messages en français.
- Fichiers : stockage privé, jamais de fichier.url dans un template, téléchargement via vue protégée.
- Aucune valeur affichée codée en dur dans les tableaux de bord : vraies requêtes.

### Tests
- Un test par règle métier ajoutée + un test 403 pour chaque rôle non autorisé.
- **Pendant le développement d'un lot** : ne lancer que les apps modifiées (`--settings=config.settings_test --keepdb --parallel <apps>`).
- **Juste avant le commit** : lancer la suite complète une seule fois (`commun referentiels offres candidatures suivi stages comptes`).
- Toujours utiliser `--settings=config.settings_test` (MD5PasswordHasher) ; jamais les settings de prod pour les tests.
- 0 échec obligatoire avant tout commit.