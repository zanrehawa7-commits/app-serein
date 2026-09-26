from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views import View
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from commun.mixins import ListeMixin
from commun.services import supprimer_ou_desactiver
from comptes.permissions import RolePermMixin, RoleRequisMixin

from .forms import (
    CanalPublicationForm,
    DepartementCreerForm,
    DepartementModifierForm,
    EtablissementForm,
    MembreForm,
    TypeStageForm,
)
from .models import CanalPublication, Departement, Etablissement, Membre, TypeStage
from .services import desactiver_membre

_FORM_TPL = "commun/formulaire.html"


def _ctx_form(titre, url_retour, **extra):
    ctx = {"titre": titre, "url_retour": url_retour}
    ctx.update(extra)
    return ctx


# ─── Département ──────────────────────────────────────────────────────────────

class DepartementListView(RolePermMixin, ListeMixin, ListView):
    permission_required = "referentiels.view_departement"
    model = Departement
    context_object_name = "departements"
    template_name = "referentiels/departement_list.html"
    champs_recherche = ["nom", "description"]


class DepartementDetailView(RolePermMixin, DetailView):
    permission_required = "referentiels.view_departement"
    model = Departement
    template_name = "referentiels/departement_detail.html"
    context_object_name = "departement"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["membres"] = self.object.membres.order_by("nom", "prenom")
        return ctx


class DepartementCreateView(RolePermMixin, CreateView):
    permission_required = "referentiels.add_departement"
    model = Departement
    form_class = DepartementCreerForm
    template_name = _FORM_TPL
    success_url = reverse_lazy("referentiels:departement_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_form("Nouveau département", self.success_url))
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Département « {self.object.nom} » créé.")
        return response


class DepartementUpdateView(RolePermMixin, UpdateView):
    permission_required = "referentiels.change_departement"
    model = Departement
    form_class = DepartementModifierForm
    template_name = _FORM_TPL

    def get_success_url(self):
        return reverse("referentiels:departement_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_form(
            f"Modifier — {self.object.nom}",
            reverse("referentiels:departement_detail", kwargs={"pk": self.object.pk}),
        ))
        # Avertissement si le responsable n'a pas de compte Responsable
        if self.object.responsable:
            membre = self.object.responsable
            a_compte_responsable = (
                hasattr(membre, "compte")
                and membre.compte is not None
                and membre.compte.role == "Responsable"
            )
            if not a_compte_responsable:
                ctx["avertissement_responsable"] = (
                    f"« {membre} » n'a pas encore de compte utilisateur avec le rôle Responsable."
                )
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Département « {self.object.nom} » mis à jour.")
        return response


class DepartementDeleteView(RolePermMixin, View):
    permission_required = "referentiels.delete_departement"

    def post(self, request, pk):
        dept = get_object_or_404(Departement, pk=pk)
        supprimer_ou_desactiver(dept, request)
        return redirect("referentiels:departement_list")

    def get(self, request, pk):
        return redirect("referentiels:departement_list")


# ─── Membre (géré depuis DepartementDetail) ───────────────────────────────────

class MembreCreateView(RolePermMixin, CreateView):
    permission_required = "referentiels.add_membre"
    model = Membre
    form_class = MembreForm
    template_name = _FORM_TPL

    def get_departement(self):
        return get_object_or_404(Departement, pk=self.kwargs["dept_pk"])

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields["departement"].queryset = Departement.objects.filter(
            pk=self.kwargs["dept_pk"]
        )
        return form

    def get_initial(self):
        return {"departement": self.kwargs["dept_pk"]}

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dept = self.get_departement()
        ctx.update(_ctx_form(
            f"Nouveau membre — {dept.nom}",
            reverse("referentiels:departement_detail", kwargs={"pk": dept.pk}),
        ))
        return ctx

    def form_valid(self, form):
        self.object = form.save()
        messages.success(self.request, f"Membre « {self.object} » ajouté.")
        return redirect("referentiels:departement_detail", pk=self.kwargs["dept_pk"])


class MembreUpdateView(RolePermMixin, UpdateView):
    permission_required = "referentiels.change_membre"
    model = Membre
    form_class = MembreForm
    template_name = _FORM_TPL

    def get_success_url(self):
        return reverse("referentiels:departement_detail", kwargs={"pk": self.object.departement_id})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_form(
            f"Modifier — {self.object}",
            reverse("referentiels:departement_detail", kwargs={"pk": self.object.departement_id}),
        ))
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Membre « {self.object} » mis à jour.")
        return response


class MembreDesactiverView(RolePermMixin, View):
    permission_required = "referentiels.change_membre"

    def post(self, request, pk):
        membre = get_object_or_404(Membre, pk=pk)
        desactiver_membre(membre, request)
        return redirect("referentiels:departement_detail", pk=membre.departement_id)

    def get(self, request, pk):
        membre = get_object_or_404(Membre, pk=pk)
        return redirect("referentiels:departement_detail", pk=membre.departement_id)


# ─── Établissement ────────────────────────────────────────────────────────────

