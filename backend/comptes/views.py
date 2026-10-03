from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView, TemplateView

from commun.mixins import ListeMixin
from .forms import (
    FormulaireConnexion,
    ReinitMotDePasseForm,
    RoleConsultationForm,
    UtilisateurCreerForm,
    UtilisateurModifierForm,
)
from .models import Utilisateur
from .services import (
    RoleInterdit,
    basculer_role_consultation,
    creer_role_consultation,
    modifier_role_consultation,
)
from .permissions import (
    APPS_LECTURE_SEULE_ADMINISTRATEUR,
    ROLES_SYSTEME,
    RolePermMixin,
    RoleRequisMixin,
    _role_utilisateur,
)

_FORM_TPL = "commun/formulaire.html"

# Apps affichées dans F02 — dans cet ordre
APPS_PERMISSIONS = [
    ("comptes", "Comptes & utilisateurs"),
    ("referentiels", "Référentiels"),
    ("offres", "Offres & besoins"),
    ("candidatures", "Candidatures"),
    ("stages", "Stages"),
    ("suivi", "Suivi & notifications"),
]
ACTIONS_ORDRE = [
    ("view", "Voir"),
    ("add", "Ajouter"),
    ("change", "Modifier"),
    ("delete", "Supprimer"),
]


# ─── Authentification ─────────────────────────────────────────────────────────

@login_not_required
class ConnexionView(auth_views.LoginView):
    form_class = FormulaireConnexion
    template_name = "registration/login.html"

    def get_success_url(self):
        role = _role_utilisateur(self.request.user)
        destinations = {
            "Administrateur": reverse_lazy("comptes:tableau_bord_admin"),
            "Secrétaire": reverse_lazy("comptes:tableau_bord_secretaire"),
            "Responsable": reverse_lazy("comptes:tableau_bord_responsable"),
        }
        return destinations.get(role, reverse_lazy("comptes:tableau_bord_admin"))


class DeconnexionView(auth_views.LogoutView):
    next_page = "comptes:connexion"


class ChangerMotDePasseView(auth_views.PasswordChangeView):
    template_name = "registration/password_change.html"
    success_url = reverse_lazy("comptes:password_change_done")


class PasswordChangeDoneView(auth_views.PasswordChangeDoneView):
    template_name = "registration/password_change_done.html"


def tableau_de_bord(request):
    role = _role_utilisateur(request.user)
    destinations = {
        "Administrateur": "comptes:tableau_bord_admin",
        "Secrétaire": "comptes:tableau_bord_secretaire",
        "Responsable": "comptes:tableau_bord_responsable",
    }
    return redirect(destinations.get(role, "comptes:tableau_bord_admin"))


