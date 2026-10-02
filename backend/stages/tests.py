import datetime
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from comptes.models import Utilisateur
from referentiels.models import Departement, Personnel
from offres.models import Offre, StatutOffre
from candidatures.models import Candidat, Candidature, StatutCandidature, TypeDemande
from referentiels.models import TypeStage

from .models import Stage, StatutStage, AffectationMaitreStage
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
    return Personnel.objects.create(
        nom=nom,
        prenom="Jean",
        departement=dept,
        actif=True,
    )


def _type_stage():
    ts, _ = TypeStage.objects.get_or_create(
        libelle="Professionnel",
        defaults={"duree_min_mois": 1, "duree_max_mois": 6},
    )
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
    u.personnel = m
    u.save(update_fields=["personnel"])
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


class DesactiverPersonnelStageActifTests(TestCase):
    def setUp(self):
        self.dept = _dept()
        self.maitre = _membre(self.dept)
        self.sec = _secretaire()
        debut = timezone.localdate() + datetime.timedelta(days=5)
        fin = debut + datetime.timedelta(days=60)
        self.cand = _candidature_accordee(self.dept)
        self.stage = constituer_stage(self.cand, debut, fin, self.maitre, self.sec)

    def test_refuse_desactiver_maitre_stage_actif(self):
        from referentiels.services import desactiver_personnel
        result = desactiver_personnel(self.maitre)
        self.assertFalse(result)
        self.maitre.refresh_from_db()
        self.assertTrue(self.maitre.actif)

    def test_autorise_desactiver_maitre_stage_termine(self):
        from referentiels.services import desactiver_personnel
        self.stage.statut = StatutStage.TERMINE
        self.stage.save(update_fields=["statut"])
        result = desactiver_personnel(self.maitre)
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


# ─── Évaluation ───────────────────────────────────────────────────────────────

from .services import evaluer_stage, peut_evaluer


def _stage_termine(dept, maitre, sec):
    """Crée un stage au statut TERMINÉ."""
    cand = _candidature_accordee(dept)
    debut = datetime.date(2025, 1, 10)
    fin = datetime.date(2025, 4, 10)
    stage = Stage.objects.create(
        candidature=cand,
        maitre_stage=maitre,
        date_debut=debut,
        date_fin_prevue=fin,
        date_fin_reelle=fin,
        statut=StatutStage.TERMINE,
    )
    return stage


class PeutEvaluerTests(TestCase):
    def setUp(self):
        self.dept = _dept("PeutEvalDept")
        self.maitre = _membre(self.dept, "MaitrePE")
        self.sec = _secretaire()
        self.stage = _stage_termine(self.dept, self.maitre, self.sec)

    def test_peut_evaluer_stage_termine_sans_note(self):
        peut, _ = peut_evaluer(self.stage)
        self.assertTrue(peut)

    def test_ne_peut_pas_evaluer_stage_non_termine(self):
        self.stage.statut = StatutStage.EN_COURS
        self.stage.save(update_fields=["statut"])
        peut, _ = peut_evaluer(self.stage)
        self.assertFalse(peut)

    def test_peut_evaluer_dans_30j(self):
        self.stage.date_evaluation = datetime.date(2025, 4, 1)
        self.stage.save(update_fields=["date_evaluation"])
        # 15 jours après = encore dans la fenêtre
        peut, date_v = peut_evaluer(self.stage, aujourd_hui=datetime.date(2025, 4, 16))
        self.assertTrue(peut)
        self.assertIsNotNone(date_v)

    def test_verouille_apres_30j(self):
        self.stage.date_evaluation = datetime.date(2025, 4, 1)
        self.stage.save(update_fields=["date_evaluation"])
        # 31 jours après = verrouillé
        peut, _ = peut_evaluer(self.stage, aujourd_hui=datetime.date(2025, 5, 2))
        self.assertFalse(peut)