class EtablissementListView(RolePermMixin, ListeMixin, ListView):
    permission_required = "referentiels.view_etablissement"
    model = Etablissement
    context_object_name = "etablissements"
    template_name = "referentiels/etablissement_list.html"
    champs_recherche = ["nom", "ville", "contact"]

    def get_queryset(self):
        qs = super().get_queryset()
        partenaire = self.request.GET.get("partenaire", "")
        if partenaire in ("1", "0"):
            qs = qs.filter(partenaire=(partenaire == "1"))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["partenaire_filtre"] = self.request.GET.get("partenaire", "")
        return ctx


class EtablissementCreateView(RolePermMixin, CreateView):
    permission_required = "referentiels.add_etablissement"
    model = Etablissement
    form_class = EtablissementForm
    template_name = _FORM_TPL
    success_url = reverse_lazy("referentiels:etablissement_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_form("Nouvel établissement", self.success_url))
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Établissement « {self.object.nom} » créé.")
        return response


class EtablissementUpdateView(RolePermMixin, UpdateView):
    permission_required = "referentiels.change_etablissement"
    model = Etablissement
    form_class = EtablissementForm
    template_name = _FORM_TPL
    success_url = reverse_lazy("referentiels:etablissement_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_form(f"Modifier — {self.object.nom}", self.success_url))
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Établissement « {self.object.nom} » mis à jour.")
        return response


class EtablissementDeleteView(RolePermMixin, View):
    permission_required = "referentiels.delete_etablissement"

    def post(self, request, pk):
        etab = get_object_or_404(Etablissement, pk=pk)
        supprimer_ou_desactiver(etab, request)
        return redirect("referentiels:etablissement_list")

    def get(self, request, pk):
        return redirect("referentiels:etablissement_list")


class EtablissementTogglePartenaireView(RolePermMixin, View):
    permission_required = "referentiels.change_etablissement"

    def post(self, request, pk):
        etab = get_object_or_404(Etablissement, pk=pk)
        etab.partenaire = not etab.partenaire
        etab.save(update_fields=["partenaire"])
        action = "défini comme partenaire" if etab.partenaire else "retiré des partenaires"
        messages.success(request, f"« {etab.nom} » {action}.")
        return redirect("referentiels:etablissement_list")

    def get(self, request, pk):
        return redirect("referentiels:etablissement_list")


# ─── TypeStage ────────────────────────────────────────────────────────────────

class TypeStageListView(RolePermMixin, ListeMixin, ListView):
    permission_required = "referentiels.view_typestage"
    model = TypeStage
    context_object_name = "types_stage"
    template_name = "referentiels/typestage_list.html"
    champs_recherche = ["libelle", "description"]


class TypeStageCreateView(RolePermMixin, CreateView):
    permission_required = "referentiels.add_typestage"
    model = TypeStage
    form_class = TypeStageForm
    template_name = _FORM_TPL
    success_url = reverse_lazy("referentiels:typestage_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_form("Nouveau type de stage", self.success_url))
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Type de stage « {self.object.libelle} » créé.")
        return response


class TypeStageUpdateView(RolePermMixin, UpdateView):
    permission_required = "referentiels.change_typestage"
    model = TypeStage
    form_class = TypeStageForm
    template_name = _FORM_TPL
    success_url = reverse_lazy("referentiels:typestage_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_form(f"Modifier — {self.object.libelle}", self.success_url))
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Type de stage « {self.object.libelle} » mis à jour.")
        return response


class TypeStageDeleteView(RolePermMixin, View):
    permission_required = "referentiels.delete_typestage"

    def post(self, request, pk):
        ts = get_object_or_404(TypeStage, pk=pk)
        supprimer_ou_desactiver(ts, request)
        return redirect("referentiels:typestage_list")

    def get(self, request, pk):
        return redirect("referentiels:typestage_list")


# ─── CanalPublication ─────────────────────────────────────────────────────────

class CanalPublicationListView(RolePermMixin, ListeMixin, ListView):
    permission_required = "referentiels.view_canalpublication"
    model = CanalPublication
    context_object_name = "canaux"
    template_name = "referentiels/canalpublication_list.html"
    champs_recherche = ["nom", "description"]


class CanalPublicationCreateView(RolePermMixin, CreateView):
    permission_required = "referentiels.add_canalpublication"
    model = CanalPublication
    form_class = CanalPublicationForm
    template_name = _FORM_TPL
    success_url = reverse_lazy("referentiels:canalpublication_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_form("Nouveau canal de publication", self.success_url))
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Canal « {self.object.nom} » créé.")
        return response


class CanalPublicationUpdateView(RolePermMixin, UpdateView):
    permission_required = "referentiels.change_canalpublication"
    model = CanalPublication
    form_class = CanalPublicationForm
    template_name = _FORM_TPL
    success_url = reverse_lazy("referentiels:canalpublication_list")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_form(f"Modifier — {self.object.nom}", self.success_url))
        return ctx

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f"Canal « {self.object.nom} » mis à jour.")
        return response


class CanalPublicationDeleteView(RolePermMixin, View):
    permission_required = "referentiels.delete_canalpublication"

    def post(self, request, pk):
        canal = get_object_or_404(CanalPublication, pk=pk)
        supprimer_ou_desactiver(canal, request)
        return redirect("referentiels:canalpublication_list")

    def get(self, request, pk):
        return redirect("referentiels:canalpublication_list")
