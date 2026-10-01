from django.contrib import admin
from .models import CanalPublication, Departement, Etablissement, Personnel, TypeStage


class PersonnelInline(admin.TabularInline):
    model = Personnel
    extra = 0
    fields = ["nom", "prenom", "fonction", "telephone", "email", "actif"]
    show_change_link = True


@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    list_display = ["nom", "responsable", "actif"]
    list_filter = ["actif"]
    search_fields = ["nom"]
    inlines = [PersonnelInline]


@admin.register(Personnel)
class PersonnelAdmin(admin.ModelAdmin):
    list_display = ["nom", "prenom", "fonction", "departement", "telephone", "email", "actif"]
    list_filter = ["actif", "departement"]
    search_fields = ["nom", "prenom", "email", "telephone"]


@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    list_display = ["nom", "ville", "contact", "partenaire", "actif"]
    list_filter = ["partenaire", "actif"]
    search_fields = ["nom", "ville"]


@admin.register(TypeStage)
class TypeStageAdmin(admin.ModelAdmin):
    list_display = ["libelle", "remunere", "actif"]
    list_filter = ["remunere", "actif"]
    search_fields = ["libelle"]


@admin.register(CanalPublication)
class CanalPublicationAdmin(admin.ModelAdmin):
    list_display = ["nom", "actif"]
    list_filter = ["actif"]
    search_fields = ["nom"]
