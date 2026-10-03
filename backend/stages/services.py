import datetime
from django.db import transaction
from django.utils import timezone


class TransitionInterdite(Exception):
    pass


def erreurs_disponibilite(candidature, date_debut=None, date_fin_prevue=None):
    """
    RG-S11 : le stage se déroule pendant la disponibilité du candidat.
    Renvoie {champ: message} ; une date à None n'est pas vérifiée (ex. début non modifiable).
    """
    message = (
        "Le stage doit se dérouler pendant la disponibilité du candidat : "
        f"du {candidature.debut_disponibilite:%d/%m/%Y} au {candidature.fin_disponibilite:%d/%m/%Y}."
    )
    erreurs = {}
    if date_debut is not None and date_debut < candidature.debut_disponibilite:
        erreurs["date_debut"] = message
    if date_fin_prevue is not None and date_fin_prevue > candidature.fin_disponibilite:
        erreurs["date_fin_prevue"] = message
    return erreurs


def _verifier_disponibilite(candidature, date_debut=None, date_fin_prevue=None):
    erreurs = erreurs_disponibilite(candidature, date_debut, date_fin_prevue)
    if erreurs:
        raise TransitionInterdite(next(iter(erreurs.values())))


def _secretaires_actives():
    from comptes.models import Utilisateur
    return list(Utilisateur.objects.filter(groups__name="Secrétaire", is_active=True))


def _responsable_departement(departement):
    from comptes.models import Utilisateur
    return Utilisateur.objects.filter(
        personnel__departement=departement,
        is_active=True,
        groups__name="Responsable",
    ).first()


@transaction.atomic
def constituer_stage(candidature, date_debut, date_fin_prevue, maitre_stage, utilisateur):
    from suivi.services import enregistrer_historique, notifier
    from candidatures.models import Candidature as C, StatutCandidature
    from .models import Stage, StatutStage

    cand = C.objects.select_for_update().get(pk=candidature.pk)
    if cand.statut != StatutCandidature.ACCORDEE:
        raise TransitionInterdite("Seule une candidature accordée peut donner lieu à un stage.")

    if Stage.objects.filter(candidature=cand).exists():
        raise TransitionInterdite(
            f"La candidature {cand.reference} a déjà un stage constitué."
        )

    if maitre_stage.departement_id != cand.departement_id:
        raise TransitionInterdite(
            "Le maître de stage doit appartenir au département de la candidature (RG22)."
        )
    if not maitre_stage.actif:
        raise TransitionInterdite("Le maître de stage doit être actif.")
    _verifier_disponibilite(cand, date_debut, date_fin_prevue)

    today = timezone.localdate()
    statut = StatutStage.EN_COURS if date_debut <= today else StatutStage.A_VENIR

    from .models import AffectationMaitreStage
    stage = Stage.objects.create(
        candidature=cand,
        maitre_stage=maitre_stage,
        date_debut=date_debut,
        date_fin_prevue=date_fin_prevue,
        statut=statut,
    )

    AffectationMaitreStage.objects.create(
        stage=stage,
        maitre_stage=maitre_stage,
        affecte_par=utilisateur,
    )

    enregistrer_historique(stage, utilisateur, "", statut, "Stage constitué.")

    cand.candidat_informe = False
    cand.date_information = None
    cand.save(update_fields=["candidat_informe", "date_information"])

    lien = f"/stages/{stage.pk}/"
    secs = _secretaires_actives()
    if secs:
        date_fmt = date_debut.strftime("%d/%m/%Y")
        notifier(
            secs,
            f"Stage constitué pour {cand.candidat}, début le {date_fmt} : informer le stagiaire.",
            lien,
        )

    return stage


def debut_modifiable(stage):
    """La date de début ne se modifie que sur un stage à venir jamais démarré."""
    from .models import StatutStage
    return stage.statut == StatutStage.A_VENIR


