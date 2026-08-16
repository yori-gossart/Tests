# Phase 17A — Gate 0, validation externe réelle : Petrobras 3W

```
3W_ACCESS:                 PASS
REAL_DATA_SUFFICIENT:      FAIL
REAL_EVENT_GROUND_TRUTH:   FAIL
FO_3W_SEMANTICS:           INVALID
BSTAR_3W_SEMANTICS:        INVALID
ISOLABILITY_3W:            AMBIGUOUS
INDEPENDENT_TEST_POSSIBLE: YES
PHASE18_AUTHORIZED:        NO
```

**Gate 0 échoué. La branche 3W est arrêtée.** Aucun protocole Phase 18 n'est préparé,
conformément à la règle « Si FAIL : arrête la branche et documente pourquoi ».

Aucune hypothèse n'a été testée, aucun modèle ajusté, aucun chiffre de performance produit.
`src/fo_metrics.py` est inchangé. Aucun FO-v2, aucun B\*\*, aucune formule créée.

Dépôt officiel `petrobras/3W` @ `93793db1`, dataset 2.0.0, 5,3 Go clonés.

---

## 1. Ce qui passe

### 3W_ACCESS : **PASS**

Le dépôt se clone intégralement depuis GitHub, sans hébergeur externe — contrairement à
LeakDB, dont les trois hôtes étaient bloqués. 2 228 fichiers Parquet lisibles avec `pyarrow`.

| | |
|---|---|
| Licence du code | Apache 2.0 |
| Licence des données | CC BY 4.0 |
| Reproductibilité | `dataset.ini` versionné, `environment.yml`, toolkit Python complet |
| Métriques officielles | `toolkit/ThreeWToolkit/metrics/_classification.py`, `assessment/model_assess.py` |

À signaler : le répertoire `dataset/folds`, que `3W_DATASET_STRUCTURE.md` décrit comme
contenant « all 3W Dataset configuration files » pour la validation croisée, **est absent de
ce commit**. La documentation est en avance sur le contenu.

### Séparation REAL / SIMULATED / HAND-DRAWN : **sans ambiguïté**

Le préfixe du nom de fichier suffit : `WELL-xxxxx_horodatage`, `SIMULATED_xxxxx`,
`DRAWN_xxxxx`. Aucun préfixe inconnu sur 2 228 fichiers.

| Type | REAL | SIMULATED | HAND-DRAWN | Total | Puits réels |
|---|---|---|---|---|---|
| 0 — normal | 594 | 0 | 0 | 594 | 9 |
| 1 — hausse brutale du BSW | **4** | 114 | 10 | 128 | 3 |
| 2 — fermeture intempestive DHSV | 22 | 16 | 0 | 38 | 7 |
| 3 — severe slugging | 32 | 74 | 0 | 106 | **2** |
| 4 — instabilité d'écoulement | 343 | 0 | 0 | 343 | 7 |
| 5 — perte rapide de productivité | **11** | 439 | 0 | 450 | 3 |
| 6 — restriction rapide dans la PCK | **6** | 215 | 0 | 221 | **2** |
| 7 — dépôt (scaling) dans la PCK | 36 | 0 | 10 | 46 | 6 |
| 8 — hydrate en ligne de production | **14** | 81 | 0 | 95 | 9 |
| 9 — hydrate en ligne de service | 57 | 150 | 0 | 207 | 15 |
| **Total** | **1 119** | **1 089** | **20** | **2 228** | **39** |

**Instances réelles anormales : 525.** Les 1 089 instances simulées et 20 dessinées à la main
sont écartées et ne serviront jamais à gonfler `n`.

### INDEPENDENT_TEST_POSSIBLE : **YES**

L'identifiant du puits figure dans chaque nom de fichier, donc une séparation par puits est
constructible et la fuite est évitable par construction. 39 puits réels distincts. Le
découpage par ligne temporelle n'est jamais nécessaire.

C'est un **YES de faisabilité, pas de puissance** : la puissance échoue pour d'autres raisons,
traitées ci-dessous.

---

## 2. REAL_EVENT_GROUND_TRUTH : **FAIL**

### 2.1 Le type 9 n'a pas de vérité terrain exploitable

**43 des 57 instances réelles de type 9 (75,4 %) ne portent aucun label d'événement.** Leur
dictionnaire de labels est littéralement :

