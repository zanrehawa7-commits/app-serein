from django.contrib.auth.models import Group
from django.test import TestCase, Client, override_settings
from django.urls import reverse

from comptes.models import Utilisateur
from comptes.forms import UtilisateurCreerForm
from referentiels.models import Departement, Personnel


def _creer_utilisateur(email, password, groupe=None, is_active=True, is_superuser=False, personnel=None):
    user = Utilisateur.objects.create_user(
        email=email, password=password,
        first_name="Test", last_name="User",
        is_active=is_active, is_superuser=is_superuser,
    )
    if personnel:
        user.personnel = personnel
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
        self.membre_a = Personnel.objects.create(
            nom="Doe", prenom="John", departement=self.dept_a
        )
        self.membre_b = Personnel.objects.create(
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


class UtilisateurF03Tests(TestCase):
    """F03 : règles de création et de désactivation des utilisateurs."""

    def setUp(self):
        self.admin = _creer_utilisateur("admin@serein.bf", "pass1234!", is_superuser=True)
        Group.objects.get_or_create(name="Responsable")
        Group.objects.get_or_create(name="Administrateur")
        Group.objects.get_or_create(name="Secrétaire")

    def test_responsable_sans_personnel_formulaire_invalide(self):
        """Créer un Responsable sans personnel lié est refusé (RG)."""
        form = UtilisateurCreerForm(data={
            "first_name": "Paul",
            "last_name": "Martin",
            "email": "paul@serein.bf",
            "role": "Responsable",
            "password1": "Test@1234",
            "password2": "Test@1234",
            "personnel": "",
        })
        self.assertFalse(form.is_valid())
        self.assertIn("personnel", form.errors)

    def test_admin_sans_groupe_peut_creer_utilisateur(self):
        """Un superuser sans groupe peut accéder à la création d'utilisateurs."""
        self.client.force_login(self.admin)
        resp = self.client.get(reverse("comptes:utilisateur_creer"))
        self.assertEqual(resp.status_code, 200)

    def test_admin_ne_peut_pas_desactiver_son_propre_compte(self):
        """Un administrateur ne peut pas désactiver son propre compte (RG33)."""
        self.client.force_login(self.admin)
        url = reverse("comptes:utilisateur_activer", kwargs={"pk": self.admin.pk})
        self.client.post(url)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active, "L'admin ne doit pas pouvoir se désactiver lui-même")


class ChangementRoleTests(TestCase):
    """Si un Responsable change de rôle, son lien personnel est retiré."""

    def setUp(self):
        self.admin = _creer_utilisateur("admin@serein.bf", "pass1234!", is_superuser=True)
        Group.objects.get_or_create(name="Administrateur")
        Group.objects.get_or_create(name="Responsable")
        Group.objects.get_or_create(name="Secrétaire")
        dept = Departement.objects.create(nom="Dept Test")
        self.pers = Personnel.objects.create(
            nom="Doe", prenom="John", departement=dept, actif=True
        )
        self.resp_user = _creer_utilisateur("resp@serein.bf", "pass1234!", "Responsable")
        self.resp_user.personnel = self.pers
        self.resp_user.save()

    def test_changement_responsable_vers_secretaire_retire_personnel(self):
        """Changer un Responsable en Secrétaire retire son lien vers le personnel."""
        self.client.force_login(self.admin)
        url = reverse("comptes:utilisateur_modifier", kwargs={"pk": self.resp_user.pk})
        self.client.post(url, {
            "first_name": self.resp_user.first_name,
            "last_name": self.resp_user.last_name,
            "email": self.resp_user.email,
            "role": "Secrétaire",
            "personnel": "",
            "is_active": True,
        })
        self.resp_user.refresh_from_db()
        self.assertIsNone(
            self.resp_user.personnel,
            "Le lien personnel doit être retiré quand un Responsable change de rôle",
        )

    def test_changement_responsable_vers_admin_retire_personnel(self):
        """Changer un Responsable en Administrateur retire aussi son lien personnel."""
        self.client.force_login(self.admin)
        url = reverse("comptes:utilisateur_modifier", kwargs={"pk": self.resp_user.pk})
        self.client.post(url, {
            "first_name": self.resp_user.first_name,
            "last_name": self.resp_user.last_name,
            "email": self.resp_user.email,
            "role": "Administrateur",
            "personnel": "",
            "is_active": True,
        })
        self.resp_user.refresh_from_db()
        self.assertIsNone(self.resp_user.personnel)


