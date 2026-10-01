import datetime
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from stages.models import Stage, StatutStage
from stages.services import demarrer_stage_auto, cloturer_stage_auto


def _responsable_dept(departement):
    from comptes.models import Utilisateur
    return Utilisateur.objects.filter(
        personnel__departement=departement,
        is_active=True,
        groups__name="Responsable",
    ).first()


class Command(BaseCommand):
    help = "Démarre les stages à venir et clôture les stages en cours dont la date est dépassée."

    def add_arguments(self, parser):
        parser.add_argument(
            "--date",
            type=str,
            help="Date de référence au format AAAA-MM-JJ (défaut : aujourd'hui).",
        )

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

        # 1) Démarrages d'abord (A_VENIR dont date_debut <= aujourd_hui)
        a_venir = Stage.objects.filter(
            statut=StatutStage.A_VENIR,
            date_debut__lte=aujourd_hui,
        )
        demarres = 0
        for stage in a_venir:
            if demarrer_stage_auto(stage, aujourd_hui):
                demarres += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  [DÉMARRÉ] {stage} (début : {stage.date_debut})")
                )

        # 2) Clôtures ensuite (EN_COURS dont date_fin_prevue < aujourd_hui)
        en_cours = Stage.objects.filter(
            statut=StatutStage.EN_COURS,
            date_fin_prevue__lt=aujourd_hui,
        )
        clotures = 0
        for stage in en_cours:
            if cloturer_stage_auto(stage, aujourd_hui):
                clotures += 1
                self.stdout.write(
                    self.style.SUCCESS(f"  [TERMINÉ]  {stage} (fin prévue : {stage.date_fin_prevue})")
                )

        # 3) Rappels évaluation : TERMINÉ + sans note + fin ≤ today-7j + rappel pas encore envoyé
        from suivi.services import notifier
        seuil_rappel = aujourd_hui - datetime.timedelta(days=7)
        a_rappeler = Stage.objects.filter(
            statut=StatutStage.TERMINE,
            note__isnull=True,
            date_fin_reelle__lte=seuil_rappel,
            rappel_evaluation_envoye=False,
        )
        rappels = 0
        for stage in a_rappeler:
            resp = _responsable_dept(stage.candidature.departement)
            if resp:
                lien = f"/stages/{stage.pk}/evaluer/"
                notifier(
                    [resp],
                    f"Rappel : le stage de {stage.candidature.candidat} est terminé et n'a pas encore été évalué.",
                    lien,
                )
            stage.rappel_evaluation_envoye = True
            stage.save(update_fields=["rappel_evaluation_envoye"])
            rappels += 1
            self.stdout.write(
                self.style.WARNING(f"  [RAPPEL]   {stage} — responsable notifié.")
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nTerminé : {demarres} stage(s) démarré(s), {clotures} stage(s) terminé(s), "
                f"{rappels} rappel(s) envoyé(s)."
            )
        )
