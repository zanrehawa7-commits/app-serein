from django.contrib import messages
from django.db.models import ProtectedError


def supprimer_ou_desactiver(instance, request=None):
    """
    Tente de supprimer `instance`. Si ProtectedError (enregistrement utilisé ailleurs),
    désactive l'instance en passant `actif=False`.
    Retourne 'supprime' ou 'desactive'.
    """
    nom = str(instance)
    try:
        instance.delete()
        if request:
            messages.success(request, f"« {nom} » supprimé avec succès.")
        return "supprime"
    except ProtectedError:
        instance.actif = False
        instance.save(update_fields=["actif"])
        if request:
            messages.warning(
                request,
                f"« {nom} » ne peut pas être supprimé car il est utilisé par d'autres données. "
                f"Il a été désactivé.",
            )
        return "desactive"
