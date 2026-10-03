from io import StringIO
from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db.models import ProtectedError
from django.test import Client, TestCase
from django.urls import reverse

from comptes.models import Utilisateur
from referentiels.models import Departement, Etablissement, Personnel, TypeStage
from referentiels.services import (
    ConfirmationRequise,
    CreerCompteRequis,
    TransitionInterdite,
    designer_responsable,
)


def _creer_utilisateur(email, password="pass1234!", groupe=None, is_superuser=False, personnel=None):
    user = Utilisateur.objects.create_user(
        email=email, password=password,
        first_name="Test", last_name="User",
        is_superuser=is_superuser,
    )
    if groupe:
        grp, _ = Group.objects.get_or_create(name=groupe)
        user.groups.add(grp)
    if personnel:
        user.personnel = personnel
        user.save(update_fields=["personnel"])
    return user


# ─── Tests AccèsRoles ─────────────────────────────────────────────────────────

class AccesRolesTests(TestCase):
    """Secrétaire et Responsable reçoivent 403 sur toutes les pages du module référentiels."""

    def setUp(self):
        self.secretaire = _creer_utilisateur("sec@serein.bf", groupe="Secrétaire")
        self.responsable = _creer_utilisateur("resp@serein.bf", groupe="Responsable")
        self.dept = Departement.objects.create(nom="Dept Test")
        self.ts = TypeStage.objects.create(libelle="Stage test", duree_min_mois=1, duree_max_mois=6)
        self.etab = Etablissement.objects.create(nom="Ecole A", ville="Ouaga")
        self.personnel = Personnel.objects.create(nom="Doe", prenom="John", departement=self.dept)

    def _assert_403(self, url_name, url_kwargs=None):
        for user in [self.secretaire, self.responsable]:
            with self.subTest(role=user.role, url=url_name):
                self.client.force_login(user)
                resp = self.client.get(reverse(url_name, kwargs=url_kwargs or {}))
                self.assertIn(
                    resp.status_code, [403, 302],
                    msg=f"{user.role} sur {url_name} devrait recevoir 403 ou redirect vers login",
                )

    def test_departement_list_interdit(self):
        self._assert_403("referentiels:departement_list")

    def test_departement_creer_interdit(self):
        self._assert_403("referentiels:departement_creer")

    def test_departement_detail_interdit(self):
        self._assert_403("referentiels:departement_detail", {"pk": self.dept.pk})

    def test_departement_modifier_interdit(self):
        self._assert_403("referentiels:departement_modifier", {"pk": self.dept.pk})

    def test_etablissement_list_interdit(self):
        self._assert_403("referentiels:etablissement_list")

    def test_etablissement_creer_interdit(self):
        self._assert_403("referentiels:etablissement_creer")

    def test_typestage_list_interdit(self):
        self._assert_403("referentiels:typestage_list")

    def test_typestage_creer_interdit(self):
        self._assert_403("referentiels:typestage_creer")

    def test_typestage_modifier_interdit(self):
        self._assert_403("referentiels:typestage_modifier", {"pk": self.ts.pk})

    def test_canalpublication_list_interdit(self):
        self._assert_403("referentiels:canalpublication_list")

    def test_personnel_list_interdit(self):
        self._assert_403("referentiels:personnel_list")

    def test_personnel_creer_interdit(self):
        self._assert_403("referentiels:personnel_creer")

    def test_personnel_modifier_interdit(self):
        self._assert_403("referentiels:personnel_modifier", {"pk": self.personnel.pk})


class AffichageListesAdministrateurTests(TestCase):
    """Les listes s'affichent réellement (200) : détecte les erreurs de template."""

    def setUp(self):
        dept = Departement.objects.create(nom="Dept Test")
        personnel = Personnel.objects.create(nom="Doe", prenom="John", departement=dept)
        _creer_utilisateur("perso@serein.bf", groupe="Secrétaire", personnel=personnel)
        Personnel.objects.create(nom="Sans", prenom="Compte")
        self.client.force_login(_creer_utilisateur("admin@serein.bf", is_superuser=True))

    def test_listes_referentiels_200(self):
        for url_name in [
            "referentiels:departement_list",
            "referentiels:etablissement_list",
            "referentiels:typestage_list",
            "referentiels:canalpublication_list",
            "referentiels:personnel_list",
        ]:
            with self.subTest(url=url_name):
                self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)


# ─── Tests TypeStage suppression ──────────────────────────────────────────────

