from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_not_required
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from .forms import FormulaireConnexion
from .permissions import RoleRequisMixin, _role_utilisateur


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
    """Dispatch vers le bon tableau de bord selon le rôle."""
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
        # Les superusers sans groupe sont traités comme Administrateur
        if request.user.is_superuser:
            return TemplateView.dispatch(self, request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)


class TableauBordSecretaireView(RoleRequisMixin, TemplateView):
    roles = ["Secrétaire"]
    template_name = "comptes/tableau_bord_secretaire.html"


class TableauBordResponsableView(RoleRequisMixin, TemplateView):
    roles = ["Responsable"]
    template_name = "comptes/tableau_bord_responsable.html"


class EnDeveloppementView(TemplateView):
    template_name = "comptes/en_developpement.html"
