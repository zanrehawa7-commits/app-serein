import datetime
import itertools
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from comptes.models import Utilisateur
from referentiels.models import Departement, Personnel
from offres.models import Offre, StatutOffre
from candidatures.models import Candidat, Candidature, StatutCandidature, TypeDemande
from referentiels.models import TypeStage

from .models import Stage, StatutStage, AffectationMaitreStage, PeriodeInterruption
from .services import (
    TransitionInterdite,
    constituer_stage,
    modifier_stage,
    terminer_stage,
    interrompre_stage,
    debut_modifiable,
    evaluer_stage,
    peut_evaluer,
    reprendre_stage,
)


# ─── Fixtures communes ────────────────────────────────────────────────────────

# Disponibilité large : ces tests ne portent pas sur RG-S11 (testée dans DisponibiliteRGS11Tests).
_DISPO_DEBUT = timezone.localdate() - datetime.timedelta(days=3 * 365)
_DISPO_FIN = timezone.localdate() + datetime.timedelta(days=3 * 365)


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


_TELEPHONES = itertools.count(70111111)


def _candidat():
    return Candidat.objects.create(nom="Ouedraogo", prenom="Fatou", telephone=str(next(_TELEPHONES)))


def _candidature_accordee(dept, maitre=None):
    cand = _candidat()
    ts = _type_stage()
    c = Candidature.objects.create(
        candidat=cand,
        departement=dept,
        type_stage=ts,
        type_demande=TypeDemande.SPONTANEE,
        debut_disponibilite=_DISPO_DEBUT,
        fin_disponibilite=_DISPO_FIN,
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

    def test_creation_toujours_a_venir_meme_si_debut_passe(self):
        """RG-S2 : seul le Responsable démarre un stage (RG-S14), même si son début est passé."""
        for decalage in (-5, 0):
            with self.subTest(decalage=decalage):
                cand = _candidature_accordee(self.dept) if decalage else self.cand
                debut = timezone.localdate() + datetime.timedelta(days=decalage)
                stage = constituer_stage(cand, debut, debut + datetime.timedelta(days=60), self.maitre, self.sec)
                self.assertEqual(stage.statut, StatutStage.A_VENIR)

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


class AucuneTransitionAutomatiqueTests(TestCase):
    """Décision du directeur de mémoire : le système alerte, il ne change jamais un statut."""

    def setUp(self):
        self.dept = _dept()
        self.maitre = _membre(self.dept)

    def _stage(self, statut, debut, fin):
        return Stage.objects.create(
            candidature=_candidature_accordee(self.dept), maitre_stage=self.maitre,
            date_debut=debut, date_fin_prevue=fin, statut=statut,
        )

    def test_la_commande_quotidienne_ne_change_aucun_statut(self):
        from io import StringIO
        from django.core.management import call_command
        jour = timezone.localdate()
        a_venir = self._stage(StatutStage.A_VENIR, jour - datetime.timedelta(days=90), jour - datetime.timedelta(days=10))
        en_cours = self._stage(StatutStage.EN_COURS, jour - datetime.timedelta(days=90), jour - datetime.timedelta(days=10))
        call_command("mettre_a_jour_stages", "--date", (jour + datetime.timedelta(days=30)).isoformat(), stdout=StringIO())
        a_venir.refresh_from_db()
        en_cours.refresh_from_db()
        self.assertEqual((a_venir.statut, en_cours.statut), (StatutStage.A_VENIR, StatutStage.EN_COURS))
        self.assertIsNone(en_cours.date_fin_reelle)


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



# ─── Fiche stage : cloisonnement département (Responsable) ────────────────────


class _DeuxDepartementsMixin:
    """Responsable du département A connecté ; stages en A et en B (dont un au vivier)."""

    def setUp(self):
        self.dept_a = _dept("Informatique")
        self.dept_b = _dept("Comptabilité")
        self.resp_a = _responsable(self.dept_a)
        maitre_a = _membre(self.dept_a, "Zongo")
        maitre_b = _membre(self.dept_b, "Ilboudo")
        self.stage_a = self._stage(self.dept_a, maitre_a, "70000001", StatutStage.EN_COURS)
        self.stage_b = self._stage(self.dept_b, maitre_b, "70000002", StatutStage.EN_COURS)
        self.stage_b_vivier = self._stage(
            self.dept_b, maitre_b, "70000003", StatutStage.TERMINE,
            note=15, vivier=True, date_evaluation=timezone.localdate(),
        )
        self.client.force_login(self.resp_a)

    def _stage(self, dept, maitre, telephone, statut, **extra):
        cand = Candidature.objects.create(
            candidat=Candidat.objects.create(nom="Stagiaire", prenom=telephone, telephone=telephone),
            departement=dept, type_stage=_type_stage(), type_demande=TypeDemande.SPONTANEE,
            debut_disponibilite=_DISPO_DEBUT, fin_disponibilite=_DISPO_FIN,
            duree_souhaitee=3, statut=StatutCandidature.ACCORDEE,
        )
        return Stage.objects.create(
            candidature=cand, maitre_stage=maitre, statut=statut,
            date_debut=timezone.localdate() - datetime.timedelta(days=60),
            date_fin_prevue=timezone.localdate() + datetime.timedelta(days=30), **extra,
        )


class StageDetailCloisonnementTests(_DeuxDepartementsMixin, TestCase):
    """RG-E7 : fiche d'un stage d'un autre département → 403, sauf stage au vivier (lecture seule)."""

    def _detail(self, stage):
        return self.client.get(reverse("stages:stage_detail", args=[stage.pk]))

    def test_autre_departement_hors_vivier_403(self):
        self.assertEqual(self._detail(self.stage_b).status_code, 403)

    def test_responsable_sans_departement_403(self):
        self.resp_a.personnel.departement = None
        self.resp_a.personnel.save(update_fields=["departement"])
        self.assertEqual(self._detail(self.stage_a).status_code, 403)

    def test_autre_departement_au_vivier_lecture_seule_sans_bouton(self):
        reponse = self._detail(self.stage_b_vivier)
        self.assertEqual(reponse.status_code, 200)
        self.assertTemplateUsed(reponse, "stages/stage_detail_vivier.html")
        pk = self.stage_b_vivier.pk
        for nom in ["stage_modifier", "stage_terminer", "stage_interrompre", "stage_evaluer", "stage_reprendre"]:
            with self.subTest(url=nom):
                self.assertNotContains(reponse, reverse(f"stages:{nom}", args=[pk]))
        self.assertContains(reponse, "Lecture seule")

    def test_propre_departement_avec_actions(self):
        reponse = self._detail(self.stage_a)
        self.assertEqual(reponse.status_code, 200)
        self.assertTemplateUsed(reponse, "stages/stage_detail.html")
        self.assertTrue(reponse.context["peut_terminer"])
        self.assertContains(reponse, reverse("stages:stage_terminer", args=[self.stage_a.pk]))

    def test_secretaire_et_administrateur_non_cloisonnes(self):
        for role, email in [("Secrétaire", "sec2@test.com"), ("Administrateur", "admin2@test.com")]:
            with self.subTest(role=role):
                self.client.force_login(_user(email, role))
                reponse = self._detail(self.stage_b)
                self.assertEqual(reponse.status_code, 200)
                self.assertTemplateUsed(reponse, "stages/stage_detail.html")


# ─── RG-E8 : dossier du candidat sur la fiche stage ───────────────────────────


class DossierCandidatRGE8Tests(_DeuxDepartementsMixin, TestCase):
    """Dossier complet pour Secrétaire, Administrateur et Responsable du département ;
    colonnes du vivier uniquement pour le Responsable d'un autre département."""

    def setUp(self):
        from candidatures.models import PieceJointe, TypePiece
        from suivi.services import enregistrer_historique
        super().setUp()
        self.stage_b_vivier.rapport.save("rapport.pdf", ContentFile(b"%PDF-1.4 rapport"), save=True)
        cand = self.stage_b_vivier.candidature
        Candidat.objects.filter(pk=cand.candidat_id).update(
            email="stagiaire@test.bf", adresse="Secteur 15, Ouagadougou", filiere="Gestion financière", niveau_etudes="L3",
        )
        self.piece = PieceJointe(candidature=cand, type_piece=TypePiece.CV, nom_original="cv_stagiaire.pdf")
        self.piece.fichier.save("cv.pdf", ContentFile(b"%PDF-1.4 cv"), save=True)
        enregistrer_historique(self.stage_b_vivier, None, "EN_COURS", "TERMINE", "Commentaire interne confidentiel")
        PeriodeInterruption.objects.create(
            stage=self.stage_b_vivier, date_debut=self.stage_b_vivier.date_debut,
            date_fin=self.stage_b_vivier.date_debut + datetime.timedelta(days=3),
            motif_interruption="Motif d'interruption privé",
        )
        # Maître de stage : nom affiché, coordonnées jamais (RG-E8).
        Personnel.objects.filter(pk=self.stage_b_vivier.maitre_stage_id).update(
            email="maitre.b@serein.bf", telephone="70999999"
        )
        self.url_piece = reverse("candidatures:piece_telecharger", args=[self.piece.pk])
        self.url_candidature = reverse("candidatures:candidature_detail", args=[cand.pk])

    def _detail(self, user=None):
        if user:
            self.client.force_login(user)
        return self.client.get(reverse("stages:stage_detail", args=[self.stage_b_vivier.pk]))

    def test_responsable_autre_departement_colonnes_du_vivier_uniquement(self):
        reponse = self._detail()
        self.assertEqual(reponse.status_code, 200)
        for visible in ["70000003", "stagiaire@test.bf", "Licence 3", "Gestion financière", "Comptabilité",
                        "15/20", "Jean Ilboudo", reverse("stages:rapport_telecharger", args=[self.stage_b_vivier.pk])]:
            with self.subTest(visible=visible):
                self.assertContains(reponse, visible)
        for masque in [self.url_piece, "cv_stagiaire.pdf", self.url_candidature, "Secteur 15",
                       "maitre.b@serein.bf", "70999999", "Commentaire interne confidentiel", "interruption privé",
                       self.stage_b_vivier.candidature.reference]:
            with self.subTest(masque=masque):
                self.assertNotContains(reponse, masque)

    def test_responsable_autre_departement_rien_d_autre_dans_le_contexte(self):
        reponse = self._detail()
        for cle in ["pieces", "historiques", "affectations_maitre", "periodes_interruption"]:
            with self.subTest(cle=cle):
                self.assertNotIn(cle, reponse.context)

    def test_responsable_autre_departement_piece_403(self):
        self._detail()
        self.assertEqual(self.client.get(self.url_piece).status_code, 403)

    def test_dossier_complet_secretaire_administrateur_responsable_du_departement(self):
        resp_b = _user("resp_b@test.com", "Responsable")
        resp_b.personnel = _membre(self.dept_b, "RespB")
        resp_b.save(update_fields=["personnel"])
        for user in [_user("sec4@test.com", "Secrétaire"), _user("admin4@test.com", "Administrateur"), resp_b]:
            with self.subTest(role=user.role):
                reponse = self._detail(user)
                self.assertEqual(reponse.status_code, 200)
                for visible in ["Dossier du candidat", self.url_piece, f"{self.url_piece}?inline=1",
                                "cv_stagiaire.pdf", self.url_candidature, "Secteur 15", "stagiaire@test.bf",
                                "Spontanée", "interruption privé"]:
                    self.assertContains(reponse, visible)


# ─── Rapport de stage : RG-E5 ─────────────────────────────────────────────────


class RapportTelechargementRGE5Tests(_DeuxDepartementsMixin, TestCase):
    """RG-E5 : rapport du département du Responsable, ou d'un autre département si stage au vivier."""

    def setUp(self):
        super().setUp()
        self.stage_b_hors_vivier = self._stage(
            self.dept_b, _membre(self.dept_b, "Some"), "70000004", StatutStage.TERMINE,
            note=10, vivier=False, date_evaluation=timezone.localdate(),
        )
        for stage in [self.stage_a, self.stage_b_vivier, self.stage_b_hors_vivier]:
            stage.rapport.save(f"rapport_{stage.pk}.pdf", ContentFile(b"%PDF-1.4 rapport"), save=True)

    def _rapport(self, stage):
        return self.client.get(reverse("stages:rapport_telecharger", args=[stage.pk]))

    def test_propre_departement_autorise(self):
        self.assertEqual(self._rapport(self.stage_a).status_code, 200)

    def test_autre_departement_au_vivier_autorise(self):
        self.assertEqual(self._rapport(self.stage_b_vivier).status_code, 200)

    def test_autre_departement_hors_vivier_403(self):
        self.assertEqual(self._rapport(self.stage_b_hors_vivier).status_code, 403)

    def test_responsable_sans_departement_hors_vivier_403(self):
        self.resp_a.personnel.departement = None
        self.resp_a.personnel.save(update_fields=["departement"])
        self.assertEqual(self._rapport(self.stage_b_hors_vivier).status_code, 403)
        self.assertEqual(self._rapport(self.stage_b_vivier).status_code, 200)

    def test_secretaire_403(self):
        self.client.force_login(_user("sec3@test.com", "Secrétaire"))
        self.assertEqual(self._rapport(self.stage_a).status_code, 403)


# ─── RG-S11 : dates du stage dans la disponibilité du candidat ────────────────


class DisponibiliteRGS11Tests(TestCase):
    """Constitution et modification : début ≥ début de disponibilité, fin ≤ fin de disponibilité."""

    def setUp(self):
        self.dept = _dept()
        self.maitre = _membre(self.dept)
        self.sec = _secretaire()
        self.aujourd_hui = timezone.localdate()
        self.dispo_debut = self.aujourd_hui + datetime.timedelta(days=10)
        self.dispo_fin = self.aujourd_hui + datetime.timedelta(days=100)
        self.cand = _candidature_accordee(self.dept)
        Candidature.objects.filter(pk=self.cand.pk).update(
            debut_disponibilite=self.dispo_debut, fin_disponibilite=self.dispo_fin
        )
        self.cand.refresh_from_db()
        self.periode = f"du {self.dispo_debut:%d/%m/%Y} au {self.dispo_fin:%d/%m/%Y}"

    def _jour(self, n):
        return self.aujourd_hui + datetime.timedelta(days=n)

    def _constituer(self, debut, fin):
        return constituer_stage(self.cand, debut, fin, self.maitre, self.sec)

    def test_constitution_bornes_incluses_acceptees(self):
        stage = self._constituer(self.dispo_debut, self.dispo_fin)
        self.assertEqual((stage.date_debut, stage.date_fin_prevue), (self.dispo_debut, self.dispo_fin))

    def test_constitution_debut_avant_disponibilite_refusee(self):
        with self.assertRaisesMessage(TransitionInterdite, self.periode):
            self._constituer(self._jour(9), self._jour(50))
        self.assertFalse(Stage.objects.exists())

    def test_constitution_fin_apres_disponibilite_refusee(self):
        with self.assertRaisesMessage(TransitionInterdite, self.periode):
            self._constituer(self._jour(20), self._jour(101))
        self.assertFalse(Stage.objects.exists())

    def test_formulaire_constitution_erreurs_sur_les_champs(self):
        from .forms import ConstituerStageForm
        form = ConstituerStageForm(
            {"date_debut": self._jour(1), "date_fin_prevue": self._jour(200), "maitre_stage": self.maitre.pk},
            departement=self.dept, candidature=self.cand,
        )
        self.assertFalse(form.is_valid())
        self.assertIn(self.periode, form.errors["date_debut"][0])
        self.assertIn(self.periode, form.errors["date_fin_prevue"][0])

    def test_vue_constitution_hors_disponibilite_affiche_la_periode(self):
        self.client.force_login(self.sec)
        reponse = self.client.post(
            reverse("stages:stage_constituer", args=[self.cand.pk]),
            {"date_debut": self._jour(1), "date_fin_prevue": self._jour(50), "maitre_stage": self.maitre.pk},
        )
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, self.periode)
        self.assertFalse(Stage.objects.exists())

    def test_modification_a_venir_debut_hors_disponibilite_refusee(self):
        stage = self._constituer(self._jour(20), self._jour(50))
        with self.assertRaisesMessage(TransitionInterdite, self.periode):
            modifier_stage(stage, self._jour(50), self.maitre, self.sec, date_debut=self._jour(5))

    def test_modification_fin_hors_disponibilite_refusee(self):
        stage = self._constituer(self._jour(20), self._jour(50))
        with self.assertRaisesMessage(TransitionInterdite, self.periode):
            modifier_stage(stage, self._jour(150), self.maitre, self.sec)
        stage.refresh_from_db()
        self.assertEqual(stage.date_fin_prevue, self._jour(50))

    def test_stage_en_cours_existant_debut_hors_disponibilite_reste_modifiable(self):
        """Stage antérieur à la règle : début non modifiable donc non vérifié, fin vérifiée."""
        stage = Stage.objects.create(
            candidature=self.cand, maitre_stage=self.maitre, statut=StatutStage.EN_COURS,
            date_debut=self._jour(-30), date_fin_prevue=self._jour(50),
        )
        autre_maitre = _membre(self.dept, "Kaboré")
        modifier_stage(stage, self._jour(60), autre_maitre, self.sec)
        stage.refresh_from_db()
        self.assertEqual((stage.maitre_stage, stage.date_fin_prevue), (autre_maitre, self._jour(60)))
        with self.assertRaisesMessage(TransitionInterdite, self.periode):
            modifier_stage(stage, self._jour(150), autre_maitre, self.sec)


