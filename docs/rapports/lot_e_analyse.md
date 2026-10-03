# Lot E — Analyse : Rôles personnalisés
## (Analyse seulement — aucun code implémenté dans ce lot)

**Date** : 2026-10-02  
**Branche** : `lot-d` (analyse rédigée en complément du lot D)  
**Statut** : Analyse seulement — aucun code n'a été ajouté.

---

## Contexte et état actuel

L'application repose sur **trois rôles fixes** définis comme Django Groups : `Administrateur`,
`Secrétaire`, `Responsable`. Ces rôles sont créés par `init_donnees.py` au démarrage.

Le contrôle d'accès s'appuie sur deux mécanismes distincts :

| Mécanisme | Où | Comment |
|---|---|---|
| Vérification du **nom du groupe** | `comptes/permissions.py` — `RoleRequisMixin(roles=[...])` | Le nom de groupe doit correspondre exactement à la liste passée à chaque vue |
| Vérification des **permissions Django** | `RolePermMixin` + `{% if perms.app.action_model %}` | Django CodePermissions standard, éditable via F02 |

Les vérifications de nom de rôle sont disséminées dans tout le code :

```python
# vues candidatures
class CandidatRechercheView(RoleRequisMixin):
    roles = ["Secrétaire"]

class _DecisionView(RoleRequisMixin):
    roles = ["Responsable"]

# vues offres
class BesoinCreateView(RoleRequisMixin):
    roles = ["Responsable"]

# utils internes
def _est_responsable(user):
    return user.groups.filter(name="Responsable").exists()
```

Ce couplage fort au nom du groupe rend toute création de rôle personnalisé inefficace :
un groupe "Responsable Adjoint" ne passerait aucune de ces gardes.

---

## E-R1 — Création / suppression de groupes depuis l'UI

### Ce que ça couvre
Permettre à l'Administrateur de créer un nouveau groupe (ex. "Responsable RH"),
de le renommer et de le supprimer, sans toucher au code.

### Analyse technique
- Les Django Groups sont déjà le modèle sous-jacent.
- Il suffit d'ajouter à `comptes/views.py` une `GroupCreateView`, `GroupRenameView` et une
  vue de suppression, protégées par `RolePermMixin`.
- Contrainte : les **3 groupes système** (`Administrateur`, `Secrétaire`, `Responsable`) doivent
  être immuables — les vues doivent les refuser en GET et POST.
- `init_donnees.py` reste la seule source de vérité pour les groupes système.
- F02 (`PermissionsRoleView`) doit lister tous les groupes, pas uniquement les 3 hardcodés.

### Effort estimé
Faible — 1 jour développeur.

### Questions ouvertes
**DÉCISION SEREIN-GE REQUISE :**
1. Quel est le cas d'usage concret ? (ex. "Responsable par intérim", "Directeur Général — lecture seule", "Auditeur" ?)
2. Y a-t-il un nombre maximal de rôles à prévoir ?

---

## E-R2 — Attribution de permissions aux rôles personnalisés

### Ce que ça couvre
Étendre F02 pour que les rôles personnalisés apparaissent aux côtés des 3 rôles système et
puissent recevoir des permissions Django standard (add/change/view/delete sur chaque modèle).

