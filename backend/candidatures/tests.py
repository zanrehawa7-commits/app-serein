import io
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from comptes.models import Utilisateur
from offres.models import Offre, StatutOffre
from referentiels.models import Departement, TypeStage, Personnel

from .models import Candidat, Candidature, PieceJointe, StatutCandidature, TypeDemande, TypePiece
from .services import (
    CandidatExistant,
    CandidatureActiveExistante,
    QuotaAtteint,
    TransitionInterdite,
    accorder,
    creer_candidat,
    creer_candidature,
    marquer_informe,
    normaliser_telephone,
    planifier_entretien,
    preselectionner,
    rechercher_candidats,
    rediriger,
    refuser,
)
from .models import MotifRefus


def _fake_pdf(name="cv.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 fake", content_type="application/pdf")


def _fake_exe(name="virus.exe"):
    return SimpleUploadedFile(name, b"MZ fake exe", content_type="application/octet-stream")


def _big_file(name="big.pdf"):
    return SimpleUploadedFile(name, b"%PDF" + b"0" * (6 * 1024 * 1024), content_type="application/pdf")


# ─── normaliser_telephone ────────────────────────────────────────────────────


class NormaliserTelephoneTests(TestCase):
    def test_strip_espaces(self):
        self.assertEqual(normaliser_telephone("70 12 34 56"), "70123456")

    def test_strip_points_tirets(self):
        self.assertEqual(normaliser_telephone("70.12-34.56"), "70123456")

    def test_prefixe_plus226(self):
        self.assertEqual(normaliser_telephone("+226 70123456"), "70123456")

    def test_prefixe_00226(self):
        self.assertEqual(normaliser_telephone("0022670123456"), "70123456")

    def test_doublon_format_different(self):
        """70 12 34 56 et +226 70123456 doivent être reconnus comme doublons."""
        creer_candidat("Alpha", "A", "70 12 34 56")
        with self.assertRaises(CandidatExistant):
            creer_candidat("Beta", "B", "+226 70123456")


# ─── Candidat CRUD ───────────────────────────────────────────────────────────


class CandidatServiceTests(TestCase):
    def test_creer_candidat(self):
        c = creer_candidat("Ouedraogo", "Fatou", "70111111")
        self.assertEqual(c.telephone, "70111111")

    def test_doublon_telephone(self):
        creer_candidat("A", "B", "70111111")
        with self.assertRaises(CandidatExistant):
            creer_candidat("C", "D", "70111111")

    def test_rechercher_par_nom(self):
        creer_candidat("Ouedraogo", "Fatou", "70111111")
        resultats = rechercher_candidats("Ouedra")
        self.assertIn("Ouedraogo", [c.nom for c in resultats])

    def test_rechercher_par_telephone(self):
        creer_candidat("Test", "Tel", "70222222")
        resultats = rechercher_candidats("70222222")
        self.assertTrue(resultats.exists())


# ─── Fixtures helpers ─────────────────────────────────────────────────────────


def _offre_factory(dept, ts, statut=StatutOffre.OUVERTE):
    return Offre.objects.create(
        type_stage=ts,
        titre="Offre test",
        description="Description test",
        profil_recherche="Profil test",
        date_debut="2027-03-01",
        date_fin="2027-06-01",
        nombre_places=3,
        statut=statut,
    )


def _setup_base():
    """Crée les fixtures minimales : groupes, users, dept, type_stage, candidat."""
    g_sec = Group.objects.get_or_create(name="Secrétaire")[0]
    g_res = Group.objects.get_or_create(name="Responsable")[0]
    g_adm = Group.objects.get_or_create(name="Administrateur")[0]

    sec = Utilisateur.objects.create_user(email="sec@test.com", password="pass", first_name="Sec")
    sec.groups.add(g_sec)

    adm = Utilisateur.objects.create_user(email="adm@test.com", password="pass", first_name="Adm")
    adm.groups.add(g_adm)

    dept = Departement.objects.create(nom="Informatique", actif=True)
    ts = TypeStage.objects.create(libelle="Stage pro", actif=True, duree_min_mois=1, duree_max_mois=6)

    membre = Personnel.objects.create(nom="Responsable", prenom="R", departement=dept, actif=True)
    res = Utilisateur.objects.create_user(email="res@test.com", password="pass", first_name="Res")
    res.groups.add(g_res)
    res.personnel = membre
    res.save()

    candidat = creer_candidat("Test", "Candidat", "70999999")
    return sec, adm, res, dept, ts, candidat


# ─── RG07 — candidature active unique ─────────────────────────────────────────


