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
from comptes.models import ProfilRole, Utilisateur
from offres.models import Besoin, Offre, Publication, StatutBesoin, StatutOffre
from referentiels.models import CanalPublication, Departement, Etablissement, Personnel, TypeStage
from stages.models import AffectationMaitreStage, PeriodeInterruption, Stage, StatutStage
from suivi.models import Notification
from suivi.services import enregistrer_historique

ADMIN = "Administrateur"
SEC = "Secrétaire"
RESP = "Responsable"
TOUS = (ADMIN, SEC, RESP)
CONSULT_TOUT = "Consultation tout coché"
CONSULT_RIEN = "Consultation rien coché"

# RG-U10 : seules routes qu'un rôle de consultation peut ouvrir, avec le droit requis
# (None = tout rôle de consultation actif). Toute autre route : 403. Le code attendu est
# celui de MATRICE.
DROIT_CONSULTATION = {
    "comptes:connexion": None,
    "comptes:deconnexion": None,
    "comptes:password_change": None,
    "comptes:password_change_done": None,
    "comptes:tableau_de_bord": None,
    "comptes:en_developpement": None,
    "comptes:tableau_bord_consultation": None,
    "suivi:notification_list": None,
    "suivi:notification_tout_lire": None,
    "suivi:notification_lire": None,
    "offres:besoin_list": "offres.view_besoin",
    "offres:besoin_detail": "offres.view_besoin",
    "offres:offre_list": "offres.view_offre",
    "offres:offre_detail": "offres.view_offre",
    "candidatures:candidat_detail": "candidatures.view_candidat",
    "candidatures:candidature_list": "candidatures.view_candidature",
    "candidatures:candidature_detail": "candidatures.view_candidature",
    "candidatures:piece_telecharger": "candidatures.telecharger_pieces_jointes",
    "stages:stage_list": "stages.view_stage",
    "stages:stage_detail": "stages.view_stage",
    "stages:vivier": "stages.consulter_vivier",
    "stages:vivier_export_csv": "stages.exporter_vivier",
    "stages:rapport_telecharger": "stages.telecharger_rapports",
    "suivi:historique_list": "suivi.view_historique",
}

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
    "comptes:tableau_bord_consultation": ((), 200, {}),
    "comptes:en_developpement": (TOUS, 200, {}),
    "comptes:utilisateur_list": ((ADMIN,), 200, {}),
    "comptes:utilisateur_creer": ((ADMIN,), 200, {}),
    "comptes:utilisateur_modifier": ((ADMIN,), 200, {"pk": "u_sec"}),
    "comptes:utilisateur_activer": ((ADMIN,), 302, {"pk": "u_sec"}),
    "comptes:utilisateur_reinit_mdp": ((ADMIN,), 200, {"pk": "u_sec"}),
    "comptes:roles_list": ((ADMIN,), 200, {}),
    "comptes:permissions_role": ((ADMIN,), 200, {"role_nom": "=Secrétaire"}),
    "comptes:role_consultation_creer": ((ADMIN,), 200, {}),
    "comptes:role_consultation_modifier": ((ADMIN,), 200, {"pk": "role_audit"}),
    "comptes:role_consultation_activer": ((ADMIN,), 302, {"pk": "role_audit"}),
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
    "suivi:historique_list": ((ADMIN,), 200, {}),
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
    "stages:stage_reprendre": ((RESP,), 200, {"pk": "stage_interrompu"}),
    "stages:rapport_telecharger": ((RESP, ADMIN), 200, {"pk": "stage_fini"}),
}

# Toutes les actions réservées au Responsable et liées à un département (besoin, candidature, stage).
# Constituer / modifier un stage (dont le maître de stage) sont réservés à la Secrétaire : 403 par rôle.
def _actions_responsable(besoin, candidature, stage, stage_termine, stage_interrompu):
    return [
        ("offres:besoin_modifier", {"pk": besoin}),
        ("offres:besoin_annuler", {"pk": besoin}),
        ("candidatures:candidature_preselectionner", {"pk": candidature}),
        ("candidatures:candidature_planifier_entretien", {"pk": candidature}),
        ("candidatures:candidature_accorder", {"pk": candidature}),
        ("candidatures:candidature_refuser", {"pk": candidature}),
        ("candidatures:candidature_rediriger", {"pk": candidature}),
        ("stages:stage_terminer", {"pk": stage}),
        ("stages:stage_interrompre", {"pk": stage}),
        ("stages:stage_evaluer", {"pk": stage_termine}),
        ("stages:stage_reprendre", {"pk": stage_interrompu}),
    ]


