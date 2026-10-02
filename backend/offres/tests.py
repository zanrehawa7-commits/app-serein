from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from comptes.models import Utilisateur
from referentiels.models import CanalPublication, Departement, Personnel, TypeStage

from .models import Besoin, Offre, Publication, StatutBesoin, StatutOffre
from .services import (
    TransitionInterdite,
    annuler_besoin,
    creer_besoin,
    creer_offre,
    fermer_offre,
    ouvrir_offre,
    rouvrir_offre,
    supprimer_offre,
    suspendre_offre,
)


def _user(email, groupe=None, is_superuser=False):
    u = Utilisateur.objects.create_user(
        email=email, password="pass1234!",
        first_name="Test", last_name="User",
        is_superuser=is_superuser,
    )
    if groupe:
        grp, _ = Group.objects.get_or_create(name=groupe)
        u.groups.add(grp)
    return u


def _besoin(departement, type_stage):
    return Besoin.objects.create(
        departement=departement,
        type_stage=type_stage,
        date_debut="2027-01-01",
        date_fin="2027-06-30",
        profil_recherche="Profil test",
        nombre_places=2,
        statut=StatutBesoin.ENVOYE,
    )


class TransitionsBesoinTests(TestCase):
    def setUp(self):
        self.dept = Departement.objects.create(nom="Dept Test")
        self.ts = TypeStage.objects.create(libelle="Stage test", duree_min_mois=1, duree_max_mois=6)
        self.secretaire = _user("sec@serein.bf", groupe="Secrétaire")
        self.responsable = _user("resp@serein.bf", groupe="Responsable")
        membre = Personnel.objects.create(nom="Doe", prenom="Jane", departement=self.dept)
        self.responsable.personnel = membre
        self.responsable.save()

    def test_creer_besoin_statut_envoye(self):
        """Un besoin créé est toujours au statut ENVOYÉ."""
        besoin = creer_besoin(
            departement=self.dept,
            type_stage=self.ts,
            date_debut="2027-01-01",
            date_fin="2027-06-30",
            profil_recherche="Profil test",
            nombre_places=2,
            utilisateur=self.responsable,
        )
        self.assertEqual(besoin.statut, StatutBesoin.ENVOYE)

    def test_creer_besoin_historique(self):
        """La création d'un besoin enregistre un historique."""
        from suivi.models import Historique
        besoin = creer_besoin(
            departement=self.dept, type_stage=self.ts,
            date_debut="2027-01-01", date_fin="2027-06-30",
            profil_recherche="Profil", nombre_places=1,
            utilisateur=self.responsable,
        )
        self.assertTrue(Historique.objects.filter(object_id=besoin.pk).exists())

    def test_creer_besoin_notifie_secretaire(self):
        """La création d'un besoin génère une notification pour la secrétaire."""
        from suivi.models import Notification
        creer_besoin(
            departement=self.dept, type_stage=self.ts,
            date_debut="2027-01-01", date_fin="2027-06-30",
            profil_recherche="Profil", nombre_places=1,
            utilisateur=self.responsable,
        )
        self.assertTrue(Notification.objects.filter(destinataire=self.secretaire).exists())

    def test_annuler_besoin_envoye(self):
        """Un besoin ENVOYÉ peut être annulé."""
        besoin = _besoin(self.dept, self.ts)
        annuler_besoin(besoin, self.responsable)
        besoin.refresh_from_db()
        self.assertEqual(besoin.statut, StatutBesoin.ANNULE)

    def test_annuler_besoin_cloture_refuse(self):
        """Un besoin CLÔTURÉ ne peut pas être annulé."""
        besoin = _besoin(self.dept, self.ts)
        besoin.statut = StatutBesoin.CLOTURE
        besoin.save()
        with self.assertRaises(TransitionInterdite):
            annuler_besoin(besoin, self.responsable)

    def test_annuler_besoin_notifie_secretaire(self):
        """L'annulation d'un besoin génère une notification pour la secrétaire."""
        from suivi.models import Notification
        besoin = _besoin(self.dept, self.ts)
        nb_avant = Notification.objects.filter(destinataire=self.secretaire).count()
        annuler_besoin(besoin, self.responsable)
        self.assertGreater(
            Notification.objects.filter(destinataire=self.secretaire).count(),
            nb_avant,
        )


