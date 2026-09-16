"""Smoke test du projet : l'application se charge et ses routes sont câblées.

Rapide et sans base de données : importe le routeur du projet et vérifie que la
route d'accueil publique est résolue. Si ce test passe, le câblage
`mvc/routes/` -> contrôleurs -> `optins/registry.py` est sain.

Point de départ pour vos propres tests : `pytest -m smoke` pour ce niveau,
`pytest` pour toute la suite. Marqueurs disponibles dans `pytest.ini`.
"""
import pytest

from mvc.routes import router


@pytest.mark.smoke
def test_le_routeur_du_projet_se_charge():
    assert router.iter_routes(), "aucune route enregistrée dans mvc/routes/"


@pytest.mark.smoke
def test_la_route_home_publique_est_resolue():
    assert router.match("GET", "/") is not None, "route d'accueil « / » introuvable"
    assert router.is_public("/", "GET"), "la route d'accueil doit être publique"
