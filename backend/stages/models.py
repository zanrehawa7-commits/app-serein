from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from commun.stockage import StockagePrive



def _get_stockage_rapport():
    return StockagePrive()


class StatutStage(models.TextChoices):
    A_VENIR = "A_VENIR", "À venir"
    EN_COURS = "EN_COURS", "En cours"
    TERMINE = "TERMINE", "Terminé"
    INTERROMPU = "INTERROMPU", "Interrompu"


class Stage(models.Model):
    candidature = models.OneToOneField(
        "candidatures.Candidature",
        on_delete=models.PROTECT,
        related_name="stage",
        verbose_name="candidature",
    )
    maitre_stage = models.ForeignKey(
        "referentiels.Personnel",
        on_delete=models.PROTECT,
        related_name="stages_encadres",
        verbose_name="maître de stage",
    )
    date_debut = models.DateField(verbose_name="date de début")
    date_fin_prevue = models.DateField(verbose_name="date de fin prévue")
    date_fin_reelle = models.DateField(null=True, blank=True, verbose_name="date de fin réelle")
    statut = models.CharField(
        max_length=20,
        choices=StatutStage.choices,
        default=StatutStage.A_VENIR,
        verbose_name="statut",
    )
    motif_interruption = models.TextField(blank=True, verbose_name="motif d'interruption")
    note = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name="note /20")
    vivier = models.BooleanField(default=False, verbose_name="vivier")
    rapport = models.FileField(
        storage=_get_stockage_rapport,
        upload_to="stages/rapports/%Y/",
        null=True,
        blank=True,
        verbose_name="rapport de stage",
    )
    date_evaluation = models.DateField(null=True, blank=True, verbose_name="date d'évaluation")
    rappel_evaluation_envoye = models.BooleanField(
        default=False,
        verbose_name="rappel évaluation envoyé",
    )

    class Meta:
        verbose_name = "Stage"
        verbose_name_plural = "Stages"
        ordering = ["-date_debut"]
        # Droits des rôles de consultation (RG-U9) ; les rôles de base passent par leur rôle.
        permissions = [
            ("consulter_vivier", "Consulter le vivier de talents"),
            ("exporter_vivier", "Exporter le vivier (CSV)"),
            ("telecharger_rapports", "Télécharger les rapports de stage"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(date_fin_prevue__gt=models.F("date_debut")),
                name="stage_date_fin_prevue_gt_date_debut",
            ),
            models.CheckConstraint(
                condition=models.Q(note__isnull=True) | models.Q(note__gte=1, note__lte=20),
                name="stage_note_entre_1_et_20",
            ),
            # vivier ne peut être True que si note >= 12
            models.CheckConstraint(
                condition=models.Q(vivier=False) | models.Q(note__gte=12),
                name="stage_vivier_necessite_note_gte_12",
            ),
        ]

    def __str__(self):
        return f"Stage {self.candidature.reference} — {self.candidature.candidat}"

    def date_demarrage_effective(self):
        """Date de la dernière reprise (RG-S12), sinon date de début : borne basse des dates saisies."""
        derniere_reprise = (
            self.periodes_interruption.filter(date_fin__isnull=False)
            .order_by("-date_fin").values_list("date_fin", flat=True).first()
        )
        return derniere_reprise or self.date_debut

    def periode_interruption_ouverte(self):
        return self.periodes_interruption.filter(date_fin__isnull=True).first()

    def clean(self):
        if self.date_debut and self.date_fin_prevue and self.date_fin_prevue <= self.date_debut:
            raise ValidationError(
                {"date_fin_prevue": "La date de fin prévue doit être postérieure à la date de début."}
            )
        if self.note is not None and not (1 <= self.note <= 20):
            raise ValidationError({"note": "La note doit être comprise entre 1 et 20."})
        if self.vivier and (self.note is None or self.note < 12):
            raise ValidationError({"vivier": "Le vivier ne peut être activé que si la note est >= 12."})
        # RG22 : le maître de stage doit appartenir au département de la candidature
        if self.maitre_stage_id and self.candidature_id:
            dept_candidature = self.candidature.departement_id
            dept_maitre = self.maitre_stage.departement_id
            if dept_maitre != dept_candidature:
                raise ValidationError(
                    {"maitre_stage": "Le maître de stage doit appartenir au département de la candidature."}
                )


class AffectationMaitreStage(models.Model):
    stage = models.ForeignKey(
        Stage,
        on_delete=models.CASCADE,
        related_name="affectations_maitre",
        verbose_name="stage",
    )
    maitre_stage = models.ForeignKey(
        "referentiels.Personnel",
        on_delete=models.PROTECT,
        related_name="+",
        verbose_name="maître de stage",
    )
    affecte_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="affecté par",
    )
    date_affectation = models.DateTimeField(auto_now_add=True, verbose_name="date d'affectation")

    class Meta:
        verbose_name = "Affectation de maître de stage"
        verbose_name_plural = "Affectations de maître de stage"
        ordering = ["-date_affectation"]

    def __str__(self):
        return f"Maître {self.maitre_stage} → {self.stage}"


class PeriodeInterruption(models.Model):
    """RG-S13 : créée à l'interruption, complétée à la reprise ; toutes les périodes sont conservées."""

    stage = models.ForeignKey(
        Stage,
        on_delete=models.CASCADE,
        related_name="periodes_interruption",
        verbose_name="stage",
    )
    date_debut = models.DateField(verbose_name="date d'interruption")
    date_fin = models.DateField(null=True, blank=True, verbose_name="date de reprise")
    motif_interruption = models.TextField(verbose_name="motif d'interruption")
    motif_reprise = models.TextField(blank=True, verbose_name="motif de reprise")
    interrompu_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="interrompu par",
    )
    repris_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="repris par",
    )

    class Meta:
        verbose_name = "Période d'interruption"
        verbose_name_plural = "Périodes d'interruption"
        ordering = ["date_debut", "pk"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(date_fin__isnull=True) | models.Q(date_fin__gte=models.F("date_debut")),
                name="periode_interruption_reprise_apres_interruption",
            ),
            models.UniqueConstraint(
                fields=["stage"],
                condition=models.Q(date_fin__isnull=True),
                name="periode_interruption_une_seule_ouverte_par_stage",
            ),
        ]

    def __str__(self):
        fin = f"{self.date_fin:%d/%m/%Y}" if self.date_fin else "en cours"
        return f"Interruption {self.stage} : {self.date_debut:%d/%m/%Y} → {fin}"
