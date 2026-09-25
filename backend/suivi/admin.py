from django.contrib import admin
from .models import Historique, Notification


@admin.register(Historique)
class HistoriqueAdmin(admin.ModelAdmin):
    list_display = ["date_action", "content_type", "object_id", "utilisateur", "ancien_statut", "nouveau_statut"]
    list_filter = ["content_type"]
    search_fields = ["utilisateur__email", "ancien_statut", "nouveau_statut", "commentaire"]
    readonly_fields = ["content_type", "object_id", "date_action"]
    date_hierarchy = "date_action"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["destinataire", "message", "lue", "date_creation"]
    list_filter = ["lue"]
    search_fields = ["destinataire__email", "message"]
    readonly_fields = ["date_creation"]
    date_hierarchy = "date_creation"
