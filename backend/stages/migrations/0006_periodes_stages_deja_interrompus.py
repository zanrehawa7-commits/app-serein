from django.db import migrations


def creer_periodes_ouvertes(apps, schema_editor):
    """Stages interrompus avant le lot F : sans période ouverte, ils ne pourraient pas être repris."""
    Stage = apps.get_model("stages", "Stage")
    PeriodeInterruption = apps.get_model("stages", "PeriodeInterruption")
    deja_ouverts = PeriodeInterruption.objects.filter(date_fin__isnull=True).values("stage")
    a_completer = Stage.objects.filter(statut="INTERROMPU").exclude(pk__in=deja_ouverts)
    PeriodeInterruption.objects.bulk_create([
        PeriodeInterruption(
            stage=stage,
            date_debut=stage.date_fin_reelle or stage.date_debut,
            motif_interruption=stage.motif_interruption or "(motif non renseigné)",
        )
        for stage in a_completer
    ])


class Migration(migrations.Migration):

    dependencies = [
        ("stages", "0005_periode_interruption"),
    ]

    operations = [
        migrations.RunPython(creer_periodes_ouvertes, migrations.RunPython.noop),
    ]
