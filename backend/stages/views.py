import csv
import os
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View
from django.utils import timezone
from django.views.generic import ListView

from commun.mixins import ListeMixin
from comptes.permissions import (
    ConsultationMixin,
    RoleRequisMixin,
    _role_utilisateur,
    a_acces,
    est_role_consultation,
)
from suivi.models import Historique

from .forms import (
    ConstituerStageForm,
    EvaluerStageForm,
    InterrompreStageForm,
    ModifierStageForm,
    ReprendreStageForm,
    TerminerStageForm,
)
from .models import Stage, StatutStage
from .services import (
    TransitionInterdite,
    constituer_stage,
    debut_modifiable,
    evaluer_stage,
    interrompre_stage,
    modifier_stage,
    peut_evaluer,
    reprendre_stage,
    terminer_stage,
)

_ROLES_LECTURE = ["Secrétaire", "Administrateur", "Responsable"]


def _get_historique(stage):
    ct = ContentType.objects.get_for_model(stage)
    return Historique.objects.filter(content_type=ct, object_id=stage.pk).select_related("utilisateur")


def _get_departement_utilisateur(user):
    try:
        return user.personnel.departement
    except Exception:
        return None


class StageListView(ConsultationMixin, ListeMixin, ListView):
    model = Stage
    template_name = "stages/stage_list.html"
    roles = _ROLES_LECTURE
    permission_consultation = "stages.view_stage"
    champs_recherche = []

    def get_queryset(self):
        from django.db.models import Q
        qs = Stage.objects.select_related(
            "candidature__candidat",
            "candidature__departement",
            "maitre_stage",
            "candidature__type_stage",
        ).all()

        role = _role_utilisateur(self.request.user)
        if role == "Responsable":
            dept = _get_departement_utilisateur(self.request.user)
            qs = qs.filter(candidature__departement=dept) if dept else qs.none()

        statut = self.request.GET.get("statut")
        if statut and statut in StatutStage.values:
            qs = qs.filter(statut=statut)

        date_debut = self.request.GET.get("date_debut")
        if date_debut:
            qs = qs.filter(date_debut__gte=date_debut)

        date_fin = self.request.GET.get("date_fin")
        if date_fin:
            qs = qs.filter(date_fin_prevue__lte=date_fin)

        type_stage = self.request.GET.get("type_stage")
        if type_stage:
            qs = qs.filter(candidature__type_stage__pk=type_stage)

        dept_filter = self.request.GET.get("departement")
        if dept_filter and (role in ["Secrétaire", "Administrateur"] or est_role_consultation(self.request.user)):
            qs = qs.filter(candidature__departement__pk=dept_filter)

        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(candidature__candidat__nom__icontains=q) |
                Q(candidature__candidat__prenom__icontains=q) |
                Q(candidature__reference__icontains=q)
            )

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from referentiels.models import Departement, TypeStage
        ctx["statut_actuel"] = self.request.GET.get("statut", "")
        ctx["statuts"] = StatutStage.choices
        ctx["types_stage"] = TypeStage.objects.filter(actif=True)
        ctx["role"] = _role_utilisateur(self.request.user)
        if ctx["role"] in ["Secrétaire", "Administrateur"] or est_role_consultation(self.request.user):
            ctx["departements"] = Departement.objects.filter(actif=True).order_by("nom")
        base = self.get_queryset()
        ctx["nb_a_venir"] = base.filter(statut=StatutStage.A_VENIR).count()
        ctx["nb_en_cours"] = base.filter(statut=StatutStage.EN_COURS).count()
        ctx["nb_termines"] = base.filter(statut=StatutStage.TERMINE).count()
        ctx["nb_interrompus"] = base.filter(statut=StatutStage.INTERROMPU).count()
        return ctx


