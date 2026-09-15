from django.contrib import admin

from .models import (
    CanalDiffusion,
    Departement,
    Etablissement,
    Membre,
    TypeStage,
)


@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    list_display = ("nom", "ville", "pays", "type", "partenaire")
    list_filter = ("type", "partenaire", "pays")
    search_fields = ("nom", "ville")


@admin.register(TypeStage)
class TypeStageAdmin(admin.ModelAdmin):
    list_display = ("nom", "duree_min_mois", "duree_max_mois", "remunere")
    list_filter = ("remunere",)
    search_fields = ("nom",)


@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    list_display = ("nom", "responsable", "actif")
    list_filter = ("actif",)
    search_fields = ("nom",)


@admin.register(Membre)
class MembreAdmin(admin.ModelAdmin):
    list_display = ("nom", "prenom", "departement", "actif")
    list_filter = ("actif", "departement")
    search_fields = ("nom", "prenom", "email")


@admin.register(CanalDiffusion)
class CanalDiffusionAdmin(admin.ModelAdmin):
    list_display = ("nom", "type", "compte")
    list_filter = ("type",)
    search_fields = ("nom", "compte")
