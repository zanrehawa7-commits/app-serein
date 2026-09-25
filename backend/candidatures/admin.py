from django.contrib import admin
from .models import Candidat, Candidature, PieceJointe


class PieceJointeInline(admin.TabularInline):
    model = PieceJointe
    extra = 0
    fields = ["type_piece", "fichier", "date_ajout"]
    readonly_fields = ["date_ajout"]
    show_change_link = True


@admin.register(Candidat)
class CandidatAdmin(admin.ModelAdmin):
    list_display = ["nom", "prenom", "telephone", "email", "niveau_etudes", "filiere", "etablissement"]
    list_filter = ["etablissement"]
    search_fields = ["nom", "prenom", "telephone", "email"]


@admin.register(Candidature)
class CandidatureAdmin(admin.ModelAdmin):
    list_display = [
        "reference", "candidat", "departement", "type_stage", "type_demande",
        "statut", "candidat_informe", "date_depot",
    ]
    list_filter = ["statut", "type_demande", "departement", "type_stage", "candidat_informe"]
    search_fields = ["reference", "candidat__nom", "candidat__prenom", "candidat__telephone"]
    readonly_fields = ["reference", "date_depot"]
    date_hierarchy = "date_depot"
    inlines = [PieceJointeInline]


@admin.register(PieceJointe)
class PieceJointeAdmin(admin.ModelAdmin):
    list_display = ["candidature", "type_piece", "date_ajout"]
    list_filter = ["type_piece"]
    search_fields = ["candidature__reference"]
    readonly_fields = ["date_ajout"]
