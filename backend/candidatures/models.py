import os
from django.core.exceptions import ValidationError
from django.db import models


class TypeDemande(models.TextChoices):
    SPONTANEE = "SPONTANEE", "Spontanée"
    SUITE_OFFRE = "SUITE_OFFRE", "Suite à une offre"


class StatutCandidature(models.TextChoices):
    RECUE = "RECUE", "Reçue"
    EN_TRAITEMENT = "EN_TRAITEMENT", "En traitement"
    ACCORDEE = "ACCORDEE", "Accordée"
    REFUSEE = "REFUSEE", "Refusée"


class MotifRefus(models.TextChoices):
    PROFIL_INADAPTE = "PROFIL_INADAPTE", "Profil inadapté"
    PERIODE_INDISPONIBLE = "PERIODE_INDISPONIBLE", "Période indisponible"
    QUOTA_ATTEINT = "QUOTA_ATTEINT", "Quota atteint"
    DESISTEMENT = "DESISTEMENT", "Désistement"
    AUTRE = "AUTRE", "Autre"


class TypePiece(models.TextChoices):
    CV = "CV", "CV"
    LETTRE_MOTIVATION = "LETTRE_MOTIVATION", "Lettre de motivation"
    LETTRE_DEMANDE = "LETTRE_DEMANDE", "Lettre de demande"
    LETTRE_RECOMMANDATION = "LETTRE_RECOMMANDATION", "Lettre de recommandation"
    AUTRE = "AUTRE", "Autre"


def _valider_piece_jointe(fichier):
    extensions_autorisees = [".pdf", ".jpg", ".jpeg", ".png"]
    ext = os.path.splitext(fichier.name)[1].lower()
    if ext not in extensions_autorisees:
        raise ValidationError(
            f"Extension non autorisée : {ext}. Formats acceptés : pdf, jpg, jpeg, png."
        )
    taille_max = 5 * 1024 * 1024  # 5 Mo
    if fichier.size > taille_max:
        raise ValidationError("La taille du fichier ne doit pas dépasser 5 Mo.")


class Candidat(models.Model):
    nom = models.CharField(max_length=100, verbose_name="nom")
    prenom = models.CharField(max_length=100, verbose_name="prénom")
    telephone = models.CharField(max_length=20, db_index=True, verbose_name="téléphone")
    email = models.EmailField(blank=True, db_index=True, verbose_name="email")
    adresse = models.TextField(blank=True, verbose_name="adresse")
    niveau_etudes = models.CharField(max_length=100, blank=True, verbose_name="niveau d'études")
    filiere = models.CharField(max_length=150, blank=True, verbose_name="filière")
    etablissement = models.ForeignKey(
        "referentiels.Etablissement",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="candidats",
        verbose_name="établissement",
    )

    class Meta:
        verbose_name = "Candidat"
        verbose_name_plural = "Candidats"
        ordering = ["nom", "prenom"]

    def __str__(self):
        return f"{self.prenom} {self.nom}"


