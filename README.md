# Serein-GE — Application de gestion des stages

Application web Django pour la gestion complète du cycle de stage chez **Serein-GE** :
besoins → offres → candidatures → stages → suivi.

---

## Stack technique

| Composant | Version |
|---|---|
| Python | 3.12 |
| Django | 5.x |
| Base de données | PostgreSQL |
| Frontend | Bootstrap 5 + Bootstrap Icons |
| Formulaires | django-crispy-forms + crispy-bootstrap5 |
| API future | Django REST Framework + SimpleJWT |
| Variables d'env | python-decouple |

---

## Prérequis

- Python 3.12+
- PostgreSQL (base `serein_db` créée)
- Git

---

## Installation

### 1. Cloner le projet

```bash
git clone <url-du-repo>
cd app-serein
```

### 2. Créer et activer l'environnement virtuel

```powershell
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python -m venv .venv
source .venv/bin/activate
```

### 3. Installer les dépendances

```bash
pip install -r backend/requirements.txt
```

### 4. Configurer les variables d'environnement

Copier le fichier exemple et remplir les valeurs :

```bash
cp .env.example .env
```

Contenu du `.env` à remplir :

```env
SECRET_KEY=une-cle-secrete-longue-et-aleatoire
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

DB_NAME=serein_db
DB_USER=postgres
DB_PASSWORD=ton_mot_de_passe
DB_HOST=localhost
DB_PORT=5432
```

> Le `.env` doit être placé à la racine du projet (`app-serein/`), au même niveau que `backend/`.

### 5. Appliquer les migrations

```bash
cd backend
python manage.py migrate
```

### 6. Charger les données de base

Crée les groupes (`Administrateur`, `Secrétaire`, `Responsable`), leurs permissions et les types de stage :

```bash
python manage.py init_donnees
```

### 7. Créer les comptes de démonstration

```bash
python manage.py init_demo
```

### 8. Lancer le serveur

```bash
python manage.py runserver
```

L'application est accessible sur : **http://127.0.0.1:8000/**

---

## Comptes de démonstration

Se connecter sur `http://127.0.0.1:8000/login/`

| Rôle | Email | Mot de passe |
|---|---|---|
| Administrateur | `admin@serein.bf` | `Admin1234!` |
| Secrétaire | `sec@serein.bf` | `Sec1234!` |
| Responsable | `resp@serein.bf` | `Resp1234!` |

> Le Responsable est rattaché au département **Informatique**.

---

## Structure du projet

```
app-serein/
├── .env                    # Variables d'environnement (ne pas commiter)
├── .env.example            # Modèle de configuration
├── backend/
│   ├── config/             # Settings, URLs, WSGI
│   ├── comptes/            # Utilisateurs, rôles, authentification
│   ├── referentiels/       # Départements, membres, établissements, types de stage
│   ├── offres/             # Besoins, offres, publications
│   ├── candidatures/       # Candidats, candidatures, pièces jointes
│   ├── stages/             # Stages (étape 7+)
│   ├── suivi/              # Historique, notifications
│   ├── commun/             # Mixins, services partagés, templates communs
│   ├── templates/          # Templates HTML
│   ├── static/             # Fichiers statiques (CSS, JS)
│   ├── media/              # Fichiers médias publics
│   └── fichiers_prives/    # Pièces jointes (accès protégé, hors /media/)
└── README.md
```

---

## Modules de l'application

| Module | Fonctionnalités |
|---|---|
| **Référentiels** | Gestion des départements, membres, établissements, types de stage, canaux de publication |
| **Utilisateurs** | Création de comptes, attribution de rôles, gestion des permissions par rôle |
| **Offres** | Expression de besoins (Responsable), création et publication d'offres (Secrétaire) |
| **Candidatures** | Recherche de candidats, saisie de candidatures, gestion des pièces jointes sécurisées |
| **Suivi** | Historique des transitions, notifications en temps réel |

---

## Rôles et accès

| Rôle | Accès |
|---|---|
| **Administrateur** | Vue d'ensemble, gestion des utilisateurs et référentiels, lecture seule sur offres/candidatures |
| **Secrétaire** | Gestion complète des candidatures, création d'offres, traitement des besoins |
| **Responsable** | Expression de besoins, lecture des offres et candidatures de son département |

---

## Commandes utiles

```bash
# Recharger les permissions des groupes
python manage.py init_donnees

# Recréer les comptes de démo (idempotent)
python manage.py init_demo

# Lancer les tests
python manage.py test

# Créer un superutilisateur personnalisé
python manage.py createsuperuser

# Générer les fichiers statiques (production)
python manage.py collectstatic
```

---

## Sécurité des fichiers

Les pièces jointes des candidatures sont stockées dans `backend/fichiers_prives/`, en dehors du dossier `media/` public. Elles ne sont **jamais** accessibles via une URL directe `/media/`. Tout téléchargement passe par une vue Django sécurisée qui vérifie les droits de l'utilisateur.

En production avec Nginx, configurer une location interne :

```nginx
location /protected/ {
    internal;
    alias /chemin/vers/fichiers_prives/;
}
```

---

## Déploiement (Docker)

Un fichier `docker-compose.yml` est prévu. Consulter la documentation de déploiement séparée.