class EvaluerStageTests(TestCase):
    def setUp(self):
        self.dept = _dept("EvalDept")
        self.maitre = _membre(self.dept, "MaitreEV")
        self.sec = _secretaire()
        self.resp = _responsable(self.dept)
        self.stage = _stage_termine(self.dept, self.maitre, self.sec)

    def test_evaluer_note_valide(self):
        evaluer_stage(self.stage, note=15, vivier=False, utilisateur=self.resp)
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.note, 15)
        self.assertFalse(self.stage.vivier)
        self.assertIsNotNone(self.stage.date_evaluation)

    def test_evaluer_avec_vivier(self):
        evaluer_stage(self.stage, note=16, vivier=True, utilisateur=self.resp)
        self.stage.refresh_from_db()
        self.assertTrue(self.stage.vivier)

    def test_vivier_interdit_si_note_insuffisante(self):
        with self.assertRaises(TransitionInterdite):
            evaluer_stage(self.stage, note=10, vivier=True, utilisateur=self.resp)

    def test_note_hors_plage(self):
        with self.assertRaises(TransitionInterdite):
            evaluer_stage(self.stage, note=21, vivier=False, utilisateur=self.resp)

    def test_refuse_si_non_termine(self):
        self.stage.statut = StatutStage.EN_COURS
        self.stage.save(update_fields=["statut"])
        with self.assertRaises(TransitionInterdite):
            evaluer_stage(self.stage, note=15, vivier=False, utilisateur=self.resp)

    def test_refuse_apres_verrou_30j(self):
        self.stage.date_evaluation = datetime.date(2025, 3, 1)
        self.stage.save(update_fields=["date_evaluation"])
        with self.assertRaises(TransitionInterdite):
            evaluer_stage(
                self.stage, note=14, vivier=False, utilisateur=self.resp,
                aujourd_hui=datetime.date(2025, 4, 10),  # +40j
            )

    def test_modification_dans_fenetre_30j(self):
        evaluer_stage(
            self.stage, note=14, vivier=False, utilisateur=self.resp,
            aujourd_hui=datetime.date(2025, 4, 15),
        )
        # Nouvelle évaluation dans les 30j
        evaluer_stage(
            self.stage, note=16, vivier=True, utilisateur=self.resp,
            aujourd_hui=datetime.date(2025, 4, 20),
        )
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.note, 16)


