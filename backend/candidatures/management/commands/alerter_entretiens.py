from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Envoie une alerte aux Secrétaires pour les entretiens dans moins de 48 h dont le candidat n'a pas encore été informé."

    def handle(self, *args, **options):
        from candidatures.models import Candidature, StatutCandidature
        from suivi.services import notifier

        def _secretaires_actives():
            from comptes.models import Utilisateur
            return list(Utilisateur.objects.filter(groups__name="Secrétaire", is_active=True))

        maintenant = timezone.now()
        seuil_48h = maintenant + timedelta(hours=48)

        candidatures = Candidature.objects.filter(
            statut=StatutCandidature.EN_TRAITEMENT,
            date_entretien__isnull=False,
            date_entretien__gt=maintenant,
            date_entretien__lte=seuil_48h,
            candidat_informe=False,
            alerte_entretien_envoyee=False,
        )

        secs = _secretaires_actives()
        nb = 0
        for cand in candidatures:
            if secs:
                date_fmt = cand.date_entretien.strftime("%d/%m/%Y à %H:%M")
                lien = f"/candidatures/{cand.pk}/"
                notifier(
                    secs,
                    f"Rappel : entretien de {cand.reference} ({cand.candidat}) prévu le {date_fmt} — candidat non informé.",
                    lien,
                )
            cand.alerte_entretien_envoyee = True
            cand.save(update_fields=["alerte_entretien_envoyee"])
            nb += 1

        self.stdout.write(self.style.SUCCESS(f"{nb} alerte(s) envoyée(s)."))
