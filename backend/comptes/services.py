from django.contrib.auth.models import Group, Permission
from django.db import transaction

from .models import ProfilRole
from .permissions import CODES_DROITS_CONSULTATION, ROLES_SYSTEME


class RoleInterdit(Exception):
    pass


def _verifier_nom(nom, groupe_existant=None):
    nom = nom.strip()
    if not nom:
        raise RoleInterdit("Le nom du rôle est obligatoire.")
    if nom.casefold() in {r.casefold() for r in ROLES_SYSTEME}:
        raise RoleInterdit(f"« {nom} » est un rôle de base : choisissez un autre nom.")
    autres = Group.objects.filter(name__iexact=nom)
    if groupe_existant is not None:
        autres = autres.exclude(pk=groupe_existant.pk)
    if autres.exists():
        raise RoleInterdit(f"Un rôle nommé « {nom} » existe déjà.")
    return nom


def _permissions_consultation(codes):
    """RG-U9 : seuls les droits de la liste blanche ; tout autre code est refusé."""
    codes = set(codes)
    interdits = codes - CODES_DROITS_CONSULTATION
    if interdits:
        raise RoleInterdit(
            "Droit non autorisé pour un rôle de consultation : " + ", ".join(sorted(interdits)) + "."
        )
    permissions = []
    for code in sorted(codes):
        app_label, codename = code.split(".")
        permissions.append(Permission.objects.get(content_type__app_label=app_label, codename=codename))
    return permissions


def _profil_consultation(groupe):
    profil = getattr(groupe, "profil", None)
    if profil is None or profil.est_systeme:
        raise RoleInterdit("Les rôles de base ne se modifient pas depuis cet écran.")
    return profil


@transaction.atomic
def creer_role_consultation(nom, description, codes):
    nom = _verifier_nom(nom)
    permissions = _permissions_consultation(codes)
    groupe = Group.objects.create(name=nom)
    ProfilRole.objects.create(groupe=groupe, description=description.strip(), actif=True, est_systeme=False)
    groupe.permissions.set(permissions)
    return groupe


@transaction.atomic
def modifier_role_consultation(groupe, nom, description, codes):
    groupe = Group.objects.select_for_update().get(pk=groupe.pk)
    profil = _profil_consultation(groupe)
    nom = _verifier_nom(nom, groupe_existant=groupe)
    permissions = _permissions_consultation(codes)

    groupe.name = nom
    groupe.save(update_fields=["name"])
    profil.description = description.strip()
    profil.save(update_fields=["description"])
    groupe.permissions.set(permissions)
    return groupe


@transaction.atomic
def basculer_role_consultation(groupe):
    """Active ou désactive ; désactivation refusée tant qu'un utilisateur actif a ce rôle (RG-U11)."""
    groupe = Group.objects.select_for_update().get(pk=groupe.pk)
    profil = _profil_consultation(groupe)
    if profil.actif:
        nb = groupe.user_set.filter(is_active=True).count()
        if nb:
            raise RoleInterdit(
                f"Impossible de désactiver « {groupe.name} » : {nb} utilisateur(s) actif(s) ont ce rôle. "
                "Changez d'abord leur rôle ou désactivez leur compte."
            )
    profil.actif = not profil.actif
    profil.save(update_fields=["actif"])
    return profil