class StageDetailView(ConsultationMixin, View):
    roles = _ROLES_LECTURE
    permission_consultation = "stages.view_stage"

    def get(self, request, pk):
        stage = get_object_or_404(
            Stage.objects.select_related(
                "candidature__candidat__etablissement",
                "candidature__departement",
                "candidature__type_stage",
                "candidature__offre",
                "maitre_stage",
            ),
            pk=pk,
        )
        role = _role_utilisateur(request.user)
        # RG-E7 : Responsable limité à son département, sauf stage au vivier (vivier partagé
        # entre départements, cf. RG-E5/E6) consulté en lecture seule.
        lecture_seule = False
        if role == "Responsable":
            dept = _get_departement_utilisateur(request.user)
            if dept is None or stage.candidature.departement != dept:
                if not stage.vivier:
                    raise PermissionDenied
                lecture_seule = True
        if lecture_seule:
            # RG-E8 : exactement les colonnes du vivier ; rien d'autre n'est chargé ni transmis.
            return render(request, "stages/stage_detail_vivier.html", {"stage": stage, "role": role})
        historiques = _get_historique(stage)
        affectations_maitre = stage.affectations_maitre.select_related(
            "maitre_stage", "affecte_par"
        ).order_by("-date_affectation")
        _peut_eval, _ = peut_evaluer(stage) if stage.statut == StatutStage.TERMINE and role == "Responsable" else (False, None)
        peut_pieces = a_acces(request.user, _ROLES_LECTURE, "candidatures.telecharger_pieces_jointes")
        return render(request, "stages/stage_detail.html", {
            "stage": stage,
            "historiques": historiques,
            "affectations_maitre": affectations_maitre,
            "role": role,
            # RG-U10 : pièces jointes jamais chargées sans le droit ; lien et rapport selon les droits.
            "peut_telecharger_pieces": peut_pieces,
            "pieces": stage.candidature.pieces.order_by("type_piece", "date_ajout") if peut_pieces else None,
            "peut_voir_candidature": a_acces(request.user, _ROLES_LECTURE, "candidatures.view_candidature"),
            "peut_telecharger_rapport": a_acces(
                request.user, ["Responsable", "Administrateur"], "stages.telecharger_rapports"
            ),
            "peut_modifier": (
                role == "Secrétaire" and
                stage.statut in [StatutStage.A_VENIR, StatutStage.EN_COURS]
            ),
            "peut_terminer": role == "Responsable" and stage.statut == StatutStage.EN_COURS,
            "peut_interrompre": (
                role == "Responsable" and
                stage.statut in [StatutStage.A_VENIR, StatutStage.EN_COURS]
            ),
            "peut_evaluer": _peut_eval,
            "peut_reprendre": role == "Responsable" and stage.statut == StatutStage.INTERROMPU,
            "periodes_interruption": stage.periodes_interruption.select_related("interrompu_par", "repris_par"),
        })


class ConstituerStageView(RoleRequisMixin, View):
    roles = ["Secrétaire"]

    def _get_candidature(self, pk):
        from candidatures.models import Candidature, StatutCandidature
        return get_object_or_404(
            Candidature.objects.select_related("departement", "candidat"),
            pk=pk,
            statut=StatutCandidature.ACCORDEE,
        )

    def get(self, request, candidature_pk):
        cand = self._get_candidature(candidature_pk)
        if hasattr(cand, "stage"):
            messages.warning(request, "Cette candidature a déjà un stage constitué.")
            return redirect("stages:stage_detail", pk=cand.stage.pk)

        form = ConstituerStageForm(departement=cand.departement, candidature=cand)
        return render(request, "stages/stage_constituer_form.html", {
            "form": form,
            "candidature": cand,
        })

    def post(self, request, candidature_pk):
        cand = self._get_candidature(candidature_pk)
        if hasattr(cand, "stage"):
            messages.warning(request, "Cette candidature a déjà un stage constitué.")
            return redirect("stages:stage_detail", pk=cand.stage.pk)

        form = ConstituerStageForm(request.POST, departement=cand.departement, candidature=cand)
        if form.is_valid():
            try:
                stage = constituer_stage(
                    candidature=cand,
                    date_debut=form.cleaned_data["date_debut"],
                    date_fin_prevue=form.cleaned_data["date_fin_prevue"],
                    maitre_stage=form.cleaned_data["maitre_stage"],
                    utilisateur=request.user,
                )
                messages.success(request, f"Stage constitué pour {cand.candidat}.")
                return redirect("stages:stage_detail", pk=stage.pk)
            except TransitionInterdite as e:
                messages.error(request, str(e))
                return redirect("candidatures:candidature_detail", pk=candidature_pk)

        return render(request, "stages/stage_constituer_form.html", {
            "form": form,
            "candidature": cand,
        })