class EvaluerStageViewTests(TestCase):
    def setUp(self):
        self.dept = _dept("EvalViewDept")
        self.maitre = _membre(self.dept, "MaitreView")
        self.sec = _secretaire()
        self.resp = _responsable(self.dept)
        self.stage = _stage_termine(self.dept, self.maitre, self.sec)

    def test_get_form_responsable(self):
        self.client.force_login(self.resp)
        url = reverse("stages:stage_evaluer", args=[self.stage.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_403_secretaire(self):
        self.client.force_login(self.sec)
        url = reverse("stages:stage_evaluer", args=[self.stage.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_post_evaluer(self):
        self.client.force_login(self.resp)
        url = reverse("stages:stage_evaluer", args=[self.stage.pk])
        response = self.client.post(url, {"note": 17, "vivier": True})
        self.assertEqual(response.status_code, 302)
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.note, 17)
        self.assertTrue(self.stage.vivier)

    def test_responsable_autre_dept_403(self):
        dept2 = _dept("AutreDeptEval")
        resp2 = _user("resp2eval@test.com", "Responsable")
        m2 = _membre(dept2, "RespM2Eval")
        resp2.personnel = m2
        resp2.save(update_fields=["personnel"])
        self.client.force_login(resp2)
        url = reverse("stages:stage_evaluer", args=[self.stage.pk])
        # Devrait retourner 404 (statut TERMINE requis OU 403)
        response = self.client.get(url)
        self.assertIn(response.status_code, [403, 404])


class VivierViewTests(TestCase):
    def setUp(self):
        self.dept = _dept("VivierDept")
        self.maitre = _membre(self.dept, "MaitreVivier")
        self.sec = _secretaire()
        self.resp = _responsable(self.dept)
        stage = _stage_termine(self.dept, self.maitre, self.sec)
        stage.note = 15
        stage.vivier = True
        stage.date_evaluation = datetime.date(2025, 4, 15)
        stage.save()

    def test_vivier_accessible_responsable(self):
        self.client.force_login(self.resp)
        response = self.client.get(reverse("stages:vivier"))
        self.assertEqual(response.status_code, 200)

    def test_403_secretaire(self):
        self.client.force_login(self.sec)
        response = self.client.get(reverse("stages:vivier"))
        self.assertEqual(response.status_code, 403)

    def test_export_csv(self):
        self.client.force_login(self.resp)
        response = self.client.get(reverse("stages:vivier_export_csv"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])


class RappelEvaluationCommandTests(TestCase):
    def setUp(self):
        self.dept = _dept("RappelDept")
        self.maitre = _membre(self.dept, "MaitreRappel")
        self.sec = _secretaire()
        self.resp = _responsable(self.dept)

    def test_rappel_envoye_apres_7j(self):
        from django.core.management import call_command
        from io import StringIO
        # Stage terminé il y a 10 jours, sans note
        stage = _stage_termine(self.dept, self.maitre, self.sec)
        date_fin = timezone.localdate() - datetime.timedelta(days=10)
        stage.date_fin_reelle = date_fin
        stage.save(update_fields=["date_fin_reelle"])

        out = StringIO()
        call_command("mettre_a_jour_stages", stdout=out)
        stage.refresh_from_db()
        self.assertTrue(stage.rappel_evaluation_envoye)

    def test_pas_rappel_avant_7j(self):
        from django.core.management import call_command
        from io import StringIO
        stage = _stage_termine(self.dept, self.maitre, self.sec)
        date_fin = timezone.localdate() - datetime.timedelta(days=3)
        stage.date_fin_reelle = date_fin
        stage.save(update_fields=["date_fin_reelle"])

        out = StringIO()
        call_command("mettre_a_jour_stages", stdout=out)
        stage.refresh_from_db()
        self.assertFalse(stage.rappel_evaluation_envoye)


# ─── Lot D — D4 : AffectationMaitreStage ─────────────────────────────────────


class AffectationMaitreStageTests(TestCase):
    def setUp(self):
        self.dept = _dept("AffectDept")
        self.maitre = _membre(self.dept, "MaitreAffect")
        self.sec = _secretaire()
        self.cand = _candidature_accordee(self.dept)

    def test_constituer_stage_cree_affectation(self):
        debut = timezone.localdate() + datetime.timedelta(days=5)
        fin = debut + datetime.timedelta(days=60)
        stage = constituer_stage(self.cand, debut, fin, self.maitre, self.sec)
        self.assertEqual(
            AffectationMaitreStage.objects.filter(stage=stage).count(), 1
        )
        a = AffectationMaitreStage.objects.get(stage=stage)
        self.assertEqual(a.maitre_stage, self.maitre)
        self.assertEqual(a.affecte_par, self.sec)

    def test_modifier_stage_meme_maitre_pas_nouvelle_affectation(self):
        debut = timezone.localdate() + datetime.timedelta(days=5)
        fin = debut + datetime.timedelta(days=60)
        stage = constituer_stage(self.cand, debut, fin, self.maitre, self.sec)
        nb_avant = AffectationMaitreStage.objects.filter(stage=stage).count()
        nouvelle_fin = fin + datetime.timedelta(days=10)
        modifier_stage(stage, nouvelle_fin, self.maitre, self.sec)
        self.assertEqual(
            AffectationMaitreStage.objects.filter(stage=stage).count(), nb_avant
        )

    def test_modifier_stage_nouveau_maitre_cree_affectation(self):
        debut = timezone.localdate() + datetime.timedelta(days=5)
        fin = debut + datetime.timedelta(days=60)
        stage = constituer_stage(self.cand, debut, fin, self.maitre, self.sec)
        nouveau_maitre = _membre(self.dept, "NouveauMaitre")
        modifier_stage(stage, fin, nouveau_maitre, self.sec)
        affectations = AffectationMaitreStage.objects.filter(stage=stage).order_by("date_affectation")
        self.assertEqual(affectations.count(), 2)
        self.assertEqual(affectations.last().maitre_stage, nouveau_maitre)

