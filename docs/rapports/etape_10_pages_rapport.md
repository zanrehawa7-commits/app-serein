# Étape 10 — Rapport : test de toutes les pages par rôle

**Date** : 2026-10-03  
**Branche** : `etape-10-pages`  
**Tests** : 278 / 278 OK (0 échec) — dont 10 nouveaux  
**Migrations** : `makemigrations --check` → "No changes detected" (aucune migration)

---

## Pourquoi

Le 2026-10-03, à la première installation sur un nouveau poste, deux bugs sont apparus en
quelques minutes d'utilisation alors que les 265 tests passaient :

- `init_donnees` plantait sur une base vide (types de stage sans durées) ;
- la page `/referentiels/personnels/` levait une `TemplateSyntaxError` (`{% load commun_tags %}`).

Les tests existants vérifiaient la logique métier et les refus d'accès (403), mais presque jamais
qu'une page **s'affiche** pour un rôle autorisé. Cette étape ferme ce trou.

---

## Ce qui a été ajouté

Un seul fichier : **`backend/commun/tests_pages.py`** (aucun code applicatif modifié).

### Jeu de données réaliste (`_DonneesPagesMixin`)

Créé une fois par classe (`setUpTestData`) :

- groupes et permissions réels via `call_command("init_donnees")` ;
- 2 départements (Informatique = A, Comptabilité = B), chacun avec son responsable et un maître de stage ;
- 3 utilisateurs : Administrateur, Secrétaire, Responsable (du département A) — **groupes réels, pas de superuser** ;
- besoins, offres ouvertes, publication ;
- candidatures RECUE (avec CV PDF, transfert et historique), EN_TRAITEMENT (suite à offre, entretien planifié), ACCORDEE ;
- stage EN_COURS, stage TERMINE évalué (note 15, vivier, rapport PDF) ;
- département B : candidature avec pièce jointe, stage en cours, stage terminé hors vivier avec rapport ;
- une notification par utilisateur.

Les PDF sont écrits dans un dossier temporaire supprimé en fin de classe (voir constat n° 6).

### Les tests

| Test | Vérifie |
|---|---|
| `test_toutes_les_routes_sont_couvertes` | Toute route nommée du projet (hors admin Django et API) figure dans `MATRICE`. **Une nouvelle page non déclarée fait échouer la suite.** |
| `test_aucune_route_inconnue_dans_la_matrice` | `MATRICE` ne contient pas de route supprimée. |
| `test_chaque_page_avec_chaque_role` | 88 routes × 3 rôles : code attendu (200 / 302 / 405) si autorisé, 403 sinon. Toute exception est rapportée comme « 500 ». |
| `test_get_ne_modifie_aucune_donnee` | Un GET sur une route d'action (suppression, activation, transition…) ne modifie rien. |
| `test_anonyme_redirige_vers_connexion` | Visiteur non connecté : redirection vers `/login/` partout sauf la page de connexion. |
| `test_routes_autre_departement_refusees` | Le Responsable de A reçoit 403/404 sur 11 routes visant des objets de B. |
| `test_listes_filtrees_sur_le_departement` | Les listes candidatures / stages / offres du Responsable ne contiennent rien de B. |
| `test_piece_jointe_servie_en_pdf`, `test_rapport_servi_en_piece_jointe`, `test_export_vivier_csv` | Les téléchargements renvoient le bon contenu. |

### Vérification que le test détecte vraiment les erreurs

Deux bugs ont été introduits volontairement puis retirés :

- `{% load commun_tags %}` ajouté dans `stages/stage_list.html` → détecté : 500 pour les 3 rôles ;
- Secrétaire ajoutée aux rôles de `StagesAEvaluerListView` → détecté : « attendu 403, obtenu 200 ».

---

## Résultat

**Aucune page ne plante**, pour aucun des 3 rôles (88 routes).
Tous les refus d'accès par rôle sont conformes au code.

---

## Constats — à trancher

