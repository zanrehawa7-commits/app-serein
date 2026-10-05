from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from comptes.models import Utilisateur
from suivi.models import Historique, Notification
from suivi.services import enregistrer_historique, notifier

from referentiels.models import Departement, TypeStage
from offres.models import Besoin, StatutBesoin


def _user(email, groupe=None):
    u = Utilisateur.objects.create_user(
        email=email, password="pass1234!",
        first_name="Test", last_name="User",
    )
    if groupe:
        grp, _ = Group.objects.get_or_create(name=groupe)
        u.groups.add(grp)
    return u


class EnregistrerHistoriqueTests(TestCase):
    def setUp(self):
        self.dept = Departement.objects.create(nom="Dept Test")
        self.ts = TypeStage.objects.create(libelle="Stage test", duree_min_mois=1, duree_max_mois=6)
        self.user = _user("test@serein.bf")
        self.besoin = Besoin.objects.create(
            departement=self.dept,
            type_stage=self.ts,
            date_debut="2027-01-01",
            date_fin="2027-06-30",
            profil_recherche="Profil",
            nombre_places=2,
            statut=StatutBesoin.ENVOYE,
        )

    def test_historique_cree(self):
        """enregistrer_historique crée bien un enregistrement lié à l'objet."""
        h = enregistrer_historique(
            self.besoin, self.user,
            ancien_statut="", nouveau_statut=StatutBesoin.ENVOYE,
            commentaire="Créé.",
        )
        self.assertEqual(h.object_id, self.besoin.pk)
        self.assertEqual(h.utilisateur, self.user)
        self.assertEqual(h.nouveau_statut, StatutBesoin.ENVOYE)

    def test_historique_content_type_correct(self):
        from django.contrib.contenttypes.models import ContentType
        h = enregistrer_historique(self.besoin, self.user, nouveau_statut="X")
        ct = ContentType.objects.get_for_model(Besoin)
        self.assertEqual(h.content_type, ct)


class NotifierTests(TestCase):
    def setUp(self):
        self.user1 = _user("u1@serein.bf")
        self.user2 = _user("u2@serein.bf")

    def test_notifier_cree_pour_chaque_destinataire(self):
        notifier([self.user1, self.user2], "Test notification", lien="/test/")
        self.assertEqual(Notification.objects.filter(destinataire=self.user1).count(), 1)
        self.assertEqual(Notification.objects.filter(destinataire=self.user2).count(), 1)

    def test_notifier_liste_vide(self):
        """notifier avec une liste vide ne doit pas lever d'exception."""
        notifier([], "Message")
        self.assertEqual(Notification.objects.count(), 0)

    def test_notifier_contenu(self):
        notifier([self.user1], "Message test", lien="/lien/")
        notif = Notification.objects.get(destinataire=self.user1)
        self.assertEqual(notif.message, "Message test")
        self.assertEqual(notif.lien, "/lien/")
        self.assertFalse(notif.lue)


class NotificationVuesTests(TestCase):
    def setUp(self):
        self.user = _user("user@serein.bf", groupe="Secrétaire")
        self.notif = Notification.objects.create(
            destinataire=self.user,
            message="Nouvelle notification test",
            lien="/besoins/1/",
        )

    def test_liste_notifications(self):
        self.client.force_login(self.user)
        resp = self.client.get(reverse("suivi:notification_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Nouvelle notification test")

    def test_marquer_comme_lue(self):
        self.client.force_login(self.user)
        self.client.get(reverse("suivi:notification_lire", kwargs={"pk": self.notif.pk}))
        self.notif.refresh_from_db()
        self.assertTrue(self.notif.lue)

    def test_tout_lire(self):
        Notification.objects.create(destinataire=self.user, message="Notif 2")
        self.client.force_login(self.user)
        self.client.post(reverse("suivi:notification_tout_lire"))
        self.assertFalse(self.user.notifications.filter(lue=False).exists())

    def test_notification_autre_utilisateur_404(self):
        """Un utilisateur ne peut pas lire les notifications d'un autre."""
        autre = _user("autre@serein.bf", groupe="Secrétaire")
        self.client.force_login(autre)
        resp = self.client.get(reverse("suivi:notification_lire", kwargs={"pk": self.notif.pk}))
        self.assertEqual(resp.status_code, 404)

    def test_liste_non_connecte_redirige(self):
        resp = self.client.get(reverse("suivi:notification_list"))
        self.assertIn(resp.status_code, [302])
