from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.
class User(AbstractUser):
    """
    Modele utilisateur personnalisé pour l'application : StageTrack - Serein-ge. 3 roles internes : Administrateur, Maitre de stage, Stagiaire."""
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrateur'
        SUPERVISOR = 'SUPERVISOR', 'Maitre de stage'
        INTERN = 'INTERN', 'Stagiaire'
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.INTERN, help_text="Rôle de l'utilisateur dans l'application",)
    email = models.EmailField(unique=True, help_text="Adresse e-mail de l'utilisateur",)
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = 'Utilisateur'
        verbose_name_plural = 'Utilisateurs'
        ordering = ['last_name', 'first_name']
    def __str__(self):
        return f"{self.get_full_name() or self.email} ({self.get_role_display()})"

    @property
    def is_admin(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_supervisor(self):
        return self.role == self.Role.SUPERVISOR

    @property
    def is_intern(self):
        return self.role == self.Role.INTERN    