ACTIONS_RESPONSABLE_DEPT_A = _actions_responsable(
    "besoin_libre", "cand_recue", "stage_cours", "stage_fini", "stage_interrompu"
)
ACTIONS_RESPONSABLE_DEPT_B = _actions_responsable(
    "besoin_b", "cand_b", "stage_b", "stage_b_fini", "stage_b_interrompu"
)

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
        cls.role_audit = Group.objects.create(name="Auditeur")
        ProfilRole.objects.create(groupe=cls.role_audit, description="Lecture")
        from comptes.permissions import CODES_DROITS_CONSULTATION
        cls.utilisateurs[CONSULT_TOUT] = _utilisateur_consultation(
            "tout@test.bf", CONSULT_TOUT, sorted(CODES_DROITS_CONSULTATION)
        )
        cls.utilisateurs[CONSULT_RIEN] = _utilisateur_consultation("rien@test.bf", CONSULT_RIEN, [])
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

        def stage_interrompu(nom, dept, maitre):
            s = stage(
                candidature(candidat(nom), dept, StatutCandidature.ACCORDEE), maitre, StatutStage.INTERROMPU,
                date_fin_reelle=aujourd_hui - datetime.timedelta(days=5), motif_interruption="Maladie",
            )
            PeriodeInterruption.objects.create(
                stage=s, date_debut=s.date_fin_reelle, motif_interruption="Maladie", interrompu_par=cls.u_sec,
            )
            return s

        cls.stage_interrompu = stage_interrompu("Zida", cls.dept_a, cls.maitre_a)
        cls.stage_b_interrompu = stage_interrompu("Nikiema", cls.dept_b, cls.maitre_b)

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

    def _post(self, url, role):
        """Comme _get, en POST sans données : le contrôle d'accès doit précéder la validation."""
        self.client.logout()
        self.client.force_login(self.utilisateurs[role])
        try:
            return self.client.post(url, {}).status_code
        except Exception as exc:  # noqa: BLE001
            return f"500 {type(exc).__name__}: {str(exc).splitlines()[0][:120]}"

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

    def test_chaque_page_roles_de_consultation(self):
        """« Tout coché » : lecture partout, 403 sur toute action ; « rien coché » : pages communes seules."""
        ecarts = []
        for nom, (_, code_ok, params) in MATRICE.items():
            for role in (CONSULT_TOUT, CONSULT_RIEN):
                ouverte = nom in DROIT_CONSULTATION and (role == CONSULT_TOUT or DROIT_CONSULTATION[nom] is None)
                attendu = code_ok if ouverte else 403
                obtenu = self._get(self._url(nom, params, role), role)
                if obtenu != attendu:
                    ecarts.append(f"{nom:50} {role:25} attendu {attendu}, obtenu {obtenu}")
        self.assertFalse(ecarts, "\n" + "\n".join(ecarts))

    def test_droits_consultation_routes_existantes(self):
        self.assertFalse(set(DROIT_CONSULTATION) - set(MATRICE))

    def test_aucun_lien_d_action_pour_un_role_de_consultation(self):
        """Chaque lien ou formulaire d'une page vue en consultation mène à une route de consultation."""
        import re
        from django.urls import Resolver404, resolve
        pages = [
            ("comptes:tableau_bord_consultation", {}), ("offres:besoin_list", {}),
            ("offres:besoin_detail", {"pk": "besoin_libre"}), ("offres:offre_list", {}),
            ("offres:offre_detail", {"pk": "offre_a"}), ("candidatures:candidature_list", {}),
            ("candidatures:candidature_detail", {"pk": "cand_recue"}),
            ("candidatures:candidature_detail", {"pk": "cand_traitement"}),
            ("candidatures:candidature_detail", {"pk": "cand_accordee"}),
            ("candidatures:candidat_detail", {"pk": "candidat_recue"}), ("stages:stage_list", {}),
            ("stages:stage_detail", {"pk": "stage_cours"}), ("stages:stage_detail", {"pk": "stage_fini"}),
            ("stages:stage_detail", {"pk": "stage_interrompu"}), ("stages:vivier", {}),
            ("suivi:historique_list", {}),
        ]
        ecarts = []
        for role in (CONSULT_TOUT, CONSULT_RIEN):
            self.client.logout()
            self.client.force_login(self.utilisateurs[role])
            for nom, params in pages:
                reponse = self.client.get(self._url(nom, params))
                if reponse.status_code != 200:
                    continue
                html = reponse.content.decode()
                for cible in re.findall(r'(?:href|action)="(/[^"#?]*)', html):
                    if cible.startswith(("/static/", "/media/")):
                        continue
                    try:
                        route = resolve(cible)
                    except Resolver404:
                        continue
                    nom_route = f"{route.namespace}:{route.url_name}" if route.namespace else route.url_name
                    if nom_route not in DROIT_CONSULTATION:
                        ecarts.append(f"{role} — {nom} {params} → {cible} ({nom_route})")
        self.assertFalse(ecarts, "\n" + "\n".join(sorted(set(ecarts))))

    def test_chaque_formulaire_a_un_bouton_d_envoi(self):
        """Un formulaire POST sans bouton est inutilisable ({{ form|crispy }} n'affiche pas les boutons du helper)."""
        import re
        ecarts = []
        for nom, (autorises, code_ok, params) in MATRICE.items():
            if code_ok != 200 or not autorises:
                continue
            role = autorises[0]
            self.client.logout()
            self.client.force_login(self.utilisateurs[role])
            reponse = self.client.get(self._url(nom, params, role))
            if reponse.streaming or "text/html" not in reponse.get("Content-Type", ""):
                continue
            html = reponse.content.decode()
            for formulaire in re.findall(r'<form[^>]*method="post"[^>]*>(.*?)</form>', html, re.S | re.I):
                if not re.search(r'<button(?![^>]*type="button")|<input[^>]*type="submit"', formulaire, re.I):
                    ecarts.append(f"{nom} ({role})")
        self.assertFalse(ecarts, "Formulaire sans bouton d'envoi :\n" + "\n".join(sorted(set(ecarts))))

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
        ("stages:stage_reprendre", {"pk": "stage_b_interrompu"}),
        ("stages:stage_evaluer", {"pk": "stage_b_fini"}),
        ("stages:rapport_telecharger", {"pk": "stage_b_fini"}),
        # Exception voulue : fiche (lecture seule, RG-E7) et rapport (RG-E5) d'un stage AU VIVIER
        # d'un autre département restent accessibles — testé dans stages.tests.
    ]

    def test_routes_autre_departement_refusees(self):
        ecarts = []
        for nom, params in self.ROUTES_AUTRE_DEPARTEMENT:
            obtenu = self._get(self._url(nom, params), RESP)
            if obtenu not in (403, 404):
                ecarts.append(f"{nom:50} obtenu {obtenu}")
        self.assertFalse(ecarts, "\n" + "\n".join(ecarts))

    def test_post_autre_departement_refuse_sans_modification(self):
        ecarts = []
        for nom, params in ACTIONS_RESPONSABLE_DEPT_B:
            obtenu = self._post(self._url(nom, params), RESP)
            if obtenu != 403:
                ecarts.append(f"{nom:50} obtenu {obtenu}")
        self.assertFalse(ecarts, "\n" + "\n".join(ecarts))
        self.assertEqual(Stage.objects.get(pk=self.stage_b.pk).statut, StatutStage.EN_COURS)
        self.assertEqual(Stage.objects.get(pk=self.stage_b_fini.pk).note, 10)
        self.assertEqual(Candidature.objects.get(pk=self.cand_b.pk).statut, StatutCandidature.EN_TRAITEMENT)
        self.assertEqual(Besoin.objects.get(pk=self.besoin_b.pk).statut, StatutBesoin.PRIS_EN_CHARGE)

    def test_listes_filtrees_sur_le_departement(self):
        self.client.force_login(self.utilisateurs[RESP])
        candidatures = self.client.get(reverse("candidatures:candidature_list")).context["object_list"]
        self.assertNotIn(self.cand_b, list(candidatures))
        stages = self.client.get(reverse("stages:stage_list")).context["object_list"]
        self.assertNotIn(self.stage_b, list(stages))
        offres = self.client.get(reverse("offres:offre_list")).context["object_list"]
        self.assertNotIn(self.offre_b, list(offres))


