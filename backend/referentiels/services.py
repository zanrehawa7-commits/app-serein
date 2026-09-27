from django.contrib import messages

from .models import Departement


def desactiver_membre(membre, request=None):
    """
    Désactive un membre. Refuse si le membre est le responsable actuel de son département.
    Retourne True si désactivé, False si refusé.
    """
    if Departement.objects.filter(responsable=membre).exists():
        if request:
            messages.error(
                request,
                f"Impossible de désactiver « {membre} » : il est responsable de son département. "
                f"Désignez d'abord un autre responsable.",
            )
        return False

    # Nouveau : refuser si maître de stage d'un stage actif (Complément 5)
    from stages.models import Stage, StatutStage
    if Stage.objects.filter(
        maitre_stage=membre,
        statut__in=[StatutStage.A_VENIR, StatutStage.EN_COURS],
    ).exists():
        if request:
            messages.error(
                request,
                f"Impossible de désactiver « {membre} » : changer d'abord le maître de stage.",
            )
        return False

    membre.actif = not membre.actif
    membre.save(update_fields=["actif"])
    if request:
        action = "activé" if membre.actif else "désactivé"
        messages.success(request, f"Membre « {membre} » {action}.")
    return True
