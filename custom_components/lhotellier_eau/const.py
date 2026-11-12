"""Constantes de l'intégration L'Hotellier Eau."""
from datetime import timedelta

DOMAIN = "lhotellier_eau"
VERSION = "1.1.0-beta.2"
BASE_URL = "https://serviceclients.lhotellier-eau.fr/wp/"
UPDATE_INTERVAL = timedelta(hours=12)
MANUFACTURER = "L'Hotellier"

# Carte Lovelace fournie avec l'intégration (chargée automatiquement)
CARD_FILE = "frontend/lhotellier-eau-card.js"
CARD_URL = f"/{DOMAIN}/lhotellier-eau-card.js"