class TableauBordAdminView(RoleRequisMixin, TemplateView):
    roles = ["Administrateur"]
    template_name = "comptes/tableau_bord_admin.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_superuser:
            return TemplateView.dispatch(self, request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from offres.models import Besoin, Offre, StatutBesoin, StatutOffre
        ctx["nb_besoins_envoyes"] = Besoin.objects.filter(statut=StatutBesoin.ENVOYE).count()
        ctx["nb_offres_ouvertes"] = Offre.objects.filter(statut=StatutOffre.OUVERTE).count()
        ctx["nb_offres_total"] = Offre.objects.count()
        return ctx


class TableauBordSecretaireView(RoleRequisMixin, TemplateView):
    roles = ["Secrétaire"]
    template_name = "comptes/tableau_bord_secretaire.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        from django.utils import timezone
        from offres.models import Besoin, Offre, StatutBesoin, StatutOffre
        from candidatures.models import Candidature, StatutCandidature
        ctx["nb_besoins_en_attente"] = Besoin.objects.filter(statut=StatutBesoin.ENVOYE).count()
        ctx["nb_offres_ouvertes"] = Offre.objects.filter(statut=StatutOffre.OUVERTE).count()
        ctx["nb_offres_brouillon"] = Offre.objects.filter(statut=StatutOffre.BROUILLON).count()
        ctx["besoins_recents"] = Besoin.objects.filter(statut=StatutBesoin.ENVOYE).select_related("departement", "type_stage").order_by("-date_creation")[:5]
        now = timezone.now()
        ctx["nb_candidatures_recues_mois"] = Candidature.objects.filter(
            statut=StatutCandidature.RECUE,
            date_depot__year=now.year,
            date_depot__month=now.month,
        ).count()
        ctx["nb_candidats_informer"] = Candidature.objects.filter(
            candidat_informe=False,
            statut__in=[StatutCandidature.ACCORDEE, StatutCandidature.REFUSEE],
        ).count()
        return ctx


class TableauBordResponsableView(RoleRequisMixin, TemplateView):
    roles = ["Responsable"]
    template_name = "comptes/tableau_bord_responsable.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.user.personnel:
            from offres.models import Besoin, StatutBesoin
            from candidatures.models import Candidature, StatutCandidature
            dept = self.request.user.personnel.departement
            ctx["nb_besoins_envoyes"] = Besoin.objects.filter(departement=dept, statut=StatutBesoin.ENVOYE).count()
            ctx["nb_besoins_pris_en_charge"] = Besoin.objects.filter(departement=dept, statut=StatutBesoin.PRIS_EN_CHARGE).count()
            ctx["besoins_recents"] = Besoin.objects.filter(departement=dept).select_related("type_stage").order_by("-date_creation")[:5]
            base_cand = Candidature.objects.filter(departement=dept)
            ctx["nb_recues"] = base_cand.filter(statut=StatutCandidature.RECUE).count()
            ctx["nb_en_traitement"] = base_cand.filter(statut=StatutCandidature.EN_TRAITEMENT).count()
            ctx["nb_accordees"] = base_cand.filter(statut=StatutCandidature.ACCORDEE).count()
            ctx["nb_refusees"] = base_cand.filter(statut=StatutCandidature.REFUSEE).count()
            ctx["candidatures_recentes"] = (
                base_cand.filter(statut=StatutCandidature.RECUE)
                .select_related("candidat")
                .order_by("-date_depot")[:5]
            )
            import datetime
            from django.utils import timezone
            from stages.models import Stage, StatutStage
            ctx["nb_stages_en_cours"] = Stage.objects.filter(
                candidature__departement=dept, statut=StatutStage.EN_COURS
            ).count()
            seuil = timezone.localdate() - datetime.timedelta(days=7)
            ctx["nb_a_evaluer"] = Stage.objects.filter(
                candidature__departement=dept,
                statut=StatutStage.TERMINE,
                note__isnull=True,
                date_fin_reelle__lte=seuil,
            ).count()
        return ctx


class EnDeveloppementView(TemplateView):
    template_name = "comptes/en_developpement.html"


# ─── F03 — Utilisateurs ───────────────────────────────────────────────────────

class UtilisateurListView(RolePermMixin, ListeMixin, ListView):
    permission_required = "comptes.view_utilisateur"
    model = Utilisateur
    context_object_name = "utilisateurs"
    template_name = "comptes/utilisateur_list.html"
    champs_recherche = ["first_name", "last_name", "email"]
    champ_actif = "is_active"
    ordering = ["last_name", "first_name"]

    def get_queryset(self):
        qs = super().get_queryset()  # ListeMixin gère q, is_active, tri
        role_filtre = self.request.GET.get("role", "")
        if role_filtre:
            qs = qs.filter(groups__name=role_filtre)
        return qs.prefetch_related("groups", "personnel__departement")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["role_filtre"] = self.request.GET.get("role", "")
        ctx["roles_disponibles"] = ["Administrateur", "Secrétaire", "Responsable"]
        return ctx


class UtilisateurCreateView(RolePermMixin, View):
    permission_required = "comptes.add_utilisateur"

    def _get_context(self, request, form):
        """Contexte enrichi quand appelé depuis le flux designer_responsable."""
        from referentiels.models import Personnel
        ctx = {
            "form": form,
            "titre": "Nouvel utilisateur",
            "url_retour": reverse_lazy("comptes:utilisateur_list"),
        }
        personnel_pk = request.GET.get("personnel") or request.POST.get("_personnel_pk")
        if personnel_pk and request.GET.get("designer") == "1":
            try:
                personnel = Personnel.objects.select_related("departement__responsable").get(pk=personnel_pk)
                ctx["designer_mode"] = True
                ctx["personnel_designer"] = personnel
                # Avertissement si un autre responsable existe déjà
                dept = personnel.departement
                if dept and dept.responsable and dept.responsable.pk != personnel.pk:
                    ctx["avertissement_remplacement"] = (
                        f"Le département « {dept.nom} » a déjà pour responsable "
                        f"« {dept.responsable} ». En créant ce compte, vous le remplacerez "
                        f"et son compte sera désactivé."
                    )
            except Personnel.DoesNotExist:
                pass
        return ctx

    def get(self, request):
        initial = {}
        role_pre = request.GET.get("role", "")
        if role_pre:
            initial["role"] = role_pre
        personnel_pk = request.GET.get("personnel")
        if personnel_pk:
            initial["personnel"] = personnel_pk
        form = UtilisateurCreerForm(initial=initial)
        return render(request, "comptes/utilisateur_creer_form.html", self._get_context(request, form))

    def post(self, request):
        form = UtilisateurCreerForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Compte de « {user.get_full_name() or user.email} » créé.")

            # Flux designer_responsable : appeler le service après création du compte
            if request.POST.get("designer") == "1" and user.personnel:
                from referentiels.services import (
                    designer_responsable, ConfirmationRequise, TransitionInterdite,
                )
                try:
                    designer_responsable(user.personnel, request.user, confirmer=True)
                    messages.success(
                        request,
                        f"« {user.personnel} » désigné(e) responsable du département "
                        f"{user.personnel.departement}.",
                    )
                except (ConfirmationRequise, TransitionInterdite) as e:
                    messages.warning(request, f"Compte créé mais désignation échouée : {e}")

            next_url = request.POST.get("next") or request.GET.get("next", "")
            return redirect(next_url or "comptes:utilisateur_list")

        return render(request, "comptes/utilisateur_creer_form.html", self._get_context(request, form))


class UtilisateurUpdateView(RolePermMixin, View):
    permission_required = "comptes.change_utilisateur"

    def _get_user(self, pk):
        return get_object_or_404(Utilisateur, pk=pk)

    def get(self, request, pk):
        utilisateur = self._get_user(pk)
        form = UtilisateurModifierForm(instance=utilisateur)
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": f"Modifier — {utilisateur.get_full_name() or utilisateur.email}",
            "url_retour": reverse_lazy("comptes:utilisateur_list"),
        })

    def post(self, request, pk):
        utilisateur = self._get_user(pk)
        ancien_role = utilisateur.role
        form = UtilisateurModifierForm(request.POST, instance=utilisateur)
        if form.is_valid():
            user = form.save()
            nouveau_role = form.cleaned_data.get("role")
            if ancien_role == "Responsable" and nouveau_role != "Responsable":
                user.personnel = None
                user.save(update_fields=["personnel"])
            messages.success(request, f"Compte de « {user.get_full_name() or user.email} » mis à jour.")
            return redirect("comptes:utilisateur_list")
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": f"Modifier — {utilisateur.get_full_name() or utilisateur.email}",
            "url_retour": reverse_lazy("comptes:utilisateur_list"),
        })


