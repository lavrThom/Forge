"""
bootstrap.py - Câblage de l'application
=======================================
Middlewares et services partagés de ce projet, lus par les DEUX points d'entrée :
le serveur de développement (`app.py`) et le chemin WSGI de production
(`wsgi.py`, `core.app.wsgi`).

C'est tout l'intérêt de ce fichier, et il a été payé cher.

Ce câblage vivait dans `app.py`, que la fabrique WSGI ne lit pas : `config.py`
ne porte que des valeurs, jamais des objets construits. Une application
déployée servait donc ses pages sans aucune de ses gardes, sauf la première.
Elle démarrait, répondait 200, authentifiait, et laissait passer tout le reste.
Voir ADR-092 (le refus qui rend la panne bruyante) et ADR-093 (ce fichier, qui
retire la cause).

Ce fichier vous appartient. Forge ne le réécrit jamais (principe 9).

Deux fonctions, appelées dans cet ordre :

    configure_services()   services partagés (magasin de sessions, ...)
    build_middlewares()    middlewares, dans leur ordre d'évaluation

Un middleware peut avoir besoin d'un service ; l'inverse ne se produit pas.
"""
from __future__ import annotations

from typing import Any

import core.forge as forge  # noqa: F401  (utilisé par les exemples ci-dessous)


def configure_services() -> None:
    """Services partagés de l'application, posés avant sa construction.

    Le magasin de sessions se câble ICI, et pas ailleurs.

    Par défaut, Forge garde les sessions en mémoire, dans le processus. Cela
    convient au développement et à un seul travailleur. Sous Gunicorn avec
    plusieurs travailleurs, chacun a le sien : une session ouverte par l'un est
    inconnue des autres, et la connexion ne réussit qu'une fois sur N.

    Exemple, avec l'opt-in `forge-mvc-sessions-db` :

        from forge_mvc_sessions_db import DbSessionStore

        forge.configure(session_store=DbSessionStore())
    """


def build_middlewares() -> list[Any]:
    """Middlewares de l'application, dans leur ordre d'évaluation.

    Chacun expose `check(request) -> Response | None` ; le premier qui renvoie
    une `Response` court-circuite la requête. Ils ne sont consultés que pour les
    routes NON publiques.

    L'ordre compte : une garde de rôle placée avant l'authentification
    s'exécuterait sans savoir qui est l'utilisateur.

    Exemple, pour exiger l'authentification puis protéger un domaine par
    préfixe d'URL :

        from forge_mvc_rbac import PrefixPermissionMiddleware   # opt-in

        return [
            AuthMiddleware("/login"),
            PrefixPermissionMiddleware({"/admin": "admin.access"}),
        ]

    Retourner une liste VIDE retire jusqu'à l'authentification : toutes les
    routes non publiques deviennent accessibles sans session. C'est un choix
    légitime pour un site entièrement public, et jamais un choix par défaut.
    """
    from core.security.middleware import AuthMiddleware

    return [AuthMiddleware("/login")]
