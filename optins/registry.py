# pyright: strict
"""Registre des opt-ins de ce projet (ADR-061).

Vue unique et explicite des opt-ins utilisés par ce projet. Aucun code d'opt-in
n'est copié ici : il vit dans le `.venv`. Ce fichier est géré par
`forge opt-in:enable` / `disable` et `forge db:*` ; il reste éditable à la main.

- `BACKEND` : le backend base de données choisi (ADR-054/060), ou None.
- `ENABLED_OPTINS` : les opt-ins utilisés, par nom vers catégorie d'intégration
  (route, library, crosscutting, cli). Les opt-ins `route` sont aussi câblés
  dans `register_optins` ; les autres y figurent pour la visibilité.
- `register_optins` : câble les routes des opt-ins `route` activés. Appelé
  depuis `mvc/routes/__init__.py` :

    from optins.registry import register_optins

    register_optins(router)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.http.router import Router

# Backend base de données (ADR-054/060). None tant qu'aucun n'est configuré.
BACKEND: str | None = None

# Opt-ins utilisés par ce projet : nom vers catégorie d'intégration.
ENABLED_OPTINS: dict[str, str] = {
    # >>> opt-in registry (géré par forge opt-in:enable / disable)
}

# >>> opt-in imports (gérés par forge opt-in:enable / disable)


def register_optins(router: Router) -> None:
    """Branche les routes des opt-ins « route » activés dans ce projet."""
    # >>> opt-in calls (gérés par forge opt-in:enable / disable)
    return None
