from django.core.exceptions import ValidationError
from django.db import models


class Departement(models.Model):
    nom = models.CharField(max_length=100, unique=True, verbose_name="nom")
    description = models.TextField(blank=True, verbose_name="description")
    actif = models.BooleanField(default=True, verbose_name="actif")
    responsable = models.OneToOneField(
        "Personnel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="departement_dirige",
        verbose_name="responsable",
    )

    class Meta:
        verbose_name = "Département"
        verbose_name_plural = "Départements"
        ordering = ["nom"]

    def __str__(self):
        return self.nom


class Personnel(models.Model):
    nom = models.CharField(max_length=100, verbose_name="nom")
    prenom = models.CharField(max_length=100, verbose_name="prénom")
    fonction = models.CharField(max_length=150, blank=True, verbose_name="fonction")
    telephone = models.CharField(max_length=20, blank=True, verbose_name="téléphone")
    email = models.EmailField(unique=True, null=True, blank=True, verbose_name="email")
    actif = models.BooleanField(default=True, verbose_name="actif")
    departement = models.ForeignKey(
        Departement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="personnels",
        verbose_name="département",
    )

    class Meta:
        verbose_name = "Personnel"
        verbose_name_plural = "Personnels"
        ordering = ["nom", "prenom"]

    def __str__(self):
        return f"{self.prenom} {self.nom}"

    def clean(self):
        # Si ce personnel est responsable d'un département, il doit y appartenir.
        try:
            dept_dirige = self.departement_dirige
        except Departement.DoesNotExist:
            dept_dirige = None

        if dept_dirige:
            if self.departement is None:
                raise ValidationError(
                    "Le responsable d'un département doit être rattaché à ce département."
                )
            if dept_dirige.pk != self.departement_id:
                raise ValidationError(
                    "Le responsable d'un département doit être membre de ce département."
                )


class Etablissement(models.Model):
    nom = models.CharField(max_length=200, unique=True, verbose_name="nom")
    ville = models.CharField(max_length=100, verbose_name="ville")
    contact = models.CharField(max_length=150, blank=True, verbose_name="contact")
    partenaire = models.BooleanField(default=False, verbose_name="partenaire")
    actif = models.BooleanField(default=True, verbose_name="actif")

    class Meta:
        verbose_name = "Établissement"
        verbose_name_plural = "Établissements"
        ordering = ["nom"]

    def __str__(self):
        return f"{self.nom} ({self.ville})"


class TypeStage(models.Model):
    libelle = models.CharField(max_length=100, unique=True, verbose_name="libellé")
    description = models.TextField(blank=True, verbose_name="description")
    remunere = models.BooleanField(default=False, verbose_name="rémunéré")
    actif = models.BooleanField(default=True, verbose_name="actif")

    class Meta:
        verbose_name = "Type de stage"
        verbose_name_plural = "Types de stage"
        ordering = ["libelle"]

    def __str__(self):
        return self.libelle


class CanalPublication(models.Model):
    nom = models.CharField(max_length=100, unique=True, verbose_name="nom")
    description = models.TextField(blank=True, verbose_name="description")
    actif = models.BooleanField(default=True, verbose_name="actif")

    class Meta:
        verbose_name = "Canal de publication"
        verbose_name_plural = "Canaux de publication"
        ordering = ["nom"]

    def __str__(self):
        return self.nom