class TypeStageSuppressionTests(TestCase):
    """Suppression TypeStage : désactivation si ProtectedError."""

    def setUp(self):
        self.admin = _creer_utilisateur("admin@serein.bf", is_superuser=True)
        self.ts = TypeStage.objects.create(libelle="Stage utilisé", actif=True, duree_min_mois=1, duree_max_mois=6)

    def test_suppression_non_utilise(self):
        self.client.force_login(self.admin)
        url = reverse("referentiels:typestage_supprimer", kwargs={"pk": self.ts.pk})
        self.client.post(url)
        self.assertFalse(TypeStage.objects.filter(pk=self.ts.pk).exists())

    def test_suppression_protegee_desactive_au_lieu_de_supprimer(self):
        self.client.force_login(self.admin)
        url = reverse("referentiels:typestage_supprimer", kwargs={"pk": self.ts.pk})
        with patch.object(TypeStage, "delete", side_effect=ProtectedError("en utilisation", set())):
            self.client.post(url)
        self.ts.refresh_from_db()
        self.assertTrue(TypeStage.objects.filter(pk=self.ts.pk).exists())
        self.assertFalse(self.ts.actif)


# ─── Tests Personnel désactivation ────────────────────────────────────────────

class PersonnelDesactiverTests(TestCase):
    """Désactivation personnel : refusée si responsable actuel."""

    def setUp(self):
        self.admin = _creer_utilisateur("admin@serein.bf", is_superuser=True)
        self.dept = Departement.objects.create(nom="Dept Test")
        self.personnel = Personnel.objects.create(
            nom="Doe", prenom="John", departement=self.dept, actif=True
        )

    def test_desactiver_personnel_non_responsable_ok(self):
        self.client.force_login(self.admin)
        url = reverse("referentiels:personnel_desactiver", kwargs={"pk": self.personnel.pk})
        self.client.post(url)
        self.personnel.refresh_from_db()
        self.assertFalse(self.personnel.actif)

    def test_desactiver_personnel_responsable_refuse(self):
        self.dept.responsable = self.personnel
        self.dept.save()
        self.client.force_login(self.admin)
        url = reverse("referentiels:personnel_desactiver", kwargs={"pk": self.personnel.pk})
        self.client.post(url)
        self.personnel.refresh_from_db()
        self.assertTrue(self.personnel.actif, "Le responsable ne doit PAS être désactivé")

    def test_reactiver_personnel_desactive(self):
        self.personnel.actif = False
        self.personnel.save()
        self.client.force_login(self.admin)
        url = reverse("referentiels:personnel_desactiver", kwargs={"pk": self.personnel.pk})
        self.client.post(url)
        self.personnel.refresh_from_db()
        self.assertTrue(self.personnel.actif)


# ─── Tests DesignerResponsable (service) ──────────────────────────────────────

