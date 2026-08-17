# Protocole Phase 23-RT — Prospective Error-Risk Triage

**PRÉ-ENREGISTRÉ ET GELÉ. Écrit et commité AVANT toute ouverture du TEST.**
Contenu unique du **COMMIT A**. Aucune métrique TEST n'apparaît ici.

```
TEST_OPENED: NO
```

---

## 1. Hypothèse confirmatoire gelée

> **H23** — ISO_PRED apporte une information hors échantillon permettant de mieux classer les
> futures erreurs d'un classifieur que les seules mesures standards d'incertitude, et cet
> apport reste présent après combinaison avec ces mesures standards.

Cette phase ne teste **pas** : si ISO améliore les probabilités ; s'il recalibre un modèle ;
s'il augmente l'exactitude ; s'il constitue un classifieur ; s'il fonctionne spécifiquement en
faible confiance ; s'il explique causalement les erreurs.

Elle teste **uniquement la capacité de triage / priorisation du risque d'erreur**.

---

## 2. DÉVIATION DÉCLARÉE — le pool de données

**Le protocole demandé fixait `SOURCE_POOL = OpenML-CC18`. Ce pool est inatteignable depuis cet
environnement, et je le signale ici plutôt que de le contourner en silence.**

Sondage effectué avant tout gel, journalisé dans `logs/access_probe.log` :

| Cible | Réponse |
|---|---|
| `www.openml.org` API (étude 99) | **000 / refus du relais** |
| `api.openml.org` API | **000 / refus du relais** |
| `openml.org`, `test.openml.org` | **000 / refus du relais** |
| Définitions de suite candidates sur GitHub (`automlbenchmark`, `benchmark-suites`, `openml-python`) | **404** |
| PDF supplémentaire du papier « OpenML Benchmarking Suites » (`ml.informatik.uni-freiburg.de`) | **egress bloqué** |
| `raw.githubusercontent.com`, `api.github.com`, `pypi.org` | accessibles |

Conséquence : ni les données CC18, ni **la liste autoritative des 72 `task_id`** ne sont
obtenables. La règle « trier par `task_id` croissant » n'est donc **pas reproductible de manière
vérifiable** — la reconstituer de mémoire serait invérifiable et je m'y refuse.

### Décision, prise avant tout résultat

Deux options existaient :

1. déclarer `INCONCLUSIVE` pour impossibilité technique ;
2. substituer un pool **atteignable, curé, versionné et à manifeste déterministe**, en déclarant
   la déviation.

**L'option 2 est retenue.** Motif : l'option 1 masquerait derrière un problème de transport un
test qui est parfaitement exécutable sur des données entièrement nouvelles, ce que le §19 du
protocole demandé interdit explicitement (« INCONCLUSIVE … interdit pour faible puissance,
résultats proches de zéro, résultats contradictoires, résultats défavorables »). La question
scientifique de H23 ne dépend pas de l'identité du dépôt hébergeur.

```
SOURCE_POOL_REQUESTED : OpenML-CC18
SOURCE_POOL_USED      : PMLB — Penn Machine Learning Benchmarks,
                        manifeste pmlb/all_summary_stats.tsv,
                        transport raw.githubusercontent.com/EpistasisLab/pmlb
DEVIATION             : pool de données uniquement. Aucune autre règle du
                        protocole demandé n'est modifiée.
```

PMLB est un dépôt de référence public, versionné par commit git, dont le manifeste fournit pour
chaque jeu `n_instances`, `n_features`, `n_classes`, `imbalance` et `task`. Il compte **179 jeux
de classification**. L'appartenance éventuelle d'un jeu retenu à OpenML-CC18 sera **notée à
titre descriptif** dans le rapport et **n'entre dans aucun critère de sélection**.

Cette déviation est inscrite ici, **avant** l'ouverture du TEST, et sera répétée dans le
rapport final ainsi que dans la section `PROTOCOL_INTEGRITY`.

---

## 3. Exclusion historique — obligatoire

Inventaire construit automatiquement par balayage du dépôt (`.md`, `.py`, `.json`, `.txt`,
`.csv` de toutes les phases 10 à 22). Écrit dans `EXCLUSION_HISTORIQUE.json` au commit B.

