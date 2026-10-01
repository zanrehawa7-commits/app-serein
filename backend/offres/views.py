from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import DetailView, ListView

from comptes.permissions import RoleRequisMixin, _role_utilisateur
from suivi.models import Historique

from .forms import BesoinForm, OffreForm, PublicationForm
from .models import Besoin, Offre, Publication, StatutBesoin, StatutOffre
from .services import (
    TransitionInterdite,
    annuler_besoin,
    creer_besoin,
    creer_offre,
    fermer_offre,
    ouvrir_offre,
    rouvrir_offre,
    supprimer_offre,
    suspendre_offre,
)

_FORM_TPL = "commun/formulaire.html"
_ROLES_TOUS = ["Administrateur", "Secrétaire", "Responsable"]


def _get_historique(objet):
    ct = ContentType.objects.get_for_model(objet)
    return Historique.objects.filter(content_type=ct, object_id=objet.pk).select_related("utilisateur")


def _verifier_dept_responsable(request, besoin):
    """Lève PermissionDenied si le responsable n'est pas du même département que le besoin."""
    if not request.user.personnel or besoin.departement != request.user.personnel.departement:
        raise PermissionDenied


# ─── Besoins ──────────────────────────────────────────────────────────────────

class BesoinListView(RoleRequisMixin, ListView):
    roles = _ROLES_TOUS
    model = Besoin
    template_name = "offres/besoin_list.html"
    context_object_name = "besoins"
    paginate_by = 20

    def get_queryset(self):
        role = _role_utilisateur(self.request.user)
        if role == "Responsable":
            if not self.request.user.personnel:
                return Besoin.objects.none()
            qs = Besoin.objects.filter(departement=self.request.user.personnel.departement)
        else:
            qs = Besoin.objects.all()

        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(profil_recherche__icontains=q)
                | Q(departement__nom__icontains=q)
                | Q(type_stage__libelle__icontains=q)
            )
        statut = self.request.GET.get("statut", "")
        if statut:
            qs = qs.filter(statut=statut)
        type_stage = self.request.GET.get("type_stage", "")
        if type_stage:
            qs = qs.filter(type_stage_id=type_stage)

        return qs.select_related("departement", "type_stage").order_by("statut", "-date_creation")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from referentiels.models import TypeStage
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["params_paginateur"] = params.urlencode()
        ctx["q"] = self.request.GET.get("q", "")
        ctx["statut_filtre"] = self.request.GET.get("statut", "")
        ctx["type_stage_filtre"] = self.request.GET.get("type_stage", "")
        ctx["types_stage"] = TypeStage.objects.filter(actif=True)
        ctx["statuts"] = StatutBesoin.choices
        ctx["role"] = _role_utilisateur(self.request.user)
        return ctx


class BesoinDetailView(RoleRequisMixin, DetailView):
    roles = _ROLES_TOUS
    model = Besoin
    template_name = "offres/besoin_detail.html"
    context_object_name = "besoin"

    def get_object(self):
        obj = super().get_object()
        if _role_utilisateur(self.request.user) == "Responsable":
            _verifier_dept_responsable(self.request, obj)
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        besoin = self.object
        ctx["historiques"] = _get_historique(besoin)
        ctx["role"] = _role_utilisateur(self.request.user)
        try:
            ctx["offre"] = besoin.offre
        except Offre.DoesNotExist:
            ctx["offre"] = None
        return ctx


class BesoinCreateView(RoleRequisMixin, View):
    roles = ["Responsable"]

    def dispatch(self, request, *args, **kwargs):
        if not request.user.personnel:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def _form(self, request, data=None, **kwargs):
        dept = request.user.personnel.departement
        form = BesoinForm(data, **kwargs)
        form.fields["departement"].queryset = dept.__class__.objects.filter(pk=dept.pk)
        form.fields["departement"].initial = dept
        return form

    def get(self, request):
        form = self._form(request)
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": "Nouveau besoin de stage",
            "url_retour": reverse("offres:besoin_list"),
        })

    def post(self, request):
        form = self._form(request, data=request.POST)
        if form.is_valid():
            besoin = creer_besoin(
                departement=request.user.personnel.departement,  # toujours le dept du membre
                type_stage=form.cleaned_data["type_stage"],
                date_debut=form.cleaned_data["date_debut"],
                date_fin=form.cleaned_data["date_fin"],
                profil_recherche=form.cleaned_data["profil_recherche"],
                nombre_places=form.cleaned_data["nombre_places"],
                utilisateur=request.user,
            )
            messages.success(request, "Besoin envoyé à la secrétaire.")
            return redirect("offres:besoin_detail", pk=besoin.pk)
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": "Nouveau besoin de stage",
            "url_retour": reverse("offres:besoin_list"),
        })


