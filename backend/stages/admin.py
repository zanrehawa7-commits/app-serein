from django.contrib import admin
from .models import Stage


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = [
        "candidature", "maitre_stage", "date_debut", "date_fin_prevue",
        "date_fin_reelle", "statut", "note", "vivier",
    ]
    list_filter = ["statut", "vivier", "maitre_stage__departement"]
    search_fields = [
        "candidature__reference",
        "candidature__candidat__nom",
        "candidature__candidat__prenom",
        "maitre_stage__nom",
    ]
    readonly_fields = ["candidature"]
    date_hierarchy = "date_debut"
