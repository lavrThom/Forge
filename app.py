"""
app.py - Point d'entrée — Forge 1.0.0-rc.9
======================================
Serveur HTTP/HTTPS multi-thread pur Python basé sur http.server.
Le chiffrement SSL est activé via APP_SSL_ENABLED pour le développement local.
En production derrière Nginx, Forge écoute en HTTP local et Nginx termine TLS.

Responsabilités :
    - Démarrer le serveur HTTP/HTTPS
    - Recevoir chaque requête entrante
    - Encapsuler la requête dans un objet Request
    - Déléguer le traitement via Application.dispatch()
    - Retourner la réponse via un objet Response
    - Servir les fichiers statiques (CSS, JS, images, polices)

Ce fichier ne contient aucune logique métier.
La gestion de l'authentification (login, logout, protection des routes) est
entièrement du ressort de l'application : voir mvc/controllers/auth_controller.py.
Le framework fournit uniquement les outils (sessions, CSRF, hashing, décorateurs).

Les routes sont déclarées dans le package mvc/routes/ (un fichier par contrôleur,
branchés dans mvc/routes/__init__.py — ADR-068).
La configuration (hôte, port, certificats) est dans config.py.
Les classes Request et Response sont dans core/http/request.py
et core/http/response.py.

Flux simplifié :

    Navigateur HTTPS ou reverse proxy local
        → RequestHandler
        → Request
        → vérification route / session / CSRF
        → ROUTES[(method, path)]
        → contrôleur (+ décorateurs @require_auth / @require_role)
        → Response
        → navigateur

Remarques :
    - Une route non publique exige une session authentifiée
    - Une route unsafe exige un token CSRF sauf exemption explicite
    - Les routes /login et /logout restent publiques mais protégées par CSRF
    - Les permissions fines par rôle sont appliquées via @require_role dans
      les contrôleurs, pas dans ce handler

Prérequis — Génération du certificat SSL auto-signé (à faire une seule fois) :

    openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"

    req -x509        : génère un certificat auto-signé
    -newkey rsa:2048 : crée une clé privée RSA de 2048 bits
    -keyout key.pem  : enregistre la clé privée dans key.pem
    -out cert.pem    : enregistre le certificat dans cert.pem
    -days 365        : valide 1 an
    -nodes           : pas de mot de passe sur la clé
    -subj "/CN=localhost" : nom du serveur

    Le navigateur affichera un avertissement de sécurité car le certificat
    n'est pas émis par une autorité reconnue. Cliquer sur "Avancer quand même".

Démarrage :
    python3 app.py              → mode dev (défaut, HTTPS local)
    python3 app.py --env prod   → mode prod (HTTP local par défaut)
"""
import argparse as _argparse
import errno as _errno
import os as _os
import sys as _sys
from typing import Any

# ── Détection de l'environnement avant tout import de config ──────────────────
# L'argument --env est parsé ici, point d'entrée unique de la CLI, et AVANT
# l'import de config.py qui lit ensuite os.environ["APP_ENV"].
#
# Le garde `__name__ == "__main__"` n'est pas décoratif. Ce fichier est aussi
# IMPORTÉ par wsgi.py en production, et sys.argv est alors celui de Gunicorn :
# --env y est absent, le défaut vaudrait "dev", et `setdefault` poserait
# APP_ENV=dev sur un serveur de production dès que l'environnement du processus
# ne la déclare pas lui-même. Les pages d'erreur rendraient alors leur
# traceback au visiteur.
#
# Sous le garde, l'import ne décide de rien : APP_ENV vient de l'environnement,
# et de lui seul.
if __name__ == "__main__":
    _p = _argparse.ArgumentParser(add_help=False)
    _p.add_argument("--env", choices=["dev", "prod"], default="dev")
    _os.environ.setdefault("APP_ENV", _p.parse_known_args()[0].env)

import logging
import mimetypes
import socket
import ssl
import traceback
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
# Seules les valeurs dont CE fichier a besoin : le serveur de développement et
# ses pages d'erreur. Tout ce qui configure l'application est lu par la fabrique.
from config import (APP_HOST, APP_PORT, APP_SSL_ENABLED, SSL_CERTFILE, SSL_KEYFILE,
                    APP_ENV, APP_CSP_NONCE_ENABLED)