class BesoinModifierView(RoleRequisMixin, View):
    roles = ["Responsable"]

    def _get_besoin_ou_redirect(self, request, pk):
        besoin = get_object_or_404(Besoin, pk=pk)
        _verifier_dept_responsable(request, besoin)
        if besoin.statut != StatutBesoin.ENVOYE:
            messages.error(request, f"Ce besoin ne peut plus être modifié (statut : {besoin.get_statut_display()}).")
            return besoin, False
        return besoin, True

    def _form(self, request, data=None, **kwargs):
        dept = request.user.personnel.departement
        form = BesoinForm(data, **kwargs)
        form.fields["departement"].queryset = dept.__class__.objects.filter(pk=dept.pk)
        return form

    def get(self, request, pk):
        besoin, peut = self._get_besoin_ou_redirect(request, pk)
        if not peut:
            return redirect("offres:besoin_detail", pk=pk)
        form = self._form(request, instance=besoin)
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": "Modifier le besoin",
            "url_retour": reverse("offres:besoin_detail", kwargs={"pk": pk}),
        })

    def post(self, request, pk):
        besoin, peut = self._get_besoin_ou_redirect(request, pk)
        if not peut:
            return redirect("offres:besoin_detail", pk=pk)
        form = self._form(request, data=request.POST, instance=besoin)
        if form.is_valid():
            form.save()
            messages.success(request, "Besoin mis à jour.")
            return redirect("offres:besoin_detail", pk=pk)
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": "Modifier le besoin",
            "url_retour": reverse("offres:besoin_detail", kwargs={"pk": pk}),
        })


class BesoinAnnulerView(RoleRequisMixin, View):
    roles = ["Responsable"]

    def post(self, request, pk):
        besoin = get_object_or_404(Besoin, pk=pk)
        _verifier_dept_responsable(request, besoin)
        try:
            annuler_besoin(besoin, request.user)
            messages.success(request, "Besoin annulé.")
        except TransitionInterdite as e:
            messages.error(request, str(e))
        return redirect("offres:besoin_detail", pk=pk)

    def get(self, request, pk):
        return redirect("offres:besoin_detail", pk=pk)


# ─── Offres ───────────────────────────────────────────────────────────────────

class OffreListView(RoleRequisMixin, ListView):
    roles = _ROLES_TOUS
    model = Offre
    template_name = "offres/offre_list.html"
    context_object_name = "offres"
    paginate_by = 20

    def get_queryset(self):
        role = _role_utilisateur(self.request.user)
        if role == "Responsable":
            if not self.request.user.personnel:
                return Offre.objects.none()
            qs = Offre.objects.filter(besoin__departement=self.request.user.personnel.departement)
        else:
            qs = Offre.objects.all()

        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(titre__icontains=q)
                | Q(description__icontains=q)
                | Q(profil_recherche__icontains=q)
            )
        statut = self.request.GET.get("statut", "")
        if statut:
            qs = qs.filter(statut=statut)
        type_stage = self.request.GET.get("type_stage", "")
        if type_stage:
            qs = qs.filter(type_stage_id=type_stage)

        return qs.select_related("type_stage", "besoin__departement").order_by("-date_creation")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from referentiels.models import TypeStage
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["params_paginateur"] = params.urlencode()
        ctx["q"] = self.request.GET.get("q", "")
        ctx["statut_filtre"] = self.request.GET.get("statut", "")
        ctx["type_stage_filtre"] = self.request.GET.get("type_stage", "")
        ctx["types_stage"] = TypeStage.objects.filter(actif=True)
        ctx["statuts"] = StatutOffre.choices
        ctx["role"] = _role_utilisateur(self.request.user)
        return ctx