class RG07Tests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()
        self.pieces = [{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}]

    def test_rg07_bloque_deuxieme_candidature_active(self):
        creer_candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2027-03-01",
            fin_disponibilite="2027-06-01", duree_souhaitee=2,
            pieces_data=self.pieces, utilisateur=self.sec,
        )
        with self.assertRaises(CandidatureActiveExistante):
            creer_candidature(
                candidat=self.candidat, departement=self.dept, type_stage=self.ts,
                type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2026-11-01",
                fin_disponibilite="2027-01-31", duree_souhaitee=2,
                pieces_data=[{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv2.pdf"}],
                utilisateur=self.sec,
            )


# ─── RG09 — cohérence type_demande / offre ────────────────────────────────────


class RG09Tests(TestCase):
    def setUp(self):
        _, _, _, self.dept, self.ts, self.candidat = _setup_base()

    def test_suite_offre_sans_offre_invalide(self):
        from django.core.exceptions import ValidationError
        c = Candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SUITE_OFFRE, offre=None,
            debut_disponibilite="2027-03-01", fin_disponibilite="2027-06-01",
            duree_souhaitee=2,
        )
        with self.assertRaises(ValidationError):
            c.clean()

    def test_spontanee_avec_offre_invalide(self):
        from django.core.exceptions import ValidationError
        offre = _offre_factory(self.dept, self.ts)
        c = Candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, offre=offre,
            debut_disponibilite="2027-03-01", fin_disponibilite="2027-06-01",
            duree_souhaitee=2,
        )
        with self.assertRaises(ValidationError):
            c.clean()

    def test_suite_offre_non_ouverte_form_invalide(self):
        """Le formulaire ne doit pas proposer d'offre non OUVERTE."""
        from .forms import CandidatureCreerForm
        offre_fermee = _offre_factory(self.dept, self.ts, statut=StatutOffre.FERMEE)
        form = CandidatureCreerForm()
        self.assertNotIn(offre_fermee, form.fields["offre"].queryset)


# ─── Création candidature ─────────────────────────────────────────────────────


class CreationCandidatureTests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()

    def test_creation_statut_recue_reference_historique(self):
        pieces = [{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}]
        c = creer_candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2027-03-01",
            fin_disponibilite="2027-06-01", duree_souhaitee=2,
            pieces_data=pieces, utilisateur=self.sec,
        )
        from django.contrib.contenttypes.models import ContentType
        from suivi.models import Historique
        ct = ContentType.objects.get_for_model(c)
        self.assertEqual(c.statut, StatutCandidature.RECUE)
        self.assertTrue(c.reference.startswith("CAND-"))
        self.assertEqual(Historique.objects.filter(content_type=ct, object_id=c.pk).count(), 1)

    def test_reference_unique_incrementielle(self):
        pieces = [{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}]
        c1 = creer_candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2027-03-01",
            fin_disponibilite="2027-06-01", duree_souhaitee=2,
            pieces_data=pieces, utilisateur=self.sec,
        )
        candidat2 = creer_candidat("Zombre", "Z", "70000001")
        c2 = creer_candidature(
            candidat=candidat2, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2027-03-01",
            fin_disponibilite="2027-06-01", duree_souhaitee=2,
            pieces_data=[{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}],
            utilisateur=self.sec,
        )
        self.assertNotEqual(c1.reference, c2.reference)

    def test_notification_responsable(self):
        from suivi.models import Notification
        pieces = [{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}]
        creer_candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2027-03-01",
            fin_disponibilite="2027-06-01", duree_souhaitee=2,
            pieces_data=pieces, utilisateur=self.sec,
        )
        self.assertTrue(Notification.objects.filter(destinataire__email="res@test.com").exists())

    def test_dept_sans_responsable_notifie_admins(self):
        from suivi.models import Notification
        dept2 = Departement.objects.create(nom="Sans Responsable", actif=True)
        candidat2 = creer_candidat("SansResp", "X", "70000002")
        pieces = [{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}]
        creer_candidature(
            candidat=candidat2, departement=dept2, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2027-03-01",
            fin_disponibilite="2027-06-01", duree_souhaitee=2,
            pieces_data=pieces, utilisateur=self.sec,
        )
        self.assertTrue(Notification.objects.filter(destinataire__email="adm@test.com").exists())


# ─── Validation pièces jointes ────────────────────────────────────────────────


class PieceJointeValidationTests(TestCase):
    def test_extension_exe_refusee(self):
        from django.core.exceptions import ValidationError
        from .models import _valider_piece_jointe
        with self.assertRaises(ValidationError):
            _valider_piece_jointe(_fake_exe())

    def test_fichier_trop_gros(self):
        from django.core.exceptions import ValidationError
        from .models import _valider_piece_jointe
        with self.assertRaises(ValidationError):
            _valider_piece_jointe(_big_file())

    def test_formset_sans_cv_invalide(self):
        from .forms import PieceJointeFormSet
        data = {
            "pieces-TOTAL_FORMS": "1",
            "pieces-INITIAL_FORMS": "0",
            "pieces-0-type_piece": TypePiece.LETTRE_MOTIVATION,
        }
        files = {"pieces-0-fichier": _fake_pdf("lettre.pdf")}
        fs = PieceJointeFormSet(data, files, prefix="pieces")
        self.assertFalse(fs.is_valid())
        self.assertIn("CV", str(fs.non_form_errors()))


# ─── Modification candidature ─────────────────────────────────────────────────


