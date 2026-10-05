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
    PersonnelForm,
    TypeStageForm,
)
from .models import CanalPublication, Departement, Etablissement, Personnel, TypeStage
from .services import (
    ConfirmationRequise,
    CreerCompteRequis,
    TransitionInterdite,
    desactiver_personnel,
    designer_responsable,
)

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
        ctx["personnels"] = self.object.personnels.order_by("nom", "prenom")
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
        dept = form.save()
        responsable = form.cleaned_data.get("nouveau_responsable")

        if responsable:
            # Rattacher d'abord le personnel au département
            responsable.departement = dept
            responsable.save(update_fields=["departement"])
            try:
                designer_responsable(responsable, self.request.user, confirmer=True)
                messages.success(
                    self.request,
                    f"Département « {dept.nom} » créé avec {responsable} comme responsable.",
                )
            except CreerCompteRequis:
                # Le dept et le rattachement sont déjà sauvés ; proposer la création du compte.
                messages.warning(
                    self.request,
                    f"Département « {dept.nom} » créé. "
                    f"« {responsable} » est désigné(e) responsable mais n'a pas encore de compte. "
                    "Créez-le maintenant.",
                )
                url = (
                    reverse("comptes:utilisateur_creer")
                    + f"?personnel={responsable.pk}&role=Responsable&designer=1"
                    + f"&next={reverse('referentiels:departement_detail', kwargs={'pk': dept.pk})}"
                )
                return redirect(url)
        else:
            messages.success(self.request, f"Département « {dept.nom} » créé.")

        return redirect("referentiels:departement_detail", pk=dept.pk)


class DepartementUpdateView(RolePermMixin, UpdateView):
    permission_required = "referentiels.change_departement"
    model = Departement
    form_class = DepartementModifierForm
    template_name = "referentiels/departement_modifier_form.html"

    def get_success_url(self):
        return reverse("referentiels:departement_detail", kwargs={"pk": self.object.pk})

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx.update(_ctx_form(
            f"Modifier — {self.object.nom}",
            reverse("referentiels:departement_detail", kwargs={"pk": self.object.pk}),
        ))
        return ctx

    def form_valid(self, form):
        # Sauvegarder les autres champs (nom, description, actif) sans toucher au responsable
        instance = form.save(commit=False)
        ancien_responsable = self.object.responsable
        instance.responsable = ancien_responsable  # ne pas laisser le ModelForm écraser
        instance.save()

        nouveau_responsable = form.cleaned_data.get("responsable")
        confirmer = self.request.POST.get("confirmer_remplacement") == "1"

        if nouveau_responsable and (
            ancien_responsable is None or nouveau_responsable.pk != ancien_responsable.pk
        ):
            try:
                designer_responsable(nouveau_responsable, self.request.user, confirmer=confirmer)
                messages.success(
                    self.request,
                    f"Département « {instance.nom} » mis à jour, {nouveau_responsable} désigné(e) responsable.",
                )
            except ConfirmationRequise as e:
                ctx = self.get_context_data(
                    form=form,
                    confirmation_requise=True,
                    ancien_responsable=e.args[0],
                )
                return self.render_to_response(ctx)
            except CreerCompteRequis:
                messages.warning(
                    self.request,
                    f"Département mis à jour. « {nouveau_responsable} » n'a pas encore de compte. Créez-le maintenant.",
                )
                url = (
                    reverse("comptes:utilisateur_creer")
                    + f"?personnel={nouveau_responsable.pk}&role=Responsable&designer=1"
                    + f"&next={reverse('referentiels:departement_detail', kwargs={'pk': instance.pk})}"
                )
                return redirect(url)
        elif not nouveau_responsable and ancien_responsable:
            # Retirer le responsable
            instance.responsable = None
            instance.save(update_fields=["responsable"])
            messages.success(self.request, f"Département « {instance.nom} » mis à jour, responsable retiré.")
        else:
            messages.success(self.request, f"Département « {instance.nom} » mis à jour.")

        return redirect(self.get_success_url())


class DepartementDeleteView(RolePermMixin, View):
    permission_required = "referentiels.delete_departement"

    def post(self, request, pk):
        dept = get_object_or_404(Departement, pk=pk)
        supprimer_ou_desactiver(dept, request)
        return redirect("referentiels:departement_list")

    def get(self, request, pk):
        return redirect("referentiels:departement_list")


# ─── Personnel ────────────────────────────────────────────────────────────────

