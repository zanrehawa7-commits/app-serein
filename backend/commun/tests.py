import tempfile
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.files.base import ContentFile
from django.test import SimpleTestCase, override_settings

from candidatures.models import PieceJointe
from commun.test_runner import _fichiers
from commun.utils import ajouter_mois
from stages.models import Stage


class StockagePriveTests(SimpleTestCase):
    """Les tests n'écrivent jamais dans le vrai dossier des fichiers privés."""

    def test_settings_test_pointe_hors_du_vrai_dossier(self):
        reel = Path(settings.FICHIERS_PRIVES_ROOT_REEL).resolve()
        test = Path(settings.FICHIERS_PRIVES_ROOT).resolve()
        self.assertNotEqual(test, reel)
        self.assertNotIn(reel, test.parents)

    def test_stockages_suivent_le_reglage_a_l_execution(self):
        stockages = [
            PieceJointe._meta.get_field("fichier").storage,
            Stage._meta.get_field("rapport").storage,
        ]
        with tempfile.TemporaryDirectory() as autre:
            with override_settings(FICHIERS_PRIVES_ROOT=autre):
                for stockage in stockages:
                    with self.subTest(stockage=stockage):
                        self.assertEqual(Path(stockage.location), Path(autre).resolve())

    def test_ecriture_dans_le_dossier_de_test_seulement(self):
        reel = settings.FICHIERS_PRIVES_ROOT_REEL
        avant = _fichiers(reel)
        stockage = PieceJointe._meta.get_field("fichier").storage
        nom = stockage.save("candidatures/test/sonde.pdf", ContentFile(b"%PDF-1.4"))
        try:
            chemin = Path(stockage.path(nom)).resolve()
            self.assertIn(Path(settings.FICHIERS_PRIVES_ROOT).resolve(), chemin.parents)
            self.assertEqual(_fichiers(reel), avant)
        finally:
            stockage.delete(nom)


class AjouterMoisTests(SimpleTestCase):

    # ── Cas normaux ───────────────────────────────────────────────────────────

    def test_cas_normal(self):
        self.assertEqual(ajouter_mois(date(2024, 3, 15), 2), date(2024, 5, 15))

    def test_n_zero(self):
        self.assertEqual(ajouter_mois(date(2024, 6, 10), 0), date(2024, 6, 10))

    def test_changement_annee(self):
        self.assertEqual(ajouter_mois(date(2024, 11, 15), 2), date(2025, 1, 15))

    def test_premier_janvier_plus_12(self):
        self.assertEqual(ajouter_mois(date(2024, 1, 1), 12), date(2025, 1, 1))

    # ── Fins de mois ─────────────────────────────────────────────────────────

    def test_31_janvier_plus_1_annee_non_bissextile(self):
        """31/01/2023 + 1 mois = 28/02/2023"""
        self.assertEqual(ajouter_mois(date(2023, 1, 31), 1), date(2023, 2, 28))

    def test_31_janvier_plus_1_annee_bissextile(self):
        """31/01/2024 + 1 mois = 29/02/2024"""
        self.assertEqual(ajouter_mois(date(2024, 1, 31), 1), date(2024, 2, 29))

    def test_31_mars_plus_1(self):
        """31/03 + 1 mois = 30/04"""
        self.assertEqual(ajouter_mois(date(2024, 3, 31), 1), date(2024, 4, 30))

    def test_31_mai_plus_1(self):
        """31/05 + 1 mois = 30/06"""
        self.assertEqual(ajouter_mois(date(2024, 5, 31), 1), date(2024, 6, 30))

    def test_31_decembre_plus_1(self):
        """31/12 + 1 mois = 31/01 de l'année suivante"""
        self.assertEqual(ajouter_mois(date(2024, 12, 31), 1), date(2025, 1, 31))

    def test_30_novembre_plus_3(self):
        """30/11 + 3 mois = 28/02 (non bissextile)"""
        self.assertEqual(ajouter_mois(date(2023, 11, 30), 3), date(2024, 2, 29))

    # ── Années bissextiles ────────────────────────────────────────────────────

    def test_29_fevrier_bissextile_plus_12_non_bissextile(self):
        """29/02/2024 + 12 mois → 28/02/2025 (2025 non bissextile)"""
        self.assertEqual(ajouter_mois(date(2024, 2, 29), 12), date(2025, 2, 28))

    def test_29_fevrier_bissextile_plus_48(self):
        """29/02/2024 + 48 mois → 29/02/2028 (2028 bissextile)"""
        self.assertEqual(ajouter_mois(date(2024, 2, 29), 48), date(2028, 2, 29))

    # ── Cas limites métier (12 mois max fin_disponibilite) ────────────────────

    def test_fin_dispo_exactement_12_mois(self):
        """Cas réel : debut_dispo = 01/03/2024, fin = ajouter_mois(debut, 12) = 01/03/2025"""
        self.assertEqual(ajouter_mois(date(2024, 3, 1), 12), date(2025, 3, 1))

    def test_fin_dispo_debut_31_janvier_12_mois(self):
        """31/01/2024 + 12 mois = 31/01/2025"""
        self.assertEqual(ajouter_mois(date(2024, 1, 31), 12), date(2025, 1, 31))
