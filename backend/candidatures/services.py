import re
from django.db import transaction
from django.utils import timezone

from commun.utils import ajouter_mois


class CandidatExistant(Exception):
    pass


class CandidatureActiveExistante(Exception):
    pass


class ValidationCandidature(Exception):
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


def _valider_candidature(
    type_stage, debut_disponibilite, fin_disponibilite, duree_souhaitee,
    type_demande, offre, pieces_data, creation=True, debut_original=None,
):
    from .models import TypeDemande
    from django.utils.dateparse import parse_date

    # Normaliser les dates (str → date) pour accepter les deux formes
    if isinstance(debut_disponibilite, str):
        debut_disponibilite = parse_date(debut_disponibilite)
    if isinstance(fin_disponibilite, str):
        fin_disponibilite = parse_date(fin_disponibilite)
    if isinstance(debut_original, str):
        debut_original = parse_date(debut_original)

    # début >= aujourd'hui (création, ou modification si la date a changé)
    if debut_disponibilite:
        doit_valider_debut = creation or (debut_original and debut_disponibilite != debut_original)
        if doit_valider_debut and debut_disponibilite < timezone.localdate():
            raise ValidationCandidature(
                "La date de début de disponibilité doit être aujourd'hui ou dans le futur."
            )

    # fin_disponibilite <= début + 12 mois
    if debut_disponibilite and fin_disponibilite:
        limite_12 = ajouter_mois(debut_disponibilite, 12)
        if fin_disponibilite > limite_12:
            raise ValidationCandidature(
                f"La fin de disponibilité ne peut pas dépasser 12 mois après le début "
                f"(au plus tard le {limite_12.strftime('%d/%m/%Y')})."
            )

    # duree_souhaitee dans les bornes du type de stage
    if type_stage and duree_souhaitee is not None:
        if duree_souhaitee < type_stage.duree_min_mois:
            raise ValidationCandidature(
                f"La durée souhaitée est inférieure au minimum autorisé "
                f"pour « {type_stage} » ({type_stage.duree_min_mois} mois)."
            )
        if duree_souhaitee > type_stage.duree_max_mois:
            raise ValidationCandidature(
                f"La durée souhaitée dépasse le maximum autorisé "
                f"pour « {type_stage} » ({type_stage.duree_max_mois} mois)."
            )

    # RG09 : cohérence type_demande / offre
    if type_demande == TypeDemande.SUITE_OFFRE and not offre:
        raise ValidationCandidature("Une offre est obligatoire pour une candidature suite à une offre.")
    if type_demande in (TypeDemande.SPONTANEE, TypeDemande.AUTRE) and offre:
        raise ValidationCandidature("Ce type de demande ne doit pas être lié à une offre.")

    # CV obligatoire (création uniquement)
    if creation and pieces_data is not None:
        has_cv = any(pd.get("type_piece") == "CV" for pd in pieces_data)
        if not has_cv:
            raise ValidationCandidature("Au moins un CV est obligatoire.")


