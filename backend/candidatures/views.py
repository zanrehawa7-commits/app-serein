import os
from pathlib import Path
from django.conf import settings
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.views.generic import ListView
from suivi.models import Historique

from commun.mixins import ListeMixin
from comptes.permissions import RoleRequisMixin
from .forms import (
    CandidatForm,
    CandidatRechercheForm,
    CandidatureForm,
    PieceJointeFormSet,
)
from .models import Candidat, Candidature, PieceJointe, StatutCandidature, TypePiece
from .services import (
    CandidatExistant,
    CandidatureActiveExistante,
    creer_candidature,
    marquer_informe,
    modifier_candidat,
    modifier_candidature,
    rechercher_candidats,
)

_ROLES_LECTURE = ["Secrétaire", "Administrateur", "Responsable"]


def _get_historique(objet):
    ct = ContentType.objects.get_for_model(objet)
    return Historique.objects.filter(content_type=ct, object_id=objet.pk).select_related("utilisateur")


def _est_responsable(user):
    return user.groups.filter(name="Responsable").exists()


# ─── Candidats ───────────────────────────────────────────────────────────────


class CandidatRechercheView(RoleRequisMixin, View):
    roles = ["Secrétaire"]
    template_name = "candidatures/candidat_recherche.html"

    def get(self, request):
        form = CandidatRechercheForm(request.GET or None)
        candidats = []
        q = ""
        if form.is_valid():
            q = form.cleaned_data["q"]
            candidats = rechercher_candidats(q)
        return render(request, self.template_name, {"form": form, "candidats": candidats, "q": q})


class CandidatCreateView(RoleRequisMixin, View):
    roles = ["Secrétaire"]
    template_name = "candidatures/candidat_form.html"

    def get(self, request):
        form = CandidatForm()
        return render(request, self.template_name, {
            "form": form, "titre": "Nouveau candidat",
            "url_retour": "candidatures:candidat_recherche",
        })

    def post(self, request):
        form = CandidatForm(request.POST)
        if form.is_valid():
            candidat = form.save()
            messages.success(request, f"Candidat {candidat} créé.")
            return redirect("candidatures:candidature_creer", candidat_pk=candidat.pk)
        return render(request, self.template_name, {
            "form": form, "titre": "Nouveau candidat",
            "url_retour": "candidatures:candidat_recherche",
        })


class CandidatDetailView(RoleRequisMixin, View):
    roles = _ROLES_LECTURE
    template_name = "candidatures/candidat_detail.html"

    def get(self, request, pk):
        candidat = get_object_or_404(Candidat, pk=pk)
        candidatures = candidat.candidatures.select_related("departement", "type_stage").order_by("-date_depot")
        return render(request, self.template_name, {
            "candidat": candidat,
            "candidatures": candidatures,
        })


class CandidatModifierView(RoleRequisMixin, View):
    roles = ["Secrétaire"]
    template_name = "candidatures/candidat_form.html"

    def get(self, request, pk):
        candidat = get_object_or_404(Candidat, pk=pk)
        form = CandidatForm(instance=candidat)
        return render(request, self.template_name, {
            "form": form, "titre": f"Modifier — {candidat}",
            "candidat": candidat,
            "url_retour": "candidatures:candidat_detail",
        })

    def post(self, request, pk):
        candidat = get_object_or_404(Candidat, pk=pk)
        form = CandidatForm(request.POST, instance=candidat)
        if form.is_valid():
            try:
                modifier_candidat(
                    candidat,
                    nom=form.cleaned_data["nom"],
                    prenom=form.cleaned_data["prenom"],
                    telephone=form.cleaned_data["telephone"],
                    email=form.cleaned_data.get("email", ""),
                    adresse=form.cleaned_data.get("adresse", ""),
                    niveau_etudes=form.cleaned_data.get("niveau_etudes", ""),
                    filiere=form.cleaned_data.get("filiere", ""),
                    etablissement=form.cleaned_data.get("etablissement"),
                )
                messages.success(request, f"Candidat {candidat} mis à jour.")
                return redirect("candidatures:candidat_detail", pk=candidat.pk)
            except CandidatExistant as e:
                form.add_error("telephone", str(e))
        return render(request, self.template_name, {
            "form": form, "titre": f"Modifier — {candidat}",
            "candidat": candidat,
            "url_retour": "candidatures:candidat_detail",
        })


# ─── Candidatures ─────────────────────────────────────────────────────────────


