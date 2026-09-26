from comptes.permissions import _role_utilisateur


def contexte_utilisateur(request):
    """Injecte le rôle et le nombre de notifications non lues dans tous les templates."""
    if not request.user.is_authenticated:
        return {"role_utilisateur": None, "nb_notifications": 0}

    role = _role_utilisateur(request.user)

    try:
        nb_notifications = request.user.notifications.filter(lue=False).count()
    except Exception:
        nb_notifications = 0

    return {
        "role_utilisateur": role,
        "nb_notifications": nb_notifications,
    }
