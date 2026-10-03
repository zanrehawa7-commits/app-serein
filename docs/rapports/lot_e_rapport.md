# Lot E — Rapport d'implémentation
## Rôles de consultation (version réduite, option C)

**Date** : 2026-10-03
**Branche** : `lot-e` (5 commits, un par sous-partie)
**Tests** : 365 / 365 OK (0 échec) — 329 avant le lot, +36
**Migrations** (additives) : `comptes/0004_profilrole`, `comptes/0005_profils_roles_systeme` (données),
`stages/0007_permissions_consultation`, `candidatures/0009_permission_pieces_jointes`
**Analyse préalable** : [`lot_e_analyse.md`](lot_e_analyse.md)

---

## Décision

L'analyse proposait deux refontes du contrôle d'accès (option A : permissions fines par action ; option B :
« famille de rôle »). **Décision : version réduite « rôles de consultation » (option C).** L'Administrateur peut
créer des rôles supplémentaires (ex. Direction générale, RH, Auditeur) qui permettent **uniquement de
consulter**. Toutes les vues d'action restent réservées aux 3 rôles de base, **sans modification**. La refonte
complète est reportée en V2 (voir la dernière section).

Décisions validées avant développement :

| # | Question | Décision |
|---|---|---|
| 1 | Page Historique (n'existait pas) | Créée, lecture seule : Administrateur + rôles de consultation ayant `view_historique` ; Secrétaire et Responsable : 403 |
| 2 | Droits proposés | Les 11 droits liés à un écran (6 permissions `view_` sans écran écartées) |
| 3 | Notifications | Ouvertes aux rôles de consultation, sans droit à cocher |
| 4 | Réactivation d'un utilisateur dont le rôle est désactivé | Refusée, avec message |

---

## E1 — Modèle (`eb53896`)

- `comptes.ProfilRole` (OneToOne `Group`) : `description`, `actif`, `est_systeme` (vrai pour les 3 rôles de base,
  posé par la migration 0005 et par `init_donnees`).
- 4 permissions personnalisées : `consulter_vivier`, `exporter_vivier`, `telecharger_rapports` (Stage),
  `telecharger_pieces_jointes` (PieceJointe).
- `comptes/permissions.py` : `DROITS_CONSULTATION` (liste blanche), `est_role_consultation`, `a_acces`.
- Liste exacte des permissions de l'Administrateur : + CRUD `profilrole` (il gère les rôles) → 41.

## E2 — Écran Administrateur (`a0410a1`)

- « Rôles & permissions » : 3 rôles de base (écran inchangé) + tableau des rôles de consultation et bouton
  « Nouveau rôle de consultation » (nom, description, 11 cases à cocher).
- Vérifications côté serveur : nom unique et différent des rôles de base ; droits limités à la liste blanche ;
  désactivation refusée tant qu'un utilisateur actif a le rôle ; rôles de base → 404 sur ces écrans.
- **Faille corrigée** : l'écran des permissions des rôles de base acceptait n'importe quel groupe ; un rôle de
  consultation aurait pu y recevoir `add_` / `change_` / `delete_`. Il est limité aux 3 rôles de base.
- Création / modification d'utilisateur : rôles de base + rôles de consultation actifs.

## E3 — Contrôle d'accès en lecture seule (`eb5998d`)

- `ConsultationMixin` : rôle de base autorisé (comportement inchangé) **ou** rôle de consultation actif ayant
  le droit requis. Appliqué à **16 vues** de liste, détail et téléchargement :

| Vues | Droit requis |
|---|---|
| Besoins (liste, fiche) | `view_besoin` |
| Offres (liste, fiche) ; bloc Publications | `view_offre` ; `view_publication` |
| Fiche candidat | `view_candidat` |
| Candidatures (liste, fiche) | `view_candidature` |
| Téléchargement d'une pièce jointe | `telecharger_pieces_jointes` |
| Stages (liste, fiche) | `view_stage` |
| Vivier / export CSV / rapport | `consulter_vivier` / `exporter_vivier` / `telecharger_rapports` |
| Notifications (3 vues) | aucun |

- Tous les départements visibles (le cloisonnement ne concerne que le Responsable) ; filtre et colonne
  « Département » ouverts aux rôles de consultation.
- Pièces jointes **ni chargées ni affichées** sans le droit ; liens (candidat, candidature, offre, fiche stage,
  rapport, export) affichés seulement si la page cible est consultable.

## E4 — Interface (`c5ee1e5`)

- Menu des rôles de consultation construit d'après les droits ; menus Secrétaire et Responsable inchangés ;
  menu Administrateur : + « Historique ».
- Tableau de bord générique : compteurs des seuls modules consultables ; rôle désactivé → message.
- Page `suivi:historique_list` : journal filtrable (type d'objet, période), liens vers les seuls objets consultables.
- La tuile « Historique » du tableau de bord Administrateur pointe vers la vraie page (et non « en développement »).

## E5 — Matrice de tests et documentation (ce commit)

- `commun/tests_pages.py` : deux rôles ajoutés à la matrice de **toutes les routes** — « tout coché » (lecture
  partout, 403 sur toute action) et « rien coché » (pages communes seules). Les attentes des 3 rôles de base
  sont inchangées.
- Nouveau test : sur chaque page vue en consultation, **chaque lien et formulaire** est résolu en route Django
  et doit être une route de consultation (vérifié en affichant volontairement le bouton « Terminer » : échec).
- Règles RG-U8 à RG-U12 (`REGLES_GESTION.md`), `CORRESPONDANCE_RG.md`.

Vérifications par mutation pendant le lot : liste blanche du service, restriction de l'écran des permissions,
accès sans le droit requis (5 échecs), liens de l'historique sans contrôle, bouton d'action affiché.

---

## Limites connues

- L'admin Django (`/admin/`) permet toujours à un superutilisateur de modifier les groupes et leurs
  permissions : hors périmètre (aucun compte de démonstration n'est superutilisateur ni `is_staff`).
- Les fiches (besoin, offre, candidature, stage) affichent leur frise d'historique à tout utilisateur qui
  peut les ouvrir ; `view_historique` ne règle que la page Historique.
- Un utilisateur a un seul rôle : un « Responsable qui consulte aussi un autre département » n'est pas possible.

---

## Évolution V2 : rôles personnalisés pouvant agir

Objectif : permettre à l'Administrateur de créer des rôles qui **agissent** (créer, traiter, décider,
constituer, évaluer…), et pas seulement consultent.

**Obstacle** : les vues d'action filtrent sur le **nom** du rôle (`RoleRequisMixin(roles=["Secrétaire"])`,
`_est_responsable`). Un rôle « Responsable adjoint » reçoit 403 partout, même avec les bonnes permissions.

**Options** (détail dans [`lot_e_analyse.md`](lot_e_analyse.md)) :

| Option | Principe | Effort estimé | Limite |
|---|---|---|---|
| A — permissions par action | Une permission Django par action métier (ex. `peut_accorder_candidature`), vérifiée à la place du nom du rôle | Élevé (4–5 j) : ~15–20 permissions, toutes les vues d'action et leurs tests | Le cloisonnement par département doit être recâblé sur l'utilisateur, plus sur le rôle |
| B — famille de rôle | `ProfilRole.famille` ∈ {Administrateur, Secrétaire, Responsable} ; les gardes vérifient la famille | Modéré (2–3 j) | Variantes des 3 rôles seulement ; pas de rôle hybride |

**Ce que le lot E prépare déjà** : `ProfilRole` (support d'un champ `famille` pour l'option B),
`ConsultationMixin` et `a_acces` (modèle d'une garde fondée sur les permissions pour l'option A), la matrice
`tests_pages.py` (garantie de non-régression pour la refonte).

**Points à trancher pour la V2** : rôles multiples par utilisateur (et priorité du département du Responsable) ;
journalisation des changements de rôles et de permissions (E-R5) ; liste des actions déléguables par rôle,
**À VALIDER PAR SEREIN-GE**.