import core.security.csp as _csp
from core.security.headers import apply_security_headers, assert_emitted_headers_are_safe
import core.forge as forge
from core.app.dev_server import (
    format_port_in_use_message,
    format_prod_host_guard_error,
    format_startup_messages,
    should_block_prod_public_host,
)
# La configuration Forge, le renderer Jinja et les routes sont posés par
# `build_application()` (plus bas), qui lit config.py. Les refaire ici
# rouvrirait la porte que l'ADR-093 ferme : deux séquences de construction pour
# une seule application, et la divergence qui vient avec.
from core.http.health import health_response, is_health_request
from core.http.media import media_response
from core.http.request import Request, RequestEntityTooLarge
from core.http.response import Response
from core.http.helpers import error_page as _error_page
from core.app.app_factory import build_application
# CORE-DROP-UPLOADS-001 (ADR-019) : le service de fichiers est un opt-in
# (forge-mvc-files). Import lazy dans le handler /media (l'app démarre sans).
# L'application est construite par la fabrique du cœur, qui lit config.py, les
# routes, puis VOTRE câblage dans bootstrap.py (ADR-093).
#
# Ce fichier ne construit plus l'Application lui-même, et c'est le sujet. Le
# câblage vivait ici, où la fabrique WSGI ne le lisait pas : la production
# servait alors une application privée de ses gardes, sans rien dire (ADR-092).
# Une seule séquence de construction, donc plus aucune divergence possible.
#
# Vos middlewares et votre magasin de sessions se câblent dans bootstrap.py.
#
# `application` porte un nom PUBLIC : c'est ce que wsgi.py sert en production.
# Ne pas le renommer.
application = build_application()

logger = logging.getLogger(__name__)

# ── Fichiers statiques ─────────────────────────────────────────────────────────

STATIC_DIR    = _os.path.realpath(_os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "static"))
STATIC_TYPES  = {"css": "text/css", "js": "application/javascript", "svg": "image/svg+xml",
                 "png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg",
                 "ico": "image/x-icon", "woff2": "font/woff2", "woff": "font/woff"}
# 1h en dev (rechargement facile), 7 jours en prod (fichiers versionnés)
STATIC_CACHE  = "max-age=3600" if APP_ENV == "dev" else "max-age=604800, immutable"


def _is_safe_static_path(static_dir: str, filepath: str) -> bool:
    """Vérifie via commonpath que filepath est strictement sous static_dir."""
    try:
        return _os.path.commonpath([static_dir, filepath]) == static_dir
    except ValueError:
        return False


