# Stage Track — Guide pour Claude Code

> Ce fichier est la source de vérité pour toute nouvelle session.
> **Lis-le intégralement avant d'écrire la moindre ligne de code.**

---

## 1. Présentation

**Stage Track** est une application web Django de gestion du cycle de vie complet des dossiers de stage pour **Serein-GE** (entreprise burkinabè).

Cycle couvert : Besoins → Offres → Candidatures → Stages → Évaluation → Vivier de talents.

Contexte : projet réalisé dans le cadre d'un **stage de Licence** (rapport de stage à remettre, méthode Scrum). Le nom affiché dans l'interface est `Stage Track` (`APP_NAME` dans settings).

---

## 2. Stack et installation (Windows / PowerShell)

### Versions exactes (testées, pip freeze 2026-10-02)

| Paquet | Version |
|---|---|
| Python | 3.12.x |
| Django | 5.2.17 |
| djangorestframework | 3.18.1 |
| djangorestframework-simplejwt | 5.5.1 |
| psycopg (v3, binary) | 3.3.6 |
| django-cors-headers | 4.9.0 |
| gunicorn | 26.2.0 |
| python-decouple | 3.8 |
| Pillow | 12.3.0 |
| django-crispy-forms | 2.7 |
| crispy-bootstrap5 | 2026.9 |
| asgiref | 3.12.1 |

### Étapes d'installation pas à pas

```powershell
# 1. Cloner
git clone <url-du-repo> app-serein
cd app-serein

# 2. Créer le venv Python 3.12 (à la RACINE du projet, pas dans backend/)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 3. Installer les dépendances
cd backend
pip install -r requirements.txt

# 4. Base PostgreSQL (adapter le mot de passe)
psql -U postgres -c "CREATE DATABASE serein_db;"
psql -U postgres -c "CREATE USER serein_user WITH PASSWORD 'motdepasse';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE serein_db TO serein_user;"

# 5. Variables d'environnement
#    Le .env est à la RACINE du projet (app-serein/.env), lu par python-decouple depuis backend/
cp ../.env.example ../.env
#    Editer .env : renseigner SECRET_KEY, DB_PASSWORD (et DB_USER, DB_NAME si differents)

# 6. Migrations
python manage.py migrate

# 7. Groupes, permissions, types de stage (idempotent)
python manage.py init_donnees

# 8. Données de demo — développement uniquement (refuse si DEBUG=False)
python manage.py init_demo
#    Comptes créés :
#      admin@serein.bf / Admin1234!  -> Administrateur
#      sec@serein.bf   / Sec1234!   -> Secrétaire
#      resp@serein.bf  / Resp1234!  -> Responsable (département Informatique)

# 9. Superutilisateur (facultatif si init_demo utilisé)
python manage.py createsuperuser

# 10. Lancer le serveur
python manage.py runserver
```

