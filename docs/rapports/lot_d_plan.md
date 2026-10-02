# Lot D — Plan d'implémentation
## Traçabilité et alertes (entretiens, redirections, maîtres de stage)

**Branche** : `lot-d` (depuis `lot-c`)  
**Basé sur** : décisions déjà prises (résumé de session précédente)

---

## Périmètre

| # | Fonctionnalité | Portée |
|---|---|---|
| D1 | Règle 72 h entre planification et entretien | `candidatures/services.py` + `forms.py` |
| D2 | Alerte secrétariat entretien < 48 h | `candidatures/models.py` + commande `alerter_entretiens` |
| D3 | Modèle `TransfertCandidature` | `candidatures/models.py` + `services.py` + `detail.html` |
| D4 | Modèle `AffectationMaitreStage` | `stages/models.py` + `services.py` + `stage_detail.html` |
| D5 | Filtres établissement + partenaire sur CandidatureListView | `candidatures/views.py` + `candidature_list.html` |

---

## D1 — Règle 72 h avant entretien

### `candidatures/forms.py` — `EntretienForm.clean_date_entretien()`
```python
from datetime import timedelta
DELAI_MIN_ENTRETIEN = timedelta(hours=72)

def clean_date_entretien(self):
    dt = self.cleaned_data.get("date_entretien")
    seuil = timezone.now() + DELAI_MIN_ENTRETIEN
    if dt and dt < seuil:
        raise forms.ValidationError(
            "L'entretien doit être planifié au moins 72 h à l'avance."
        )
    return dt
```

### `candidatures/services.py` — `planifier_entretien()`
- Ajouter la même vérification (défense en profondeur) :
```python
from datetime import timedelta
seuil = timezone.now() + timedelta(hours=72)
if date_entretien < seuil:
    raise TransitionInterdite(
        "L'entretien doit être planifié au moins 72 h à l'avance."
    )
```
- Resetter `alerte_entretien_envoyee=False` dans `update_fields`

---

## D2 — Alerte secrétariat entretien < 48 h

### Nouveau champ `Candidature.alerte_entretien_envoyee`
- `BooleanField(default=False, verbose_name="alerte entretien envoyée")`
- Resetté à `False` quand un nouvel entretien est planifié (`planifier_entretien()`)

### Migration `candidatures/0008_...`
```
AddField Candidature.alerte_entretien_envoyee (BooleanField, default=False)
```

### Commande `python manage.py alerter_entretiens`
- Fichier : `candidatures/management/commands/alerter_entretiens.py`
- Logique :
  ```python
  seuil_48h = timezone.now() + timedelta(hours=48)
  candidatures = Candidature.objects.filter(
      statut=StatutCandidature.EN_TRAITEMENT,
      date_entretien__isnull=False,
      date_entretien__lte=seuil_48h,
      date_entretien__gte=timezone.now(),  # pas passé
      candidat_informe=False,
      alerte_entretien_envoyee=False,
  )
  for cand in candidatures:
      notifier(secs, f"Entretien de {cand.reference} dans moins de 48 h ...", lien)
      cand.alerte_entretien_envoyee = True
      cand.save(update_fields=["alerte_entretien_envoyee"])
  ```
- Idempotente : `alerte_entretien_envoyee=False` garantit qu'on n'envoie qu'une seule fois

---

## D3 — Modèle `TransfertCandidature`

### `candidatures/models.py`
```python
class TransfertCandidature(models.Model):
    candidature = models.ForeignKey(
        Candidature, on_delete=models.CASCADE,
        related_name="transferts", verbose_name="candidature"
    )
    departement_source = models.ForeignKey(
        "referentiels.Departement", on_delete=models.PROTECT,
        related_name="+", verbose_name="département source"
    )
    departement_cible = models.ForeignKey(
        "referentiels.Departement", on_delete=models.PROTECT,
        related_name="+", verbose_name="département cible"
    )
    motif = models.TextField(verbose_name="motif")
    realise_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+", verbose_name="réalisé par"
    )
    date_transfert = models.DateTimeField(auto_now_add=True, verbose_name="date de transfert")

    class Meta:
        verbose_name = "Transfert de candidature"
        verbose_name_plural = "Transferts de candidature"
        ordering = ["-date_transfert"]

    def __str__(self):
        return f"Transfert {self.candidature.reference} → {self.departement_cible}"
```

### `candidatures/services.py` — `rediriger()`
Après la modification du département, créer :
```python
TransfertCandidature.objects.create(
    candidature=cand,
    departement_source=ancien_dept,
    departement_cible=nouveau_departement,
    motif=motif,
    realise_par=utilisateur,
)
```

### Migration `candidatures/0009_transfertcandidature.py`
`CreateModel TransfertCandidature`

### Template `candidature_detail.html`
- Section "Historique des redirections" : tableau des `transferts` (date, source, cible, motif, réalisé par)
- Visible pour les 3 rôles

---

## D4 — Modèle `AffectationMaitreStage`