class Candidature(models.Model):
    reference = models.CharField(max_length=20, unique=True, verbose_name="référence")
    candidat = models.ForeignKey(
        Candidat,
        on_delete=models.PROTECT,
        related_name="candidatures",
        verbose_name="candidat",
    )
    departement = models.ForeignKey(
        "referentiels.Departement",
        on_delete=models.PROTECT,
        related_name="candidatures",
        verbose_name="département",
    )
    offre = models.ForeignKey(
        "offres.Offre",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="candidatures",
        verbose_name="offre",
    )
    type_stage = models.ForeignKey(
        "referentiels.TypeStage",
        on_delete=models.PROTECT,
        related_name="candidatures",
        verbose_name="type de stage",
    )
    type_demande = models.CharField(
        max_length=20,
        choices=TypeDemande.choices,
        verbose_name="type de demande",
    )
    debut_disponibilite = models.DateField(verbose_name="début de disponibilité")
    fin_disponibilite = models.DateField(verbose_name="fin de disponibilité")
    duree_souhaitee = models.PositiveSmallIntegerField(verbose_name="durée souhaitée (semaines)")
    statut = models.CharField(
        max_length=20,
        choices=StatutCandidature.choices,
        default=StatutCandidature.RECUE,
        verbose_name="statut",
    )
    motif_refus = models.CharField(
        max_length=30,
        choices=MotifRefus.choices,
        blank=True,
        verbose_name="motif de refus",
    )
    precision_motif = models.TextField(blank=True, verbose_name="précision du motif")
    date_entretien = models.DateTimeField(null=True, blank=True, verbose_name="date d'entretien")
    commentaire = models.TextField(blank=True, verbose_name="commentaire")
    candidat_informe = models.BooleanField(default=False, verbose_name="candidat informé")
    date_information = models.DateTimeField(null=True, blank=True, verbose_name="date d'information")
    date_depot = models.DateTimeField(auto_now_add=True, verbose_name="date de dépôt")

    class Meta:
        verbose_name = "Candidature"
        verbose_name_plural = "Candidatures"
        ordering = ["-date_depot"]
        constraints = [
            # RG07 : une seule candidature active par candidat
            models.UniqueConstraint(
                fields=["candidat"],
                condition=models.Q(statut__in=["RECUE", "EN_TRAITEMENT"]),
                name="candidature_unique_active_par_candidat",
            ),
            # RG09 : offre obligatoire si SUITE_OFFRE, interdite si SPONTANEE
            models.CheckConstraint(
                condition=(
                    models.Q(type_demande="SUITE_OFFRE", offre__isnull=False)
                    | models.Q(type_demande="SPONTANEE", offre__isnull=True)
                ),
                name="candidature_offre_coherente_type_demande",
            ),
            models.CheckConstraint(
                condition=models.Q(fin_disponibilite__gt=models.F("debut_disponibilite")),
                name="candidature_fin_dispo_gt_debut",
            ),
        ]

    def __str__(self):
        return f"{self.reference} — {self.candidat}"

    def clean(self):
        if self.debut_disponibilite and self.fin_disponibilite:
            if self.fin_disponibilite <= self.debut_disponibilite:
                raise ValidationError(
                    {"fin_disponibilite": "La fin de disponibilité doit être postérieure au début."}
                )
        # RG09
        if self.type_demande == TypeDemande.SUITE_OFFRE and not self.offre_id:
            raise ValidationError({"offre": "Une offre est obligatoire pour une candidature suite à une offre."})
        if self.type_demande == TypeDemande.SPONTANEE and self.offre_id:
            raise ValidationError({"offre": "Une candidature spontanée ne doit pas être liée à une offre."})

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = self._generer_reference()
        super().save(*args, **kwargs)

    @classmethod
    def _generer_reference(cls):
        from django.utils import timezone
        annee = timezone.now().year
        derniere = (
            cls.objects.filter(reference__startswith=f"CAND-{annee}-")
            .order_by("reference")
            .last()
        )
        if derniere:
            numero = int(derniere.reference.split("-")[-1]) + 1
        else:
            numero = 1
        return f"CAND-{annee}-{numero:04d}"


class PieceJointe(models.Model):
    candidature = models.ForeignKey(
        Candidature,
        on_delete=models.CASCADE,
        related_name="pieces",
        verbose_name="candidature",
    )
    type_piece = models.CharField(
        max_length=30,
        choices=TypePiece.choices,
        verbose_name="type de pièce",
    )
    fichier = models.FileField(
        upload_to="candidatures/%Y/%m/",
        validators=[_valider_piece_jointe],
        verbose_name="fichier",
    )
    date_ajout = models.DateTimeField(auto_now_add=True, verbose_name="date d'ajout")

    class Meta:
        verbose_name = "Pièce jointe"
        verbose_name_plural = "Pièces jointes"
        ordering = ["type_piece"]

    def __str__(self):
        return f"{self.get_type_piece_display()} — {self.candidature.reference}"
