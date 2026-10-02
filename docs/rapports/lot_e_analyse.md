# Lot E — Analyse des fonctionnalités avancées
## (Analyse seulement — aucun code implémenté dans ce lot)

**Date** : 2026-10-02  
**Branche** : `lot-d` (analyse rédigée en même temps)  
**Statut** : Analyse seulement — aucun code n'a été ajouté.

---

## Périmètre analysé

Ce lot regroupe des fonctionnalités à fort impact métier, plusieurs nécessitant des décisions Serein-GE avant implémentation.

---

## E1 — Tableau de bord global (Administrateur)

### Fonctionnalité
Tableau de bord agrégé pour l'Administrateur : vue d'ensemble de tous les départements — candidatures reçues, accordées, stages en cours, taux d'accord par type de stage, alertes globales.

### Analyse technique
- Aucun nouveau modèle nécessaire : tout se calcule par agrégations sur les modèles existants.
- Django ORM : `Candidature.objects.values("departement").annotate(...)`, `Stage.objects.values("statut").annotate(...)`.
- Vue simple `DashboardAdminView` (ListView ou TemplateView avec contexte enrichi).
- Graphiques : Bootstrap 5 + Chart.js (CDN) pour des barres/camemberts — pas de dépendance lourde.

### Effort estimé
Faible à modéré. 1–2 jours développeur.

### Questions ouvertes
- Quels indicateurs sont prioritaires pour Serein-GE ? (taux accord, délais moyens de traitement, top établissements ?)
- Faut-il un export CSV/PDF du tableau de bord ?

---

## E2 — Portail candidat (accès externe)

### Fonctionnalité
Un candidat peut suivre l'avancée de sa candidature en ligne avec un lien de suivi unique (sans création de compte).

### Analyse technique
- Nouveau modèle `LienSuiviCandidature` :
  - `candidature = OneToOneField(Candidature, CASCADE)`
  - `token = CharField(unique=True)` — UUID généré à la création de la candidature
  - `date_expiration = DateTimeField` (optionnel)
- Vue publique `SuiviCandidatureView` : décorée `@login_not_required` (Django 5.1+), accès via `/suivi/<token>/`.
- Expose : statut, date d'entretien, décision finale. Ne montre pas les commentaires internes ni les pièces jointes.
- Envoi du lien par la Secrétaire via email (nécessite configuration SMTP).

### Dépendances
- Configuration `EMAIL_BACKEND` + `DEFAULT_FROM_EMAIL` dans `.env`.
- Migration : CreateModel `LienSuiviCandidature`.

### Questions ouvertes
**DÉCISION SEREIN-GE REQUISE :**
1. Le lien doit-il expirer ? Si oui, au bout de combien de temps ?
2. Faut-il une page publique générique ou juste un email automatique ?
3. Quelles informations afficher au candidat ? (statut seul ? date entretien ? motif de refus ?)
4. La Secrétaire envoie-t-elle le lien manuellement ou automatiquement à chaque transition ?

---

## E3 — Statistiques et exports avancés

### Fonctionnalité
- Export Excel (.xlsx) de la liste des stagiaires avec filtres avancés.
- Export PDF d'une fiche candidature complète (pièces jointes comprises).
- Rapport mensuel automatique envoyé par email aux Administrateurs.

### Analyse technique
- **Export Excel** : bibliothèque `openpyxl` (légère, Django-compatible). Vue `ExportStagesXlsxView`, accès Administrateur + Responsable. Simple boucle sur le queryset → `openpyxl.Workbook`.
- **Export PDF candidature** : `reportlab` ou `weasyprint`. Weasyprint est plus simple (HTML → PDF) mais lourd à déployer (dépendances système). Reportlab génère directement mais l'API est verbeuse. Recommandation : évaluer selon l'environnement de production.
- **Rapport mensuel** : commande `python manage.py envoyer_rapport_mensuel` + cron/celery beat.

### Dépendances
- `openpyxl` : simple `pip install`, pas de dépendances système.
- `weasyprint` : nécessite `pango`, `cairo`, `libffi` — complexe sur Windows, simple sur Linux.