class CandidatureCreateView(RoleRequisMixin, View):
    roles = ["Secrétaire"]
    template_name = "candidatures/candidature_form.html"

    def _get_candidat(self, candidat_pk):
        return get_object_or_404(Candidat, pk=candidat_pk)

    def get(self, request, candidat_pk):
        candidat = self._get_candidat(candidat_pk)
        form = CandidatureForm()
        formset = PieceJointeFormSet(prefix="pieces")
        return render(request, self.template_name, {
            "form": form, "formset": formset, "candidat": candidat,
            "titre": "Nouvelle candidature",
        })

    def post(self, request, candidat_pk):
        candidat = self._get_candidat(candidat_pk)
        form = CandidatureForm(request.POST)
        formset = PieceJointeFormSet(request.POST, request.FILES, prefix="pieces")

        if form.is_valid() and formset.is_valid():
            pieces_data = []
            for f in formset.forms:
                if f.cleaned_data and f.cleaned_data.get("fichier"):
                    upload = f.cleaned_data["fichier"]
                    pieces_data.append({
                        "type_piece": f.cleaned_data["type_piece"],
                        "fichier": upload,
                        "nom_original": upload.name,
                    })
            cd = form.cleaned_data
            try:
                candidature = creer_candidature(
                    candidat=candidat,
                    departement=cd["departement"],
                    type_stage=cd["type_stage"],
                    type_demande=cd["type_demande"],
                    debut_disponibilite=cd["debut_disponibilite"],
                    fin_disponibilite=cd["fin_disponibilite"],
                    duree_souhaitee=cd["duree_souhaitee"],
                    commentaire=cd.get("commentaire", ""),
                    offre=cd.get("offre"),
                    pieces_data=pieces_data,
                    utilisateur=request.user,
                )
                messages.success(request, f"Candidature {candidature.reference} enregistrée.")
                return redirect("candidatures:candidature_detail", pk=candidature.pk)
            except CandidatureActiveExistante as e:
                messages.error(request, str(e))

        return render(request, self.template_name, {
            "form": form, "formset": formset, "candidat": candidat,
            "titre": "Nouvelle candidature",
        })


class CandidatureListView(RoleRequisMixin, ListeMixin, ListView):
    roles = _ROLES_LECTURE
    model = Candidature
    template_name = "candidatures/candidature_list.html"
    context_object_name = "candidatures"
    champs_recherche = ["reference", "candidat__nom", "candidat__prenom", "candidat__telephone"]
    champ_actif = None

    def get_queryset(self):
        qs = super().get_queryset().select_related("candidat", "departement", "type_stage")

        if _est_responsable(self.request.user):
            if self.request.user.membre:
                qs = qs.filter(departement=self.request.user.membre.departement)
            else:
                qs = qs.none()

        statut = self.request.GET.get("statut")
        if statut:
            qs = qs.filter(statut=statut)

        departement_id = self.request.GET.get("departement")
        if departement_id:
            qs = qs.filter(departement_id=departement_id)

        type_demande = self.request.GET.get("type_demande")
        if type_demande:
            qs = qs.filter(type_demande=type_demande)

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from referentiels.models import Departement
        from .models import TypeDemande
        ctx["statuts"] = StatutCandidature.choices
        ctx["types_demande"] = TypeDemande.choices
        ctx["departements"] = Departement.objects.filter(actif=True)
        ctx["statut_filtre"] = self.request.GET.get("statut", "")
        ctx["departement_filtre"] = self.request.GET.get("departement", "")
        ctx["type_demande_filtre"] = self.request.GET.get("type_demande", "")
        return ctx


class CandidatureDetailView(RoleRequisMixin, View):
    roles = _ROLES_LECTURE
    template_name = "candidatures/candidature_detail.html"

    def get(self, request, pk):
        candidature = get_object_or_404(
            Candidature.objects.select_related("candidat", "departement", "type_stage", "offre"),
            pk=pk,
        )
        if _est_responsable(request.user):
            if not request.user.membre or candidature.departement != request.user.membre.departement:
                raise PermissionDenied

        pieces = candidature.pieces.order_by("type_piece")
        historiques = _get_historique(candidature).order_by("-date_action")
        return render(request, self.template_name, {
            "candidature": candidature,
            "pieces": pieces,
            "historiques": historiques,
        })


