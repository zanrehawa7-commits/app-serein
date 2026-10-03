"""
Étape 10 — chaque page de l'application, ouverte avec chaque rôle.

Vérifie pour toutes les routes nommées (hors admin Django et API) :
  - aucune exception (erreur 500) ;
  - le code attendu par rôle : page servie pour les rôles autorisés, 403 sinon,
    redirection vers la connexion pour un visiteur anonyme ;
  - le cloisonnement par département du Responsable.

Toute nouvelle route doit être ajoutée à MATRICE (test_toutes_les_routes_sont_couvertes).
"""

import datetime
from io import StringIO

from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase
from django.urls import URLResolver, get_resolver, reverse
from django.utils import timezone

from candidatures.models import (
    Candidat,
    Candidature,
    PieceJointe,
    StatutCandidature,
    TransfertCandidature,
    TypeDemande,
    TypePiece,
)
from comptes.models import Utilisateur
from offres.models import Besoin, Offre, Publication, StatutBesoin, StatutOffre
from referentiels.models import CanalPublication, Departement, Etablissement, Personnel, TypeStage
from stages.models import AffectationMaitreStage, Stage, StatutStage
from suivi.models import Notification
from suivi.services import enregistrer_historique

ADMIN = "Administrateur"
SEC = "Secrétaire"
RESP = "Responsable"
TOUS = (ADMIN, SEC, RESP)

