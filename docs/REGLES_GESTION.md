# Règles de gestion — Stage Track

> Document de référence généré à partir du code source (vérification directe sur models.py,
> services.py, forms.py). Dernière mise à jour : **2026-10-03** (étape 10).
>
> Correspondance avec la numérotation du cahier des charges (RG01–RG35) : [`CORRESPONDANCE_RG.md`](CORRESPONDANCE_RG.md).

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
| RG-U8 | **Rôles de consultation** (lot E) : l'Administrateur peut créer des rôles supplémentaires qui permettent **uniquement de consulter**. Les 3 rôles de base (`ProfilRole.est_systeme`) ne sont ni supprimables, ni renommables, ni modifiables depuis l'écran des rôles de consultation. Nom unique, différent des rôles de base (casse ignorée). Un utilisateur a toujours **un seul** rôle. | `comptes/models.py` (`ProfilRole`), `comptes/services.py` |
| RG-U9 | Droits d'un rôle de consultation : **liste blanche de 11 droits**, chacun lié à un écran — `view_besoin`, `view_offre`, `view_publication`, `view_candidature`, `view_candidat`, `telecharger_pieces_jointes`, `view_stage`, `consulter_vivier`, `exporter_vivier`, `telecharger_rapports`, `view_historique`. Tout autre droit (`add_` / `change_` / `delete_`…) est refusé côté serveur, même envoyé à la main. L'écran des permissions des rôles de base refuse les rôles de consultation (404). | `comptes/permissions.py` (`DROITS_CONSULTATION`), `comptes/services.py` |
| RG-U10 | **Lecture seule** : un rôle de consultation actif ouvre une liste, une fiche ou un téléchargement seulement s'il a le droit correspondant (`ConsultationMixin`) ; il voit **tous les départements** ; toutes les vues d'action restent réservées aux rôles de base (403). Les pièces jointes des candidats (données personnelles) ne sont ni chargées ni affichées sans `telecharger_pieces_jointes`. Menu et tableau de bord construits d'après les droits ; notifications ouvertes sans droit. | `comptes/permissions.py`, vues offres / candidatures / stages / suivi |
| RG-U11 | Désactivation d'un rôle de consultation refusée tant qu'un utilisateur actif l'a. Rôle désactivé : aucun accès (message sur le tableau de bord, 403 ailleurs) ; réactivation d'un utilisateur refusée tant que son rôle est désactivé. | `comptes/services.py`, `comptes/views.py` |
| RG-U12 | **Page Historique** (journal des actions, lecture seule) : Administrateur et rôles de consultation ayant `view_historique` ; Secrétaire et Responsable : 403. Un lien vers l'objet n'apparaît que si l'utilisateur peut l'ouvrir. | `suivi/views.py` (`HistoriqueListView`) |

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
| RG-O4 | Machines d'état : Besoin — ENVOYE → PRIS_EN_CHARGE (création d'une offre depuis le besoin) → CLOTURE (fermeture de l'offre, RG-O9) ; ANNULE depuis ENVOYE ou PRIS_EN_CHARGE ; **CLOTURE et ANNULE sont finaux**. Offre — BROUILLON → OUVERTE ↔ SUSPENDUE → FERMEE (fermeture depuis OUVERTE ou SUSPENDUE) ; suppression possible en BROUILLON. | `offres/services.py` |
| RG-O5 | Offre créée depuis un besoin : besoin doit être ENVOYE et sans offre existante (`select_for_update`). | `offres/services.py` |
| RG-O6 | **ParametreOffre** = singleton (pk forcé à 1, delete() = no-op). 8 variables dans le modèle de texte : `{contact}`, `{type_stage}`, `{departement}`, `{duree_min}`, `{duree_max}`, `{nombre_places}`, `{date_debut}`, `{date_fin}`. | `offres/models.py` |
| RG-O7 | `texte_publie` généré automatiquement à la création de l'offre, modifiable ensuite par la Secrétaire. | `offres/services.py` |
| RG-O8 | `Offre.places_restantes()` = nombre_places − candidatures.filter(statut=ACCORDEE).count(). | `offres/models.py` |
| RG-O9 | **Fermer l'offre clôture le besoin** : dans la même transaction, si l'offre a un besoin lié au statut PRIS_EN_CHARGE, il passe à CLOTURE, avec une entrée d'historique (« Offre fermée ») et une notification aux Responsables du département du besoin. Besoin dans un autre statut (ex. ANNULE) ou offre sans besoin : aucun changement côté besoin, la fermeture de l'offre reste valide. CLOTURE est final : ni modification, ni annulation, ni nouvelle prise en charge. | `offres/services.py` (`fermer_offre`) |

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
| RG-S11 | Dates du stage dans la disponibilité du candidat : `date_debut ≥ debut_disponibilite` et `date_fin_prevue ≤ fin_disponibilite`, **bloquant** (formulaire + service), message avec la période du candidat. À la modification, le début n'est vérifié que s'il est modifiable (stage à venir jamais démarré) ; la fin l'est toujours. Stages existants inchangés : la règle s'applique à leur prochaine modification. | `stages/services.py` (`erreurs_disponibilite`), `stages/forms.py` |
| RG-S12 | **Reprise d'un stage interrompu** (Responsable du département du stage uniquement) : INTERROMPU → EN_COURS si la date de reprise est passée ou du jour, A_VENIR si elle est future. Date de reprise ≥ date d'interruption ; nouvelle fin prévue > date de reprise et ≤ fin de disponibilité du candidat ; motif obligatoire. `date_fin_reelle` remise à vide. Historique + notification aux Secrétaires. Une fin prévue déjà passée est acceptée (régularisation) : message d'information, clôture par la mise à jour quotidienne. Ensuite le cycle normal s'applique : démarrage automatique à la date de reprise (pas au début d'origine), clôture, évaluation. Après reprise, la date de début n'est plus modifiable ; terminer / interrompre exigent une date ≥ date de reprise. | `stages/services.py` (`reprendre_stage`, `date_demarrage_effective`) |
| RG-S13 | **Périodes d'interruption** (`PeriodeInterruption`) : créée à chaque interruption (date, motif, auteur), complétée à la reprise (date, motif, auteur). Toutes les périodes sont conservées et affichées sur la fiche stage. Une seule période ouverte par stage (contrainte en base). Les stages interrompus avant le lot F ont reçu leur période ouverte (migration 0006). Un stage à venir peut être interrompu avant sa date de début. | `stages/models.py`, `stages/services.py` |

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
| RG-E7 | Fiche stage : un Responsable ne voit que les stages de son département (sans département → 403). Exception : un stage **au vivier** d'un autre département est consultable en lecture seule, limitée aux colonnes du vivier (RG-E8). Secrétaire et Administrateur : non cloisonnés. | `stages/views.py` (`StageDetailView`) |
| RG-E8 | **Dossier du candidat sur la fiche stage.** Secrétaire, Administrateur et Responsable du département du stage : identité, contacts (téléphone, email, adresse), établissement, niveau et filière, type de demande, offre, période de disponibilité, durée souhaitée, pièces jointes (Voir / Télécharger via la vue protégée), lien vers la candidature. Responsable d'un autre département (stage au vivier) : **exactement les colonnes du vivier** — identité, téléphone, email, niveau d'études, filière, établissement, type de stage, département, période du stage, maître de stage (nom uniquement), note, rapport — et rien d'autre (ni pièces jointes, ni coordonnées du maître de stage, ni historique, ni périodes d'interruption, ni lien vers la candidature). Contrôle côté serveur : template dédié, ces données ne sont ni chargées ni transmises. | `stages/views.py`, `templates/stages/stage_detail_vivier.html` |

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