class CandidatureModifierView(RoleRequisMixin, View):
    roles = ["Secrétaire"]
    template_name = "candidatures/candidature_form.html"

    def _get_candidature(self, pk):
        return get_object_or_404(Candidature.objects.select_related("candidat"), pk=pk)

    def get(self, request, pk):
        candidature = self._get_candidature(pk)
        if candidature.statut != StatutCandidature.RECUE:
            messages.error(request, "Seules les candidatures au statut REÇUE peuvent être modifiées.")
            return redirect("candidatures:candidature_detail", pk=pk)
        form = CandidatureForm(instance=candidature)
        formset = PieceJointeFormSet(prefix="pieces")
        return render(request, self.template_name, {
            "form": form, "formset": formset,
            "candidat": candidature.candidat,
            "candidature": candidature,
            "pieces_existantes": candidature.pieces.order_by("type_piece"),
            "titre": f"Modifier — {candidature.reference}",
        })

    def post(self, request, pk):
        candidature = self._get_candidature(pk)
        if candidature.statut != StatutCandidature.RECUE:
            messages.error(request, "Seules les candidatures au statut REÇUE peuvent être modifiées.")
            return redirect("candidatures:candidature_detail", pk=pk)

        form = CandidatureForm(request.POST, instance=candidature)
        formset = PieceJointeFormSet(request.POST, request.FILES, prefix="pieces")
        pieces_existantes = candidature.pieces.order_by("type_piece")

        pieces_a_supprimer = [
            int(v) for k, v in request.POST.items()
            if k.startswith("delete_piece_")
        ]

        if form.is_valid() and formset.is_valid():
            nouvelles_pieces = []
            for f in formset.forms:
                if f.cleaned_data and f.cleaned_data.get("fichier"):
                    upload = f.cleaned_data["fichier"]
                    nouvelles_pieces.append({
                        "type_piece": f.cleaned_data["type_piece"],
                        "fichier": upload,
                        "nom_original": upload.name,
                    })

            pieces_restantes = pieces_existantes.exclude(pk__in=pieces_a_supprimer)
            a_cv = (
                pieces_restantes.filter(type_piece=TypePiece.CV).exists()
                or any(p["type_piece"] == TypePiece.CV for p in nouvelles_pieces)
            )
            if not a_cv:
                messages.error(request, "Au moins un CV doit rester dans le dossier.")
                return render(request, self.template_name, {
                    "form": form, "formset": formset,
                    "candidat": candidature.candidat,
                    "candidature": candidature,
                    "pieces_existantes": pieces_existantes,
                    "titre": f"Modifier — {candidature.reference}",
                })

            cd = form.cleaned_data
            modifier_candidature(
                candidature=candidature,
                departement=cd["departement"],
                type_stage=cd["type_stage"],
                type_demande=cd["type_demande"],
                debut_disponibilite=cd["debut_disponibilite"],
                fin_disponibilite=cd["fin_disponibilite"],
                duree_souhaitee=cd["duree_souhaitee"],
                commentaire=cd.get("commentaire", ""),
                offre=cd.get("offre"),
                nouvelles_pieces=nouvelles_pieces,
                pieces_a_supprimer=pieces_a_supprimer,
                utilisateur=request.user,
            )
            messages.success(request, "Candidature mise à jour.")
            return redirect("candidatures:candidature_detail", pk=pk)

        return render(request, self.template_name, {
            "form": form, "formset": formset,
            "candidat": candidature.candidat,
            "candidature": candidature,
            "pieces_existantes": pieces_existantes,
            "titre": f"Modifier — {candidature.reference}",
        })


# ─── Téléchargement protégé ───────────────────────────────────────────────────


_CONTENT_TYPES = {
    ".pdf":  "application/pdf",
    ".jpg":  "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png":  "image/png",
}


class PieceJointeTelechargerView(RoleRequisMixin, View):
    roles = _ROLES_LECTURE

    def get(self, request, pk):
        piece = get_object_or_404(
            PieceJointe.objects.select_related("candidature__departement"), pk=pk
        )
        if _est_responsable(request.user):
            if not request.user.membre or piece.candidature.departement != request.user.membre.departement:
                raise PermissionDenied

        file_path = Path(settings.FICHIERS_PRIVES_ROOT) / piece.fichier.name
        if not file_path.exists():
            raise Http404("Fichier introuvable.")

        nom = piece.nom_original or file_path.name
        ext = Path(nom).suffix.lower()
        content_type = _CONTENT_TYPES.get(ext, "application/octet-stream")

        # ?inline=1 → affichage dans le navigateur (PDF viewer, image)
        # Sans filename + sans as_attachment : pas de Content-Disposition → le navigateur affiche
        if request.GET.get("inline") == "1":
            return FileResponse(open(file_path, "rb"), content_type=content_type)

        # Téléchargement forcé
        return FileResponse(
            open(file_path, "rb"),
            content_type=content_type,
            as_attachment=True,
            filename=nom,
        )


# ─── Candidats à informer ─────────────────────────────────────────────────────


class CandidatsInformerListView(RoleRequisMixin, ListView):
    roles = ["Secrétaire"]
    model = Candidature
    template_name = "candidatures/candidats_informer.html"
    context_object_name = "candidatures"
    paginate_by = 20

    def get_queryset(self):
        return (
            Candidature.objects.filter(
                candidat_informe=False,
                statut__in=[StatutCandidature.ACCORDEE, StatutCandidature.REFUSEE],
            )
            .select_related("candidat", "departement", "type_stage")
            .order_by("-date_depot")
        )


class CandidatureMarquerInformeView(RoleRequisMixin, View):
    roles = ["Secrétaire"]

    def post(self, request, pk):
        candidature = get_object_or_404(Candidature, pk=pk)
        marquer_informe(candidature, request.user)
        messages.success(request, f"Candidat {candidature.candidat} marqué comme informé.")
        next_url = request.POST.get("next", "")
        return redirect(next_url or "candidatures:candidats_informer")