Aucun de ces points n'a été modifié : ils demandent une décision.

### 1. Droits Django de l'Administrateur ≠ CLAUDE.md

CLAUDE.md §4 : Administrateur **en lecture seule** sur `offres`, `candidatures`, `stages`, `suivi`.
`init_donnees.GROUPES_PERMISSIONS` lui donne **add / change / delete / view** sur `offres`, `stages` et `suivi`.

Impact réel limité : les vues de ces apps filtrent par **rôle** (`RoleRequisMixin`), donc l'Administrateur
est bien refusé (403) sur toutes les pages de création/modification — le test le confirme. Les permissions
ne jouent que sur les `{% if perms... %}` des templates (boutons affichés) et sur l'admin Django.

**Décision :** réduire les permissions à `view` (code) ou corriger CLAUDE.md (doc) ?

### 2. Un Responsable peut ouvrir la fiche d'un stage d'un autre département

`StageDetailView` ne lève pas `PermissionDenied` : elle masque seulement les boutons d'action.
À l'inverse, `CandidatureDetailView` renvoie 403 pour une candidature d'un autre département, et la
liste des stages du Responsable est bien filtrée sur son département.

**Décision :** aligner sur la fiche candidature (403) ? *Recommandé : oui, par cohérence.*

### 3. Rapport de stage d'un autre département téléchargeable s'il est au vivier

`RapportTelechargerView` autorise le Responsable si le stage est au vivier, quel que soit le département.
Cohérent avec un vivier partagé entre départements, mais non documenté dans `REGLES_GESTION.md`.

**Décision :** confirmer (et documenter) ou restreindre au département ?

### 4. « Vue Référentiels » pour Secrétaire et Responsable

CLAUDE.md §4 indique « Vue Référentiels » pour ces deux rôles, et leurs groupes ont bien les permissions
`view_*`. Mais toutes les pages `/referentiels/` sont réservées à l'Administrateur (`RolePermMixin`) et
des tests existants exigent le 403. Les permissions servent en pratique aux listes déroulantes des formulaires.

**Décision :** préciser la doc (« pas d'accès aux écrans Référentiels ») ou ouvrir les listes en lecture ?

### 5. `notification_lire` agit sur un GET

Ouvrir `/notifications/<pk>/lire/` marque la notification comme lue, alors que CLAUDE.md §6 exige
« Actions en POST uniquement ». Impact faible (seulement ses propres notifications) et pratique pour
un lien cliqué dans le menu.

**Décision :** accepter comme exception documentée, ou passer le menu en formulaires POST ?

---

## Constat — bug d'environnement de test (correction proposée)

### 6. Les tests existants écrivent dans le vrai dossier `fichiers_prives/`

`PieceJointe.fichier` et `Stage.rapport` utilisent un stockage **callable** : Django l'instancie au
chargement des modèles avec un `location` explicite. Le `@override_settings(FICHIERS_PRIVES_ROOT=...)`
des tests de `candidatures` n'a donc aucun effet sur l'écriture.

Mesure : **chaque lancement de la suite complète ajoute 50 PDF** dans `backend/fichiers_prives/candidatures/`
(400 fichiers accumulés le 2026-10-03). Le dossier est ignoré par git, mais en production ce serait le
dossier des vraies pièces des candidats.

Point lié : `PieceJointeTelechargerView` reconstruit le chemin depuis `settings.FICHIERS_PRIVES_ROOT`,
alors que `RapportTelechargerView` passe par le stockage (`stage.rapport.path`). Les deux devraient
passer par le stockage.

**Correction proposée (petit lot séparé) :** dans `config/settings_test.py`, pointer
`FICHIERS_PRIVES_ROOT` vers un dossier temporaire **et** faire lire le réglage par le stockage à chaque
accès (sous-classe de `FileSystemStorage` sans `location` figé), puis utiliser `piece.fichier.path`
dans la vue. Nettoyage des 450 fichiers de test existants à faire à la main.