class UtilisateurActiverView(RoleRequisMixin, View):
    """Bascule is_active. Un admin ne peut pas se désactiver lui-même (RG33)."""
    roles = ["Administrateur"]

    def post(self, request, pk):
        utilisateur = get_object_or_404(Utilisateur, pk=pk)
        if utilisateur == request.user:
            messages.error(request, "Vous ne pouvez pas désactiver votre propre compte.")
            return redirect("comptes:utilisateur_list")
        groupe = utilisateur.groups.select_related("profil").first()
        profil = getattr(groupe, "profil", None) if groupe else None
        if not utilisateur.is_active and profil and not profil.actif:
            messages.error(
                request,
                f"Le rôle « {groupe.name} » est désactivé : changez d'abord le rôle de cet utilisateur.",
            )
            return redirect("comptes:utilisateur_list")
        utilisateur.is_active = not utilisateur.is_active
        utilisateur.save(update_fields=["is_active"])
        action = "activé" if utilisateur.is_active else "désactivé"
        messages.success(
            request,
            f"Compte de « {utilisateur.get_full_name() or utilisateur.email} » {action}.",
        )
        return redirect("comptes:utilisateur_list")

    def get(self, request, pk):
        return redirect("comptes:utilisateur_list")


class UtilisateurReinitMdpView(RolePermMixin, View):
    permission_required = "comptes.change_utilisateur"

    def _get_user(self, pk):
        return get_object_or_404(Utilisateur, pk=pk)

    def get(self, request, pk):
        utilisateur = self._get_user(pk)
        form = ReinitMotDePasseForm()
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": f"Réinitialiser le mot de passe — {utilisateur.get_full_name() or utilisateur.email}",
            "url_retour": reverse_lazy("comptes:utilisateur_list"),
        })

    def post(self, request, pk):
        utilisateur = self._get_user(pk)
        form = ReinitMotDePasseForm(request.POST)
        if form.is_valid():
            utilisateur.set_password(form.cleaned_data["nouveau_mdp1"])
            utilisateur.save()
            messages.success(
                request,
                f"Mot de passe de « {utilisateur.get_full_name() or utilisateur.email} » réinitialisé.",
            )
            return redirect("comptes:utilisateur_list")
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": f"Réinitialiser le mot de passe — {utilisateur.get_full_name() or utilisateur.email}",
            "url_retour": reverse_lazy("comptes:utilisateur_list"),
        })


