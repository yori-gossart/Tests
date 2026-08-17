# Phase 19 — Gate banc physique : ZeMA / UCI, condition monitoring hydraulique

```
HYDRAULIC_ACCESS:          PASS   (avec réserve d'intégrité, voir §1)
PHYSICAL_REAL_DATA:        PASS
INDEPENDENT_REPLICATION:   FAIL
MATCHED_BASELINE:          PASS
SIGMA_IDENTIFIABILITY:     AMBIGUOUS
FO_PHYSICAL_SEMANTICS:     AMBIGUOUS
BSTAR_PHYSICAL_SEMANTICS:  AMBIGUOUS
ISOLABILITY_PHYSICAL:      VALID
CONFIRMATORY_TEST_POSSIBLE: NO
PHASE20_AUTHORIZED:        NO
```

**Aucun protocole Phase 20 n'est écrit.** Aucune performance FO n'a été calculée.
`src/fo_metrics.py` est inchangé. Aucun FO-v2, aucun B\*\*, aucune formule modifiée.

Classification demandée :
- **baseline : `MATCHED_EXPERIMENTAL_BASELINE`** (ni contrefactuel apparié, ni baseline non appariée)
- **`SIGMA_SOURCE = EFFECTIVE_VARIABILITY_ONLY`**

---

## 1. Accès et intégrité — PASS, avec une réserve à consigner

L'hôte officiel `archive.ics.uci.edu` est **bloqué par le proxy** sur les trois voies testées :
`curl` (HTTP 000), WebFetch (`EGRESS_BLOCKED`), et le paquet officiel `ucimlrepo`
(`ConnectionError`). Le dépôt canonique est donc inatteignable depuis cet environnement.

Les données ont été obtenues depuis un miroir GitHub accessible
(`Machine-Learning-FGA/Hydraulic-systems`, répertoire `data/`), qui embarque les fichiers
`.txt` originaux **et** le `documentation.txt` d'origine signé Helwig / ZeMA.

> **Réserve** : ne pouvant atteindre UCI, je ne peux pas vérifier ce miroir par empreinte
> contre l'original. Je vérifie à la place la conformité structurelle complète à la
> documentation officielle — et elle est totale, y compris sur des quantités qu'un miroir
> altéré n'aurait aucune raison de conserver.

### Vérifications d'intégrité — toutes passées

| Contrôle | Attendu | Mesuré |
|---|---|---|
| Cycles | 2 205 | **2 205** ✔ |
| Attributs totaux | 43 680 | **43 680** ✔ |
| Capteurs conformes | 17 / 17 | **17 / 17** ✔ |
| Valeurs manquantes | aucune | **0 NaN, 0 Inf** ✔ |
| `profile.txt` | 2205 × 5 | **2205 × 5**, 0 NaN ✔ |

Fréquences vérifiées une à une : PS1–PS6 et EPS1 à 100 Hz (6 000 colonnes), FS1–FS2 à 10 Hz
(600), TS1–TS4, VS1, SE, CE, CP à 1 Hz (60).

Les distributions de classes reproduisent **exactement** celles publiées dans la
documentation : refroidisseur 732 / 732 / 741, vanne 1125 / 360 / 360 / 360, pompe
1221 / 492 / 492, accumulateur 599 / 399 / 399 / 808, drapeau de stabilité 1449 / 756.

### PHYSICAL_REAL_DATA — PASS

Banc d'essai physique réel (circuit primaire de travail + circuit secondaire de
refroidissement-filtration reliés par le réservoir d'huile), capteurs réels, dégradation
réelle des quatre composants. Sans ambiguïté.

### Les quatre composants et leurs états

| Composant | États | Optimum |
|---|---|---|
| Refroidisseur | 3 % (proche de la défaillance), 20 % (rendement réduit), 100 % | 100 % |
| Vanne | 73 % (proche de la défaillance), 80 %, 90 %, 100 % | 100 % |
| Fuite interne pompe | 2 (sévère), 1 (faible), 0 | 0 |
| Accumulateur | 90 bar (proche de la défaillance), 100, 115, 130 | 130 bar |