class TransitionsOffreTests(TestCase):
    def setUp(self):
        self.dept = Departement.objects.create(nom="Dept Test")
        self.ts = TypeStage.objects.create(libelle="Stage test", duree_min_mois=1, duree_max_mois=6)
        self.secretaire = _user("sec@serein.bf", groupe="Secrétaire")
        self.offre = Offre.objects.create(
            type_stage=self.ts,
            titre="Offre Test",
            description="Description",
            profil_recherche="Profil",
            date_debut="2027-01-01",
            date_fin="2027-06-30",
            nombre_places=2,
            statut=StatutOffre.BROUILLON,
        )

    def test_ouvrir_offre_brouillon(self):
        ouvrir_offre(self.offre, self.secretaire)
        self.offre.refresh_from_db()
        self.assertEqual(self.offre.statut, StatutOffre.OUVERTE)

    def test_ouvrir_offre_deja_ouverte_refuse(self):
        self.offre.statut = StatutOffre.OUVERTE
        self.offre.save()
        with self.assertRaises(TransitionInterdite):
            ouvrir_offre(self.offre, self.secretaire)

    def test_suspendre_offre_ouverte(self):
        self.offre.statut = StatutOffre.OUVERTE
        self.offre.save()
        suspendre_offre(self.offre, self.secretaire)
        self.offre.refresh_from_db()
        self.assertEqual(self.offre.statut, StatutOffre.SUSPENDUE)

    def test_suspendre_offre_brouillon_refuse(self):
        with self.assertRaises(TransitionInterdite):
            suspendre_offre(self.offre, self.secretaire)

    def test_rouvrir_offre_suspendue(self):
        self.offre.statut = StatutOffre.SUSPENDUE
        self.offre.save()
        rouvrir_offre(self.offre, self.secretaire)
        self.offre.refresh_from_db()
        self.assertEqual(self.offre.statut, StatutOffre.OUVERTE)

    def test_fermer_offre_ouverte(self):
        self.offre.statut = StatutOffre.OUVERTE
        self.offre.save()
        fermer_offre(self.offre, self.secretaire)
        self.offre.refresh_from_db()
        self.assertEqual(self.offre.statut, StatutOffre.FERMEE)

    def test_fermer_offre_suspendue(self):
        self.offre.statut = StatutOffre.SUSPENDUE
        self.offre.save()
        fermer_offre(self.offre, self.secretaire)
        self.offre.refresh_from_db()
        self.assertEqual(self.offre.statut, StatutOffre.FERMEE)

    def test_supprimer_offre_brouillon(self):
        pk = self.offre.pk
        supprimer_offre(self.offre, self.secretaire)
        self.assertFalse(Offre.objects.filter(pk=pk).exists())

    def test_supprimer_offre_ouverte_refuse(self):
        self.offre.statut = StatutOffre.OUVERTE
        self.offre.save()
        with self.assertRaises(TransitionInterdite):
            supprimer_offre(self.offre, self.secretaire)

    def test_transitions_enregistrent_historique(self):
        """Chaque transition enregistre un historique."""
        from suivi.models import Historique
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Offre)
        nb_avant = Historique.objects.filter(content_type=ct, object_id=self.offre.pk).count()
        ouvrir_offre(self.offre, self.secretaire)
        self.assertGreater(
            Historique.objects.filter(content_type=ct, object_id=self.offre.pk).count(),
            nb_avant,
        )


class CreerOffreDepuisBesoinTests(TestCase):
    """Création d'une offre liée à un besoin : transition atomique + select_for_update."""

    def setUp(self):
        self.dept = Departement.objects.create(nom="Dept Test")
        self.ts = TypeStage.objects.create(libelle="Stage test", duree_min_mois=1, duree_max_mois=6)
        self.secretaire = _user("sec@serein.bf", groupe="Secrétaire")

    def test_creer_offre_depuis_besoin_pris_en_charge(self):
        """Lier une offre à un besoin ENVOYÉ doit le passer en PRIS_EN_CHARGE."""
        besoin = _besoin(self.dept, self.ts)
        offre = creer_offre(
            type_stage=self.ts, titre="Offre Liée", description="Desc",
            profil_recherche="Profil", date_debut="2027-01-01", date_fin="2027-06-30",
            nombre_places=2, utilisateur=self.secretaire, besoin=besoin,
        )
        besoin.refresh_from_db()
        self.assertEqual(besoin.statut, StatutBesoin.PRIS_EN_CHARGE)
        self.assertEqual(offre.besoin, besoin)

    def test_double_creation_offre_meme_besoin_refuse(self):
        """Créer deux offres sur le même besoin : la seconde doit lever TransitionInterdite."""
        besoin = _besoin(self.dept, self.ts)
        creer_offre(
            type_stage=self.ts, titre="Offre 1", description="D1",
            profil_recherche="P1", date_debut="2027-01-01", date_fin="2027-06-30",
            nombre_places=2, utilisateur=self.secretaire, besoin=besoin,
        )
        besoin.refresh_from_db()
        with self.assertRaises(TransitionInterdite):
            creer_offre(
                type_stage=self.ts, titre="Offre 2", description="D2",
                profil_recherche="P2", date_debut="2027-01-01", date_fin="2027-06-30",
                nombre_places=2, utilisateur=self.secretaire, besoin=besoin,
            )

    def test_creer_offre_besoin_pris_en_charge_refuse(self):
        """Lier une offre à un besoin déjà PRIS_EN_CHARGE doit lever TransitionInterdite."""
        besoin = _besoin(self.dept, self.ts)
        besoin.statut = StatutBesoin.PRIS_EN_CHARGE
        besoin.save()
        with self.assertRaises(TransitionInterdite):
            creer_offre(
                type_stage=self.ts, titre="Offre X", description="D",
                profil_recherche="P", date_debut="2027-01-01", date_fin="2027-06-30",
                nombre_places=2, utilisateur=self.secretaire, besoin=besoin,
            )


