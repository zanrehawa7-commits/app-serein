from django.contrib.contenttypes.models import ContentType

from .models import Historique, Notification


def enregistrer_historique(objet, utilisateur, ancien_statut="", nouveau_statut="", commentaire=""):
    """Enregistre une entrée dans l'historique d'un objet métier (Besoin, Offre, Stage…)."""
    ct = ContentType.objects.get_for_model(objet)
    return Historique.objects.create(
        content_type=ct,
        object_id=objet.pk,
        utilisateur=utilisateur,
        ancien_statut=ancien_statut,
        nouveau_statut=nouveau_statut,
        commentaire=commentaire,
    )


def notifier(destinataires, message, lien=""):
    """Crée une notification pour chaque utilisateur de la liste (bulk)."""
    if not destinataires:
        return
    Notification.objects.bulk_create([
        Notification(destinataire=dest, message=message, lien=lien)
        for dest in destinataires
    ])
