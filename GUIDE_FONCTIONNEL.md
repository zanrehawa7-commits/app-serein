# Guide fonctionnel — Stage Track (Serein-GE)

Ce document explique la logique de l'application, le rôle de chaque acteur, et comment vérifier que chaque fonctionnalité marche correctement.

---

## Vue d'ensemble du cycle

L'application gère le cycle complet d'un stage en entreprise :

```
Responsable exprime un besoin
        ↓
Secrétaire crée une offre et la publie
        ↓
Secrétaire reçoit et enregistre les candidatures
        ↓
Responsable examine et prend une décision
        ↓
Secrétaire informe le candidat de la décision
```

---

## Les 3 rôles

### Administrateur
- Gère les utilisateurs (créer, modifier, activer/désactiver, réinitialiser le mot de passe)
- Gère les référentiels : départements, membres, établissements, types de stage, canaux de publication
- Gère les permissions de chaque rôle
- **Lecture seule** sur les offres et les candidatures (il supervise, il ne saisit pas)

### Secrétaire
- Reçoit les candidatures physiques et les saisit dans le système
- Recherche si le candidat existe déjà avant de créer un nouveau profil
- Gère les pièces jointes (CV, lettre de motivation, etc.)
- Crée et publie les offres de stage
- Informe les candidats des décisions prises par le Responsable

### Responsable
- Exprime des besoins en stage pour son département
- Consulte les candidatures reçues pour son département uniquement
- Prend les décisions : présélectionner, planifier un entretien, accorder ou refuser
- Peut rediriger une candidature vers un autre département si elle ne correspond pas

---

## Scénarios de test complets

### Préparation (à faire une seule fois)

1. Lancer le serveur : `cd backend && python manage.py runserver`
2. Aller sur `http://127.0.0.1:8000/login/`

---

### Scénario 1 — Gestion des utilisateurs (Administrateur)

**Connexion :** `admin@serein.bf` / `Admin1234!`

**Ce qu'il faut vérifier :**

1. **Créer un utilisateur** → Menu Utilisateurs → Nouveau  
   - Remplir email, prénom, nom, choisir le rôle "Secrétaire"  
   - Vérifier que le compte apparaît dans la liste

2. **Changer le mot de passe** d'un utilisateur → Détail → Réinitialiser le mot de passe  
   - Le mot de passe doit changer sans connaître l'ancien

3. **Désactiver un utilisateur** → Détail → Désactiver  
   - L'utilisateur ne peut plus se connecter  
   - Un administrateur ne peut pas se désactiver lui-même

4. **Gérer les permissions d'un rôle** → Menu Rôles & Permissions  
   - Cocher/décocher des permissions pour la Secrétaire ou le Responsable  
   - Les cases du rôle Administrateur sur les comptes sont grises (non modifiables)

---

### Scénario 2 — Référentiels (Administrateur)

**Connexion :** `admin@serein.bf` / `Admin1234!`

**Ce qu'il faut vérifier :**

1. **Créer un département** → Menu Référentiels → Départements → Nouveau  
   - Exemple : "Comptabilité"

2. **Ajouter un membre** → Détail du département → Ajouter un membre  
   - Exemple : "Koné Ibrahim"

3. **Désigner un responsable** → Modifier le département → choisir le responsable  
   - Le responsable doit être un membre actif de ce département

4. **Créer un établissement** → Référentiels → Établissements → Nouveau  
   - Basculer le statut partenaire avec le bouton dédié

