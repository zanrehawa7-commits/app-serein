from django.contrib.auth import get_user_model
from django.db import transaction
from django.urls import reverse

from commun.utils import ajouter_mois
from suivi.services import enregistrer_historique, notifier

from .models import Besoin, Offre, StatutBesoin, StatutOffre


class TransitionInterdite(Exception):
    pass


def _valider_duree(type_stage, date_debut, date_fin):
    """Lève TransitionInterdite si la durée sort des bornes du type de stage."""
    from django.utils.dateparse import parse_date
    if isinstance(date_debut, str):
        date_debut = parse_date(date_debut)
    if isinstance(date_fin, str):
        date_fin = parse_date(date_fin)
    date_min_fin = ajouter_mois(date_debut, type_stage.duree_min_mois)
    date_max_fin = ajouter_mois(date_debut, type_stage.duree_max_mois)
    if date_fin < date_min_fin:
        raise TransitionInterdite(
            f"Durée trop courte pour « {type_stage} » "
            f"(min {type_stage.duree_min_mois} mois — fin au plus tôt le {date_min_fin.strftime('%d/%m/%Y')})."
        )
    if date_fin > date_max_fin:
        raise TransitionInterdite(
            f"Durée trop longue pour « {type_stage} » "
            f"(max {type_stage.duree_max_mois} mois — fin au plus tard le {date_max_fin.strftime('%d/%m/%Y')})."
        )


def _secretaires_actives():
    Utilisateur = get_user_model()
    return list(Utilisateur.objects.filter(groups__name="Secrétaire", is_active=True))


@transaction.atomic
def creer_besoin(departement, type_stage, date_debut, date_fin, profil_recherche, nombre_places, utilisateur):
    _valider_duree(type_stage, date_debut, date_fin)
    besoin = Besoin.objects.create(
        departement=departement,
        type_stage=type_stage,
        date_debut=date_debut,
        date_fin=date_fin,
        profil_recherche=profil_recherche,
        nombre_places=nombre_places,
        statut=StatutBesoin.ENVOYE,
    )
    enregistrer_historique(besoin, utilisateur, nouveau_statut=StatutBesoin.ENVOYE, commentaire="Besoin créé.")
    lien = reverse("offres:besoin_detail", kwargs={"pk": besoin.pk})
    notifier(
        _secretaires_actives(),
        f"Nouveau besoin : {departement} — {type_stage}.",
        lien=lien,
    )
    return besoin


@transaction.atomic
def annuler_besoin(besoin, utilisateur):
    if besoin.statut not in (StatutBesoin.ENVOYE, StatutBesoin.PRIS_EN_CHARGE):
        raise TransitionInterdite(
            f"Impossible d'annuler un besoin au statut « {besoin.get_statut_display()} »."
        )
    ancien = besoin.statut
    besoin.statut = StatutBesoin.ANNULE
    besoin.save(update_fields=["statut"])
    enregistrer_historique(
        besoin, utilisateur,
        ancien_statut=ancien,
        nouveau_statut=StatutBesoin.ANNULE,
        commentaire="Besoin annulé.",
    )
    lien = reverse("offres:besoin_detail", kwargs={"pk": besoin.pk})
    notifier(
        _secretaires_actives(),
        f"Besoin annulé : {besoin.departement} — {besoin.type_stage}.",
        lien=lien,
    )
    return besoin


@transaction.atomic
def creer_offre(type_stage, titre, description, profil_recherche, date_debut, date_fin, nombre_places, utilisateur, besoin=None):
    if besoin is not None:
        # Verrou contre les créations concurrentes sur le même besoin (RG atomique)
        besoin = Besoin.objects.select_for_update().get(pk=besoin.pk)
        if besoin.statut != StatutBesoin.ENVOYE:
            raise TransitionInterdite(
                f"Le besoin est déjà au statut « {besoin.get_statut_display()} » et ne peut plus être pris en charge."
            )
        try:
            if besoin.offre is not None:
                raise TransitionInterdite("Ce besoin dispose déjà d'une offre associée.")
        except Offre.DoesNotExist:
            pass

        ancien_statut_besoin = besoin.statut
        besoin.statut = StatutBesoin.PRIS_EN_CHARGE
        besoin.save(update_fields=["statut"])
        enregistrer_historique(
            besoin, utilisateur,
            ancien_statut=ancien_statut_besoin,
            nouveau_statut=StatutBesoin.PRIS_EN_CHARGE,
            commentaire="Besoin pris en charge — offre créée.",
        )

    _valider_duree(type_stage, date_debut, date_fin)
    offre = Offre.objects.create(
        besoin=besoin,
        type_stage=type_stage,
        titre=titre,
        description=description,
        profil_recherche=profil_recherche,
        date_debut=date_debut,
        date_fin=date_fin,
        nombre_places=nombre_places,
        statut=StatutOffre.BROUILLON,
    )
    enregistrer_historique(offre, utilisateur, nouveau_statut=StatutOffre.BROUILLON, commentaire="Offre créée.")
    return offre


@transaction.atomic
def ouvrir_offre(offre, utilisateur):
    if offre.statut != StatutOffre.BROUILLON:
        raise TransitionInterdite(
            f"L'offre est au statut « {offre.get_statut_display()} » — impossible d'ouvrir."
        )
    ancien = offre.statut
    offre.statut = StatutOffre.OUVERTE
    offre.save(update_fields=["statut"])
    enregistrer_historique(offre, utilisateur, ancien_statut=ancien, nouveau_statut=StatutOffre.OUVERTE)
    return offre


@transaction.atomic
def suspendre_offre(offre, utilisateur):
    if offre.statut != StatutOffre.OUVERTE:
        raise TransitionInterdite(
            f"L'offre est au statut « {offre.get_statut_display()} » — impossible de suspendre."
        )
    ancien = offre.statut
    offre.statut = StatutOffre.SUSPENDUE
    offre.save(update_fields=["statut"])
    enregistrer_historique(offre, utilisateur, ancien_statut=ancien, nouveau_statut=StatutOffre.SUSPENDUE)
    return offre


@transaction.atomic
def rouvrir_offre(offre, utilisateur):
    if offre.statut != StatutOffre.SUSPENDUE:
        raise TransitionInterdite(
            f"L'offre est au statut « {offre.get_statut_display()} » — impossible de rouvrir."
        )
    ancien = offre.statut
    offre.statut = StatutOffre.OUVERTE
    offre.save(update_fields=["statut"])
    enregistrer_historique(offre, utilisateur, ancien_statut=ancien, nouveau_statut=StatutOffre.OUVERTE)
    return offre


@transaction.atomic
def fermer_offre(offre, utilisateur):
    if offre.statut not in (StatutOffre.OUVERTE, StatutOffre.SUSPENDUE):
        raise TransitionInterdite(
            f"L'offre est au statut « {offre.get_statut_display()} » — impossible de fermer."
        )
    ancien = offre.statut
    offre.statut = StatutOffre.FERMEE
    offre.save(update_fields=["statut"])
    enregistrer_historique(offre, utilisateur, ancien_statut=ancien, nouveau_statut=StatutOffre.FERMEE)
    return offre


@transaction.atomic
def supprimer_offre(offre, utilisateur):
    if offre.statut != StatutOffre.BROUILLON:
        raise TransitionInterdite(
            f"Seule une offre en brouillon peut être supprimée (statut actuel : « {offre.get_statut_display()} »)."
        )
    offre.delete()
