import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("stages", "0002_stage_evaluation"),
        ("referentiels", "0002_rename_membre_personnel"),
    ]

    operations = [
        # Corrige l'état de migration : stages/0001_initial (state_operations) gardait
        # la référence historique referentiels.membre ; cette migration la met à jour
        # vers referentiels.personnel. Aucune opération DB : la FK physique est déjà
        # correcte grâce aux database_operations de stages/0001_initial.
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="stage",
                    name="maitre_stage",
                    field=models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="stages_encadres",
                        to="referentiels.personnel",
                        verbose_name="maître de stage",
                    ),
                ),
            ],
            database_operations=[],
        ),
    ]
