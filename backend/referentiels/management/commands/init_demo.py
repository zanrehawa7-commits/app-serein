"""
Commande de démo : crée les comptes et données minimales pour tester l'application.
Idempotente — peut être relancée sans risque de doublon.

Usage :
    python manage.py init_donnees   # d'abord (groupes + types de stage)
    python manage.py init_demo      # ensuite (comptes + département démo)

Comptes créés :
    admin@serein.bf   / Admin1234!   -> Administrateur
    sec@serein.bf     / Sec1234!     -> Secrétaire
    resp@serein.bf    / Resp1234!    -> Responsable (département Informatique)
"""
from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from comptes.models import Utilisateur
from referentiels.models import Departement, Personnel


COMPTES_DEMO = [
    {
        "email": "admin@serein.bf",
        "password": "Admin1234!",
        "first_name": "Admin",
        "last_name": "Serein",
        "groupe": "Administrateur",
        "personnel": None,
    },
    {
        "email": "sec@serein.bf",
        "password": "Sec1234!",
        "first_name": "Marie",
        "last_name": "Koné",
        "groupe": "Secrétaire",
        "personnel": None,
    },
    {
        "email": "resp@serein.bf",
        "password": "Resp1234!",
        "first_name": "Paul",
        "last_name": "Traoré",
        "groupe": "Responsable",
        "personnel": {"nom": "Traoré", "prenom": "Paul", "departement": "Informatique"},
    },
]


class Command(BaseCommand):
    help = "Crée les comptes et données de démonstration (idempotent)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError(
                "init_demo est réservé au développement. "
                "Refus d'exécution car DEBUG=False."
            )
        self._verifier_groupes()
        self._creer_comptes()
        self.stdout.write(self.style.SUCCESS("\nDonnées de démo prêtes. Identifiants :"))
        self.stdout.write("  admin@serein.bf  /  Admin1234!  -> Administrateur")
        self.stdout.write("  sec@serein.bf    /  Sec1234!    -> Secrétaire")
        self.stdout.write("  resp@serein.bf   /  Resp1234!   -> Responsable")

    def _verifier_groupes(self):
        manquants = [
            g for g in ["Administrateur", "Secrétaire", "Responsable"]
            if not Group.objects.filter(name=g).exists()
        ]
        if manquants:
            self.stdout.write(self.style.WARNING(
                f"Groupes manquants : {manquants}. Lance d'abord : python manage.py init_donnees"
            ))

    def _creer_comptes(self):
        for data in COMPTES_DEMO:
            user, cree = Utilisateur.objects.get_or_create(
                email=data["email"],
                defaults={
                    "first_name": data["first_name"],
                    "last_name": data["last_name"],
                    "is_active": True,
                },
            )
            if cree:
                user.set_password(data["password"])

            # Forcer le mot de passe à jour même si le compte existait déjà
            if not cree:
                user.first_name = data["first_name"]
                user.last_name = data["last_name"]
                user.set_password(data["password"])

            # Personnel + département pour le Responsable
            if data["personnel"] and not user.personnel:
                dept, _ = Departement.objects.get_or_create(
                    nom=data["personnel"]["departement"],
                    defaults={"actif": True},
                )
                personnel, _ = Personnel.objects.get_or_create(
                    nom=data["personnel"]["nom"],
                    prenom=data["personnel"]["prenom"],
                    departement=dept,
                    defaults={"actif": True},
                )
                user.personnel = personnel
                # Désigner comme responsable du département
                dept.responsable = personnel
                dept.save(update_fields=["responsable"])

            user.save()

            # Groupe
            try:
                groupe = Group.objects.get(name=data["groupe"])
                user.groups.set([groupe])
            except Group.DoesNotExist:
                pass

            action = "créé" if cree else "mis à jour"
            self.stdout.write(f"  [{data['groupe']}] {data['email']} — {action}.")