# Route → (rôles autorisés, code attendu pour un rôle autorisé, paramètres d'URL).
# Les paramètres désignent un attribut du jeu de données (voir setUpTestData) ;
# "@notif" = la notification propre à l'utilisateur connecté.
# 405 : action POST uniquement — le GET passe le contrôle de rôle puis est refusé.
# 302 sur une action : le GET redirige sans rien modifier (test_get_ne_modifie_aucune_donnee),
# sauf notification_lire qui marque la notification comme lue (lien cliqué dans le menu).
MATRICE = {
    # ── comptes ──────────────────────────────────────────────────────────────
    "comptes:connexion": (TOUS, 200, {}),
    "comptes:deconnexion": (TOUS, 405, {}),
    "comptes:password_change": (TOUS, 200, {}),
    "comptes:password_change_done": (TOUS, 200, {}),
    "comptes:tableau_de_bord": (TOUS, 302, {}),
    "comptes:tableau_bord_admin": ((ADMIN,), 200, {}),
    "comptes:tableau_bord_secretaire": ((SEC,), 200, {}),
    "comptes:tableau_bord_responsable": ((RESP,), 200, {}),
    "comptes:en_developpement": (TOUS, 200, {}),
    "comptes:utilisateur_list": ((ADMIN,), 200, {}),
    "comptes:utilisateur_creer": ((ADMIN,), 200, {}),
    "comptes:utilisateur_modifier": ((ADMIN,), 200, {"pk": "u_sec"}),
    "comptes:utilisateur_activer": ((ADMIN,), 302, {"pk": "u_sec"}),
    "comptes:utilisateur_reinit_mdp": ((ADMIN,), 200, {"pk": "u_sec"}),
    "comptes:roles_list": ((ADMIN,), 200, {}),
    "comptes:permissions_role": ((ADMIN,), 200, {"role_nom": "=Secrétaire"}),
    # ── referentiels ─────────────────────────────────────────────────────────
    "referentiels:departement_list": ((ADMIN,), 200, {}),
    "referentiels:departement_creer": ((ADMIN,), 200, {}),
    "referentiels:departement_detail": ((ADMIN,), 200, {"pk": "dept_a"}),
    "referentiels:departement_modifier": ((ADMIN,), 200, {"pk": "dept_a"}),
    "referentiels:departement_supprimer": ((ADMIN,), 302, {"pk": "dept_a"}),
    "referentiels:personnel_list": ((ADMIN,), 200, {}),
    "referentiels:personnel_creer": ((ADMIN,), 200, {}),
    "referentiels:personnel_detail": ((ADMIN,), 200, {"pk": "resp_a"}),
    "referentiels:personnel_modifier": ((ADMIN,), 200, {"pk": "resp_a"}),
    "referentiels:personnel_desactiver": ((ADMIN,), 302, {"pk": "maitre_a"}),
    "referentiels:etablissement_list": ((ADMIN,), 200, {}),
    "referentiels:etablissement_creer": ((ADMIN,), 200, {}),
    "referentiels:etablissement_modifier": ((ADMIN,), 200, {"pk": "etab"}),
    "referentiels:etablissement_supprimer": ((ADMIN,), 302, {"pk": "etab"}),
    "referentiels:etablissement_partenaire": ((ADMIN,), 302, {"pk": "etab"}),
    "referentiels:typestage_list": ((ADMIN,), 200, {}),
    "referentiels:typestage_creer": ((ADMIN,), 200, {}),
    "referentiels:typestage_modifier": ((ADMIN,), 200, {"pk": "type_stage"}),
    "referentiels:typestage_supprimer": ((ADMIN,), 302, {"pk": "type_stage"}),
    "referentiels:canalpublication_list": ((ADMIN,), 200, {}),
    "referentiels:canalpublication_creer": ((ADMIN,), 200, {}),
    "referentiels:canalpublication_modifier": ((ADMIN,), 200, {"pk": "canal"}),
    "referentiels:canalpublication_supprimer": ((ADMIN,), 302, {"pk": "canal"}),
    # ── offres ───────────────────────────────────────────────────────────────
    "offres:besoin_list": (TOUS, 200, {}),
    "offres:besoin_creer": ((RESP,), 200, {}),
    "offres:besoin_detail": (TOUS, 200, {"pk": "besoin_a"}),
    "offres:besoin_modifier": ((RESP,), 200, {"pk": "besoin_libre"}),
    "offres:besoin_annuler": ((RESP,), 302, {"pk": "besoin_libre"}),
    "offres:offre_list": (TOUS, 200, {}),
    "offres:offre_creer": ((SEC,), 200, {}),
    "offres:offre_creer_depuis_besoin": ((SEC,), 200, {"besoin_pk": "besoin_libre"}),
    "offres:offre_detail": (TOUS, 200, {"pk": "offre_a"}),
    "offres:offre_modifier": ((SEC,), 200, {"pk": "offre_a"}),
    "offres:offre_ouvrir": ((SEC,), 302, {"pk": "offre_a"}),
    "offres:offre_suspendre": ((SEC,), 302, {"pk": "offre_a"}),
    "offres:offre_rouvrir": ((SEC,), 302, {"pk": "offre_a"}),
    "offres:offre_fermer": ((SEC,), 302, {"pk": "offre_a"}),
    "offres:offre_supprimer": ((SEC,), 302, {"pk": "offre_a"}),
    "offres:publication_creer": ((SEC,), 302, {"offre_pk": "offre_a"}),
    "offres:publication_modifier": ((SEC,), 200, {"pk": "publication"}),
    "offres:publication_supprimer": ((SEC,), 302, {"pk": "publication"}),
    "offres:parametre_offre": ((ADMIN,), 200, {}),
    # ── suivi ────────────────────────────────────────────────────────────────
    "suivi:notification_list": (TOUS, 200, {}),
    "suivi:notification_tout_lire": (TOUS, 302, {}),
    "suivi:notification_lire": (TOUS, 302, {"pk": "@notif"}),
    # ── candidatures ─────────────────────────────────────────────────────────
    "candidatures:candidat_recherche": ((SEC,), 200, {}),
    "candidatures:candidat_creer": ((SEC,), 200, {}),
    "candidatures:candidat_detail": (TOUS, 200, {"pk": "candidat_recue"}),
    "candidatures:candidat_modifier": ((SEC,), 200, {"pk": "candidat_recue"}),
    "candidatures:candidature_creer": ((SEC,), 200, {"candidat_pk": "candidat_libre"}),
    "candidatures:candidature_list": (TOUS, 200, {}),
    "candidatures:candidature_detail": (TOUS, 200, {"pk": "cand_recue"}),
    "candidatures:candidature_modifier": ((SEC,), 200, {"pk": "cand_recue"}),
    "candidatures:piece_telecharger": (TOUS, 200, {"pk": "piece_a"}),
    "candidatures:candidats_informer": ((SEC,), 200, {}),
    "candidatures:candidature_informer": ((SEC,), 405, {"pk": "cand_traitement"}),
    "candidatures:candidature_preselectionner": ((RESP,), 405, {"pk": "cand_recue"}),
    "candidatures:candidature_planifier_entretien": ((RESP,), 405, {"pk": "cand_traitement"}),
    "candidatures:candidature_accorder": ((RESP,), 200, {"pk": "cand_traitement"}),
    "candidatures:candidature_refuser": ((RESP,), 200, {"pk": "cand_recue"}),
    "candidatures:candidature_rediriger": ((RESP,), 200, {"pk": "cand_recue"}),
    # ── stages ───────────────────────────────────────────────────────────────
    "stages:stage_list": (TOUS, 200, {}),
    "stages:stages_a_evaluer": ((RESP, ADMIN), 200, {}),
    "stages:vivier": ((RESP, ADMIN), 200, {}),
    "stages:vivier_export_csv": ((RESP, ADMIN), 200, {}),
    "stages:stage_detail": (TOUS, 200, {"pk": "stage_cours"}),
    "stages:stage_constituer": ((SEC,), 200, {"candidature_pk": "cand_accordee"}),
    "stages:stage_modifier": ((SEC,), 200, {"pk": "stage_cours"}),
    "stages:stage_terminer": ((RESP,), 200, {"pk": "stage_cours"}),
    "stages:stage_interrompre": ((RESP,), 200, {"pk": "stage_cours"}),
    "stages:stage_evaluer": ((RESP,), 200, {"pk": "stage_fini"}),
    "stages:rapport_telecharger": ((RESP, ADMIN), 200, {"pk": "stage_fini"}),
}

