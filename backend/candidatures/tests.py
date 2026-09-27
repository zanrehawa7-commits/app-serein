import io
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from comptes.models import Utilisateur
from offres.models import Offre, StatutOffre
from referentiels.models import Departement, TypeStage, Membre

from .models import Candidat, Candidature, PieceJointe, StatutCandidature, TypeDemande, TypePiece
from .services import (
    CandidatExistant,
    CandidatureActiveExistante,
    creer_candidat,
    creer_candidature,
    marquer_informe,
    normaliser_telephone,
    rechercher_candidats,
)

import tempfile, os
from pathlib import Path


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
        date_debut="2026-10-01",
        date_fin="2026-12-31",
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
    ts = TypeStage.objects.create(libelle="Stage pro", actif=True)

    membre = Membre.objects.create(nom="Responsable", prenom="R", departement=dept, actif=True)
    res = Utilisateur.objects.create_user(email="res@test.com", password="pass", first_name="Res")
    res.groups.add(g_res)
    res.membre = membre
    res.save()

    candidat = creer_candidat("Test", "Candidat", "70999999")
    return sec, adm, res, dept, ts, candidat


# ─── RG07 — candidature active unique ─────────────────────────────────────────


@override_settings(FICHIERS_PRIVES_ROOT=tempfile.mkdtemp())
class RG07Tests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()
        self.pieces = [{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}]

    def test_rg07_bloque_deuxieme_candidature_active(self):
        creer_candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2026-10-01",
            fin_disponibilite="2026-12-31", duree_souhaitee=2,
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
            debut_disponibilite="2026-10-01", fin_disponibilite="2026-12-31",
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
            debut_disponibilite="2026-10-01", fin_disponibilite="2026-12-31",
            duree_souhaitee=2,
        )
        with self.assertRaises(ValidationError):
            c.clean()

    def test_suite_offre_non_ouverte_form_invalide(self):
        """Le formulaire ne doit pas proposer d'offre non OUVERTE."""
        from .forms import CandidatureForm
        offre_fermee = _offre_factory(self.dept, self.ts, statut=StatutOffre.FERMEE)
        form = CandidatureForm()
        self.assertNotIn(offre_fermee, form.fields["offre"].queryset)


# ─── Création candidature ─────────────────────────────────────────────────────


@override_settings(FICHIERS_PRIVES_ROOT=tempfile.mkdtemp())
class CreationCandidatureTests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()

    def test_creation_statut_recue_reference_historique(self):
        pieces = [{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}]
        c = creer_candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2026-10-01",
            fin_disponibilite="2026-12-31", duree_souhaitee=2,
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
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2026-10-01",
            fin_disponibilite="2026-12-31", duree_souhaitee=2,
            pieces_data=pieces, utilisateur=self.sec,
        )
        candidat2 = creer_candidat("Zombre", "Z", "70000001")
        c2 = creer_candidature(
            candidat=candidat2, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2026-10-01",
            fin_disponibilite="2026-12-31", duree_souhaitee=2,
            pieces_data=[{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}],
            utilisateur=self.sec,
        )
        self.assertNotEqual(c1.reference, c2.reference)

    def test_notification_responsable(self):
        from suivi.models import Notification
        pieces = [{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}]
        creer_candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2026-10-01",
            fin_disponibilite="2026-12-31", duree_souhaitee=2,
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
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2026-10-01",
            fin_disponibilite="2026-12-31", duree_souhaitee=2,
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


@override_settings(FICHIERS_PRIVES_ROOT=tempfile.mkdtemp())
class ModificationCandidatureTests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()
        pieces = [{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}]
        self.candidature = creer_candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2026-10-01",
            fin_disponibilite="2026-12-31", duree_souhaitee=2,
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


@override_settings(FICHIERS_PRIVES_ROOT=tempfile.mkdtemp())
class MarquerInformeTests(TestCase):
    def setUp(self):
        self.sec, self.adm, self.res, self.dept, self.ts, self.candidat = _setup_base()
        pieces = [{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}]
        self.candidature = creer_candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2026-10-01",
            fin_disponibilite="2026-12-31", duree_souhaitee=2,
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


@override_settings(FICHIERS_PRIVES_ROOT=tempfile.mkdtemp())
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
            debut_disponibilite="2026-10-01", fin_disponibilite="2026-12-31", duree_souhaitee=2,
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
        membre2 = Membre.objects.create(nom="Res2", prenom="R", departement=self.dept2, actif=True)
        g_res = Group.objects.get(name="Responsable")
        self.res2 = Utilisateur.objects.create_user(email="res2@test.com", password="pass")
        self.res2.groups.add(g_res)
        self.res2.membre = membre2
        self.res2.save()

    @override_settings(FICHIERS_PRIVES_ROOT=tempfile.mkdtemp())
    def test_responsable_autre_dept_candidature_detail_403(self):
        pieces = [{"type_piece": TypePiece.CV, "fichier": _fake_pdf(), "nom_original": "cv.pdf"}]
        candidature = creer_candidature(
            candidat=self.candidat, departement=self.dept, type_stage=self.ts,
            type_demande=TypeDemande.SPONTANEE, debut_disponibilite="2026-10-01",
            fin_disponibilite="2026-12-31", duree_souhaitee=2,
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