```
{'0': 73122}      {'0': 16094}      {'0': 15396}
```

Toutes les observations labellisées valent 0, c'est-à-dire *normal*, alors que le fichier est
rangé dans le répertoire de l'événement 9. L'instant de début est donc irrécupérable pour les
trois quarts de ce type. Sur les 8 autres types, ce phénomène est absent (0 instance sans
onset).

### 2.2 Toutes les instances ont une heure initiale non labellisée

**Chaque instance réelle commence par exactement 3 600 observations à `class = NA`** — une
heure à 1 Hz. Systématique, sur les 525 instances.

Les notes de version 2.0.0 affirment pourtant : « All labeling gaps in real instances were
eliminated (all observations were labeled) ». Le contenu du dépôt à ce commit contredit cette
affirmation.

### 2.3 Pour trois types, il n'existe aucune période normale labellisée avant l'événement

Médiane des observations labellisées `0` immédiatement avant l'onset :

| Type | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 |
|---|---|---|---|---|---|---|---|---|---|
| Pré-événement labellisé normal | 43 573 | 3 546 | **0** | **0** | 7 508 | 4 123 | 23 271 | 50 092 | **0** |

Pour les types 3, 4 et 9 — soit **432 des 525 instances réelles anormales, 82 %** — la seule
donnée pré-événement disponible est l'heure **non labellisée**.

Traiter `NA` comme « normal » serait une **hypothèse**, pas un label. C'est exactement le genre
de substitution que les phases précédentes ont refusé.

---

## 3. REAL_DATA_SUFFICIENT : **FAIL**

### 3.1 Effectifs par type

Demi-largeur d'IC de Wilson à 95 %, p = 0,5, au niveau instance :

| Type | n réel | IC 95 % | Demi-largeur |
|---|---|---|---|
| 1 | **4** | [0,150 ; 0,850] | **0,350** |
| 6 | **6** | [0,188 ; 0,812] | **0,312** |
| 5 | **11** | [0,213 ; 0,720] | 0,254 |
| 8 | **14** | [0,268 ; 0,732] | 0,232 |
| 2 | 22 | [0,307 ; 0,693] | 0,193 |
| 3 | 32 | [0,336 ; 0,664] | 0,164 |
| 7 | 36 | [0,345 ; 0,655] | 0,155 |
| 9 | 57 | [0,366 ; 0,617] | 0,126 |
| 4 | 343 | [0,446 ; 0,551] | **0,053** |

Le seuil établi en Phase 12A — 93 instances pour une demi-largeur ≤ 0,10 — n'est atteint que
par **le type 4**. Et 343 des 525 instances (65 %) sont de type 4 : le corpus réel est
essentiellement un corpus mono-événement.

### 3.2 Concentration par puits — le problème dominant

| Type | Puits | Part du puits le plus représenté |
|---|---|---|
| 3 | **2** | **96,9 %** (WELL-00014 : 31 des 32) |
| 2 | 7 | 59,1 % |
| 5 | **3** | 54,5 % |
| 7 | 6 | 52,8 % |
| 1 | **3** | 50,0 % |
| 6 | **2** | 50,0 % |
| 4 | 7 | 32,7 % |
| 8 | 9 | 28,6 % |
| 9 | 15 | 15,8 % |

Une séparation sans fuite doit être **par puits**. Or pour les types 1, 3, 5 et 6, il n'y a que
2 ou 3 puits : retirer un puits du train supprime la moitié à 97 % des instances de ce type.
Pour le type 3, retirer WELL-00014 laisse **une seule instance** en test.

Six types sur neuf ont un puits qui porte au moins la moitié de leurs instances : un modèle
entraîné dessus apprendrait le puits autant que l'événement.

### 3.3 Aucun canal commun

**Aucune des 27 variables n'est présente dans plus de 99,9 % des instances réelles anormales.**

| Variable | Présente dans |
|---|---|
| T-TPT | 94,9 % |
| P-TPT | 80,6 % |
| P-MON-CKP | 75,0 % |
| P-ANULAR | 73,7 % |
| P-PDG | 70,7 % |
| … | … |
| P-MON-SDV-P, P-JUS-BS, QBS, PT-P | **0,0 %** |