class ModifierStageView(RoleRequisMixin, View):
    roles = ["Secrétaire"]

    def _get_stage(self, pk):
        return get_object_or_404(
            Stage.objects.select_related(
                "candidature__departement", "candidature__candidat", "maitre_stage"
            ),
            pk=pk,
        )

    def get(self, request, pk):
        stage = self._get_stage(pk)
        if stage.statut not in [StatutStage.A_VENIR, StatutStage.EN_COURS]:
            messages.error(request, "Ce stage ne peut plus être modifié.")
            return redirect("stages:stage_detail", pk=pk)

        form = ModifierStageForm(
            initial={
                "date_debut": stage.date_debut,
                "date_fin_prevue": stage.date_fin_prevue,
                "maitre_stage": stage.maitre_stage,
            },
            departement=stage.candidature.departement,
            stage=stage,
        )
        return render(request, "stages/stage_modifier_form.html", {
            "form": form,
            "stage": stage,
            "debut_modifiable": debut_modifiable(stage),
        })

    def post(self, request, pk):
        stage = self._get_stage(pk)
        if stage.statut not in [StatutStage.A_VENIR, StatutStage.EN_COURS]:
            messages.error(request, "Ce stage ne peut plus être modifié.")
            return redirect("stages:stage_detail", pk=pk)

        form = ModifierStageForm(
            request.POST,
            departement=stage.candidature.departement,
            stage=stage,
        )
        if form.is_valid():
            try:
                modifier_stage(
                    stage=stage,
                    date_debut=form.cleaned_data.get("date_debut"),
                    date_fin_prevue=form.cleaned_data["date_fin_prevue"],
                    maitre_stage=form.cleaned_data["maitre_stage"],
                    utilisateur=request.user,
                )
                messages.success(request, "Stage modifié avec succès.")
                return redirect("stages:stage_detail", pk=pk)
            except TransitionInterdite as e:
                messages.error(request, str(e))
                return redirect("stages:stage_detail", pk=pk)

        return render(request, "stages/stage_modifier_form.html", {
            "form": form,
            "stage": stage,
            "debut_modifiable": debut_modifiable(stage),
        })


class TerminerStageView(RoleRequisMixin, View):
    roles = ["Responsable"]

    def _get_stage(self, pk, request):
        stage = get_object_or_404(
            Stage.objects.select_related(
                "candidature__departement", "candidature__candidat"
            ),
            pk=pk,
        )
        dept = _get_departement_utilisateur(request.user)
        if dept is None or stage.candidature.departement != dept:
            raise PermissionDenied
        return stage

    def get(self, request, pk):
        stage = self._get_stage(pk, request)
        if stage.statut != StatutStage.EN_COURS:
            messages.error(request, "Ce stage n'est pas en cours.")
            return redirect("stages:stage_detail", pk=pk)
        form = TerminerStageForm(stage=stage)
        return render(request, "stages/stage_terminer_form.html", {"form": form, "stage": stage})

    def post(self, request, pk):
        stage = self._get_stage(pk, request)
        if stage.statut != StatutStage.EN_COURS:
            messages.error(request, "Ce stage n'est pas en cours.")
            return redirect("stages:stage_detail", pk=pk)
        form = TerminerStageForm(request.POST, stage=stage)
        if form.is_valid():
            try:
                terminer_stage(
                    stage=stage,
                    date_fin_reelle=form.cleaned_data["date_fin_reelle"],
                    utilisateur=request.user,
                )
                messages.success(request, "Stage terminé.")
                return redirect("stages:stage_detail", pk=pk)
            except TransitionInterdite as e:
                messages.error(request, str(e))
                return redirect("stages:stage_detail", pk=pk)
        return render(request, "stages/stage_terminer_form.html", {"form": form, "stage": stage})


class InterrompreStageView(RoleRequisMixin, View):
    roles = ["Responsable"]

    def _get_stage(self, pk, request):
        stage = get_object_or_404(
            Stage.objects.select_related(
                "candidature__departement", "candidature__candidat"
            ),
            pk=pk,
        )
        dept = _get_departement_utilisateur(request.user)
        if dept is None or stage.candidature.departement != dept:
            raise PermissionDenied
        return stage

    def get(self, request, pk):
        stage = self._get_stage(pk, request)
        if stage.statut not in [StatutStage.A_VENIR, StatutStage.EN_COURS]:
            messages.error(request, "Ce stage ne peut pas être interrompu.")
            return redirect("stages:stage_detail", pk=pk)
        form = InterrompreStageForm(stage=stage)
        return render(request, "stages/stage_interrompre_form.html", {"form": form, "stage": stage})

    def post(self, request, pk):
        stage = self._get_stage(pk, request)
        if stage.statut not in [StatutStage.A_VENIR, StatutStage.EN_COURS]:
            messages.error(request, "Ce stage ne peut pas être interrompu.")
            return redirect("stages:stage_detail", pk=pk)
        form = InterrompreStageForm(request.POST, stage=stage)
        if form.is_valid():
            try:
                interrompre_stage(
                    stage=stage,
                    date_fin_reelle=form.cleaned_data["date_fin_reelle"],
                    motif=form.cleaned_data["motif_interruption"],
                    utilisateur=request.user,
                )
                messages.success(request, "Stage interrompu.")
                return redirect("stages:stage_detail", pk=pk)
            except TransitionInterdite as e:
                messages.error(request, str(e))
                return redirect("stages:stage_detail", pk=pk)
        return render(request, "stages/stage_interrompre_form.html", {"form": form, "stage": stage})


