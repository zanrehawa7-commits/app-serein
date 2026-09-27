import datetime
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from comptes.models import Utilisateur
from referentiels.models import Departement, Membre
from offres.models import Offre, StatutOffre
from candidatures.models import Candidat, Candidature, StatutCandidature, TypeDemande
from referentiels.models import TypeStage

from .models import Stage, StatutStage
from .services import (
    TransitionInterdite,
    constituer_stage,
    modifier_stage,
    terminer_stage,
    interrompre_stage,
    demarrer_stage_auto,
    cloturer_stage_auto,
)


# ─── Fixtures communes ────────────────────────────────────────────────────────

def _groupe(nom):
    g, _ = Group.objects.get_or_create(name=nom)
    return g


def _user(email, role):
    u = Utilisateur.objects.create_user(email=email, password="pass")
    u.groups.add(_groupe(role))
    return u


def _dept(nom="DRH"):
    return Departement.objects.create(nom=nom, actif=True)


def _membre(dept, nom="Traoré"):
    return Membre.objects.create(
        nom=nom,
        prenom="Jean",
        departement=dept,
        actif=True,
    )


def _type_stage():
    ts, _ = TypeStage.objects.get_or_create(libelle="Professionnel")
    return ts


def _candidat():
    return Candidat.objects.create(nom="Ouedraogo", prenom="Fatou", telephone="70111111")


def _candidature_accordee(dept, maitre=None):
    cand = _candidat()
    ts = _type_stage()
    c = Candidature.objects.create(
        candidat=cand,
        departement=dept,
        type_stage=ts,
        type_demande=TypeDemande.SPONTANEE,
        debut_disponibilite=datetime.date(2025, 1, 1),
        fin_disponibilite=datetime.date(2025, 12, 31),
        duree_souhaitee=3,
        statut=StatutCandidature.ACCORDEE,
    )
    return c


def _secretaire():
    return _user("sec@test.com", "Secrétaire")


def _responsable(dept):
    u = _user("resp@test.com", "Responsable")
    m = _membre(dept, "Resp")
    u.membre = m
    u.save(update_fields=["membre"])
    return u


# ─── constituer_stage ─────────────────────────────────────────────────────────


class ConstituerStageTests(TestCase):
    def setUp(self):
        self.dept = _dept()
        self.maitre = _membre(self.dept)
        self.cand = _candidature_accordee(self.dept)
        self.sec = _secretaire()

    def test_creation_a_venir(self):
        debut = timezone.localdate() + datetime.timedelta(days=10)
        fin = debut + datetime.timedelta(days=60)
        stage = constituer_stage(self.cand, debut, fin, self.maitre, self.sec)
        self.assertEqual(stage.statut, StatutStage.A_VENIR)
        self.assertEqual(stage.candidature, self.cand)

    def test_creation_en_cours_si_debut_passe(self):
        debut = timezone.localdate() - datetime.timedelta(days=5)
        fin = debut + datetime.timedelta(days=60)
        stage = constituer_stage(self.cand, debut, fin, self.maitre, self.sec)
        self.assertEqual(stage.statut, StatutStage.EN_COURS)

    def test_refuse_si_statut_pas_accordee(self):
        self.cand.statut = StatutCandidature.RECUE
        self.cand.save(update_fields=["statut"])
        debut = timezone.localdate() + datetime.timedelta(days=10)
        fin = debut + datetime.timedelta(days=30)
        with self.assertRaises(Exception):  # get_object_or_404 → Http404
            constituer_stage(self.cand, debut, fin, self.maitre, self.sec)

    def test_refuse_maitre_autre_departement(self):
        dept2 = _dept("Compta")
        autre_maitre = _membre(dept2, "Autre")
        debut = timezone.localdate() + datetime.timedelta(days=10)
        fin = debut + datetime.timedelta(days=30)
        with self.assertRaises(TransitionInterdite):
            constituer_stage(self.cand, debut, fin, autre_maitre, self.sec)

    def test_refuse_stage_deja_existant(self):
        debut = timezone.localdate() + datetime.timedelta(days=10)
        fin = debut + datetime.timedelta(days=30)
        constituer_stage(self.cand, debut, fin, self.maitre, self.sec)
        with self.assertRaises(TransitionInterdite):
            constituer_stage(self.cand, debut, fin, self.maitre, self.sec)

    def test_reset_candidat_informe(self):
        self.cand.candidat_informe = True
        self.cand.save(update_fields=["candidat_informe"])
        debut = timezone.localdate() + datetime.timedelta(days=10)
        fin = debut + datetime.timedelta(days=30)
        constituer_stage(self.cand, debut, fin, self.maitre, self.sec)
        self.cand.refresh_from_db()
        self.assertFalse(self.cand.candidat_informe)


