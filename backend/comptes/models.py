from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UtilisateurManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("L'adresse email est obligatoire.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Le superutilisateur doit avoir is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Le superutilisateur doit avoir is_superuser=True.")
        return self.create_user(email, password, **extra_fields)


class Utilisateur(AbstractUser):
    username = None
    email = models.EmailField(unique=True, verbose_name="email")
    telephone = models.CharField(max_length=20, blank=True, verbose_name="téléphone")
    personnel = models.OneToOneField(
        "referentiels.Personnel",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="compte",
        verbose_name="personnel associé",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UtilisateurManager()

    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return self.get_full_name() or self.email

    @property
    def role(self):
        groupe = self.groups.first()
        return groupe.name if groupe else None


class ProfilRole(models.Model):
    """
    Complète un Group Django. Les 3 rôles de base sont « système » (est_systeme) ; les autres
    sont des rôles de consultation, en lecture seule (RG-U8).
    """

    groupe = models.OneToOneField(
        "auth.Group",
        on_delete=models.CASCADE,
        related_name="profil",
        verbose_name="groupe",
    )
    description = models.TextField(blank=True, verbose_name="description")
    actif = models.BooleanField(default=True, verbose_name="actif")
    est_systeme = models.BooleanField(default=False, verbose_name="rôle système")

    class Meta:
        verbose_name = "Profil de rôle"
        verbose_name_plural = "Profils de rôle"
        ordering = ["-est_systeme", "groupe__name"]

    def __str__(self):
        return self.groupe.name
