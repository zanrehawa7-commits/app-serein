# Stage Track — Export pour la modélisation UML

> Extrait **du code source** (commit de référence : `a6db938` + lot `fix/besoin-cloture`, 2026-10-03), pour mettre à jour les
> diagrammes de classes, d'états et de cas d'utilisation du rapport.
>
> - Section 1 : générée par introspection des modèles Django (`_meta`) — champs, relations, contraintes,
>   méthodes tels que la base les définit.
> - Section 3 : générée à partir de la matrice des droits de `backend/commun/tests_pages.py`, **vérifiée par
>   la suite de tests** (chaque route × chaque rôle).
> - Sections 2 et 5 : relevées dans `services.py`, les vues et les commandes ; chaque ligne cite sa fonction.
> - Section 4 : contenu de `docs/REGLES_GESTION.md` et `docs/CORRESPONDANCE_RG.md`.
>
> Rien n'est inventé ; ce qui n'existe pas dans le code est signalé comme tel.

## Sommaire

1. [Modèles](#1-modèles)
2. [Cycles de statuts](#2-cycles-de-statuts)
3. [Acteurs et cas d'utilisation](#3-acteurs-et-cas-dutilisation)
4. [Règles de gestion](#4-règles-de-gestion)
5. [Commandes planifiées](#5-commandes-planifiées)

---

## 1. Modèles

Conventions :

- **Obligatoire** : `NOT NULL` et non vide. **facultatif (vide)** : chaîne vide autorisée (`blank=True`).
  **facultatif (NULL)** : `null=True`. **automatique** : rempli par Django (`auto_now_add`).
- **Multiplicité** : notation UML `A [x] ── [y] B` — un B est lié à x A ; un A est lié à y B. Ce sont les
  multiplicités **de la base**. Contrainte applicative non visible ici : un utilisateur a **un seul** groupe
  (rôle), bien que `groups` soit un ManyToMany (RG-U2, RG-U8).
- Les relations inverses (côté cible) sont données par `related_name` ; `+` = aucun accès inverse.

### App `comptes`

#### Utilisateur — « Utilisateur »

Table `comptes_utilisateur` · tri par défaut : last_name, first_name

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `password` | CharField (max 128) | obligatoire | — |
| `last_login` | DateTimeField | facultatif (NULL) | — |
| `is_superuser` | BooleanField | obligatoire | `False` |
| `first_name` | CharField (max 150) | facultatif (vide) | — |
| `last_name` | CharField (max 150) | facultatif (vide) | — |
| `is_staff` | BooleanField | obligatoire | `False` |
| `is_active` | BooleanField | obligatoire | `True` |
| `date_joined` | DateTimeField | obligatoire | `now()` |
| `email` | CharField (max 254, unique) | obligatoire | — |
| `telephone` | CharField (max 20) | facultatif (vide) | — |
| `personnel` | OneToOne → referentiels.Personnel | facultatif (NULL) | — |
| `groups` | ManyToMany → auth.Group | facultatif | — |
| `user_permissions` | ManyToMany → auth.Permission | facultatif | — |

Relations :

- `personnel` : **OneToOne** → `referentiels.Personnel` · related_name `compte` · on_delete `PROTECT` · multiplicité : Personnel [0..1] ── [0..1] Utilisateur
- `groups` : **ManyToMany** → `auth.Group` · related_name `user_set` · on_delete `—` · multiplicité : Group [0..*] ── [0..*] Utilisateur
- `user_permissions` : **ManyToMany** → `auth.Permission` · related_name `user_set` · on_delete `—` · multiplicité : Permission [0..*] ── [0..*] Utilisateur

Méthodes :

- `role()` (propriété)

#### ProfilRole — « Profil de rôle »

Table `comptes_profilrole` · tri par défaut : -est_systeme, groupe__name

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `groupe` | OneToOne → auth.Group | obligatoire | — |
| `description` | TextField | facultatif (vide) | — |
| `actif` | BooleanField | obligatoire | `True` |
| `est_systeme` | BooleanField | obligatoire | `False` |

Relations :

- `groupe` : **OneToOne** → `auth.Group` · related_name `profil` · on_delete `CASCADE` · multiplicité : Group [1] ── [0..1] ProfilRole

### App `referentiels`

#### Departement — « Département »

Table `referentiels_departement` · tri par défaut : nom

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `nom` | CharField (max 100, unique) | obligatoire | — |
| `description` | TextField | facultatif (vide) | — |
| `actif` | BooleanField | obligatoire | `True` |
| `responsable` | OneToOne → referentiels.Personnel | facultatif (NULL) | — |

Relations :

- `responsable` : **OneToOne** → `referentiels.Personnel` · related_name `departement_dirige` · on_delete `SET_NULL` · multiplicité : Personnel [0..1] ── [0..1] Departement

#### Personnel — « Personnel »

Table `referentiels_personnel` · tri par défaut : nom, prenom

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `nom` | CharField (max 100) | obligatoire | — |
| `prenom` | CharField (max 100) | obligatoire | — |
| `fonction` | CharField (max 150) | facultatif (vide) | — |
| `telephone` | CharField (max 20) | facultatif (vide) | — |
| `email` | CharField (max 254, unique) | facultatif (NULL) | — |
| `actif` | BooleanField | obligatoire | `True` |
| `departement` | ForeignKey → referentiels.Departement | facultatif (NULL) | — |

Relations :

- `departement` : **ForeignKey** → `referentiels.Departement` · related_name `personnels` · on_delete `PROTECT` · multiplicité : Departement [0..1] ── [0..*] Personnel

Méthodes :

- `clean()` (méthode)

#### Etablissement — « Établissement »

Table `referentiels_etablissement` · tri par défaut : nom

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `nom` | CharField (max 200, unique) | obligatoire | — |
| `ville` | CharField (max 100) | obligatoire | — |
| `contact` | CharField (max 150) | facultatif (vide) | — |
| `partenaire` | BooleanField | obligatoire | `False` |
| `actif` | BooleanField | obligatoire | `True` |

#### TypeStage — « Type de stage »

Table `referentiels_typestage` · tri par défaut : libelle

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `libelle` | CharField (max 100, unique) | obligatoire | — |
| `description` | TextField | facultatif (vide) | — |
| `remunere` | BooleanField | obligatoire | `False` |
| `actif` | BooleanField | obligatoire | `True` |
| `duree_min_mois` | PositiveSmallIntegerField (validateur MinValueValidator(1)) | obligatoire | — |
| `duree_max_mois` | PositiveSmallIntegerField (validateur MinValueValidator(1)) | obligatoire | — |

Contraintes BD :

- CHECK duree_max_mois ≥ duree_min_mois — `typestage_max_gte_min`

Méthodes :

- `clean()` (méthode)

#### CanalPublication — « Canal de publication »

Table `referentiels_canalpublication` · tri par défaut : nom

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `nom` | CharField (max 100, unique) | obligatoire | — |
| `description` | TextField | facultatif (vide) | — |
| `actif` | BooleanField | obligatoire | `True` |

### App `offres`

**Énumérations (TextChoices)**

- `StatutBesoin` : `ENVOYE` (Envoyé) · `PRIS_EN_CHARGE` (Pris en charge) · `CLOTURE` (Clôturé) · `ANNULE` (Annulé)
- `StatutOffre` : `BROUILLON` (Brouillon) · `OUVERTE` (Ouverte) · `SUSPENDUE` (Suspendue) · `FERMEE` (Fermée)

#### ParametreOffre — « Paramètre de texte d'offre »

Table `offres_parametreoffre` · tri par défaut : —

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `contact` | TextField | facultatif (vide) | — |
| `texte_modele` | TextField | facultatif (vide) | — |

Méthodes :

- `save()` (méthode)
- `delete()` (méthode)
- `get_instance()` (méthode de classe)

#### Besoin — « Besoin »

Table `offres_besoin` · tri par défaut : -date_creation

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `departement` | ForeignKey → referentiels.Departement | obligatoire | — |
| `type_stage` | ForeignKey → referentiels.TypeStage | obligatoire | — |
| `date_debut` | DateField | obligatoire | — |
| `date_fin` | DateField | obligatoire | — |
| `profil_recherche` | TextField | obligatoire | — |
| `nombre_places` | PositiveSmallIntegerField | obligatoire | — |
| `statut` | CharField (max 20, choix : StatutBesoin) | obligatoire | `StatutBesoin.ENVOYE` |
| `date_creation` | DateTimeField | automatique | date/heure de création |

Relations :

- `departement` : **ForeignKey** → `referentiels.Departement` · related_name `besoins` · on_delete `PROTECT` · multiplicité : Departement [1] ── [0..*] Besoin
- `type_stage` : **ForeignKey** → `referentiels.TypeStage` · related_name `besoins` · on_delete `PROTECT` · multiplicité : TypeStage [1] ── [0..*] Besoin

Contraintes BD :

- CHECK nombre_places ≥ 1 — `besoin_nombre_places_gte_1`
- CHECK date_fin > date_debut — `besoin_date_fin_gt_date_debut`

Méthodes :

- `clean()` (méthode)

#### Offre — « Offre »

Table `offres_offre` · tri par défaut : -date_creation

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `besoin` | OneToOne → offres.Besoin | facultatif (NULL) | — |
| `departement` | ForeignKey → referentiels.Departement | facultatif (NULL) | — |
| `type_stage` | ForeignKey → referentiels.TypeStage | obligatoire | — |
| `titre` | CharField (max 200) | obligatoire | — |
| `description` | TextField | obligatoire | — |
| `profil_recherche` | TextField | obligatoire | — |
| `date_debut` | DateField | obligatoire | — |
| `date_fin` | DateField | obligatoire | — |
| `nombre_places` | PositiveSmallIntegerField | obligatoire | — |
| `texte_publie` | TextField | facultatif (vide) | — |
| `statut` | CharField (max 20, choix : StatutOffre) | obligatoire | `StatutOffre.BROUILLON` |
| `date_creation` | DateTimeField | automatique | date/heure de création |

Relations :

- `besoin` : **OneToOne** → `offres.Besoin` · related_name `offre` · on_delete `PROTECT` · multiplicité : Besoin [0..1] ── [0..1] Offre
- `departement` : **ForeignKey** → `referentiels.Departement` · related_name `offres` · on_delete `PROTECT` · multiplicité : Departement [0..1] ── [0..*] Offre
- `type_stage` : **ForeignKey** → `referentiels.TypeStage` · related_name `offres` · on_delete `PROTECT` · multiplicité : TypeStage [1] ── [0..*] Offre

Contraintes BD :

- CHECK nombre_places ≥ 1 — `offre_nombre_places_gte_1`
- CHECK date_fin > date_debut — `offre_date_fin_gt_date_debut`

Méthodes :

- `clean()` (méthode)
- `places_restantes()` (méthode)

#### Publication — « Publication »

Table `offres_publication` · tri par défaut : -date_publication

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `offre` | ForeignKey → offres.Offre | obligatoire | — |
| `canal` | ForeignKey → referentiels.CanalPublication | obligatoire | — |
| `url` | CharField (max 200) | obligatoire | — |
| `description` | TextField | facultatif (vide) | — |
| `date_publication` | DateField | obligatoire | — |

Relations :

- `offre` : **ForeignKey** → `offres.Offre` · related_name `publications` · on_delete `CASCADE` · multiplicité : Offre [1] ── [0..*] Publication
- `canal` : **ForeignKey** → `referentiels.CanalPublication` · related_name `publications` · on_delete `PROTECT` · multiplicité : CanalPublication [1] ── [0..*] Publication

### App `candidatures`

**Énumérations (TextChoices)**

- `NiveauEtudes` : `BAC` (Bac) · `BTS` (BTS / DUT) · `L1` (Licence 1) · `L2` (Licence 2) · `L3` (Licence 3) · `M1` (Master 1) · `M2` (Master 2) · `DOC` (Doctorat) · `AUTRE` (Autre)
- `TypeDemande` : `SPONTANEE` (Spontanée) · `SUITE_OFFRE` (Suite à une offre) · `AUTRE` (Autre)
- `StatutCandidature` : `RECUE` (Reçue) · `EN_TRAITEMENT` (En traitement) · `ACCORDEE` (Accordée) · `REFUSEE` (Refusée)
- `MotifRefus` : `PROFIL_INADAPTE` (Profil inadapté) · `PERIODE_INDISPONIBLE` (Période indisponible) · `QUOTA_ATTEINT` (Quota atteint) · `DESISTEMENT` (Désistement) · `AUTRE` (Autre)
- `TypePiece` : `CV` (CV) · `LETTRE_MOTIVATION` (Lettre de motivation) · `LETTRE_DEMANDE` (Lettre de demande) · `LETTRE_RECOMMANDATION` (Lettre de recommandation) · `AUTRE` (Autre)

#### Candidat — « Candidat »

Table `candidatures_candidat` · tri par défaut : nom, prenom

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `nom` | CharField (max 100) | obligatoire | — |
| `prenom` | CharField (max 100) | obligatoire | — |
| `telephone` | CharField (max 20, unique) | obligatoire | — |
| `email` | CharField (max 254) | facultatif (vide) | — |
| `adresse` | TextField | facultatif (vide) | — |
| `niveau_etudes` | CharField (max 10, choix : NiveauEtudes) | facultatif (vide) | — |
| `filiere` | CharField (max 150) | facultatif (vide) | — |
| `etablissement` | ForeignKey → referentiels.Etablissement | facultatif (NULL) | — |
| `etablissement_autre` | CharField (max 200) | facultatif (vide) | — |

Relations :

- `etablissement` : **ForeignKey** → `referentiels.Etablissement` · related_name `candidats` · on_delete `PROTECT` · multiplicité : Etablissement [0..1] ── [0..*] Candidat

#### Candidature — « Candidature »

Table `candidatures_candidature` · tri par défaut : -date_depot

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `reference` | CharField (max 20, unique) | obligatoire | — |
| `candidat` | ForeignKey → candidatures.Candidat | obligatoire | — |
| `departement` | ForeignKey → referentiels.Departement | obligatoire | — |
| `offre` | ForeignKey → offres.Offre | facultatif (NULL) | — |
| `type_stage` | ForeignKey → referentiels.TypeStage | obligatoire | — |
| `type_demande` | CharField (max 20, choix : TypeDemande) | obligatoire | — |
| `debut_disponibilite` | DateField | obligatoire | — |
| `fin_disponibilite` | DateField | obligatoire | — |
| `duree_souhaitee` | PositiveSmallIntegerField | obligatoire | — |
| `statut` | CharField (max 20, choix : StatutCandidature) | obligatoire | `StatutCandidature.RECUE` |
| `motif_refus` | CharField (max 30, choix : MotifRefus) | facultatif (vide) | — |
| `precision_motif` | TextField | facultatif (vide) | — |
| `date_entretien` | DateTimeField | facultatif (NULL) | — |
| `commentaire` | TextField | facultatif (vide) | — |
| `candidat_informe` | BooleanField | obligatoire | `False` |
| `date_information` | DateTimeField | facultatif (NULL) | — |
| `alerte_entretien_envoyee` | BooleanField | obligatoire | `False` |
| `date_depot` | DateTimeField | automatique | date/heure de création |

Relations :

- `candidat` : **ForeignKey** → `candidatures.Candidat` · related_name `candidatures` · on_delete `PROTECT` · multiplicité : Candidat [1] ── [0..*] Candidature
- `departement` : **ForeignKey** → `referentiels.Departement` · related_name `candidatures` · on_delete `PROTECT` · multiplicité : Departement [1] ── [0..*] Candidature
- `offre` : **ForeignKey** → `offres.Offre` · related_name `candidatures` · on_delete `PROTECT` · multiplicité : Offre [0..1] ── [0..*] Candidature
- `type_stage` : **ForeignKey** → `referentiels.TypeStage` · related_name `candidatures` · on_delete `PROTECT` · multiplicité : TypeStage [1] ── [0..*] Candidature

Contraintes BD :

- UNIQUE (candidat) si statut ∈ {RECUE, EN_TRAITEMENT} — `candidature_unique_active_par_candidat`
- CHECK ((offre non NULL ET type_demande = 'SUITE_OFFRE') OU (offre est NULL ET type_demande = 'SPONTANEE') OU (offre est NULL ET type_demande = 'AUTRE')) — `candidature_offre_coherente_type_demande`
- CHECK fin_disponibilite > debut_disponibilite — `candidature_fin_dispo_gt_debut`

Méthodes :

- `clean()` (méthode)
- `save()` (méthode)
- `_generer_reference()` (méthode de classe)

#### TransfertCandidature — « Transfert de candidature »

Table `candidatures_transfertcandidature` · tri par défaut : -date_transfert

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `candidature` | ForeignKey → candidatures.Candidature | obligatoire | — |
| `departement_source` | ForeignKey → referentiels.Departement | obligatoire | — |
| `departement_cible` | ForeignKey → referentiels.Departement | obligatoire | — |
| `motif` | TextField | obligatoire | — |
| `realise_par` | ForeignKey → comptes.Utilisateur | facultatif (NULL) | — |
| `date_transfert` | DateTimeField | automatique | date/heure de création |

Relations :

- `candidature` : **ForeignKey** → `candidatures.Candidature` · related_name `transferts` · on_delete `CASCADE` · multiplicité : Candidature [1] ── [0..*] TransfertCandidature
- `departement_source` : **ForeignKey** → `referentiels.Departement` · related_name `(aucun accès inverse)` · on_delete `PROTECT` · multiplicité : Departement [1] ── [0..*] TransfertCandidature
- `departement_cible` : **ForeignKey** → `referentiels.Departement` · related_name `(aucun accès inverse)` · on_delete `PROTECT` · multiplicité : Departement [1] ── [0..*] TransfertCandidature
- `realise_par` : **ForeignKey** → `comptes.Utilisateur` · related_name `(aucun accès inverse)` · on_delete `SET_NULL` · multiplicité : Utilisateur [0..1] ── [0..*] TransfertCandidature

#### PieceJointe — « Pièce jointe »

Table `candidatures_piecejointe` · tri par défaut : type_piece

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `candidature` | ForeignKey → candidatures.Candidature | obligatoire | — |
| `type_piece` | CharField (max 30, choix : TypePiece) | obligatoire | — |
| `fichier` | FileField (max 100, stockage StockagePrive, validateur _valider_piece_jointe) | obligatoire | — |
| `nom_original` | CharField (max 255) | facultatif (vide) | — |
| `date_ajout` | DateTimeField | automatique | date/heure de création |

Relations :

- `candidature` : **ForeignKey** → `candidatures.Candidature` · related_name `pieces` · on_delete `CASCADE` · multiplicité : Candidature [1] ── [0..*] PieceJointe

Contraintes BD :

- UNIQUE (candidature, type_piece) si NON type_piece = 'AUTRE' — `piecejointe_unique_type_par_candidature`

Permissions personnalisées :

- `telecharger_pieces_jointes` — Télécharger les pièces jointes des candidats

### App `stages`

**Énumérations (TextChoices)**

- `StatutStage` : `A_VENIR` (À venir) · `EN_COURS` (En cours) · `TERMINE` (Terminé) · `INTERROMPU` (Interrompu)

#### Stage — « Stage »

Table `stages_stage` · tri par défaut : -date_debut

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `candidature` | OneToOne → candidatures.Candidature | obligatoire | — |
| `maitre_stage` | ForeignKey → referentiels.Personnel | obligatoire | — |
| `date_debut` | DateField | obligatoire | — |
| `date_fin_prevue` | DateField | obligatoire | — |
| `date_fin_reelle` | DateField | facultatif (NULL) | — |
| `statut` | CharField (max 20, choix : StatutStage) | obligatoire | `StatutStage.A_VENIR` |
| `motif_interruption` | TextField | facultatif (vide) | — |
| `note` | PositiveSmallIntegerField | facultatif (NULL) | — |
| `vivier` | BooleanField | obligatoire | `False` |
| `rapport` | FileField (max 100, stockage StockagePrive) | facultatif (NULL) | — |
| `date_evaluation` | DateField | facultatif (NULL) | — |
| `rappel_evaluation_envoye` | BooleanField | obligatoire | `False` |

Relations :

- `candidature` : **OneToOne** → `candidatures.Candidature` · related_name `stage` · on_delete `PROTECT` · multiplicité : Candidature [1] ── [0..1] Stage
- `maitre_stage` : **ForeignKey** → `referentiels.Personnel` · related_name `stages_encadres` · on_delete `PROTECT` · multiplicité : Personnel [1] ── [0..*] Stage

Contraintes BD :

- CHECK date_fin_prevue > date_debut — `stage_date_fin_prevue_gt_date_debut`
- CHECK (note est NULL OU (note ≥ 1 ET note ≤ 20)) — `stage_note_entre_1_et_20`
- CHECK (vivier = False OU note ≥ 12) — `stage_vivier_necessite_note_gte_12`

Permissions personnalisées :

- `consulter_vivier` — Consulter le vivier de talents
- `exporter_vivier` — Exporter le vivier (CSV)
- `telecharger_rapports` — Télécharger les rapports de stage

Méthodes :

- `date_demarrage_effective()` (méthode) — Date de la dernière reprise (RG-S12), sinon date de début : borne basse des dates saisies.
- `periode_interruption_ouverte()` (méthode)
- `clean()` (méthode)

#### AffectationMaitreStage — « Affectation de maître de stage »

Table `stages_affectationmaitrestage` · tri par défaut : -date_affectation

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `stage` | ForeignKey → stages.Stage | obligatoire | — |
| `maitre_stage` | ForeignKey → referentiels.Personnel | obligatoire | — |
| `affecte_par` | ForeignKey → comptes.Utilisateur | facultatif (NULL) | — |
| `date_affectation` | DateTimeField | automatique | date/heure de création |

Relations :

- `stage` : **ForeignKey** → `stages.Stage` · related_name `affectations_maitre` · on_delete `CASCADE` · multiplicité : Stage [1] ── [0..*] AffectationMaitreStage
- `maitre_stage` : **ForeignKey** → `referentiels.Personnel` · related_name `(aucun accès inverse)` · on_delete `PROTECT` · multiplicité : Personnel [1] ── [0..*] AffectationMaitreStage
- `affecte_par` : **ForeignKey** → `comptes.Utilisateur` · related_name `(aucun accès inverse)` · on_delete `SET_NULL` · multiplicité : Utilisateur [0..1] ── [0..*] AffectationMaitreStage

#### PeriodeInterruption — « Période d'interruption »

Table `stages_periodeinterruption` · tri par défaut : date_debut, pk

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `stage` | ForeignKey → stages.Stage | obligatoire | — |
| `date_debut` | DateField | obligatoire | — |
| `date_fin` | DateField | facultatif (NULL) | — |
| `motif_interruption` | TextField | obligatoire | — |
| `motif_reprise` | TextField | facultatif (vide) | — |
| `interrompu_par` | ForeignKey → comptes.Utilisateur | facultatif (NULL) | — |
| `repris_par` | ForeignKey → comptes.Utilisateur | facultatif (NULL) | — |

Relations :

- `stage` : **ForeignKey** → `stages.Stage` · related_name `periodes_interruption` · on_delete `CASCADE` · multiplicité : Stage [1] ── [0..*] PeriodeInterruption
- `interrompu_par` : **ForeignKey** → `comptes.Utilisateur` · related_name `(aucun accès inverse)` · on_delete `SET_NULL` · multiplicité : Utilisateur [0..1] ── [0..*] PeriodeInterruption
- `repris_par` : **ForeignKey** → `comptes.Utilisateur` · related_name `(aucun accès inverse)` · on_delete `SET_NULL` · multiplicité : Utilisateur [0..1] ── [0..*] PeriodeInterruption

Contraintes BD :

- CHECK (date_fin est NULL OU date_fin ≥ date_debut) — `periode_interruption_reprise_apres_interruption`
- UNIQUE (stage) si date_fin est NULL — `periode_interruption_une_seule_ouverte_par_stage`

### App `suivi`

#### Historique — « Historique »

Table `suivi_historique` · tri par défaut : -date_action

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `content_type` | ForeignKey → contenttypes.ContentType | obligatoire | — |
| `object_id` | PositiveIntegerField | obligatoire | — |
| `utilisateur` | ForeignKey → comptes.Utilisateur | facultatif (NULL) | — |
| `ancien_statut` | CharField (max 30) | facultatif (vide) | — |
| `nouveau_statut` | CharField (max 30) | facultatif (vide) | — |
| `commentaire` | TextField | facultatif (vide) | — |
| `date_action` | DateTimeField | automatique | date/heure de création |

Relations :

- `content_type` : **ForeignKey** → `contenttypes.ContentType` · related_name `historique_set` · on_delete `CASCADE` · multiplicité : ContentType [1] ── [0..*] Historique
- `utilisateur` : **ForeignKey** → `comptes.Utilisateur` · related_name `historiques` · on_delete `SET_NULL` · multiplicité : Utilisateur [0..1] ── [0..*] Historique
- `objet` : **GenericForeignKey** (`content_type` + `object_id`) → n'importe quel modèle ; multiplicité : 0..* entrées par objet, 1 objet par entrée

#### Notification — « Notification »

Table `suivi_notification` · tri par défaut : -date_creation

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | BigAutoField | clé primaire (auto) | — |
| `destinataire` | ForeignKey → comptes.Utilisateur | obligatoire | — |
| `message` | TextField | obligatoire | — |
| `lien` | CharField (max 200) | facultatif (vide) | — |
| `lue` | BooleanField | obligatoire | `False` |
| `date_creation` | DateTimeField | automatique | date/heure de création |

Relations :

- `destinataire` : **ForeignKey** → `comptes.Utilisateur` · related_name `notifications` · on_delete `CASCADE` · multiplicité : Utilisateur [1] ── [0..*] Notification

### Modèles Django utilisés

#### Group — « groupe »

Table `auth_group` · tri par défaut : —

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | AutoField | clé primaire (auto) | — |
| `name` | CharField (max 150, unique) | obligatoire | — |
| `permissions` | ManyToMany → auth.Permission | facultatif | — |

Relations :

- `permissions` : **ManyToMany** → `auth.Permission` · related_name `group_set` · on_delete `—` · multiplicité : Permission [0..*] ── [0..*] Group

#### Permission — « permission »

Table `auth_permission` · tri par défaut : content_type__app_label, content_type__model, codename

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | AutoField | clé primaire (auto) | — |
| `name` | CharField (max 255) | obligatoire | — |
| `content_type` | ForeignKey → contenttypes.ContentType | obligatoire | — |
| `codename` | CharField (max 100) | obligatoire | — |

Relations :

- `content_type` : **ForeignKey** → `contenttypes.ContentType` · related_name `permission_set` · on_delete `CASCADE` · multiplicité : ContentType [1] ── [0..*] Permission

Contraintes BD :

- UNIQUE (content_type, codename)

#### ContentType — « type de contenu »

Table `django_content_type` · tri par défaut : —

| Champ | Type | Obligatoire | Défaut |
|---|---|---|---|
| `id` | AutoField | clé primaire (auto) | — |
| `app_label` | CharField (max 100) | obligatoire | — |
| `model` | CharField (max 100) | obligatoire | — |

Contraintes BD :

- UNIQUE (app_label, model)

---

## 2. Cycles de statuts

« Manuelle » = déclenchée par un utilisateur depuis un écran ; « automatique » = commande planifiée
(section 5). Chaque transition enregistre une entrée d'historique (`suivi.services.enregistrer_historique`).

### 2.1 Besoin (`offres.Besoin.statut` — `StatutBesoin`)

| Départ | Arrivée | Fonction de service | Rôle | Type |
|---|---|---|---|---|
| — (création) | `ENVOYE` | `offres.services.creer_besoin` | Responsable (son département) | manuelle |
| `ENVOYE` | `PRIS_EN_CHARGE` | `offres.services.creer_offre` (création d'une offre à partir du besoin) | Secrétaire | manuelle |
| `ENVOYE`, `PRIS_EN_CHARGE` | `ANNULE` | `offres.services.annuler_besoin` | Responsable (son département) | manuelle |
| `PRIS_EN_CHARGE` | `CLOTURE` | `offres.services.fermer_offre` (fermeture de l'offre liée, RG-O9) — historique « Offre fermée » + notification aux Responsables du département | Secrétaire | manuelle (effet de la fermeture de l'offre) |

- La modification d'un besoin (`BesoinModifierView`) n'est possible qu'au statut `ENVOYE` et ne change pas le statut.
- `CLOTURE` et `ANNULE` sont des **états finaux** : ni modification, ni annulation, ni nouvelle prise en charge
  (`annuler_besoin` et `creer_offre` lèvent `TransitionInterdite`).
- Fermeture d'une offre dont le besoin n'est pas `PRIS_EN_CHARGE` (ex. `ANNULE`) : le besoin ne change pas.

### 2.2 Offre (`offres.Offre.statut` — `StatutOffre`)

| Départ | Arrivée | Fonction de service | Rôle | Type |
|---|---|---|---|---|
| — (création) | `BROUILLON` | `offres.services.creer_offre` | Secrétaire | manuelle |
| `BROUILLON` | `OUVERTE` | `offres.services.ouvrir_offre` | Secrétaire | manuelle |
| `OUVERTE` | `SUSPENDUE` | `offres.services.suspendre_offre` | Secrétaire | manuelle |
| `SUSPENDUE` | `OUVERTE` | `offres.services.rouvrir_offre` | Secrétaire | manuelle |
| `OUVERTE`, `SUSPENDUE` | `FERMEE` (+ besoin lié `PRIS_EN_CHARGE` → `CLOTURE`, RG-O9) | `offres.services.fermer_offre` | Secrétaire | manuelle |
| `BROUILLON` | (supprimée) | `offres.services.supprimer_offre` | Secrétaire | manuelle |

### 2.3 Candidature (`candidatures.Candidature.statut` — `StatutCandidature`)

| Départ | Arrivée | Fonction de service | Rôle | Type |
|---|---|---|---|---|
| — (création) | `RECUE` | `candidatures.services.creer_candidature` | Secrétaire | manuelle |
| `RECUE` | `RECUE` | `candidatures.services.modifier_candidature` | Secrétaire | manuelle |
| `RECUE` | `RECUE` (département changé, `TransfertCandidature` créé) | `candidatures.services.rediriger` | Responsable (son département) | manuelle |
| `RECUE` | `EN_TRAITEMENT` | `candidatures.services.preselectionner` | Responsable (son département) | manuelle |
| `EN_TRAITEMENT` | `EN_TRAITEMENT` (date d'entretien) | `candidatures.services.planifier_entretien` | Responsable (son département) | manuelle |
| `EN_TRAITEMENT` | `ACCORDEE` | `candidatures.services.accorder` | Responsable (son département) | manuelle |
| `RECUE`, `EN_TRAITEMENT` | `REFUSEE` | `candidatures.services.refuser` | Responsable (son département) | manuelle |

Actions sans changement de statut :

- `candidatures.services.marquer_informe` (Secrétaire) : `candidat_informe = True`, `date_information` renseignée.
- Commande `alerter_entretiens` (Système) : notifie les Secrétaires, pose `alerte_entretien_envoyee = True`.
- Une candidature `ACCORDEE` donne lieu à un stage (`stages.services.constituer_stage`) ; elle reste `ACCORDEE`.

`ACCORDEE` et `REFUSEE` sont des états finaux (aucune transition sortante).

### 2.4 Stage (`stages.Stage.statut` — `StatutStage`)

| Départ | Arrivée | Fonction de service | Rôle | Type |
|---|---|---|---|---|
| — (création depuis une candidature `ACCORDEE`) | `A_VENIR` si début futur, sinon `EN_COURS` | `stages.services.constituer_stage` | Secrétaire | manuelle |
| `A_VENIR`, `EN_COURS` | (inchangé : dates, maître de stage) | `stages.services.modifier_stage` | Secrétaire | manuelle |
| `A_VENIR` | `EN_COURS` | `stages.services.demarrer_stage_auto` (date de démarrage effective ≤ aujourd'hui) | Système (`mettre_a_jour_stages`) | automatique |
| `EN_COURS` | `TERMINE` | `stages.services.terminer_stage` | Responsable (son département) | manuelle |
| `EN_COURS` | `TERMINE` | `stages.services.cloturer_stage_auto` (date de fin prévue dépassée) | Système (`mettre_a_jour_stages`) | automatique |
| `A_VENIR`, `EN_COURS` | `INTERROMPU` (crée une `PeriodeInterruption`) | `stages.services.interrompre_stage` | Responsable (son département) | manuelle |
| `INTERROMPU` | `EN_COURS` si reprise passée ou du jour, sinon `A_VENIR` (complète la `PeriodeInterruption`) | `stages.services.reprendre_stage` | Responsable (son département) | manuelle |
| `TERMINE` | `TERMINE` (note, vivier, rapport) | `stages.services.evaluer_stage` (modifiable 30 jours, `peut_evaluer`) | Responsable (son département) | manuelle |

- Date de démarrage effective : `Stage.date_demarrage_effective()` = date de la dernière reprise, sinon `date_debut`.
- `TERMINE` est final pour le statut ; seule l'évaluation le modifie encore (30 jours après `date_evaluation`).

---

## 3. Acteurs et cas d'utilisation

Acteurs : **Administrateur**, **Secrétaire**, **Responsable** (rôles de base), **Rôle de consultation** (rôles
créés par l'Administrateur, lecture seule), **Système** (commandes planifiées, section 5).
Chaque cas cite sa route Django. « son département » : le Responsable n'agit que sur les objets de son
département (RG-U5).

### Administrateur

**Compte**

- Se connecter (`comptes:connexion`)
- Se déconnecter (`comptes:deconnexion`)
- Changer son mot de passe (`comptes:password_change`)
- Consulter son tableau de bord (`comptes:tableau_bord_admin`)

**Utilisateurs et rôles**

- Consulter les utilisateurs (`comptes:utilisateur_list`)
- Créer un utilisateur (`comptes:utilisateur_creer`)
- Modifier un utilisateur (dont son rôle) (`comptes:utilisateur_modifier`)
- Activer / désactiver un compte (`comptes:utilisateur_activer`)
- Réinitialiser le mot de passe d'un utilisateur (`comptes:utilisateur_reinit_mdp`)
- Consulter les rôles (`comptes:roles_list`)
- Gérer les permissions d'un rôle de base (`comptes:permissions_role`)
- Créer un rôle de consultation (`comptes:role_consultation_creer`)
- Modifier un rôle de consultation (`comptes:role_consultation_modifier`)
- Activer / désactiver un rôle de consultation (`comptes:role_consultation_activer`)

**Référentiels**

- Consulter les départements (`referentiels:departement_list`)
- Créer un département (`referentiels:departement_creer`)
- Consulter un département (`referentiels:departement_detail`)
- Modifier un département (dont désigner son responsable) (`referentiels:departement_modifier`)
- Supprimer (ou désactiver) un département (`referentiels:departement_supprimer`)
- Consulter le personnel (`referentiels:personnel_list`)
- Créer un personnel (`referentiels:personnel_creer`)
- Consulter un personnel (`referentiels:personnel_detail`)
- Modifier un personnel (`referentiels:personnel_modifier`)
- Désactiver un personnel (`referentiels:personnel_desactiver`)
- Consulter les établissements (`referentiels:etablissement_list`)
- Créer un établissement (`referentiels:etablissement_creer`)
- Modifier un établissement (`referentiels:etablissement_modifier`)
- Supprimer (ou désactiver) un établissement (`referentiels:etablissement_supprimer`)
- Marquer / retirer un établissement partenaire (`referentiels:etablissement_partenaire`)
- Consulter les types de stage (`referentiels:typestage_list`)
- Créer un type de stage (`referentiels:typestage_creer`)
- Modifier un type de stage (durées min / max) (`referentiels:typestage_modifier`)
- Supprimer (ou désactiver) un type de stage (`referentiels:typestage_supprimer`)
- Consulter les canaux de publication (`referentiels:canalpublication_list`)
- Créer un canal de publication (`referentiels:canalpublication_creer`)
- Modifier un canal de publication (`referentiels:canalpublication_modifier`)
- Supprimer (ou désactiver) un canal (`referentiels:canalpublication_supprimer`)

**Besoins et offres**

- Consulter les besoins (`offres:besoin_list`)
- Consulter un besoin (`offres:besoin_detail`)
- Consulter les offres (`offres:offre_list`)
- Consulter une offre (`offres:offre_detail`)
- Paramétrer le modèle de texte des offres (`offres:parametre_offre`)

**Candidatures**

- Consulter un candidat (`candidatures:candidat_detail`)
- Consulter les candidatures (`candidatures:candidature_list`)
- Consulter une candidature (`candidatures:candidature_detail`)
- Voir / télécharger une pièce jointe (`candidatures:piece_telecharger`)

**Stages**

- Consulter les stages (`stages:stage_list`)
- Consulter les stages à évaluer (`stages:stages_a_evaluer`)
- Consulter le vivier de talents (`stages:vivier`)
- Exporter le vivier (CSV) (`stages:vivier_export_csv`)
- Consulter un stage (dossier du candidat) (`stages:stage_detail`)
- Télécharger un rapport de stage (`stages:rapport_telecharger`)

**Suivi**

- Consulter ses notifications (`suivi:notification_list`)
- Marquer toutes ses notifications comme lues (`suivi:notification_tout_lire`)
- Ouvrir une notification (la marque comme lue) (`suivi:notification_lire`)
- Consulter l'historique des actions (`suivi:historique_list`)

### Secrétaire

**Compte**

- Se connecter (`comptes:connexion`)
- Se déconnecter (`comptes:deconnexion`)
- Changer son mot de passe (`comptes:password_change`)
- Consulter son tableau de bord (`comptes:tableau_bord_secretaire`)

**Besoins et offres**

- Consulter les besoins (`offres:besoin_list`)
- Consulter un besoin (`offres:besoin_detail`)
- Consulter les offres (`offres:offre_list`)
- Créer une offre (`offres:offre_creer`)
- Créer une offre à partir d'un besoin (`offres:offre_creer_depuis_besoin`)
- Consulter une offre (`offres:offre_detail`)
- Modifier une offre (`offres:offre_modifier`)
- Ouvrir une offre (`offres:offre_ouvrir`)
- Suspendre une offre (`offres:offre_suspendre`)
- Rouvrir une offre (`offres:offre_rouvrir`)
- Fermer une offre (`offres:offre_fermer`)
- Supprimer une offre (brouillon) (`offres:offre_supprimer`)
- Ajouter une publication à une offre (`offres:publication_creer`)
- Modifier une publication (`offres:publication_modifier`)
- Supprimer une publication (`offres:publication_supprimer`)

**Candidatures**

- Rechercher un candidat (`candidatures:candidat_recherche`)
- Enregistrer un candidat (`candidatures:candidat_creer`)
- Consulter un candidat (`candidatures:candidat_detail`)
- Modifier un candidat (`candidatures:candidat_modifier`)
- Enregistrer une candidature (`candidatures:candidature_creer`)
- Consulter les candidatures (`candidatures:candidature_list`)
- Consulter une candidature (`candidatures:candidature_detail`)
- Modifier une candidature (statut Reçue) (`candidatures:candidature_modifier`)
- Voir / télécharger une pièce jointe (`candidatures:piece_telecharger`)
- Consulter les candidats à informer (`candidatures:candidats_informer`)
- Marquer le candidat comme informé (`candidatures:candidature_informer`)

**Stages**

- Consulter les stages (`stages:stage_list`)
- Consulter un stage (dossier du candidat) (`stages:stage_detail`)
- Constituer un stage (`stages:stage_constituer`)
- Modifier un stage (dates, maître de stage) (`stages:stage_modifier`)

**Suivi**

- Consulter ses notifications (`suivi:notification_list`)
- Marquer toutes ses notifications comme lues (`suivi:notification_tout_lire`)
- Ouvrir une notification (la marque comme lue) (`suivi:notification_lire`)

### Responsable

**Compte**

- Se connecter (`comptes:connexion`)
- Se déconnecter (`comptes:deconnexion`)
- Changer son mot de passe (`comptes:password_change`)
- Consulter son tableau de bord (`comptes:tableau_bord_responsable`)

**Besoins et offres**

- Consulter les besoins — *son département* (`offres:besoin_list`)
- Exprimer un besoin de stage — *son département* (`offres:besoin_creer`)
- Consulter un besoin — *son département* (`offres:besoin_detail`)
- Modifier un besoin (statut Envoyé) — *son département* (`offres:besoin_modifier`)
- Annuler un besoin — *son département* (`offres:besoin_annuler`)
- Consulter les offres — *son département* (`offres:offre_list`)
- Consulter une offre — *son département* (`offres:offre_detail`)

**Candidatures**

- Consulter un candidat (`candidatures:candidat_detail`)
- Consulter les candidatures — *son département* (`candidatures:candidature_list`)
- Consulter une candidature — *son département* (`candidatures:candidature_detail`)
- Voir / télécharger une pièce jointe — *son département* (`candidatures:piece_telecharger`)
- Présélectionner une candidature — *son département* (`candidatures:candidature_preselectionner`)
- Planifier un entretien — *son département* (`candidatures:candidature_planifier_entretien`)
- Accorder une candidature — *son département* (`candidatures:candidature_accorder`)
- Refuser une candidature — *son département* (`candidatures:candidature_refuser`)
- Rediriger une candidature vers un autre département — *son département* (`candidatures:candidature_rediriger`)

**Stages**

- Consulter les stages — *son département* (`stages:stage_list`)
- Consulter les stages à évaluer — *son département* (`stages:stages_a_evaluer`)
- Consulter le vivier de talents — *tous départements* (`stages:vivier`)
- Exporter le vivier (CSV) — *tous départements* (`stages:vivier_export_csv`)
- Consulter un stage (dossier du candidat) — *son département ; autre département seulement si stage au vivier (lecture limitée, RG-E8)* (`stages:stage_detail`)
- Terminer un stage — *son département* (`stages:stage_terminer`)
- Interrompre un stage — *son département* (`stages:stage_interrompre`)
- Évaluer un stage (note, vivier, rapport) — *son département* (`stages:stage_evaluer`)
- Reprendre un stage interrompu — *son département* (`stages:stage_reprendre`)
- Télécharger un rapport de stage — *son département ; autre département seulement si stage au vivier (RG-E5)* (`stages:rapport_telecharger`)

**Suivi**

- Consulter ses notifications (`suivi:notification_list`)
- Marquer toutes ses notifications comme lues (`suivi:notification_tout_lire`)
- Ouvrir une notification (la marque comme lue) (`suivi:notification_lire`)

### Rôle de consultation (créé par l'Administrateur)

Lecture seule, tous départements. Chaque cas n'est ouvert que si le droit indiqué est coché (« — » : ouvert à tout rôle de consultation actif). Toute autre route : 403.

| Module | Cas d'utilisation | Droit requis | Route |
|---|---|---|---|
| Compte | Se connecter | — | `comptes:connexion` |
| Compte | Se déconnecter | — | `comptes:deconnexion` |
| Compte | Changer son mot de passe | — | `comptes:password_change` |
| Compte | Consulter son tableau de bord | — | `comptes:tableau_bord_consultation` |
| Besoins et offres | Consulter les besoins | `offres.view_besoin` | `offres:besoin_list` |
| Besoins et offres | Consulter un besoin | `offres.view_besoin` | `offres:besoin_detail` |
| Besoins et offres | Consulter les offres | `offres.view_offre` | `offres:offre_list` |
| Besoins et offres | Consulter une offre | `offres.view_offre` | `offres:offre_detail` |
| Candidatures | Consulter un candidat | `candidatures.view_candidat` | `candidatures:candidat_detail` |
| Candidatures | Consulter les candidatures | `candidatures.view_candidature` | `candidatures:candidature_list` |
| Candidatures | Consulter une candidature | `candidatures.view_candidature` | `candidatures:candidature_detail` |
| Candidatures | Voir / télécharger une pièce jointe | `candidatures.telecharger_pieces_jointes` | `candidatures:piece_telecharger` |
| Stages | Consulter les stages | `stages.view_stage` | `stages:stage_list` |
| Stages | Consulter un stage (dossier du candidat) | `stages.view_stage` | `stages:stage_detail` |
| Stages | Consulter le vivier de talents | `stages.consulter_vivier` | `stages:vivier` |
| Stages | Exporter le vivier (CSV) | `stages.exporter_vivier` | `stages:vivier_export_csv` |
| Stages | Télécharger un rapport de stage | `stages.telecharger_rapports` | `stages:rapport_telecharger` |
| Suivi | Consulter ses notifications | — | `suivi:notification_list` |
| Suivi | Marquer toutes ses notifications comme lues | — | `suivi:notification_tout_lire` |
| Suivi | Ouvrir une notification (la marque comme lue) | — | `suivi:notification_lire` |
| Suivi | Consulter l'historique des actions | `suivi.view_historique` | `suivi:historique_list` |

### Système (commandes planifiées)

- Démarrer automatiquement les stages à venir — `stages.services.demarrer_stage_auto`
- Clôturer automatiquement les stages dont la date de fin est dépassée (et notifier le Responsable) — `stages.services.cloturer_stage_auto`
- Rappeler au Responsable d'évaluer un stage terminé depuis 7 jours — commande `mettre_a_jour_stages`
- Alerter les Secrétaires d'un entretien dans moins de 48 h, candidat non informé — commande `alerter_entretiens`

### Relations « include » / « extend » (vérifiées dans le code)

| Cas de base | Relation | Cas lié | Où dans le code |
|---|---|---|---|
| Enregistrer une candidature | «include» | Joindre les pièces (un CV obligatoire, PDF ≤ 3 Mo) | `candidatures.services._valider_candidature` |
| Enregistrer une candidature | «extend» | Enregistrer un candidat (s'il n'existe pas) | `CandidatRechercheView` → `CandidatCreateView` |
| Refuser une candidature | «include» | Saisir le motif (précision obligatoire si « Autre ») | `candidatures.services.refuser` |
| Rediriger une candidature | «include» | Choisir le département cible et saisir le motif | `RedirigerForm`, `candidatures.services.rediriger` |
| Accorder une candidature | «extend» | Confirmer le dépassement du quota de l'offre | `QuotaAtteint`, `confirmer_depassement` |
| Planifier un entretien | «include» | Respecter le délai de 72 h | `EntretienForm`, `planifier_entretien` |
| Créer une offre à partir d'un besoin | «include» | Passer le besoin à « Pris en charge » | `offres.services.creer_offre` |
| Fermer une offre | «include» | Clôturer le besoin lié s'il est « Pris en charge » (+ notifier le Responsable) | `offres.services.fermer_offre` |
| Constituer un stage | «include» | Choisir un maître de stage actif du département (RG22) | `stages.services.constituer_stage` |
| Constituer / modifier un stage | «include» | Vérifier les dates dans la disponibilité du candidat (RG-S11) | `stages.services.erreurs_disponibilite` |
| Modifier un stage | «extend» | Changer de maître de stage (trace `AffectationMaitreStage`) | `stages.services.modifier_stage` |
| Interrompre un stage | «include» | Saisir le motif d'interruption | `stages.services.interrompre_stage` |
| Reprendre un stage interrompu | «include» | Saisir le motif de reprise et la nouvelle fin prévue | `stages.services.reprendre_stage` |
| Évaluer un stage | «extend» | Déposer le rapport de stage (facultatif) | `EvaluerStageForm.rapport` |
| Évaluer un stage | «extend» | Ajouter au vivier (note ≥ 12) | `stages.services.evaluer_stage` |
| Modifier un département | «extend» | Désigner le responsable (confirmation si remplacement) | `referentiels.services.designer_responsable` |
| Créer / modifier un utilisateur | «include» | Choisir un rôle ; lier un personnel si Responsable | `UtilisateurCreerForm`, `UtilisateurModifierForm` |
| Toute transition de statut | «include» | Enregistrer l'historique | `suivi.services.enregistrer_historique` |

---

## 4. Règles de gestion

Contenu intégral de `docs/REGLES_GESTION.md` (4.1) et de `docs/CORRESPONDANCE_RG.md` (4.2), tels qu'au commit
de référence.

### 4.1 Règles de gestion vérifiées dans le code

> Document de référence généré à partir du code source (vérification directe sur models.py,
> services.py, forms.py). Dernière mise à jour : **2026-10-03** (étape 10).
>
> Correspondance avec la numérotation du cahier des charges (RG01–RG35) : [`CORRESPONDANCE_RG.md`](CORRESPONDANCE_RG.md).

---

#### Personnel (ex-Membre)

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

#### Utilisateurs et accès

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

#### Référentiels

| # | Règle | Source |
|---|---|---|
| RG-R1 | Un référentiel utilisé ne peut pas être supprimé (`PROTECT`). Tentative → désactivation (`actif=False`) via `supprimer_ou_desactiver()`. | `commun/services.py` |
| RG-R2 | Durée min ≤ durée max sur TypeStage (`CheckConstraint` + `clean()`). | `referentiels/models.py` |
| RG-R3 | Les écrans Référentiels (départements, personnels, établissements, types de stage, canaux) sont **réservés à l'Administrateur** : Secrétaire et Responsable → 403, y compris en lecture. Les données restent proposées dans les listes déroulantes de leurs formulaires. | `referentiels/views.py` (`RolePermMixin`) |

---

#### Offres et besoins

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

#### Candidats et candidatures

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

#### Pièces jointes

| # | Règle | Source |
|---|---|---|
| RG11 | Extension obligatoire : `.pdf`. Magic bytes vérifiés (`%PDF`). Taille max : **3 Mo**. | `candidatures/models.py` |
| RG-PJ1 | CV obligatoire à la création (au moins un fichier avec `type_piece = CV`). | `candidatures/services.py` |
| RG-PJ2 | Un seul exemplaire de chaque type de pièce par candidature, sauf TypePiece.AUTRE (illimité). `UniqueConstraint` en base. | `candidatures/models.py` |
| RG-PJ3 | Stockage dans `fichiers_prives/` (hors `MEDIA_ROOT`, `base_url=None`). Jamais de `.url` dans les templates. Téléchargement via vue protégée uniquement. | `candidatures/models.py` + `views.py` |

---

#### Traitement des candidatures (Responsable)

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

#### Stages

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

#### Évaluation et vivier

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

#### Notifications

| # | Règle | Source |
|---|---|---|
| RG-N1 | Toutes les notifications passent par `suivi.services.notifier(destinataires, message, lien)`. Bulk create. | `suivi/services.py` |
| RG-N2 | Dropdown base.html : 5 dernières non lues (context processor). | `comptes/context_processors.py` |
| RG-N3 | Marquage individuel (`NotificationLireView`) ou tout marquer (`NotificationToutLireView`). | `suivi/views.py` |
| RG-N4 | **Exception assumée** à « actions en POST uniquement » : ouvrir `/notifications/<pk>/lire/` en GET marque la notification comme lue puis redirige vers son lien. Raison : le menu utilise de simples liens ; l'opération n'altère aucune donnée métier et se limite aux notifications de l'utilisateur connecté (autre utilisateur → 404). « Tout marquer comme lu » reste en POST. | `suivi/views.py` |

---

#### Valeurs "À VALIDER PAR SEREIN-GE"

| Sujet | Situation actuelle |
|---|---|
| TypeDemande AUTRE | Cas d'usage exact non précisé ; implémenté comme "ni spontané, ni suite à offre" (offre interdite). |
| Durées des 5 types de stage | Créés par `init_donnees` sans duree_min/max → à compléter via l'interface Administrateur. |
| Filtre "partenaire" sur listes | Accessible à tous les rôles pour l'instant. |
| Fréquence cron `alerter_entretiens` | Toutes les 2 h provisoire. |
| Fréquence cron `mettre_a_jour_stages` | 1×/nuit provisoire. |
| Accès AffectationMaitreStage aux Admins | Masqué pour l'instant. |
| Notifications email SMTP | Non implémentées ; uniquement in-app. |

### 4.2 Correspondance cahier des charges (RG01–RG35) → code

> Pour citer les règles dans le rapport de stage.
> **Cahier des charges** : règles numérotées **RG01 à RG35**.
> **Code** : numérotation de [`REGLES_GESTION.md`](REGLES_GESTION.md) (RG-U*, RG-P*, RG-R*, RG-E*, RG-S*, RG-N*…),
> qui reprend tel quel le numéro du cahier quand le code le cite (RG07, RG09…).
>
> Le texte du cahier des charges **n'est pas dans le dépôt**. Seules les correspondances vérifiables sont remplies ;
> les autres sont marquées **À COMPLÉTER** — ne pas les deviner.
> Dernière mise à jour : 2026-10-03.

#### Niveau de certitude

| Niveau | Signification |
|---|---|
| **Certain** | Le code cite explicitement le numéro du cahier, et la règle y est décrite dans `REGLES_GESTION.md`. |
| **Indiqué** | Correspondance donnée par l'auteur du projet, non citée dans le code. |
| **À confirmer** | Le code cite le numéro, mais le rattachement à une règle de `REGLES_GESTION.md` est une lecture du code. |

#### Tableau RG01 → RG35

| Cahier | Code | Règle (résumé) | Certitude | Où dans le code |
|---|---|---|---|---|
| RG01 | — | À COMPLÉTER | — | — |
| RG02 | — | À COMPLÉTER | — | — |
| RG03 | — | À COMPLÉTER | — | — |
| RG04 | — | À COMPLÉTER | — | — |
| RG05 | — | À COMPLÉTER | — | — |
| RG06 | — | À COMPLÉTER | — | — |
| **RG07** | **RG07** | Une seule candidature active (RECUE ou EN_TRAITEMENT) par candidat. | Certain | `candidatures/models.py` (contrainte), `candidatures/services.py` |
| RG08 | — | À COMPLÉTER | — | — |
| **RG09** | **RG09** | Offre obligatoire si SUITE_OFFRE, interdite si SPONTANEE ou AUTRE. | Certain | `candidatures/models.py`, `candidatures/services.py` |
| RG10 | — | À COMPLÉTER | — | — |
| **RG11** | **RG11** | Pièces jointes : PDF uniquement (`%PDF`), 3 Mo maximum. | Certain | `candidatures/models.py` |
| RG12 | — | À COMPLÉTER | — | — |
| **RG13** | **RG-U5** (+ RG-E7) | Un Responsable n'agit que sur les objets de son département ; sinon 403. | À confirmer | `comptes/permissions.py` (`DepartementResponsableMixin`), vues offres / candidatures / stages |
| RG14 | — | À COMPLÉTER | — | — |
| RG15 | — | À COMPLÉTER | — | — |
| RG16 | — | À COMPLÉTER | — | — |
| RG17 | — | À COMPLÉTER | — | — |
| RG18 | — | À COMPLÉTER | — | — |
| **RG19** | **RG19** | Candidats à informer (ACCORDEE ou REFUSEE, non informés) ; la Secrétaire marque « informé ». | Certain | `candidatures/services.py` |
| RG20 | — | À COMPLÉTER | — | — |
| RG21 | — | À COMPLÉTER | — | — |
| **RG22** | **RG22** | Maître de stage = personnel actif du même département que la candidature. | Certain | `stages/models.py`, `stages/services.py` |
| RG23 | — | À COMPLÉTER | — | — |
| RG24 | — | À COMPLÉTER | — | — |
| RG25 | — | À COMPLÉTER | — | — |
| RG26 | — | À COMPLÉTER | — | — |
| RG27 | — | À COMPLÉTER | — | — |
| RG28 | — | À COMPLÉTER | — | — |
| **RG29** | **RG-E5** | Un Responsable lit le rapport d'un stage d'un autre département uniquement si ce stage est au vivier. | Indiqué | `stages/views.py` (`RapportTelechargerView`) |
| RG30 | — | À COMPLÉTER | — | — |
| **RG31** | **RG-P2 / RG-P5** | Responsable d'un département choisi parmi les personnels actifs de ce département. | À confirmer | `referentiels/forms.py` (aide du champ), `referentiels/services.py` |
| RG32 | — | À COMPLÉTER | — | — |
| **RG33** | **RG-U7** | Un administrateur ne peut pas désactiver son propre compte. | Certain | `comptes/views.py` (`UtilisateurActiverView`) |
| RG34 | — | À COMPLÉTER | — | — |
| RG35 | — | À COMPLÉTER | — | — |

**Bilan** : 9 / 35 renseignées (6 certaines, 1 indiquée, 2 à confirmer) — 26 à compléter à partir du cahier des charges.

#### Règles du code sans numéro du cahier connu

À rattacher à un numéro RGxx lors de la complétion du tableau ci-dessus (ou à signaler comme règles ajoutées
pendant le développement).

| Code | Règle (résumé) | Origine |
|---|---|---|
| RG-E7 | Fiche stage d'un autre département : 403 pour un Responsable, sauf stage au vivier (lecture seule, colonnes du vivier). | Décision étape 10, précisée au lot F |
| RG-E8 | Dossier du candidat sur la fiche stage ; Responsable d'un autre département : colonnes du vivier uniquement. | Lot F (directeur de mémoire) |
| RG-R3 | Écrans Référentiels réservés à l'Administrateur. | Décision étape 10 |
| RG-N4 | Exception assumée : `notification_lire` accepte le GET. | Décision étape 10 |
| RG-E1 à RG-E4, RG-E6 | Note 1–20, vivier si note ≥ 12, verrouillage 30 jours, rapport non verrouillé, vivier consultable. | Étape 9 |
| RG-S1 à RG-S10 | Constitution, transitions et automatisation des stages. | Étape 8 |
| RG-S11 | Dates du stage dans la disponibilité du candidat (bloquant). | Lot F (directeur de mémoire) |
| RG-S12, RG-S13 | Reprise d'un stage interrompu ; périodes d'interruption conservées. | Lot F (directeur de mémoire) |
| RG-O9 | Fermer l'offre → le besoin lié PRIS_EN_CHARGE passe à CLOTURE (état final), historique + notification. | Spécification de l'étape 5, implémentée au lot fix/besoin-cloture |
| RG-R1, RG-R2 | Suppression → désactivation si utilisé ; durée min ≤ max. | Étapes 4 / lot B |
| RG-P1 à RG-P7 | Règles sur le personnel et les responsables de département. | Lot A |
| RG-U1 à RG-U4, RG-U6 | Connexion par email, rôle = groupe, superuser, session 30 min, changement de rôle. | Étapes 3–4 |
| RG-U8 à RG-U12 | Rôles de consultation (lecture seule) : création, 11 droits en liste blanche, accès par droit, désactivation, page Historique. | Lot E (version réduite, option C) |
| RG-N1 à RG-N3 | Notifications in-app. | Étape 5 |

Liste complète et à jour : [`REGLES_GESTION.md`](REGLES_GESTION.md).

---

## 5. Commandes planifiées

| Commande | Rôle (texte d'aide du code) | Fréquence prévue | Options |
|---|---|---|---|
| `mettre_a_jour_stages` | « Démarre les stages à venir et clôture les stages en cours dont la date est dépassée. » + rappels d'évaluation J+7 | 1×/nuit (provisoire) | `--date AAAA-MM-JJ` |
| `alerter_entretiens` | « Envoie une alerte aux Secrétaires pour les entretiens dans moins de 48 h dont le candidat n'a pas encore été informé. » | toutes les 2 h (provisoire) | — |

- Les deux commandes sont idempotentes. **La fréquence n'est pas dans le code** (aucune configuration cron dans
  le dépôt) : valeurs provisoires notées dans `REGLES_GESTION.md`, **À VALIDER PAR SEREIN-GE**.
- Commandes d'installation, non planifiées : `init_donnees` (« Initialise les groupes, permissions et
  référentiels de base (idempotent). ») et `init_demo` (« Crée les comptes et données de démonstration
  (idempotent). » — refusée si `DEBUG=False`).