@transaction.atomic
def modifier_stage(stage, date_fin_prevue, maitre_stage, utilisateur, date_debut=None):
    from suivi.services import enregistrer_historique
    from .models import Stage as S, StatutStage

    s = S.objects.select_for_update().get(pk=stage.pk)
    if s.statut not in [StatutStage.A_VENIR, StatutStage.EN_COURS]:
        raise TransitionInterdite(
            f"Impossible de modifier un stage au statut « {s.get_statut_display()} »."
        )

    if maitre_stage.departement_id != s.candidature.departement_id:
        raise TransitionInterdite("Le maître de stage doit appartenir au département (RG22).")
    if not maitre_stage.actif:
        raise TransitionInterdite("Le maître de stage doit être actif.")
    # Début vérifié seulement s'il est modifiable : un stage en cours dont le début
    # (antérieur à la règle) sort de la disponibilité reste modifiable.
    debut_a_verifier = (date_debut or s.date_debut) if debut_modifiable(s) else None
    _verifier_disponibilite(s.candidature, debut_a_verifier, date_fin_prevue)

    changements = []
    if date_debut is not None and debut_modifiable(s):
        if date_debut != s.date_debut:
            changements.append(f"début : {s.date_debut} → {date_debut}")
            s.date_debut = date_debut

    if date_fin_prevue != s.date_fin_prevue:
        changements.append(f"fin prévue : {s.date_fin_prevue} → {date_fin_prevue}")
        s.date_fin_prevue = date_fin_prevue

    maitre_change = maitre_stage.pk != s.maitre_stage_id
    if maitre_change:
        changements.append(f"maître de stage : {s.maitre_stage} → {maitre_stage}")
        s.maitre_stage = maitre_stage

    if not changements:
        return s

    s.save()
    commentaire = "Stage modifié — " + " ; ".join(changements)
    enregistrer_historique(s, utilisateur, s.statut, s.statut, commentaire)

    if maitre_change:
        from .models import AffectationMaitreStage
        AffectationMaitreStage.objects.create(
            stage=s,
            maitre_stage=maitre_stage,
            affecte_par=utilisateur,
        )

    return s


@transaction.atomic
def terminer_stage(stage, date_fin_reelle, utilisateur):
    from suivi.services import enregistrer_historique, notifier
    from .models import Stage as S, StatutStage

    s = S.objects.select_for_update().get(pk=stage.pk)
    if s.statut != StatutStage.EN_COURS:
        raise TransitionInterdite(
            f"Impossible de terminer : statut actuel « {s.get_statut_display()} »."
        )
    today = timezone.localdate()
    if date_fin_reelle < s.date_debut:
        raise TransitionInterdite("La date de fin réelle ne peut pas être antérieure à la date de début.")
    if date_fin_reelle > today:
        raise TransitionInterdite("La date de fin réelle ne peut pas être dans le futur.")

    s.statut = StatutStage.TERMINE
    s.date_fin_reelle = date_fin_reelle
    s.save(update_fields=["statut", "date_fin_reelle"])

    enregistrer_historique(s, utilisateur, StatutStage.EN_COURS, StatutStage.TERMINE, "Stage terminé.")

    lien = f"/stages/{s.pk}/"
    secs = _secretaires_actives()
    if secs:
        notifier(secs, f"Stage de {s.candidature.candidat} terminé.", lien)

    return s


@transaction.atomic
def interrompre_stage(stage, date_fin_reelle, motif, utilisateur):
    from suivi.services import enregistrer_historique, notifier
    from .models import Stage as S, StatutStage

    s = S.objects.select_for_update().get(pk=stage.pk)
    if s.statut not in [StatutStage.A_VENIR, StatutStage.EN_COURS]:
        raise TransitionInterdite(
            f"Impossible d'interrompre : statut actuel « {s.get_statut_display()} »."
        )
    if not motif.strip():
        raise TransitionInterdite("Le motif d'interruption est obligatoire.")

    ancien = s.statut
    s.statut = StatutStage.INTERROMPU
    s.date_fin_reelle = date_fin_reelle
    s.motif_interruption = motif
    s.save(update_fields=["statut", "date_fin_reelle", "motif_interruption"])

    enregistrer_historique(
        s, utilisateur, ancien, StatutStage.INTERROMPU,
        f"Stage interrompu — {motif}",
    )

    lien = f"/stages/{s.pk}/"
    secs = _secretaires_actives()
    if secs:
        notifier(secs, f"Stage de {s.candidature.candidat} interrompu.", lien)

    return s


