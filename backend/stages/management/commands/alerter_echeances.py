import datetime

from django.core.management.base import BaseCommand, CommandError
from django.urls import reverse
from django.utils import timezone

from candidatures.models import Candidature
from candidatures.services import (
    candidatures_accordees_sans_stage_expirantes,
    candidatures_disponibilite_expirante,
)
from stages.models import Stage, StatutStage
from stages.services import stages_a_demarrer, stages_a_terminer
from suivi.services import notifier, responsables_ou_administrateurs


def _secretaires_actives():
    from comptes.models import Utilisateur
    return list(Utilisateur.objects.filter(groups__name="Secrétaire", is_active=True))


class Command(BaseCommand):
    help = (
        "Alertes d'échéances (RG-S15) : stages à démarrer / à terminer, disponibilités expirant dans 72 h, "
        "rappels d'évaluation. Ne change jamais un statut : le système alerte, il ne décide pas."
    )

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, help="Date de référence au format AAAA-MM-JJ (défaut : aujourd'hui).")

    def handle(self, *args, **options):
        date_str = options.get("date")
        if date_str:
            try:
                aujourd_hui = datetime.date.fromisoformat(date_str)
            except ValueError:
                raise CommandError(f"Format de date invalide : {date_str!r}. Attendu : AAAA-MM-JJ.")
        else:
            aujourd_hui = timezone.localdate()
        self.stdout.write(f"Date de référence : {aujourd_hui}")

        compteurs = {
            "à démarrer": self._stages_a_demarrer(aujourd_hui),
            "à terminer": self._stages_a_terminer(aujourd_hui),
            "disponibilité (en cours)": self._disponibilites_en_cours(aujourd_hui),
            "disponibilité (accordées sans stage)": self._disponibilites_sans_stage(aujourd_hui),
            "rappels d'évaluation": self._rappels_evaluation(aujourd_hui),
        }
        resume = ", ".join(f"{n} {libelle}" for libelle, n in compteurs.items())
        self.stdout.write(self.style.SUCCESS(f"\nAlertes envoyées : {resume}."))

    def _envoyer(self, destinataires, message, lien, etiquette, objet):
        notifier(destinataires, message, lien)
        self.stdout.write(self.style.WARNING(f"  [{etiquette}] {objet}"))

    # a) RG-S15
    def _stages_a_demarrer(self, aujourd_hui):
        n = 0
        for s in stages_a_demarrer(aujourd_hui):
            if s.alerte_demarrage_envoyee:
                continue
            self._envoyer(
                responsables_ou_administrateurs(s.candidature.departement),
                f"Stage de {s.candidature.candidat} à démarrer (démarrage possible le "
                f"{s.date_demarrage_effective():%d/%m/%Y}).",
                reverse("stages:stage_detail", args=[s.pk]), "À DÉMARRER", s,
            )
            Stage.objects.filter(pk=s.pk).update(alerte_demarrage_envoyee=True)
            n += 1
        return n

    # b) RG-S15 : le stage reste « En cours » après la date, rien d'automatique.
    def _stages_a_terminer(self, aujourd_hui):
        n = 0
        for s in stages_a_terminer(aujourd_hui):
            if s.alerte_fin_envoyee:
                continue
            self._envoyer(
                responsables_ou_administrateurs(s.candidature.departement),
                f"Stage de {s.candidature.candidat} à terminer : fin prévue le {s.date_fin_prevue:%d/%m/%Y}.",
                reverse("stages:stage_detail", args=[s.pk]), "À TERMINER", s,
            )
            Stage.objects.filter(pk=s.pk).update(alerte_fin_envoyee=True)
            n += 1
        return n

    # c) RG-S15 : jamais de refus automatique.
    def _disponibilites_en_cours(self, aujourd_hui):
        n = 0
        for c in candidatures_disponibilite_expirante(aujourd_hui):
            if c.alerte_disponibilite_envoyee:
                continue
            self._envoyer(
                responsables_ou_administrateurs(c.departement),
                f"Candidature {c.reference} ({c.candidat}) : la disponibilité du candidat se termine le "
                f"{c.fin_disponibilite:%d/%m/%Y}.",
                reverse("candidatures:candidature_detail", args=[c.pk]), "DISPONIBILITÉ", c,
            )
            Candidature.objects.filter(pk=c.pk).update(alerte_disponibilite_envoyee=True)
            n += 1
        return n

    # d) RG-S15
    def _disponibilites_sans_stage(self, aujourd_hui):
        n = 0
        secretaires = _secretaires_actives()
        for c in candidatures_accordees_sans_stage_expirantes(aujourd_hui):
            if c.alerte_disponibilite_stage_envoyee:
                continue
            self._envoyer(
                secretaires,
                f"Candidature {c.reference} ({c.candidat}) accordée sans stage : disponibilité jusqu'au "
                f"{c.fin_disponibilite:%d/%m/%Y}.",
                reverse("candidatures:candidature_detail", args=[c.pk]), "SANS STAGE", c,
            )
            Candidature.objects.filter(pk=c.pk).update(alerte_disponibilite_stage_envoyee=True)
            n += 1
        return n

    # e) RG-S10 : rappel d'évaluation J+7, calculé sur la date de fin réelle (saisie par le Responsable).
    def _rappels_evaluation(self, aujourd_hui):
        n = 0
        a_rappeler = Stage.objects.filter(
            statut=StatutStage.TERMINE,
            note__isnull=True,
            date_fin_reelle__lte=aujourd_hui - datetime.timedelta(days=7),
            rappel_evaluation_envoye=False,
        ).select_related("candidature__candidat", "candidature__departement")
        for s in a_rappeler:
            self._envoyer(
                responsables_ou_administrateurs(s.candidature.departement),
                f"Rappel : le stage de {s.candidature.candidat} est terminé et n'a pas encore été évalué.",
                reverse("stages:stage_detail", args=[s.pk]), "RAPPEL", s,
            )
            Stage.objects.filter(pk=s.pk).update(rappel_evaluation_envoye=True)
            n += 1
        return n