class ModificationCandidatureTests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()
        pieces = [{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}]
        self.candidature = creer_candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2027-03-01",
            fin_disponibilite="2027-06-01", duree_souhaitee=2,
            pieces_data=pieces, utilisateur=self.sec,
        )

    def test_modification_non_recue_bloquee(self):
        self.candidature.statut = StatutCandidature.EN_TRAITEMENT
        self.candidature.save(update_fields=["statut"])
        self.client.force_login(self.sec)
        url = reverse("candidatures:candidature_modifier", args=[self.candidature.pk])
        response = self.client.post(url, {})
        self.assertRedirects(response, reverse("candidatures:candidature_detail", args=[self.candidature.pk]))


# ─── Marquer informé ─────────────────────────────────────────────────────────


class MarquerInformeTests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()
        pieces = [{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}]
        self.candidature = creer_candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2027-03-01",
            fin_disponibilite="2027-06-01", duree_souhaitee=2,
            pieces_data=pieces, utilisateur=self.sec,
        )
        self.candidature.statut = StatutCandidature.ACCORDEE
        self.candidature.save(update_fields=["statut"])

    def test_marquer_informe(self):
        from django.contrib.contenttypes.models import ContentType
        from suivi.models import Historique
        marquer_informe(self.candidature, self.sec)
        self.candidature.refresh_from_db()
        self.assertTrue(self.candidature.candidat_informe)
        self.assertIsNotNone(self.candidature.date_information)
        ct = ContentType.objects.get_for_model(self.candidature)
        self.assertEqual(Historique.objects.filter(content_type=ct, object_id=self.candidature.pk).count(), 2)


# ─── places_restantes ─────────────────────────────────────────────────────────


class PlacesRestantesTests(TestCase):
    def setUp(self):
        _, _, _, self.dept, self.ts, _ = _setup_base()
        self.offre = _offre_factory(self.dept, self.ts)

    def test_places_restantes_diminue(self):
        self.assertEqual(self.offre.places_restantes(), 3)
        candidat = creer_candidat("Place", "Test", "70000010")
        candidature = creer_candidature(
            candidat=candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SUITE_OFFRE, offre=self.offre,
            debut_disponibilite="2027-03-01", fin_disponibilite="2027-06-01", duree_souhaitee=2,
            pieces_data=[{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}],
            utilisateur=None,
        )
        candidature.statut = StatutCandidature.ACCORDEE
        candidature.save(update_fields=["statut"])
        self.offre.refresh_from_db()
        self.assertEqual(self.offre.places_restantes(), 2)


# ─── Accès sécurisé ──────────────────────────────────────────────────────────


