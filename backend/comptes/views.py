from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import FormView, ListView, TemplateView

from commun.mixins import ListeMixin
from .forms import (
    FormulaireConnexion,
    ReinitMotDePasseForm,
    UtilisateurCreerForm,
    UtilisateurModifierForm,
)
from .models import Utilisateur
from .permissions import RolePermMixin, RoleRequisMixin, _role_utilisateur

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
        from offres.models import Besoin, Offre, StatutBesoin, StatutOffre
        ctx["nb_besoins_en_attente"] = Besoin.objects.filter(statut=StatutBesoin.ENVOYE).count()
        ctx["nb_offres_ouvertes"] = Offre.objects.filter(statut=StatutOffre.OUVERTE).count()
        ctx["nb_offres_brouillon"] = Offre.objects.filter(statut=StatutOffre.BROUILLON).count()
        ctx["besoins_recents"] = Besoin.objects.filter(statut=StatutBesoin.ENVOYE).select_related("departement", "type_stage").order_by("-date_creation")[:5]
        return ctx


class TableauBordResponsableView(RoleRequisMixin, TemplateView):
    roles = ["Responsable"]
    template_name = "comptes/tableau_bord_responsable.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.user.membre:
            from offres.models import Besoin, StatutBesoin
            dept = self.request.user.membre.departement
            ctx["nb_besoins_envoyes"] = Besoin.objects.filter(departement=dept, statut=StatutBesoin.ENVOYE).count()
            ctx["nb_besoins_pris_en_charge"] = Besoin.objects.filter(departement=dept, statut=StatutBesoin.PRIS_EN_CHARGE).count()
            ctx["besoins_recents"] = Besoin.objects.filter(departement=dept).select_related("type_stage").order_by("-date_creation")[:5]
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
        return qs.prefetch_related("groups", "membre__departement")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["role_filtre"] = self.request.GET.get("role", "")
        ctx["roles_disponibles"] = ["Administrateur", "Secrétaire", "Responsable"]
        return ctx


class UtilisateurCreateView(RolePermMixin, View):
    permission_required = "comptes.add_utilisateur"

    def get(self, request):
        form = UtilisateurCreerForm()
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": "Nouvel utilisateur",
            "url_retour": reverse_lazy("comptes:utilisateur_list"),
        })

    def post(self, request):
        form = UtilisateurCreerForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f"Compte de « {user.get_full_name() or user.email} » créé.")
            return redirect("comptes:utilisateur_list")
        return render(request, _FORM_TPL, {
            "form": form,
            "titre": "Nouvel utilisateur",
            "url_retour": reverse_lazy("comptes:utilisateur_list"),
        })


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
                user.membre = None
                user.save(update_fields=["membre"])
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
        ctx["groupes"] = Group.objects.filter(
            name__in=["Administrateur", "Secrétaire", "Responsable"]
        ).prefetch_related("permissions")
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
                        est_verrouillee = (
                            groupe.name == "Administrateur" and app_code == "comptes"
                        )
                        actions.append({
                            "exists": True,
                            "perm": perm,
                            "action_label": action_label,
                            "checked": perm.pk in perms_groupe or est_verrouillee,
                            "disabled": est_verrouillee,
                        })
                    else:
                        actions.append({"exists": False, "action_label": action_label})
                if any(a["exists"] for a in actions):
                    modeles.append({"label": model_label, "actions": actions})
            if modeles:
                structure.append({"app_label": app_label, "modeles": modeles})
        return structure

    def get(self, request, role_nom):
        groupe = get_object_or_404(Group, name=role_nom)
        structure = self._build_structure(groupe)
        return render(request, self.template_name, {
            "groupe": groupe,
            "structure": structure,
            "roles": ["Administrateur", "Secrétaire", "Responsable"],
            "role_actif": role_nom,
            "actions_ordre": ACTIONS_ORDRE,
        })

    def post(self, request, role_nom):
        groupe = get_object_or_404(Group, name=role_nom)
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

        all_relevant_ids = set(
            Permission.objects.filter(content_type__app_label__in=apps_codes)
            .values_list("pk", flat=True)
        )
        # Conserver les permissions hors périmètre (admin Django, etc.)
        autres_ids = set(groupe.permissions.values_list("pk", flat=True)) - all_relevant_ids
        groupe.permissions.set(autres_ids | (selected_ids & all_relevant_ids))

        messages.success(request, f"Permissions du rôle « {groupe.name} » mises à jour.")
        return redirect("comptes:permissions_role", role_nom=role_nom)