class ReprendreStageView(RoleRequisMixin, View):
    """RG-S12 : reprise d'un stage interrompu, par le Responsable du département."""
    roles = ["Responsable"]

    def _get_stage(self, pk, request):
        stage = get_object_or_404(
            Stage.objects.select_related("candidature__departement", "candidature__candidat"),
            pk=pk,
        )
        dept = _get_departement_utilisateur(request.user)
        if dept is None or stage.candidature.departement != dept:
            raise PermissionDenied
        return stage

    def _formulaire_ou_redirection(self, request, stage, data=None):
        periode = stage.periode_interruption_ouverte()
        if stage.statut != StatutStage.INTERROMPU or periode is None:
            messages.error(request, "Seul un stage interrompu peut être repris.")
            return None, None
        return ReprendreStageForm(data, stage=stage, periode=periode), periode

    def _afficher(self, request, stage, form, periode):
        return render(request, "stages/stage_reprendre_form.html", {
            "form": form, "stage": stage, "periode": periode,
        })

    def get(self, request, pk):
        stage = self._get_stage(pk, request)
        form, periode = self._formulaire_ou_redirection(request, stage)
        if form is None:
            return redirect("stages:stage_detail", pk=pk)
        return self._afficher(request, stage, form, periode)

    def post(self, request, pk):
        stage = self._get_stage(pk, request)
        form, periode = self._formulaire_ou_redirection(request, stage, request.POST)
        if form is None:
            return redirect("stages:stage_detail", pk=pk)
        if not form.is_valid():
            return self._afficher(request, stage, form, periode)
        try:
            reprendre_stage(
                stage=stage,
                date_reprise=form.cleaned_data["date_reprise"],
                date_fin_prevue=form.cleaned_data["date_fin_prevue"],
                motif=form.cleaned_data["motif_reprise"],
                utilisateur=request.user,
            )
        except TransitionInterdite as e:
            messages.error(request, str(e))
            return redirect("stages:stage_detail", pk=pk)
        messages.success(request, "Stage repris.")
        if form.cleaned_data["date_fin_prevue"] < timezone.localdate():
            messages.info(
                request,
                "La fin prévue est déjà dépassée : pensez à terminer ce stage, rien ne se fait automatiquement.",
            )
        return redirect("stages:stage_detail", pk=pk)


class EvaluerStageView(RoleRequisMixin, View):
    roles = ["Responsable"]

    def _get_stage(self, pk, request):
        stage = get_object_or_404(
            Stage.objects.select_related(
                "candidature__departement", "candidature__candidat"
            ),
            pk=pk,
            statut=StatutStage.TERMINE,
        )
        dept = _get_departement_utilisateur(request.user)
        if dept is None or stage.candidature.departement != dept:
            raise PermissionDenied
        return stage

    def get(self, request, pk):
        stage = self._get_stage(pk, request)
        peut, date_verrou = peut_evaluer(stage)
        if not peut:
            messages.error(
                request,
                "L'évaluation de ce stage est verrouillée"
                + (f" depuis le {date_verrou.strftime('%d/%m/%Y')}." if date_verrou else "."),
            )
            return redirect("stages:stage_detail", pk=pk)
        initial = {}
        if stage.note is not None:
            initial["note"] = stage.note
            initial["vivier"] = stage.vivier
        form = EvaluerStageForm(initial=initial)
        return render(request, "stages/stage_evaluer_form.html", {
            "form": form,
            "stage": stage,
            "date_verrou": date_verrou,
        })

    def post(self, request, pk):
        stage = self._get_stage(pk, request)
        peut, date_verrou = peut_evaluer(stage)
        if not peut:
            messages.error(request, "L'évaluation est verrouillée.")
            return redirect("stages:stage_detail", pk=pk)
        form = EvaluerStageForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                evaluer_stage(
                    stage=stage,
                    note=form.cleaned_data["note"],
                    vivier=form.cleaned_data["vivier"],
                    rapport_file=form.cleaned_data.get("rapport"),
                    utilisateur=request.user,
                )
                messages.success(request, "Évaluation enregistrée.")
                return redirect("stages:stage_detail", pk=pk)
            except TransitionInterdite as e:
                messages.error(request, str(e))
                return redirect("stages:stage_detail", pk=pk)
        return render(request, "stages/stage_evaluer_form.html", {
            "form": form,
            "stage": stage,
            "date_verrou": date_verrou,
        })


