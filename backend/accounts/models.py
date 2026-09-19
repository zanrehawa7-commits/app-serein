from django.contrib.auth.models import AbstractUser, Permission
from django.db import models


class Role(models.Model):
    """Rôle dynamique attribué aux utilisateurs."""

    code = models.SlugField(max_length=50, unique=True)
    nom = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(
        Permission,
        blank=True,
        related_name="roles",
    )
    actif = models.BooleanField(default=True)
    systeme = models.BooleanField(
        default=False,
        help_text="Un rôle système ne peut pas être supprimé.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rôle"
        verbose_name_plural = "Rôles"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class User(AbstractUser):
    email = models.EmailField(unique=True)

    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="utilisateurs",
        null=True,
        blank=True,
    )

    membre = models.OneToOneField(
        "referentials.Membre",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="user_account",
        help_text="Obligatoire pour les maîtres de stage",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username", "first_name", "last_name"]

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.get_full_name() or self.email}"

    @property
    def is_admin_role(self):
        return self.role and self.role.code == "admin"

    @property
    def is_supervisor(self):
        return self.role and self.role.code == "maitre_stage"

    @property
    def is_intern(self):
        return self.role and self.role.code == "stagiaire"

    @property
    def departement(self):
        return self.membre.departement if self.membre else None