class ResponsableSansDepartementTests(_DonneesPagesMixin, TestCase):
    """Un Responsable dont le personnel n'a pas de département n'agit sur rien (403, jamais 500)."""

    def setUp(self):
        Personnel.objects.filter(pk=self.resp_a.pk).update(departement=None)

    def test_actions_refusees_en_get_et_en_post(self):
        ecarts = []
        for nom, params in ACTIONS_RESPONSABLE_DEPT_A + [("offres:besoin_creer", {})]:
            url = self._url(nom, params)
            for methode, obtenu in (("GET", self._get(url, RESP)), ("POST", self._post(url, RESP))):
                # GET d'une action POST seule : 405, ou 302 de redirection sans effet
                # (vérifié par test_get_ne_modifie_aucune_donnee), est acceptable.
                if obtenu != 403 and not (methode == "GET" and obtenu in (302, 405)):
                    ecarts.append(f"{nom:50} {methode:4} obtenu {obtenu}")
        self.assertFalse(ecarts, "\n" + "\n".join(ecarts))
        self.assertEqual(Stage.objects.get(pk=self.stage_cours.pk).statut, StatutStage.EN_COURS)
        self.assertEqual(Stage.objects.get(pk=self.stage_fini.pk).note, 15)
        self.assertEqual(Candidature.objects.get(pk=self.cand_recue.pk).statut, StatutCandidature.RECUE)
        self.assertEqual(Besoin.objects.get(pk=self.besoin_libre.pk).statut, StatutBesoin.ENVOYE)
        self.assertEqual(Besoin.objects.count(), 3)