_PDF = b"%PDF-1.4 test etape 10"


def _routes_nommees():
    """Toutes les routes « ns:nom » du projet, hors admin Django et API."""
    def parcourir(motifs, ns=None):
        for motif in motifs:
            if isinstance(motif, URLResolver):
                sous_ns = motif.namespace or ns
                if sous_ns == "admin" or str(motif.pattern).startswith("api"):
                    continue
                yield from parcourir(motif.url_patterns, sous_ns)
            elif motif.name:
                yield f"{ns}:{motif.name}" if ns else motif.name
    return set(parcourir(get_resolver().url_patterns))


class _DonneesPagesMixin:
    """Jeu de données réaliste partagé (fichiers dans le dossier temporaire de settings_test)."""

    @classmethod
    def setUpTestData(cls):
        call_command("init_donnees", stdout=StringIO())
        aujourd_hui = timezone.localdate()

        cls.type_stage = TypeStage.objects.get(libelle="Stage professionnel")
        cls.etab = Etablissement.objects.create(nom="Université Joseph Ki-Zerbo", ville="Ouagadougou")
        cls.canal = CanalPublication.objects.create(nom="Site web")

        cls.dept_a = Departement.objects.create(nom="Informatique")
        cls.dept_b = Departement.objects.create(nom="Comptabilité")
        cls.resp_a = Personnel.objects.create(nom="Kaboré", prenom="Awa", departement=cls.dept_a)
        cls.resp_b = Personnel.objects.create(nom="Sawadogo", prenom="Issa", departement=cls.dept_b)
        cls.maitre_a = Personnel.objects.create(nom="Zongo", prenom="Paul", departement=cls.dept_a)
        cls.maitre_b = Personnel.objects.create(nom="Ilboudo", prenom="Marie", departement=cls.dept_b)
        Departement.objects.filter(pk=cls.dept_a.pk).update(responsable=cls.resp_a)
        Departement.objects.filter(pk=cls.dept_b.pk).update(responsable=cls.resp_b)

        def utilisateur(email, role, personnel=None):
            u = Utilisateur.objects.create_user(
                email=email, password="pass", first_name="Test", last_name=role, personnel=personnel,
            )
            u.groups.add(Group.objects.get(name=role))
            return u

        cls.utilisateurs = {
            ADMIN: utilisateur("admin@test.bf", ADMIN),
            SEC: utilisateur("sec@test.bf", SEC),
            RESP: utilisateur("resp@test.bf", RESP, personnel=cls.resp_a),
        }
        cls.u_sec = cls.utilisateurs[SEC]
        cls.notifs = {
            role: Notification.objects.create(destinataire=u, message="Test", lien="/")
            for role, u in cls.utilisateurs.items()
        }

        debut = aujourd_hui + datetime.timedelta(days=30)
        fin = debut + datetime.timedelta(days=90)

        def besoin(dept):
            return Besoin.objects.create(
                departement=dept, type_stage=cls.type_stage, date_debut=debut, date_fin=fin,
                profil_recherche="Développeur", nombre_places=2, statut=StatutBesoin.PRIS_EN_CHARGE,
            )

        cls.besoin_a = besoin(cls.dept_a)
        cls.besoin_libre = Besoin.objects.create(
            departement=cls.dept_a, type_stage=cls.type_stage, date_debut=debut, date_fin=fin,
            profil_recherche="Réseau", nombre_places=1, statut=StatutBesoin.ENVOYE,
        )
        cls.besoin_b = besoin(cls.dept_b)

        def offre(b, titre):
            return Offre.objects.create(
                besoin=b, departement=b.departement, type_stage=cls.type_stage, titre=titre,
                description="Description", profil_recherche="Profil", date_debut=debut, date_fin=fin,
                nombre_places=2, texte_publie="Texte publié", statut=StatutOffre.OUVERTE,
            )

        cls.offre_a = offre(cls.besoin_a, "Stage développeur")
        cls.offre_b = offre(cls.besoin_b, "Stage comptable")
        cls.publication = Publication.objects.create(
            offre=cls.offre_a, canal=cls.canal, url="https://example.com/offre", date_publication=aujourd_hui,
        )

        telephones = iter(range(70000001, 70000100))

        def candidat(nom):
            return Candidat.objects.create(
                nom=nom, prenom="Test", telephone=str(next(telephones)), email=f"{nom.lower()}@test.bf",
                niveau_etudes="L3", filiere="Informatique", etablissement=cls.etab,
            )

        def candidature(cand, dept, statut, offre=None, **extra):
            return Candidature.objects.create(
                candidat=cand, departement=dept, type_stage=cls.type_stage,
                type_demande=TypeDemande.SUITE_OFFRE if offre else TypeDemande.SPONTANEE, offre=offre,
                debut_disponibilite=debut, fin_disponibilite=fin, duree_souhaitee=3, statut=statut, **extra,
            )

        def piece(cand):
            pj = PieceJointe(candidature=cand, type_piece=TypePiece.CV, nom_original="cv.pdf")
            pj.fichier.save("cv.pdf", ContentFile(_PDF), save=True)
            return pj

        def stage(cand, maitre, statut, **extra):
            s = Stage.objects.create(
                candidature=cand, maitre_stage=maitre, date_debut=aujourd_hui - datetime.timedelta(days=60),
                date_fin_prevue=aujourd_hui + datetime.timedelta(days=30), statut=statut, **extra,
            )
            AffectationMaitreStage.objects.create(stage=s, maitre_stage=maitre, affecte_par=cls.u_sec)
            return s

        cls.candidat_libre = candidat("Libre")
        cls.candidat_recue = candidat("Ouedraogo")
        cls.cand_recue = candidature(cls.candidat_recue, cls.dept_a, StatutCandidature.RECUE)
        cls.piece_a = piece(cls.cand_recue)
        TransfertCandidature.objects.create(
            candidature=cls.cand_recue, departement_source=cls.dept_b, departement_cible=cls.dept_a,
            motif="Profil plus adapté", realise_par=cls.utilisateurs[RESP],
        )
        enregistrer_historique(cls.cand_recue, cls.u_sec, "", StatutCandidature.RECUE, "Saisie")

        cls.cand_traitement = candidature(
            candidat("Traore"), cls.dept_a, StatutCandidature.EN_TRAITEMENT, offre=cls.offre_a,
            date_entretien=timezone.now() + datetime.timedelta(days=5),
        )
        cls.cand_accordee = candidature(candidat("Compaore"), cls.dept_a, StatutCandidature.ACCORDEE)

        cls.stage_cours = stage(
            candidature(candidat("Kone"), cls.dept_a, StatutCandidature.ACCORDEE),
            cls.maitre_a, StatutStage.EN_COURS,
        )
        enregistrer_historique(cls.stage_cours, cls.u_sec, StatutStage.A_VENIR, StatutStage.EN_COURS)

        cls.stage_fini = stage(
            candidature(candidat("Sanou"), cls.dept_a, StatutCandidature.ACCORDEE),
            cls.maitre_a, StatutStage.TERMINE, date_fin_reelle=aujourd_hui - datetime.timedelta(days=2),
            note=15, vivier=True, date_evaluation=aujourd_hui,
        )
        cls.stage_fini.rapport.save("rapport.pdf", ContentFile(_PDF), save=True)

        # Département B : objets que le Responsable du département A ne doit pas atteindre.
        cls.cand_b = candidature(candidat("Bationo"), cls.dept_b, StatutCandidature.EN_TRAITEMENT)
        cls.piece_b = piece(cls.cand_b)
        cls.stage_b = stage(
            candidature(candidat("Some"), cls.dept_b, StatutCandidature.ACCORDEE),
            cls.maitre_b, StatutStage.EN_COURS,
        )
        cls.stage_b_fini = stage(
            candidature(candidat("Yameogo"), cls.dept_b, StatutCandidature.ACCORDEE),
            cls.maitre_b, StatutStage.TERMINE, date_fin_reelle=aujourd_hui - datetime.timedelta(days=2),
            note=10, vivier=False, date_evaluation=aujourd_hui,
        )
        cls.stage_b_fini.rapport.save("rapport_b.pdf", ContentFile(_PDF), save=True)

    def _url(self, nom, params, role=None):
        kwargs = {}
        for cle, ref in params.items():
            if ref == "@notif":
                kwargs[cle] = self.notifs[role].pk
            elif ref.startswith("="):
                kwargs[cle] = ref[1:]
            else:
                kwargs[cle] = getattr(self, ref).pk
        return reverse(nom, kwargs=kwargs)

    def _get(self, url, role=None):
        """Code HTTP de la réponse, ou « 500 Exception » si la vue lève une erreur."""
        self.client.logout()
        if role:
            self.client.force_login(self.utilisateurs[role])
        try:
            return self.client.get(url).status_code
        except Exception as exc:  # noqa: BLE001 — on veut lister toutes les pages en échec
            return f"500 {type(exc).__name__}: {str(exc).splitlines()[0][:120]}"


