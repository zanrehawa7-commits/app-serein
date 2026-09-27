import re
from django.db import transaction
from django.utils import timezone


class CandidatExistant(Exception):
    pass


class CandidatureActiveExistante(Exception):
    pass


def normaliser_telephone(telephone):
    """Strip espaces/points/tirets, supprime préfixe +226/00226 → 8 chiffres."""
    if not telephone:
        return telephone
    tel = re.sub(r"[\s.\-]", "", telephone)
    tel = re.sub(r"^(\+226|00226)", "", tel)
    return tel


def rechercher_candidats(q):
    from django.db.models import Q
    from .models import Candidat
    tel = normaliser_telephone(q)
    return (
        Candidat.objects.filter(
            Q(nom__icontains=q)
            | Q(prenom__icontains=q)
            | Q(telephone__icontains=tel)
            | Q(email__icontains=q)
        )
        .prefetch_related("candidatures")
        .order_by("nom", "prenom")
    )


def _verifier_unicite_telephone(telephone, exclude_pk=None):
    from .models import Candidat
    qs = Candidat.objects.filter(telephone=telephone)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise CandidatExistant(f"Un candidat avec le téléphone {telephone} existe déjà.")


def creer_candidat(nom, prenom, telephone, email="", adresse="", niveau_etudes="", filiere="", etablissement=None):
    from .models import Candidat
    tel = normaliser_telephone(telephone)
    _verifier_unicite_telephone(tel)
    return Candidat.objects.create(
        nom=nom,
        prenom=prenom,
        telephone=tel,
        email=email,
        adresse=adresse,
        niveau_etudes=niveau_etudes,
        filiere=filiere,
        etablissement=etablissement,
    )


def modifier_candidat(candidat, nom, prenom, telephone, email="", adresse="", niveau_etudes="", filiere="", etablissement=None):
    tel = normaliser_telephone(telephone)
    _verifier_unicite_telephone(tel, exclude_pk=candidat.pk)
    candidat.nom = nom
    candidat.prenom = prenom
    candidat.telephone = tel
    candidat.email = email
    candidat.adresse = adresse
    candidat.niveau_etudes = niveau_etudes
    candidat.filiere = filiere
    candidat.etablissement = etablissement
    candidat.save()
    return candidat


@transaction.atomic
def _generer_reference():
    from .models import Candidature
    annee = timezone.now().year
    derniere = (
        Candidature.objects.select_for_update()
        .filter(reference__startswith=f"CAND-{annee}-")
        .order_by("reference")
        .last()
    )
    if derniere:
        numero = int(derniere.reference.split("-")[-1]) + 1
    else:
        numero = 1
    return f"CAND-{annee}-{numero:04d}"


def _responsable_departement(departement):
    from comptes.models import Utilisateur
    return Utilisateur.objects.filter(
        membre__departement=departement,
        is_active=True,
        groups__name="Responsable",
    ).first()


def _administrateurs_actifs():
    from comptes.models import Utilisateur
    return list(
        Utilisateur.objects.filter(groups__name="Administrateur", is_active=True)
    )


@transaction.atomic
def creer_candidature(
    candidat, departement, type_stage, type_demande,
    debut_disponibilite, fin_disponibilite, duree_souhaitee,
    commentaire="", offre=None, pieces_data=None, utilisateur=None,
):
    from suivi.services import enregistrer_historique, notifier
    from .models import Candidature, PieceJointe, StatutCandidature

    # RG07
    if Candidature.objects.filter(
        candidat=candidat,
        statut__in=[StatutCandidature.RECUE, StatutCandidature.EN_TRAITEMENT],
    ).exists():
        raise CandidatureActiveExistante(
            f"{candidat} a déjà une candidature active."
        )

    reference = _generer_reference()

    candidature = Candidature.objects.create(
        reference=reference,
        candidat=candidat,
        departement=departement,
        offre=offre,
        type_stage=type_stage,
        type_demande=type_demande,
        debut_disponibilite=debut_disponibilite,
        fin_disponibilite=fin_disponibilite,
        duree_souhaitee=duree_souhaitee,
        commentaire=commentaire,
        statut=StatutCandidature.RECUE,
    )

    for pd in (pieces_data or []):
        PieceJointe.objects.create(
            candidature=candidature,
            type_piece=pd["type_piece"],
            fichier=pd["fichier"],
            nom_original=pd.get("nom_original", ""),
        )

    enregistrer_historique(candidature, utilisateur, "", StatutCandidature.RECUE, "Candidature reçue.")

    lien = f"/candidatures/{candidature.pk}/"
    responsable = _responsable_departement(departement)
    if responsable:
        notifier([responsable], f"Nouvelle candidature {reference} reçue pour votre département.", lien)
    else:
        admins = _administrateurs_actifs()
        if admins:
            notifier(admins, f"Candidature {reference} : département sans responsable.", lien)

    return candidature


@transaction.atomic
def modifier_candidature(
    candidature, departement, type_stage, type_demande,
    debut_disponibilite, fin_disponibilite, duree_souhaitee,
    commentaire="", offre=None,
    nouvelles_pieces=None, pieces_a_supprimer=None, utilisateur=None,
):
    from suivi.services import enregistrer_historique
    from .models import PieceJointe, StatutCandidature

    candidature.departement = departement
    candidature.type_stage = type_stage
    candidature.type_demande = type_demande
    candidature.debut_disponibilite = debut_disponibilite
    candidature.fin_disponibilite = fin_disponibilite
    candidature.duree_souhaitee = duree_souhaitee
    candidature.commentaire = commentaire
    candidature.offre = offre
    candidature.save()

    if pieces_a_supprimer:
        PieceJointe.objects.filter(pk__in=pieces_a_supprimer, candidature=candidature).delete()

    for pd in (nouvelles_pieces or []):
        PieceJointe.objects.create(
            candidature=candidature,
            type_piece=pd["type_piece"],
            fichier=pd["fichier"],
            nom_original=pd.get("nom_original", ""),
        )

    enregistrer_historique(
        candidature, utilisateur,
        StatutCandidature.RECUE, StatutCandidature.RECUE,
        "Candidature modifiée.",
    )
    return candidature


@transaction.atomic
def marquer_informe(candidature, utilisateur):
    from suivi.services import enregistrer_historique
    candidature.candidat_informe = True
    candidature.date_information = timezone.now()
    candidature.save(update_fields=["candidat_informe", "date_information"])
    enregistrer_historique(
        candidature, utilisateur,
        candidature.statut, candidature.statut,
        "Candidat informé de la décision.",
    )
    return candidature
