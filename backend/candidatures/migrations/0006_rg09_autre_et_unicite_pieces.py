from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("candidatures", "0005_niveau_etudes_bts_doctorat_autre"),
    ]

    operations = [
        # 1. Supprimer l'ancienne contrainte RG09 (ne couvre pas AUTRE)
        migrations.RemoveConstraint(
            model_name="candidature",
            name="candidature_offre_coherente_type_demande",
        ),
        # 2. Recréer la contrainte RG09 en incluant AUTRE (offre interdite)
        migrations.AddConstraint(
            model_name="candidature",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(type_demande="SUITE_OFFRE", offre__isnull=False)
                    | models.Q(type_demande="SPONTANEE", offre__isnull=True)
                    | models.Q(type_demande="AUTRE", offre__isnull=True)
                ),
                name="candidature_offre_coherente_type_demande",
            ),
        ),
        # 3. UniqueConstraint (candidature, type_piece) sauf AUTRE
        #    Vérifié en base : aucun doublon existant.
        migrations.AddConstraint(
            model_name="piecejointe",
            constraint=models.UniqueConstraint(
                fields=["candidature", "type_piece"],
                condition=~models.Q(type_piece="AUTRE"),
                name="piecejointe_unique_type_par_candidature",
            ),
        ),
    ]