Quatre variables sont **entièrement absentes de toutes** les instances réelles anormales.
Exiger un socle commun coûte très cher :

| Socle commun | Instances retenues | Type 1 | Type 6 | Type 2 |
|---|---|---|---|---|
| T-TPT seul | 498 / 525 | 4 | 6 | 22 |
| + P-TPT | 406 / 525 | 4 | 6 | 21 |
| + P-MON-CKP | **275 / 525** | **3** | **3** | **6** |

Trois canaux communs — un minimum pour toute métrique multivariée — réduisent le corpus de
48 % et ramènent les types rares à 3 instances.

---

## 4. FO_3W_SEMANTICS : **INVALID**

FO consomme `delta[z, j, t]`, « l'écart causé par l'événement », et un `σ` par canal. 3W ne
fournit ni l'un ni l'autre.

| Exigence de FO | TEP | LeakDB | **3W** |
|---|---|---|---|
| Contrefactuel apparié | ✔ même graine, IDV=0 vs IDV=k, bit-identique avant la panne | ✔ le `.inp` livré EST le contrefactuel | **✘ impossible** — un puits réel ne se rejoue pas sans l'événement |
| σ déclaré | ✔ `XNS(1..41)` dans `teprob.f` | ✔ plancher de bruit mesuré empiriquement | **✘ aucune spécification de bruit** |
| Aucun plancher arbitraire | ✔ 41 valeurs, aucune nulle | ✔ | **✘ 4 canaux à 0 % de disponibilité** |

Les deux seuls contournements possibles sont explicitement interdits par la règle de
transposition :

1. **Redéfinir `delta`** comme écart à la période pré-événement. Ce n'est pas un
   contrefactuel : c'est un autre instant, qui confond l'événement avec la dérive du puits et
   les changements de point de fonctionnement. Et pour 82 % des instances cette période
   n'est même pas labellisée.
2. **Inventer `σ`** en l'estimant sur des périodes « normales » qui sont non labellisées, avec
   un plancher pour les canaux absents.

> Par la règle de la mission — « Si FO nécessite une nouvelle définition pour 3W :
> `FO_3W_SEMANTICS = INVALID` et FO est retiré de la validation 3W » — **FO est retiré.**

Ce verdict est cohérent avec la Phase 16 : FO s'y était révélé être `max |δ|/σ`, dont la valeur
propre au-delà des normes standards était WEAK. Il n'y a rien à sauver ici, et rien n'a été
tenté.

## 5. BSTAR_3W_SEMANTICS : **INVALID**

Deux blocages indépendants :

1. **B\* est construit sur `d_S`**, donc il hérite intégralement des blocages de FO : pas de
   contrefactuel, pas de σ.
2. **Il n'y a pas d'espace de designs à comparer.** B\*(S) compare des sous-ensembles de
   capteurs. Dans 3W, l'ensemble de canaux n'est pas un choix de design : il est dicté par ce
   que chaque puits a effectivement instrumenté, et il **varie d'une instance à l'autre**. La
   question à laquelle B\* répond ne se pose pas ici.

Le support gelé `E*` serait pré-enregistrable au sens procédural (item 12), mais sur une
quantité `d_R` qui n'est pas définissable. La procédure est valide, l'objet ne l'est pas.

## 6. ISOLABILITY_3W : **AMBIGUOUS**

**Conceptuellement bien définie** : 9 types d'événements labellisés, centroïdes de classe,
distance de Mahalanobis vers le type concurrent le plus proche, covariance estimable sur les
données. Aucun contrefactuel ni σ déclaré n'est requis. C'est le seul des trois axes qui
survive à la transposition.

**Pratiquement contrainte** :

- l'espace de features diffère d'une instance à l'autre (§3.3), donc les distances ne sont
  comparables qu'après restriction à un socle commun, qui coûte 48 % du corpus ;
- les centroïdes des types 1, 5 et 6 reposeraient sur 3 à 11 instances issues de 2 à 3 puits ;
- le type 9 n'a pas d'onset exploitable pour 75 % de ses instances.

D'où AMBIGUOUS plutôt que VALID : la notion tient, le corpus réel ne la porte pas.

## 7. Mesurabilité (item 18)