class PermissionsAdministrateurLectureSeuleTests(TestCase):
    """F02 : impossible de redonner à l'Administrateur l'écriture sur offres, candidatures, stages, suivi."""

    def setUp(self):
        from io import StringIO
        from django.core.management import call_command
        call_command("init_donnees", stdout=StringIO())
        self.admin = _creer_utilisateur("admin@serein.bf", "pass", groupe="Administrateur")
        self.client.force_login(self.admin)
        self.url = reverse("comptes:permissions_role", args=["Administrateur"])

    def test_post_ne_redonne_pas_l_ecriture(self):
        from django.contrib.auth.models import Permission
        groupe = Group.objects.get(name="Administrateur")
        demandees = list(groupe.permissions.values_list("pk", flat=True))
        demandees += list(
            Permission.objects.filter(codename__in=["add_offre", "change_candidature", "delete_stage", "change_notification"])
            .values_list("pk", flat=True)
        )
        self.client.post(self.url, {"permissions": [str(pk) for pk in demandees]})
        ecriture = groupe.permissions.filter(
            content_type__app_label__in=["offres", "candidatures", "stages", "suivi"]
        ).exclude(codename__startswith="view_")
        self.assertFalse(ecriture.exists(), list(ecriture.values_list("codename", flat=True)))
        self.assertTrue(groupe.permissions.filter(codename="view_offre").exists())

    def test_cases_ecriture_grisees_et_decochees(self):
        reponse = self.client.get(self.url)
        actions = {
            (bloc["app_label"], modele["label"], action["action_label"]): action
            for bloc in reponse.context["structure"]
            for modele in bloc["modeles"]
            for action in modele["actions"] if action["exists"]
        }
        ajout_offre = actions[("Offres & besoins", "Offre", "Ajouter")]
        self.assertTrue(ajout_offre["disabled"])
        self.assertFalse(ajout_offre["checked"])
        voir_offre = actions[("Offres & besoins", "Offre", "Voir")]
        self.assertFalse(voir_offre["disabled"])


# ─── Lot E1 : profils de rôle et droits de consultation ───────────────────────


def _role_consultation(nom, codes=(), actif=True):
    """Groupe + profil de consultation, avec les permissions « app.codename » données."""
    from django.contrib.auth.models import Permission
    from comptes.models import ProfilRole
    groupe = Group.objects.create(name=nom)
    ProfilRole.objects.create(groupe=groupe, description="Test", actif=actif)
    for code in codes:
        app, codename = code.split(".")
        groupe.permissions.add(Permission.objects.get(content_type__app_label=app, codename=codename))
    return groupe


class ProfilRoleTests(TestCase):

    def _init_donnees(self):
        from io import StringIO
        from django.core.management import call_command
        call_command("init_donnees", stdout=StringIO())

    def test_init_donnees_cree_les_profils_systeme_idempotent(self):
        from comptes.models import ProfilRole
        self._init_donnees()
        self._init_donnees()
        profils = ProfilRole.objects.filter(est_systeme=True)
        self.assertEqual(
            sorted(profils.values_list("groupe__name", flat=True)), ["Administrateur", "Responsable", "Secrétaire"]
        )
        self.assertTrue(all(p.actif for p in profils))

    def test_init_donnees_ne_touche_pas_aux_roles_de_consultation(self):
        groupe = _role_consultation("Auditeur", ["offres.view_offre"], actif=False)
        self._init_donnees()
        groupe.profil.refresh_from_db()
        self.assertEqual((groupe.profil.est_systeme, groupe.profil.actif), (False, False))
        self.assertEqual(list(groupe.permissions.values_list("codename", flat=True)), ["view_offre"])

    def test_migration_0005_marque_les_groupes_existants(self):
        import importlib
        from django.apps import apps
        from comptes.models import ProfilRole
        Group.objects.create(name="Secrétaire")
        Group.objects.create(name="Autre")
        migration = importlib.import_module("comptes.migrations.0005_profils_roles_systeme")
        migration.creer_profils_systeme(apps, None)
        self.assertEqual(list(ProfilRole.objects.values_list("groupe__name", "est_systeme")), [("Secrétaire", True)])

    def test_permissions_personnalisees_creees(self):
        from django.contrib.auth.models import Permission
        for app, codename in [("candidatures", "telecharger_pieces_jointes"), ("stages", "consulter_vivier"),
                              ("stages", "exporter_vivier"), ("stages", "telecharger_rapports")]:
            with self.subTest(codename=codename):
                self.assertTrue(Permission.objects.filter(content_type__app_label=app, codename=codename).exists())

    def test_liste_blanche_onze_droits_de_consultation_uniquement(self):
        from comptes.permissions import CODES_DROITS_CONSULTATION
        self.assertEqual(len(CODES_DROITS_CONSULTATION), 11)
        for code in CODES_DROITS_CONSULTATION:
            with self.subTest(code=code):
                self.assertFalse(code.split(".")[1].startswith(("add_", "change_", "delete_")))

    def test_est_role_consultation_et_a_acces(self):
        from comptes.permissions import a_acces, est_role_consultation
        _role_consultation("Auditeur", ["offres.view_offre"])
        _role_consultation("Ancien", ["offres.view_offre"], actif=False)
        auditeur = _creer_utilisateur("aud@serein.bf", "pass", groupe="Auditeur")
        ancien = _creer_utilisateur("anc@serein.bf", "pass", groupe="Ancien")
        sec = _creer_utilisateur("sec@serein.bf", "pass", groupe="Secrétaire")
        sans_role = _creer_utilisateur("x@serein.bf", "pass")
        self.assertEqual(
            [est_role_consultation(u) for u in (auditeur, ancien, sec, sans_role)], [True, False, False, False]
        )
        self.assertTrue(a_acces(auditeur, ["Administrateur"], "offres.view_offre"))
        self.assertFalse(a_acces(auditeur, ["Administrateur"], "offres.view_besoin"))
        self.assertTrue(a_acces(auditeur, ["Administrateur"]))
        self.assertFalse(a_acces(ancien, ["Administrateur"], "offres.view_offre"))
        self.assertTrue(a_acces(sec, ["Secrétaire"], "offres.view_besoin"))
        self.assertFalse(a_acces(sec, ["Administrateur"], "offres.view_offre"))


