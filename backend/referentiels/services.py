from django.contrib import messages
from django.db import transaction

from .models import Departement


class TransitionInterdite(Exception):
    pass


class ConfirmationRequise(Exception):
    """Levée quand un autre responsable existe et que confirmer=False."""
    pass


class CreerCompteRequis(Exception):
    """Levée quand le personnel désigné n'a pas encore de compte utilisateur."""
    pass


def desactiver_personnel(personnel, request=None):
    """
    Active/désactive un personnel.
    Refuse si responsable actuel du département ou maître de stage d'un stage en cours.
    """
    if Departement.objects.filter(responsable=personnel).exists():
        if request:
            messages.error(
                request,
                f"Impossible de désactiver « {personnel} » : il est responsable de son département. "
                "Désignez d'abord un autre responsable.",
            )
        return False

    from stages.models import Stage, StatutStage
    if Stage.objects.filter(
        maitre_stage=personnel,
        statut__in=[StatutStage.A_VENIR, StatutStage.EN_COURS],
    ).exists():
        if request:
            messages.error(
                request,
                f"Impossible de désactiver « {personnel} » : changer d'abord le maître de stage.",
            )
        return False

    personnel.actif = not personnel.actif
    personnel.save(update_fields=["actif"])
    if request:
        action = "activé" if personnel.actif else "désactivé"
        messages.success(request, f"Personnel « {personnel} » {action}.")
    return True


def designer_responsable(personnel, utilisateur, confirmer=False):
    """
    Désigne `personnel` comme responsable de son département.

    Ordre strict (corrections applicables) :
    a) vérifications : actif, département renseigné
    b) si le personnel n'a pas de compte → CreerCompteRequis (AUCUN changement en base)
    c) si un autre responsable existe et confirmer=False → ConfirmationRequise (AUCUN changement)
    d) dans une seule transaction atomique :
       - désactiver le compte de l'ancien responsable s'il existe
       - assigner le nouveau responsable
       - historique + notifications Administrateurs
    """
    from suivi.services import enregistrer_historique, notifier
    from comptes.models import Utilisateur

    # a) vérifications
    if not personnel.actif:
        raise TransitionInterdite(
            f"Impossible de désigner « {personnel} » : ce personnel est inactif."
        )
    if personnel.departement is None:
        raise TransitionInterdite(
            f"Impossible de désigner « {personnel} » : ce personnel n'appartient à aucun département."
        )

    # b) vérifier compte AVANT toute modification
    a_compte = hasattr(personnel, "compte") and personnel.compte is not None
    if not a_compte:
        raise CreerCompteRequis(personnel)

    # Rafraîchir le département avec verrouillage optimiste
    dept = Departement.objects.get(pk=personnel.departement_id)
    ancien = dept.responsable

    # c) vérifier remplacement
    if ancien and ancien.pk != personnel.pk and not confirmer:
        raise ConfirmationRequise(ancien)

    # d) transaction atomique
    with transaction.atomic():
        if ancien and ancien.pk != personnel.pk:
            if hasattr(ancien, "compte") and ancien.compte is not None:
                ancien.compte.is_active = False
                ancien.compte.save(update_fields=["is_active"])
                enregistrer_historique(
                    ancien.compte,
                    utilisateur,
                    ancien_statut="actif",
                    nouveau_statut="inactif",
                    commentaire=(
                        f"Désactivé suite au remplacement comme responsable "
                        f"du département {dept.nom}"
                    ),
                )

        dept.responsable = personnel
        dept.save(update_fields=["responsable"])

        enregistrer_historique(
            dept,
            utilisateur,
            ancien_statut=str(ancien) if ancien else "Aucun",
            nouveau_statut=str(personnel),
            commentaire=f"Désignation de {personnel} comme responsable",
        )

        admins = list(
            Utilisateur.objects.filter(groups__name="Administrateur", is_active=True)
        )
        notifier(
            admins,
            f"{personnel} désigné(e) responsable du département {dept.nom}.",
        )