# ─── modifier_stage ───────────────────────────────────────────────────────────


class ModifierStageTests(TestCase):
    def setUp(self):
        self.dept = _dept()
        self.maitre = _membre(self.dept)
        self.cand = _candidature_accordee(self.dept)
        self.sec = _secretaire()
        debut = timezone.localdate() + datetime.timedelta(days=10)
        fin = debut + datetime.timedelta(days=60)
        self.stage = constituer_stage(self.cand, debut, fin, self.maitre, self.sec)

    def test_modifier_date_fin(self):
        nouvelle_fin = self.stage.date_debut + datetime.timedelta(days=90)
        modifier_stage(self.stage, nouvelle_fin, self.maitre, self.sec)
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.date_fin_prevue, nouvelle_fin)

    def test_changer_maitre(self):
        nouveau = _membre(self.dept, "Nouveau")
        modifier_stage(self.stage, self.stage.date_fin_prevue, nouveau, self.sec)
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.maitre_stage, nouveau)

    def test_modifier_date_debut_si_a_venir(self):
        nouveau_debut = self.stage.date_debut + datetime.timedelta(days=3)
        modifier_stage(self.stage, self.stage.date_fin_prevue, self.maitre, self.sec, date_debut=nouveau_debut)
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.date_debut, nouveau_debut)

    def test_refuse_modifier_stage_termine(self):
        self.stage.statut = StatutStage.TERMINE
        self.stage.save(update_fields=["statut"])
        with self.assertRaises(TransitionInterdite):
            modifier_stage(self.stage, self.stage.date_fin_prevue, self.maitre, self.sec)


# ─── terminer_stage ───────────────────────────────────────────────────────────


class TerminerStageTests(TestCase):
    def setUp(self):
        self.dept = _dept()
        self.maitre = _membre(self.dept)
        self.cand = _candidature_accordee(self.dept)
        self.sec = _secretaire()
        debut = timezone.localdate() - datetime.timedelta(days=30)
        fin = timezone.localdate() + datetime.timedelta(days=30)
        self.stage = constituer_stage(self.cand, debut, fin, self.maitre, self.sec)
        # Forcer EN_COURS pour le test
        self.stage.statut = StatutStage.EN_COURS
        self.stage.save(update_fields=["statut"])
        self.resp = _responsable(self.dept)

    def test_terminer_stage(self):
        date_fin = timezone.localdate()
        terminer_stage(self.stage, date_fin, self.resp)
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.statut, StatutStage.TERMINE)
        self.assertEqual(self.stage.date_fin_reelle, date_fin)

    def test_refuse_si_date_futur(self):
        with self.assertRaises(TransitionInterdite):
            terminer_stage(self.stage, timezone.localdate() + datetime.timedelta(days=1), self.resp)

    def test_refuse_si_pas_en_cours(self):
        self.stage.statut = StatutStage.A_VENIR
        self.stage.save(update_fields=["statut"])
        with self.assertRaises(TransitionInterdite):
            terminer_stage(self.stage, timezone.localdate(), self.resp)


# ─── interrompre_stage ────────────────────────────────────────────────────────


