"""
config.py — Configuration de l'application
==========================================
Charge les variables d'environnement depuis les fichiers env/* appropriés.

Environnements disponibles :
    dev  (défaut) — charge env/example puis env/dev
    prod          — charge env/example puis env/prod

Sélection de l'environnement :
    Variable d'environnement APP_ENV=prod  (shell ou .env)
    ou depuis le point d'entrée (app.py parse --env et pose os.environ["APP_ENV"])

Fichiers d'environnement :
    env/example  commité dans git — squelette des variables requises
    env/dev      ignoré par git   — valeurs réelles de développement
    env/prod     ignoré par git   — valeurs réelles de production

Ce module ne produit aucun effet de bord à l'import :
    - pas de parse CLI
    - pas de connexion réseau
    - pas de création de pool
"""
from dotenv import load_dotenv
import os

from core.app.env import is_prod, read_app_env
from core.security.csp import nonce_enabled as _csp_nonce_enabled

# ── Détection de l'environnement ───────────────────────────────────────────────

# Normalisée par le cœur (ENV-APP-ENV-NORMALISATION-001) : « Prod » et
# « prod » désignent le même environnement, et un blanc de bord ne doit pas
# faire charger un fichier env/ inexistant en silence.
APP_ENV = read_app_env()

# ── Chargement des variables d'environnement ───────────────────────────────────

load_dotenv("env/example")                   # valeurs par défaut (squelette)
load_dotenv(f"env/{APP_ENV}", override=True) # surcharge avec l'environnement choisi

# ── Variables de configuration ─────────────────────────────────────────────────

# Base de données : aucune configuration ici (ADR-060). Le cœur est agnostique
# BDD (ADR-054) et le backend installé lit lui-même ses variables (DB_APP_*,
# DB_ADMIN_*, DB_NAME, ...) directement dans l'environnement. Installez un
# backend (forge-mvc-sqlite, forge-mvc-mariadb, ...) et renseignez ses variables
# dans env/dev selon sa documentation.

APP_NAME          = os.getenv("APP_NAME",          "Forge")
APP_ROUTES_MODULE = os.getenv("APP_ROUTES_MODULE", "mvc.routes")
VIEWS_DIR         = os.getenv("VIEWS_DIR",         "mvc/views")
SQL_DIR           = os.getenv("SQL_DIR",           "mvc/models/sql")

# Dossier, sous VIEWS_DIR, où vivent les vues de l'application (à la main ou
# générées par make:crud), à côté de public/ ; les dossiers du cadre (layouts,
# components, ...) restent à la racine (ADR-073). "app" par défaut : vos vues
# vont dans mvc/views/app/<entite>/ et vos contrôleurs rendent "app/<entite>/...".
# Mettez "" pour ranger à plat (mvc/views/<entite>/), disposition historique.
APP_VIEWS_NAMESPACE = os.getenv("APP_VIEWS_NAMESPACE", "app")

# Upload : le noyau ne garde que le plafond de corps multipart (ADR-032).
# UPLOAD_ROOT, UPLOAD_ALLOWED_EXTENSIONS, UPLOAD_ALLOWED_MIME_TYPES sont lues par
# l'opt-in forge-mvc-files depuis l'environnement ; ajoutez-les à env/dev au besoin.
UPLOAD_MAX_SIZE   = int(os.getenv("UPLOAD_MAX_SIZE", 5 * 1024 * 1024))

# Mail : aucune configuration ici. Le mail est un opt-in (forge-mvc-mail,
# ADR-031) qui lit ses variables MAIL_* directement depuis l'environnement.
# Installez forge-mvc-mail et ajoutez le bloc MAIL_* à env/dev pour l'activer.

APP_HOST          = os.getenv("APP_HOST", "127.0.0.1")
APP_PORT          = int(os.getenv("APP_PORT", 8000))
_ssl_default      = "false" if is_prod(APP_ENV) else "true"
APP_SSL_ENABLED   = os.getenv("APP_SSL_ENABLED", _ssl_default).strip().lower() in {
    "1", "true", "yes", "on"
}
SSL_CERTFILE      = os.getenv("SSL_CERTFILE", "cert.pem")
SSL_KEYFILE       = os.getenv("SSL_KEYFILE", "key.pem")
# La règle de lecture vit dans `core.security.csp`, pour que le serveur de
# développement et l'adaptateur WSGI répondent identiquement (principe 11).
# Elle était écrite ici en double : les deux jeux de valeurs coïncidaient, mais
# rien ne les y obligeait (CORE-WSGI-CSP-NONCE-001).
APP_CSP_NONCE_ENABLED = _csp_nonce_enabled()

# Reverse proxy — IPs des proxies de confiance autorisés à fournir X-Real-IP.
# Liste séparée par virgules, espaces tolérés. Vide par défaut : Forge ignore
# alors complètement X-Real-IP (HTTP-TRUSTED-PROXY-IP-001).
APP_TRUSTED_PROXIES = frozenset(
    p.strip() for p in os.getenv("APP_TRUSTED_PROXIES", "").split(",") if p.strip()
)
