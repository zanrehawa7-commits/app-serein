from django.core.validators import MinValueValidator
from django.db import migrations, models

# Valeurs initiales par libellé — validées et modifiables par l'admin.
_DUREES_PAR_LIBELLE = {
    "Stage d'immersion": (1, 2),
    "Stage de perfectionnement": (1, 3),
    "Stage professionnel": (1, 6),
    "Stage de fin d'études": (3, 6),
    "Stage de géomètre expert": (3, 12),
}
_DEFAULT_MIN = 1
_DEFAULT_MAX = 6


def remplir_durees(apps, schema_editor):
    TypeStage = apps.get_model("referentiels", "TypeStage")
    for ts in TypeStage.objects.all():
        min_m, max_m = _DUREES_PAR_LIBELLE.get(ts.libelle, (_DEFAULT_MIN, _DEFAULT_MAX))
        ts.duree_min_mois = min_m
        ts.duree_max_mois = max_m
        ts.save(update_fields=["duree_min_mois", "duree_max_mois"])


class Migration(migrations.Migration):

    dependencies = [
        ("referentiels", "0003_data_permissions_membre"),
    ]

    operations = [
        # 1. Ajouter les champs avec valeurs temporaires
        migrations.AddField(
            model_name="typestage",
            name="duree_min_mois",
            field=models.PositiveSmallIntegerField(
                default=1,
                validators=[MinValueValidator(1)],
                verbose_name="durée minimale (mois)",
                help_text="Durée minimale du stage en mois entiers.",
            ),
        ),
        migrations.AddField(
            model_name="typestage",
            name="duree_max_mois",
            field=models.PositiveSmallIntegerField(
                default=6,
                validators=[MinValueValidator(1)],
                verbose_name="durée maximale (mois)",
                help_text="Durée maximale du stage en mois entiers.",
            ),
        ),
        # 2. Peupler selon le libellé
        migrations.RunPython(remplir_durees, migrations.RunPython.noop),
        # 3. Rendre les champs obligatoires (retirer default)
        migrations.AlterField(
            model_name="typestage",
            name="duree_min_mois",
            field=models.PositiveSmallIntegerField(
                validators=[MinValueValidator(1)],
                verbose_name="durée minimale (mois)",
                help_text="Durée minimale du stage en mois entiers.",
            ),
        ),
        migrations.AlterField(
            model_name="typestage",
            name="duree_max_mois",
            field=models.PositiveSmallIntegerField(
                validators=[MinValueValidator(1)],
                verbose_name="durée maximale (mois)",
                help_text="Durée maximale du stage en mois entiers.",
            ),
        ),
        # 4. Contrainte DB min ≤ max
        migrations.AddConstraint(
            model_name="typestage",
            constraint=models.CheckConstraint(
                condition=models.Q(duree_max_mois__gte=models.F("duree_min_mois")),
                name="typestage_max_gte_min",
            ),
        ),
    ]
