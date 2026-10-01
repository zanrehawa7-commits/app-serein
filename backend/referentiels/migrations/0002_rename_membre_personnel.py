from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("referentiels", "0001_initial"),
    ]

    operations = [
        migrations.RenameModel("Membre", "Personnel"),
        migrations.AlterModelOptions(
            name="personnel",
            options={
                "ordering": ["nom", "prenom"],
                "verbose_name": "Personnel",
                "verbose_name_plural": "Personnels",
            },
        ),
        migrations.AlterUniqueTogether(
            name="personnel",
            unique_together=set(),
        ),
        migrations.AlterField(
            model_name="personnel",
            name="departement",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="personnels",
                to="referentiels.departement",
                verbose_name="département",
            ),
        ),
    ]