class PagesParRoleTests(_DonneesPagesMixin, TestCase):

    def test_toutes_les_routes_sont_couvertes(self):
        manquantes = _routes_nommees() - set(MATRICE)
        self.assertFalse(manquantes, f"Routes à ajouter dans MATRICE : {sorted(manquantes)}")

    def test_aucune_route_inconnue_dans_la_matrice(self):
        inconnues = set(MATRICE) - _routes_nommees()
        self.assertFalse(inconnues, f"Routes de MATRICE qui n'existent plus : {sorted(inconnues)}")

    def test_chaque_page_avec_chaque_role(self):
        ecarts = []
        for nom, (autorises, code_ok, params) in MATRICE.items():
            for role in TOUS:
                obtenu = self._get(self._url(nom, params, role), role)
                attendu = code_ok if role in autorises else 403
                if obtenu != attendu:
                    ecarts.append(f"{nom:50} {role:15} attendu {attendu}, obtenu {obtenu}")
        self.assertFalse(ecarts, "\n" + "\n".join(ecarts))

    def test_get_ne_modifie_aucune_donnee(self):
        actions = [n for n, (_, code, _) in MATRICE.items() if code in (302, 405)]
        actions.remove("suivi:notification_lire")
        for nom in actions:
            autorises, _, params = MATRICE[nom]
            self._get(self._url(nom, params, autorises[0]), autorises[0])

        self.assertTrue(Departement.objects.get(pk=self.dept_a.pk).actif)
        self.assertTrue(Personnel.objects.get(pk=self.maitre_a.pk).actif)
        self.assertTrue(TypeStage.objects.get(pk=self.type_stage.pk).actif)
        self.assertTrue(CanalPublication.objects.get(pk=self.canal.pk).actif)
        etab = Etablissement.objects.get(pk=self.etab.pk)
        self.assertEqual((etab.actif, etab.partenaire), (True, False))
        self.assertTrue(Utilisateur.objects.get(pk=self.u_sec.pk).is_active)
        self.assertEqual(Besoin.objects.get(pk=self.besoin_libre.pk).statut, StatutBesoin.ENVOYE)
        self.assertEqual(Offre.objects.get(pk=self.offre_a.pk).statut, StatutOffre.OUVERTE)
        self.assertTrue(Publication.objects.filter(pk=self.publication.pk).exists())
        self.assertFalse(Notification.objects.filter(lue=True).exists())
        cand = Candidature.objects.get(pk=self.cand_traitement.pk)
        self.assertFalse(cand.candidat_informe)
        self.assertEqual(Candidature.objects.get(pk=self.cand_recue.pk).statut, StatutCandidature.RECUE)

    def test_anonyme_redirige_vers_connexion(self):
        ecarts = []
        connexion = reverse("comptes:connexion")
        for nom, (_, _, params) in MATRICE.items():
            if nom == "comptes:connexion":
                continue
            # La notification d'un rôle quelconque suffit : l'anonyme n'atteint jamais la vue.
            url = self._url(nom, params, ADMIN)
            self.client.logout()
            reponse = self.client.get(url)
            if reponse.status_code != 302 or not reponse["Location"].startswith(connexion):
                ecarts.append(f"{nom:50} obtenu {reponse.status_code} {reponse.get('Location', '')}")
        self.assertFalse(ecarts, "\n" + "\n".join(ecarts))
        self.assertEqual(self._get(reverse("comptes:connexion")), 200)