# ─── RG-S12 / RG-S13 : reprise d'un stage interrompu ──────────────────────────


class RepriseStageTests(TestCase):

    def setUp(self):
        self.dept = _dept()
        self.maitre = _membre(self.dept)
        self.sec = _secretaire()
        self.resp = _responsable(self.dept)
        self.aujourd_hui = timezone.localdate()
        self.cand = _candidature_accordee(self.dept)
        self.stage = Stage.objects.create(
            candidature=self.cand, maitre_stage=self.maitre, statut=StatutStage.EN_COURS,
            date_debut=self._jour(-60), date_fin_prevue=self._jour(30),
        )
        interrompre_stage(self.stage, self._jour(-10), "Maladie", self.resp)
        self.stage.refresh_from_db()

    def _jour(self, n):
        return self.aujourd_hui + datetime.timedelta(days=n)

    def _reprendre(self, reprise, fin, motif="Rétabli"):
        return reprendre_stage(self.stage, reprise, fin, motif, self.resp)

    def _assert_inchange(self):
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.statut, StatutStage.INTERROMPU)
        self.assertIsNotNone(self.stage.periode_interruption_ouverte())

    def test_interruption_cree_une_periode_ouverte(self):
        periode = self.stage.periodes_interruption.get()
        self.assertEqual(
            (periode.date_debut, periode.date_fin, periode.motif_interruption, periode.interrompu_par),
            (self._jour(-10), None, "Maladie", self.resp),
        )

    def test_reprise_date_passee_en_cours(self):
        self._reprendre(self._jour(-2), self._jour(60))
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.statut, StatutStage.EN_COURS)
        self.assertEqual(self.stage.date_fin_prevue, self._jour(60))
        self.assertIsNone(self.stage.date_fin_reelle)
        self.assertEqual(self.stage.motif_interruption, "")
        periode = self.stage.periodes_interruption.get()
        self.assertEqual(
            (periode.date_fin, periode.motif_reprise, periode.repris_par), (self._jour(-2), "Rétabli", self.resp)
        )

    def test_reprise_date_future_a_venir(self):
        self._reprendre(self._jour(5), self._jour(60))
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.statut, StatutStage.A_VENIR)

    def test_reprise_avant_interruption_refusee(self):
        with self.assertRaisesMessage(TransitionInterdite, "antérieure à la date d'interruption"):
            self._reprendre(self._jour(-11), self._jour(60))
        self._assert_inchange()

    def test_fin_avant_reprise_refusee(self):
        with self.assertRaises(TransitionInterdite):
            self._reprendre(self._jour(5), self._jour(5))
        self._assert_inchange()

    def test_fin_apres_disponibilite_refusee(self):
        Candidature.objects.filter(pk=self.cand.pk).update(fin_disponibilite=self._jour(40))
        with self.assertRaisesMessage(TransitionInterdite, "disponibilité du candidat"):
            self._reprendre(self._jour(-2), self._jour(41))
        self._assert_inchange()

    def test_motif_obligatoire(self):
        with self.assertRaises(TransitionInterdite):
            self._reprendre(self._jour(-2), self._jour(60), motif="  ")
        self._assert_inchange()

    def test_stage_non_interrompu_refuse(self):
        self._reprendre(self._jour(-2), self._jour(60))
        with self.assertRaisesMessage(TransitionInterdite, "Seul un stage interrompu"):
            self._reprendre(self._jour(-1), self._jour(70))

    def test_historique_et_notification_secretaires(self):
        from suivi.models import Historique, Notification
        self._reprendre(self._jour(-2), self._jour(60))
        derniere = Historique.objects.filter(object_id=self.stage.pk).order_by("-pk").first()
        self.assertEqual(
            (derniere.ancien_statut, derniere.nouveau_statut), (StatutStage.INTERROMPU, StatutStage.EN_COURS)
        )
        self.assertTrue(Notification.objects.filter(destinataire=self.sec, message__contains="repris").exists())

    def test_periodes_conservees_apres_deux_interruptions(self):
        self._reprendre(self._jour(-8), self._jour(60))
        interrompre_stage(self.stage, self._jour(-4), "Congé", self.resp)
        self.stage.refresh_from_db()
        self._reprendre(self._jour(-1), self._jour(70), motif="Retour")
        periodes = list(self.stage.periodes_interruption.values_list("date_debut", "date_fin", "motif_interruption"))
        self.assertEqual(periodes, [
            (self._jour(-10), self._jour(-8), "Maladie"),
            (self._jour(-4), self._jour(-1), "Congé"),
        ])

    def test_interruption_anterieure_a_la_reprise_refusee(self):
        self._reprendre(self._jour(-2), self._jour(60))
        with self.assertRaises(TransitionInterdite):
            interrompre_stage(self.stage, self._jour(-3), "Erreur", self.resp)

    def test_date_debut_non_modifiable_apres_reprise_future(self):
        self._reprendre(self._jour(5), self._jour(60))
        self.stage.refresh_from_db()
        self.assertFalse(debut_modifiable(self.stage))

    # ── Cohérence avec la commande quotidienne et l'évaluation ──────────────

    def test_reprise_future_reste_a_venir_jusqu_au_demarrage_manuel(self):
        from io import StringIO
        from django.core.management import call_command
        self._reprendre(self._jour(5), self._jour(60))
        call_command("mettre_a_jour_stages", "--date", self._jour(10).isoformat(), stdout=StringIO())
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.statut, StatutStage.A_VENIR)

    def test_reprise_avec_fin_passee_reste_en_cours(self):
        from io import StringIO
        from django.core.management import call_command
        self._reprendre(self._jour(-9), self._jour(-1))
        call_command("mettre_a_jour_stages", stdout=StringIO())
        self.stage.refresh_from_db()
        self.assertEqual((self.stage.statut, self.stage.date_fin_reelle), (StatutStage.EN_COURS, None))

    def test_repris_puis_termine_est_evaluable(self):
        self._reprendre(self._jour(-5), self._jour(60))
        with self.assertRaisesMessage(TransitionInterdite, "reprise"):
            terminer_stage(self.stage, self._jour(-6), self.resp)
        terminer_stage(self.stage, self._jour(-1), self.resp)
        self.stage.refresh_from_db()
        self.assertTrue(peut_evaluer(self.stage)[0])
        evaluer_stage(self.stage, 14, True, self.resp)
        self.stage.refresh_from_db()
        self.assertEqual((self.stage.note, self.stage.vivier), (14, True))

    # ── Vue ─────────────────────────────────────────────────────────────────

    def _post(self, **donnees):
        self.client.force_login(self.resp)
        return self.client.post(reverse("stages:stage_reprendre", args=[self.stage.pk]), donnees, follow=True)

    def test_vue_reprise(self):
        reponse = self._post(date_reprise=self._jour(-2), date_fin_prevue=self._jour(60), motif_reprise="Rétabli")
        self.assertRedirects(reponse, reverse("stages:stage_detail", args=[self.stage.pk]))
        self.stage.refresh_from_db()
        self.assertEqual(self.stage.statut, StatutStage.EN_COURS)
        self.assertContains(reponse, "Périodes d")
        self.assertNotContains(reponse, "pensez à terminer ce stage")

    def test_vue_reprise_fin_passee_message_information(self):
        reponse = self._post(
            date_reprise=self._jour(-9), date_fin_prevue=self._jour(-1), motif_reprise="Régularisation"
        )
        self.assertContains(
            reponse, "La fin prévue est déjà dépassée : pensez à terminer ce stage, rien ne se fait automatiquement."
        )

    def test_vue_dates_invalides_formulaire_reaffiche(self):
        reponse = self._post(date_reprise=self._jour(-11), date_fin_prevue=self._jour(60), motif_reprise="X")
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "antérieure à la date d")
        self._assert_inchange()

    def test_vue_bouton_reprendre_sur_la_fiche(self):
        self.client.force_login(self.resp)
        reponse = self.client.get(reverse("stages:stage_detail", args=[self.stage.pk]))
        self.assertContains(reponse, reverse("stages:stage_reprendre", args=[self.stage.pk]))


class MigrationPeriodesStagesInterrompusTests(TestCase):
    """Migration 0006 : les stages interrompus avant le lot F reçoivent une période ouverte."""

    def test_cree_une_periode_ouverte_une_seule_fois(self):
        import importlib
        from django.apps import apps
        migration = importlib.import_module("stages.migrations.0006_periodes_stages_deja_interrompus")
        dept = _dept()
        stage = Stage.objects.create(
            candidature=_candidature_accordee(dept), maitre_stage=_membre(dept), statut=StatutStage.INTERROMPU,
            date_debut=timezone.localdate() - datetime.timedelta(days=30),
            date_fin_prevue=timezone.localdate() + datetime.timedelta(days=30),
            date_fin_reelle=timezone.localdate() - datetime.timedelta(days=3), motif_interruption="Ancien motif",
        )
        migration.creer_periodes_ouvertes(apps, None)
        migration.creer_periodes_ouvertes(apps, None)
        periode = PeriodeInterruption.objects.get(stage=stage)
        self.assertEqual(
            (periode.date_debut, periode.date_fin, periode.motif_interruption),
            (stage.date_fin_reelle, None, "Ancien motif"),
        )
