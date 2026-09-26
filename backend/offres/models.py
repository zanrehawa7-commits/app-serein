from django.core.exceptions import ValidationError
from django.db import models


class StatutBesoin(models.TextChoices):
    ENVOYE = "ENVOYE", "Envoyé"
    PRIS_EN_CHARGE = "PRIS_EN_CHARGE", "Pris en charge"
    CLOTURE = "CLOTURE", "Clôturé"
    ANNULE = "ANNULE", "Annulé"


class StatutOffre(models.TextChoices):
    BROUILLON = "BROUILLON", "Brouillon"
    OUVERTE = "OUVERTE", "Ouverte"
    SUSPENDUE = "SUSPENDUE", "Suspendue"
    FERMEE = "FERMEE", "Fermée"


class Besoin(models.Model):
    departement = models.ForeignKey(
        "referentiels.Departement",
        on_delete=models.PROTECT,
        related_name="besoins",
        verbose_name="département",
    )
    type_stage = models.ForeignKey(
        "referentiels.TypeStage",
        on_delete=models.PROTECT,
        related_name="besoins",
        verbose_name="type de stage",
    )
    date_debut = models.DateField(verbose_name="date de début")
    date_fin = models.DateField(verbose_name="date de fin")
    profil_recherche = models.TextField(verbose_name="profil recherché")
    nombre_places = models.PositiveSmallIntegerField(verbose_name="nombre de places")
    statut = models.CharField(
        max_length=20,
        choices=StatutBesoin.choices,
        default=StatutBesoin.ENVOYE,
        verbose_name="statut",
    )
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="date de création")

    class Meta:
        verbose_name = "Besoin"
        verbose_name_plural = "Besoins"
        ordering = ["-date_creation"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(nombre_places__gte=1),
                name="besoin_nombre_places_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(date_fin__gt=models.F("date_debut")),
                name="besoin_date_fin_gt_date_debut",
            ),
        ]

    def __str__(self):
        return f"Besoin {self.departement} — {self.type_stage} ({self.date_debut})"

    def clean(self):
        if self.date_debut and self.date_fin and self.date_fin <= self.date_debut:
            raise ValidationError({"date_fin": "La date de fin doit être postérieure à la date de début."})
        if self.nombre_places is not None and self.nombre_places < 1:
            raise ValidationError({"nombre_places": "Le nombre de places doit être au moins 1."})


class Offre(models.Model):
    besoin = models.OneToOneField(
        Besoin,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="offre",
        verbose_name="besoin associé",
    )
    type_stage = models.ForeignKey(
        "referentiels.TypeStage",
        on_delete=models.PROTECT,
        related_name="offres",
        verbose_name="type de stage",
    )
    titre = models.CharField(max_length=200, verbose_name="titre")
    description = models.TextField(verbose_name="description")
    profil_recherche = models.TextField(verbose_name="profil recherché")
    date_debut = models.DateField(verbose_name="date de début")
    date_fin = models.DateField(verbose_name="date de fin")
    nombre_places = models.PositiveSmallIntegerField(verbose_name="nombre de places")
    statut = models.CharField(
        max_length=20,
        choices=StatutOffre.choices,
        default=StatutOffre.BROUILLON,
        verbose_name="statut",
    )
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="date de création")

    class Meta:
        verbose_name = "Offre"
        verbose_name_plural = "Offres"
        ordering = ["-date_creation"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(nombre_places__gte=1),
                name="offre_nombre_places_gte_1",
            ),
            models.CheckConstraint(
                condition=models.Q(date_fin__gt=models.F("date_debut")),
                name="offre_date_fin_gt_date_debut",
            ),
        ]

    def __str__(self):
        return self.titre

    def clean(self):
        if self.date_debut and self.date_fin and self.date_fin <= self.date_debut:
            raise ValidationError({"date_fin": "La date de fin doit être postérieure à la date de début."})
        if self.nombre_places is not None and self.nombre_places < 1:
            raise ValidationError({"nombre_places": "Le nombre de places doit être au moins 1."})

    def places_restantes(self):
        """Nombre de places encore disponibles (sera affiné à l'étape stages)."""
        return self.nombre_places


class Publication(models.Model):
    offre = models.ForeignKey(
        Offre,
        on_delete=models.CASCADE,
        related_name="publications",
        verbose_name="offre",
    )
    canal = models.ForeignKey(
        "referentiels.CanalPublication",
        on_delete=models.PROTECT,
        related_name="publications",
        verbose_name="canal",
    )
    url = models.URLField(verbose_name="URL")
    description = models.TextField(blank=True, verbose_name="description")
    date_publication = models.DateField(verbose_name="date de publication")

    class Meta:
        verbose_name = "Publication"
        verbose_name_plural = "Publications"
        ordering = ["-date_publication"]

    def __str__(self):
        return f"{self.offre} — {self.canal}"
