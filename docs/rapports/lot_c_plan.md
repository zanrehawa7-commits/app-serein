# Lot C — Modèle de texte de l'offre : plan d'implémentation

## Périmètre

1. **ParametreOffre (singleton)** : modèle de texte configurable par l'Administrateur.
2. **Offre.departement** : champ FK ajouté ; rempli par migration depuis le besoin lié.
3. **Offre.texte_publie** : texte généré à la création, éditable par la Secrétaire.
4. **Vue admin** `ParametreOffreView` : GET/POST, Administrateur uniquement.
5. Mise à jour du template `offre_detail.html` : utilise `offre.texte_publie`.
6. Tests unitaires pour chaque règle.

---

## Modèles (`offres/models.py`)

### ParametreOffre (singleton)
```
contact         TextField(blank=True)
texte_modele    TextField(blank=True)
```
- `save()` force `pk=1` (singleton).
- `delete()` est inhibé (ne peut pas être supprimé).
- `get_instance()` : `get_or_create(pk=1, defaults=...)`.

### Variables supportées dans `texte_modele`
| Variable | Source |
|---|---|
| `{contact}` | ParametreOffre.contact |
| `{type_stage}` | offre.type_stage.libelle |
| `{departement}` | offre.departement.nom (vide si null) |
| `{duree_min}` | offre.type_stage.duree_min_mois |
| `{duree_max}` | offre.type_stage.duree_max_mois |
| `{nombre_places}` | offre.nombre_places |
| `{date_debut}` | offre.date_debut (dd/mm/YYYY) |
| `{date_fin}` | offre.date_fin (dd/mm/YYYY) |

### Offre — champs ajoutés
```
departement   ForeignKey(Departement, null=True, blank=True, PROTECT)
texte_publie  TextField(blank=True)
```

---

## Migration `offres/0002_parametre_offre_departement_texte.py`
1. `CreateModel ParametreOffre`
2. `AddField Offre.departement` (null=True)
3. `RunPython` : pour chaque offre avec un besoin, `offre.departement = offre.besoin.departement`
4. `AddField Offre.texte_publie` (blank=True)

**Pas d'AlterField NOT NULL** : le champ reste nullable (offres standalone sans besoin historiques).

---

## Service `offres/services.py`

```python
def generer_texte_offre(offre, parametre) -> str:
    # str.replace pour chaque variable
    
def creer_offre(..., departement=None):
    # Si departement is None et besoin fourni → departement = besoin.departement
    # Crée l'offre avec departement
    # Génère texte_publie et sauvegarde
```

---

## Formulaires

### `OffreForm` (mise à jour)
- Ajout de `departement` (ModelChoiceField, Departement actifs, requis).
- Ajout de `texte_publie` (Textarea, non requis).

### `ParametreOffreForm` (nouveau)
- Champs : `contact`, `texte_modele`.
- Help text liste les variables disponibles.

---

## Vues

| Vue | Rôle | Changements |
|---|---|---|
| `OffreCreateView` | Secrétaire | Passe `departement` au service |
| `OffreCreateFromBesoinView` | Secrétaire | Pre-fill + passe `departement=besoin.departement` |
| `OffreDetailView` | 3 rôles | Supprime texte_publication hardcodé ; utilise `offre.texte_publie` |
| `OffreListView` | 3 rôles | Filtre Responsable par `departement` direct |
| `ParametreOffreView` (nouveau) | Administrateur | GET/POST singleton |

---

## URLs

`offres/parametres/` → `ParametreOffreView`, name=`parametre_offre`

---

## Templates

- `offre_detail.html` : remplace le bloc `texte_publication` hardcodé par `offre.texte_publie`.
- `offres/parametre_offre_form.html` (nouveau) : formulaire avec aide sur les variables.
- `base.html` : lien « Modèle d'offre » dans la nav admin (section Paramètres).

---

## Init données

- `ParametreOffre` n'est pas dans `GROUPES_PERMISSIONS` explicitement.
  - Admin : couvert par `"offres": _CRUD` → a déjà `add/change/view/delete parametre_offre`.
  - Secrétaire/Responsable : n'ont que des permissions explicites → pas de parametre_offre. ✓
- `ParametreOffre.get_instance()` crée le singleton avec texte par défaut au premier accès.

---

## Tests (`offres/tests.py`)

- `ParametreOffreTests` : singleton (deux `save()` n'ont qu'un enregistrement), `delete()` ignoré.
- `GenererTexteOffreTests` : toutes les variables remplacées ; variables manquantes → chaîne vide.
- `OffresCreerDepartementTests` : departement depuis besoin ; departement explicite ; null si standalone sans forme.

---

## Vérification Règles de revue

- [x] Pas de réécriture de migration existante.
- [x] Avant UniqueConstraint/CHECK : aucune contrainte d'unicité ajoutée ici.
- [x] `makemigrations --check` sera lancé avant commit.
- [x] texte_modele par défaut marqué « À VALIDER PAR SEREIN-GE » dans le rapport.
- [x] Pas de duplication : `departement` sur Offre n'est pas redondant (l'offre sans besoin n'a pas de département autrement accessible).
- [x] Logique métier dans services.py (`generer_texte_offre`, `creer_offre`).
- [x] Sécurité : `ParametreOffreView` protégée par `roles=["Administrateur"]` côté serveur.
- [x] Pas de `piece.fichier.url` ; cette section ne touche pas les fichiers.