# ─── F02 — Rôles & permissions ────────────────────────────────────────────────

class RolesListView(RoleRequisMixin, TemplateView):
    roles = ["Administrateur"]
    template_name = "comptes/roles_list.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["groupes"] = Group.objects.filter(name__in=ROLES_SYSTEME).prefetch_related("permissions")
        ctx["roles_consultation"] = (
            Group.objects.filter(profil__est_systeme=False)
            .select_related("profil")
            .annotate(nb_utilisateurs=Count("user", filter=Q(user__is_active=True)))
            .order_by("name")
        )
        return ctx


class PermissionsRoleView(RoleRequisMixin, View):
    roles = ["Administrateur"]
    template_name = "comptes/role_permissions.html"

    def _build_structure(self, groupe):
        """Construit la structure de données pour le template."""
        apps_labels = {code: label for code, label in APPS_PERMISSIONS}
        perms_groupe = set(groupe.permissions.values_list("pk", flat=True))

        structure = []
        for app_code, app_label in APPS_PERMISSIONS:
            cts = ContentType.objects.filter(app_label=app_code).order_by("model")
            modeles = []
            for ct in cts:
                model_class = ct.model_class()
                model_label = (
                    model_class._meta.verbose_name.capitalize()
                    if model_class
                    else ct.model.capitalize()
                )
                actions = []
                for action_code, action_label in ACTIONS_ORDRE:
                    codename = f"{action_code}_{ct.model}"
                    perm = Permission.objects.filter(
                        content_type=ct, codename=codename
                    ).first()
                    if perm:
                        est_admin = groupe.name == "Administrateur"
                        est_verrouillee = est_admin and app_code == "comptes"
                        est_interdite = (
                            est_admin
                            and app_code in APPS_LECTURE_SEULE_ADMINISTRATEUR
                            and action_code != "view"
                        )
                        actions.append({
                            "exists": True,
                            "perm": perm,
                            "action_label": action_label,
                            "checked": (perm.pk in perms_groupe or est_verrouillee) and not est_interdite,
                            "disabled": est_verrouillee or est_interdite,
                        })
                    else:
                        actions.append({"exists": False, "action_label": action_label})
                if any(a["exists"] for a in actions):
                    modeles.append({"label": model_label, "actions": actions})
            if modeles:
                structure.append({"app_label": app_label, "modeles": modeles})
        return structure

    def get(self, request, role_nom):
        groupe = get_object_or_404(Group, name=role_nom, name__in=ROLES_SYSTEME)
        structure = self._build_structure(groupe)
        return render(request, self.template_name, {
            "groupe": groupe,
            "structure": structure,
            "roles": ["Administrateur", "Secrétaire", "Responsable"],
            "role_actif": role_nom,
            "actions_ordre": ACTIONS_ORDRE,
        })

    def post(self, request, role_nom):
        groupe = get_object_or_404(Group, name=role_nom, name__in=ROLES_SYSTEME)
        apps_codes = [code for code, _ in APPS_PERMISSIONS]

        selected_ids = set(
            int(pk) for pk in request.POST.getlist("permissions") if pk.isdigit()
        )

        # Garde-fou : les permissions comptes sont toujours conservées pour Administrateur
        if groupe.name == "Administrateur":
            comptes_perm_ids = set(
                Permission.objects.filter(content_type__app_label="comptes")
                .values_list("pk", flat=True)
            )
            selected_ids |= comptes_perm_ids
            selected_ids -= set(
                Permission.objects.filter(content_type__app_label__in=APPS_LECTURE_SEULE_ADMINISTRATEUR)
                .exclude(codename__startswith="view_")
                .values_list("pk", flat=True)
            )

        all_relevant_ids = set(
            Permission.objects.filter(content_type__app_label__in=apps_codes)
            .values_list("pk", flat=True)
        )
        # Conserver les permissions hors périmètre (admin Django, etc.)
        autres_ids = set(groupe.permissions.values_list("pk", flat=True)) - all_relevant_ids
        groupe.permissions.set(autres_ids | (selected_ids & all_relevant_ids))

        messages.success(request, f"Permissions du rôle « {groupe.name} » mises à jour.")
        return redirect("comptes:permissions_role", role_nom=role_nom)


