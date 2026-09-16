# ADR-002 : Style et rédaction de la documentation

## Statut

Accepté.

## Date

2026-09-16

## Contexte

La documentation du projet (guides, pages du site, README, ADR, notes) doit
rester lisible, homogène et durable, quel que soit l'auteur, humain ou agent IA.
Sans règle explicite, le style dérive : mélange de langues, ponctuation
irrégulière, caractères typographiques hétérogènes, phrases empilées sur une
seule ligne difficiles à relire en diff.

Forge applique déjà ces conventions à sa propre documentation, actées par son
ADR-087 (style rédactionnel canonique), dont les règles ci-dessous dérivent.
Ce projet les reprend à son compte pour partir sur une base saine, et reste
libre de les étendre : cet ADR lui appartient.

## Décision

Toute documentation du projet respecte les règles suivantes.

1. **Langue** : rédiger en français, sauf les noms de commandes, symboles de
   code et termes techniques indispensables.
2. **Une phrase par ligne** dans la source Markdown : après le point final,
   la phrase suivante commence sur une nouvelle ligne.
   Cela garde les diffs lisibles et se prête au rendu ligne à ligne.
3. **Pas de tiret cadratin** (le caractère long).
   Préférer la virgule, le point-virgule, les deux-points, ou le trait d'union
   court selon le sens.
4. **Ponctuation française** : espaces insécables avant les signes doubles
   (deux-points, point-virgule, point d'interrogation, point d'exclamation) et
   autour des guillemets français.
5. **Au plus un deux-points par phrase**, réservé à l'énumération, à la citation
   ou à la conséquence annoncée.
   Sinon, une virgule pour l'incise, ou un point et une phrase nouvelle.
6. **Liens internes** vers le fichier `.md` cible, vérifiés au build strict de
   la documentation.
7. **Éviter les anglicismes** inutiles et les tournures calquées sur l'anglais.

Cette décision porte sur la rédaction, pas sur le fond : elle s'applique aux
corrections comme aux nouveaux documents.

## Conséquences

- La documentation reste homogène et relisible, y compris en revue de diff.
- Les contributeurs, humains comme agents IA, disposent d'une règle unique et
  explicite à suivre et à faire respecter.
- Un écart de style devient un correctif simple, pas une négociation.

## Alternatives écartées

- Laisser le style au jugement de chaque auteur : rejeté, la documentation
  dérive vite et devient incohérente.
- Adopter un style typographique anglo-saxon (tiret cadratin, pas d'espaces
  insécables) : rejeté, le projet rédige en français et vise une lecture
  française correcte.

## Suite

Ces règles valent pour tous les ADR suivants et pour l'ensemble de la
documentation du projet.