class InterrompreStageTests(TestCase):
    def setUp(self):
        self.dept = _dept()
        self.maitre = _membre(self.dept)
        self.cand = _candidature_accordee(self.dept)
        self.sec = _secretaire()
        debut = timezone.localdate() + datetime.timedelta(days=5)
        fin = debut + datetime.timedelta(days=60)
        self.stage = constituer_stage(self.cand, debut, fin, self.maitre, self.sec)
        self.resp = _responsable(self.dept)

    def test_interrompre_a_venir(self):
        date_inter = timezone.localdate()
        interrompre_stage(self.stage, date_inter, "Abandon du stagiaire.", self.resp)
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.statut, StatutStage.INTERROMPU)
        self.assertIsNotNone(self.stage.motif_interruption)

    def test_refuse_sans_motif(self):
        with self.assertRaises(TransitionInterdite):
            interrompre_stage(self.stage, timezone.localdate(), "  ", self.resp)

    def test_refuse_si_termine(self):
        self.stage.statut = StatutStage.TERMINE
        self.stage.save(update_fields=["statut"])
        with self.assertRaises(TransitionInterdite):
            interrompre_stage(self.stage, timezone.localdate(), "raison", self.resp)


# ─── Commande automatique ─────────────────────────────────────────────────────


class DemarrerStageAutoTests(TestCase):
    def setUp(self):
        self.dept = _dept()
        self.maitre = _membre(self.dept)
        self.sec = _secretaire()

    def _stage(self, debut, fin, statut=None):
        cand = _candidature_accordee(self.dept)
        stage = constituer_stage(cand, debut, fin, self.maitre, self.sec)
        if statut and stage.statut != statut:
            stage.statut = statut
            stage.save(update_fields=["statut"])
        return stage

    def test_demarre_si_date_atteinte(self):
        debut = datetime.date(2025, 1, 1)
        fin = datetime.date(2025, 6, 30)
        stage = self._stage(debut, fin, StatutStage.A_VENIR)
        result = demarrer_stage_auto(stage, datetime.date(2025, 1, 1))
        self.assertTrue(result)
        stage.refresh_from_db()
        self.assertEqual(stage.statut, StatutStage.EN_COURS)

    def test_ne_demarre_pas_si_futur(self):
        debut = datetime.date(2099, 1, 1)
        fin = datetime.date(2099, 6, 30)
        stage = self._stage(debut, fin, StatutStage.A_VENIR)
        result = demarrer_stage_auto(stage, datetime.date(2025, 1, 1))
        self.assertFalse(result)
        stage.refresh_from_db()
        self.assertEqual(stage.statut, StatutStage.A_VENIR)


class CloturerStageAutoTests(TestCase):
    def setUp(self):
        self.dept = _dept()
        self.maitre = _membre(self.dept)
        self.sec = _secretaire()

    def _stage_en_cours(self, debut, fin):
        cand = _candidature_accordee(self.dept)
        stage = Stage.objects.create(
            candidature=cand,
            maitre_stage=self.maitre,
            date_debut=debut,
            date_fin_prevue=fin,
            statut=StatutStage.EN_COURS,
        )
        return stage

    def test_cloture_si_date_depasse(self):
        debut = datetime.date(2025, 1, 1)
        fin = datetime.date(2025, 3, 31)
        stage = self._stage_en_cours(debut, fin)
        result = cloturer_stage_auto(stage, datetime.date(2025, 4, 1))
        self.assertTrue(result)
        stage.refresh_from_db()
        self.assertEqual(stage.statut, StatutStage.TERMINE)
        self.assertEqual(stage.date_fin_reelle, fin)

    def test_ne_cloture_pas_si_date_non_atteinte(self):
        debut = datetime.date(2025, 1, 1)
        fin = datetime.date(2025, 6, 30)
        stage = self._stage_en_cours(debut, fin)
        result = cloturer_stage_auto(stage, datetime.date(2025, 3, 1))
        self.assertFalse(result)
        stage.refresh_from_db()
        self.assertEqual(stage.statut, StatutStage.EN_COURS)

    def test_serveur_arrete_a_venir_devient_termine(self):
        """Si le serveur n'a pas tourné, un stage A_VENIR dont début et fin sont passés
        doit être d'abord démarré puis clôturé dans la même exécution."""
        debut = datetime.date(2025, 1, 1)
        fin = datetime.date(2025, 3, 31)
        cand = _candidature_accordee(self.dept)
        stage = Stage.objects.create(
            candidature=cand,
            maitre_stage=self.maitre,
            date_debut=debut,
            date_fin_prevue=fin,
            statut=StatutStage.A_VENIR,
        )
        aujourd_hui = datetime.date(2025, 4, 15)
        demarrer_stage_auto(stage, aujourd_hui)
        stage.refresh_from_db()
        self.assertEqual(stage.statut, StatutStage.EN_COURS)
        cloturer_stage_auto(stage, aujourd_hui)
        stage.refresh_from_db()
        self.assertEqual(stage.statut, StatutStage.TERMINE)


