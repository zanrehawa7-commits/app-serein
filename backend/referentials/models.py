from django.db import models


class Departement(models.Model):
    """Département de Serein-GE."""

    nom = models.CharField(max_length=100, unique=True)
    responsable = models.ForeignKey(
        "Membre",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departements_diriges",
        help_text="Le responsable doit être un membre de ce département.",
    )
    description = models.TextField(blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Département"
        verbose_name_plural = "Départements"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Membre(models.Model):
    """Membre d'un département."""

    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    email = models.EmailField(unique=True, blank=True, null=True)
    departement = models.ForeignKey(
        Departement,
        on_delete=models.PROTECT,
        related_name="membres",
    )
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Membre"
        verbose_name_plural = "Membres"
        ordering = ["nom", "prenom"]
        unique_together = [["nom", "prenom", "departement"]]

    def __str__(self):
        return f"{self.prenom} {self.nom} — {self.departement.nom}"

    @property
    def est_responsable(self):
        return self.departements_diriges.exists()


class Etablissement(models.Model):
    """Établissement d'origine des candidats."""

    class Type(models.TextChoices):
        LYCEE = "LYCEE", "Lycée"
        UNIVERSITE = "UNIVERSITE", "Université"
        ECOLE_PRO = "ECOLE_PRO", "École professionnelle"
        AUTRE = "AUTRE", "Autre"

    nom = models.CharField(max_length=200, unique=True)
    ville = models.CharField(max_length=100)
    pays = models.CharField(max_length=100, default="Burkina Faso")
    type = models.CharField(max_length=20, choices=Type.choices)
    partenaire = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Établissement"
        verbose_name_plural = "Établissements"
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} ({self.ville})"


class TypeStage(models.Model):
    """Type de stage."""

    nom = models.CharField(max_length=100, unique=True)
    duree_min_mois = models.PositiveIntegerField(
        help_text="Durée minimale en mois"
    )
    duree_max_mois = models.PositiveIntegerField(
        help_text="Durée maximale en mois"
    )
    remunere = models.BooleanField(
        default=False,
        help_text="Stage rémunéré ?",
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Type de stage"
        verbose_name_plural = "Types de stage"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class CanalDiffusion(models.Model):
    """Canal de diffusion des offres."""

    class Type(models.TextChoices):
        FACEBOOK = "FACEBOOK", "Facebook"
        LINKEDIN = "LINKEDIN", "LinkedIn"
        SITE_WEB = "SITE_WEB", "Site web"
        AUTRE = "AUTRE", "Autre"

    type = models.CharField(max_length=20, choices=Type.choices)
    nom = models.CharField(max_length=100)
    compte = models.CharField(
        max_length=150,
        blank=True,
        help_text="Nom du compte ou de la page",
    )
    url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Canal de diffusion"
        verbose_name_plural = "Canaux de diffusion"
        ordering = ["type", "nom"]

    def __str__(self):
        return f"{self.get_type_display()} — {self.nom}"
