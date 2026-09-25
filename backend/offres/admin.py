from django.contrib import admin
from .models import Besoin, Offre, Publication


@admin.register(Besoin)
class BesoinAdmin(admin.ModelAdmin):
    list_display = ["departement", "type_stage", "nombre_places", "date_debut", "date_fin", "statut", "date_creation"]
    list_filter = ["statut", "departement", "type_stage"]
    search_fields = ["departement__nom", "profil_recherche"]
    readonly_fields = ["date_creation"]
    date_hierarchy = "date_creation"


class PublicationInline(admin.TabularInline):
    model = Publication
    extra = 0
    fields = ["canal", "url", "date_publication", "description"]
    show_change_link = True


@admin.register(Offre)
class OffreAdmin(admin.ModelAdmin):
    list_display = ["titre", "type_stage", "nombre_places", "date_debut", "date_fin", "statut", "date_creation"]
    list_filter = ["statut", "type_stage"]
    search_fields = ["titre", "description", "profil_recherche"]
    readonly_fields = ["date_creation"]
    date_hierarchy = "date_creation"
    inlines = [PublicationInline]


@admin.register(Publication)
class PublicationAdmin(admin.ModelAdmin):
    list_display = ["offre", "canal", "date_publication", "url"]
    list_filter = ["canal"]
    search_fields = ["offre__titre", "canal__nom"]
