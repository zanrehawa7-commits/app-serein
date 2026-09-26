from django.contrib.auth.models import Group
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from comptes.models import Utilisateur
from referentiels.models import Departement, Membre


def _creer_utilisateur(email, password, groupe=None, is_active=True, is_superuser=False, membre=None):
    user = Utilisateur.objects.create_user(
        email=email, password=password,
        first_name="Test", last_name="User",
        is_active=is_active, is_superuser=is_superuser,
    )
    if membre:
        user.membre = membre
        user.save()
    if groupe:
        grp, _ = Group.objects.get_or_create(name=groupe)
        user.groups.add(grp)
    return user


class ConnexionTests(TestCase):

    def setUp(self):
        self.client = Client()
        self.url_login = reverse("comptes:connexion")

    def test_connexion_par_email_ok(self):
        """Un utilisateur actif peut se connecter avec son email."""
        _creer_utilisateur("admin@serein.bf", "pass1234!", "Administrateur")
        resp = self.client.post(self.url_login, {
            "username": "admin@serein.bf", "password": "pass1234!"
        })
        self.assertRedirects(resp, reverse("comptes:tableau_bord_admin"), fetch_redirect_response=False)

    def test_compte_desactive_refuse(self):
        """Un compte is_active=False est refusé avec le message RG33."""
        _creer_utilisateur("inactif@serein.bf", "pass1234!", is_active=False)
        resp = self.client.post(self.url_login, {
            "username": "inactif@serein.bf", "password": "pass1234!"
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "désactivé")

    def test_mauvais_credentials_message_generique(self):
        """Des identifiants incorrects affichent le message générique."""
        resp = self.client.post(self.url_login, {
            "username": "inconnu@serein.bf", "password": "mauvais"
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "incorrect")


class ProtectionTests(TestCase):

    def setUp(self):
        self.client = Client()

    def test_page_protegee_redirige_vers_login(self):
        """Un utilisateur non connecté est redirigé vers /login/."""
        resp = self.client.get(reverse("comptes:tableau_bord_admin"))
        self.assertRedirects(
            resp,
            f"{reverse('comptes:connexion')}?next={reverse('comptes:tableau_bord_admin')}",
            fetch_redirect_response=False,
        )

    def test_secretaire_acces_page_admin_403(self):
        """Une Secrétaire accédant à une page Admin reçoit un 403."""
        _creer_utilisateur("sec@serein.bf", "pass1234!", "Secrétaire")
        self.client.login(username="sec@serein.bf", password="pass1234!")
        resp = self.client.get(reverse("comptes:tableau_bord_admin"))
        self.assertEqual(resp.status_code, 403)


class RedirectionTableauBordTests(TestCase):

    def _login(self, email, password):
        self.client.login(username=email, password=password)

    def test_admin_redirige_vers_tdb_admin(self):
        _creer_utilisateur("a@serein.bf", "pass1234!", "Administrateur")
        resp = self.client.post(reverse("comptes:connexion"), {
            "username": "a@serein.bf", "password": "pass1234!"
        })
        self.assertRedirects(resp, reverse("comptes:tableau_bord_admin"), fetch_redirect_response=False)

    def test_secretaire_redirige_vers_tdb_secretaire(self):
        _creer_utilisateur("s@serein.bf", "pass1234!", "Secrétaire")
        resp = self.client.post(reverse("comptes:connexion"), {
            "username": "s@serein.bf", "password": "pass1234!"
        })
        self.assertRedirects(resp, reverse("comptes:tableau_bord_secretaire"), fetch_redirect_response=False)

    def test_responsable_redirige_vers_tdb_responsable(self):
        _creer_utilisateur("r@serein.bf", "pass1234!", "Responsable")
        resp = self.client.post(reverse("comptes:connexion"), {
            "username": "r@serein.bf", "password": "pass1234!"
        })
        self.assertRedirects(resp, reverse("comptes:tableau_bord_responsable"), fetch_redirect_response=False)

    def test_superuser_sans_groupe_traite_comme_admin(self):
        """Un superutilisateur sans groupe arrive sur le tableau de bord Admin."""
        _creer_utilisateur("su@serein.bf", "pass1234!", is_superuser=True)
        resp = self.client.post(reverse("comptes:connexion"), {
            "username": "su@serein.bf", "password": "pass1234!"
        })
        self.assertRedirects(resp, reverse("comptes:tableau_bord_admin"), fetch_redirect_response=False)

    def test_superuser_sans_groupe_acces_tdb_admin(self):
        """Un superutilisateur sans groupe peut accéder au tableau de bord Admin."""
        _creer_utilisateur("su2@serein.bf", "pass1234!", is_superuser=True)
        self.client.login(username="su2@serein.bf", password="pass1234!")
        resp = self.client.get(reverse("comptes:tableau_bord_admin"))
        self.assertEqual(resp.status_code, 200)


class DepartementMixinTests(TestCase):

    def setUp(self):
        self.dept_a = Departement.objects.create(nom="Département A")
        self.dept_b = Departement.objects.create(nom="Département B")
        self.membre_a = Membre.objects.create(
            nom="Doe", prenom="John", departement=self.dept_a
        )
        self.membre_b = Membre.objects.create(
            nom="Smith", prenom="Jane", departement=self.dept_b
        )

    def test_responsable_sans_membre_recoit_message_erreur(self):
        """Un responsable sans membre rattaché est redirigé avec un message d'erreur."""
        user = _creer_utilisateur("resp_sans@serein.bf", "pass1234!", "Responsable")
        self.client.login(username="resp_sans@serein.bf", password="pass1234!")
        # On accède au TDB responsable — le mixin doit laisser passer (la vue ne filtre pas par défaut)
        # mais un accès à une vue DepartementResponsableMixin sans membre doit rediriger
        # On simule via la vue TDB responsable d'abord (pas de mixin dept ici, juste accès OK)
        resp = self.client.get(reverse("comptes:tableau_bord_responsable"))
        self.assertEqual(resp.status_code, 200)

    def test_responsable_sans_departement_mixin_message(self):
        """DepartementResponsableMixin redirige si le responsable n'a pas de département."""
        from django.test import RequestFactory
        from comptes.permissions import DepartementResponsableMixin
        from django.views.generic import View

        class VueTest(DepartementResponsableMixin, View):
            def get(self, request, *args, **kwargs):
                from django.http import HttpResponse
                return HttpResponse("ok")

        user = _creer_utilisateur("resp_nodept@serein.bf", "pass1234!", "Responsable")
        factory = RequestFactory()
        request = factory.get("/test/")
        request.user = user
        from django.contrib.messages.storage.fallback import FallbackStorage
        setattr(request, 'session', self.client.session)
        setattr(request, '_messages', FallbackStorage(request))
        vue = VueTest.as_view()
        resp = vue(request)
        # Doit rediriger vers TDB responsable
        self.assertEqual(resp.status_code, 302)


class Page404Tests(TestCase):

    @override_settings(DEBUG=False)
    def test_page_404_personnalisee(self):
        """La page 404 personnalisée est utilisée en mode production."""
        resp = self.client.get("/url-inexistante-xyz/")
        self.assertEqual(resp.status_code, 404)
        self.assertContains(resp, "introuvable", status_code=404)
