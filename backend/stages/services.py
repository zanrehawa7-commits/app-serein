from django.db import transaction
from django.utils import timezone


class TransitionInterdite(Exception):
    pass


def _secretaires_actives():
    from comptes.models import Utilisateur
    return list(Utilisateur.objects.filter(groups__name="Secrétaire", is_active=True))


def _responsable_departement(departement):
    from comptes.models import Utilisateur
    return Utilisateur.objects.filter(
        membre__departement=departement,
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

    today = timezone.localdate()
    statut = StatutStage.EN_COURS if date_debut <= today else StatutStage.A_VENIR

    stage = Stage.objects.create(
        candidature=cand,
        maitre_stage=maitre_stage,
        date_debut=date_debut,
        date_fin_prevue=date_fin_prevue,
        statut=statut,
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

    changements = []
    if date_debut is not None and s.statut == StatutStage.A_VENIR:
        if date_debut != s.date_debut:
            changements.append(f"début : {s.date_debut} → {date_debut}")
            s.date_debut = date_debut

    if date_fin_prevue != s.date_fin_prevue:
        changements.append(f"fin prévue : {s.date_fin_prevue} → {date_fin_prevue}")
        s.date_fin_prevue = date_fin_prevue

    if maitre_stage.pk != s.maitre_stage_id:
        changements.append(f"maître de stage : {s.maitre_stage} → {maitre_stage}")
        s.maitre_stage = maitre_stage

    if not changements:
        return s

    s.save()
    commentaire = "Stage modifié — " + " ; ".join(changements)
    enregistrer_historique(s, utilisateur, s.statut, s.statut, commentaire)
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
