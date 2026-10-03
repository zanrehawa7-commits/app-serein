# Lot D — Rapport d'implémentation
## Traçabilité et alertes (entretiens, redirections, maîtres de stage)

**Date** : 2026-10-02  
**Branche** : `lot-d`  
**Commit** : 6705b84  
**Tests** : 265 / 265 OK (0 échec)  
**Migrations** : `makemigrations --check` → "No changes detected"

---

## Ce qui a été implémenté

### D1 — Règle 72 h minimum avant entretien

**`candidatures/forms.py` — `EntretienForm.clean_date_entretien()`**
- Ancienne règle : date > maintenant
- Nouvelle règle : date >= maintenant + 72 h
- Message : `"L'entretien doit être planifié au moins 72 h à l'avance."`
- Help text mis à jour en conséquence

**`candidatures/services.py` — `planifier_entretien()`**
- Même vérification côté service (défense en profondeur)
- Lève `TransitionInterdite` si la date est dans moins de 72 h

**Impact sur les tests existants :** `test_planifier_entretien_ok` utilisait `+5 jours` (120 h) → toujours valide. Les tests `test_planifier_date_passee_form_invalide` valident toujours car date passée < date actuelle < seuil 72 h.

---

### D2 — Alerte secrétariat entretien < 48 h

**Nouveau champ `Candidature.alerte_entretien_envoyee`**
- `BooleanField(default=False)`
- Resetté à `False` par `planifier_entretien()` à chaque replanification

**Commande `python manage.py alerter_entretiens`**
- Fichier : `candidatures/management/commands/alerter_entretiens.py`
- Filtre : `statut=EN_TRAITEMENT`, `date_entretien` dans 0–48 h, `candidat_informe=False`, `alerte_entretien_envoyee=False`
- Pour chaque candidature : notifie toutes les Secrétaires actives, puis met `alerte_entretien_envoyee=True`
- Idempotente : relancer deux fois ne renvoie pas d'alerte en double
- À planifier via cron (ex. toutes les 2 h)

**Migration** : `candidatures/0008_lot_d.py` — AddField + CreateModel

---

### D3 — Modèle `TransfertCandidature`

**`candidatures/models.py`**
- Champs : `candidature` (CASCADE), `departement_source` (PROTECT), `departement_cible` (PROTECT), `motif` (TextField), `realise_par` (SET_NULL, null), `date_transfert` (auto_now_add)
- `Meta.ordering = ["-date_transfert"]`

**`candidatures/services.py` — `rediriger()`**
- Après modification du département de la candidature, crée automatiquement un `TransfertCandidature`
- Capture l'ancien département avant la modification

**`candidatures/views.py` — `CandidatureDetailView`**
- Passe `transferts` au template (select_related source/cible/realise_par)

**`templates/candidatures/candidature_detail.html`**
- Nouvelle section "Historique des redirections" : tableau avec date, source, cible, motif, réalisé par
- Visible pour les 3 rôles, affichée uniquement si `transferts` existe

---

### D4 — Modèle `AffectationMaitreStage`

**`stages/models.py`**
- Champs : `stage` (CASCADE), `maitre_stage` (PROTECT), `affecte_par` (SET_NULL, null), `date_affectation` (auto_now_add)
- `Meta.ordering = ["-date_affectation"]`

**`stages/services.py`**
- `constituer_stage()` : crée une `AffectationMaitreStage` après la création du stage
- `modifier_stage()` : crée une `AffectationMaitreStage` uniquement si le maître a changé (pas de doublon si seule la date de fin change)

**`stages/views.py` — `StageDetailView`**
- Passe `affectations_maitre` au template (select_related maitre_stage/affecte_par)

**`templates/stages/stage_detail.html`**
- Nouvelle section "Historique des maîtres de stage" : tableau avec date, maître, affecté par
- Visible pour Responsable et Secrétaire uniquement (pas Administrateur)

**Migration** : `stages/0004_lot_d.py` — CreateModel AffectationMaitreStage

---

### D5 — Filtres établissement + partenaire sur CandidatureListView

**`candidatures/views.py`**
- `get_queryset()` : deux nouveaux filtres `candidat__etablissement_id` et `candidat__etablissement__partenaire=True`
- `get_context_data()` : ajoute `etablissements` (actifs, triés par nom), `etablissement_filtre`, `partenaire_filtre`

**`templates/candidatures/candidature_list.html`**
- Nouveau `<select>` "Tous établissements" dans la barre de filtres
- Nouvelle case à cocher "Partenaires" à côté
- Compatibles avec le bouton "Réinitialiser" existant

---

## Migrations

| Fichier | Contenu |
|---|---|
| `candidatures/0008_lot_d.py` | AddField alerte_entretien_envoyee + CreateModel TransfertCandidature |
| `stages/0004_lot_d.py` | CreateModel AffectationMaitreStage |

---

## Tests ajoutés (14 nouveaux)

| Classe | Tests |
|---|---|
| `Entretien72hTests` | 4 tests (service + form) |
| `AlerterEntretiensCommandTests` | 4 tests (alerte, idempotence, filtre informé, entretien lointain) |
| `TransfertCandidatureTests` | 3 tests (création, source/cible corrects, deux redirections) |
| `AffectationMaitreStageTests` | 3 tests (création, pas de doublon, changement crée affectation) |

---

## Questions ouvertes pour Serein-GE

1. **Cron `alerter_entretiens`** : quelle fréquence ? Recommandation : toutes les 2 h suffit pour une alerte < 48 h.
2. **Affichage `AffectationMaitreStage` aux Administrateurs** : pour l'instant masqué (informations opérationnelles). Peut être rendu visible si besoin d'audit.
3. **Filtre partenaire sur la liste candidatures** : doit-il être réservé à certains rôles (ex. Administrateur uniquement) ou accessible à tous ? Pour l'instant visible pour Secrétaire et Responsable.

---

## Vérification règles de revue (CLAUDE.md)

| Règle | Statut |
|---|---|
| Logique métier dans `services.py` | OK — TransfertCandidature/AffectationMaitreStage créés dans services |
| `on_delete=PROTECT` vers référentiels | OK — PROTECT vers Departement / Personnel |
| `CASCADE` pour compositions | OK — CASCADE vers Candidature / Stage |
| `SET_NULL` pour Utilisateur optionnel | OK — realise_par / affecte_par |
| Pas de null=True sur CharField/TextField | OK |
| Langue française | OK |
| Tests avant commit | OK — 265 tests, 0 échec |
| makemigrations --check | OK — "No changes detected" |
| Commit sur branche lot-d, pas main, pas push | OK |