class AccesSecuriteTests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()
        # dept2 avec un responsable différent
        self.dept2 = Departement.objects.create(nom="Autre", actif=True)
        membre2 = Personnel.objects.create(nom="Res2", prenom="R", departement=self.dept2, actif=True)
        g_res = Group.objects.get(name="Responsable")
        self.res2 = Utilisateur.objects.create_user(email="res2@test.com", password="pass")
        self.res2.groups.add(g_res)
        self.res2.personnel = membre2
        self.res2.save()

    def test_responsable_autre_dept_candidature_detail_403(self):
        pieces = [{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}]
        candidature = creer_candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2027-03-01",
            fin_disponibilite="2027-06-01", duree_souhaitee=2,
            pieces_data=pieces, utilisateur=self.sec,
        )
        self.client.force_login(self.res2)
        url = reverse("candidatures:candidature_detail", args=[candidature.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_non_connecte_redirige_login(self):
        url = reverse("candidatures:candidature_list")
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_fichier_inaccessible_via_media(self):
        """La route /media/ ne sert pas les fichiers privés."""
        response = self.client.get("/media/candidatures/1/cv_test.pdf")
        # Soit 404 soit redirige login — dans tous les cas pas 200
        self.assertNotEqual(response.status_code, 200)

    def test_responsable_modifier_candidature_403(self):
        """Responsable → vue de modification → 403 (Secrétaire uniquement)."""
        self.client.force_login(self.res)
        url = reverse("candidatures:candidature_modifier", args=[1])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


# ─── Étape 7 — Transitions Responsable ───────────────────────────────────────


def _candidature_factory(dept, ts, candidat, utilisateur, statut=StatutCandidature.RECUE):
    return creer_candidature(
        candidat=candidat, departement=dept, type_stage=ts,
        type_demande=TypeDemande.SPONTANEE,
        debut_disponibilite="2027-03-01", fin_disponibilite="2027-06-01", duree_souhaitee=2,
        pieces_data=[{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}],
        utilisateur=utilisateur,
    )


class PreselectionnerTests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()
        self.cand = _candidature_factory(self.dept, self.ts, self.candidat, self.sec)

    def test_preselectionner_recue_ok(self):
        from suivi.models import Notification
        preselectionner(self.cand, self.res)
        self.cand.refresh_from_db()
        self.assertEqual(self.cand.statut, StatutCandidature.EN_TRAITEMENT)
        self.assertFalse(self.cand.candidat_informe)
        self.assertIsNone(self.cand.date_information)
        self.assertTrue(Notification.objects.filter(destinataire__email="sec@test.com").count() >= 1)

    def test_preselectionner_non_recue_leve_erreur(self):
        self.cand.statut = StatutCandidature.EN_TRAITEMENT
        self.cand.save(update_fields=["statut"])
        with self.assertRaises(TransitionInterdite):
            preselectionner(self.cand, self.res)

    def test_preselectionner_vue_post_ok(self):
        self.client.force_login(self.res)
        url = reverse("candidatures:candidature_preselectionner", args=[self.cand.pk])
        response = self.client.post(url, {"presel-commentaire": "Bon profil"})
        self.assertRedirects(response, reverse("candidatures:candidature_detail", args=[self.cand.pk]))
        self.cand.refresh_from_db()
        self.assertEqual(self.cand.statut, StatutCandidature.EN_TRAITEMENT)

    def test_preselectionner_vue_admin_403(self):
        self.client.force_login(self.adm)
        url = reverse("candidatures:candidature_preselectionner", args=[self.cand.pk])
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 403)


class PlanifierEntretienTests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()
        cand = _candidature_factory(self.dept, self.ts, self.candidat, self.sec)
        preselectionner(cand, self.res)
        self.cand = cand

    def test_planifier_entretien_ok(self):
        from django.utils import timezone
        from suivi.models import Notification
        dt = timezone.now().replace(microsecond=0) + timezone.timedelta(days=5)
        planifier_entretien(self.cand, dt, self.res)
        self.cand.refresh_from_db()
        self.assertEqual(self.cand.date_entretien, dt)
        self.assertFalse(self.cand.candidat_informe)
        self.assertTrue(Notification.objects.filter(destinataire__email="sec@test.com").count() >= 1)

    def test_planifier_date_passee_form_invalide(self):
        from .forms import EntretienForm
        from django.utils import timezone
        dt = timezone.now() - timezone.timedelta(days=1)
        form = EntretienForm({"entretien-date_entretien": dt.strftime("%Y-%m-%dT%H:%M")}, prefix="entretien")
        self.assertFalse(form.is_valid())

    def test_planifier_statut_incorrect_leve_erreur(self):
        from django.utils import timezone
        self.cand.statut = StatutCandidature.RECUE
        self.cand.save(update_fields=["statut"])
        with self.assertRaises(TransitionInterdite):
            planifier_entretien(self.cand, timezone.now() + timezone.timedelta(days=5), self.res)


class AccorderTests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()
        cand = _candidature_factory(self.dept, self.ts, self.candidat, self.sec)
        preselectionner(cand, self.res)
        self.cand = cand

    def test_accorder_ok(self):
        from suivi.models import Notification
        accorder(self.cand, self.res)
        self.cand.refresh_from_db()
        self.assertEqual(self.cand.statut, StatutCandidature.ACCORDEE)
        self.assertFalse(self.cand.candidat_informe)
        self.assertTrue(Notification.objects.filter(destinataire__email="sec@test.com").count() >= 1)

    def test_accorder_non_en_traitement_leve_erreur(self):
        self.cand.statut = StatutCandidature.RECUE
        self.cand.save(update_fields=["statut"])
        with self.assertRaises(TransitionInterdite):
            accorder(self.cand, self.res)

    def test_quota_atteint_leve_exception(self):
        offre = _offre_factory(self.dept, self.ts)
        offre.nombre_places = 1
        offre.save(update_fields=["nombre_places"])
        # Accorder une première candidature sur cette offre
        candidat2 = creer_candidat("Quota", "Test", "70000020")
        cand2 = creer_candidature(
            candidat=candidat2, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SUITE_OFFRE, offre=offre,
            debut_disponibilite="2027-03-01", fin_disponibilite="2027-06-01", duree_souhaitee=2,
            pieces_data=[{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}],
            utilisateur=self.sec,
        )
        cand2.statut = StatutCandidature.ACCORDEE
        cand2.save(update_fields=["statut"])
        # Préparer la deuxième
        candidat3 = creer_candidat("Quota2", "Test", "70000021")
        cand3 = creer_candidature(
            candidat=candidat3, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SUITE_OFFRE, offre=offre,
            debut_disponibilite="2027-03-01", fin_disponibilite="2027-06-01", duree_souhaitee=2,
            pieces_data=[{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}],
            utilisateur=self.sec,
        )
        preselectionner(cand3, self.res)
        with self.assertRaises(QuotaAtteint):
            accorder(cand3, self.res, confirmer_depassement=False)

    def test_quota_peut_etre_depasse_avec_confirmation(self):
        """Accorder malgré quota atteint doit réussir si confirmer_depassement=True."""
        offre = _offre_factory(self.dept, self.ts)
        offre.nombre_places = 1
        offre.save(update_fields=["nombre_places"])
        # Remplir le quota avec une candidature accordée
        candidat_quota = creer_candidat("QuotaConf", "X", "70000022")
        cand_accordee = creer_candidature(
            candidat=candidat_quota, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SUITE_OFFRE, offre=offre,
            debut_disponibilite="2027-03-01", fin_disponibilite="2027-06-01", duree_souhaitee=2,
            pieces_data=[{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}],
            utilisateur=self.sec,
        )
        cand_accordee.statut = StatutCandidature.ACCORDEE
        cand_accordee.save(update_fields=["statut"])
        # Préparer une 2e cand SUITE_OFFRE pour la même offre
        candidat_depassement = creer_candidat("QuotaDep", "Y", "70000023")
        cand_dep = creer_candidature(
            candidat=candidat_depassement, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SUITE_OFFRE, offre=offre,
            debut_disponibilite="2027-03-01", fin_disponibilite="2027-06-01", duree_souhaitee=2,
            pieces_data=[{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}],
            utilisateur=self.sec,
        )
        preselectionner(cand_dep, self.res)
        # Quota atteint → sans confirmation → QuotaAtteint
        with self.assertRaises(QuotaAtteint):
            accorder(cand_dep, self.res, confirmer_depassement=False)
        # Avec confirmation → succès
        accorder(cand_dep, self.res, confirmer_depassement=True)
        cand_dep.refresh_from_db()
        self.assertEqual(cand_dep.statut, StatutCandidature.ACCORDEE)


class RefuserTests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()
        self.cand = _candidature_factory(self.dept, self.ts, self.candidat, self.sec)

    def test_refuser_depuis_recue_ok(self):
        refuser(self.cand, MotifRefus.PROFIL_INADAPTE, "", self.res)
        self.cand.refresh_from_db()
        self.assertEqual(self.cand.statut, StatutCandidature.REFUSEE)
        self.assertFalse(self.cand.candidat_informe)

    def test_refuser_depuis_en_traitement_ok(self):
        preselectionner(self.cand, self.res)
        refuser(self.cand, MotifRefus.PROFIL_INADAPTE, "", self.res)
        self.cand.refresh_from_db()
        self.assertEqual(self.cand.statut, StatutCandidature.REFUSEE)

    def test_refuser_autre_sans_precision_leve_erreur(self):
        with self.assertRaises(TransitionInterdite):
            refuser(self.cand, MotifRefus.AUTRE, "", self.res)

    def test_refuser_autre_avec_precision_ok(self):
        refuser(self.cand, MotifRefus.AUTRE, "Raison spécifique", self.res)
        self.cand.refresh_from_db()
        self.assertEqual(self.cand.statut, StatutCandidature.REFUSEE)
        self.assertEqual(self.cand.precision_motif, "Raison spécifique")

    def test_refuser_vue_admin_403(self):
        self.client.force_login(self.adm)
        url = reverse("candidatures:candidature_refuser", args=[self.cand.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)


class RedirigerTests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()
        self.cand = _candidature_factory(self.dept, self.ts, self.candidat, self.sec)
        self.dept2 = Departement.objects.create(nom="Marketing", actif=True)
        membre2 = Personnel.objects.create(nom="Resp2", prenom="R2", departement=self.dept2, actif=True)
        g_res = Group.objects.get(name="Responsable")
        self.res2 = Utilisateur.objects.create_user(email="res2@test.com", password="pass")
        self.res2.groups.add(g_res)
        self.res2.personnel = membre2
        self.res2.save()

    def test_rediriger_ok(self):
        from suivi.models import Notification
        rediriger(self.cand, self.dept2, "Compétences marketing", self.res)
        self.cand.refresh_from_db()
        self.assertEqual(self.cand.departement, self.dept2)
        self.assertFalse(self.cand.candidat_informe)
        # Notif au responsable du nouveau dept
        self.assertTrue(Notification.objects.filter(destinataire__email="res2@test.com").count() >= 1)
        # Notif aux secrétaires
        self.assertTrue(Notification.objects.filter(destinataire__email="sec@test.com").count() >= 1)

    def test_rediriger_meme_dept_leve_erreur(self):
        with self.assertRaises(TransitionInterdite):
            rediriger(self.cand, self.dept, "Auto-redirection", self.res)

    def test_rediriger_non_recue_leve_erreur(self):
        preselectionner(self.cand, self.res)
        with self.assertRaises(TransitionInterdite):
            rediriger(self.cand, self.dept2, "Trop tard", self.res)

    def test_rediriger_notifie_admins_si_pas_responsable(self):
        """Département sans responsable → admins notifiés."""
        from suivi.models import Notification
        dept3 = Departement.objects.create(nom="SansResp", actif=True)
        candidat2 = creer_candidat("Redir", "Test", "70000030")
        cand2 = _candidature_factory(self.dept, self.ts, candidat2, self.sec)
        rediriger(cand2, dept3, "Redirection test", self.res)
        self.assertTrue(Notification.objects.filter(destinataire__email="adm@test.com").count() >= 1)

    def test_rediriger_vue_post_ok(self):
        self.client.force_login(self.res)
        url = reverse("candidatures:candidature_rediriger", args=[self.cand.pk])
        response = self.client.post(url, {
            "nouveau_departement": self.dept2.pk,
            "motif": "Compétences marketing",
        })
        self.cand.refresh_from_db()
        self.assertEqual(self.cand.departement, self.dept2)


# ─── Lot B — Nouveaux tests ────────────────────────────────────────────────────


class TypeDemandAUTRETests(TestCase):
    """AUTRE : offre interdite, contrainte RG09 respectée."""

    def setUp(self):
        _, _, _, self.dept, self.ts, self.candidat = _setup_base()

    def test_autre_sans_offre_valide(self):
        from django.core.exceptions import ValidationError
        c = Candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.AUTRE, offre=None,
            debut_disponibilite="2027-03-01", fin_disponibilite="2027-06-01",
            duree_souhaitee=2,
        )
        c.clean()  # ne doit pas lever d'exception

    def test_autre_avec_offre_invalide(self):
        from django.core.exceptions import ValidationError
        offre = _offre_factory(self.dept, self.ts)
        c = Candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.AUTRE, offre=offre,
            debut_disponibilite="2027-03-01", fin_disponibilite="2027-06-01",
            duree_souhaitee=2,
        )
        with self.assertRaises(ValidationError):
            c.clean()


