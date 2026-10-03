# Règles de gestion — Stage Track

> Document de référence généré à partir du code source (vérification directe sur models.py,
> services.py, forms.py). Dernière mise à jour : **2026-10-02** (lot D + vérifications pré-merge).

---

## Personnel (ex-Membre)

| # | Règle | Source |
|---|---|---|
| RG-P1 | Un personnel peut être sans département (`departement` nullable). | `referentiels/models.py` |
| RG-P2 | Le responsable d'un département doit appartenir à ce département (`clean()` sur Personnel). | `referentiels/models.py` |
| RG-P3 | Désactivation d'un personnel refusée s'il est responsable actuel d'un département. | `referentiels/services.py` |
| RG-P4 | Désactivation refusée si le personnel est maître de stage d'un stage A_VENIR ou EN_COURS. Remédiation : changer d'abord le maître de stage. | `referentiels/services.py` |
| RG-P5 | Désignation d'un responsable : le personnel doit être actif, avoir un département, et avoir un compte utilisateur (vérifié AVANT toute modification en base). | `referentiels/services.py` |
| RG-P6 | Si un responsable existant est remplacé sans confirmation → `ConfirmationRequise` (zéro changement en base). Avec confirmation → ancien compte désactivé, admins notifiés. | `referentiels/services.py` |
| RG-P7 | Un seul responsable par département (`Departement.responsable` = OneToOneField vers Personnel). | `referentiels/models.py` |

---

## Utilisateurs et accès

| # | Règle | Source |
|---|---|---|
| RG-U1 | Connexion par email (`USERNAME_FIELD = "email"`, pas de `username`). | `comptes/models.py` |
| RG-U2 | Rôle = premier groupe Django de l'utilisateur (`user.role = groups.first().name`). Un utilisateur = un groupe. | `comptes/models.py` |
| RG-U3 | Superutilisateur sans groupe → traité comme Administrateur dans `_role_utilisateur()`. | `comptes/permissions.py` |
| RG-U4 | Déconnexion automatique après 30 min d'inactivité (`SESSION_COOKIE_AGE = 1800`). | `config/settings.py` |
| RG-U5 | Un Responsable n'agit que sur les objets **de son département** (besoins, candidatures, stages). Sans personnel, sans département, ou objet d'un autre département → **403**, en GET comme en POST. Seules exceptions en lecture : stage au vivier (RG-E5, RG-E7). Les listes d'un Responsable sans département sont vides. | `offres/views.py`, `candidatures/views.py`, `stages/views.py` |
| RG-U6 | Si rôle change DE Responsable → autre rôle : `user.personnel = None ; user.save()`. | `comptes/views.py` (CLAUDE.md §F03) |
| RG-U7 | Auto-désactivation refusée (RG33 dans le code). | `comptes/views.py` |

---

## Référentiels

| # | Règle | Source |
|---|---|---|
| RG-R1 | Un référentiel utilisé ne peut pas être supprimé (`PROTECT`). Tentative → désactivation (`actif=False`) via `supprimer_ou_desactiver()`. | `commun/services.py` |
| RG-R2 | Durée min ≤ durée max sur TypeStage (`CheckConstraint` + `clean()`). | `referentiels/models.py` |
| RG-R3 | Les écrans Référentiels (départements, personnels, établissements, types de stage, canaux) sont **réservés à l'Administrateur** : Secrétaire et Responsable → 403, y compris en lecture. Les données restent proposées dans les listes déroulantes de leurs formulaires. | `referentiels/views.py` (`RolePermMixin`) |

---

## Offres et besoins

| # | Règle | Source |
|---|---|---|
| RG-O1 | La durée de l'offre (date_debut → date_fin) doit être dans les bornes [duree_min_mois, duree_max_mois] du TypeStage. | `offres/services.py` |
| RG-O2 | date_fin > date_debut pour Besoin et Offre (`CheckConstraint` + `clean()`). | `offres/models.py` |
| RG-O3 | nombre_places ≥ 1 (`CheckConstraint` + `clean()`). | `offres/models.py` |
| RG-O4 | Machines d'état : Besoin (ENVOYE→PRIS_EN_CHARGE→CLOTURE, ou ANNULE depuis ENVOYE/PRIS_EN_CHARGE) ; Offre (BROUILLON→OUVERTE↔SUSPENDUE→FERMEE). | `offres/services.py` |
| RG-O5 | Offre créée depuis un besoin : besoin doit être ENVOYE et sans offre existante (`select_for_update`). | `offres/services.py` |
| RG-O6 | **ParametreOffre** = singleton (pk forcé à 1, delete() = no-op). 8 variables dans le modèle de texte : `{contact}`, `{type_stage}`, `{departement}`, `{duree_min}`, `{duree_max}`, `{nombre_places}`, `{date_debut}`, `{date_fin}`. | `offres/models.py` |
| RG-O7 | `texte_publie` généré automatiquement à la création de l'offre, modifiable ensuite par la Secrétaire. | `offres/services.py` |
| RG-O8 | `Offre.places_restantes()` = nombre_places − candidatures.filter(statut=ACCORDEE).count(). | `offres/models.py` |