5. **Supprimer un référentiel utilisé** → doit être bloqué (message d'avertissement)

---

### Scénario 3 — Besoins et offres

**Connexion Responsable :** `resp@serein.bf` / `Resp1234!`

**Étape A — Exprimer un besoin :**
1. Menu → Mes besoins → Nouveau besoin
2. Remplir : type de stage, dates, nombre de places, description du profil
3. Soumettre → le besoin passe au statut **Envoyé**
4. La Secrétaire reçoit une notification

**Connexion Secrétaire :** `sec@serein.bf` / `Sec1234!`

**Étape B — Créer une offre depuis le besoin :**
1. Menu → Besoins → cliquer sur le besoin "Envoyé"
2. Bouton "Créer une offre" → remplir le formulaire
3. L'offre est en **Brouillon** — le besoin passe à **Pris en charge**

**Étape C — Publier l'offre :**
1. Menu → Offres → cliquer sur l'offre
2. Bouton "Ouvrir" → l'offre est **Ouverte** et visible pour les candidatures

> **Règle importante :** un besoin ne peut être lié qu'à une seule offre.  
> Si le Responsable annule un besoin déjà pris en charge, la Secrétaire est notifiée.

---

### Scénario 4 — Enregistrer une candidature (Secrétaire)

**Connexion :** `sec@serein.bf` / `Sec1234!`

1. Menu → Candidatures → Nouvelle candidature  
2. **Rechercher le candidat** par nom, prénom, téléphone ou email  
   - Si trouvé → cliquer "Créer une candidature pour ce candidat"  
   - Si non trouvé → bouton "Nouveau candidat"

3. **Créer le candidat** (si nouveau) :  
   - Nom, prénom, téléphone (8 chiffres burkinabè)  
   - Niveau d'études, filière, établissement  
   - Si l'établissement n'est pas dans la liste → choisir "Autre" et saisir le nom

4. **Créer la candidature** :  
   - Département, type de stage, type de demande  
   - **Spontanée** = le candidat se présente seul, pas d'offre à choisir  
   - **Suite à une offre** = le candidat répond à une offre publiée, l'offre est obligatoire  
   - Dates de disponibilité + durée souhaitée  
   - Ajouter au moins **un CV** (PDF, JPG ou PNG, max 5 Mo)

5. La candidature est créée avec le statut **Reçue**  
   Le Responsable du département reçoit une notification

> **Règles importantes :**  
> - Un candidat ne peut avoir qu'une seule candidature active à la fois (Reçue ou En traitement)  
> - Les pièces jointes ne sont pas accessibles via une URL directe — tout passe par le bouton de téléchargement sécurisé

---

### Scénario 5 — Traiter une candidature (Responsable)

**Connexion :** `resp@serein.bf` / `Resp1234!`

Le Responsable voit uniquement les candidatures de **son département**.

**Tableau de bord :** 4 compteurs (Reçues / En traitement / Accordées / Refusées) + les 5 dernières reçues.

**Menu latéral :** liens directs vers chaque statut.

#### Action 1 — Présélectionner (statut Reçue → En traitement)
1. Cliquer sur une candidature "Reçue"
2. Dans le panel "Actions — Responsable" → saisir un commentaire (optionnel)
3. Cliquer "Présélectionner"
4. La Secrétaire reçoit une notification : "Candidat à informer"

#### Action 2 — Planifier un entretien (statut En traitement)
1. Cliquer sur une candidature "En traitement"
2. Choisir une date et heure **dans le futur**
3. Cliquer "Planifier"
4. La Secrétaire reçoit un message : "Entretien planifié le JJ/MM/AAAA à HH:MM pour CAND-XXXX : prévenir le candidat"

#### Action 3 — Accorder le stage (statut En traitement → Accordée)
1. Cliquer "Accorder le stage"
2. Ajouter un commentaire (optionnel) → Confirmer
3. **Si l'offre liée est à quota plein** → message d'avertissement apparaît  
   Cliquer "Confirmer malgré tout" pour dépasser le quota
4. La Secrétaire est notifiée : "Candidat à informer"

#### Action 4 — Refuser (statut Reçue ou En traitement → Refusée)
1. Cliquer "Refuser"
2. Choisir un motif dans la liste
3. Si motif = **"Autre"** → un champ de précision apparaît automatiquement (obligatoire)
4. Confirmer → La Secrétaire est notifiée

#### Action 5 — Rediriger (statut Reçue uniquement)
1. Cliquer "Rediriger vers un autre département"
2. Choisir le nouveau département (le département actuel n'est pas proposé)
3. Saisir le motif → Confirmer
4. La candidature disparaît de la liste du Responsable actuel
5. Le Responsable du nouveau département est notifié  
   Si le nouveau département n'a pas de responsable → les Administrateurs sont notifiés

---

### Scénario 6 — Informer le candidat (Secrétaire)

**Connexion :** `sec@serein.bf` / `Sec1234!`

Après chaque décision du Responsable, la Secrétaire doit contacter le candidat par téléphone ou email, puis marquer la candidature comme "informée" dans le système.

1. Menu → Candidats à informer  
   La liste affiche toutes les candidatures **Accordées ou Refusées** dont le candidat n'a pas encore été informé

2. Les colonnes affichent :
   - Téléphone du candidat (pour l'appeler directement)
   - Décision (Accordée / Refusée)
   - Motif de refus (si applicable)
   - Date de l'entretien (si planifié)

3. Cliquer "Marquer informé" → la ligne disparaît de la liste

---

## Règles métier importantes à connaître

| Règle | Description |
|---|---|
| **Un candidat = une candidature active** | Impossible d'enregistrer une 2e candidature si une est déjà en cours (Reçue ou En traitement) |
| **Offre obligatoire si Suite à une offre** | Le champ offre est obligatoire si type = "Suite à une offre", interdit si "Spontanée" |
| **Pièces jointes sécurisées** | Les fichiers ne sont jamais accessibles par une URL directe |
| **Formats acceptés** | PDF, JPG, JPEG, PNG — taille max 5 Mo |
| **Quota d'offre** | Le Responsable peut dépasser le quota, mais doit confirmer explicitement |
| **Département du Responsable** | Il ne voit que les candidatures de son département |
| **Référentiel protégé** | Un département ou établissement utilisé ne peut pas être supprimé |
| **Rôle et membre** | Un Responsable doit être lié à un membre d'un département |
| **Maître de stage = même département** | Le maître de stage doit appartenir au département de la candidature |
| **Statut auto du stage** | Si date de début ≤ aujourd'hui → En cours, sinon À venir |
| **Terminer = date passée** | La date de fin réelle ne peut pas être dans le futur |
| **Interrompre = motif obligatoire** | L'interruption est irréversible et nécessite un motif |
| **Maître de stage actif** | Impossible de désactiver un membre qui encadre un stage en cours |

---

## Notifications — qui reçoit quoi

| Événement | Destinataires |
|---|---|
| Nouvelle candidature reçue | Responsable du département (ou Admins si absent) |
| Présélection | Secrétaires |
| Entretien planifié | Secrétaires ("prévenir le candidat") |
| Stage accordé | Secrétaires |
| Candidature refusée | Secrétaires |
| Candidature redirigée | Responsable du nouveau département (ou Admins) + Secrétaires |

Les notifications apparaissent dans la cloche en haut à droite. Les 5 dernières sont visibles directement, un lien permet de voir toutes les notifications.

---

## Scénario 7 — Constituer et suivre un stage (Secrétaire + Responsable)

### Qu'est-ce que "constituer un stage" ?

Quand le Responsable accorde une candidature, cela signifie qu'il accepte le candidat en principe. Mais l'accord seul ne suffit pas : il faut encore **formaliser le stage** dans le système en précisant les dates et l'encadrant. C'est cette étape qu'on appelle "constituer le stage".

```
Candidature ACCORDÉE (décision du Responsable)
        ↓
Secrétaire constitue le stage
→ saisit la date de début, la date de fin prévue, le maître de stage
        ↓
Stage créé → statut "À venir" ou "En cours"
        ↓
Stagiaire informé, suivi dans le système
```

Tant que le stage n'est pas constitué, un badge `!` orange apparaît dans la liste des candidatures accordées pour rappeler à la Secrétaire qu'il reste quelque chose à faire.

### Prérequis
- Une candidature au statut **Accordée** existe.
- Le département concerné a au moins un membre actif (futur maître de stage).

### Constituer le stage (Secrétaire)

**Connexion :** `sec@serein.bf`

1. Menu → Candidatures → ouvrir la candidature accordée
2. Bouton vert **"Constituer le stage"** en haut à droite  
   *(remplacé par "Voir le stage" si un stage existe déjà)*
3. Renseigner :
   - **Date de début** du stage
   - **Date de fin prévue**
   - **Maître de stage** (liste filtrée aux membres actifs du département)
4. Valider → le stage est créé automatiquement avec :
   - Statut **À venir** si la date de début est dans le futur
   - Statut **En cours** si la date de début est aujourd'hui ou passée
5. Les Secrétaires reçoivent une notification → informer le stagiaire de sa date de début

### Vérifier dans la liste (Menu → Stages)
- Onglets : À venir / En cours / Terminés / Interrompus
- Filtres disponibles : recherche par nom, dates, type de stage, département
- Un stage accordé sans stage constitué affiche un badge `!` orange dans la liste des candidatures

### Modifier le stage (Secrétaire)
1. Ouvrir le détail du stage → bouton "Modifier"
2. Date de début modifiable seulement si statut A_VENIR
3. Maître de stage et date de fin toujours modifiables (si A_VENIR ou EN_COURS)

### Terminer un stage (Responsable)
**Connexion :** `resp@serein.bf`

1. Menu → Stages → En cours → ouvrir le stage
2. Bouton "Terminer" → saisir la date de fin réelle (≤ aujourd'hui)
3. Le stage passe au statut **Terminé**
4. Les Secrétaires reçoivent une notification

### Interrompre un stage (Responsable)
1. Ouvrir un stage À venir ou En cours
2. Bouton "Interrompre" → saisir la date et le motif (obligatoire)
3. Le stage passe au statut **Interrompu** (irréversible)

---

## Commande automatique — Mise à jour des stages

La commande suivante doit être planifiée quotidiennement (par exemple via cron) :

```bash
cd backend && python manage.py mettre_a_jour_stages
```

**Ce qu'elle fait :**
1. Passe en **En cours** tous les stages À venir dont la date de début est atteinte
2. Passe en **Terminé** tous les stages En cours dont la date de fin prévue est dépassée

**Simuler une date passée** (utile si le serveur a été éteint plusieurs jours) :
```bash
python manage.py mettre_a_jour_stages --date 2025-06-01
```

La commande est **idempotente** — relancer plusieurs fois n'a aucun effet négatif.

---

## Règles métier importantes — Étape 8

| Règle | Description |
|---|---|
| **Maître de stage = même département** | Le maître de stage doit appartenir au département de la candidature |
| **Statut auto à la constitution** | Si date_debut ≤ aujourd'hui → EN_COURS, sinon A_VENIR |
| **Terminer = date réelle ≤ aujourd'hui** | Impossible de saisir une date future |
| **Interrompre = motif obligatoire** | Le motif d'interruption est requis |
| **Maître de stage actif** | Impossible de désactiver un membre maître de stage d'un stage A_VENIR ou EN_COURS (changer d'abord le maître) |

---

## Notifications — Étape 8

| Événement | Destinataires |
|---|---|
| Stage constitué | Secrétaires ("informer le stagiaire de la date de début") |
| Stage terminé manuellement | Secrétaires |
| Stage interrompu | Secrétaires |
| Stage terminé automatiquement | Responsable du département ("à évaluer") |
