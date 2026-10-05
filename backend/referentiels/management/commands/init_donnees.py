from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand

from comptes.models import ProfilRole
from comptes.permissions import APPS_LECTURE_SEULE_ADMINISTRATEUR
from referentiels.models import TypeStage


_CRUD = ["add", "change", "delete", "view"]

# Format : "app" → toutes les modèles de l'app ; "app.modele" → modèle spécifique
GROUPES_PERMISSIONS = {
    "Administrateur": {
        "comptes": _CRUD,
        "referentiels": _CRUD,
        **{app: ["view"] for app in APPS_LECTURE_SEULE_ADMINISTRATEUR},
    },
    "Secrétaire": {
        "offres.besoin": ["view"],
        "offres.offre": _CRUD,
        "offres.publication": _CRUD,
        "candidatures.candidat": _CRUD,
        "candidatures.candidature": ["add", "change", "view"],
        "candidatures.piecejointe": ["add", "change", "delete", "view"],
        "stages.stage": ["add", "change", "view"],
        "referentiels": ["view"],
    },
    "Responsable": {
        "offres.besoin": ["add", "change", "view"],
        "offres.offre": ["view"],
        "candidatures.candidature": ["change", "view"],
        "candidatures.candidat": ["view"],
        "stages": ["add", "change", "view"],
        "referentiels": ["view"],
    },
}

# Libellé → (durée min, durée max) en mois. Mêmes valeurs que la migration
# referentiels/0004 : sur une base neuve, aucune ligne n'existe à compléter.
TYPES_STAGE = {
    "Stage de perfectionnement": (1, 3),
    "Stage professionnel": (1, 6),
    "Stage de géomètre expert": (3, 12),
    "Stage d'immersion": (1, 2),
    "Stage de fin d'études": (3, 6),
}


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
            ProfilRole.objects.update_or_create(groupe=groupe, defaults={"est_systeme": True, "actif": True})

            perms_a_ajouter = []
            for cle, actions in apps_perms.items():
                if "." in cle:
                    # Format "app.modele" : une seule ContentType
                    app_label, model_name = cle.split(".", 1)
                    try:
                        ct = ContentType.objects.get(app_label=app_label, model=model_name)
                        for action_perm in actions:
                            codename = f"{action_perm}_{model_name}"
                            perm = Permission.objects.filter(content_type=ct, codename=codename).first()
                            if perm:
                                perms_a_ajouter.append(perm)
                    except ContentType.DoesNotExist:
                        self.stdout.write(self.style.WARNING(f"    ContentType '{cle}' introuvable — ignoré."))
                else:
                    # Format "app" : toutes les modèles de l'application
                    cts = ContentType.objects.filter(app_label=cle)
                    for ct in cts:
                        for action_perm in actions:
                            codename = f"{action_perm}_{ct.model}"
                            perm = Permission.objects.filter(content_type=ct, codename=codename).first()
                            if perm:
                                perms_a_ajouter.append(perm)

            groupe.permissions.set(perms_a_ajouter)
            self.stdout.write(f"    {len(perms_a_ajouter)} permission(s) attribuée(s).")

    def _creer_types_stage(self):
        for libelle, (duree_min, duree_max) in TYPES_STAGE.items():
            # Les durées existantes ne sont jamais écrasées : l'admin a pu les modifier.
            _, cree = TypeStage.objects.get_or_create(
                libelle=libelle,
                defaults={"duree_min_mois": duree_min, "duree_max_mois": duree_max},
            )
            action = "créé" if cree else "déjà existant"
            self.stdout.write(f"  Type de stage '{libelle}' {action}.")