class OffreDetailView(RoleRequisMixin, DetailView):
    roles = _ROLES_TOUS
    model = Offre
    template_name = "offres/offre_detail.html"
    context_object_name = "offre"

    def get_object(self):
        obj = super().get_object()
        if _role_utilisateur(self.request.user) == "Responsable":
            if not self.request.user.personnel:
                raise PermissionDenied
            if not obj.besoin or obj.besoin.departement != self.request.user.personnel.departement:
                raise PermissionDenied
        return obj

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        offre = self.object
        ctx["historiques"] = _get_historique(offre)
        ctx["publications"] = offre.publications.select_related("canal").order_by("-date_publication")
        ctx["role"] = _role_utilisateur(self.request.user)
        ctx["places_restantes"] = offre.places_restantes()
        ctx["texte_publication"] = (
            f"OFFRE DE STAGE — {offre.titre}\n"
            f"Type : {offre.type_stage}\n"
            f"Période : du {offre.date_debut.strftime('%d/%m/%Y')} au {offre.date_fin.strftime('%d/%m/%Y')}\n"
            f"Profil recherché : {offre.profil_recherche}\n"
            f"Nombre de places : {offre.nombre_places}\n"
            f"Contact : Serein-GE"
        )
        if offre.statut == StatutOffre.OUVERTE and _role_utilisateur(self.request.user) == "Secrétaire":
            ctx["form_publication"] = PublicationForm()
        return ctx


class OffreCreateView(RoleRequisMixin, View):
    roles = ["Secrétaire"]

    def get(self, request):
        form = OffreForm()
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": "Nouvelle offre de stage",
            "url_retour": reverse("offres:offre_list"),
        })

    def post(self, request):
        form = OffreForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            offre = creer_offre(
                type_stage=cd["type_stage"],
                titre=cd["titre"],
                description=cd["description"],
                profil_recherche=cd["profil_recherche"],
                date_debut=cd["date_debut"],
                date_fin=cd["date_fin"],
                nombre_places=cd["nombre_places"],
                utilisateur=request.user,
            )
            messages.success(request, f"Offre « {offre.titre} » créée (brouillon).")
            return redirect("offres:offre_detail", pk=offre.pk)
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": "Nouvelle offre de stage",
            "url_retour": reverse("offres:offre_list"),
        })


class OffreCreateFromBesoinView(RoleRequisMixin, View):
    roles = ["Secrétaire"]

    def _get_besoin(self, pk):
        return get_object_or_404(Besoin, pk=pk)

    def get(self, request, besoin_pk):
        besoin = self._get_besoin(besoin_pk)
        initial = {
            "type_stage": besoin.type_stage,
            "date_debut": besoin.date_debut,
            "date_fin": besoin.date_fin,
            "profil_recherche": besoin.profil_recherche,
            "nombre_places": besoin.nombre_places,
        }
        form = OffreForm(initial=initial)
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": "Créer une offre depuis le besoin",
            "url_retour": reverse("offres:besoin_detail", kwargs={"pk": besoin_pk}),
        })

    def post(self, request, besoin_pk):
        besoin = self._get_besoin(besoin_pk)
        form = OffreForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            try:
                offre = creer_offre(
                    type_stage=cd["type_stage"],
                    titre=cd["titre"],
                    description=cd["description"],
                    profil_recherche=cd["profil_recherche"],
                    date_debut=cd["date_debut"],
                    date_fin=cd["date_fin"],
                    nombre_places=cd["nombre_places"],
                    utilisateur=request.user,
                    besoin=besoin,
                )
                messages.success(request, f"Offre « {offre.titre} » créée. Le besoin est pris en charge.")
                return redirect("offres:offre_detail", pk=offre.pk)
            except TransitionInterdite as e:
                messages.error(request, str(e))
                return redirect("offres:besoin_detail", pk=besoin_pk)
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": "Créer une offre depuis le besoin",
            "url_retour": reverse("offres:besoin_detail", kwargs={"pk": besoin_pk}),
        })


class OffreModifierView(RoleRequisMixin, View):
    roles = ["Secrétaire"]

    def get(self, request, pk):
        offre = get_object_or_404(Offre, pk=pk)
        if offre.statut == StatutOffre.FERMEE:
            messages.error(request, "Une offre fermée ne peut plus être modifiée.")
            return redirect("offres:offre_detail", pk=pk)
        form = OffreForm(instance=offre)
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": f"Modifier — {offre.titre}",
            "url_retour": reverse("offres:offre_detail", kwargs={"pk": pk}),
        })

    def post(self, request, pk):
        offre = get_object_or_404(Offre, pk=pk)
        if offre.statut == StatutOffre.FERMEE:
            messages.error(request, "Une offre fermée ne peut plus être modifiée.")
            return redirect("offres:offre_detail", pk=pk)
        form = OffreForm(request.POST, instance=offre)
        if form.is_valid():
            form.save()
            messages.success(request, f"Offre « {offre.titre} » mise à jour.")
            return redirect("offres:offre_detail", pk=pk)
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": f"Modifier — {offre.titre}",
            "url_retour": reverse("offres:offre_detail", kwargs={"pk": pk}),
        })