class PersonnelListView(RolePermMixin, ListeMixin, ListView):
    permission_required = "referentiels.view_personnel"
    model = Personnel
    context_object_name = "personnels"
    template_name = "referentiels/personnel_list.html"
    champs_recherche = ["nom", "prenom", "fonction", "email", "telephone"]

    def get_queryset(self):
        qs = super().get_queryset()
        dept_pk = self.request.GET.get("dept", "")
        if dept_pk:
            qs = qs.filter(departement__pk=dept_pk)
        responsable_filtre = self.request.GET.get("responsable", "")
        if responsable_filtre == "1":
            qs = qs.filter(departement_dirige__isnull=False)
        elif responsable_filtre == "0":
            qs = qs.filter(departement_dirige__isnull=True)
        return qs.select_related("departement", "departement_dirige", "compte")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["departements"] = Departement.objects.filter(actif=True).order_by("nom")
        ctx["dept_filtre"] = self.request.GET.get("dept", "")
        ctx["responsable_filtre"] = self.request.GET.get("responsable", "")
        return ctx


class PersonnelDetailView(RolePermMixin, DetailView):
    permission_required = "referentiels.view_personnel"
    model = Personnel
    template_name = "referentiels/personnel_detail.html"
    context_object_name = "personnel"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["dept_dirige"] = Departement.objects.filter(responsable=self.object).first()
        return ctx


class PersonnelCreateView(RolePermMixin, CreateView):
    permission_required = "referentiels.add_personnel"
    model = Personnel
    form_class = PersonnelForm
    template_name = "referentiels/personnel_form.html"

    def get_initial(self):
        initial = super().get_initial()
        dept_pk = self.request.GET.get("dept")
        if dept_pk:
            initial["departement"] = dept_pk
        return initial

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["titre"] = "Nouveau personnel"
        ctx["url_retour"] = reverse("referentiels:personnel_list")
        return ctx

    def form_valid(self, form):
        self.object = form.save()
        return self._gerer_designation(form, creation=True)

    def _gerer_designation(self, form, creation=False):
        label = "créé" if creation else "mis à jour"
        if form.cleaned_data.get("designer_responsable"):
            confirmer = self.request.POST.get("confirmer_remplacement") == "1"
            try:
                designer_responsable(self.object, self.request.user, confirmer=confirmer)
                messages.success(
                    self.request,
                    f"Personnel « {self.object} » {label} et désigné(e) responsable.",
                )
            except ConfirmationRequise as e:
                ctx = self.get_context_data(
                    form=form,
                    confirmation_requise=True,
                    ancien_responsable=e.args[0],
                )
                return self.render_to_response(ctx)
            except CreerCompteRequis:
                messages.info(
                    self.request,
                    f"Personnel « {self.object} » {label}. Créez maintenant son compte Responsable.",
                )
                url = (
                    reverse("comptes:utilisateur_creer")
                    + f"?personnel={self.object.pk}&role=Responsable&designer=1"
                    + f"&next={reverse('referentiels:personnel_detail', kwargs={'pk': self.object.pk})}"
                )
                return redirect(url)
            except TransitionInterdite as e:
                messages.error(self.request, str(e))
        else:
            messages.success(self.request, f"Personnel « {self.object} » {label}.")

        return redirect("referentiels:personnel_detail", pk=self.object.pk)


class PersonnelUpdateView(RolePermMixin, UpdateView):
    permission_required = "referentiels.change_personnel"
    model = Personnel
    form_class = PersonnelForm
    template_name = "referentiels/personnel_form.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["titre"] = f"Modifier — {self.object}"
        ctx["url_retour"] = reverse("referentiels:personnel_detail", kwargs={"pk": self.object.pk})
        ctx["dept_dirige"] = Departement.objects.filter(responsable=self.object).first()
        # Pré-cocher la case si déjà responsable
        if not ctx.get("form").is_bound:
            dept_dirige = ctx["dept_dirige"]
            if dept_dirige:
                ctx["form"].initial["designer_responsable"] = True
        return ctx

    def form_valid(self, form):
        self.object = form.save()
        return self._gerer_designation(form, creation=False)

    # Réutilise la méthode du CreateView
    _gerer_designation = PersonnelCreateView._gerer_designation


class PersonnelDesactiverView(RolePermMixin, View):
    permission_required = "referentiels.change_personnel"

    def post(self, request, pk):
        personnel = get_object_or_404(Personnel, pk=pk)
        desactiver_personnel(personnel, request)
        return redirect("referentiels:personnel_detail", pk=pk)

    def get(self, request, pk):
        return redirect("referentiels:personnel_detail", pk=pk)


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