### Analyse technique
- `PermissionsRoleView` est déjà générique (prend un `Group` en paramètre d'URL).
- Seul le `get_object_or_404(Group, name=nom)` et la liste des onglets dans le template
  limitent aux 3 groupes hardcodés.
- Fix minimal : récupérer tous les groupes actifs plutôt qu'une liste fixe, laisser la vue
  gérer n'importe quel `Group`.
- Les "cases grises" de l'Administrateur (toujours cochées, non modifiables) ne s'appliquent
  qu'aux permissions `comptes` — cette logique reste valide pour les groupes personnalisés.

### Effort estimé
Faible — ½ jour développeur.

### Limite
Cela ne résout **pas** le problème des vérifications par nom de rôle (voir E-R3).
Un rôle personnalisé avec toutes les permissions d'un Secrétaire obtiendrait des permissions
Django, mais continuerait à recevoir un 403 sur les vues `roles=["Secrétaire"]`.

---

## E-R3 — Remplacer les vérifications par nom de rôle

### Pourquoi c'est le vrai défi

Même avec E-R1 et E-R2, un rôle personnalisé bute sur les gardes codées en dur.
Deux vues illustrent le problème :

**Cas 1 — Secrétaire uniquement**
`CandidatRechercheView(roles=["Secrétaire"])` — aucune permission Django n'est associée
à "rechercher un candidat". Le contrôle est purement par nom de groupe.

**Cas 2 — Responsable avec scoping département**
`_DecisionView(roles=["Responsable"])` + `_est_responsable(user)` dans
`CandidatureListView.get_queryset()` — le nom "Responsable" conditionne non seulement
l'accès, mais aussi LE FILTRAGE des données par département. Un rôle "Responsable Adjoint"
aurait besoin du même filtrage, ce qui est impossible sans refactoring.

### Options architecturales

**Option A — Permission synthétique par action**
Créer des permissions Django personnalisées (ex. `candidatures.peut_recevoir_candidature`,
`offres.peut_traiter_besoin`) et remplacer chaque `roles=[...]` par un `permission_required`.
- ✅ Extensible et standard Django
- ✅ F02 peut exposer ces nouvelles permissions
- ❌ Environ 15-20 permissions à définir dans `models.py` ou `AppConfig`
- ❌ Le scoping département pour `Responsable` doit être recâblé sur une propriété
  de l'utilisateur (ex. `user.personnel.departement`) et non sur le groupe
- Effort : **Élevé — 4-5 jours** pour recâbler toutes les vues + tests

**Option B — Champ "famille de rôle" sur le groupe**
Ajouter un modèle `MetaRole` lié à `Group` avec `famille in ("Administrateur", "Secrétaire", "Responsable", "Personnalisé")`.
`RoleRequisMixin` vérifierait `user.groupe.metarole.famille` au lieu du nom brut.
- ✅ Migration légère, retro-compatible
- ✅ Un rôle "Responsable Adjoint" ayant `famille="Responsable"` passerait toutes les gardes
- ❌ Nécessite un modèle supplémentaire + migration + UI de choix dans `GroupCreateView`
- ❌ N'aide pas si l'objectif est un rôle hybride (ex. à la fois Secrétaire ET Responsable)
- Effort : **Modéré — 2-3 jours**

**Recommandation** : Option B si le besoin est "des variantes des 3 rôles existants" ;
Option A si le besoin est "des rôles entièrement nouveaux avec permissions fines".

---

## E-R4 — Rôles multiples par utilisateur

### Ce que ça couvre
Un utilisateur pourrait appartenir à plusieurs groupes (ex. Secrétaire et Responsable Adjoint).

### Analyse technique
`Utilisateur.role` renvoie actuellement le premier groupe de l'utilisateur :
```python
@property
def role(self):
    return self.groups.values_list("name", flat=True).first()
```

Avec plusieurs groupes :
- `RoleRequisMixin` doit passer si **l'un** des groupes est dans `self.roles`
- `_est_responsable(user)` fonctionne déjà (filtre par nom de groupe, pas par role unique)
- L'UI de gestion des utilisateurs (formulaire `ChoiceField` → rôle unique) doit devenir un `MultipleChoiceField`
- Le scoping département devient ambigu si un utilisateur est à la fois Secrétaire et Responsable

### Effort estimé
Modéré — 2 jours. Mais **bloquant sur E-R3** : les gardes à nom unique doivent d'abord être remplacées.

### Questions ouvertes
**DÉCISION SEREIN-GE REQUISE :**
- Un utilisateur peut-il avoir plusieurs rôles simultanément ? Quel est le cas d'usage ?
- Si oui : le département du Responsable prime-t-il sur les autres rôles ?

---

## E-R5 — Journalisation des changements de rôles et permissions

### Ce que ça couvre
Tracer qui a modifié quelles permissions sur quel groupe, et quand un utilisateur a changé de rôle.

### Analyse technique
- Étendre `enregistrer_historique()` pour accepter des objets `Group` (le ContentType
  `auth.group` est déjà disponible via Django).
- Dans `PermissionsRoleView.post()` : appeler `enregistrer_historique` avec les permissions
  avant/après.
- Dans `UtilisateurModifierView.post()` : déjà journalisé via l'historique utilisateur.
- Affichage : colonne "Audit permissions" dans F02 ou page dédiée.

### Effort estimé
Faible — ½ jour.

---

## Priorité recommandée

| Sous-feature | Effort | Valeur | Dépend de | Recommandation |
|---|---|---|---|---|
| E-R1 — CRUD groupes UI | Faible | Moyen | — | Priorité 2 |
| E-R2 — Permissions sur groupes perso | Faible | Moyen | E-R1 | Priorité 2 |
| E-R3 (Option B — famille) | Modéré | Élevé | E-R1 | **Priorité 1** |
| E-R3 (Option A — permissions fines) | Élevé | Élevé | E-R1 | Priorité 3 |
| E-R4 — Rôles multiples | Modéré | Faible/Moyen | E-R3 | Priorité 4 |
| E-R5 — Audit trail | Faible | Moyen | — | Priorité 2 |

---

## Conclusion

La fonctionnalité "rôles personnalisés" se décline en plusieurs niveaux de profondeur.
Les sous-features E-R1, E-R2 et E-R5 sont indépendantes et implémentables rapidement.
Le véritable enjeu est **E-R3** : tant que les gardes d'accès reposent sur des noms de
groupe hardcodés, un rôle personnalisé sera bloqué même avec les bonnes permissions Django.

**La décision architecturale (Option A vs B dans E-R3) doit être prise par Serein-GE**
avant tout développement, car elle conditionne l'ensemble de la refonte.

Si le seul besoin à court terme est "créer un Responsable de département sans personnel rattaché",
une solution alternative moins coûteuse existe : permettre l'affectation d'un utilisateur
Responsable sans `user.personnel` en ajoutant un FK `Utilisateur.departement` de secours.
