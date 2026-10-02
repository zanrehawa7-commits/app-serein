from django.db import migrations, models
import django.db.models.deletion


def remplir_departement_depuis_besoin(apps, schema_editor):
    Offre = apps.get_model("offres", "Offre")
    for offre in Offre.objects.select_related("besoin__departement").filter(besoin__isnull=False):
        offre.departement = offre.besoin.departement
        offre.save(update_fields=["departement"])


class Migration(migrations.Migration):

    dependencies = [
        ("offres", "0001_initial"),
        ("referentiels", "0004_typestage_durees"),
    ]

    operations = [
        migrations.CreateModel(
            name="ParametreOffre",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("contact", models.TextField(blank=True, verbose_name="contact")),
                ("texte_modele", models.TextField(blank=True, verbose_name="modèle de texte")),
            ],
            options={
                "verbose_name": "Paramètre de texte d'offre",
                "verbose_name_plural": "Paramètres de texte d'offre",
            },
        ),
        migrations.AddField(
            model_name="offre",
            name="departement",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="offres",
                to="referentiels.departement",
                verbose_name="département",
            ),
        ),
        migrations.RunPython(remplir_departement_depuis_besoin, migrations.RunPython.noop),
        migrations.AddField(
            model_name="offre",
            name="texte_publie",
            field=models.TextField(blank=True, verbose_name="texte de l'offre"),
        ),
    ]
