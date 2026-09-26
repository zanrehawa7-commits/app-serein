from unittest.mock import patch

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models import ProtectedError
from django.test import Client, TestCase
from django.urls import reverse

from comptes.models import Utilisateur
from referentiels.models import Departement, Etablissement, Membre, TypeStage


def _creer_utilisateur(email, password="pass1234!", groupe=None, is_superuser=False):
    user = Utilisateur.objects.create_user(
        email=email, password=password,
        first_name="Test", last_name="User",
        is_superuser=is_superuser,
    )
    if groupe:
        grp, _ = Group.objects.get_or_create(name=groupe)
        user.groups.add(grp)
    return user


class AccesRolesTests(TestCase):
    """Secrétaire et Responsable reçoivent 403 sur toutes les pages du module référentiels."""

    def setUp(self):
        self.secretaire = _creer_utilisateur("sec@serein.bf", groupe="Secrétaire")
        self.responsable = _creer_utilisateur("resp@serein.bf", groupe="Responsable")
        self.dept = Departement.objects.create(nom="Dept Test")
        self.ts = TypeStage.objects.create(libelle="Stage test")
        self.etab = Etablissement.objects.create(nom="Ecole A", ville="Ouaga")

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


class TypeStageSuppressionTests(TestCase):
    """Suppression TypeStage : désactivation si ProtectedError."""

    def setUp(self):
        self.admin = _creer_utilisateur("admin@serein.bf", is_superuser=True)
        self.ts = TypeStage.objects.create(libelle="Stage utilisé", actif=True)

    def test_suppression_non_utilise(self):
        """Un TypeStage non référencé est supprimé définitivement."""
        self.client.force_login(self.admin)
        url = reverse("referentiels:typestage_supprimer", kwargs={"pk": self.ts.pk})
        self.client.post(url)
        self.assertFalse(TypeStage.objects.filter(pk=self.ts.pk).exists())

    def test_suppression_protegee_desactive_au_lieu_de_supprimer(self):
        """Si suppression impossible (ProtectedError), le TypeStage est désactivé."""
        self.client.force_login(self.admin)
        url = reverse("referentiels:typestage_supprimer", kwargs={"pk": self.ts.pk})
        with patch.object(TypeStage, "delete", side_effect=ProtectedError("en utilisation", set())):
            self.client.post(url)
        self.ts.refresh_from_db()
        self.assertTrue(TypeStage.objects.filter(pk=self.ts.pk).exists(), "Le TypeStage doit exister")
        self.assertFalse(self.ts.actif, "Le TypeStage doit être marqué inactif")


class MembreDesactiverTests(TestCase):
    """Désactivation membre : refusée si responsable actuel du département."""

    def setUp(self):
        self.admin = _creer_utilisateur("admin@serein.bf", is_superuser=True)
        self.dept = Departement.objects.create(nom="Dept Test")
        self.membre = Membre.objects.create(
            nom="Doe", prenom="John", departement=self.dept, actif=True
        )

    def test_desactiver_membre_non_responsable_ok(self):
        """Un membre ordinaire peut être désactivé."""
        self.client.force_login(self.admin)
        url = reverse("referentiels:membre_desactiver", kwargs={"pk": self.membre.pk})
        self.client.post(url)
        self.membre.refresh_from_db()
        self.assertFalse(self.membre.actif)

    def test_desactiver_membre_responsable_refuse(self):
        """Impossible de désactiver un membre qui est responsable de son département."""
        self.dept.responsable = self.membre
        self.dept.save()
        self.client.force_login(self.admin)
        url = reverse("referentiels:membre_desactiver", kwargs={"pk": self.membre.pk})
        self.client.post(url)
        self.membre.refresh_from_db()
        self.assertTrue(self.membre.actif, "Le membre responsable ne doit PAS être désactivé")

    def test_reactiver_membre_desactive(self):
        """Un membre désactivé peut être réactivé."""
        self.membre.actif = False
        self.membre.save()
        self.client.force_login(self.admin)
        url = reverse("referentiels:membre_desactiver", kwargs={"pk": self.membre.pk})
        self.client.post(url)
        self.membre.refresh_from_db()
        self.assertTrue(self.membre.actif)


class DepartementResponsableTests(TestCase):
    """Le formulaire rejette un responsable qui n'appartient pas au département."""

    def setUp(self):
        self.admin = _creer_utilisateur("admin@serein.bf", is_superuser=True)
        self.dept_a = Departement.objects.create(nom="Dept A")
        self.dept_b = Departement.objects.create(nom="Dept B")
        self.membre_b = Membre.objects.create(
            nom="Smith", prenom="Jane", departement=self.dept_b, actif=True
        )

    def test_responsable_hors_departement_refuse(self):
        """
        Poster un responsable d'un autre département doit invalider le formulaire :
        le membre n'est pas dans le queryset restreint au département A.
        """
        self.client.force_login(self.admin)
        url = reverse("referentiels:departement_modifier", kwargs={"pk": self.dept_a.pk})
        resp = self.client.post(url, {
            "nom": self.dept_a.nom,
            "description": "",
            "responsable": self.membre_b.pk,
            "actif": True,
        })
        # Formulaire invalide → réaffichage (200) sans modification
        self.assertEqual(resp.status_code, 200)
        self.dept_a.refresh_from_db()
        self.assertIsNone(
            self.dept_a.responsable,
            "Un responsable d'un autre département ne doit pas être accepté",
        )

    def test_responsable_meme_departement_accepte(self):
        """Un membre du département A peut être désigné responsable."""
        membre_a = Membre.objects.create(
            nom="Martin", prenom="Paul", departement=self.dept_a, actif=True
        )
        self.client.force_login(self.admin)
        url = reverse("referentiels:departement_modifier", kwargs={"pk": self.dept_a.pk})
        resp = self.client.post(url, {
            "nom": self.dept_a.nom,
            "description": "",
            "responsable": membre_a.pk,
            "actif": True,
        })
        self.dept_a.refresh_from_db()
        self.assertEqual(self.dept_a.responsable, membre_a)


class PermissionsTypestageTests(TestCase):
    """Retirer add_typestage du rôle → vue 403 et bouton masqué dans la liste."""

    def setUp(self):
        self.groupe, _ = Group.objects.get_or_create(name="Administrateur")
        ct = ContentType.objects.get_for_model(TypeStage)
        # Attribue view, change, delete — pas add
        for codename in ["view_typestage", "change_typestage", "delete_typestage"]:
            perm = Permission.objects.get(content_type=ct, codename=codename)
            self.groupe.permissions.add(perm)
        self.admin = Utilisateur.objects.create_user(
            email="admin_noadd@serein.bf", password="pass1234!",
            first_name="A", last_name="B",
        )
        self.admin.groups.add(self.groupe)

    def test_vue_creer_typestage_403_sans_permission_add(self):
        """Sans add_typestage, la vue de création retourne 403."""
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("referentiels:typestage_creer"))
        self.assertEqual(resp.status_code, 403)

    def test_bouton_nouveau_absent_sans_permission_add(self):
        """Sans add_typestage, le bouton 'Nouveau' n'apparaît pas dans la liste."""
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("referentiels:typestage_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, reverse("referentiels:typestage_creer"))