class DesignerResponsableTests(TestCase):

    def setUp(self):
        self.dept = Departement.objects.create(nom="Informatique")
        self.personnel = Personnel.objects.create(
            nom="Traoré", prenom="Paul", departement=self.dept, actif=True
        )
        self.admin_user = _creer_utilisateur("admin@serein.bf", is_superuser=True)
        Utilisateur.objects.get_or_create_superuser = None  # pas utile

    def _creer_compte_responsable(self, personnel, email):
        groupe, _ = Group.objects.get_or_create(name="Responsable")
        user = Utilisateur.objects.create_user(
            email=email, password="pass1234!",
            first_name=personnel.prenom, last_name=personnel.nom,
        )
        user.groups.add(groupe)
        user.personnel = personnel
        user.save(update_fields=["personnel"])
        return user

    def test_designation_simple(self):
        compte = self._creer_compte_responsable(self.personnel, "resp@test.bf")
        designer_responsable(self.personnel, self.admin_user, confirmer=True)
        self.dept.refresh_from_db()
        self.assertEqual(self.dept.responsable, self.personnel)

    def test_personnel_inactif_interdit(self):
        self.personnel.actif = False
        self.personnel.save()
        with self.assertRaises(TransitionInterdite):
            designer_responsable(self.personnel, self.admin_user)

    def test_personnel_sans_departement_interdit(self):
        p = Personnel.objects.create(nom="Sans", prenom="Dept", departement=None, actif=True)
        with self.assertRaises(TransitionInterdite):
            designer_responsable(p, self.admin_user)

    def test_personnel_sans_compte_leve_creer_compte_requis_sans_modification(self):
        """CreerCompteRequis doit être levée AVANT tout changement en base."""
        ancien = Personnel.objects.create(nom="Ancien", prenom="Resp", departement=self.dept, actif=True)
        ancien_compte = self._creer_compte_responsable(ancien, "ancien@test.bf")
        self.dept.responsable = ancien
        self.dept.save()

        # self.personnel n'a pas de compte
        with self.assertRaises(CreerCompteRequis):
            designer_responsable(self.personnel, self.admin_user, confirmer=True)

        # Aucune modification en base : l'ancien responsable est toujours actif
        self.dept.refresh_from_db()
        self.assertEqual(self.dept.responsable, ancien)
        ancien_compte.refresh_from_db()
        self.assertTrue(ancien_compte.is_active, "L'ancien responsable doit rester actif")

    def test_remplacement_confirmation_requise_sans_confirmer(self):
        ancien = Personnel.objects.create(nom="Ancien", prenom="Resp", departement=self.dept, actif=True)
        self._creer_compte_responsable(ancien, "ancien@test.bf")
        self.dept.responsable = ancien
        self.dept.save()
        self._creer_compte_responsable(self.personnel, "nouveau@test.bf")

        with self.assertRaises(ConfirmationRequise):
            designer_responsable(self.personnel, self.admin_user, confirmer=False)

        # Aucune modification
        self.dept.refresh_from_db()
        self.assertEqual(self.dept.responsable, ancien)

    def test_remplacement_confirme_desactive_ancien_compte(self):
        ancien = Personnel.objects.create(nom="Ancien", prenom="Resp", departement=self.dept, actif=True)
        ancien_compte = self._creer_compte_responsable(ancien, "ancien@test.bf")
        self.dept.responsable = ancien
        self.dept.save()
        self._creer_compte_responsable(self.personnel, "nouveau@test.bf")
        # Groupe admin pour recevoir la notif
        Group.objects.get_or_create(name="Administrateur")

        designer_responsable(self.personnel, self.admin_user, confirmer=True)

        self.dept.refresh_from_db()
        self.assertEqual(self.dept.responsable, self.personnel)
        ancien_compte.refresh_from_db()
        self.assertFalse(ancien_compte.is_active, "Le compte de l'ancien responsable doit être désactivé")


# ─── Tests Département responsable (formulaire) ───────────────────────────────

class DepartementResponsableFormTests(TestCase):
    """Le formulaire de modification rejette un responsable qui n'est pas dans le département."""

    def setUp(self):
        self.admin = _creer_utilisateur("admin@serein.bf", is_superuser=True)
        self.dept_a = Departement.objects.create(nom="Dept A")
        self.dept_b = Departement.objects.create(nom="Dept B")
        self.personnel_b = Personnel.objects.create(
            nom="Smith", prenom="Jane", departement=self.dept_b, actif=True
        )

    def test_responsable_hors_departement_refuse(self):
        """
        Poster un responsable d'un autre département doit invalider le formulaire :
        le personnel n'est pas dans le queryset restreint au département A.
        """
        self.client.force_login(self.admin)
        url = reverse("referentiels:departement_modifier", kwargs={"pk": self.dept_a.pk})
        resp = self.client.post(url, {
            "nom": self.dept_a.nom,
            "description": "",
            "responsable": self.personnel_b.pk,
            "actif": True,
        })
        # Formulaire invalide ou CreerCompteRequis → redirection ou réaffichage
        self.dept_a.refresh_from_db()
        self.assertIsNone(
            self.dept_a.responsable,
            "Un responsable d'un autre département ne doit pas être accepté",
        )

    def test_responsable_meme_departement_avec_compte_accepte(self):
        """Un personnel du département A avec un compte peut être désigné responsable."""
        personnel_a = Personnel.objects.create(
            nom="Martin", prenom="Paul", departement=self.dept_a, actif=True
        )
        groupe, _ = Group.objects.get_or_create(name="Responsable")
        groupe_admin, _ = Group.objects.get_or_create(name="Administrateur")
        compte = Utilisateur.objects.create_user(
            email="martin@test.bf", password="pass1234!",
            first_name="Paul", last_name="Martin",
        )
        compte.groups.add(groupe)
        compte.personnel = personnel_a
        compte.save(update_fields=["personnel"])

        self.client.force_login(self.admin)
        url = reverse("referentiels:departement_modifier", kwargs={"pk": self.dept_a.pk})
        self.client.post(url, {
            "nom": self.dept_a.nom,
            "description": "",
            "responsable": personnel_a.pk,
            "actif": True,
        })
        self.dept_a.refresh_from_db()
        self.assertEqual(self.dept_a.responsable, personnel_a)


# ─── Tests changement département interdit si responsable ─────────────────────