class PieceJointePDFSeulementTests(TestCase):
    """_valider_piece_jointe : PDF uniquement, 3 Mo, magic bytes."""

    def _valider(self, fichier):
        from .models import _valider_piece_jointe
        return _valider_piece_jointe(fichier)

    def test_pdf_valide_accepte(self):
        self._valider(_fake_pdf())  # ne doit pas lever

    def test_jpg_refuse(self):
        from django.core.exceptions import ValidationError
        jpg = SimpleUploadedFile("photo.jpg", b"%PDF" + b"fake", content_type="image/jpeg")
        # Extension .jpg → refusée même si magic OK
        with self.assertRaises(ValidationError):
            self._valider(jpg)

    def test_png_refuse(self):
        from django.core.exceptions import ValidationError
        png = SimpleUploadedFile("img.png", b"\x89PNG fake", content_type="image/png")
        with self.assertRaises(ValidationError):
            self._valider(png)

    def test_fichier_trop_gros_3mo(self):
        from django.core.exceptions import ValidationError
        gros = SimpleUploadedFile("gros.pdf", b"%PDF" + b"0" * (3 * 1024 * 1024 + 1))
        with self.assertRaises(ValidationError):
            self._valider(gros)

    def test_fichier_3mo_exact_accepte(self):
        ok = SimpleUploadedFile("ok.pdf", b"%PDF" + b"0" * (3 * 1024 * 1024 - 4))
        self._valider(ok)  # ne doit pas lever

    def test_magic_bytes_invalides(self):
        from django.core.exceptions import ValidationError
        faux = SimpleUploadedFile("faux.pdf", b"PK\x03\x04 fake zip")
        with self.assertRaises(ValidationError):
            self._valider(faux)