# ─── Désactiver membre — maître de stage actif (Complément 5) ─────────────────


class DesactiverMembreStageActifTests(TestCase):
    def setUp(self):
        self.dept = _dept()
        self.maitre = _membre(self.dept)
        self.sec = _secretaire()
        debut = timezone.localdate() + datetime.timedelta(days=5)
        fin = debut + datetime.timedelta(days=60)
        self.cand = _candidature_accordee(self.dept)
        self.stage = constituer_stage(self.cand, debut, fin, self.maitre, self.sec)

    def test_refuse_desactiver_maitre_stage_actif(self):
        from referentiels.services import desactiver_membre
        result = desactiver_membre(self.maitre)
        self.assertFalse(result)
        self.maitre.refresh_from_db()
        self.assertTrue(self.maitre.actif)

    def test_autorise_desactiver_maitre_stage_termine(self):
        from referentiels.services import desactiver_membre
        self.stage.statut = StatutStage.TERMINE
        self.stage.save(update_fields=["statut"])
        result = desactiver_membre(self.maitre)
        self.assertTrue(result)
        self.maitre.refresh_from_db()
        self.assertFalse(self.maitre.actif)


# ─── Vues ─────────────────────────────────────────────────────────────────────


class StageListViewTests(TestCase):
    def setUp(self):
        self.dept = _dept()
        self.maitre = _membre(self.dept)
        self.sec = _secretaire()
        self.client.force_login(self.sec)

    def test_liste_accessible_secretaire(self):
        response = self.client.get(reverse("stages:stage_list"))
        self.assertEqual(response.status_code, 200)

    def test_403_pour_anonyme(self):
        self.client.logout()
        response = self.client.get(reverse("stages:stage_list"))
        # Redirige vers login
        self.assertIn(response.status_code, [302, 403])


class ConstituerStageViewTests(TestCase):
    def setUp(self):
        self.dept = _dept()
        self.maitre = _membre(self.dept)
        self.cand = _candidature_accordee(self.dept)
        self.sec = _secretaire()
        self.client.force_login(self.sec)

    def test_get_form(self):
        url = reverse("stages:stage_constituer", args=[self.cand.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_post_constitue_stage(self):
        debut = (timezone.localdate() + datetime.timedelta(days=10)).isoformat()
        fin = (timezone.localdate() + datetime.timedelta(days=70)).isoformat()
        url = reverse("stages:stage_constituer", args=[self.cand.pk])
        response = self.client.post(url, {
            "date_debut": debut,
            "date_fin_prevue": fin,
            "maitre_stage": self.maitre.pk,
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(Stage.objects.count(), 1)

    def test_responsable_ne_peut_pas_constituer(self):
        resp = _responsable(self.dept)
        self.client.force_login(resp)
        url = reverse("stages:stage_constituer", args=[self.cand.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)