**Exclusions imposées par le protocole demandé** : `CREDIT`, `GAS`, `DRYBEAN`, `SENSORLESS`,
`HAR`, `ZeMA`.

**Exclusions supplémentaires issues de l'inventaire du dépôt** : `SECOM`, `STEEL` (Steel Plates
Faults), `SCANIA` / `APS`, `TENNESSEE` / TEP, `LEAKDB`, `EPANET`, `3W`, `DIGITS`.

Tout nom de jeu PMLB contenant, en minuscules, l'un des jetons suivants est exclu :

```
credit, gas, bean, sensorless, har, zema, secom, steel, scania, aps,
tennessee, eastman, leak, epanet, 3w, digit, hydraulic
```

Le jeton `digit` exclut `optdigits` **et** `pendigits` : `optdigits` est la source de
`sklearn.datasets.load_digits` utilisée en Phase 13A, et `pendigits` est exclu par prudence.
Le jeton `har` est appliqué comme **mot entier** pour ne pas exclure abusivement des noms qui
le contiennent par hasard ; toute exclusion effective est journalisée avec son motif.

Aucune donnée historique n'apparaîtra dans un gate confirmatoire. Elle ne peut figurer qu'en
annexe descriptive.

---

## 4. Critères d'éligibilité, gelés

Un jeu candidat doit satisfaire **toutes** les conditions, vérifiées avant toute exécution :

| Critère | Seuil |
|---|---|
| tâche | classification supervisée |
| observations | **≥ 1 000** et **≤ 100 000** |
| variables utilisables | **≥ 5** et **≤ 500** après prétraitement |
| classes | **≥ 2** |
| effectif de la plus petite classe | **≥ 50** |
| texte libre nécessitant un modèle linguistique | absent |
| identifiant trivialement prédictif de la cible | absent |
| fuite manifeste de cible | absente |
| compatibilité avec les 4 familles gelées | oui |

La multiclassification est autorisée. Les trois scores probabilistes et les deux méta-modèles
doivent s'appliquer proprement.

**Contrôle anti-identifiant, gelé** : toute colonne dont le nombre de valeurs distinctes est
≥ 0,95 × n_observations est retirée avant tout calcul, et le retrait est journalisé.

---

## 5. Règle de sélection, gelée et aveugle

1. Partir des jeux de classification du manifeste PMLB.
2. Retirer les exclusions historiques du §3.
3. Retirer les jeux ne satisfaisant pas le §4 sur les métadonnées du manifeste.
4. **Trier les candidats restants par nom de jeu, ordre lexicographique croissant** (octets,
   `LC_ALL=C`). C'est l'analogue déterministe de « `task_id` croissant » sur un manifeste dont
   les identifiants numériques ne sont pas disponibles.
5. Parcourir cette liste dans l'ordre et retenir les **4 premiers jeux réellement exécutables**.
6. Toute tâche non exécutable est **journalisée avec sa cause et son identifiant conservé**, puis
   on passe à la suivante dans l'ordre déterministe.

**Aucune sélection selon** : exactitude, AUROC, ISO, difficulté, nombre d'erreurs, comportement
du modèle, intérêt apparent. **Aucune substitution après consultation d'une métrique TEST.**

```
MIN_DATASETS    = 3
TARGET_DATASETS = 4
```

Si moins de 3 jeux sont techniquement exécutables après effort raisonnable documenté :
`PHASE23_RESULT = INCONCLUSIVE`, **et pour cette seule cause technique**.

---

## 6. Familles de modèles, gelées

Exactement quatre, sans ajout, sans suppression, sans remplacement. Grilles minimales,
sélection par exactitude **sur CALIBRATION uniquement**, égalité tranchée par l'ordre de grille.

| # | Famille | Implémentation | Grille |
|---|---|---|---|
| M1 | Logistic Regression | `LogisticRegression(max_iter=5000)` | `C ∈ {0,1 ; 1 ; 10}` |
| M2 | Random Forest | `RandomForestClassifier(n_estimators=300)` | `min_samples_leaf ∈ {1 ; 5}` |
| M3 | Gradient Boosting | `HistGradientBoostingClassifier` | `learning_rate ∈ {0,05 ; 0,1}` |
| M4 | RBF-SVM | `SVC(kernel="rbf", probability=True)` | `C ∈ {1 ; 10}` |

