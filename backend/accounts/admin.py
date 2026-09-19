from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Role, User


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Administration des rôles."""

    list_display = ["nom", "code", "actif", "systeme", "created_at"]
    list_filter = ["actif", "systeme"]
    search_fields = ["nom", "code"]
    prepopulated_fields = {"code": ("nom",)}
    filter_horizontal = ["permissions"]
    readonly_fields = ["created_at"]

    def has_delete_permission(self, request, obj=None):
        if obj and obj.systeme:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Administration des utilisateurs."""

    list_display = [
        "email", "username", "first_name", "last_name", "role", "is_active", "date_joined",
    ]
    list_filter = ["role", "is_active", "is_staff"]
    search_fields = ["email", "username", "first_name", "last_name"]
    ordering = ["last_name", "first_name"]

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Informations personnelles", {
            "fields": ("first_name", "last_name"),
        }),
        ("Rôle et accès", {
            "fields": ("role", "membre", "is_active", "is_staff", "is_superuser"),
        }),
        ("Dates", {
            "fields": ("last_login", "date_joined"),
            "classes": ("collapse",),
        }),
    )

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email", "username", "first_name", "last_name", "role", "password1", "password2",
            ),
        }),
    )

    readonly_fields = ["last_login", "date_joined"]

    def has_delete_permission(self, request, obj=None):
        if obj and obj == request.user:
            return False
        return super().has_delete_permission(request, obj)