class ServiceValidationCandidatureTests(TestCase):
    """_valider_candidature via creer_candidature / modifier_candidature."""

    def setUp(self):
        self.sec, _, _, self.dept, self.ts, self.candidat = _setup_base()
        self.pieces = [{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}]

    def _creer(self, **kwargs):
        defaults = dict(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE,
            debut_disponibilite="2027-03-01", fin_disponibilite="2027-06-01",
            duree_souhaitee=2, pieces_data=self.pieces, utilisateur=self.sec,
        )
        defaults.update(kwargs)
        return creer_candidature(**defaults)

    def test_debut_passe_creation_bloque(self):
        from .services import ValidationCandidature
        with self.assertRaises(ValidationCandidature):
            self._creer(debut_disponibilite="2026-01-01", fin_disponibilite="2026-07-01")

    def test_fin_dispo_plus_12_mois_bloque(self):
        from .services import ValidationCandidature
        with self.assertRaises(ValidationCandidature):
            self._creer(fin_disponibilite="2028-04-01")  # > 2027-03-01 + 12 mois

    def test_fin_dispo_exactement_12_mois_ok(self):
        from commun.utils import ajouter_mois
        from datetime import date
        debut = date(2027, 3, 1)
        fin = ajouter_mois(debut, 12)  # = 2028-03-01
        self._creer(fin_disponibilite=fin.isoformat())

    def test_duree_souhaitee_en_dessous_min_bloque(self):
        from .services import ValidationCandidature
        with self.assertRaises(ValidationCandidature):
            self._creer(duree_souhaitee=0)

    def test_duree_souhaitee_au_dessus_max_bloque(self):
        from .services import ValidationCandidature
        with self.assertRaises(ValidationCandidature):
            self._creer(duree_souhaitee=7)  # ts.duree_max_mois = 6

    def test_creation_sans_cv_bloque(self):
        from .services import ValidationCandidature
        with self.assertRaises(ValidationCandidature):
            self._creer(
                pieces_data=[{
                    "type_piece": TypePiece.LETTRE_MOTIVATION,
                    "fichier": _fake_pdf("lettre.pdf"),
                    "nom_original": "lettre.pdf",
                }]
            )

    def test_modification_debut_passe_si_inchange_ok(self):
        """Modification sans changer debut_disponibilite : pas de refus même si date passée."""
        cand = self._creer()
        # Simuler une candidature avec un début passé en base
        Candidature.objects.filter(pk=cand.pk).update(debut_disponibilite="2026-01-01")
        cand.refresh_from_db()
        from .services import modifier_candidature
        # Ne doit pas lever ValidationCandidature (date inchangée)
        modifier_candidature(
            candidature=cand,
            departement=self.dept,
            type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE,
            debut_disponibilite=cand.debut_disponibilite,  # inchangé
            fin_disponibilite="2026-07-01",
            duree_souhaitee=2,
            utilisateur=self.sec,
        )

    def test_modification_debut_passe_si_change_bloque(self):
        """Modification avec un nouveau début passé → refusé."""
        cand = self._creer()
        from .services import modifier_candidature, ValidationCandidature
        with self.assertRaises(ValidationCandidature):
            modifier_candidature(
                candidature=cand,
                departement=self.dept,
                type_stage=self.ts,
                type_demande=TypeDemande.SPONTANEE,
                debut_disponibilite="2026-01-01",  # nouveau début passé
                fin_disponibilite="2026-07-01",
                duree_souhaitee=2,
                utilisateur=self.sec,
            )


