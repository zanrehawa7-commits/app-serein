from django.db import migrations


def supprimer_permissions_membre(apps, schema_editor):
    """
    Après RenameModel, le ContentType est renommé (membre→personnel) mais les
    codenames add_membre/change_membre/delete_membre/view_membre restent en base.
    post_migrate crée les nouvelles *_personnel ; on supprime ici les orphelines.
    """
    Permission = apps.get_model("auth", "Permission")
    Permission.objects.filter(
        content_type__app_label="referentiels",
        content_type__model="personnel",
        codename__in=["add_membre", "change_membre", "delete_membre", "view_membre"],
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("referentiels", "0002_rename_membre_personnel"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(
            supprimer_permissions_membre,
            migrations.RunPython.noop,
        ),
    ]
