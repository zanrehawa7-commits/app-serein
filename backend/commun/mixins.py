from django.db.models import Q


class ListeMixin:
    """
    Mixin réutilisable pour toutes les vues de liste.
    Gère : recherche textuelle (?q=), filtre actif/inactif (?actif=1|0),
    tri par colonne (?tri=champ|-champ) et pagination (20/page).

    Attributs à définir dans la subclass :
    - `champs_recherche` : liste de noms de champs pour la recherche fulltext.
    - `champ_actif` : nom du champ booléen de statut (défaut "actif", utiliser
      "is_active" pour Utilisateur).
    """
    paginate_by = 20
    champs_recherche = []
    champ_actif = "actif"

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q", "").strip()
        actif = self.request.GET.get("actif", "")
        tri = self.request.GET.get("tri", "")

        if q and self.champs_recherche:
            filtre = Q()
            for champ in self.champs_recherche:
                filtre |= Q(**{f"{champ}__icontains": q})
            qs = qs.filter(filtre)

        if actif in ("1", "0"):
            qs = qs.filter(**{self.champ_actif: (actif == "1")})

        if tri:
            try:
                qs = qs.order_by(tri)
            except Exception:
                pass

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["params_paginateur"] = params.urlencode()
        ctx["q"] = self.request.GET.get("q", "")
        ctx["actif_filtre"] = self.request.GET.get("actif", "")
        ctx["tri_actuel"] = self.request.GET.get("tri", "")
        return ctx