class AccesVuesBesoinTests(TestCase):
    """Tests d'accès aux vues besoin par rôle."""

    def setUp(self):
        self.dept = Departement.objects.create(nom="Dept A")
        self.dept_b = Departement.objects.create(nom="Dept B")
        self.ts = TypeStage.objects.create(libelle="Stage test", duree_min_mois=1, duree_max_mois=6)
        self.admin = _user("admin@serein.bf", is_superuser=True)
        self.secretaire = _user("sec@serein.bf", groupe="Secrétaire")
        membre = Personnel.objects.create(nom="Doe", prenom="Jane", departement=self.dept)
        self.responsable = _user("resp@serein.bf", groupe="Responsable")
        self.responsable.personnel = membre
        self.responsable.save()
        self.besoin = _besoin(self.dept, self.ts)
        self.besoin_autre = _besoin(self.dept_b, self.ts)

    def test_liste_besoins_accessible_tous_roles(self):
        for user in [self.admin, self.secretaire, self.responsable]:
            with self.subTest(role=user.role):
                self.client.force_login(user)
                resp = self.client.get(reverse("offres:besoin_list"))
                self.assertEqual(resp.status_code, 200)

    def test_responsable_voit_uniquement_son_departement(self):
        self.client.force_login(self.responsable)
        resp = self.client.get(reverse("offres:besoin_list"))
        besoins = list(resp.context["besoins"])
        self.assertIn(self.besoin, besoins)
        self.assertNotIn(self.besoin_autre, besoins)

    def test_responsable_autre_dept_403(self):
        """Le responsable n'a pas accès au détail d'un besoin d'un autre département."""
        self.client.force_login(self.responsable)
        resp = self.client.get(reverse("offres:besoin_detail", kwargs={"pk": self.besoin_autre.pk}))
        self.assertEqual(resp.status_code, 403)

    def test_creer_besoin_secretaire_403(self):
        self.client.force_login(self.secretaire)
        resp = self.client.get(reverse("offres:besoin_creer"))
        self.assertEqual(resp.status_code, 403)

    def test_creer_besoin_admin_403(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("offres:besoin_creer"))
        self.assertEqual(resp.status_code, 403)

    def test_creer_besoin_responsable_sans_membre_403(self):
        resp_sans_membre = _user("resp2@serein.bf", groupe="Responsable")
        self.client.force_login(resp_sans_membre)
        resp = self.client.get(reverse("offres:besoin_creer"))
        self.assertEqual(resp.status_code, 403)


class AccesVuesOffreTests(TestCase):
    """Tests d'accès aux vues offre par rôle."""

    def setUp(self):
        self.dept = Departement.objects.create(nom="Dept A")
        self.ts = TypeStage.objects.create(libelle="Stage test", duree_min_mois=1, duree_max_mois=6)
        self.admin = _user("admin@serein.bf", is_superuser=True)
        self.secretaire = _user("sec@serein.bf", groupe="Secrétaire")
        self.responsable = _user("resp@serein.bf", groupe="Responsable")
        self.offre = Offre.objects.create(
            type_stage=self.ts, titre="Test", description="D",
            profil_recherche="P", date_debut="2027-01-01", date_fin="2027-06-30",
            nombre_places=2, statut=StatutOffre.BROUILLON,
        )

    def test_liste_offres_accessible_tous(self):
        for user in [self.admin, self.secretaire, self.responsable]:
            with self.subTest(role=user.role):
                self.client.force_login(user)
                resp = self.client.get(reverse("offres:offre_list"))
                self.assertEqual(resp.status_code, 200)

    def test_creer_offre_secretaire_ok(self):
        self.client.force_login(self.secretaire)
        resp = self.client.get(reverse("offres:offre_creer"))
        self.assertEqual(resp.status_code, 200)

    def test_creer_offre_responsable_403(self):
        self.client.force_login(self.responsable)
        resp = self.client.get(reverse("offres:offre_creer"))
        self.assertEqual(resp.status_code, 403)

    def test_creer_offre_admin_403(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("offres:offre_creer"))
        self.assertEqual(resp.status_code, 403)

    def test_transition_ouvrir_via_vue(self):
        """La vue offre_ouvrir passe l'offre de BROUILLON à OUVERTE."""
        self.client.force_login(self.secretaire)
        self.client.post(reverse("offres:offre_ouvrir", kwargs={"pk": self.offre.pk}))
        self.offre.refresh_from_db()
        self.assertEqual(self.offre.statut, StatutOffre.OUVERTE)

    def test_transition_ouvrir_deja_ouverte_message_erreur(self):
        """Tenter d'ouvrir une offre déjà ouverte → message d'erreur, pas d'exception."""
        self.offre.statut = StatutOffre.OUVERTE
        self.offre.save()
        self.client.force_login(self.secretaire)
        resp = self.client.post(
            reverse("offres:offre_ouvrir", kwargs={"pk": self.offre.pk}),
            follow=True,
        )
        self.assertEqual(resp.status_code, 200)
        msgs = [str(m) for m in resp.context["messages"]]
        self.assertTrue(any("impossible" in m.lower() or "statut" in m.lower() for m in msgs))

    def test_supprimer_offre_non_brouillon_message_erreur(self):
        """Supprimer une offre ouverte redirige avec message d'erreur."""
        self.offre.statut = StatutOffre.OUVERTE
        self.offre.save()
        self.client.force_login(self.secretaire)
        resp = self.client.post(
            reverse("offres:offre_supprimer", kwargs={"pk": self.offre.pk}),
            follow=True,
        )
        self.assertTrue(Offre.objects.filter(pk=self.offre.pk).exists())
        msgs = [str(m) for m in resp.context["messages"]]
        self.assertTrue(any("brouillon" in m.lower() for m in msgs))