> **Attention** : le venv est dans `app-serein/.venv/`, pas dans `backend/`.
> Depuis le répertoire `backend/`, appeler Python avec le chemin relatif :
> `.\.venv\Scripts\python.exe manage.py ...` (depuis `app-serein/backend/`, le venv est à `..\..\`).
> Ou activer le venv depuis la racine avant de naviguer dans `backend/`.

### Commandes de test

```powershell
# Premier run ou après migration — recreer la base de test
python manage.py test --settings=config.settings_test --parallel=auto ^
  commun referentiels offres candidatures suivi stages comptes

# Runs suivants — conserver la base (beaucoup plus rapide)
python manage.py test --settings=config.settings_test --keepdb --parallel=auto ^
  commun referentiels offres candidatures suivi stages comptes

# Pendant le développement : seulement les apps modifiées
python manage.py test --settings=config.settings_test --keepdb --parallel=auto candidatures stages
```

`config/settings_test.py` utilise `MD5PasswordHasher` → ×1000 plus rapide que PBKDF2.
**Ne jamais utiliser les settings de prod pour les tests.**

Les tests n'écrivent **jamais** dans `fichiers_prives/` : `settings_test` pointe `FICHIERS_PRIVES_ROOT` vers un
dossier temporaire supprimé en fin de suite, et le runner `commun.test_runner.StageTrackTestRunner` fait échouer
la suite si un fichier apparaît dans le vrai dossier. Inutile d'ajouter `override_settings(FICHIERS_PRIVES_ROOT=...)`.

---

## 3. Architecture

### Structure du projet

```
app-serein/
├── .venv/                  <- venv (jamais commite)
├── .env                    <- secrets (jamais commite)
├── .env.example            <- template a copier
├── backend/
│   ├── manage.py
│   ├── config/             <- settings.py, settings_test.py, urls.py, wsgi.py
│   ├── commun/             <- mixins, utils, services partages (pas de modeles)
│   ├── comptes/            <- Utilisateur, permissions, context_processors
│   ├── referentiels/       <- Departement, Personnel, Etablissement, TypeStage, CanalPublication
│   ├── offres/             <- Besoin, Offre, Publication, ParametreOffre
│   ├── candidatures/       <- Candidat, Candidature, PieceJointe, TransfertCandidature
│   ├── stages/             <- Stage, AffectationMaitreStage
│   ├── suivi/              <- Historique (GenericFK), Notification
│   ├── static/
│   ├── templates/
│   └── fichiers_prives/    <- PDF candidats + rapports (hors media/, jamais servi directement)
└── docs/
    ├── REGLES_GESTION.md   <- toutes les règles verifiees dans le code
    └── rapports/           <- rapports d'implementation des lots (C, D, E...)
```

### Apps et ordre de dépendance

| App | Rôle |
|---|---|
| `commun` | Utilitaires partagés — aucun modèle |
| `comptes` | `Utilisateur` (email, personnel, groupes), permissions, context processor |
| `referentiels` | Tables de référence : Departement, Personnel, Etablissement, TypeStage, CanalPublication |
| `offres` | Besoin, Offre, Publication, ParametreOffre (singleton) |
| `candidatures` | Candidat, Candidature, PieceJointe, TransfertCandidature |
| `stages` | Stage, AffectationMaitreStage |
| `suivi` | Historique (ContentType + object_id), Notification |

### Relations clés (vérifiées dans les modèles)

```
Departement  <-OneToOne->  Personnel       (responsable, nullable)
Utilisateur  <-OneToOne->  Personnel       (compte, related_name="compte")
Candidature  ->  Candidat, Departement, TypeStage, Offre (nullable)
Stage        <-OneToOne->  Candidature     (related_name="stage")
Stage        ->  Personnel                 (maitre_stage, PROTECT)
Historique   ->  ContentType + object_id   (GenericFK sur tout objet)
TransfertCandidature -> Candidature (CASCADE), Departement x2 (PROTECT)
AffectationMaitreStage -> Stage (CASCADE), Personnel (PROTECT)
```

Pour accéder à l'utilisateur depuis un personnel : `personnel.compte` (PAS `personnel.utilisateur`).
Pour filtrer les personnels sans compte : `Personnel.objects.filter(compte__isnull=True)`.

### Module commun (`backend/commun/`)

- **`ListeMixin`** (mixins.py) : hérite sur toute `ListView`. Pagination (20/page), `?q=` fulltext, `?actif=1|0`, `?tri=champ`. Injecte `params_paginateur`, `q`, `actif_filtre`, `tri_actuel`.
- **`supprimer_ou_desactiver(instance, request)`** (services.py) : tente `delete()`, intercepte `ProtectedError` → `actif=False`.
- **`ajouter_mois(date, n)`** (utils.py) : calcul correct des dates en mois entiers (gère fins de mois). Utiliser systématiquement — jamais `timedelta(days=30*n)`.
- **Templates** : `commun/formulaire.html` (Create/Update via crispy), `_pagination.html`, `_modal_confirmer.html` (POST + csrf), `_historique.html` (timeline).

### Logique métier

**Toujours dans `services.py`** — jamais dans les vues ni les modèles (sauf `clean()`).
Services : `@transaction.atomic` + `select_for_update()` sur l'objet principal.
Toujours vérifier toutes les préconditions AVANT la première écriture en base.

### Stockage privé des fichiers

- `FICHIERS_PRIVES_ROOT = backend/fichiers_prives/` — hors `MEDIA_ROOT`.
- `commun.stockage.StockagePrive` (FileSystemStorage qui relit `FICHIERS_PRIVES_ROOT` à chaque accès) → pas d'URL publique.
- Accès au fichier toujours via le stockage (`piece.fichier.path`, `stage.rapport.path`), jamais en reconstruisant le chemin.
- **Interdit** : `piece.fichier.url` ou `stage.rapport.url` dans les templates.
- Téléchargement uniquement via vues Django : `PieceJointeTelechargerView`, `RapportTelechargerView`.
- Production : Nginx + `X-Accel-Redirect` (ne jamais exposer `fichiers_prives/` directement).

### Commandes planifiées

| Commande | Frequence suggeree | Rôle |
|---|---|---|
| `python manage.py mettre_a_jour_stages` | 1×/nuit | A_VENIR→EN_COURS, EN_COURS→TERMINE, rappels evaluation J+7 |
| `python manage.py alerter_entretiens` | Toutes les 2 h | Alerte Secretaires : entretien < 48 h + candidat non informe |

Les deux commandes sont **idempotentes**. `mettre_a_jour_stages` accepte `--date AAAA-MM-JJ`.

---

## 4. Rôles et droits

### 3 rôles fixes (Django Groups, créés par init_donnees)

| Rôle | Droits |
|---|---|
| **Administrateur** | Toutes permissions sur `comptes` + `referentiels` ; **lecture seule** sur `offres`, `candidatures`, `stages`, `suivi`. Superuser sans groupe = Administrateur. |
| **Secrétaire** | Vue Besoin ; CRUD Offre + Publication ; CRUD Candidat + PieceJointe ; CRU Candidature ; Constituer + Modifier Stage. |
| **Responsable** | CU Besoin + Vue Offre (son département) ; Change/Vue Candidature (son département) ; Change/Vue Stage : terminer, interrompre, évaluer (son département). |

Matrice complète et idempotente : `referentiels/management/commands/init_donnees.py` → `GROUPES_PERMISSIONS`.

**Référentiels (écrans `/referentiels/`) : réservés à l'Administrateur** (`RolePermMixin`) — Secrétaire et
Responsable → 403 (RG-R3). Leurs permissions `view_*` sur `referentiels` ne donnent accès à aucun écran ;
les listes déroulantes des formulaires (départements, types de stage…) ne dépendent pas des permissions.

**Lecture seule de l'Administrateur — ne jamais lui redonner add/change/delete** sur ces apps.
Source unique : `comptes.permissions.APPS_LECTURE_SEULE_ADMINISTRATEUR`, utilisée par `init_donnees` ET par
l'écran F02 (cases grisées + filtrage serveur au POST). La liste exacte de ses 36 permissions est figée par
`referentiels.tests.InitDonneesCommandeTests.test_permissions_exactes_du_groupe_administrateur`.

### Contrôle d'accès

- `comptes/permissions.py` → `RoleRequisMixin(roles=[...])` (CBV) ; `@role_requis(...)` (FBV).
- `RolePermMixin` = Administrateur + `PermissionRequiredMixin` (superuser bypass les permissions Django).
- `LoginRequiredMiddleware` natif Django 5.1 protège toutes les vues. Exceptions : `@login_not_required`.
- Context processor : `role_utilisateur`, `nb_notifications`, `dernieres_notifications` (5 dernières).

### Scoping département (Responsable)

`_est_responsable(user)` = `user.groups.filter(name="Responsable").exists()`.
Si `user.personnel is None` → 403 ou redirect (vérification dans les vues).

---

## 5. Règles de gestion

> **Référence complète et numérotée** : [`docs/REGLES_GESTION.md`](docs/REGLES_GESTION.md)

Règles structurantes à mémoriser :

- **RG07** : une seule candidature active (RECUE ou EN_TRAITEMENT) par candidat.
- **RG09** : offre obligatoire si SUITE_OFFRE, interdite si SPONTANEE ou AUTRE.
- **RG11** : pièces jointes = PDF (magic bytes `%PDF`), **3 Mo** max, CV obligatoire à la création.
- **RG22** : maître de stage = personnel actif du même département que la candidature.
- Entretien ≥ 72 h après planification ; alerte secrétariat à J−48 h (`candidat_informe=False`).
- Accord : quota → `QuotaAtteint` non bloquant (2ème passage avec `confirmer_depassement=True`).
- Refus : motif obligatoire ; motif AUTRE → précision obligatoire.
- Redirection : RECUE uniquement → statut reste RECUE, tracée dans `TransfertCandidature`.
- Note 1–20 ; vivier si note ≥ 12 ; verrouillage 30 j après `date_evaluation` (note + vivier).
- Rapport de stage : **non verrouillé**, uploadable à tout moment après la première évaluation.
- **RG-E5** (voulu) : un Responsable lit le rapport d'un stage d'un autre département **uniquement si ce stage est au vivier**.
- **RG-E7** : fiche stage d'un autre département → 403 pour un Responsable, sauf stage au vivier (lecture seule, aucun bouton).
- `ParametreOffre` singleton : `delete()` est un no-op, `pk` forcé à 1.

---

## 6. Conventions et règles de revue

### Code

- **Langue** : français dans tous les identifiants (verbose_name, commentaires…), sans accents dans les noms Python.
- `TextChoices` pour toutes les énumérations.
- `__str__`, `class Meta` (verbose_name, ordering) sur chaque modèle.
- `on_delete=PROTECT` vers les référentiels ; `CASCADE` pour les compositions.
- Pas de `null=True` sur CharField/TextField : `blank=True` avec valeur vide.
- Commentaires uniquement quand le POURQUOI n'est pas évident. Pas de commentaires décrivant le QUOI.

### Données et migrations

- Jamais modifier une migration déjà appliquée : nouvelle migration uniquement.
- Renommages via `RenameModel` / `RenameField` (jamais suppression + recréation).
- `makemigrations --check --dry-run` = "No changes detected" avant chaque commit.
- Ne jamais inventer de données métier → marquer **"À VALIDER PAR SEREIN-GE"**.

### Logique métier

- Toute règle métier vit dans `services.py` ET dans le formulaire.
- `@transaction.atomic` + `select_for_update()` sur l'objet modifié.
- Vérifier TOUTES les préconditions AVANT la première écriture en base.
- Chaque transition : contrôle + historique + notifications.
- Dates : toujours `ajouter_mois()`. Jamais de calcul approximatif.

### Sécurité et accès

- Contrôles côté serveur (rôle + permission + département). Jamais uniquement côté template.
- Actions en POST uniquement. Pattern Post/Redirect/Get. Messages en français.
  Seule exception assumée : `notification_lire` accepte le GET (lien du menu ; marquer comme lue n'altère aucune donnée métier — RG-N4).
- Fichiers privés : jamais de `.url` dans les templates ; téléchargement via vue protégée.

### Tests

- Un test par règle métier + un test 403 pour chaque rôle non autorisé.
- **Pendant le dev** : `--settings=config.settings_test --keepdb --parallel=auto <apps modifiées>`.
- **Avant le commit** : suite complète `commun referentiels offres candidatures suivi stages comptes`.
- 0 échec obligatoire. Jamais les settings de prod pour les tests.

---

## 7. Méthode de travail avec moi

1. **Plan avant le code** : pour toute demande non triviale, présenter un plan complet (fichiers, migrations, tests, ordre) et attendre ma validation.
2. **Travailler par lots** (Lot E, F…) sur des branches dédiées (`lot-x`) depuis `main`.
3. **Un commit par lot**, après 0 échec sur la suite complète.
4. **Ne jamais pusher** sans mon accord explicite.
5. **Ne jamais inventer** de données métier → marquer "À VALIDER PAR SEREIN-GE".
6. Migrations additive-only.
7. Vérifier `makemigrations --check` avant chaque commit.
8. Rapports d'implémentation dans `docs/rapports/lot_X_rapport.md`.

---

## 8. État d'avancement

| Étape / Lot | Contenu | État | Commit |
|---|---|---|---|
| Étapes 1–2 | 6 apps, modèles, migrations, admin Django | ✅ | 962c0cf |
| Étape 3 | Auth, permissions, templates Bootstrap 5 | ✅ | cd10c23 |
| Étape 4 (F02–F07) | Module Administrateur : rôles, users, référentiels CRUD | ✅ | a3643ee |
| Étape 5 (F08, F09, F14, F17) | Besoins, offres, publications, notifs in-app | ✅ | 9e88b40 |
| Étape 6 (F10) | Candidatures : saisie, pièces jointes privées | ✅ | 841a958 |
| Étape 7 (F11) | Traitement candidatures par le Responsable | ✅ | 0eee903 |
| Étape 8 (F12) | Stages : constitution, suivi, commande auto | ✅ | 688d944 |
| Étape 9 (F13) | Évaluation + vivier + export CSV + rappels auto | ✅ | aab7f77 |
| Lot 0 | Renommage app → Stage Track | ✅ | 81fdb97 |
| Lot A | Membre → Personnel (modèles, vues, templates) | ✅ | 1f1b348 |
| Lot B | Durées TypeStage, dates candidature, PDF-only, 3 Mo | ✅ | b338348 |
| Lot C | ParametreOffre singleton, Offre.departement, texte_publie | ✅ | a0b2fd6 |
| Lot D | 72 h entretiens, alerter_entretiens, TransfertCandidature, AffectationMaitreStage | ✅ | bcd2999 |
| Fix | init_donnees sur base neuve + liste personnels (commun_tags) | ✅ | cae763e |
| Étape 10 (pages) | Test de toutes les pages × rôles + cloisonnement département (`commun/tests_pages.py`) | ✅ | — |

**Branche active** : `etape-10-constats` (contient `fix-fichiers-tests` ; à fusionner dans `main` après validation)
**Tests** : **295 / 295** ✅ — 0 echec

> Toute nouvelle route doit être déclarée dans `MATRICE` (`commun/tests_pages.py`), sinon la suite échoue.

---

## 9. En attente / À faire

### Lot E — Rôles personnalisés

Analyse complète : [`docs/rapports/lot_e_analyse.md`](docs/rapports/lot_e_analyse.md)

**Décision bloquante (E-R3)** avant tout développement :
- Option A : remplacer les gardes `roles=[...]` hardcodes par des permissions Django fines. Effort élevé, très flexible.
- Option B : ajouter un champ "famille de rôle" sur Group (variantes des 3 rôles existants). Effort modéré.

E-R1 (CRUD groupes), E-R2 (permissions sur groupes perso), E-R5 (audit trail permissions) sont indépendants et réalisables rapidement quelle que soit la décision E-R3.

### Prochaines étapes

| Étape | Contenu |
|---|---|
| Étape 10 | Finitions UX, accessibilité, optimisations requêtes |
| Étape 11 | Recette avec les utilisateurs finaux |
| Étape 12 | Déploiement Debian : Gunicorn, Nginx, X-Accel-Redirect, crons systemd |

### Questions ouvertes / À VALIDER PAR SEREIN-GE

| Sujet | Situation |
|---|---|
| TypeDemande AUTRE : cas d'usage exact ? | Implémenté sans offre, sans définition précise |
| Durées des 5 types de stage (duree_min/max) | Valeurs initiales de la migration 0004 (reprises par init_donnees) → à confirmer |
| Filtre "partenaire" sur listes : tous rôles ou Admin seul ? | Tous rôles (provisoire) |
| Fréquence cron `alerter_entretiens` | Toutes les 2 h (provisoire) |
| Fréquence cron `mettre_a_jour_stages` | 1×/nuit (provisoire) |
| **Lot E — architecture E-R3 : Option A ou B ?** | **Bloquant** |
| AffectationMaitreStage visible aux Administrateurs ? | Masqué (provisoire) |
| Notifications email SMTP en production | Non implémentées (in-app uniquement) |
| Constats 1 à 5 de l'étape 10 (droits Admin, fiche stage autre département, rapport vivier, accès Référentiels, GET notification_lire) | À trancher — voir [`docs/rapports/etape_10_pages_rapport.md`](docs/rapports/etape_10_pages_rapport.md) |
| Constat 6 : les tests écrivent dans le vrai `fichiers_prives/` | Correction proposée (petit lot séparé) |

---

## 10. Historique des décisions

| Décision | Raison | Lot/Étape |
|---|---|---|
| Membre → Personnel | Terminologie Serein-GE (glossaire projet) | Lot A |
| 3 types de demande : SPONTANEE, SUITE_OFFRE, AUTRE | Cahier des charges | Étape 6 |
| Administrateur = lecture seule hors comptes/referentiels | Séparation rôle admin-système / métier | Étape 4 |
| PDF uniquement + magic bytes %PDF | Contrôle réel du contenu, sécurité upload | Lot B |
| 3 Mo max par pièce (pas 5 Mo) | Valeur réelle vérifiée dans models.py | Lot B |
| 72 h minimum avant entretien | Demande directeur de mémoire | Lot D |
| Alerte secrétariat à 48 h si candidat non informé | Besoin opérationnel | Lot D |
| Accord = avertissement quota non bloquant | Décision Serein-GE | Étape 7 |
| Rapport stage non verrouillé (note/vivier seuls verrouillés) | Correction directeur de mémoire | Étape 9 |
| Personnel sans département autorisé | Employé avant affectation ou sans département | Lot A |
| Departement.responsable = OneToOne Personnel | Pas de champ booléen dupliqué | Étapes 1–4 |
| ParametreOffre singleton (pk=1, delete() no-op) | Une seule config pour toute l'appli | Lot C |
| Stockage fichiers dans fichiers_prives/ (hors media/) | Pas d'URL publique, contrôle via vues Django | Étape 6 |
| designer_responsable vérifie compte AVANT toute modif | Correction directeur de mémoire | Lot A |
| TransfertCandidature + AffectationMaitreStage | Traçabilité demandée | Lot D |
| Administrateur en lecture seule sur offres, candidatures, stages, suivi (view uniquement) | Régression introduite à l'Étape 4 (`a3643ee`, `_CRUD`) puis réimposée à chaque `init_donnees` (`permissions.set`) ; l'écran F02 permettait aussi de recocher les droits. Corrigé par une source unique + test de la liste exacte | Étape 10 |