---

## Candidats et candidatures

| # | Règle | Source |
|---|---|---|
| RG07 | Un candidat ne peut avoir qu'une seule candidature active (statut RECUE ou EN_TRAITEMENT) simultanément. `UniqueConstraint` en base + contrôle service. | `candidatures/models.py` + services |
| RG09 | TypeDemande SUITE_OFFRE → offre obligatoire. TypeDemande SPONTANEE ou AUTRE → offre interdite. `CheckConstraint` + `clean()` + service. | `candidatures/models.py` + services |
| RG-C1 | Téléphone candidat normalisé : espaces/points/tirets supprimés, préfixe +226 ou 00226 retiré → 8 chiffres burkinabè. Appliqué à la saisie ET à la recherche. | `candidatures/services.py` |
| RG-C2 | Téléphone normalisé unique par candidat (`unique=True` sur le champ). | `candidatures/models.py` |
| RG-C3 | Date de début de disponibilité ≥ aujourd'hui (à la création ; pas vérifiée si inchangée à la modification). | `candidatures/services.py` |
| RG-C4 | Date de fin de disponibilité ≤ début + 12 mois (`ajouter_mois(debut, 12)`). | `candidatures/services.py` |
| RG-C5 | Durée souhaitée dans [type_stage.duree_min_mois, type_stage.duree_max_mois]. | `candidatures/services.py` |
| RG-C6 | Dépôt initial tracé dans l'historique (commentaire "Dépôt initial.", avec l'identité de la secrétaire). | `candidatures/services.py` |
| RG-C7 | Candidature modifiable uniquement si statut = RECUE. | `candidatures/views.py` |

---

## Pièces jointes

| # | Règle | Source |
|---|---|---|
| RG11 | Extension obligatoire : `.pdf`. Magic bytes vérifiés (`%PDF`). Taille max : **3 Mo**. | `candidatures/models.py` |
| RG-PJ1 | CV obligatoire à la création (au moins un fichier avec `type_piece = CV`). | `candidatures/services.py` |
| RG-PJ2 | Un seul exemplaire de chaque type de pièce par candidature, sauf TypePiece.AUTRE (illimité). `UniqueConstraint` en base. | `candidatures/models.py` |
| RG-PJ3 | Stockage dans `fichiers_prives/` (hors `MEDIA_ROOT`, `base_url=None`). Jamais de `.url` dans les templates. Téléchargement via vue protégée uniquement. | `candidatures/models.py` + `views.py` |

---

## Traitement des candidatures (Responsable)

| # | Règle | Source |
|---|---|---|
| RG-T1 | Présélection : RECUE → EN_TRAITEMENT. Reset `candidat_informe=False`, `date_information=None`. | `candidatures/services.py` |
| RG-T2 | Planifier entretien : EN_TRAITEMENT uniquement. Date ≥ maintenant + 72 h. Reset `alerte_entretien_envoyee=False`. | `candidatures/services.py` + forms |
| RG-T3 | Alerte entretien : commande `alerter_entretiens` ; filtre EN_TRAITEMENT + date dans 0-48 h + `candidat_informe=False` + `alerte_entretien_envoyee=False`. Idempotente. | `candidatures/management/commands/alerter_entretiens.py` |
| RG-T4 | Accord : EN_TRAITEMENT → ACCORDEE. Si offre liée et `places_restantes() ≤ 0` et `confirmer_depassement=False` → `QuotaAtteint` (avertissement, non bloquant). | `candidatures/services.py` |
| RG-T5 | Refus : RECUE ou EN_TRAITEMENT → REFUSEE. Motif obligatoire. Si motif = AUTRE → précision obligatoire. | `candidatures/services.py` |
| RG-T6 | Redirection : RECUE uniquement → département change, statut reste RECUE. Tracée dans `TransfertCandidature`. Notifie le responsable du nouveau département (ou admins si absent). | `candidatures/services.py` |
| RG-T7 | À chaque décision (présélection, entretien, accord, refus, redirection) : reset `candidat_informe=False`, `date_information=None`. | `candidatures/services.py` |
| RG19 | Candidats à informer : filtre `candidat_informe=False` + statut ACCORDEE ou REFUSEE. Secrétaire marque "informé" (`marquer_informe()`). | `candidatures/services.py` |
| RG-T8 | Pas d'espace stagiaire en ligne : la Secrétaire est le seul canal d'information du candidat. | Décision projet |

---

## Stages