def _utilisateur_consultation(email, nom_role, codes, actif=True):
    """Rôle de consultation (profil non système) portant les droits « app.codename » donnés."""
    from django.contrib.auth.models import Permission
    groupe = Group.objects.create(name=nom_role)
    ProfilRole.objects.create(groupe=groupe, actif=actif)
    for code in codes:
        app, codename = code.split(".")
        groupe.permissions.add(Permission.objects.get(content_type__app_label=app, codename=codename))
    u = Utilisateur.objects.create_user(email=email, password="pass", first_name="Test", last_name=nom_role)
    u.groups.add(groupe)
    return u


class RoleConsultationAccesTests(_DonneesPagesMixin, TestCase):
    """RG-U10 : lecture selon les droits cochés, tous départements, 403 sur toute action."""

    ACTIONS_CANDIDATURES = [
        ("candidatures:candidat_recherche", {}),
        ("candidatures:candidat_creer", {}),
        ("candidatures:candidat_modifier", {"pk": "candidat_recue"}),
        ("candidatures:candidature_creer", {"candidat_pk": "candidat_libre"}),
        ("candidatures:candidature_modifier", {"pk": "cand_recue"}),
        ("candidatures:candidats_informer", {}),
        ("candidatures:candidature_informer", {"pk": "cand_traitement"}),
        ("candidatures:candidature_preselectionner", {"pk": "cand_recue"}),
        ("candidatures:candidature_planifier_entretien", {"pk": "cand_traitement"}),
        ("candidatures:candidature_accorder", {"pk": "cand_traitement"}),
        ("candidatures:candidature_refuser", {"pk": "cand_recue"}),
        ("candidatures:candidature_rediriger", {"pk": "cand_recue"}),
    ]

    def _client(self, utilisateur):
        self.client.logout()
        self.client.force_login(utilisateur)
        return self.client

    def _code(self, nom, params, methode="get"):
        try:
            return getattr(self.client, methode)(self._url(nom, params)).status_code
        except Exception as exc:  # noqa: BLE001
            return f"500 {type(exc).__name__}"

    def test_view_candidature_lecture_tous_departements_et_403_ailleurs(self):
        self._client(_utilisateur_consultation("aud@test.bf", "Lecteur", ["candidatures.view_candidature"]))
        liste = self.client.get(reverse("candidatures:candidature_list"))
        self.assertEqual(liste.status_code, 200)
        self.assertIn(self.cand_b, list(liste.context["object_list"]))
        self.assertIn(self.cand_recue, list(liste.context["object_list"]))
        self.assertEqual(self._code("candidatures:candidature_detail", {"pk": "cand_b"}), 200)
        ecarts = []
        for nom, params in self.ACTIONS_CANDIDATURES:
            for methode in ("get", "post"):
                obtenu = self._code(nom, params, methode)
                if obtenu != 403:
                    ecarts.append(f"{nom} {methode} → {obtenu}")
        for nom, params in [
            ("candidatures:candidat_detail", {"pk": "candidat_recue"}),
            ("candidatures:piece_telecharger", {"pk": "piece_a"}),
            ("offres:offre_list", {}), ("offres:besoin_list", {}),
            ("stages:stage_list", {}), ("stages:vivier", {}), ("stages:vivier_export_csv", {}),
            ("stages:rapport_telecharger", {"pk": "stage_fini"}),
        ]:
            obtenu = self._code(nom, params)
            if obtenu != 403:
                ecarts.append(f"{nom} → {obtenu}")
        self.assertFalse(ecarts, "\n".join(ecarts))

    def test_pieces_jointes_seulement_avec_le_droit(self):
        url_piece = reverse("candidatures:piece_telecharger", args=[self.piece_a.pk])
        self._client(_utilisateur_consultation("sans@test.bf", "SansPieces", ["candidatures.view_candidature"]))
        fiche = self.client.get(reverse("candidatures:candidature_detail", args=[self.cand_recue.pk]))
        self.assertIsNone(fiche.context["pieces"])
        self.assertNotContains(fiche, url_piece)
        self.assertEqual(self.client.get(url_piece).status_code, 403)

        self._client(_utilisateur_consultation(
            "avec@test.bf", "AvecPieces", ["candidatures.view_candidature", "candidatures.telecharger_pieces_jointes"]
        ))
        fiche = self.client.get(reverse("candidatures:candidature_detail", args=[self.cand_recue.pk]))
        self.assertContains(fiche, url_piece)
        self.assertEqual(self.client.get(url_piece).status_code, 200)

    def test_pieces_masquees_sur_la_fiche_stage_sans_le_droit(self):
        self._client(_utilisateur_consultation("st@test.bf", "Stages", ["stages.view_stage"]))
        fiche = self.client.get(reverse("stages:stage_detail", args=[self.stage_cours.pk]))
        self.assertEqual(fiche.status_code, 200)
        self.assertIsNone(fiche.context["pieces"])
        self.assertNotContains(fiche, "/candidatures/pieces/")
        self.assertNotContains(fiche, reverse("candidatures:candidature_detail", args=[self.stage_cours.candidature.pk]))

    def test_vivier_export_et_rapport_selon_les_droits(self):
        self._client(_utilisateur_consultation("v@test.bf", "Vivier", ["stages.consulter_vivier"]))
        vivier = self.client.get(reverse("stages:vivier"))
        self.assertEqual(vivier.status_code, 200)
        self.assertNotContains(vivier, reverse("stages:vivier_export_csv"))
        self.assertNotContains(vivier, reverse("stages:rapport_telecharger", args=[self.stage_fini.pk]))
        self.assertEqual(self.client.get(reverse("stages:vivier_export_csv")).status_code, 403)

        self._client(_utilisateur_consultation(
            "v2@test.bf", "Vivier2", ["stages.consulter_vivier", "stages.exporter_vivier", "stages.telecharger_rapports"]
        ))
        self.assertEqual(self.client.get(reverse("stages:vivier_export_csv")).status_code, 200)
        self.assertEqual(
            self.client.get(reverse("stages:rapport_telecharger", args=[self.stage_fini.pk])).status_code, 200
        )

    def test_role_desactive_n_ouvre_aucun_acces(self):
        self._client(_utilisateur_consultation(
            "off@test.bf", "Ancien", ["candidatures.view_candidature", "stages.view_stage"], actif=False
        ))
        for nom in ["candidatures:candidature_list", "stages:stage_list", "suivi:notification_list"]:
            with self.subTest(url=nom):
                self.assertEqual(self.client.get(reverse(nom)).status_code, 403)

    def test_filtre_departement_sur_la_liste_des_stages(self):
        self._client(_utilisateur_consultation("f@test.bf", "Filtre", ["stages.view_stage"]))
        reponse = self.client.get(reverse("stages:stage_list"), {"departement": self.dept_b.pk})
        stages = list(reponse.context["object_list"])
        self.assertTrue(stages)
        self.assertTrue(all(s.candidature.departement == self.dept_b for s in stages))

    def test_notifications_ouvertes_sans_droit(self):
        self._client(_utilisateur_consultation("n@test.bf", "Aucun", []))
        self.assertEqual(self.client.get(reverse("suivi:notification_list")).status_code, 200)