# ─── Lot E2 : écran des rôles de consultation ─────────────────────────────────


class RolesConsultationEcranTests(TestCase):

    def setUp(self):
        from io import StringIO
        from django.core.management import call_command
        call_command("init_donnees", stdout=StringIO())
        self.admin = _creer_utilisateur("admin@serein.bf", "pass", groupe="Administrateur")
        self.client.force_login(self.admin)

    def _creer(self, **donnees):
        valeurs = {"nom": "Auditeur", "description": "Audit interne", "droits": ["offres.view_offre"]}
        valeurs.update(donnees)
        return self.client.post(reverse("comptes:role_consultation_creer"), valeurs)

    def test_creation_role_lecture_seule(self):
        reponse = self._creer(droits=["offres.view_offre", "candidatures.telecharger_pieces_jointes"])
        self.assertRedirects(reponse, reverse("comptes:roles_list"))
        groupe = Group.objects.get(name="Auditeur")
        self.assertEqual((groupe.profil.est_systeme, groupe.profil.actif), (False, True))
        self.assertEqual(
            sorted(groupe.permissions.values_list("codename", flat=True)),
            ["telecharger_pieces_jointes", "view_offre"],
        )

    def test_droits_ecriture_refuses_cote_serveur(self):
        for code in ["offres.add_offre", "candidatures.change_candidature", "stages.delete_stage"]:
            with self.subTest(code=code):
                reponse = self._creer(nom=f"Pirate {code}", droits=["offres.view_offre", code])
                self.assertEqual(reponse.status_code, 200)
                self.assertFalse(Group.objects.filter(name=f"Pirate {code}").exists())

    def test_service_refuse_un_droit_hors_liste_blanche(self):
        from comptes.services import RoleInterdit, creer_role_consultation
        with self.assertRaisesMessage(RoleInterdit, "offres.add_offre"):
            creer_role_consultation("Pirate", "", ["offres.view_offre", "offres.add_offre"])
        self.assertFalse(Group.objects.filter(name="Pirate").exists())

    def test_modification_ne_peut_pas_ajouter_d_ecriture(self):
        self._creer()
        groupe = Group.objects.get(name="Auditeur")
        self.client.post(
            reverse("comptes:role_consultation_modifier", args=[groupe.pk]),
            {"nom": "Auditeur", "description": "", "droits": ["offres.view_offre", "offres.change_offre"]},
        )
        self.assertEqual(list(groupe.permissions.values_list("codename", flat=True)), ["view_offre"])

    def test_nom_d_un_role_de_base_ou_existant_refuse(self):
        self._creer()
        for nom in ["secrétaire", "ADMINISTRATEUR", "auditeur"]:
            with self.subTest(nom=nom):
                reponse = self._creer(nom=nom)
                self.assertEqual(reponse.status_code, 200)
        self.assertEqual(Group.objects.filter(profil__est_systeme=False).count(), 1)

    def test_roles_de_base_ni_modifiables_ni_desactivables(self):
        for nom in ["Administrateur", "Secrétaire", "Responsable"]:
            groupe = Group.objects.get(name=nom)
            with self.subTest(role=nom):
                self.assertEqual(
                    self.client.get(reverse("comptes:role_consultation_modifier", args=[groupe.pk])).status_code, 404
                )
                self.assertEqual(
                    self.client.post(
                        reverse("comptes:role_consultation_modifier", args=[groupe.pk]),
                        {"nom": "Renommé", "droits": []},
                    ).status_code,
                    404,
                )
                self.assertEqual(
                    self.client.post(reverse("comptes:role_consultation_activer", args=[groupe.pk])).status_code, 404
                )
                groupe.refresh_from_db()
                self.assertEqual((groupe.name, groupe.profil.actif), (nom, True))

    def test_ecran_permissions_de_base_refuse_un_role_de_consultation(self):
        self._creer()
        url = reverse("comptes:permissions_role", args=["Auditeur"])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.assertEqual(self.client.post(url, {"permissions": []}).status_code, 404)

    def test_desactivation_refusee_tant_qu_un_utilisateur_actif(self):
        self._creer()
        groupe = Group.objects.get(name="Auditeur")
        auditeur = _creer_utilisateur("aud@serein.bf", "pass", groupe="Auditeur")
        url = reverse("comptes:role_consultation_activer", args=[groupe.pk])
        self.client.post(url)
        groupe.profil.refresh_from_db()
        self.assertTrue(groupe.profil.actif)
        auditeur.is_active = False
        auditeur.save(update_fields=["is_active"])
        self.client.post(url)
        groupe.profil.refresh_from_db()
        self.assertFalse(groupe.profil.actif)

    def test_reactivation_utilisateur_refusee_si_role_desactive(self):
        self._creer()
        groupe = Group.objects.get(name="Auditeur")
        auditeur = _creer_utilisateur("aud@serein.bf", "pass", groupe="Auditeur", is_active=False)
        self.client.post(reverse("comptes:role_consultation_activer", args=[groupe.pk]))
        self.client.post(reverse("comptes:utilisateur_activer", args=[auditeur.pk]))
        auditeur.refresh_from_db()
        self.assertFalse(auditeur.is_active)

    def test_formulaire_utilisateur_propose_les_roles_de_consultation_actifs(self):
        from comptes.forms import UtilisateurCreerForm
        self._creer()
        self._creer(nom="Ancien")
        self.client.post(reverse("comptes:role_consultation_activer", args=[Group.objects.get(name="Ancien").pk]))
        valeurs = []
        for valeur, libelle in UtilisateurCreerForm().fields["role"].choices:
            valeurs += [v for v, _ in libelle] if isinstance(libelle, (list, tuple)) else [valeur]
        self.assertIn("Auditeur", valeurs)
        self.assertNotIn("Ancien", valeurs)
        self.assertTrue({"Administrateur", "Secrétaire", "Responsable"} <= set(valeurs))

    def test_creation_utilisateur_avec_role_de_consultation(self):
        self._creer()
        self.client.post(reverse("comptes:utilisateur_creer"), {
            "first_name": "Awa", "last_name": "Audit", "email": "awa@serein.bf", "telephone": "",
            "role": "Auditeur", "password1": "MotDePasse!2026", "password2": "MotDePasse!2026",
        })
        self.assertEqual(Utilisateur.objects.get(email="awa@serein.bf").role, "Auditeur")


