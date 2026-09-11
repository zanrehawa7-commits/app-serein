FROM python:3.12-slim

# Variables d'environnement Python Python ne mette pas en cache les sorties
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Dépendances système
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Créez un répertoire de travail pour l'application    
WORKDIR /app

# Installation des dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copie du code source    
COPY . .

# Port exposé pour l'application
EXPOSE 8000

# Commande de démarrage de l'application
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]