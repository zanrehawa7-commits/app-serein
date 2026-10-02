import calendar
from datetime import date


def ajouter_mois(d: date, n: int) -> date:
    """
    Retourne la date d + n mois entiers.

    Gère les fins de mois : 31/01 + 1 → 28 ou 29/02 selon l'année,
    31/03 + 1 → 30/04, etc.  n peut être 0 ou positif.
    """
    if n == 0:
        return d
    mois_total = d.month + n
    annee = d.year + (mois_total - 1) // 12
    mois = ((mois_total - 1) % 12) + 1
    max_jour = calendar.monthrange(annee, mois)[1]
    jour = min(d.day, max_jour)
    return date(annee, mois, jour)