class StagesAEvaluerListView(RoleRequisMixin, View):
    roles = ["Responsable", "Administrateur"]

    def get(self, request):
        import datetime
        from django.utils import timezone
        today = timezone.localdate()
        seuil = today - datetime.timedelta(days=7)

        qs = Stage.objects.filter(
            statut=StatutStage.TERMINE,
            note__isnull=True,
            date_fin_reelle__lte=seuil,
        ).select_related(
            "candidature__candidat",
            "candidature__departement",
            "maitre_stage",
        )

        role = _role_utilisateur(request.user)
        if role == "Responsable":
            dept = _get_departement_utilisateur(request.user)
            qs = qs.filter(candidature__departement=dept) if dept else qs.none()

        return render(request, "stages/stages_a_evaluer.html", {
            "stages": qs.order_by("date_fin_reelle"),
            "role": role,
        })


class VivierListView(ConsultationMixin, ListView):
    model = Stage
    template_name = "stages/vivier.html"
    roles = ["Responsable", "Administrateur"]
    permission_consultation = "stages.consulter_vivier"
    paginate_by = 20

    def get_queryset(self):
        return Stage.objects.filter(vivier=True).select_related(
            "candidature__candidat",
            "candidature__candidat__etablissement",
            "candidature__departement",
            "candidature__type_stage",
            "maitre_stage",
        ).order_by("-note", "candidature__candidat__nom")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["role"] = _role_utilisateur(self.request.user)
        ctx["afficher_departement"] = ctx["role"] == "Administrateur" or est_role_consultation(self.request.user)
        ctx["peut_exporter"] = a_acces(self.request.user, self.roles, "stages.exporter_vivier")
        ctx["peut_voir_stage"] = a_acces(self.request.user, _ROLES_LECTURE, "stages.view_stage")
        ctx["peut_telecharger_rapport"] = a_acces(self.request.user, self.roles, "stages.telecharger_rapports")
        return ctx


class VivierExportCsvView(ConsultationMixin, View):
    roles = ["Responsable", "Administrateur"]
    permission_consultation = "stages.exporter_vivier"

    def get(self, request):
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = 'attachment; filename="vivier.csv"'

        writer = csv.writer(response)
        writer.writerow([
            "Candidat", "Téléphone", "Email", "Niveau d'études", "Filière",
            "Établissement", "Type de stage", "Département",
            "Date début", "Date fin", "Note /20", "Maître de stage",
        ])

        stages = Stage.objects.filter(vivier=True).select_related(
            "candidature__candidat",
            "candidature__candidat__etablissement",
            "candidature__departement",
            "candidature__type_stage",
            "maitre_stage",
        ).order_by("-note", "candidature__candidat__nom")

        for s in stages:
            c = s.candidature.candidat
            writer.writerow([
                str(c),
                c.telephone,
                c.email or "",
                c.get_niveau_etudes_display() or "",
                c.filiere or "",
                str(c.etablissement or c.etablissement_autre or ""),
                s.candidature.type_stage.libelle,
                s.candidature.departement.nom,
                s.date_debut.strftime("%d/%m/%Y"),
                (s.date_fin_reelle or s.date_fin_prevue).strftime("%d/%m/%Y"),
                str(s.note),
                str(s.maitre_stage),
            ])

        return response


class RapportTelechargerView(ConsultationMixin, View):
    roles = ["Responsable", "Administrateur"]
    permission_consultation = "stages.telecharger_rapports"

    def get(self, request, pk):
        stage = get_object_or_404(
            Stage.objects.select_related("candidature__departement"),
            pk=pk,
        )

        if not stage.rapport:
            raise Http404("Aucun rapport pour ce stage.")

        # RG-E5 : rapport d'un autre département lisible uniquement si le stage est au vivier.
        role = _role_utilisateur(request.user)
        if role == "Responsable":
            dept = _get_departement_utilisateur(request.user)
            if dept is None or stage.candidature.departement != dept:
                if not stage.vivier:
                    raise PermissionDenied

        try:
            path = stage.rapport.path
        except Exception:
            raise Http404("Fichier introuvable.")

        if not os.path.exists(path):
            raise Http404("Fichier introuvable.")

        return FileResponse(
            open(path, "rb"),
            as_attachment=True,
            filename=os.path.basename(path),
        )
