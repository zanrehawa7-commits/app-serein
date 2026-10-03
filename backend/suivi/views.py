from django.contrib.contenttypes.models import ContentType
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.views import View
from django.views.generic import ListView

from comptes.permissions import ConsultationMixin, a_acces

from .models import Historique, Notification

_ROLES_TOUS = ["Administrateur", "Secrétaire", "Responsable"]


class NotificationListView(ConsultationMixin, ListView):
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


class NotificationLireView(ConsultationMixin, View):
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


class NotificationToutLireView(ConsultationMixin, View):
    """Marque toutes les notifications de l'utilisateur comme lues (POST uniquement)."""
    roles = _ROLES_TOUS

    def post(self, request):
        request.user.notifications.filter(lue=False).update(lue=True)
        return redirect("suivi:notification_list")

    def get(self, request):
        return redirect("suivi:notification_list")


# Objets dont l'historique a une page de détail : (vue, rôles de base autorisés, droit de consultation).
_FICHES_HISTORIQUE = {
    ("offres", "besoin"): ("offres:besoin_detail", _ROLES_TOUS, "offres.view_besoin"),
    ("offres", "offre"): ("offres:offre_detail", _ROLES_TOUS, "offres.view_offre"),
    ("candidatures", "candidature"): ("candidatures:candidature_detail", _ROLES_TOUS, "candidatures.view_candidature"),
    ("stages", "stage"): ("stages:stage_detail", _ROLES_TOUS, "stages.view_stage"),
}


class HistoriqueListView(ConsultationMixin, ListView):
    """
    RG-U12 : journal des actions, en lecture seule — Administrateur et rôles de consultation
    ayant view_historique. Un lien vers l'objet n'apparaît que si l'utilisateur peut l'ouvrir.
    """
    roles = ["Administrateur"]
    permission_consultation = "suivi.view_historique"
    template_name = "suivi/historique_list.html"
    context_object_name = "historiques"
    paginate_by = 20

    def get_queryset(self):
        qs = Historique.objects.select_related("content_type", "utilisateur").order_by("-date_action", "-pk")
        type_objet = self.request.GET.get("type", "")
        if type_objet:
            app_label, _, model = type_objet.partition(".")
            qs = qs.filter(content_type__app_label=app_label, content_type__model=model)
        du = parse_date(self.request.GET.get("du", "") or "")
        au = parse_date(self.request.GET.get("au", "") or "")
        if du:
            qs = qs.filter(date_action__date__gte=du)
        if au:
            qs = qs.filter(date_action__date__lte=au)
        return qs.prefetch_related("objet")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        accessibles = {
            cle: url for cle, (url, roles, droit) in _FICHES_HISTORIQUE.items()
            if a_acces(self.request.user, roles, droit)
        }
        for h in ctx["historiques"]:
            url = accessibles.get((h.content_type.app_label, h.content_type.model))
            h.lien = reverse(url, args=[h.object_id]) if url and h.objet is not None else ""
            modele = h.content_type.model_class()
            h.type_libelle = modele._meta.verbose_name if modele else h.content_type.model
        ctx["types_objet"] = [
            (f"{app}.{model}", ContentType.objects.get_by_natural_key(app, model).model_class()._meta.verbose_name)
            for app, model in _FICHES_HISTORIQUE
        ]
        params = self.request.GET.copy()
        params.pop("page", None)
        ctx["params_paginateur"] = params.urlencode()
        ctx["filtres"] = {cle: self.request.GET.get(cle, "") for cle in ("type", "du", "au")}
        return ctx