class CloisonnementDepartementTests(_DonneesPagesMixin, TestCase):
    """Le Responsable du département A n'atteint pas les objets du département B."""

    ROUTES_AUTRE_DEPARTEMENT = [
        ("offres:besoin_modifier", {"pk": "besoin_b"}),
        ("offres:offre_detail", {"pk": "offre_b"}),
        ("candidatures:candidature_detail", {"pk": "cand_b"}),
        ("candidatures:piece_telecharger", {"pk": "piece_b"}),
        ("candidatures:candidature_accorder", {"pk": "cand_b"}),
        ("candidatures:candidature_refuser", {"pk": "cand_b"}),
        ("candidatures:candidature_rediriger", {"pk": "cand_b"}),
        ("stages:stage_detail", {"pk": "stage_b"}),
        ("stages:stage_terminer", {"pk": "stage_b"}),
        ("stages:stage_interrompre", {"pk": "stage_b"}),
        ("stages:stage_evaluer", {"pk": "stage_b_fini"}),
        ("stages:rapport_telecharger", {"pk": "stage_b_fini"}),
        # Exception voulue : fiche (lecture seule) et rapport d'un stage AU VIVIER d'un autre
        # département restent accessibles — testé dans stages.tests.
        # À TRANCHER (docs/rapports/etape_10_pages_rapport.md) — volontairement absent :
        #   stages:rapport_telecharger d'un autre département : autorisé si stage au vivier.
    ]

    def test_routes_autre_departement_refusees(self):
        ecarts = []
        for nom, params in self.ROUTES_AUTRE_DEPARTEMENT:
            obtenu = self._get(self._url(nom, params), RESP)
            if obtenu not in (403, 404):
                ecarts.append(f"{nom:50} obtenu {obtenu}")
        self.assertFalse(ecarts, "\n" + "\n".join(ecarts))

    def test_listes_filtrees_sur_le_departement(self):
        self.client.force_login(self.utilisateurs[RESP])
        candidatures = self.client.get(reverse("candidatures:candidature_list")).context["object_list"]
        self.assertNotIn(self.cand_b, list(candidatures))
        stages = self.client.get(reverse("stages:stage_list")).context["object_list"]
        self.assertNotIn(self.stage_b, list(stages))
        offres = self.client.get(reverse("offres:offre_list")).context["object_list"]
        self.assertNotIn(self.offre_b, list(offres))


class TelechargementsTests(_DonneesPagesMixin, TestCase):

    def test_piece_jointe_servie_en_pdf(self):
        self.client.force_login(self.utilisateurs[SEC])
        reponse = self.client.get(reverse("candidatures:piece_telecharger", args=[self.piece_a.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertEqual(b"".join(reponse.streaming_content), _PDF)

    def test_rapport_servi_en_piece_jointe(self):
        self.client.force_login(self.utilisateurs[RESP])
        reponse = self.client.get(reverse("stages:rapport_telecharger", args=[self.stage_fini.pk]))
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("attachment", reponse["Content-Disposition"])
        self.assertEqual(b"".join(reponse.streaming_content), _PDF)

    def test_export_vivier_csv(self):
        self.client.force_login(self.utilisateurs[ADMIN])
        reponse = self.client.get(reverse("stages:vivier_export_csv"))
        self.assertEqual(reponse.status_code, 200)
        self.assertIn("text/csv", reponse["Content-Type"])
        self.assertIn("Sanou", reponse.content.decode("utf-8-sig"))
