from django.conf import settings
from comptes.permissions import _role_utilisateur


def contexte_utilisateur(request):
    """Injecte le rôle et le nombre de notifications non lues dans tous les templates."""
    if not request.user.is_authenticated:
        return {"role_utilisateur": None, "nb_notifications": 0}

    role = _role_utilisateur(request.user)

    try:
        nb_notifications = request.user.notifications.filter(lue=False).count()
        dernieres_notifications = list(
            request.user.notifications.order_by("lue", "-date_creation")[:5]
        )
    except Exception:
        nb_notifications = 0
        dernieres_notifications = []

    nb_a_informer = 0
    if role == "Secrétaire":
        try:
            from candidatures.models import Candidature, StatutCandidature
            nb_a_informer = Candidature.objects.filter(
                candidat_informe=False,
                statut__in=[
                    StatutCandidature.ACCORDEE,
                    StatutCandidature.REFUSEE,
                ],
            ).count() + Candidature.objects.filter(
                candidat_informe=False,
                statut=StatutCandidature.EN_TRAITEMENT,
                date_entretien__isnull=False,
            ).count()
        except Exception:
            nb_a_informer = 0

    return {
        "role_utilisateur": role,
        "nb_notifications": nb_notifications,
        "dernieres_notifications": dernieres_notifications,
        "nb_a_informer": nb_a_informer,
        "APP_NAME": getattr(settings, "APP_NAME", "Stage Track"),
    }
