"""Constantes et fixtures partagées par les tests du projet.

Le plugin pytest de forge-mvc-testing (ADR-041) est chargé automatiquement dès
que le paquet est installé (voir requirements-dev.txt) : FakeRequest et les
fixtures associées sont disponibles dans les tests sans import explicite.
"""
from pathlib import Path

# Racine du projet, partagée par les tests qui inspectent l'arborescence.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