**État pleinement sain** (les quatre composants à l'optimum) : **21 cycles**, dont **10 avec
le drapeau de stabilité à 0**, répartis en 3 blocs contigus entre les cycles 1664 et 1796.

---

## 2. INDEPENDENT_REPLICATION — **FAIL**

C'est le résultat central de cette phase, et il confirme dans les termes les plus forts
l'avertissement de la mission de ne pas traiter les 2 205 cycles comme 2 205 expériences.

### Le plan est un plan par blocs, pas une randomisation

| Colonne du profil | Nombre de plages contiguës | Longueur médiane |
|---|---|---|
| **Refroidisseur** | **3** | 732 |
| Accumulateur | 12 | 133 |
| Fuite pompe | 37 | 41 |
| Vanne | 145 | 10 |

- **144 configurations distinctes**, réalisées en **194 blocs contigus**, longueur médiane
  **10 cycles**, minimum **10 cycles par configuration**.
- **P(deux cycles consécutifs partagent la même configuration) = 0,912.**

L'effectif indépendant n'est donc pas 2 205 mais **au plus 194 blocs**, et pour certains
composants bien moins.

### Le refroidisseur est le cas limite

Le refroidisseur n'a **que 3 plages** pour 3 niveaux : chaque niveau a été réglé **une seule
fois**, puis maintenu pendant ~732 cycles consécutifs. Il n'existe **aucune réplication
indépendante** de l'état du refroidisseur. Un découpage sans fuite par bloc ne peut pas
retirer un niveau de refroidisseur du train sans le supprimer entièrement.

La documentation officielle l'annonçait d'ailleurs : les quatre colonnes de condition
« describe **degradation processes over time** ». L'indice de cycle est une trajectoire, pas
un tirage.

---

## 3. MATCHED_BASELINE — **PASS**

C'est le point le plus favorable du dossier.

Pour chacune des **10 combinaisons composant × niveau dégradé**, j'ai vérifié qu'il existe des
cycles sains-sur-ce-composant partageant **exactement** les états des trois autres composants :

| Composant | Niveau | Cycles | Couverture contextuelle appariée |
|---|---|---|---|
| Refroidisseur | 3 %, 20 % | 732, 732 | **1,000** |
| Vanne | 73 %, 80 %, 90 % | 360 ×3 | **1,000** |
| Pompe | 1, 2 | 492, 492 | **1,000** |
| Accumulateur | 90, 100, 115 bar | 808, 399, 399 | **1,000** |

**Couverture 1,000 partout.** Le plan factoriel du banc permet donc de définir `delta` comme

```
delta = cycle dégradé  −  distribution des cycles sains-sur-ce-composant
                          aux MÊMES états des trois autres composants
```

sans inventer aucun contrefactuel : les cycles sains de référence sont des mesures réelles.

### Classification, telle que la mission la demande

| | |
|---|---|
| `PAIRED_COUNTERFACTUAL` | **non** — un banc physique ne peut pas exécuter le même cycle avec et sans défaut ; les cycles sains sont d'autres cycles, à d'autres instants |
| **`MATCHED_EXPERIMENTAL_BASELINE`** | **oui** — appariement exact sur les trois autres composants, couverture 100 % |
| `UNMATCHED_BASELINE` | sans objet, on fait mieux |

C'est strictement supérieur à 3W (aucune baseline appariée) et strictement inférieur à TEP et
LeakDB (contrefactuel apparié bit-à-bit). `delta` porte ici, en plus de l'effet du défaut, la
variabilité inter-cycles — ce qui nous amène à σ.

---

## 4. SIGMA_IDENTIFIABILITY — **AMBIGUOUS** ; `SIGMA_SOURCE = EFFECTIVE_VARIABILITY_ONLY`

Le banc **ne déclare aucune spécification de bruit de mesure** — contrairement à TEP, dont
`teprob.f` publie `XNS(1..41)`.

La mission interdit de déclarer automatiquement `σ = écart-type des cycles sains` sans
vérifier que cette quantité a le sens requis. **Je l'ai donc mesuré.**

### Mesure : la variabilité intra-configuration n'est pas un plancher de bruit

Sur les 144 blocs d'au moins 10 cycles stables, j'ai régressé la moyenne par cycle de chaque
capteur sur l'indice de cycle à l'intérieur du bloc. Si le bruit dominait, la pente serait
nulle.

| Capteur | R² médian de la dérive linéaire | Part de variance retirée par détendance |
|---|---|---|
| **TS2** | 0,713 | **0,843** |
| TS1 | 0,713 | 0,757 |
| TS3 | 0,685 | 0,657 |
| PS5 | 0,490 | 0,627 |
| PS6 | 0,470 | 0,608 |
| TS4 | 0,438 | 0,527 |
| FS2 | 0,331 | 0,492 |
| PS4 | — | 0,460 |
| PS1 | 0,187 | 0,414 |
| EPS1 | 0,204 | 0,406 |
| … | … | … |
| CE | 0,153 | **0,226** |

**Médiane sur les 17 capteurs : 41,4 % de la variance intra-bloc est de la dérive
systématique**, de 22,6 % (CE) à 84,3 % (TS2). Sur les capteurs de température, la dérive
thermique domine largement le bruit.

### Ce qui reste après détendance n'est toujours pas du bruit de mesure

Chaque cycle n'est mesuré **qu'une fois**. Il n'existe aucune structure de mesure répétée —
pas deux capteurs redondants sur la même grandeur physique — permettant de séparer le bruit
d'instrument de la variabilité cycle-à-cycle réelle du procédé. Le résidu détendancé les
conflate irréductiblement.

D'où la classification :

```
SIGMA_SOURCE: EFFECTIVE_VARIABILITY_ONLY
```

Une variabilité effective par capteur est estimable et physiquement significative. Un σ de
**bruit de mesure**, au sens que FO lui donne, **n'est pas identifiable** dans ce plan
expérimental.

---

## 5. FO_PHYSICAL_SEMANTICS — **AMBIGUOUS**

FO consomme deux objets. Ce banc en fournit un.

| Exigence de FO | TEP | LeakDB | 3W | **ZeMA** |
|---|---|---|---|---|
| `delta` = écart causé par l'événement | ✔ contrefactuel apparié | ✔ | ✘ | **✔ baseline expérimentale appariée, couverture 100 %** |
| `σ` = bruit de mesure | ✔ `XNS` déclaré | ✔ mesuré | ✘ | **✘ seulement variabilité effective** |

**Le côté `delta` tient.** C'est la première fois depuis TEP qu'un jeu de données réel permet
de définir `delta` sans rien inventer.

**Le côté `σ` ne tient pas.** Dans `fo_metrics.py`, σ est explicitement « a property of the
MEASUREMENT CONDITIONS », et c'est ce qui fonde toute la construction de B\* : le support ne
doit pas suivre quand le bruit de mesure bouge. Substituer une variabilité effective dont
41 % de la variance est de la dérive thermique change ce que `d_S` mesure : « combien
d'unités de bruit » devient « combien d'unités de dispersion naturelle incluant la dérive ».

Ce n'est pas une nuance : `d_S ≤ η` cesserait de signifier « l'événement est noyé dans le
bruit » pour signifier « l'événement est dans l'étalement naturel du banc ». Deux affirmations
différentes.

Je ne redéfinis pas FO pour absorber cette différence, et je ne propose aucun FO-v2.

---

## 6. BSTAR_PHYSICAL_SEMANTICS — **AMBIGUOUS**, mais à signaler séparément

La mission demande de signaler si B\* reste valide indépendamment de FO. Réponse nuancée, et
c'est la première fois qu'elle l'est.

**Ce que B\* exige et que ce banc fournit, contrairement à 3W :**

| Exigence | ZeMA |
|---|---|
| Ensemble commun de capteurs | **✔ les 17 capteurs présents dans les 2 205 cycles, 0 valeur manquante** |
| Sous-échantillonnage possible des capteurs | **✔ espace de designs réel et libre** |
| Designs comparables entre conditions | **✔ le même sous-ensemble a un sens dans toutes les configurations** |
| Support de scénarios gelable avant test | **✔ pré-enregistrable sur des blocs réservés** |

Sur 3W, B\* échouait pour deux raisons indépendantes : pas de σ **et** pas d'espace de designs.
Ici, **l'espace de designs et le support gelable sont pleinement disponibles**. Le seul
obstacle restant est le σ qu'il hérite de FO.

C'est un constat utile : l'obstruction de B\* sur ce banc est **entièrement** celle de σ, et
non un défaut de sa propre construction.

---

## 7. ISOLABILITY_PHYSICAL — **VALID**

| Mesure | Possible ? |
|---|---|
| Détectabilité | oui — sain contre dégradé, par composant |
| Isolabilité | oui — 4 composants, états croisés factoriellement |
| Sévérité | oui — 3 à 4 niveaux ordonnés par composant |
| Confusion entre composants | oui — les 144 configurations couvrent les combinaisons |

Les baselines standards sont toutes calculables : SNR, Mahalanobis / T², KL, distances
inter-classes — 17 capteurs présents partout, aucune valeur manquante, aucun socle commun à
négocier (le problème qui minait 3W).

Points de référence de la littérature officielle du jeu de données, utilisables comme
étalons : Helwig et al. (I2MTC 2015) rapportent que refroidisseur et vanne sont des cibles
« faciles » (classification parfaite) tandis que pompe et surtout accumulateur sont
« more complex » ; Schneider et al. (tm 2017) descendent à 0,35 % d'erreur sur l'accumulateur
contre 9,6 % initialement.

---

## 8. CONFIRMATORY_TEST_POSSIBLE — **NO**

Un découpage sans fuite doit garder les blocs de configuration entiers — jamais découper à
l'intérieur d'un bloc, ni a fortiori à l'intérieur d'un cycle.

| Composant | Blocs disponibles | Test hors échantillon par blocs ? |
|---|---|---|
| Vanne | 145 | **oui** |
| Pompe | 37 | **oui** |
| Accumulateur | 12 (3 par niveau) | **marginal** |
| **Refroidisseur** | **3 (1 par niveau)** | **impossible** |

Pour une validation confirmatoire portant sur les quatre composants, la réponse est **non** :
le refroidisseur ne peut pas être testé hors échantillon, et l'accumulateur ne le serait qu'au
prix d'intervalles inexploitables.

---

## 9. Règle d'arrêt appliquée

`FO_PHYSICAL_SEMANTICS ≠ VALID`. Conformément à la règle :

### FO exige-t-il structurellement un simulateur ou un contrefactuel contrôlé ?

**Oui, pour son σ — pas pour son delta.** C'est la conclusion précise que quatre jeux de
données permettent maintenant de formuler :

- `delta` de FO est obtenable dès qu'un plan expérimental **factoriel apparié** existe. ZeMA le
  démontre sur un banc physique réel, sans simulateur.
- `σ` de FO n'a été disponible que là où le processus générateur le **déclare** (TEP :
  `XNS` dans `teprob.f`) ou là où un contrefactuel apparié permet de l'**isoler**
  empiriquement (LeakDB : résidu hors fenêtre de fuite).

