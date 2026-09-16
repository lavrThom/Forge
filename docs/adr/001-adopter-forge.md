# ADR-001 — Adopter Forge et ses conventions

## Statut

Accepté.

## Date

2026-09-16

## Contexte

Ce projet est une application web bâtie sur le framework Forge.
Forge est un framework MVC Python explicite, testable et durable : pas de magie
cachée, SQL visible, sécurité par défaut, et une CLI qui génère le code répétitif.

Choisir Forge engage le projet sur des conventions précises.
Ce premier ADR les acte et amorce la pratique des ADR pour les décisions à venir.

## Décision

1. Le projet adopte Forge et ses conventions :
   - structure MVC explicite (`mvc/entities`, `models`, `controllers`, `views`,
     `routes.py`) ;
   - entités décrites par des contrats JSON (source de vérité), code généré
     régénérable, code manuel préservé ;
   - routes nommées selon la convention `/<controleur>/<methode>` ;
   - accès base via `core.database.db`, requêtes paramétrées, sans ORM ;
   - sécurité par défaut (authentification, CSRF, sessions) jamais désactivée
     pour aller plus vite ;
   - fonctionnalités optionnelles ajoutées via les opt-ins `forge-mvc-*` à la
     demande.
2. Le projet adopte la **discipline ADR** : toute décision structurante
   (architecture, convention, dépendance, choix difficile à défaire) est
   consignée dans `docs/adr/`, au format de cet ADR.
3. On privilégie les petits incréments à une responsabilité, et on révèle la
   cause d'un problème avant d'en corriger le symptôme.

## Conséquences

- Le « pourquoi » des choix du projet reste tracé et partageable.
- Les contributeurs, humains comme agents IA, disposent d'un cadre commun
  (voir aussi `CLAUDE.md` et `AGENTS.md` à la racine du projet).
- S'écarter d'une convention Forge devient une décision explicite, documentée
  par un nouvel ADR, plutôt qu'une dérive silencieuse.

## Alternatives écartées

- Un framework « tout inclus » avec ORM et comportements implicites : rejeté,
  Forge privilégie l'explicite et le SQL visible.
- Un micro-framework nu sans conventions : rejeté, on perdrait le cadre et les
  générateurs qui font la valeur de Forge.

## Suite

Numéroter les ADR suivants `002`, `003`, etc. dans `docs/adr/`.