`HistGradientBoostingClassifier` réalise la famille « Gradient Boosting » : choix
d'implémentation, pas changement de famille.

**Règle de coût gelée** : si `n_train > 10 000`, M4 est ajusté sur un sous-échantillon
stratifié de 10 000 lignes de TRAIN, graine gelée. Uniforme, indépendante de tout résultat.
Une cellule dépassant **120 minutes** ou ne convergeant pas est déclarée `NOT_EXECUTABLE`, avec
son motif, et **n'est pas remplacée**.

---

## 7. Split gelé

```
TRAIN = 60 %   CALIBRATION = 20 %   TEST = 20 %
SEED  = 23260823
```

Déterministe, stratifié par classe, identique pour tous les scores comparés dans une même
cellule. **Le TEST reste fermé jusqu'à ce que les commits A et B soient effectivement gelés et
poussés.** Aucune métrique TEST n'est calculée avant.

---

## 8. Prétraitement

Appris **sur TRAIN uniquement**, appliqué tel quel à CALIBRATION et TEST. CALIBRATION et TEST
n'influencent jamais l'imputation, la standardisation, l'encodage, le choix de variables ni
aucune transformation apprise.

Pipeline minimal et uniforme, identique pour tous les jeux :

1. retrait des colonnes quasi-identifiantes (§4) ;
2. retrait des colonnes constantes sur TRAIN ;
3. indicatrice de manquant pour toute colonne à plus de 5 % de manquants sur TRAIN ;
4. imputation par la médiane de TRAIN ;
5. `StandardScaler` ajusté sur TRAIN.

Aucune PCA. Aucune sélection de variables. Aucun rééquilibrage. Aucune augmentation. Aucun
traitement spécifique à un jeu n'est prévu ; s'il en fallait un, il serait documenté avant TEST.

---

## 9. Label d'erreur et variante ISO gelée

```
ERROR = 1  si  y_pred != y_true      ERROR = 0  sinon
```

`ISO_PRED` est la variante confirmatoire de la Phase 21-IR, réutilisée **sans aucune
modification** : la fonction `isolability` de `src/phase21_ir_iso.py`, copiée caractère pour
caractère depuis `src/phase20_dr_run.py` et vérifiée à l'import
(SHA-256 de la fonction `492c42dbee0b88c6e45867374da1c146a0d4d4df6fb6adf634b65931d57d6318`),
appelée avec `own` construit sur l'**étiquette prédite**.

Elle produit trois variables — `iso_d_nearest`, `iso_margin_ratio`, `iso_centroid_min` — avec
centroïdes de classe et covariance Ledoit-Wolf estimés **sur TRAIN seul**.

**Score de risque `ISO_PRED`, gelé** : `− iso_margin_ratio`. Une isolabilité relative élevée
signifie une prédiction bien séparée de ses concurrentes, donc peu risquée ; le signe est donc
inversé pour respecter la convention `HIGHER = MORE LIKELY ERROR`. Les trois variables entrent
en revanche toutes dans `ISO_META` (§11).

**Interdits** : utiliser `y_true` de l'observation évaluée dans la construction d'ISO ;
inventer une nouvelle variante ; employer `ISO_FROZEN` (variante oracle de la Phase 21) comme
candidat confirmatoire, ici ou en sauvetage.

---

## 10. Scores de risque standards

Pour chaque prédiction probabiliste `p`, sur `K` classes :

| # | Nom | Formule |
|---|---|---|
| B1 | `MCP_RISK` | `1 − max_k p_k` |
| B2 | `ENTROPY_RISK` | `− Σ_k p_k log p_k / log K`, avec `0·log 0 = 0` par bornage à `1e-300` |
| B3 | `MARGIN_RISK` | `1 − (p_(1) − p_(2))`, où `p_(1) ≥ p_(2)` sont les deux plus grandes |

Pour `K = 2`, `ENTROPY_RISK` est normalisée par `log 2`. Convention générale :
**plus le score est grand, plus la prédiction est risquée.**

---

## 11. Méta-modèles confirmatoires

Ajustés **sur CALIBRATION uniquement**, jamais sur TEST.

| Modèle | Entrées |
|---|---|
| `STANDARD_META` | `MCP_RISK` + `ENTROPY_RISK` + `MARGIN_RISK` |
| `ISO_META` | `MCP_RISK` + `ENTROPY_RISK` + `MARGIN_RISK` + `ISO_PRED` |