class FormulaireCandidatureValidationTests(TestCase):
    """Validations de CandidatureCreerForm et CandidatureModifierForm."""

    def setUp(self):
        self.sec, _, _, self.dept, self.ts, self.candidat = _setup_base()

    def _form_data(self, **kwargs):
        data = {
            "departement": self.dept.pk,
            "type_stage": self.ts.pk,
            "type_demande": "SPONTANEE",
            "debut_disponibilite": "2027-03-01",
            "fin_disponibilite": "2027-06-01",
            "duree_souhaitee": 2,
            "commentaire": "",
        }
        data.update(kwargs)
        return data

    def test_debut_passe_invalide(self):
        from .forms import CandidatureCreerForm
        form = CandidatureCreerForm(self._form_data(debut_disponibilite="2026-01-01"))
        self.assertFalse(form.is_valid())
        self.assertIn("debut_disponibilite", form.errors)

    def test_fin_plus_12_mois_invalide(self):
        from .forms import CandidatureCreerForm
        form = CandidatureCreerForm(self._form_data(fin_disponibilite="2028-05-01"))
        self.assertFalse(form.is_valid())
        self.assertIn("fin_disponibilite", form.errors)

    def test_duree_hors_bornes_invalide(self):
        from .forms import CandidatureCreerForm
        form = CandidatureCreerForm(self._form_data(duree_souhaitee=10))  # max=6
        self.assertFalse(form.is_valid())
        self.assertIn("duree_souhaitee", form.errors)

    def test_autre_avec_offre_invalide(self):
        from .forms import CandidatureCreerForm
        offre = _offre_factory(self.dept, self.ts)
        form = CandidatureCreerForm(self._form_data(type_demande="AUTRE", offre=offre.pk))
        self.assertFalse(form.is_valid())
        self.assertIn("offre", form.errors)

    def test_modifier_form_debut_inchange_passe_ok(self):
        """CandidatureModifierForm : debut inchangé + passé → pas d'erreur."""
        from .forms import CandidatureModifierForm
        from datetime import date
        cand = Candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande="SPONTANEE",
            debut_disponibilite=date(2026, 1, 1),
            fin_disponibilite=date(2026, 7, 1),
            duree_souhaitee=2,
        )
        form = CandidatureModifierForm(
            self._form_data(debut_disponibilite="2026-01-01", fin_disponibilite="2026-07-01"),
            instance=cand,
        )
        # Le seul champ invalide potentiel est fin > debut+12 mais 2026-07-01 <= 2027-01-01 ✓
        # Et debut inchangé → pas d'erreur date passée
        self.assertNotIn("debut_disponibilite", form.errors)


class FormsetUnicitePiecesTests(TestCase):
    """BasePieceJointeFormSet : CV obligatoire + un seul par type (sauf AUTRE)."""

    def test_deux_cv_refuses(self):
        from .forms import PieceJointeFormSet
        data = {
            "pieces-TOTAL_FORMS": "2",
            "pieces-INITIAL_FORMS": "0",
            "pieces-0-type_piece": TypePiece.CV,
            "pieces-1-type_piece": TypePiece.CV,
        }
        files = {
            "pieces-0-fichier": _fake_pdf("cv1.pdf"),
            "pieces-1-fichier": _fake_pdf("cv2.pdf"),
        }
        fs = PieceJointeFormSet(data, files, prefix="pieces")
        self.assertFalse(fs.is_valid())
        self.assertTrue(any("seul" in str(e).lower() or "CV" in str(e) for e in fs.non_form_errors()))

    def test_deux_autres_autorises(self):
        from .forms import PieceJointeFormSet
        data = {
            "pieces-TOTAL_FORMS": "2",
            "pieces-INITIAL_FORMS": "0",
            "pieces-0-type_piece": TypePiece.CV,
            "pieces-1-type_piece": TypePiece.AUTRE,
        }
        files = {
            "pieces-0-fichier": _fake_pdf("cv.pdf"),
            "pieces-1-fichier": _fake_pdf("autre.pdf"),
        }
        fs = PieceJointeFormSet(data, files, prefix="pieces")
        self.assertTrue(fs.is_valid(), msg=str(fs.errors) + str(fs.non_form_errors()))


