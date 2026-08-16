# Phase 13A — Gate de transposabilité FO sur scikit-learn digits

```
DIGITS_ACCESS_GATE: PASS
FO_TRANSPOSABILITY: AMBIGUOUS
FO_TEST_AUTHORIZED: NO
```

FO n'a pas été testé, ni modifié ; `src/fo_metrics.py` a été **importé**, jamais édité.
Aucun score FO n'a été mis en relation avec un résultat de reconstruction. Aucune ressource
externe : le dataset vient uniquement de `sklearn.datasets.load_digits`.

---

## Partie 1 — DIGITS_ACCESS_GATE : PASS

Les dix points sont vérifiés par exécution réelle.

| # | Point | Statut | Mesure |
|---|---|---|---|
| 1 | `load_digits` fonctionne localement | **PASS** | chargé depuis le package, aucun réseau |
| 2 | 1 797 observations + labels | **PASS** | `data (1797, 64)`, `target (1797,)`, 10 classes, 0 NaN, valeurs 0–16 |
| 3 | 64 pixels = 64 canaux d'observation | **PASS** | colonnes de `X` ; **3 canaux morts** (pixels 0, 32, 39, nuls sur tout le dataset) |
| 4 | Sous-ensemble de pixels = design de capteurs | **PASS** | indexation vérifiée à k = 64, 48, 32, 16, 8, 4 |
| 5 | Vérité terrain non ambiguë | **PASS** | 1 797 vecteurs uniques, **0 doublon**, donc 0 conflit de label ; classes équilibrées (174–183) |
| 6 | Inféreur indépendant | **PASS** | `LogisticRegression` entraînée sur TRAIN, rapportée sur VALIDATION |
| 7 | FO et B\* calculables sans modification | **PASS** *(mais voir partie 2)* | `visibility`, `freeze_support`, `b_dynamic`, `b_star` s'exécutent tels quels |
| 8 | Aucun paramètre FO n'exige les labels test | **PASS** | κ, η, σ, baseline fixés a priori ; le split test n'est touché nulle part dans cette phase |
| 9 | Splits gelés avant tout résultat | **PASS** | seed 20260816, stratifié, disjoint : 1005 / 252 / 540 |
| 10 | Niveaux de perte d'information par masquage | **PASS** | 6 niveaux, labels jamais modifiés |

### Point 6 — les six grandeurs sont bien produites

| Grandeur | Disponible |
|---|---|
| classe prédite | oui |
| probabilités / postérieurs | oui, `(252, 10)` |
| rang de la vraie classe | oui, 1 à 6 observés |
| marge top1–top2 | oui, 0,0004 à 0,9999 |
| entropie | oui, 0,0004 à 1,7223 |
| succès / échec de reconstruction | oui, 243/252 |

L'exactitude de validation (0,9643) n'est rapportée que pour montrer que l'inféreur
fonctionne. Elle n'est reliée à aucune grandeur FO nulle part dans cette phase.

L'accès et la structure ne posent donc aucun problème. Le blocage est ailleurs.

---

## Partie 2 — FO_TRANSPOSABILITY : AMBIGUOUS

FO **s'exécute** sur digits sans modification. Ce n'est pas la question. La question est de
savoir si ce qu'il calcule alors est déterminé par le problème ou par mes choix. Quatre
constats mesurés disent : par mes choix.

### Constat 1 — quatre déclarations que FO ne fixe pas, avec une sensibilité de 1 500×

FO consomme `delta[z, j, t]` — « l'écart causé par l'événement » — et un σ par capteur.
Digits ne dit ni quel est l'état sans événement, ni quel est le bruit de mesure. Il faut
donc déclarer : **baseline de delta**, **σ**, **κ**, **η**.

Quatre variantes également défendables, κ = η = 3 :

| baseline | σ | \|E\*\| / 1797 | B\* |
|---|---|---|---|
| fond vierge | écart-type pixel (train) | 0,9917 | **0,00056** |
| fond vierge | unitaire | 1,0000 (dégénéré) | 0,00056 |
| image moyenne train | écart-type pixel (train) | 0,2610 | **0,8358** |
| image moyenne train | unitaire | 1,0000 (dégénéré) | 0,0262 |

B\* varie d'un facteur **1 500** entre deux déclarations que rien dans FO ne départage.
Pré-enregistrer l'une des quatre rend le résultat reproductible ; cela ne le rend pas
signifiant. C'est exactement le mode d'échec documenté sur la branche EPA — une métrique
dont la définition n'est pas déterminée par les artefacts — et il est ici constatable
**avant** de tester.

### Constat 2 — σ n'est pas défini sur digits

FO divise par le bruit de mesure par capteur. **Digits n'a pas de bruit de mesure** : `X`
est un tableau d'entiers figé dans 0–16. Le substitut naturel, l'écart-type par pixel sur
le train, vaut **exactement 0 pour trois canaux** (pixels 0, 32, 39) et quasi 0 pour
d'autres.

Conséquence mesurée : `d_R_max = 1e9`, produit uniquement par le plancher `1e-9` que j'ai
dû introduire pour éviter une division par zéro. Ce nombre ne vient pas de FO, il vient de
ma réparation. Le coefficient de variation de `d_R` atteint 42,4 — entièrement artefactuel.

Sous σ unitaire, l'artefact disparaît mais l'autre extrême apparaît : `d_R` a un coefficient
de variation de **0,009**. Toute image de chiffre possède un pixel proche de l'intensité
maximale 16, donc `d_R` est quasi constant et **E\* dégénère à 100 % du dataset**.