class PersonnelChangerDeptTests(TestCase):

    def setUp(self):
        self.admin = _creer_utilisateur("admin@serein.bf", is_superuser=True)
        self.dept_a = Departement.objects.create(nom="Dept A")
        self.dept_b = Departement.objects.create(nom="Dept B")
        self.responsable = Personnel.objects.create(
            nom="Kone", prenom="Ibrahim", departement=self.dept_a, actif=True
        )
        self.dept_a.responsable = self.responsable
        self.dept_a.save()

    def test_changer_departement_responsable_refuse(self):
        """Modifier le département d'un responsable via le formulaire doit être refusé."""
        self.client.force_login(self.admin)
        url = reverse("referentiels:personnel_modifier", kwargs={"pk": self.responsable.pk})
        resp = self.client.post(url, {
            "nom": self.responsable.nom,
            "prenom": self.responsable.prenom,
            "fonction": "",
            "telephone": "",
            "email": "",
            "departement": self.dept_b.pk,
            "actif": True,
            "designer_responsable": "",
        })
        # Formulaire invalide → réaffichage avec erreur
        self.assertEqual(resp.status_code, 200)
        self.responsable.refresh_from_db()
        self.assertEqual(
            self.responsable.departement, self.dept_a,
            "Le département du responsable ne doit pas changer",
        )


# ─── Tests permissions *_personnel dans les groupes ───────────────────────────

class PermissionsPersonnelGroupesTests(TestCase):
    """Après init_donnees, les groupes ont *_personnel (pas *_membre)."""

    def setUp(self):
        from referentiels.management.commands.init_donnees import Command
        cmd = Command()
        cmd.stdout = type("FakeOut", (), {"write": lambda s, m: None})()
        cmd._creer_groupes()

    def test_groupe_administrateur_a_permissions_personnel(self):
        groupe = Group.objects.get(name="Administrateur")
        codenames = set(groupe.permissions.values_list("codename", flat=True))
        for action in ["add", "change", "delete", "view"]:
            with self.subTest(action=action):
                self.assertIn(f"{action}_personnel", codenames)

    def test_groupe_administrateur_sans_permissions_membre(self):
        groupe = Group.objects.get(name="Administrateur")
        codenames = set(groupe.permissions.values_list("codename", flat=True))
        for action in ["add", "change", "delete", "view"]:
            with self.subTest(action=action):
                self.assertNotIn(f"{action}_membre", codenames)

    def test_groupe_secretaire_a_view_personnel(self):
        groupe = Group.objects.get(name="Secrétaire")
        codenames = set(groupe.permissions.values_list("codename", flat=True))
        self.assertIn("view_personnel", codenames)

    def test_groupe_responsable_a_view_personnel(self):
        groupe = Group.objects.get(name="Responsable")
        codenames = set(groupe.permissions.values_list("codename", flat=True))
        self.assertIn("view_personnel", codenames)


# ─── Tests commande init_donnees (base neuve) ─────────────────────────────────

class InitDonneesCommandeTests(TestCase):

    def _lancer(self):
        call_command("init_donnees", stdout=StringIO())

    def test_cree_les_types_de_stage_avec_durees_sur_base_vide(self):
        from referentiels.management.commands.init_donnees import TYPES_STAGE
        TypeStage.objects.all().delete()
        self._lancer()
        for libelle, (duree_min, duree_max) in TYPES_STAGE.items():
            with self.subTest(libelle=libelle):
                ts = TypeStage.objects.get(libelle=libelle)
                self.assertEqual((ts.duree_min_mois, ts.duree_max_mois), (duree_min, duree_max))

    def test_permissions_exactes_du_groupe_administrateur(self):
        """CRUD sur comptes et référentiels ; lecture seule sur offres, candidatures, stages, suivi."""
        crud = ["add", "change", "delete", "view"]
        attendues = {f"comptes.{a}_{m}" for m in ["utilisateur", "profilrole"] for a in crud}
        attendues |= {
            f"referentiels.{a}_{m}"
            for m in ["canalpublication", "departement", "etablissement", "personnel", "typestage"]
            for a in crud
        }
        attendues |= {
            "offres.view_besoin", "offres.view_offre", "offres.view_parametreoffre", "offres.view_publication",
            "candidatures.view_candidat", "candidatures.view_candidature",
            "candidatures.view_piecejointe", "candidatures.view_transfertcandidature",
            "stages.view_stage", "stages.view_affectationmaitrestage", "stages.view_periodeinterruption",
            "suivi.view_historique", "suivi.view_notification",
        }
        self._lancer()
        obtenues = {
            f"{app}.{code}"
            for app, code in Group.objects.get(name="Administrateur")
            .permissions.values_list("content_type__app_label", "codename")
        }
        self.assertEqual(obtenues, attendues)

    def test_relancer_init_donnees_retablit_la_lecture_seule(self):
        """Un droit ajouté à la main (admin Django, SQL…) est retiré au prochain init_donnees."""
        self._lancer()
        groupe = Group.objects.get(name="Administrateur")
        groupe.permissions.add(Permission.objects.get(codename="add_offre"))
        self._lancer()
        self.assertFalse(groupe.permissions.filter(codename="add_offre").exists())

    def test_idempotente_et_ne_modifie_pas_les_durees_existantes(self):
        TypeStage.objects.all().delete()
        self._lancer()
        TypeStage.objects.filter(libelle="Stage professionnel").update(duree_min_mois=2, duree_max_mois=4)
        self._lancer()
        self.assertEqual(TypeStage.objects.count(), 5)
        ts = TypeStage.objects.get(libelle="Stage professionnel")
        self.assertEqual((ts.duree_min_mois, ts.duree_max_mois), (2, 4))


