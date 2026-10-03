from django.shortcuts import get_object_or_404, redirect
from django.views import View
from django.views.generic import ListView

from comptes.permissions import RoleRequisMixin

from .models import Notification

_ROLES_TOUS = ["Administrateur", "Secrétaire", "Responsable"]


class NotificationListView(RoleRequisMixin, ListView):
    roles = _ROLES_TOUS
    template_name = "suivi/notifications.html"
    context_object_name = "notifications"
    paginate_by = 20

    def get_queryset(self):
        return self.request.user.notifications.order_by("lue", "-date_creation")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["params_paginateur"] = params.urlencode()
        return ctx


class NotificationLireView(RoleRequisMixin, View):
    """Marque une notification comme lue et redirige vers son lien (GET ou POST)."""
    roles = _ROLES_TOUS

    def _marquer_et_rediriger(self, request, pk):
        notif = get_object_or_404(Notification, pk=pk, destinataire=request.user)
        if not notif.lue:
            notif.lue = True
            notif.save(update_fields=["lue"])
        if notif.lien:
            return redirect(notif.lien)
        return redirect("suivi:notification_list")

    # Exception assumée à « actions en POST uniquement » (RG-N4) : le menu des notifications
    # utilise de simples liens. Marquer comme lue n'altère aucune donnée métier et ne
    # concerne que les notifications de l'utilisateur connecté.
    def get(self, request, pk):
        return self._marquer_et_rediriger(request, pk)

    def post(self, request, pk):
        return self._marquer_et_rediriger(request, pk)


class NotificationToutLireView(RoleRequisMixin, View):
    """Marque toutes les notifications de l'utilisateur comme lues (POST uniquement)."""
    roles = _ROLES_TOUS

    def post(self, request):
        request.user.notifications.filter(lue=False).update(lue=True)
        return redirect("suivi:notification_list")

    def get(self, request):
        return redirect("suivi:notification_list")