### Questions ouvertes
**DÉCISION SEREIN-GE REQUISE :**
1. Format PDF ou HTML pour la fiche candidature ?
2. Rapport mensuel par email : oui/non ? Destinataires ?
3. Quels champs dans l'export Excel des stages ?

---

## E4 — Notifications par email (en plus des notifications in-app)

### Fonctionnalité
En complément des notifications Django (déjà implémentées), envoyer des emails aux utilisateurs pour les événements importants : nouvelle candidature, décision, entretien planifié.

### Analyse technique
- Utiliser Django `send_mail()` ou `EmailMessage`.
- Envelopper dans `suivi/services.py` : `notifier_email(destinataires, sujet, corps_html)`.
- **Gabarits email** : `templates/emails/notification_entretien.html`, etc.
- Configuration : `EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"`, variables dans `.env` (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`).
- En développement : `EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"`.

### Effort estimé
Modéré. La plomberie est simple ; le vrai travail est la rédaction des gabarits et le test de délivrabilité (SPF, DKIM).

### Questions ouvertes
**DÉCISION SEREIN-GE REQUISE :**
1. Quel fournisseur SMTP ? (serveur interne Serein-GE, Gmail pro, SendGrid, Mailgun ?)
2. Pour quels événements envoyer un email (liste exhaustive) ?
3. Les candidats reçoivent-ils aussi des emails (portail E2) ou seulement les agents internes ?

---

## E5 — Gestion des conflits de planning (maîtres de stage)

### Fonctionnalité
Alerte si un maître de stage est déjà affecté à un stage EN_COURS ou A_VENIR au moment de constituer un nouveau stage.

### Analyse technique
- Dans `constituer_stage()` : requête `Stage.objects.filter(maitre_stage=maitre_stage, statut__in=["A_VENIR", "EN_COURS"]).exists()`.
- Comportement proposé : avertissement (pas blocage) — la Secrétaire peut confirmer quand même.
- Pattern identique à `AccorderView` pour le quota (afficher un avertissement + champ caché `confirmer_chevauchement`).

### Effort estimé
Faible. 1 demi-journée.

### Questions ouvertes
**DÉCISION SEREIN-GE REQUISE :**
1. Doit-on bloquer ou seulement avertir ?
2. Un maître peut-il encadrer plusieurs stagiaires en même temps ?

---

## E6 — Archivage et purge des données

### Fonctionnalité
Archivage automatique des candidatures et stages anciens (> N ans), avec export avant suppression.

### Analyse technique
- Commande `python manage.py archiver_donnees --annees 3`.
- Dépend de la politique de rétention RGPD de Serein-GE.
- Stratégie douce : marquage `archive=True` sur Candidature/Stage → filtre dans les listes. Pas de suppression physique.

### Questions ouvertes
**DÉCISION SEREIN-GE REQUISE (priorité)** :
1. Durée de rétention réglementaire au Burkina Faso ?
2. Politique RGPD locale applicable ?
3. Données à anonymiser vs. conserver vs. supprimer ?

---

## Priorité recommandée

| Lot E | Effort | Impact métier | Blocant RGPD ? | Recommandation |
|---|---|---|---|---|
| E1 — Tableau de bord Admin | Faible | Élevé | Non | **Priorité 1** |
| E5 — Conflits planning | Faible | Moyen | Non | **Priorité 2** |
| E4 — Notifications email | Modéré | Moyen | Non | Priorité 3 |
| E3 — Exports Excel | Modéré | Moyen | Non | Priorité 3 |
| E2 — Portail candidat | Élevé | Élevé | Décision requise | Priorité 4 |
| E6 — Archivage/purge | Modéré | Faible | **Oui** | Priorité selon avis juridique |

---

## Conclusion

Les fonctionnalités E1 et E5 sont les plus simples à implémenter et apporteraient une valeur immédiate. E2, E4 et E6 nécessitent des décisions métier et/ou techniques de Serein-GE avant d'être planifiées. E3 (export PDF) dépend de l'environnement de déploiement (Docker Linux simplifie considerablement weasyprint).
