# Point d'entrée de validation du projet (ADR-063).
#
# `make check` reproduit les gardes qualité du framework Forge en une commande :
# lint, typage strict, tests, documentation. À lancer dans l'environnement
# virtuel activé (voir requirements-dev.txt et requirements-docs.txt).

.PHONY: check lint typage test docs install

# Chaîne complète de validation.
check: lint typage test docs

lint:
	ruff check .

typage:
	pyright

test:
	pytest

docs:
	mkdocs build --strict

# Installe le projet et tout son outillage de développement.
install:
	pip install -r requirements.txt -r requirements-dev.txt -r requirements-docs.txt