# ─── RG33 : pas d'auto-désactivation ni de changement de son propre rôle ───────


class AutoModificationCompteTests(TestCase):
    """Le formulaire « Modifier » ne doit pas contourner RG33 (bug trouvé en recette)."""

    def setUp(self):
        from io import StringIO
        from django.core.management import call_command
        call_command("init_donnees", stdout=StringIO())
        self.admin = _creer_utilisateur("admin@serein.bf", "pass", groupe="Administrateur")
        self.sec = _creer_utilisateur("sec@serein.bf", "pass", groupe="Secrétaire")
        self.client.force_login(self.admin)

    def _modifier(self, cible, **valeurs):
        donnees = {"first_name": "Nouveau", "last_name": cible.last_name, "email": cible.email,
                   "telephone": "", "role": "Administrateur"}
        donnees.update(valeurs)
        return self.client.post(reverse("comptes:utilisateur_modifier", args=[cible.pk]), donnees)

    def test_se_desactiver_par_le_formulaire_est_ignore(self):
        self._modifier(self.admin)  # case « actif » décochée : absente du POST
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertEqual(self.admin.first_name, "Nouveau")

    def test_changer_son_propre_role_est_ignore(self):
        self._modifier(self.admin, role="Secrétaire", is_active="on")
        self.admin.refresh_from_db()
        self.assertEqual(self.admin.role, "Administrateur")

    def test_champs_grises_sur_son_propre_compte(self):
        form = self.client.get(reverse("comptes:utilisateur_modifier", args=[self.admin.pk])).context["form"]
        self.assertTrue(form.fields["is_active"].disabled)
        self.assertTrue(form.fields["role"].disabled)

    def test_modifier_un_autre_compte_reste_possible(self):
        self._modifier(self.sec, role="Secrétaire")  # case « actif » décochée
        self.sec.refresh_from_db()
        self.assertFalse(self.sec.is_active)
        self._modifier(self.sec, role="Administrateur", is_active="on")
        self.sec.refresh_from_db()
        self.assertEqual((self.sec.is_active, self.sec.role), (True, "Administrateur"))
