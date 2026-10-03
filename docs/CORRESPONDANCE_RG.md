# Correspondance des règles de gestion — cahier des charges → code

> Pour citer les règles dans le rapport de stage.
> **Cahier des charges** : règles numérotées **RG01 à RG35**.
> **Code** : numérotation de [`REGLES_GESTION.md`](REGLES_GESTION.md) (RG-U*, RG-P*, RG-R*, RG-E*, RG-S*, RG-N*…),
> qui reprend tel quel le numéro du cahier quand le code le cite (RG07, RG09…).
>
> Le texte du cahier des charges **n'est pas dans le dépôt**. Seules les correspondances vérifiables sont remplies ;
> les autres sont marquées **À COMPLÉTER** — ne pas les deviner.
> Dernière mise à jour : 2026-10-03.

## Niveau de certitude

| Niveau | Signification |
|---|---|
| **Certain** | Le code cite explicitement le numéro du cahier, et la règle y est décrite dans `REGLES_GESTION.md`. |
| **Indiqué** | Correspondance donnée par l'auteur du projet, non citée dans le code. |
| **À confirmer** | Le code cite le numéro, mais le rattachement à une règle de `REGLES_GESTION.md` est une lecture du code. |

## Tableau RG01 → RG35

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

## Règles du code sans numéro du cahier connu

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