| # | Règle | Source |
|---|---|---|
| RG22 | Maître de stage = personnel actif du même département que la candidature. | `stages/models.py` + services |
| RG-S1 | Constitution : candidature ACCORDEE, aucun stage existant, maître actif même département. | `stages/services.py` |
| RG-S2 | Statut à la création : date_debut ≤ aujourd'hui → EN_COURS ; sinon → A_VENIR. | `stages/services.py` |
| RG-S3 | date_fin_prevue > date_debut (`CheckConstraint` + `clean()`). | `stages/models.py` |
| RG-S4 | Modification : A_VENIR ou EN_COURS uniquement. date_debut modifiable seulement si A_VENIR. | `stages/services.py` |
| RG-S5 | Terminer : EN_COURS → TERMINE. date_fin_reelle ∈ [date_debut, aujourd'hui]. | `stages/services.py` |
| RG-S6 | Interrompre : A_VENIR ou EN_COURS → INTERROMPU. Motif obligatoire. | `stages/services.py` |
| RG-S7 | Historique des maîtres : `AffectationMaitreStage` créée à la constitution et à chaque changement de maître (pas de doublon si seule la date change). | `stages/services.py` |
| RG-S8 | Démarrage automatique (`mettre_a_jour_stages`) : A_VENIR → EN_COURS si date_debut ≤ aujourd'hui. Exécuté AVANT les clôtures. | `stages/services.py` |
| RG-S9 | Clôture automatique : EN_COURS → TERMINE si date_fin_prevue < aujourd'hui. Notifie le Responsable du département. | `stages/services.py` |
| RG-S10 | Rappel évaluation automatique : TERMINE + note=null + date_fin ≤ aujourd'hui-7j + rappel_evaluation_envoye=False → notif Responsable + flag posé (idempotent). | `stages/management/commands/mettre_a_jour_stages.py` |

---

## Évaluation et vivier

| # | Règle | Source |
|---|---|---|
| RG-E1 | Note obligatoirement entre 1 et 20 (`CheckConstraint` + `clean()` + service). | `stages/models.py` + services |
| RG-E2 | Vivier = True nécessite note ≥ 12 (`CheckConstraint` + `clean()` + service). | `stages/models.py` + services |
| RG-E3 | Verrouillage 30 jours après `date_evaluation` : note et vivier ne peuvent plus être modifiés. | `stages/services.py` |
| RG-E4 | Rapport de stage : non verrouillé, uploadable ou remplaçable à tout moment après le premier enregistrement de l'évaluation. | `stages/services.py` |
| RG-E5 | Rapport téléchargeable par le Responsable du même département. Un autre département (ou un Responsable sans département) y accède **seulement si `vivier=True`** — comportement voulu, décidé à l'étape 9 et confirmé à l'étape 10 (le vivier est partagé entre départements). Administrateur : autorisé. Secrétaire → 403. | `stages/views.py` (`RapportTelechargerView`) |
| RG-E6 | Vivier consultable par tous les Responsables et l'Administrateur (export CSV inclus). | `stages/views.py` |
| RG-E7 | Fiche stage : un Responsable ne voit que les stages de son département (sans département → 403). Exception : un stage **au vivier** d'un autre département est consultable **en lecture seule** — aucun bouton d'action, pas de lien vers la candidature. Secrétaire et Administrateur : non cloisonnés. | `stages/views.py` (`StageDetailView`) |

---

## Notifications

| # | Règle | Source |
|---|---|---|
| RG-N1 | Toutes les notifications passent par `suivi.services.notifier(destinataires, message, lien)`. Bulk create. | `suivi/services.py` |
| RG-N2 | Dropdown base.html : 5 dernières non lues (context processor). | `comptes/context_processors.py` |
| RG-N3 | Marquage individuel (`NotificationLireView`) ou tout marquer (`NotificationToutLireView`). | `suivi/views.py` |
| RG-N4 | **Exception assumée** à « actions en POST uniquement » : ouvrir `/notifications/<pk>/lire/` en GET marque la notification comme lue puis redirige vers son lien. Raison : le menu utilise de simples liens ; l'opération n'altère aucune donnée métier et se limite aux notifications de l'utilisateur connecté (autre utilisateur → 404). « Tout marquer comme lu » reste en POST. | `suivi/views.py` |

---

## Valeurs "À VALIDER PAR SEREIN-GE"

| Sujet | Situation actuelle |
|---|---|
| TypeDemande AUTRE | Cas d'usage exact non précisé ; implémenté comme "ni spontané, ni suite à offre" (offre interdite). |
| Durées des 5 types de stage | Créés par `init_donnees` sans duree_min/max → à compléter via l'interface Administrateur. |
| Filtre "partenaire" sur listes | Accessible à tous les rôles pour l'instant. |
| Fréquence cron `alerter_entretiens` | Toutes les 2 h provisoire. |
| Fréquence cron `mettre_a_jour_stages` | 1×/nuit provisoire. |
| Accès AffectationMaitreStage aux Admins | Masqué pour l'instant. |
| Notifications email SMTP | Non implémentées ; uniquement in-app. |
