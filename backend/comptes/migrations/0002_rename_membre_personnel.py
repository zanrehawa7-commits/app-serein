from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("comptes", "0001_initial"),
        ("referentiels", "0002_rename_membre_personnel"),
    ]

    operations = [
        migrations.RenameField(
            model_name="utilisateur",
            old_name="membre",
            new_name="personnel",
        ),
    ]