# ─── Lot D — D1 : règle 72 h avant entretien ─────────────────────────────────


class Entretien72hTests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()
        cand = _candidature_factory(self.dept, self.ts, self.candidat, self.sec)
        preselectionner(cand, self.res)
        self.cand = cand

    def test_entretien_moins_72h_interdit(self):
        from django.utils import timezone
        dt = timezone.now() + timezone.timedelta(hours=24)
        with self.assertRaises(TransitionInterdite):
            planifier_entretien(self.cand, dt, self.res)

    def test_entretien_plus_72h_accepte(self):
        from django.utils import timezone
        from suivi.models import Notification
        dt = timezone.now() + timezone.timedelta(hours=73)
        planifier_entretien(self.cand, dt, self.res)
        self.cand.refresh_from_db()
        self.assertEqual(self.cand.date_entretien, dt)

    def test_form_entretien_moins_72h_invalide(self):
        from .forms import EntretienForm
        from django.utils import timezone
        dt = timezone.now() + timezone.timedelta(hours=24)
        form = EntretienForm(
            {"date_entretien": dt.strftime("%Y-%m-%dT%H:%M")},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("date_entretien", form.errors)

    def test_form_entretien_73h_valide(self):
        from .forms import EntretienForm
        from django.utils import timezone
        dt = timezone.now() + timezone.timedelta(hours=73)
        form = EntretienForm(
            {"date_entretien": dt.strftime("%Y-%m-%dT%H:%M")},
        )
        self.assertTrue(form.is_valid(), msg=str(form.errors))


# ─── Lot D — D2 : alerte secrétariat entretien < 48 h ────────────────────────


class AlerterEntretiensCommandTests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()

    def _cand_avec_entretien(self, delta_heures):
        from django.utils import timezone
        cand = _candidature_factory(self.dept, self.ts, self.candidat, self.sec)
        preselectionner(cand, self.res)
        cand.date_entretien = timezone.now() + timezone.timedelta(hours=delta_heures)
        cand.candidat_informe = False
        cand.alerte_entretien_envoyee = False
        cand.save(update_fields=["date_entretien", "candidat_informe", "alerte_entretien_envoyee"])
        return cand

    def test_alerte_envoyee_entretien_dans_24h(self):
        from django.core.management import call_command
        from io import StringIO
        cand = self._cand_avec_entretien(24)
        out = StringIO()
        call_command("alerter_entretiens", stdout=out)
        cand.refresh_from_db()
        self.assertTrue(cand.alerte_entretien_envoyee)
        self.assertIn("1 alerte", out.getvalue())

    def test_pas_alerte_si_deja_envoyee(self):
        from django.core.management import call_command
        from io import StringIO
        cand = self._cand_avec_entretien(24)
        cand.alerte_entretien_envoyee = True
        cand.save(update_fields=["alerte_entretien_envoyee"])
        out = StringIO()
        call_command("alerter_entretiens", stdout=out)
        self.assertIn("0 alerte", out.getvalue())

    def test_pas_alerte_si_candidat_informe(self):
        from django.core.management import call_command
        from io import StringIO
        cand = self._cand_avec_entretien(24)
        cand.candidat_informe = True
        cand.save(update_fields=["candidat_informe"])
        out = StringIO()
        call_command("alerter_entretiens", stdout=out)
        self.assertIn("0 alerte", out.getvalue())

    def test_pas_alerte_si_entretien_lointain(self):
        from django.core.management import call_command
        from io import StringIO
        cand = self._cand_avec_entretien(96)  # 4 jours — hors < 48 h
        out = StringIO()
        call_command("alerter_entretiens", stdout=out)
        cand.refresh_from_db()
        self.assertFalse(cand.alerte_entretien_envoyee)


# ─── Lot D — D3 : TransfertCandidature ───────────────────────────────────────


class TransfertCandidatureTests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()
        self.dept2 = Departement.objects.create(nom="RH", actif=True)
        self.cand = _candidature_factory(self.dept, self.ts, self.candidat, self.sec)

    def test_rediriger_cree_transfert(self):
        from .models import TransfertCandidature
        rediriger(self.cand, self.dept2, "Mieux adapté", self.res)
        self.assertEqual(TransfertCandidature.objects.filter(candidature=self.cand).count(), 1)

    def test_transfert_source_et_cible_corrects(self):
        from .models import TransfertCandidature
        rediriger(self.cand, self.dept2, "Test", self.res)
        t = TransfertCandidature.objects.get(candidature=self.cand)
        self.assertEqual(t.departement_source, self.dept)
        self.assertEqual(t.departement_cible, self.dept2)
        self.assertEqual(t.motif, "Test")
        self.assertEqual(t.realise_par, self.res)

    def test_deux_redirections_deux_transferts(self):
        from .models import TransfertCandidature
        dept3 = Departement.objects.create(nom="Comptabilité", actif=True)
        rediriger(self.cand, self.dept2, "Premier", self.res)
        self.cand.refresh_from_db()
        rediriger(self.cand, dept3, "Deuxième", self.res)
        self.assertEqual(TransfertCandidature.objects.filter(candidature=self.cand).count(), 2)