# ─── Lot E — Rôles de consultation (lecture seule) ────────────────────────────

def _groupe_consultation(pk):
    """404 pour un rôle de base : il ne se modifie ni ne se désactive depuis ces écrans (RG-U8)."""
    return get_object_or_404(Group.objects.select_related("profil"), pk=pk, profil__est_systeme=False)


class RoleConsultationCreateView(RoleRequisMixin, View):
    roles = ["Administrateur"]

    def _afficher(self, request, form):
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": "Nouveau rôle de consultation",
            "sous_titre": "Lecture seule : aucune action métier n'est possible avec ce rôle.",
            "url_retour": reverse_lazy("comptes:roles_list"),
        })

    def get(self, request):
        return self._afficher(request, RoleConsultationForm())

    def post(self, request):
        form = RoleConsultationForm(request.POST)
        if not form.is_valid():
            return self._afficher(request, form)
        try:
            groupe = creer_role_consultation(
                form.cleaned_data["nom"], form.cleaned_data["description"], form.cleaned_data["droits"]
            )
        except RoleInterdit as e:
            form.add_error(None, str(e))
            return self._afficher(request, form)
        messages.success(request, f"Rôle de consultation « {groupe.name} » créé.")
        return redirect("comptes:roles_list")


class RoleConsultationModifierView(RoleRequisMixin, View):
    roles = ["Administrateur"]

    def _afficher(self, request, form, groupe):
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": f"Modifier le rôle de consultation — {groupe.name}",
            "sous_titre": "Lecture seule : aucune action métier n'est possible avec ce rôle.",
            "url_retour": reverse_lazy("comptes:roles_list"),
        })

    def get(self, request, pk):
        groupe = _groupe_consultation(pk)
        droits = [
            f"{app}.{code}"
            for app, code in groupe.permissions.values_list("content_type__app_label", "codename")
        ]
        form = RoleConsultationForm(initial={
            "nom": groupe.name, "description": groupe.profil.description, "droits": droits,
        })
        return self._afficher(request, form, groupe)

    def post(self, request, pk):
        groupe = _groupe_consultation(pk)
        form = RoleConsultationForm(request.POST)
        if not form.is_valid():
            return self._afficher(request, form, groupe)
        try:
            modifier_role_consultation(
                groupe, form.cleaned_data["nom"], form.cleaned_data["description"], form.cleaned_data["droits"]
            )
        except RoleInterdit as e:
            form.add_error(None, str(e))
            return self._afficher(request, form, groupe)
        messages.success(request, "Rôle de consultation mis à jour.")
        return redirect("comptes:roles_list")


class RoleConsultationActiverView(RoleRequisMixin, View):
    roles = ["Administrateur"]

    def post(self, request, pk):
        groupe = _groupe_consultation(pk)
        try:
            profil = basculer_role_consultation(groupe)
        except RoleInterdit as e:
            messages.error(request, str(e))
            return redirect("comptes:roles_list")
        etat = "activé" if profil.actif else "désactivé"
        messages.success(request, f"Rôle « {groupe.name} » {etat}.")
        return redirect("comptes:roles_list")

    def get(self, request, pk):
        return redirect("comptes:roles_list")