### Constat 3 — B\* est indiscernable de B_dynamic sur ce benchmark

C'est le constat décisif, et il est vérifié positivement.

B\* existe pour une raison précise, énoncée dans `fo_metrics.py` : le dénominateur de
B_dynamic bouge quand le **bruit de mesure** change, ce qui rend deux valeurs incomparables.
B\* gèle le support une fois pour toutes.

Or l'axe de perte d'information imposé par le brief est le **masquage de pixels**, qui
change `S`, jamais σ. Et le support de B_dynamic ne dépend que des capteurs de référence et
de σ — **jamais de `S`**. Les deux supports coïncident donc par construction.

Vérifié sur 24 designs, 8 niveaux de masquage (k = 64 → 1), trois tirages chacun :

```
B* identique à B_dynamic dans tous les cas : True
```

à la précision machine, y compris aux valeurs intermédiaires (k=8 : 0,632997 / 0,884961 /
0,245791). Le défaut que B\* corrige **ne peut pas se manifester ici**.

Preuve par contraste — en faisant varier σ artificiellement, les supports divergent bien :

| σ × | support B\* | support B | B\* | B |
|---|---|---|---|---|
| 0,5 | 1782 | 1797 | 0,0039 | 0,0072 |
| 1,0 | 1782 | 1782 | 0,1829 | 0,1829 |
| 2,0 | 1782 | **109** | 0,9955 | 0,9266 |
| 4,0 | 1782 | **31** | 1,0000 | 1,0000 |

Cet axe n'existe pas dans digits. Tester B\* ici mesurerait donc B_dynamic sous un autre
nom, et la phase ne pourrait rien conclure sur la propriété qui distingue B\*.

### Constat 4 — FO mesure une amplitude, la question porte sur un motif

```
d_S(z) = max_{j ∈ S} |delta[z, j]| / σ_j
```

C'est un **maximum de magnitudes par canal**. Il est invariant au motif formé par les
canaux entre eux. Deux images de chiffres différents ayant le même pixel le plus brillant
reçoivent la même valeur.

Or l'identité d'un chiffre est **exclusivement** un motif, jamais une amplitude. D'où une
divergence sémantique concrète :

- un sous-ensemble entièrement situé dans un trait commun à tous les chiffres marque fort
  (`d_S` élevé, FO le dit « visible ») et ne porte **aucune** information de classe ;
- un sous-ensemble faiblement encré mais placé sur les zones discriminantes peut être
  très informatif alors que FO le déclare « aveugle ».

Dans le problème hydraulique, « aucun capteur ne dépasse le plancher de bruit » est
exactement la bonne notion de perte d'information. Ici, FO répondrait à « y a-t-il de
l'encre sous mes capteurs ? », alors que la question posée est « le motif sous mes capteurs
détermine-t-il le chiffre ? ». Ce sont deux questions différentes.

---

## Pourquoi AMBIGUOUS et non INVALID

INVALID signifierait que FO ne peut pas être appliqué. Ce n'est pas le cas : les quatre
fonctions s'exécutent sans modification, et sous certaines déclarations `E*` est non
dégénéré et `d_S(z)` prend des valeurs par scénario exploitables.

Ce qui manque n'est pas la calculabilité, c'est la **détermination** : rien dans le problème
ne désigne la bonne baseline, le bon σ, le bon κ, le bon η ; et pour B\* spécifiquement, le
benchmark ne peut structurellement pas exercer la propriété qui le distingue de la métrique
qu'il répare.

Un test lancé maintenant produirait un chiffre parfaitement reproductible et parfaitement
ininterprétable : favorable, il serait attribuable à ma déclaration ; défavorable, à la
même. C'est la situation exacte dans laquelle la branche EPA a été arrêtée.

---

## Ce qu'il faudrait pour lever l'ambiguïté

Sans modifier FO, dans l'ordre :

1. **Introduire un axe de bruit de mesure** — perturber les pixels par un bruit gaussien de
   σ connu, au lieu de (ou en plus de) les masquer. Cela donne à σ un sens, rend `d_S`
   comparable à un plancher de bruit réel, et surtout rend B\* distinguable de B_dynamic,
   donc testable pour ce qu'il est. Le brief de cette phase impose le masquage seul ; c'est
   une décision qui vous revient, pas une réparation que je peux décider.
2. **Fixer la baseline de delta par un argument**, pas par convention. Le fond vierge est
   défendable parce que le fond de digits vaut littéralement 0 ; l'image moyenne l'est parce
   que FO parle d'un écart à l'état sans événement. Il faut trancher explicitement.
3. **Exclure les trois canaux morts** de tout design de référence, ou déclarer un σ plancher
   motivé plutôt qu'un `1e-9` d'implémentation.

Je n'entreprends aucune de ces trois choses de ma propre initiative, et je ne modifie pas FO
pour rendre le test possible.

---

## Verdict

```
DIGITS_ACCESS_GATE: PASS
FO_TRANSPOSABILITY: AMBIGUOUS
FO_TEST_AUTHORIZED: NO
```

Arrêt ici comme demandé. FO reste `NOT_EVALUATED`.

---

## Fichiers produits

```
phase13a_digits/RAPPORT_PHASE13A_TRANSPOSABILITE.md   ce rapport
phase13a_digits/GATE_13A_CHECKS.json                  les dix vérifications, mesurées
src/phase13a_transposability_gate.py                  gate rejouable
```

`src/fo_metrics.py` est inchangé — vérifiable par `git diff`.
