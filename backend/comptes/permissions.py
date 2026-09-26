from django.contrib.auth.mixins import AccessMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from functools import wraps


ROLES_VALIDES = ["Administrateur", "Secrétaire", "Responsable"]


def _role_utilisateur(user):
    """Renvoie le rôle effectif : groupe Django ou 'Administrateur' pour les superusers."""
    if user.is_superuser:
        return "Administrateur"
    return user.role


class RoleRequisMixin(AccessMixin):
    """Mixin CBV : restreint l'accès aux rôles listés dans `roles`."""
    roles = []

    def dispatch(self, request, *args, **kwargs):
        role = _role_utilisateur(request.user)
        if role not in self.roles:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


def role_requis(*roles):
    """Décorateur FBV : restreint l'accès aux rôles passés en argument."""
    def decorateur(vue):
        @wraps(vue)
        def wrapper(request, *args, **kwargs):
            role = _role_utilisateur(request.user)
            if role not in roles:
                raise PermissionDenied
            return vue(request, *args, **kwargs)
        return wrapper
    return decorateur


class RolePermMixin(RoleRequisMixin, PermissionRequiredMixin):
    """
    Mixin combiné : vérifie le rôle Administrateur ET la permission Django.
    Les superusers bypasse la vérification des permissions.
    Subclasses définissent `permission_required = "app.action_model"`.
    """
    roles = ["Administrateur"]

    def has_permission(self):
        if self.request.user.is_superuser:
            return True
        return super().has_permission()


class DepartementResponsableMixin(AccessMixin):
    """
    Mixin CBV pour les vues Responsable.
    Vérifie que l'objet appartient au département du responsable connecté (RG13).
    Surcharger `get_departement_objet(self)` pour retourner le département de l'objet.
    """

    def dispatch(self, request, *args, **kwargs):
        role = _role_utilisateur(request.user)
        if role != "Responsable":
            return super().dispatch(request, *args, **kwargs)

        if not request.user.membre or not request.user.membre.departement_id:
            from django.contrib import messages
            messages.error(
                request,
                "Votre compte n'est pas rattaché à un département. "
                "Contactez l'administrateur.",
            )
            return redirect("comptes:tableau_bord_responsable")

        return super().dispatch(request, *args, **kwargs)

    def get_departement_objet(self):
        """À surcharger : renvoie le département de l'objet consulté."""
        raise NotImplementedError

    def verifier_departement(self):
        """Lève PermissionDenied si l'objet n'appartient pas au département du responsable."""
        dept_objet = self.get_departement_objet()
        dept_user = self.request.user.membre.departement
        if dept_objet != dept_user:
            raise PermissionDenied
