import stages.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('stages', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='stage',
            name='rappel_evaluation_envoye',
            field=models.BooleanField(default=False, verbose_name='rappel évaluation envoyé'),
        ),
        migrations.AlterField(
            model_name='stage',
            name='rapport',
            field=models.FileField(
                blank=True,
                null=True,
                storage=stages.models._get_stockage_rapport,
                upload_to='stages/rapports/%Y/',
                verbose_name='rapport de stage',
            ),
        ),
    ]
