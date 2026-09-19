from django.contrib import admin
from .models import Departement, Membre, Etablissement, TypeStage, CanalDiffusion     
class MembreInline(admin.TabularInline):
    model = Membre
    extra = 1
    fields = ['nom', 'prenom', 'email', 'actif']
    show_change_link = True
@admin.register(Departement)
class DepartementAdmin(admin.ModelAdmin):
    list_display = ['nom', 'responsable', 'nombre_membres', 'actif', "created_at"]
    list_filter = ["actif",]
    search_fields = ["nom",]
    readonly_fields = ["created_at"]
    inlines = [MembreInline]

    def has_add_permission(self, request, obj=None):
        if obj and obj.membres.exists():
            return False
        return super().has_delete_permission(request, obj)
@admin.register(Membre)
class MembreAdmin(admin.ModelAdmin):
    list_display = ["nom", "prenom", "email", "departement", "a_un_compte", "actif"]
    list_filter = ["actif", "departement"]
    search_fields = ["nom", "prenom", "email"]
    readonly_fields = ["created_at"]

@admin.register(Etablissement)
class EtablissementAdmin(admin.ModelAdmin):
    list_display = ["nom", "ville", "pays", "type", "partenaire", "created_at"]
    list_filter = ["type", "partenaire", "pays"]
    search_fields = ["nom", "ville"]
    readonly_fields = ["created_at", "updated_at"]

@admin.register(TypeStage)
class TypeStageAdmin(admin.ModelAdmin):
    list_display = ["nom", "duree_min_mois", "duree_max_mois", "remunere"]
    list_filter = ["remunere",]
    search_fields = ["nom"]
    readonly_fields = ["created_at"]
@admin.register(CanalDiffusion)
class CanalDiffusionAdmin(admin.ModelAdmin):
    list_display = ["nom", "type", "compte"]
    list_filter = ["type",]
    search_fields = ["nom", "compte"]
    readonly_fields = ["created_at"]