# ─── Évaluation ───────────────────────────────────────────────────────────────


def peut_evaluer(stage, aujourd_hui=None):
    """Retourne (bool: peut_évaluer, date|None: date_verrouillage)."""
    from .models import StatutStage
    if aujourd_hui is None:
        aujourd_hui = timezone.localdate()
    if stage.statut != StatutStage.TERMINE:
        return False, None
    if stage.date_evaluation:
        date_verrou = stage.date_evaluation + datetime.timedelta(days=30)
        if aujourd_hui > date_verrou:
            return False, date_verrou
        return True, date_verrou
    return True, None


@transaction.atomic
def evaluer_stage(stage, note, vivier, utilisateur, rapport_file=None, aujourd_hui=None):
    from suivi.services import enregistrer_historique
    from .models import Stage as S, StatutStage

    if aujourd_hui is None:
        aujourd_hui = timezone.localdate()

    s = S.objects.select_for_update().get(pk=stage.pk)
    if s.statut != StatutStage.TERMINE:
        raise TransitionInterdite("Seul un stage terminé peut être évalué.")

    if s.date_evaluation:
        date_verrou = s.date_evaluation + datetime.timedelta(days=30)
        if aujourd_hui > date_verrou:
            raise TransitionInterdite(
                f"L'évaluation est verrouillée depuis le {date_verrou.strftime('%d/%m/%Y')}."
            )

    if not (1 <= note <= 20):
        raise TransitionInterdite("La note doit être comprise entre 1 et 20.")
    if vivier and note < 12:
        raise TransitionInterdite("Le vivier ne peut être activé que si la note est ≥ 12.")

    s.note = note
    s.vivier = vivier

    if rapport_file:
        s.rapport = rapport_file

    if not s.date_evaluation:
        s.date_evaluation = aujourd_hui

    s.save()

    enregistrer_historique(
        s, utilisateur, StatutStage.TERMINE, StatutStage.TERMINE,
        f"Évaluation : note {note}/20, vivier {'oui' if vivier else 'non'}.",
    )

    return s


# ─── Fonctions pour la commande automatique ───────────────────────────────────


@transaction.atomic
def demarrer_stage_auto(stage, aujourd_hui):
    """A_VENIR → EN_COURS si date_debut <= aujourd_hui. Retourne True si transition faite."""
    from suivi.services import enregistrer_historique
    from .models import Stage as S, StatutStage

    s = S.objects.select_for_update().get(pk=stage.pk)
    if s.statut != StatutStage.A_VENIR or s.date_debut > aujourd_hui:
        return False

    s.statut = StatutStage.EN_COURS
    s.save(update_fields=["statut"])
    enregistrer_historique(
        s, None, StatutStage.A_VENIR, StatutStage.EN_COURS,
        "Démarrage automatique (Système).",
    )
    return True


@transaction.atomic
def cloturer_stage_auto(stage, aujourd_hui):
    """EN_COURS → TERMINE si date_fin_prevue < aujourd_hui. Retourne True si transition faite."""
    from suivi.services import enregistrer_historique, notifier
    from .models import Stage as S, StatutStage

    s = S.objects.select_for_update().get(pk=stage.pk)
    if s.statut != StatutStage.EN_COURS or s.date_fin_prevue >= aujourd_hui:
        return False

    s.statut = StatutStage.TERMINE
    s.date_fin_reelle = s.date_fin_prevue
    s.save(update_fields=["statut", "date_fin_reelle"])
    enregistrer_historique(
        s, None, StatutStage.EN_COURS, StatutStage.TERMINE,
        "Clôture automatique (Système).",
    )

    resp = _responsable_departement(s.candidature.departement)
    if resp:
        lien = f"/stages/{s.pk}/"
        notifier(
            [resp],
            f"Stage terminé : {s.candidature.candidat} — à évaluer.",
            lien,
        )

    return True
