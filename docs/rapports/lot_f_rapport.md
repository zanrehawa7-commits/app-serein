# Lot F — Rapport d'implémentation
## Module Stages : dates dans la disponibilité, reprise après interruption, dossier du candidat

**Date** : 2026-10-03
**Origine** : demandes du directeur de mémoire
**Branche** : `lot-f` (3 commits, un par demande)
**Tests** : 329 / 329 OK (0 échec) — 297 avant le lot, +32
**Migrations** : `stages/0005_periode_interruption` (modèle), `stages/0006_periodes_stages_deja_interrompus` (données) — additives

---

## Décisions validées avant développement

| # | Question | Décision |
|---|---|---|
| 1 | Stage en cours dont le début (antérieur à la règle) sort de la disponibilité | Début vérifié seulement s'il est modifiable (stage à venir jamais démarré) ; fin toujours vérifiée |
| 2 | Fiche d'un stage au vivier vue par le Responsable d'un autre département | Toute la fiche limitée aux colonnes du vivier (identité, téléphone, email, niveau, filière, établissement, type de stage, département, période, note, rapport) |
| 3 | Nouvelle fin prévue déjà passée lors d'une reprise | Acceptée (régularisation) avec message : « Ce stage sera clôturé automatiquement à la prochaine exécution de la mise à jour quotidienne. » |

---

## F1 — Dates du stage dans la disponibilité du candidat (RG-S11) — commit `a39185b`

- Règle **bloquante**, dans le service (`erreurs_disponibilite`, vérifiée avant toute écriture) **et** dans le
  formulaire (erreur sur le champ concerné). Message : *« Le stage doit se dérouler pendant la disponibilité du
  candidat : du JJ/MM/AAAA au JJ/MM/AAAA. »*
- Constitution : début ≥ début de disponibilité, fin ≤ fin de disponibilité. Modification : fin toujours,
  début seulement s'il est modifiable (`debut_modifiable`).
- Formulaires : panneau « Disponibilité du candidat » et calendrier borné (`min` / `max`).
- **Constat** : l'« avertissement non bloquant » existant comparait les dates à une disponibilité du **maître de
  stage** qui n'existe pas (`_get_membres_dispos` renvoyait `{}`) : il ne s'affichait jamais. Code mort supprimé.
- Stages existants non modifiés : la règle s'applique à leur prochaine modification.

## F2 — Reprise d'un stage interrompu (RG-S12, RG-S13) — commit `d177ad6`

- Modèle `PeriodeInterruption` : créé à chaque interruption, complété à la reprise ; toutes les périodes sont
  conservées. Contraintes en base : reprise ≥ interruption, une seule période ouverte par stage.
- Migration 0006 : les stages déjà interrompus reçoivent leur période ouverte (sinon ils ne pourraient pas être repris).
- `reprendre_stage` (Responsable du département) : INTERROMPU → EN_COURS (reprise passée ou du jour) ou A_VENIR
  (reprise future) ; reprise ≥ interruption, fin > reprise et ≤ fin de disponibilité, motif obligatoire ;
  `date_fin_reelle` vidée ; historique + notification aux Secrétaires.
- **Cohérence du cycle** : `Stage.date_demarrage_effective()` (dernière reprise, sinon début).
  - La commande quotidienne démarre un stage repris **à sa date de reprise** : sans cela, elle l'aurait redémarré
    dès la nuit suivante (son début d'origine étant passé).
  - Terminer / interrompre exigent une date ≥ reprise ; la date de début n'est plus modifiable après une reprise.
  - Un stage repris puis terminé est évaluable (statut TERMINE) ; la clôture automatique et le rappel J+7 sont inchangés.
- **Correction au passage** : un stage **à venir** ne pouvait pas être interrompu par l'écran (le formulaire
  exigeait date ≥ début ET ≤ aujourd'hui). La borne basse ne s'applique plus qu'aux stages en cours.
- Fiche stage : bouton « Reprendre le stage », tableau des périodes d'interruption.

## F3 — Dossier du candidat sur la fiche stage (RG-E8) — ce commit

| Qui | Ce qui est affiché |
|---|---|
| Secrétaire, Administrateur, Responsable du département | Bloc « Dossier du candidat » complet : identité, contacts, établissement, niveau/filière, type de demande, offre, disponibilité, durée souhaitée, pièces jointes (Voir / Télécharger), lien vers la candidature |
| Responsable d'un autre département (stage au vivier) | Colonnes du vivier uniquement, sur un template dédié (`stage_detail_vivier.html`) |

**Contrôle côté serveur** : pour le Responsable d'un autre département, la vue retourne avant de charger quoi
que ce soit d'autre — pièces jointes, historique, maîtres de stage et périodes ne sont ni requêtés ni transmis
au template. Le téléchargement direct d'une pièce reste refusé (403).

---

## Tests ajoutés

| Classe | Couvre |
|---|---|
| `DisponibiliteRGS11Tests` (8) | Bornes incluses, début / fin hors disponibilité refusés (service, formulaire, vue), stage existant modifiable |
| `RepriseStageTests` (19) | Reprise EN_COURS / A_VENIR, 5 refus (dates, motif, statut), périodes conservées après deux interruptions, commande quotidienne, repris → terminé → évalué, vue et messages |
| `MigrationPeriodesStagesInterrompusTests` (1) | Migration 0006 idempotente |
| `DossierCandidatRGE8Tests` (4) | Contenu par rôle, pièces et contacts absents du contexte pour un autre département, pièce en 403 |
| `commun/tests_pages.py` | Nouvelle route dans la matrice, cloisonnement et Responsable sans département |

Vérification par mutation : en réintroduisant chaque défaut (démarrage sur le début d'origine, reprise avant
interruption, fiche complète pour un autre département), les tests correspondants échouent.

## Points d'attention

- Après ces migrations, relancer les tests **une fois sans `--keepdb`** : avec `--parallel`, les copies de la base
  de test sont réutilisées telles quelles et n'ont pas la nouvelle table.
- La page Vivier et l'export CSV affichent aussi le **maître de stage** ; la fiche limitée (RG-E8) ne l'affiche
  pas, conformément à la décision. La page Vivier n'affiche pas l'email (le CSV oui).