Un banc physique qui mesure chaque cycle une seule fois ne peut pas séparer le bruit
d'instrument de la variabilité du procédé. Il faudrait, au choix : une spécification
constructeur des capteurs, une mesure redondante simultanée de la même grandeur, ou un
jumeau numérique fournissant le contrefactuel. **FO dépend donc structurellement d'une de ces
trois choses, qu'aucun jeu de données réel rencontré jusqu'ici ne fournit.**

### B\* séparément

B\* n'est pas invalide *pour ses propres raisons* sur ce banc : son espace de designs et son
support gelable existent tous deux. Il est bloqué **uniquement** par le σ qu'il partage avec
FO. Si un σ déclaré devenait disponible sur un banc de ce type, B\* y serait testable — ce qui
n'est pas le cas de FO, dont la Phase 16 a par ailleurs déjà montré que l'apport propre est
WEAK.

### Conséquence

FO et B\* sont tous deux `AMBIGUOUS`, donc aucun n'est `VALID`. **La validation physique de
FO/B\* s'arrête ici.** Aucun protocole Phase 20 n'est écrit.

L'architecture standard Visibilité / Robustesse / Isolabilité **pourrait** être testée
séparément sur ce banc — l'isolabilité y est VALID, les baselines standards toutes
calculables, et les composants vanne et pompe offrent respectivement 145 et 37 blocs
indépendants. Mais, conformément à la règle : **elle ne devra plus être présentée comme une
technologie FO/B\***, puisque la Phase 16 avait déjà établi que tout le gain de cette
architecture provient de métriques standards.