def _responsable_departement(departement):
    from comptes.models import Utilisateur
    return Utilisateur.objects.filter(
        personnel__departement=departement,
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

    _valider_candidature(
        type_stage=type_stage,
        debut_disponibilite=debut_disponibilite,
        fin_disponibilite=fin_disponibilite,
        duree_souhaitee=duree_souhaitee,
        type_demande=type_demande,
        offre=offre,
        pieces_data=pieces_data,
        creation=True,
    )

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

    _valider_candidature(
        type_stage=type_stage,
        debut_disponibilite=debut_disponibilite,
        fin_disponibilite=fin_disponibilite,
        duree_souhaitee=duree_souhaitee,
        type_demande=type_demande,
        offre=offre,
        pieces_data=None,  # pas de contrôle CV à la modification
        creation=False,
        debut_original=candidature.debut_disponibilite,
    )

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


# ─── Étape 7 — Transitions (Responsable) ─────────────────────────────────────


class TransitionInterdite(Exception):
    pass


class QuotaAtteint(Exception):
    pass


def _secretaires_actives():
    from comptes.models import Utilisateur
    return list(Utilisateur.objects.filter(groups__name="Secrétaire", is_active=True))


@transaction.atomic
def preselectionner(candidature, utilisateur, commentaire=""):
    from suivi.services import enregistrer_historique, notifier
    from .models import Candidature as C, StatutCandidature
    cand = C.objects.select_for_update().get(pk=candidature.pk)
    if cand.statut != StatutCandidature.RECUE:
        raise TransitionInterdite(
            f"Impossible de présélectionner : statut actuel « {cand.get_statut_display()} »."
        )
    cand.statut = StatutCandidature.EN_TRAITEMENT
    cand.candidat_informe = False
    cand.date_information = None
    cand.save(update_fields=["statut", "candidat_informe", "date_information"])
    enregistrer_historique(
        cand, utilisateur,
        StatutCandidature.RECUE, StatutCandidature.EN_TRAITEMENT,
        commentaire or "Candidature présélectionnée.",
    )
    lien = f"/candidatures/{cand.pk}/"
    secs = _secretaires_actives()
    if secs:
        notifier(secs, f"Décision sur {cand.reference} : En traitement. Candidat à informer.", lien)
    return cand


@transaction.atomic
def planifier_entretien(candidature, date_entretien, utilisateur):
    from datetime import timedelta
    from suivi.services import enregistrer_historique, notifier
    from .models import Candidature as C, StatutCandidature
    cand = C.objects.select_for_update().get(pk=candidature.pk)
    if cand.statut != StatutCandidature.EN_TRAITEMENT:
        raise TransitionInterdite(
            f"Impossible de planifier un entretien : statut actuel « {cand.get_statut_display()} »."
        )
    if date_entretien < timezone.now() + timedelta(hours=72):
        raise TransitionInterdite(
            "L'entretien doit être planifié au moins 72 h à l'avance."
        )
    cand.date_entretien = date_entretien
    cand.candidat_informe = False
    cand.date_information = None
    cand.alerte_entretien_envoyee = False
    cand.save(update_fields=["date_entretien", "candidat_informe", "date_information", "alerte_entretien_envoyee"])
    date_fmt = date_entretien.strftime("%d/%m/%Y à %H:%M")
    enregistrer_historique(
        cand, utilisateur,
        StatutCandidature.EN_TRAITEMENT, StatutCandidature.EN_TRAITEMENT,
        f"Entretien planifié le {date_fmt}.",
    )
    lien = f"/candidatures/{cand.pk}/"
    secs = _secretaires_actives()
    if secs:
        notifier(
            secs,
            f"Entretien planifié le {date_fmt} pour {cand.reference} : prévenir le candidat.",
            lien,
        )
    return cand


@transaction.atomic
def accorder(candidature, utilisateur, commentaire="", confirmer_depassement=False):
    from suivi.services import enregistrer_historique, notifier
    from .models import Candidature as C, StatutCandidature
    cand = C.objects.select_for_update().get(pk=candidature.pk)
    if cand.statut != StatutCandidature.EN_TRAITEMENT:
        raise TransitionInterdite(
            f"Impossible d'accorder : statut actuel « {cand.get_statut_display()} »."
        )
    if cand.offre_id and not confirmer_depassement:
        cand.offre.refresh_from_db()
        if cand.offre.places_restantes() <= 0:
            raise QuotaAtteint(
                f"Le quota de {cand.offre.nombre_places} place(s) est atteint pour cette offre."
            )
    cand.statut = StatutCandidature.ACCORDEE
    cand.candidat_informe = False
    cand.date_information = None
    cand.save(update_fields=["statut", "candidat_informe", "date_information"])
    enregistrer_historique(
        cand, utilisateur,
        StatutCandidature.EN_TRAITEMENT, StatutCandidature.ACCORDEE,
        commentaire or "Candidature accordée.",
    )
    lien = f"/candidatures/{cand.pk}/"
    secs = _secretaires_actives()
    if secs:
        notifier(secs, f"Décision sur {cand.reference} : Accordée. Candidat à informer.", lien)
    return cand


@transaction.atomic
def refuser(candidature, motif, precision_motif, utilisateur, commentaire=""):
    from suivi.services import enregistrer_historique, notifier
    from .models import Candidature as C, StatutCandidature, MotifRefus
    cand = C.objects.select_for_update().get(pk=candidature.pk)
    if cand.statut not in [StatutCandidature.RECUE, StatutCandidature.EN_TRAITEMENT]:
        raise TransitionInterdite(
            f"Impossible de refuser : statut actuel « {cand.get_statut_display()} »."
        )
    if not motif:
        raise TransitionInterdite("Le motif de refus est obligatoire.")
    if motif == MotifRefus.AUTRE and not precision_motif.strip():
        raise TransitionInterdite("La précision du motif est obligatoire pour « Autre ».")
    ancien_statut = cand.statut
    cand.statut = StatutCandidature.REFUSEE
    cand.motif_refus = motif
    cand.precision_motif = precision_motif
    cand.candidat_informe = False
    cand.date_information = None
    cand.save(update_fields=[
        "statut", "motif_refus", "precision_motif",
        "candidat_informe", "date_information",
    ])
    enregistrer_historique(
        cand, utilisateur,
        ancien_statut, StatutCandidature.REFUSEE,
        commentaire or f"Refusée — {cand.get_motif_refus_display()}.",
    )
    lien = f"/candidatures/{cand.pk}/"
    secs = _secretaires_actives()
    if secs:
        notifier(secs, f"Décision sur {cand.reference} : Refusée. Candidat à informer.", lien)
    return cand


@transaction.atomic
def rediriger(candidature, nouveau_departement, motif, utilisateur):
    from suivi.services import enregistrer_historique, notifier
    from .models import Candidature as C, StatutCandidature
    cand = C.objects.select_for_update().get(pk=candidature.pk)
    if cand.statut != StatutCandidature.RECUE:
        raise TransitionInterdite(
            f"Impossible de rediriger : statut actuel « {cand.get_statut_display()} »."
        )
    if not nouveau_departement.actif:
        raise TransitionInterdite("Le département cible n'est pas actif.")
    if nouveau_departement.pk == cand.departement_id:
        raise TransitionInterdite("Le département cible doit être différent du département actuel.")
    from .models import TransfertCandidature
    ancien_dept = cand.departement
    ancien_dept_nom = ancien_dept.nom
    cand.departement = nouveau_departement
    cand.candidat_informe = False
    cand.date_information = None
    cand.save(update_fields=["departement", "candidat_informe", "date_information"])
    TransfertCandidature.objects.create(
        candidature=cand,
        departement_source=ancien_dept,
        departement_cible=nouveau_departement,
        motif=motif,
        realise_par=utilisateur,
    )
    commentaire_hist = f"Redirigée de {ancien_dept_nom} vers {nouveau_departement.nom} : {motif}"
    enregistrer_historique(
        cand, utilisateur,
        StatutCandidature.RECUE, StatutCandidature.RECUE,
        commentaire_hist,
    )
    lien = f"/candidatures/{cand.pk}/"
    resp_nouveau = _responsable_departement(nouveau_departement)
    if resp_nouveau:
        notifier([resp_nouveau], f"Candidature {cand.reference} redirigée vers votre département.", lien)
    else:
        admins = _administrateurs_actifs()
        if admins:
            notifier(admins, f"Candidature {cand.reference} redirigée vers {nouveau_departement.nom} (sans responsable).", lien)
    secs = _secretaires_actives()
    if secs:
        notifier(secs, f"{cand.reference} redirigée vers {nouveau_departement.nom}.", lien)
    return cand


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
