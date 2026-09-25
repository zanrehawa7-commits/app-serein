from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models


class Historique(models.Model):
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        verbose_name="type d'objet",
    )
    object_id = models.PositiveIntegerField(verbose_name="identifiant objet")
    objet = GenericForeignKey("content_type", "object_id")
    utilisateur = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="historiques",
        verbose_name="utilisateur",
    )
    ancien_statut = models.CharField(max_length=30, blank=True, verbose_name="ancien statut")
    nouveau_statut = models.CharField(max_length=30, blank=True, verbose_name="nouveau statut")
    commentaire = models.TextField(blank=True, verbose_name="commentaire")
    date_action = models.DateTimeField(auto_now_add=True, verbose_name="date de l'action")

    class Meta:
        verbose_name = "Historique"
        verbose_name_plural = "Historiques"
        ordering = ["-date_action"]
        indexes = [
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"{self.date_action:%d/%m/%Y %H:%M} — {self.ancien_statut} → {self.nouveau_statut}"


class Notification(models.Model):
    destinataire = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        verbose_name="destinataire",
    )
    message = models.TextField(verbose_name="message")
    lien = models.CharField(max_length=200, blank=True, verbose_name="lien")
    lue = models.BooleanField(default=False, verbose_name="lue")
    date_creation = models.DateTimeField(auto_now_add=True, verbose_name="date de création")

    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ["-date_creation"]

    def __str__(self):
        return f"Notification → {self.destinataire} ({self.date_creation:%d/%m/%Y})"