---

## 10. Verdicts

```
HYDRAULIC_ACCESS:           PASS
PHYSICAL_REAL_DATA:         PASS
INDEPENDENT_REPLICATION:    FAIL
MATCHED_BASELINE:           PASS
SIGMA_IDENTIFIABILITY:      AMBIGUOUS
FO_PHYSICAL_SEMANTICS:      AMBIGUOUS
BSTAR_PHYSICAL_SEMANTICS:   AMBIGUOUS
ISOLABILITY_PHYSICAL:       VALID
CONFIRMATORY_TEST_POSSIBLE: NO
PHASE20_AUTHORIZED:         NO
```

**Causes précises :**

1. **Réplication** — 194 blocs pour 2 205 cycles, P(cycles consécutifs identiques) = 0,912, et
   **3 plages seulement** pour le refroidisseur : un niveau, un réglage, aucune réplication.
2. **σ** — aucune spécification de bruit déclarée ; la variabilité intra-configuration est à
   41 % médians de la dérive systématique (jusqu'à 84 % sur TS2), et le résidu conflate
   irréductiblement bruit d'instrument et variabilité du procédé, chaque cycle n'étant mesuré
   qu'une fois.
3. **Test confirmatoire** — le refroidisseur ne peut pas être tenu hors échantillon.

**Ce qui n'est pas en cause :** l'intégrité (2 205 cycles, 43 680 attributs, 0 valeur
manquante, 17/17 capteurs conformes), la nature physique réelle des données, la baseline
appariée (couverture 100 %), l'espace de designs capteurs, et l'isolabilité. Ce banc est le
meilleur candidat rencontré depuis TEP — et il échoue quand même, pour des raisons qui tiennent
au plan expérimental et non à la qualité des données.

---

## 11. Livrables

```
phase19_hydraulic/RAPPORT_PHASE19_GATE_BANC_PHYSIQUE.md   ce rapport
phase19_hydraulic/AUDIT_HYDRAULIC.json                    audit complet A-D
phase19_hydraulic/SENSOR_INTEGRITY.csv                    17 capteurs, formes et NaN
phase19_hydraulic/MATCHED_BASELINE_COVERAGE.csv           couverture appariée, 10 combinaisons
phase19_hydraulic/CONFIGURATION_COUNTS.csv                144 configurations
phase19_hydraulic/SIGMA_DECOMPOSITION.csv                 dérive contre bruit, 17 capteurs
phase19_hydraulic/logs/audit.log                          journal
phase19_hydraulic/SHA256SUMS.txt                          empreintes
src/phase19_hydraulic_audit.py                            audit rejouable
```

Les données (1,3 Go) ne sont pas versionnées ; la source et la réserve d'intégrité sont
enregistrées dans `AUDIT_HYDRAULIC.json`.
