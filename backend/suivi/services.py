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


def responsables_ou_administrateurs(departement):
    """
    Destinataires d'une alerte de département : ses Responsables actifs ; à défaut les
    Administrateurs actifs (même repli que la redirection d'une candidature), pour ne pas la perdre.
    """
    from comptes.models import Utilisateur
    responsables = list(Utilisateur.objects.filter(
        groups__name="Responsable", is_active=True, personnel__departement=departement,
    ))
    return responsables or list(Utilisateur.objects.filter(groups__name="Administrateur", is_active=True))
