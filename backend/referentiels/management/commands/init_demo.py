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

Scénarios de recette des alertes (RG-S15), département Informatique, dates recalculées à chaque
lancement (alertes remises à zéro) : un cas de chaque alerte a) à e), dont un stage « À venir »
démarrable aujourd'hui. Ensuite : python manage.py alerter_echeances
"""
import datetime

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from django.utils import timezone

from candidatures.models import Candidat, Candidature, StatutCandidature, TypeDemande
from comptes.models import Utilisateur
from referentiels.models import Departement, Personnel, TypeStage
from stages.models import AffectationMaitreStage, Stage, StatutStage


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
        self._creer_scenarios_alertes()
        self.stdout.write(self.style.SUCCESS("\nDonnées de démo prêtes. Identifiants :"))
        self.stdout.write("  admin@serein.bf  /  Admin1234!  -> Administrateur")
        self.stdout.write("  sec@serein.bf    /  Sec1234!    -> Secrétaire")
        self.stdout.write("  resp@serein.bf   /  Resp1234!   -> Responsable")
        self.stdout.write("Alertes de démo : python manage.py alerter_echeances")

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

    # (téléphone, nom, statut candidature, décalages dispo début/fin, stage : statut, début, fin, fin réelle)
    SCENARIOS = [
        ("79000001", "Démarrable", StatutCandidature.ACCORDEE, -30, 120, (StatutStage.A_VENIR, 0, 90, None)),
        ("79000002", "ÀTerminer", StatutCandidature.ACCORDEE, -90, 120, (StatutStage.EN_COURS, -60, 2, None)),
        ("79000003", "DispoExpire", StatutCandidature.RECUE, -30, 2, None),
        ("79000004", "SansStage", StatutCandidature.ACCORDEE, -30, 3, None),
        ("79000005", "ÀÉvaluer", StatutCandidature.ACCORDEE, -150, 120, (StatutStage.TERMINE, -120, -8, -8)),
    ]

    def _creer_scenarios_alertes(self):
        """Un cas de chaque alerte a) à e) ; idempotent (dates réalignées, alertes remises à zéro)."""
        dept = Departement.objects.filter(nom="Informatique").first()
        type_stage = TypeStage.objects.filter(libelle="Stage professionnel").first()
        if dept is None or type_stage is None:
            self.stdout.write(self.style.WARNING("Scénarios d'alertes ignorés : lance d'abord init_donnees."))
            return
        maitre, _ = Personnel.objects.get_or_create(
            nom="Zongo", prenom="Démo", defaults={"departement": dept, "actif": True, "fonction": "Maître de stage"},
        )
        jour = timezone.localdate()
        decaler = lambda n: jour + datetime.timedelta(days=n)  # noqa: E731
        for telephone, nom, statut, dispo_debut, dispo_fin, stage in self.SCENARIOS:
            candidat, _ = Candidat.objects.get_or_create(
                telephone=telephone, defaults={"nom": nom, "prenom": "Démo"},
            )
            valeurs = {
                "departement": dept, "type_stage": type_stage, "type_demande": TypeDemande.SPONTANEE,
                "offre": None, "statut": statut, "duree_souhaitee": 3,
                "debut_disponibilite": decaler(dispo_debut), "fin_disponibilite": decaler(dispo_fin),
                "alerte_disponibilite_envoyee": False, "alerte_disponibilite_stage_envoyee": False,
            }
            cand = Candidature.objects.filter(candidat=candidat).first()
            if cand is None:
                cand = Candidature.objects.create(candidat=candidat, **valeurs)
            else:
                Candidature.objects.filter(pk=cand.pk).update(**valeurs)
            if stage is None:
                continue
            statut_stage, debut, fin, fin_reelle = stage
            st, cree = Stage.objects.update_or_create(candidature=cand, defaults={
                "maitre_stage": maitre, "statut": statut_stage,
                "date_debut": decaler(debut), "date_fin_prevue": decaler(fin),
                "date_fin_reelle": decaler(fin_reelle) if fin_reelle is not None else None,
                "note": None, "vivier": False, "date_evaluation": None,
                "alerte_demarrage_envoyee": False, "alerte_fin_envoyee": False, "rappel_evaluation_envoye": False,
            })
            if cree:
                AffectationMaitreStage.objects.create(stage=st, maitre_stage=maitre)
        self.stdout.write(f"  Scénarios d'alertes prêts ({len(self.SCENARIOS)} cas, département {dept}).")
