from django.contrib.auth.mixins import AccessMixin, PermissionRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from functools import wraps


ROLES_VALIDES = ["Administrateur", "Secrétaire", "Responsable"]

# L'Administrateur consulte les données métier sans jamais les modifier (CLAUDE.md §4).
# Source unique pour init_donnees et l'écran F02 : sans elle, les droits complets
# revenaient à chaque init_donnees ou via les cases à cocher.
APPS_LECTURE_SEULE_ADMINISTRATEUR = ("offres", "candidatures", "stages", "suivi")

# Rôles de base : ni supprimables, ni renommables, seuls à pouvoir agir (RG-U8).
ROLES_SYSTEME = tuple(ROLES_VALIDES)

# RG-U9 : seuls droits attribuables à un rôle de consultation (liste blanche, vérifiée côté
# serveur). Chacun correspond à un écran ; jamais de add_/change_/delete_.
DROITS_CONSULTATION = [
    ("Offres & besoins", [
        ("offres.view_besoin", "Consulter les besoins"),
        ("offres.view_offre", "Consulter les offres"),
        ("offres.view_publication", "Consulter les publications des offres"),
    ]),
    ("Candidatures", [
        ("candidatures.view_candidature", "Consulter les candidatures"),
        ("candidatures.view_candidat", "Consulter les fiches candidats"),
        ("candidatures.telecharger_pieces_jointes", "Télécharger les pièces jointes (données personnelles)"),
    ]),
    ("Stages", [
        ("stages.view_stage", "Consulter les stages"),
        ("stages.consulter_vivier", "Consulter le vivier"),
        ("stages.exporter_vivier", "Exporter le vivier (CSV)"),
        ("stages.telecharger_rapports", "Télécharger les rapports de stage"),
    ]),
    ("Suivi", [
        ("suivi.view_historique", "Consulter l'historique"),
    ]),
]
CODES_DROITS_CONSULTATION = {code for _, droits in DROITS_CONSULTATION for code, _ in droits}


def _role_utilisateur(user):
    """Renvoie le rôle effectif : groupe Django ou 'Administrateur' pour les superusers."""
    if user.is_superuser:
        return "Administrateur"
    return user.role


def est_role_consultation(user):
    """Rôle de consultation ACTIF (un rôle désactivé n'ouvre aucun accès)."""
    if not user.is_authenticated or user.is_superuser:
        return False
    groupe = user.groups.select_related("profil").first()
    profil = getattr(groupe, "profil", None) if groupe else None
    return bool(profil and profil.actif and not profil.est_systeme)


def a_acces(user, roles, permission=None):
    """
    Règle commune aux vues et aux templates : rôle de base autorisé (comportement inchangé),
    ou rôle de consultation actif possédant `permission` (None = tout rôle de consultation actif).
    """
    if _role_utilisateur(user) in roles:
        return True
    if not est_role_consultation(user):
        return False
    return permission is None or user.has_perm(permission)


class RoleRequisMixin(AccessMixin):
    """Mixin CBV : restreint l'accès aux rôles listés dans `roles`."""
    roles = []

    def dispatch(self, request, *args, **kwargs):
        role = _role_utilisateur(request.user)
        if role not in self.roles:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)


class ConsultationMixin(AccessMixin):
    """
    Vues de LISTE, DÉTAIL et TÉLÉCHARGEMENT uniquement (RG-U10) : rôles de base `roles`
    (comportement inchangé) ou rôle de consultation actif ayant `permission_consultation`
    (None = tout rôle de consultation actif). Ne jamais l'utiliser sur une vue d'action.
    """
    roles = []
    permission_consultation = None

    def dispatch(self, request, *args, **kwargs):
        if not a_acces(request.user, self.roles, self.permission_consultation):
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

        if not request.user.personnel or not request.user.personnel.departement_id:
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
        dept_user = self.request.user.personnel.departement
        if dept_objet != dept_user:
            raise PermissionDenied