### `stages/models.py`
```python
class AffectationMaitreStage(models.Model):
    stage = models.ForeignKey(
        Stage, on_delete=models.CASCADE,
        related_name="affectations_maitre", verbose_name="stage"
    )
    maitre_stage = models.ForeignKey(
        "referentiels.Personnel", on_delete=models.PROTECT,
        related_name="+", verbose_name="maître de stage"
    )
    affecte_par = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="+", verbose_name="affecté par"
    )
    date_affectation = models.DateTimeField(auto_now_add=True, verbose_name="date d'affectation")

    class Meta:
        verbose_name = "Affectation de maître de stage"
        verbose_name_plural = "Affectations de maître de stage"
        ordering = ["-date_affectation"]

    def __str__(self):
        return f"Maître {self.maitre_stage} → {self.stage}"
```

### `stages/services.py`
- Dans `constituer_stage()` : après `stage = Stage.objects.create(...)`, créer `AffectationMaitreStage`
- Dans `modifier_stage()` : si `maitre_stage` change, créer `AffectationMaitreStage`

### Migration `stages/0004_affectationmaitrestage.py`
`CreateModel AffectationMaitreStage`

### Template `stage_detail.html`
- Section "Historique des maîtres de stage" : tableau des `affectations_maitre` (date, maître, par)
- Visible pour Responsable et Secrétaire

---

## D5 — Filtres établissement + partenaire sur CandidatureListView

### `candidatures/views.py` — `CandidatureListView`
**`get_queryset()` :**
```python
etablissement_id = self.request.GET.get("etablissement")
if etablissement_id:
    qs = qs.filter(candidat__etablissement_id=etablissement_id)

partenaire = self.request.GET.get("partenaire")
if partenaire == "1":
    qs = qs.filter(candidat__etablissement__partenaire=True)
```

**`get_context_data()` :**
```python
from referentiels.models import Etablissement
ctx["etablissements"] = Etablissement.objects.filter(actif=True).order_by("nom")
ctx["etablissement_filtre"] = self.request.GET.get("etablissement", "")
ctx["partenaire_filtre"] = self.request.GET.get("partenaire", "")
```

### `candidature_list.html`
- Ajouter `<select>` pour établissement et checkbox partenaire dans la barre de filtres

---

## Migrations prévues

| Numéro | App | Contenu |
|---|---|---|
| `candidatures/0008` | candidatures | AddField alerte_entretien_envoyee |
| `candidatures/0009` | candidatures | CreateModel TransfertCandidature |
| `stages/0004` | stages | CreateModel AffectationMaitreStage |

---

## Tests prévus

### D1 — 72 h
- `test_entretien_moins_72h_interdit` : `planifier_entretien()` lève `TransitionInterdite` si < 72 h
- `test_entretien_exactement_72h_accepte` : 72 h pile est accepté
- `test_form_entretien_moins_72h_invalide` : `EntretienForm.clean_date_entretien()` rejette < 72 h

### D2 — Alerte 48 h
- `test_alerte_envoyee_entretien_dans_48h` : commande envoie notif et met `alerte_entretien_envoyee=True`
- `test_alerte_pas_envoyee_si_deja_envoyee` : idempotence
- `test_alerte_pas_envoyee_si_candidat_informe` : `candidat_informe=True` → pas d'alerte
- `test_alerte_reset_apres_replanification` : `planifier_entretien()` remet `alerte_entretien_envoyee=False`

### D3 — TransfertCandidature
- `test_rediriger_cree_transfert` : `rediriger()` crée un `TransfertCandidature`
- `test_transfert_contient_bon_departement` : source/cible corrects
- `test_deux_redirections_deux_transferts` : deux appels → deux enregistrements

### D4 — AffectationMaitreStage
- `test_constituer_stage_cree_affectation` : `constituer_stage()` crée `AffectationMaitreStage`
- `test_modifier_stage_meme_maitre_pas_de_nouvelle_affectation` : pas de doublon si maître inchangé
- `test_modifier_stage_nouveau_maitre_cree_affectation` : changement de maître → nouvelle affectation

### D5 — Filtres
- `test_filtre_etablissement` : filtre sur `candidat__etablissement`
- `test_filtre_partenaire` : filtre sur `candidat__etablissement__partenaire=True`

---

## Vérification règles de revue (CLAUDE.md)

| Règle | Statut prévu |
|---|---|
| Logique métier dans `services.py` | OK — transferts/affectations créés dans services |
| `on_delete=PROTECT` vers référentiels | OK — PROTECT vers Departement / Personnel |
| `CASCADE` pour compositions | OK — CASCADE vers Candidature / Stage |
| `on_delete=SET_NULL` pour Utilisateur optionnel | OK — realise_par / affecte_par |
| TextChoices pour énumérations | N/A |
| Langue française | OK |
| Pas de null=True sur CharField/TextField | OK — TextField obligatoire (motif) |
| Tests avant commit | Prévu |
| makemigrations --check | Prévu |
| Commit sur branche lot-d, pas main, pas push | Prévu |