class _OffreTransitionView(RoleRequisMixin, View):
    """Base pour les vues de transition d'état d'une offre (POST uniquement)."""
    roles = ["Secrétaire"]

    def _transition(self, offre, utilisateur):
        raise NotImplementedError

    def _message_succes(self, offre):
        return f"Offre « {offre.titre} » mise à jour."

    def post(self, request, pk):
        offre = get_object_or_404(Offre, pk=pk)
        try:
            self._transition(offre, request.user)
            messages.success(request, self._message_succes(offre))
        except TransitionInterdite as e:
            messages.error(request, str(e))
        return redirect("offres:offre_detail", pk=pk)

    def get(self, request, pk):
        return redirect("offres:offre_detail", pk=pk)


class OffreOuvrirView(_OffreTransitionView):
    def _transition(self, offre, utilisateur):
        ouvrir_offre(offre, utilisateur)

    def _message_succes(self, offre):
        return f"Offre « {offre.titre} » ouverte aux candidatures."


class OffreSuspendreView(_OffreTransitionView):
    def _transition(self, offre, utilisateur):
        suspendre_offre(offre, utilisateur)

    def _message_succes(self, offre):
        return f"Offre « {offre.titre} » suspendue."


class OffreRouvrirView(_OffreTransitionView):
    def _transition(self, offre, utilisateur):
        rouvrir_offre(offre, utilisateur)

    def _message_succes(self, offre):
        return f"Offre « {offre.titre} » réouverte."


class OffreFermerView(_OffreTransitionView):
    def _transition(self, offre, utilisateur):
        fermer_offre(offre, utilisateur)

    def _message_succes(self, offre):
        return f"Offre « {offre.titre} » fermée."


class OffreSupprimerView(RoleRequisMixin, View):
    roles = ["Secrétaire"]

    def post(self, request, pk):
        offre = get_object_or_404(Offre, pk=pk)
        titre = str(offre)
        try:
            supprimer_offre(offre, request.user)
            messages.success(request, f"Offre « {titre} » supprimée.")
            return redirect("offres:offre_list")
        except TransitionInterdite as e:
            messages.error(request, str(e))
            return redirect("offres:offre_detail", pk=pk)

    def get(self, request, pk):
        return redirect("offres:offre_detail", pk=pk)


# ─── Publications ─────────────────────────────────────────────────────────────

class PublicationCreateView(RoleRequisMixin, View):
    roles = ["Secrétaire"]

    def post(self, request, offre_pk):
        offre = get_object_or_404(Offre, pk=offre_pk)
        if offre.statut != StatutOffre.OUVERTE:
            messages.error(request, "Impossible d'ajouter une publication : l'offre n'est pas ouverte.")
            return redirect("offres:offre_detail", pk=offre_pk)
        form = PublicationForm(request.POST)
        if form.is_valid():
            pub = form.save(commit=False)
            pub.offre = offre
            pub.save()
            messages.success(request, "Publication ajoutée.")
        else:
            for field, errs in form.errors.items():
                label = form.fields[field].label if field in form.fields else field
                for err in errs:
                    messages.error(request, f"{label} : {err}")
        return redirect("offres:offre_detail", pk=offre_pk)

    def get(self, request, offre_pk):
        return redirect("offres:offre_detail", pk=offre_pk)


class PublicationModifierView(RoleRequisMixin, View):
    roles = ["Secrétaire"]

    def get(self, request, pk):
        pub = get_object_or_404(Publication, pk=pk)
        form = PublicationForm(instance=pub)
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": f"Modifier la publication — {pub.canal}",
            "url_retour": reverse("offres:offre_detail", kwargs={"pk": pub.offre_id}),
        })

    def post(self, request, pk):
        pub = get_object_or_404(Publication, pk=pk)
        form = PublicationForm(request.POST, instance=pub)
        if form.is_valid():
            form.save()
            messages.success(request, "Publication mise à jour.")
            return redirect("offres:offre_detail", pk=pub.offre_id)
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": f"Modifier la publication — {pub.canal}",
            "url_retour": reverse("offres:offre_detail", kwargs={"pk": pub.offre_id}),
        })


class PublicationSupprimerView(RoleRequisMixin, View):
    roles = ["Secrétaire"]

    def post(self, request, pk):
        pub = get_object_or_404(Publication, pk=pk)
        offre_pk = pub.offre_id
        pub.delete()
        messages.success(request, "Publication supprimée.")
        return redirect("offres:offre_detail", pk=offre_pk)

    def get(self, request, pk):
        pub = get_object_or_404(Publication, pk=pk)
        return redirect("offres:offre_detail", pk=pub.offre_id)