`ISO_PRED` entre ici sous forme de ses **trois variables** en `signe(x)·log1p(|x|)`, comme aux
phases précédentes.

Contraintes : `LogisticRegression(penalty="l2", C=1.0, max_iter=5000)` dans les deux cas ;
`StandardScaler` ajusté sur CALIBRATION dans les deux cas ; mêmes observations ; même split ;
**aucune différence autre que l'ajout d'ISO**. Aucun réglage utilisant TEST.

Comparaison principale : **`ISO_META` contre `STANDARD_META`**.

Scores évalués par cellule : `ISO_PRED`, `MCP_RISK`, `ENTROPY_RISK`, `MARGIN_RISK`,
`STANDARD_META`, `ISO_META`.

---

## 12. Métrique globale principale — AUGRC

Trier les `N` observations TEST par score de risque **croissant** (les plus confiantes d'abord).
Soit `e_i ∈ {0,1}` l'indicatrice d'erreur dans cet ordre. Pour `k = 1 … N` :

```
couverture         c_k = k / N
risque généralisé  g_k = (1/N) · Σ_{i=1..k} e_i
AUGRC              = (1/N) · Σ_{k=1..N} g_k
```

Le risque **généralisé** rapporte les erreurs acceptées à l'effectif **total**, non au seul
effectif accepté — c'est ce qui distingue AUGRC de AURC et lui évite l'instabilité de AURC aux
faibles couvertures.

```
LOWER_IS_BETTER: YES
```

Secondaire, avec risque conditionnel classique :

```
risque  r_k = (1/k) · Σ_{i=1..k} e_i        AURC = (1/N) · Σ_{k=1..N} r_k
```

`AURC` est rapportée mais **ne décide seule d'aucun verdict**. Les deux implémentations sont
vérifiées par les tests unitaires du §17.

---

## 13. Métriques opérationnelles

Trier les observations TEST du **plus risqué au moins risqué**. Pour `q ∈ {5 %, 10 %, 20 %}`,
avec `m = ⌈q·N⌉` :

```
ERROR_CAPTURE@q   = (erreurs parmi les m plus risquées) / (erreurs totales TEST)
RESIDUAL_ERROR@q  = (erreurs parmi les N − m restantes) / (N − m)
LIFT@q            = ERROR_CAPTURE@q / q            (q en décimal)
```

---

## 14. Point opérationnel à seuil gelé

Simulation de déploiement réel. **Sur CALIBRATION uniquement** : pour chaque score, choisir le
seuil correspondant à `TARGET_REJECTION_RATE = 10 %` (quantile 0,90 du score sur CALIBRATION),
puis **geler ce seuil** et l'appliquer tel quel au TEST.

Rapporter `ACHIEVED_REJECTION_RATE_TEST`, `ACHIEVED_COVERAGE_TEST`, `ERROR_CAPTURE_TEST`,
`RESIDUAL_ERROR_TEST`. **Aucun réajustement du seuil sur TEST.**

---

## 15. Comparaison principale

```
DELTA_AUGRC              = AUGRC_STANDARD_META − AUGRC_ISO_META
DELTA_ERROR_CAPTURE_10   = ERROR_CAPTURE_10_ISO_META − ERROR_CAPTURE_10_STANDARD_META
DELTA_RESIDUAL_ERROR_10  = RESIDUAL_ERROR_10_STANDARD_META − RESIDUAL_ERROR_10_ISO_META
```

Convention : **positif = amélioration apportée par ISO**.

---

## 16. Statistiques

```
N_BOOTSTRAP = 10 000        CI = 95 %
```

Bootstrap **apparié** sur les observations TEST : chaque tirage rééchantillonne **les mêmes
indices conjointement** pour `STANDARD_META` et `ISO_META`. IC produits pour `DELTA_AUGRC`,
`DELTA_ERROR_CAPTURE_10`, `DELTA_RESIDUAL_ERROR_10`.

p-value bilatérale : `p = 2 · min( P(Δ ≤ 0), P(Δ ≥ 0) )`, bornée à 1.
Multiplicité : **correction de Holm** sur les tests cellulaires confirmatoires de `DELTA_AUGRC`.
Les tirages bootstrap ne sont **jamais** traités comme des observations indépendantes.

---

## 17. Tests unitaires obligatoires, avant TEST

À exécuter et faire passer avant toute ouverture du TEST, sur données synthétiques contrôlées :

1. un score parfait trie mieux qu'un score aléatoire (AUGRC et AURC plus faibles) ;
2. un score inversé trie mal (AUGRC plus élevé que l'aléatoire) ;
3. `ERROR_CAPTURE@10 = 1` si toutes les erreurs sont dans les 10 % les plus risqués ;
4. `LIFT@q` est exact sur un cas calculé à la main ;
5. AUGRC respecte `LOWER_IS_BETTER` ;
6. `STANDARD_META` et `ISO_META` utilisent exactement les mêmes observations ;
7. le bootstrap est apparié (mêmes indices pour les deux scores) ;
8. aucune étiquette TEST n'entre dans `ISO_PRED` ;
9. les trois splits ne se chevauchent pas et couvrent tout ;
10. le prétraitement appris sur TRAIN ne fuit ni vers CALIBRATION ni vers TEST.

Tout test défaillant est corrigé **avant** ouverture du TEST.

---

## 18. Agrégation multi-jeux

Produire : médiane des deltas sur toutes les cellules ; moyenne descriptive ; nombre de cellules
positives, négatives, compatibles avec zéro ; résultats par jeu ; résultats par famille ;
résultats **hors Random Forest**.

Explicitement :
`MEDIAN_DELTA_AUGRC_ALL`, `MEDIAN_DELTA_ERROR_CAPTURE_10_ALL`,
`MEDIAN_DELTA_RESIDUAL_ERROR_10_ALL`, et les mêmes en `*_NO_RF`.

**Random Forest ne doit jamais suffire seule à faire passer un gate.**

---

## 19. Gates confirmatoires, codés littéralement avant TEST

### GATE 1 — `ERROR_RISK_REPLICATED`

Vérifie que la propriété de la Phase 21 — ISO ordonne les erreurs mieux que le hasard —
survit sur données entièrement nouvelles. Métrique de ranking : **AUROC de `ISO_PRED` pour
prédire `ERROR` sur TEST**, avec IC bootstrap 95 %.

`YES` si **toutes** les conditions tiennent :

- AUROC médiane d'`ISO_PRED` sur les cellules exécutées **≥ 0,55** ;
- IC 95 % strictement au-dessus de 0,50 dans **≥ ⅔ des cellules** ;
- effet présent dans **≥ 2 jeux** et **≥ 2 familles** ;
- les trois points précédents tiennent encore **après retrait de Random Forest**.

Ce gate ne peut **jamais** servir seul à revendiquer une utilité produit.

### GATE 2 — `INCREMENTAL_TRIAGE`

`YES` seulement si **simultanément** :

- `MEDIAN_DELTA_AUGRC_ALL > 0` ;
- `MEDIAN_DELTA_ERROR_CAPTURE_10_ALL > 0` ;
- l'effet n'est pas limité à une seule cellule : **≥ 3 cellules** avec `DELTA_AUGRC > 0` dont
  l'IC apparié exclut 0, réparties sur **≥ 2 jeux** ;
- l'IC bootstrap agrégé de `DELTA_AUGRC` (stratifié, chaque jeu de poids égal) **exclut 0 du
  côté favorable**.

Une seule cellule spectaculaire ne suffit jamais.

### GATE 3 — `ROBUST_ACROSS_DATASETS`

`YES` seulement si le gain apparaît dans la majorité des jeux exécutables : **≥ 3 sur 4**, ou
**≥ 2 sur 3**. Un jeu est positif si sa médiane de `DELTA_AUGRC` sur les quatre familles est
> 0 **et** sa médiane de `DELTA_ERROR_CAPTURE_10` est > 0.

### GATE 4 — `ROBUST_ACROSS_MODELS`

`YES` seulement si la médiane de `DELTA_AUGRC` est > 0 dans **≥ 3 des 4 familles** **et** si
`MEDIAN_DELTA_AUGRC_NO_RF > 0` avec `MEDIAN_DELTA_ERROR_CAPTURE_10_NO_RF > 0`.
Si Random Forest est indispensable : `ROBUST_ACROSS_MODELS = NO`.

### GATE 5 — `OPERATIONAL_GAIN`

Gate de valeur pratique. `YES` seulement si :

- `MEDIAN_DELTA_ERROR_CAPTURE_10_ALL ≥ +0,05` — au moins **+5 points de pourcentage** d'erreurs
  supplémentaires capturées à budget de revue de 10 %, en médiane ;
- **et** `MEDIAN_DELTA_RESIDUAL_ERROR_10_ALL > 0`.

Un gain purement statistique microscopique ne suffit pas.

---

## 20. Verdicts pré-définis

```
ERROR_RISK_REPLICATED:
INCREMENTAL_TRIAGE:
ROBUST_ACROSS_DATASETS:
ROBUST_ACROSS_MODELS:
OPERATIONAL_GAIN:

PHASE23_RESULT:
BRANCH_DECISION:
```

- **SUPPORTED** si les cinq gates valent `YES` → `BRANCH_DECISION: ADVANCE_TO_PRODUCT_VALIDATION`.
- **FALSIFIED, falsification applicative** si `ERROR_RISK_REPLICATED = YES` mais qu'un ou
  plusieurs gates d'utilité incrémentale échouent → `CLOSE_APPLICATIVE_ISO_BRANCH`.
  En particulier `INCREMENTAL_TRIAGE = NO` suffit à empêcher toute progression produit.
- **FALSIFIED, échec de réplication** si `ERROR_RISK_REPLICATED = NO` →
  `CLOSE_APPLICATIVE_ISO_BRANCH`, en documentant que la propriété de la Phase 21 reste un
  résultat historique valide sur son périmètre mais ne se réplique pas prospectivement ici.
- **INCONCLUSIVE** uniquement pour : moins de 3 jeux confirmatoires réellement exécutables ;
  corruption de données ; impossibilité technique empêchant une exécution conforme ; violation
  irréparable du protocole avant ouverture du TEST. **Interdit** pour faible puissance,
  résultats proches de zéro, résultats contradictoires ou défavorables.

---

## 21. Aucun sauvetage post-hoc

```
NO_RESCUE_ANALYSIS: TRUE
```

Après ouverture du TEST, interdiction de : changer ISO ; essayer `ISO_FROZEN` comme candidat
confirmatoire ; changer un seuil ; chercher d'autres quantiles ; ajouter 1 %, 2 %, 15 %, 30 %
parce qu'ils sont meilleurs ; ajouter ou retirer un modèle ; changer la sélection de jeux ;
chercher un sous-groupe ; chercher une dérive temporelle ; réutiliser
`NATURAL_TEMPORAL_SHIFT` ; tester de nouvelles transformations ; faire de l'ingénierie de
variables ISO ; introduire une combinaison post-hoc.

Le signal `NATURAL_TEMPORAL_SHIFT` de la Phase 22 **n'est ni une hypothèse ni un critère** de
cette phase. Toute curiosité secondaire va dans `EXPLORATORY_APPENDIX` et ne modifie aucun
verdict. Idéalement, aucune analyse exploratoire n'est lancée.

`src/fo_metrics.py` reste inchangé et non importé. FO, B\*, Visibility, Robustness, R7 sont
absents.

---

## 22. Structure des commits

| Commit | Contenu | Règle |
|---|---|---|
| **A** | ce protocole seul | poussé avant toute ouverture du TEST — `TEST_OPENED: NO` |
| **B** | jeux candidats, exclus et retenus, motifs, empreintes, effectifs, classes, indices TRAIN/CALIB/TEST, graines, exécutabilité | aucune métrique TEST — `TEST_OPENED: NO` |
| code | scripts, implémentation AUGRC, tests unitaires, calculs CALIBRATION | ne remplace jamais A, B ou C |
| **C** | ouverture du TEST, toutes les cellules, toutes les métriques, bootstrap, Holm, agrégations, hors-RF, gates, verdict, décision de branche | seulement après A et B |

Avant le commit C, vérifier par `git diff` que le protocole, la définition d'ISO, les jeux, les
splits, les modèles et les gates n'ont pas changé, et produire la section
`PROTOCOL_INTEGRITY` du rapport.

---

**Graine globale : 23260823. Bootstrap : 10 000. Correction : Holm.
Seuil opérationnel : +0,05 de `DELTA_ERROR_CAPTURE_10` en médiane. AUGRC : plus bas est
meilleur.**

---

## AMENDEMENT 1 — 2026-08-17, avant toute ouverture du TEST

```
TEST_OPENED: NO
```

**Objet : l'ordre lexicographique gelé du §5 sélectionne des jeux quasi-dupliqués.**

Vérification faite après application des §3 et §4 au manifeste PMLB, **avant tout téléchargement
de données et avant tout modèle** : sur 179 jeux de classification, 8 sont exclus par
l'historique et 108 sont inéligibles sur métadonnées, laissant 63 candidats. Les sept premiers
dans l'ordre lexicographique gelé sont :

```
GAMETES_Epistasis_2_Way_20atts_0.1H_EDM_1_1
GAMETES_Epistasis_2_Way_20atts_0.4H_EDM_1_1
GAMETES_Epistasis_3_Way_20atts_0.2H_EDM_1_1
GAMETES_Heterogeneity_20atts_1600_Het_0.4_0.2_50_EDM_2_001
GAMETES_Heterogeneity_20atts_1600_Het_0.4_0.2_75_EDM_2_001
Hill_Valley_with_noise
Hill_Valley_without_noise
```

Appliquer la règle à la lettre retiendrait **quatre variantes du même simulateur GAMETES**,
différant seulement par leur héritabilité. Les gates 2, 3 et 4 exigent une robustesse « sur
plusieurs jeux indépendants » ; quatre paramétrages d'un même générateur ne sont pas des jeux
indépendants, et le gate `ROBUST_ACROSS_DATASETS` serait vidé de sens. De même,
`Hill_Valley_with_noise` et `_without_noise` sont la même base.

**Correction retenue, purement structurelle et aveugle aux résultats.** Trois règles s'ajoutent
au §5, appliquées *avant* le tri :

1. **Déduplication par famille.** Clé de famille = **premier jeton du nom découpé sur `_`**, en
   minuscules. Au plus **un** jeu par famille est conservé : le **premier dans l'ordre
   lexicographique**. Mécanique, sans jugement.
2. **Exclusion des jeux `_deprecated_*`**, que PMLB marque comme remplacés et qui dupliquent des
   jeux conservés par ailleurs.
3. **Exclusion des jeux `mfeat_*`** — UCI *Multiple Features*, chiffres manuscrits : même source
   que les données `digits` employées en Phase 13A, que le jeton `digit` du §3 ne captait pas.

Ces règles ne dépendent d'aucune performance, d'aucun modèle, d'aucune métrique et d'aucune
donnée téléchargée : uniquement des **noms** du manifeste. Elles retirent 20 candidats et en
laissent **43**. Les quatre premiers deviennent :

| # | Jeu | n | p | K |
|---|---|---|---|---|
| 1 | `GAMETES_Epistasis_2_Way_20atts_0.1H_EDM_1_1` | 1 600 | 20 | 2 |
| 2 | `Hill_Valley_with_noise` | 1 212 | 100 | 2 |
| 3 | `adult` | 48 842 | 14 | 2 |
| 4 | `agaricus_lepiota` | 8 145 | 22 | 2 |

**Objet second : évaluabilité d'une cellule, seuils gelés ici.**

1. **Avant TEST**, sur CALIBRATION uniquement : une cellule dont le classifieur produit
   **moins de 20 erreurs sur CALIBRATION** est déclarée `NOT_EXECUTABLE`, car ni les
   méta-modèles ni le seuil opérationnel ne peuvent y être ajustés. Si **les quatre familles**
   d'un jeu échouent ainsi, ce jeu est `NOT_EXECUTABLE` et la marche déterministe **continue au
   candidat suivant**, exactement comme le prévoit le §5 pour toute tâche non exécutable.
2. **Après ouverture du TEST** : une cellule comptant **moins de 20 erreurs sur TEST** est
   déclarée `NOT_EVALUABLE_LOW_EVENTS`, rapportée avec son effectif, et **exclue des
   agrégations**. Elle n'est pas remplacée.

Ces deux seuils sont gelés ici, avant tout accès au TEST, et reprennent la valeur déjà utilisée
en Phase 21-IR.

Aucun résultat, aucune métrique et aucune donnée téléchargée n'existaient au moment de cet
amendement : la chronologie est vérifiable dans l'historique git. Cet amendement ne pourra pas
être révisé.