# ─── Lot B — Validation durée Besoin/Offre ────────────────────────────────────


class DureeBesoinTests(TestCase):
    """creer_besoin et BesoinForm valident la durée selon duree_min/max du TypeStage."""

    def setUp(self):
        self.dept = Departement.objects.create(nom="Dept Test")
        self.ts = TypeStage.objects.create(
            libelle="Stage pro", duree_min_mois=2, duree_max_mois=5
        )
        self.secretaire = _user("sec@serein.bf", groupe="Secrétaire")
        self.responsable = _user("resp@serein.bf", groupe="Responsable")
        membre = Personnel.objects.create(nom="Doe", prenom="J", departement=self.dept)
        self.responsable.personnel = membre
        self.responsable.save()

    def test_duree_valide_service(self):
        """3 mois avec min=2, max=5 → OK."""
        from commun.utils import ajouter_mois
        from datetime import date
        debut = date(2027, 1, 1)
        fin = ajouter_mois(debut, 3)
        besoin = creer_besoin(
            departement=self.dept, type_stage=self.ts,
            date_debut=debut, date_fin=fin,
            profil_recherche="Profil", nombre_places=1,
            utilisateur=self.responsable,
        )
        self.assertIsNotNone(besoin.pk)

    def test_duree_trop_courte_service(self):
        """1 mois avec min=2 → TransitionInterdite."""
        from commun.utils import ajouter_mois
        from datetime import date
        debut = date(2027, 1, 1)
        fin = ajouter_mois(debut, 1)
        with self.assertRaises(TransitionInterdite):
            creer_besoin(
                departement=self.dept, type_stage=self.ts,
                date_debut=debut, date_fin=fin,
                profil_recherche="Profil", nombre_places=1,
                utilisateur=self.responsable,
            )

    def test_duree_trop_longue_service(self):
        """6 mois avec max=5 → TransitionInterdite."""
        from commun.utils import ajouter_mois
        from datetime import date
        debut = date(2027, 1, 1)
        fin = ajouter_mois(debut, 6)
        with self.assertRaises(TransitionInterdite):
            creer_besoin(
                departement=self.dept, type_stage=self.ts,
                date_debut=debut, date_fin=fin,
                profil_recherche="Profil", nombre_places=1,
                utilisateur=self.responsable,
            )

    def test_duree_trop_courte_formulaire(self):
        from offres.forms import BesoinForm
        data = {
            "departement": self.dept.pk,
            "type_stage": self.ts.pk,
            "date_debut": "2027-01-01",
            "date_fin": "2027-01-31",  # < 2 mois
            "profil_recherche": "Profil",
            "nombre_places": 1,
        }
        form = BesoinForm(data)
        self.assertFalse(form.is_valid())
        self.assertTrue(form.non_field_errors())

    def test_duree_valide_formulaire(self):
        from offres.forms import BesoinForm
        data = {
            "departement": self.dept.pk,
            "type_stage": self.ts.pk,
            "date_debut": "2027-01-01",
            "date_fin": "2027-04-01",  # 3 mois ✓
            "profil_recherche": "Profil",
            "nombre_places": 1,
        }
        form = BesoinForm(data)
        self.assertTrue(form.is_valid(), msg=str(form.errors))
