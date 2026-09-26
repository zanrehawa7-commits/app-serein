from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from referentiels.models import TypeStage


_CRUD = ["add", "change", "delete", "view"]

GROUPES_PERMISSIONS = {
    "Administrateur": {
        "comptes": _CRUD,
        "referentiels": _CRUD,
        "offres": _CRUD,
        "candidatures": _CRUD,
        "stages": _CRUD,
        "suivi": _CRUD,
    },
    "Secrétaire": {
        "offres": ["add", "change", "view"],          # Offre, Publication
        "candidatures": ["add", "change", "view"],    # Candidat, Candidature, PieceJointe
        "referentiels": ["view"],                     # lecture Besoin incluse
    },
    "Responsable": {
        "offres": ["add", "change", "view"],          # Besoin
        "candidatures": ["change", "view"],           # Candidature
        "stages": ["add", "change", "view"],          # Stage
        "referentiels": ["view"],                     # lecture Membre
    },
}

TYPES_STAGE = [
    "Stage de perfectionnement",
    "Stage professionnel",
    "Stage de géomètre expert",
    "Stage d'immersion",
    "Stage de fin d'études",
]


class Command(BaseCommand):
    help = "Initialise les groupes, permissions et référentiels de base (idempotent)."

    def handle(self, *args, **options):
        self._creer_groupes()
        self._creer_types_stage()
        self.stdout.write(self.style.SUCCESS("Initialisation terminée."))

    def _creer_groupes(self):
        for nom_groupe, apps_perms in GROUPES_PERMISSIONS.items():
            groupe, cree = Group.objects.get_or_create(name=nom_groupe)
            action = "créé" if cree else "déjà existant"
            self.stdout.write(f"  Groupe '{nom_groupe}' {action}.")

            perms_a_ajouter = []
            for app_label, actions in apps_perms.items():
                cts = ContentType.objects.filter(app_label=app_label)
                for ct in cts:
                    for action_perm in actions:
                        codename = f"{action_perm}_{ct.model}"
                        try:
                            perm = Permission.objects.get(content_type=ct, codename=codename)
                            perms_a_ajouter.append(perm)
                        except Permission.DoesNotExist:
                            pass

            groupe.permissions.set(perms_a_ajouter)

    def _creer_types_stage(self):
        for libelle in TYPES_STAGE:
            _, cree = TypeStage.objects.get_or_create(libelle=libelle)
            action = "créé" if cree else "déjà existant"
            self.stdout.write(f"  Type de stage '{libelle}' {action}.")
