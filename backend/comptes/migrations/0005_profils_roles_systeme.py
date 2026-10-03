from django.db import migrations

ROLES_SYSTEME = ("Administrateur", "Secrétaire", "Responsable")


def creer_profils_systeme(apps, schema_editor):
    """Groupes déjà créés par init_donnees : profil système. Sur une base neuve, init_donnees le fera."""
    Group = apps.get_model("auth", "Group")
    ProfilRole = apps.get_model("comptes", "ProfilRole")
    for groupe in Group.objects.filter(name__in=ROLES_SYSTEME):
        ProfilRole.objects.update_or_create(groupe=groupe, defaults={"est_systeme": True, "actif": True})


class Migration(migrations.Migration):

    dependencies = [
        ("comptes", "0004_profilrole"),
    ]

    operations = [
        migrations.RunPython(creer_profils_systeme, migrations.RunPython.noop),
    ]