class InterfaceConsultationTests(_DonneesPagesMixin, TestCase):
    """RG-U10 / RG-U12 : menu et tableau de bord d'après les droits ; page Historique."""

    def _connecter(self, codes, actif=True, nom="Lecteur"):
        u = _utilisateur_consultation(f"{nom.lower()}@test.bf", nom, codes, actif=actif)
        self.client.logout()
        self.client.force_login(u)
        return u

    def test_redirection_et_menu_d_apres_les_droits(self):
        self._connecter(["candidatures.view_candidature"])
        reponse = self.client.get(reverse("comptes:tableau_de_bord"), follow=True)
        self.assertRedirects(reponse, reverse("comptes:tableau_bord_consultation"))
        self.assertContains(reponse, reverse("candidatures:candidature_list"))
        for absent in ["offres:offre_list", "offres:besoin_list", "stages:stage_list", "stages:vivier",
                       "suivi:historique_list", "comptes:utilisateur_list", "candidatures:candidat_recherche"]:
            with self.subTest(absent=absent):
                self.assertNotContains(reponse, reverse(absent))

    def test_tableau_de_bord_seulement_les_modules_consultables(self):
        self._connecter(["stages.view_stage"])
        reponse = self.client.get(reverse("comptes:tableau_bord_consultation"))
        self.assertEqual([c[0] for c in reponse.context["compteurs"]], ["Stages en cours"])
        self.assertFalse(reponse.context["voit_historique"])

    def test_role_desactive_message_sur_le_tableau_de_bord(self):
        self._connecter(["stages.view_stage"], actif=False)
        reponse = self.client.get(reverse("comptes:tableau_de_bord"), follow=True)
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, "Rôle désactivé")
        self.assertNotIn("compteurs", reponse.context)

    def test_tableau_de_bord_consultation_refuse_aux_roles_de_base(self):
        for role in TOUS:
            with self.subTest(role=role):
                self.assertEqual(self._get(reverse("comptes:tableau_bord_consultation"), role), 403)

    def test_menus_des_roles_de_base(self):
        historique = reverse("suivi:historique_list")
        for role, present in [(ADMIN, True), (SEC, False), (RESP, False)]:
            with self.subTest(role=role):
                self.client.logout()
                self.client.force_login(self.utilisateurs[role])
                reponse = self.client.get(reverse("comptes:tableau_de_bord"), follow=True)
                self.assertEqual(historique in reponse.content.decode(), present)

    def test_historique_administrateur_avec_liens(self):
        self.client.force_login(self.utilisateurs[ADMIN])
        reponse = self.client.get(reverse("suivi:historique_list"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, reverse("candidatures:candidature_detail", args=[self.cand_recue.pk]))
        self.assertContains(reponse, reverse("stages:stage_detail", args=[self.stage_cours.pk]))

    def test_historique_liens_seulement_vers_les_objets_consultables(self):
        self._connecter(["suivi.view_historique", "stages.view_stage"])
        reponse = self.client.get(reverse("suivi:historique_list"))
        self.assertEqual(reponse.status_code, 200)
        self.assertContains(reponse, reverse("stages:stage_detail", args=[self.stage_cours.pk]))
        self.assertNotContains(reponse, reverse("candidatures:candidature_detail", args=[self.cand_recue.pk]))
        self.assertContains(reponse, str(self.cand_recue))

    def test_historique_refuse_sans_le_droit(self):
        self._connecter(["stages.view_stage"])
        self.assertEqual(self.client.get(reverse("suivi:historique_list")).status_code, 403)

    def test_historique_filtre_par_type(self):
        self.client.force_login(self.utilisateurs[ADMIN])
        reponse = self.client.get(reverse("suivi:historique_list"), {"type": "stages.stage"})
        types = {h.content_type.model for h in reponse.context["historiques"]}
        self.assertEqual(types, {"stage"})


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