def _error_context() -> "dict[str, Any] | None":
    """Contexte de la page 500 : détail de l'exception en cours.

    Uniquement en développement (APP_ENV == "dev") : type, message et traceback
    de l'exception sont passés au template `errors/500.html` (bloc `{% if error %}`).
    En production, renvoie None — aucune fuite de traceback côté client.
    """
    if APP_ENV != "dev":
        return None
    exc_type, exc, _tb = _sys.exc_info()
    if exc is None:
        return None
    return {
        "error": {
            "type": exc_type.__name__ if exc_type else "Exception",
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    }


def _dev_error(detail: "dict[str, Any]") -> "dict[str, Any] | None":
    """Détail d'erreur passé aux pages 404 / 413, uniquement en développement.

    En production (APP_ENV != "dev"), renvoie None : la page d'erreur reste
    neutre, sans information interne (chemin demandé, taille reçue…).
    """
    return {"error": detail} if APP_ENV == "dev" else None


class RequestHandler(BaseHTTPRequestHandler):
    """
    Routeur/dispatcher des requêtes HTTP.

    Chaque requête entrante crée une instance de cette classe dans son propre thread.
    Elle encapsule la requête dans un objet Request, recherche le contrôleur
    correspondant dans ROUTES et lui délègue le traitement.

    Le contrôle d'accès ici est volontairement minimal :
        - si le chemin est public, la requête est dispatchée normalement
        - sinon, une session authentifiée est requise
    Les vérifications CSRF et de rôles sont traitées dans l'application et les
    contrôleurs, pas dans ce handler.

    Elle ne contient aucune logique métier.
    """

    def do_GET(self):
        """Traite les requêtes HTTP GET."""
        with _csp.request_nonce(_csp.generate_nonce() if APP_CSP_NONCE_ENABLED else None):
            try:
                request = Request(self)
                if is_health_request(request.path):
                    self._send_response(health_response())
                    return
                if request.path == "/favicon.ico":
                    self._serve_static("/static/favicon.ico")
                    return
                if request.path.startswith("/static"):
                    self._serve_static(request.path)
                    return
                if request.path.startswith("/media/"):
                    self._serve_media(request.path, request)
                    return
                self._send_response(self._dispatch(request))
            except Exception:
                logger.exception("Erreur GET %s", self.path)
                self._send_response(_error_page("errors/500.html", 500, _error_context()))

    def do_POST(self):
        """Traite les requêtes HTTP POST."""
        self._handle_dynamic_request("POST")

    def do_PUT(self):
        """Traite les requêtes HTTP PUT."""
        self._handle_dynamic_request("PUT")

    def do_PATCH(self):
        """Traite les requêtes HTTP PATCH."""
        self._handle_dynamic_request("PATCH")

    def do_DELETE(self):
        """Traite les requêtes HTTP DELETE."""
        self._handle_dynamic_request("DELETE")

    def _handle_dynamic_request(self, label: str):
        """Traite une requête applicative non statique."""
        with _csp.request_nonce(_csp.generate_nonce() if APP_CSP_NONCE_ENABLED else None):
            try:
                request = Request(self)
                self._send_response(self._dispatch(request))
            except RequestEntityTooLarge as exc:
                received = exc.args[0] if exc.args else None
                self._send_response(_error_page("errors/413.html", 413, _dev_error({"received": received})))
            except Exception:
                logger.exception("Erreur %s %s", label, self.path)
                self._send_response(_error_page("errors/500.html", 500, _error_context()))

    def _dispatch(self, request: Request) -> Response:
        """Délègue le routage et le contrôle d'accès à l'Application.

        Le nonce CSP est posé en amont par `request_nonce(...)` dans les handlers
        (cycle de vie thread-local nettoyé en `finally`), conformément au contrat
        de `core/security/csp.py`.
        """
        return application.dispatch(request)

    def _send_response(self, response: Response) -> None:
        """Envoie un objet Response au navigateur avec les headers de sécurité.

        Les headers de sécurité Forge (X-Frame-Options, CSP, etc.) sont posés
        en `setdefault` via `core.security.headers.apply_security_headers` —
        une route applicative qui définit explicitement un de ces headers
        garde la main. Voir `WSGI-SECURITY-HEADERS-001`.
        """
        # Corps : soit un itérable de streaming (Response.file → Range/206,
        # CORE-HTTP-FILE-RANGE-001), soit le `body` bytes habituel. Même contrat
        # que le chemin WSGI (`core/app/wsgi.py`) : dans le cas streaming,
        # `Content-Length` vient de `response.content_length`, taille de la
        # tranche servie, et non de `len(body)` qui vaut alors zéro.
        stream = getattr(response, "stream", None)
        content_length = (
            (getattr(response, "content_length", None) or 0)
            if stream is not None else
            len(response.body)
        )

        # Couche de défense partagée avec le chemin WSGI : un seul helper,
        # un seul contrat. `include_hsts=True` : le serveur de dev sait quand
        # il sert TLS via APP_SSL_ENABLED ; HSTS sur HTTP local est inoffensif.
        headers_out: dict[str, str] = {str(k): str(v) for k, v in response.headers.items()}
        # `Cache-Control: no-store` vient désormais du drapeau `no_store` de la
        # route, honoré par `Application.dispatch`, donc par les DEUX serveurs
        # (NO-STORE-ROUTE-FLAG-001). La liste de chemins qui vivait ici ne
        # valait que pour le serveur de développement : la production servait
        # `/login` sans l'en-tête.
        apply_security_headers(
            headers_out,
            include_hsts=True,
            csp=_csp.build_csp_header(_csp.get_request_nonce()),
        )

        # La liste exacte que ce serveur va émettre, dans l'ordre où il l'émet.
        entetes_emis: list[tuple[str, str]] = [
            ("Content-Type", str(response.content_type)),
            ("Content-Length", str(content_length)),
        ]
        entetes_emis.extend((str(k), str(v)) for k, v in headers_out.items())
        # Cookies additionnels : une ligne Set-Cookie par cookie accumulé via
        # response.add_cookie (CORE-RESPONSE-MULTI-COOKIE-001).
        entetes_emis.extend(
            ("Set-Cookie", str(cookie))
            for cookie in getattr(response, "set_cookies", [])
        )

        # CORE-HEADER-CRLF-001 puis CORE-HEADER-CRLF-COMPLETUDE-001 : contrôle
        # AVANT la première ligne. Ce serveur émet ses en-têtes un par un ; une
        # fois `send_response` appelé, il est trop tard pour refuser.
        #
        # Le contrôle portait sur un dictionnaire reconstruit à la main, qui
        # reprenait les en-têtes applicatifs et les cookies mais **pas**
        # `Content-Type`. Un `content_type` porteur d'un saut de ligne partait
        # donc sans être vu. Contrôler la liste réellement émise supprime la
        # question de savoir ce qu'on a pensé à y remettre.
        assert_emitted_headers_are_safe(entetes_emis)

        self.send_response(response.status)
        for key, value in entetes_emis:
            self.send_header(key, value)
        self.end_headers()
        if stream is None:
            self.wfile.write(response.body)
            return
        try:
            for chunk in stream:
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            # Le client a coupé en cours de téléchargement (lecteur vidéo qui
            # saute, onglet fermé). Les en-têtes sont déjà partis : il n'y a
            # plus de réponse d'erreur à envoyer, seulement une trace.
            logger.info("Client déconnecté pendant l'envoi de %s", self.path)

    def _serve_static(self, path: str) -> None:
        """
        Sert un fichier statique (CSS, JS, SVG, PNG, JPG, ICO, WOFF/WOFF2).

        Sécurité — Protection contre le Path Traversal :
            os.path.realpath() résout le chemin absolu réel ; commonpath()
            vérifie que le fichier est strictement sous static/. Sinon → 403.
        """
        filepath = _os.path.realpath(_os.path.join(STATIC_DIR, path.removeprefix("/static/")))

        if not _is_safe_static_path(STATIC_DIR, filepath):
            self._send_response(_error_page("errors/403.html", 403))
            return

        if not _os.path.isfile(filepath):
            self._send_response(_error_page("errors/404.html", 404, _dev_error({"path": path})))
            return

        try:
            with open(filepath, "rb") as file:
                content = file.read()
            ext          = path.split(".")[-1].lower()
            content_type = STATIC_TYPES.get(ext) or mimetypes.guess_type(filepath)[0] or "application/octet-stream"
            self._send_response(Response(200, content, content_type,
                                         headers={"Cache-Control": STATIC_CACHE}))
        except FileNotFoundError:
            self._send_response(_error_page("errors/404.html", 404, _dev_error({"path": path})))

    def _serve_media(self, path: str, request: Any = None) -> None:
        """Sert un média, par la source unique partagée avec le chemin WSGI.

        Ce handler portait sa propre copie du service : import de l'opt-in,
        retrait du préfixe, repli 404. Le chemin WSGI n'en avait aucune, et une
        application déployée rendait 404 sur TOUS ses médias en servant ses
        pages normalement (CORE-WSGI-MEDIA-PARITY-001).

        La réponse vient désormais de `core.http.media`, que les deux serveurs
        appellent. Un écart de comportement entre eux devient impossible,
        puisqu'il n'y a plus deux comportements.
        """
        self._send_response(media_response(path, request))

    def log_message(self, format: str, *args: Any) -> None:
        """Affiche chaque requête reçue dans le terminal avec l'adresse IP du client."""
        logger.info("[%s] %s", self.address_string(), format % args)


def _make_ssl_context() -> ssl.SSLContext:
    """
    Crée le contexte SSL du serveur HTTPS de développement.

    Réservé au développement local, à la pédagogie et aux tests.
    En production, TLS doit être terminé par Nginx ou un reverse proxy équivalent.

    TLS 1.2 est le minimum explicitement imposé ; TLS 1.3 est utilisé si disponible.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


# Délai max accordé au handshake TLS d'un client avant abandon de la connexion.
# Protège la boucle d'accept des clients muets, lents, ou des scanners.
TLS_HANDSHAKE_TIMEOUT = 10  # secondes


class TLSThreadingHTTPServer(ThreadingHTTPServer):
    """
    Serveur HTTPS de développement avec handshake TLS par thread client.

    Le socket d'écoute reste volontairement un socket TCP brut. L'ancien code
    `server.socket = ssl_ctx.wrap_socket(server.socket, server_side=True)`
    appliquait TLS au socket d'écoute, ce qui faisait exécuter le handshake
    dans la boucle accept() du thread principal : un client TLS lent, muet,
    parlant le mauvais protocole, ou refusant le certificat auto-signé
    pouvait alors figer tout le serveur de développement (Recv-Q saturé,
    ERR_TIMED_OUT côté client, aucun traceback).

    Flux réel :

        TCP accept()                       (thread principal — non bloquant)
            → ThreadingMixIn lance un thread (thread du client)
                → wrap_socket()              (handshake TLS, borné par timeout)
                    → RequestHandler         (requête HTTP)

    Ne pas simplifier cette classe en réintroduisant
    `wrap_socket(server.socket)` sur le socket d'écoute : ce serait
    exactement la régression du bug d'origine. Voir ADR-015 — Handshake TLS
    par thread client pour le serveur de développement
    (`docs/adr/015-dev-tls-handshake-per-thread.md`).
    """
    ssl_context: ssl.SSLContext | None = None

    def get_request(self) -> "tuple[socket.socket, Any]":
        # accept() retourne un socket TCP brut, sans TLS.
        # Le wrap se fera dans process_request_thread (= thread du client).
        return self.socket.accept()

    def process_request_thread(self, request: Any, client_address: Any) -> None:
        # Cette méthode s'exécute dans le thread lancé par ThreadingMixIn,
        # donc le handshake TLS ne bloque jamais la boucle d'accept.
        if self.ssl_context is not None:
            request.settimeout(TLS_HANDSHAKE_TIMEOUT)
            try:
                request = self.ssl_context.wrap_socket(request, server_side=True)
            except (ssl.SSLError, OSError, socket.timeout) as exc:
                logger.warning(
                    "Handshake TLS échoué depuis %s : %s", client_address, exc
                )
                self.shutdown_request(request)
                return
            request.settimeout(None)  # comportement bloquant standard ensuite
        super().process_request_thread(request, client_address)


# ── Point d'entrée ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _env = APP_ENV.upper()
    _fmt = {
        "dev" : f"[%(levelname)s-{_env}] %(message)s",
        "prod": f"%(asctime)s [%(levelname)s-{_env}] %(message)s",
    }
    logging.basicConfig(
        level  = logging.DEBUG if APP_ENV == "dev" else logging.INFO,
        format = _fmt[APP_ENV],
    )

    # APP-PY-PROD-HOST-GUARD-001 : `python app.py` n'est pas un serveur de
    # production publique. Si APP_ENV=prod ET APP_HOST écoute sur toutes les
    # interfaces (0.0.0.0 / ::), on refuse de démarrer plutôt que d'émettre
    # un simple warning ignorable. Le garde n'est PAS dans le chemin WSGI
    # (`create_configured_wsgi_app`) — la production WSGI/Gunicorn reste
    # entièrement fonctionnelle.
    if should_block_prod_public_host(APP_ENV, APP_HOST):
        for _line in format_prod_host_guard_error(APP_ENV, APP_HOST).splitlines():
            logger.error(_line)
        _sys.exit(1)

    TLSThreadingHTTPServer.allow_reuse_address = True
    try:
        server = TLSThreadingHTTPServer((APP_HOST, APP_PORT), RequestHandler)
    except OSError as exc:
        if exc.errno == _errno.EADDRINUSE:
            for _line in format_port_in_use_message(APP_HOST, APP_PORT).splitlines():
                logger.error(_line)
            _sys.exit(1)
        raise

    if APP_SSL_ENABLED:
        ssl_ctx = _make_ssl_context()
        ssl_ctx.load_cert_chain(certfile=SSL_CERTFILE, keyfile=SSL_KEYFILE)
        server.ssl_context = ssl_ctx

    logger.info("Environnement : %s", APP_ENV)
    for _line in format_startup_messages(APP_HOST, APP_PORT, APP_SSL_ENABLED):
        logger.info(_line)

    _server_sw = _os.environ.get("SERVER_SOFTWARE", "").lower()
    _web_concurrency = _os.environ.get("WEB_CONCURRENCY", "1")
    _multi_worker = (
        "gunicorn" in _server_sw
        or "uwsgi" in _server_sw
        or (_web_concurrency.isdigit() and int(_web_concurrency) > 1)
    )
    if _multi_worker:
        logger.warning(
            "AVERTISSEMENT — Forge utilise des sessions mémoire (backend mono-processus). "
            "Le multi-worker n'est pas supporté sans backend de session partagé. "
            "Activez un store partagé, par exemple l'opt-in forge-mvc-sessions-db : "
            "forge.configure(session_store=DbSessionStore())."
        )

    from core.app.prod_warnings import emit_memory_store_warning_if_needed
    emit_memory_store_warning_if_needed(APP_ENV, forge.get("session_store"), logger=logger)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Arrêt demandé — attente des requêtes en cours...")
        server.shutdown()   # attend la fin de tous les threads en vol
    finally:
        server.server_close()
        logger.info("Serveur arrêté.")