| Mesure | Possible ? |
|---|---|
| Détection | oui — labels binaires normal / anormal, une fois `NA` tranché |
| Délai de détection | **partiellement** — l'onset est exploitable pour 8 types sur 9 ; irrécupérable pour 75 % du type 9 |
| Classification | oui — 9 types |
| Taux de faux positifs | oui — 594 instances réelles de classe 0 |
| Confusion entre événements | oui, mais les lignes des types 1, 5, 6 reposeraient sur 4 à 11 instances |

Les labels transitoires (`TRANSIENT_OFFSET = 100`, donc `100 + k`) sont présents dans 6 types
sur 9 et permettraient une définition fine du délai — c'est un point fort du dataset, inutile
ici.

---

## 8. Verdict et arrêt

```
3W_ACCESS:                 PASS
REAL_DATA_SUFFICIENT:      FAIL
REAL_EVENT_GROUND_TRUTH:   FAIL
FO_3W_SEMANTICS:           INVALID
BSTAR_3W_SEMANTICS:        INVALID
ISOLABILITY_3W:            AMBIGUOUS
INDEPENDENT_TEST_POSSIBLE: YES
PHASE18_AUTHORIZED:        NO
```

**Causes de rejet, énoncées précisément :**

1. **Vérité terrain** — 43 des 57 instances réelles de type 9 ne portent aucun label
   d'événement ; toutes les instances ont 3 600 observations initiales non labellisées ; les
   types 3, 4 et 9 (82 % du corpus) n'ont aucune période normale labellisée avant l'onset.
2. **Effectifs** — 4 instances pour le type 1, 6 pour le type 6, 11 pour le type 5 ; le seuil
   de 93 n'est atteint que par le type 4, qui représente à lui seul 65 % du corpus.
3. **Concentration par puits** — 2 puits seulement pour les types 3 et 6, un puits portant
   96,9 % du type 3 ; six types sur neuf ont un puits majoritaire.
4. **Canaux** — aucune variable présente dans toutes les instances ; quatre entièrement
   absentes ; un socle de trois canaux coûte 48 % du corpus.
5. **FO et B\*** — nécessitent un contrefactuel et un σ déclaré que 3W ne fournit pas, et que
   la règle de transposition interdit d'inventer.

**Ce qui n'est pas en cause :** l'accès, la licence, la reproductibilité, la séparation
REAL/SIMULATED/HAND-DRAWN, et la possibilité d'un découpage sans fuite. 3W est un dépôt
exemplaire sur ces points. Ce qui échoue est l'adéquation entre ce corpus réel et la question
posée.

**Ce que je ne fais pas :** aucun protocole Phase 18 n'est écrit ; aucune instance simulée
n'est mobilisée pour compenser les effectifs réels ; aucune redéfinition de FO, de B\* ni de
`delta` n'est proposée. La branche s'arrête ici.

**Si la question devait être rouverte** — ce n'est pas ma décision — la seule voie honnête
serait une étude à périmètre réduit portant sur l'isolabilité standard seule, restreinte aux
types disposant d'au moins six puits (2, 4, 7, 8, 9) et à un socle de canaux déclaré à
l'avance, avec le type 9 écarté pour défaut de vérité terrain. Cela ne validerait pas
l'architecture sur données réelles : cela testerait un axe sur quatre types.

---

## 9. Livrables

```
phase17a_3w/RAPPORT_PHASE17A_GATE0_3W.md   ce rapport
phase17a_3w/AUDIT_SUMMARY.json             totaux et métadonnées du dépôt
phase17a_3w/INSTANCE_INVENTORY.csv         REAL / SIMULATED / HAND-DRAWN par type
phase17a_3w/REAL_INSTANCE_AUDIT.csv        1 119 instances réelles, une ligne chacune
phase17a_3w/REAL_PER_EVENT_TYPE.csv        synthèse par type d'événement
phase17a_3w/CHANNEL_AVAILABILITY.csv       disponibilité des 27 variables
phase17a_3w/WELL_BY_EVENT_TYPE.csv         structure puits × type
phase17a_3w/logs/audit.log                 journal d'exécution
phase17a_3w/SHA256SUMS.txt                 empreintes
src/phase17a_3w_audit.py                   audit rejouable
```

Le clone 3W (5,3 Go) n'est pas versionné ; le commit `93793db1` est enregistré et le clone est
reproductible depuis GitHub.
