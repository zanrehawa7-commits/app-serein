from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import ProfilRole, Utilisateur


@admin.register(Utilisateur)
class UtilisateurAdmin(BaseUserAdmin):
    list_display = ["email", "first_name", "last_name", "role", "is_active", "is_staff"]
    list_filter = ["is_active", "is_staff", "groups"]
    search_fields = ["email", "first_name", "last_name"]
    ordering = ["last_name", "first_name"]

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Informations personnelles", {"fields": ("first_name", "last_name", "telephone")}),
        ("Rôle et accès", {"fields": ("groups", "personnel", "is_active", "is_staff", "is_superuser")}),
        ("Dates", {"fields": ("last_login", "date_joined"), "classes": ("collapse",)}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "telephone", "groups", "password1", "password2"),
        }),
    )
    readonly_fields = ["last_login", "date_joined"]
    filter_horizontal = ["groups", "user_permissions"]

    def has_delete_permission(self, request, obj=None):
        if obj and obj == request.user:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(ProfilRole)
class ProfilRoleAdmin(admin.ModelAdmin):
    list_display = ["groupe", "est_systeme", "actif"]
    list_filter = ["est_systeme", "actif"]