# ─── Tests permissions TypeStage ──────────────────────────────────────────────

class PermissionsTypestageTests(TestCase):
    """Retirer add_typestage du rôle → vue 403 et bouton masqué dans la liste."""

    def setUp(self):
        self.groupe, _ = Group.objects.get_or_create(name="Administrateur")
        ct = ContentType.objects.get_for_model(TypeStage)
        for codename in ["view_typestage", "change_typestage", "delete_typestage"]:
            perm = Permission.objects.get(content_type=ct, codename=codename)
            self.groupe.permissions.add(perm)
        self.admin = Utilisateur.objects.create_user(
            email="admin_noadd@serein.bf", password="pass1234!",
            first_name="A", last_name="B",
        )
        self.admin.groups.add(self.groupe)

    def test_vue_creer_typestage_403_sans_permission_add(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("referentiels:typestage_creer"))
        self.assertEqual(resp.status_code, 403)

    def test_bouton_nouveau_absent_sans_permission_add(self):
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("referentiels:typestage_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, reverse("referentiels:typestage_creer"))


# ─── Lot B — TypeStage duree_min/max ─────────────────────────────────────────


class TypeStageDureeModelTests(TestCase):
    """TypeStage.clean() et contrainte max >= min."""

    def _admin(self):
        return _creer_utilisateur("admin@serein.bf", is_superuser=True)

    def test_duree_valide(self):
        from django.core.exceptions import ValidationError
        ts = TypeStage(libelle="X", duree_min_mois=2, duree_max_mois=4)
        ts.clean()  # ne doit pas lever

    def test_max_inferieur_min_leve_erreur(self):
        from django.core.exceptions import ValidationError
        ts = TypeStage(libelle="Y", duree_min_mois=4, duree_max_mois=2)
        with self.assertRaises(ValidationError):
            ts.clean()

    def test_min_egal_max_valide(self):
        from django.core.exceptions import ValidationError
        ts = TypeStage(libelle="Z", duree_min_mois=3, duree_max_mois=3)
        ts.clean()  # ne doit pas lever


class TypeStageFormDureeTests(TestCase):
    """TypeStageForm valide les bornes de durée."""

    def setUp(self):
        self.admin = _creer_utilisateur("admin@serein.bf", is_superuser=True)

    def _data(self, **kwargs):
        d = {"libelle": "Test Stage", "description": "", "remunere": False, "actif": True,
             "duree_min_mois": 1, "duree_max_mois": 6}
        d.update(kwargs)
        return d

    def test_formulaire_valide(self):
        from referentiels.forms import TypeStageForm
        form = TypeStageForm(self._data())
        self.assertTrue(form.is_valid(), msg=form.errors)

    def test_max_inferieur_min_invalide(self):
        from referentiels.forms import TypeStageForm
        form = TypeStageForm(self._data(duree_min_mois=5, duree_max_mois=2))
        self.assertFalse(form.is_valid())
        self.assertIn("duree_max_mois", form.errors)

    def test_creation_typestage_via_vue(self):
        self.client.force_login(self.admin)
        url = reverse("referentiels:typestage_creer")
        response = self.client.post(url, {
            "libelle": "Nouveau Type",
            "description": "",
            "remunere": False,
            "actif": True,
            "duree_min_mois": 2,
            "duree_max_mois": 4,
        })
        self.assertEqual(TypeStage.objects.filter(libelle="Nouveau Type").count(), 1)
        ts = TypeStage.objects.get(libelle="Nouveau Type")
        self.assertEqual(ts.duree_min_mois, 2)
        self.assertEqual(ts.duree_max_mois, 4)
