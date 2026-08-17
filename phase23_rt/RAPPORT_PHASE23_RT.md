# Phase 23-RT — Prospective Error-Risk Triage

## A. Executive verdict

```
ERROR_RISK_REPLICATED:        NO
INCREMENTAL_TRIAGE:           YES
ROBUST_ACROSS_DATASETS:       NO
ROBUST_ACROSS_MODELS:         YES
OPERATIONAL_GAIN:             NO

PHASE23_RESULT:               FALSIFIED
BRANCH_DECISION:              CLOSE_APPLICATIVE_ISO_BRANCH
```

Trois des cinq gates confirmatoires échouent, dont le gate de valeur pratique. Le gain
opérationnel médian est **+0,004** d'erreurs capturées à budget de revue de 10 %, contre
**+0,05 exigés** — douze fois trop petit — et il **change de signe** dans la simulation de
déploiement à seuil gelé, où la médiane devient **−0,004**.

---

## B. PROTOCOL_INTEGRITY

```
PROTOCOL_CHANGED_AFTER_TEST:  NO
ISO_CHANGED_AFTER_TEST:       NO
DATASETS_CHANGED_AFTER_TEST:  NO
MODELS_CHANGED_AFTER_TEST:    NO
METRICS_CHANGED_AFTER_TEST:   NO
GATES_CHANGED_AFTER_TEST:     NO
CONFIRMATORY_VALIDITY:        VALID
```

| Étape | Commit | État |
|---|---|---|
| **A** protocole gelé | `e531cd7` | SHA-256 `524ebbb7…a838bcffcd`, `TEST_OPENED: NO` |
| Amendement 1 | `b870d5e` | avant TEST, avant tout téléchargement — SHA-256 `19c17f52…8c33829e` |
| **B** data gate | `91837b1` | `TEST_OPENED: NO`, aucune métrique TEST |
| code + tests + CALIB | `b253b3a` | `TEST_OPENED: NO`, 13/13 tests unitaires passés |
| **C** résultats | ce commit | TEST ouvert une seule fois |

Vérifications exécutées avant le commit C : `git diff b870d5e -- phase23_rt/PROTOCOLE_PHASE23_RT.md`
**vide** ; `git diff e531cd7 -- src/phase21_ir_iso.py src/phase20_dr_run.py src/fo_metrics.py`
**vide** ; `git diff 91837b1 -- phase23_rt/DATA_GATE.json phase23_rt/SPLIT_*.csv` **vide**.
`src/fo_metrics.py` = `f17cd735…de486c79`, inchangé et non importé. La fonction `isolability`
est vérifiée verbatim à l'import (`492c42db…d57d6318`). `ISO_FROZEN`, variante oracle, n'est
utilisée nulle part.

### Déviation déclarée avant le gel

`SOURCE_POOL` demandé = **OpenML-CC18**, **inatteignable** : `www.openml.org`,
`api.openml.org`, `openml.org` et `test.openml.org` répondent 000 au travers du relais ; les
définitions de suite candidates sur GitHub renvoient 404 ; le PDF supplémentaire du papier
*OpenML Benchmarking Suites* est bloqué par l'egress. Ni les données, ni la **liste autoritative
des 72 `task_id`** ne sont obtenables, donc la règle « trier par `task_id` croissant » n'est pas
reproductible de manière vérifiable.

`SOURCE_POOL` utilisé = **PMLB**, manifeste `pmlb/all_summary_stats.tsv`
(SHA-256 `d658820a…2cc33960`), 179 jeux de classification, transport
`media.githubusercontent.com` (les fichiers PMLB sont en Git LFS ; `raw.githubusercontent.com`
ne renvoie que le pointeur). **La déviation porte sur le pool seul** ; aucune autre règle n'a
été modifiée. Elle a été inscrite dans le commit A, avant tout accès aux données. Le motif est
que déclarer `INCONCLUSIVE` aurait masqué derrière un problème de transport un test parfaitement
exécutable sur des données entièrement nouvelles — ce que le protocole demandé interdit.

---

## C. Datasets

Sur 179 jeux de classification : **8 exclus par l'historique**, **108 inéligibles** sur
métadonnées, **20 retirés par l'amendement 1**, laissant 43 candidats. Marche déterministe dans
l'ordre lexicographique, aveugle à toute performance.

### Exclusions historiques appliquées

Imposées : `CREDIT`, `GAS`, `DRYBEAN`, `SENSORLESS`, `HAR`, `ZeMA`.
Issues du balayage automatique du dépôt (17 jetons trouvés dans les phases 10 à 22) : `SECOM`,
`STEEL`, `SCANIA`/`APS`, `TENNESSEE`/TEP, `LEAKDB`, `EPANET`, `3W`, `DIGITS`, `HYDRAULIC`.
Effectivement retirés de PMLB : `_deprecated_credit_a`, `_deprecated_credit_g`,
`analcatdata_creditscore`, `credit_approval_australia`, `credit_approval_germany`, `optdigits`,
`pendigits`, `soybean`. **Aucun jeu retenu n'appartient à l'historique du dépôt.**

### Trail complet de la marche, tout saut journalisé

| Candidat | Statut | Cause |
|---|---|---|
| `GAMETES_Epistasis_2_Way_20atts_0.1H_EDM_1_1` | **EXECUTABLE** | — |
| `Hill_Valley_with_noise` | NOT_ELIGIBLE | `p = 0` hors [5, 500] |
| `adult` | **EXECUTABLE** | — |
| `agaricus_lepiota` | **EXECUTABLE** | — |
| `allbp` | NOT_ELIGIBLE | plus petite classe 14 < 50 |
| `allhyper` | NOT_ELIGIBLE | plus petite classe 10 < 50 |
| `allhypo` | **EXECUTABLE** | — |

### Jeux retenus, splits 60/20/20 stratifiés, graine 23260823

| Jeu | n | p | K | plus petite classe | TRAIN | CALIB | TEST | SHA-256 (préfixe) |
|---|---|---|---|---|---|---|---|---|
| GAMETES_Epistasis_2_Way | 1 600 | 20 | 2 | 800 | 960 | 320 | 320 | `679309c8e1362d0d` |
| adult | 48 842 | 14 | 2 | 11 687 | 29 305 | 9 769 | 9 768 | `fb8bc76eafa39558` |
| agaricus_lepiota | 8 145 | 22 | 2 | 3 917 | 4 887 | 1 629 | 1 629 | `cd9fc8d6cdc07793` |
| allhypo | 3 770 | 29 | 3 | 95 | 2 262 | 754 | 754 | `7e9d156208d5310d` |

Toutes les classes sont présentes dans chacun des trois splits, partition exacte vérifiée.
`adult` et `agaricus_lepiota` appartiennent aussi à OpenML-CC18 — **note descriptive, sans
effet sur la sélection**.

### Cellules non exécutables, décidées sur CALIBRATION seule, avant TEST

| Cellule | Cause |
|---|---|
| `agaricus_lepiota` / RF, GBM, SVM | **0 erreur** sur CALIBRATION < 20 — le jeu est séparable |
| `allhypo` / GBM | 14 erreurs sur CALIBRATION < 20 |

**12 des 16 cellules sont exécutables**, réparties sur les **4 jeux**. Aucune n'est remplacée.
Aucune cellule n'a été déclarée `NOT_EVALUABLE_LOW_EVENTS` après ouverture du TEST.

---

## D. Résultats par cellule

`DELTA_AUGRC = AUGRC(STANDARD_META) − AUGRC(ISO_META)` — positif = ISO améliore.
AUGRC : **plus bas est meilleur**.

| Jeu / modèle | exact. TEST | erreurs | AUGRC std | AUGRC ISO | **Δ AUGRC** | IC 95 % | p brute | Holm | AUROC(ISO_PRED) |
|---|---|---|---|---|---|---|---|---|---|
| GAMETES / LogReg | 0,4688 | 170 | 0,26208 | 0,25659 | +0,00549 | [−0,0064 ; +0,0173] | 0,365 | non | 0,549 |
| GAMETES / RF | 0,5656 | 139 | 0,20477 | 0,19598 | +0,00879 | [−0,0058 ; +0,0241] | 0,240 | non | 0,484 |
| GAMETES / GBM | 0,6469 | 113 | 0,16493 | 0,16294 | +0,00199 | [−0,0087 ; +0,0130] | 0,712 | non | 0,475 |
| GAMETES / SVM | 0,5312 | 150 | 0,23511 | 0,22410 | +0,01101 | [−0,0024 ; +0,0242] | 0,113 | non | 0,486 |
| adult / LogReg | 0,8316 | 1 645 | 0,04368 | 0,04340 | +0,00028 | [+0,00001 ; +0,00055] | 0,040 | non | **0,695** |
| adult / RF | 0,8662 | 1 307 | 0,02714 | 0,02709 | +0,00005 | [−0,0001 ; +0,0002] | 0,539 | non | **0,711** |
| adult / GBM | 0,8755 | 1 216 | 0,02398 | 0,02403 | **−0,00005** | [−0,0002 ; +0,0001] | 0,322 | non | **0,702** |
| adult / SVM | 0,8467 | 1 497 | 0,03907 | 0,03710 | +0,00197 | [+0,0014 ; +0,0025] | 0,000 | **✓** | **0,707** |
| agaricus / LogReg | 0,9755 | 40 | 0,00391 | 0,00140 | +0,00251 | [+0,0010 ; +0,0043] | 0,000 | **✓** | 0,495 |
| allhypo / LogReg | 0,9377 | 47 | 0,00814 | 0,00974 | **−0,00160** | [−0,0030 ; −0,0004] | 0,010 | non | **0,750** |
| allhypo / RF | 0,9536 | 35 | 0,00293 | 0,00241 | +0,00052 | [−0,00004 ; +0,0011] | 0,070 | non | **0,738** |
| allhypo / SVM | 0,9390 | 46 | 0,01043 | 0,00971 | +0,00072 | [−0,0003 ; +0,0019] | 0,168 | non | **0,749** |

**Après correction de Holm : 2 cellules sur 12** survivent (adult/SVM, agaricus/LogReg).
Une cellule montre une **perte significative** (allhypo/LogReg, −0,0016, IC entièrement négatif).

### AUGRC médiane par score, 12 cellules

| Score | AUGRC médiane |
|---|---|
| `ISO_PRED` seul | **0,0461** |
| `MCP_RISK` | 0,0331 |
| `ENTROPY_RISK` | 0,0331 |
| `MARGIN_RISK` | 0,0331 |
| `STANDARD_META` | 0,0331 |
| **`ISO_META`** | **0,0321** |

`ISO_PRED` seul est **moins bon que n'importe lequel des trois scores standards** dans les 12
cellules. Note structurelle : trois des quatre jeux sont binaires, et pour `K = 2` les trois
scores standards sont des transformations monotones l'un de l'autre — ils sont donc exactement
à égalité partout sauf sur `allhypo` (`K = 3`). C'est une conséquence du tirage aveugle, pas un
choix.

### ERROR_CAPTURE, RESIDUAL_ERROR et LIFT à 10 %

| Jeu / modèle | EC@10 std | EC@10 ISO | **Δ EC@10** | IC 95 % | RE@10 std | RE@10 ISO | Δ RE@10 |
|---|---|---|---|---|---|---|---|
| GAMETES / LogReg | 0,1000 | 0,1059 | +0,0059 | [−0,0114 ; +0,0241] | 0,5313 | 0,5278 | +0,0035 |
| GAMETES / RF | 0,1007 | 0,1439 | +0,0432 | [0,0000 ; +0,0972] | 0,4340 | 0,4132 | +0,0208 |
| GAMETES / GBM | 0,0797 | 0,1150 | +0,0354 | [−0,0374 ; +0,0855] | 0,3611 | 0,3472 | +0,0139 |
| GAMETES / SVM | 0,0733 | 0,1200 | +0,0467 | [0,0000 ; +0,0942] | 0,4826 | 0,4583 | +0,0243 |
| adult / LogReg | 0,2571 | 0,2730 | +0,0158 | [+0,0013 ; +0,0288] | 0,1390 | 0,1361 | +0,0030 |
| adult / RF | 0,3236 | 0,3259 | +0,0023 | [−0,0122 ; +0,0151] | 0,1006 | 0,1002 | +0,0003 |
| adult / GBM | 0,3322 | 0,3273 | −0,0049 | [−0,0133 ; +0,0058] | 0,0924 | 0,0931 | −0,0007 |
| adult / SVM | 0,2739 | 0,2886 | +0,0147 | [−0,0034 ; +0,0323] | 0,1237 | 0,1212 | +0,0025 |
| agaricus / LogReg | 0,8000 | 0,8000 | **0,0000** | [0,0000 ; +0,0435] | 0,0055 | 0,0055 | 0,0000 |
| allhypo / LogReg | 0,5745 | 0,5745 | **0,0000** | [−0,0800 ; +0,0625] | 0,0295 | 0,0295 | 0,0000 |
| allhypo / RF | 0,8571 | 0,8571 | **0,0000** | [−0,1579 ; +0,1795] | 0,0074 | 0,0074 | 0,0000 |
| allhypo / SVM | 0,6087 | 0,5652 | −0,0435 | [−0,0962 ; 0,0000] | 0,0266 | 0,0295 | −0,0030 |

Sur **3 cellules**, l'ajout d'ISO ne change **rien du tout** au contenu des 10 % les plus
risqués. Les tables complètes à 5 % et 20 % avec les LIFT sont dans `CELL_SCORES.csv`.

---

## E. Agrégation par jeu

| Jeu | médiane Δ AUGRC | médiane Δ EC@10 | positif au sens du gate 3 |
|---|---|---|---|
| GAMETES | +0,007139 | +0,039282 | **oui** |
| adult | +0,000165 | +0,008496 | **oui** |
| agaricus_lepiota | +0,002510 | 0,000000 | non — Δ EC@10 nul |
| allhypo | +0,000519 | 0,000000 | non — Δ EC@10 nul |

**2 jeux positifs sur 4**, alors que le gate 3 en exige 3.

## F. Agrégation par famille de modèle

| Famille | médiane Δ AUGRC | médiane Δ EC@10 |
|---|---|---|
| Logistic Regression | +0,000280 | +0,002941 |
| Random Forest | +0,000520 | +0,002295 |
| Gradient Boosting | +0,000971 | +0,015232 |
| RBF-SVM | +0,001970 | +0,014696 |

**4 familles sur 4** ont une médiane positive.

## G. Analyse sans Random Forest — confirmatoire

| Quantité | Toutes cellules | Sans Random Forest |
|---|---|---|
| `MEDIAN_DELTA_AUGRC` | **+0,001344** | **+0,001970** |
| `MEDIAN_DELTA_ERROR_CAPTURE_10` | **+0,004089** | **+0,005882** |
| `MEDIAN_DELTA_RESIDUAL_ERROR_10` | +0,001422 | +0,002503 |
| AUROC médiane d'`ISO_PRED` | 0,6986 | 0,6950 |

Le résultat ne dépend **pas** de Random Forest : les médianes hors RF sont même légèrement
supérieures. Random Forest n'est nécessaire à aucun gate, et son retrait n'en sauve aucun non
plus. `MEAN_DELTA_AUGRC_ALL` = +0,002639, `n_positive` = 10/12, `n_negative` = 2/12,
`IC contenant 0` = **8/12**.

## H. Simulation de déploiement à seuil gelé

Seuil pris au quantile 0,90 de chaque score **sur CALIBRATION**, puis appliqué tel quel au TEST,
sans aucun réajustement.

| Jeu / modèle | rejet réalisé std | rejet réalisé ISO | EC std | EC ISO | **Δ EC** |
|---|---|---|---|---|---|
| GAMETES / LogReg | 0,1281 | 0,1156 | 0,1353 | 0,1235 | −0,0118 |
| GAMETES / RF | 0,1156 | 0,1000 | 0,1151 | 0,1439 | +0,0288 |
| GAMETES / GBM | 0,1000 | 0,0844 | 0,0796 | 0,0885 | +0,0089 |
| GAMETES / SVM | **0,1750** | **0,0688** | 0,1600 | 0,0933 | **−0,0667** |
| adult / LogReg | 0,0985 | 0,1035 | 0,2541 | 0,2796 | +0,0255 |
| adult / RF | 0,1036 | 0,0988 | 0,3321 | 0,3213 | −0,0107 |
| adult / GBM | 0,0983 | 0,0969 | 0,3248 | 0,3166 | −0,0082 |
| adult / SVM | 0,0974 | 0,0937 | 0,2645 | 0,2712 | +0,0067 |
| agaricus / LogReg | 0,0964 | 0,0878 | 0,8000 | 0,8000 | 0,0000 |
| allhypo / LogReg | 0,0995 | 0,0995 | 0,5745 | 0,5745 | 0,0000 |
| allhypo / RF | 0,1088 | 0,1074 | 0,9143 | 0,8571 | **−0,0571** |
| allhypo / SVM | 0,0928 | 0,0955 | 0,5870 | 0,5652 | −0,0217 |

**Médiane du Δ ERROR_CAPTURE au seuil gelé : −0,0041.** Le signe s'inverse par rapport au
classement pur (+0,0041). La cause est visible : le seuil calibré transfère moins bien pour
`ISO_META`, dont le taux de rejet réalisé dérive davantage — jusqu'à 0,0688 au lieu des 10 %
visés sur GAMETES/SVM, contre 0,1750 pour `STANDARD_META` sur la même cellule. C'est le résultat
le plus pertinent pour un déploiement réel, et il est **défavorable**.

---

## I. Gates — pourquoi chaque verdict

**GATE 1 — `ERROR_RISK_REPLICATED = NO`.** La médiane d'AUROC d'`ISO_PRED` est **0,6986**, au-delà
du seuil de 0,55, et 4 familles participent. Mais la condition de consistance échoue :
seulement **7 cellules sur 12 (58,3 %)** ont un IC 95 % strictement au-dessus de 0,50, contre
**⅔ exigés** ; hors RF, 5 sur 9 (55,6 %). Le clivage est net et par jeu : `adult` 0,695–0,711 et
`allhypo` 0,738–0,750 portent un vrai signal, tandis que `GAMETES` 0,475–0,549 et `agaricus`
0,495 n'en portent aucun. **La propriété de la Phase 21 se réplique sur 2 jeux prospectifs sur
4, pas sur la majorité exigée.**

**GATE 2 — `INCREMENTAL_TRIAGE = YES`.** Les quatre conditions passent littéralement :
médiane Δ AUGRC **+0,001344 > 0** ; médiane Δ EC@10 **+0,004089 > 0** ; **3 cellules** à Δ > 0
avec IC excluant 0, réparties sur **2 jeux** ; médiane stratifiée **+0,001515 > 0**. Ce gate est
le seul du bloc « utilité » à passer, et il ne demandait qu'un signe, pas une magnitude.

**GATE 3 — `ROBUST_ACROSS_DATASETS = NO`.** 2 jeux positifs sur 4, contre 3 exigés.
`agaricus_lepiota` et `allhypo` ont un Δ EC@10 médian **exactement nul**.

**GATE 4 — `ROBUST_ACROSS_MODELS = YES`.** Les 4 familles ont une médiane Δ AUGRC positive, et
les médianes hors Random Forest sont positives (+0,001970 et +0,005882). L'effet, tel qu'il est,
n'est pas porté par une seule famille.

**GATE 5 — `OPERATIONAL_GAIN = NO`.** Médiane Δ EC@10 **+0,004089** contre **+0,05 exigés** :
**douze fois trop petit**. La condition de cohérence sur Δ RESIDUAL_ERROR@10 (+0,001422 > 0) est
remplie, mais elle ne rachète pas la magnitude. Et dans la simulation de déploiement à seuil
gelé (§H), la médiane est **négative**.

---

## J. Interprétation

Les quatre niveaux demandés se séparent nettement.

**Signal statistique — partiellement présent.** `ISO_PRED` ordonne les erreurs nettement mieux
que le hasard sur `adult` (AUROC ≈ 0,70) et `allhypo` (≈ 0,74), et pas du tout sur `GAMETES`
(≈ 0,49) et `agaricus` (0,495). Sur les 12 cellules la médiane est 0,699, mais la dispersion
disqualifie la réplication au sens pré-enregistré.

**Gain incrémental — réel mais négligeable.** Médiane +0,0013 d'AUGRC sur des AUGRC allant de
0,0024 à 0,262 ; 2 cellules sur 12 survivent à Holm ; 8 sur 12 ont un IC contenant 0 ; une
cellule perd significativement.

**Robustesse — asymétrique.** Robuste **aux modèles** (4/4 familles, indépendant de Random
Forest), pas robuste **aux jeux** (2/4).

**Gain opérationnel — absent, et négatif en déploiement.** +0,4 point de pourcentage d'erreurs
capturées à 10 % de budget, contre 5 points exigés ; −0,4 point au seuil gelé.

### Le motif central

Le résultat le plus informatif de la phase est la **dissociation** entre les deux propriétés
testées, visible sur la figure 4 :

- Sur les jeux où `ISO_PRED` **a** du signal (`adult`, `allhypo`, AUROC 0,70–0,75), l'apport
  incrémental est **quasi nul** : Δ AUGRC médian +0,000165 et +0,000519, Δ EC@10 +0,0085 et
  **0,0000**. L'information d'ISO y est donc **redondante** avec les scores probabilistes.
- Sur les jeux où `ISO_PRED` **n'a pas** de signal (`GAMETES`, AUROC 0,475–0,549), l'apport
  apparent est le plus grand de l'étude : Δ EC@10 médian **+0,0393**. Mais une variable qui ne
  classe pas les erreurs mieux que le hasard ne peut pas y apporter d'information sur les
  erreurs. Sur ce jeu les exactitudes sont de 0,47 à 0,65 — un problème quasi insoluble — et le
  gain apparent est bien mieux expliqué par la latitude d'une logistique à 6 variables contre 3
  ajustée sur 320 observations de CALIBRATION.

Autrement dit : **là où ISO sait quelque chose, les scores standards le savent déjà ; là où ISO
« ajoute » quelque chose, il ne sait rien.** C'est la lecture la plus directe de H23, et elle
est négative.

---

## K. Anomalies, limites et réserves

1. **Déviation de pool** (§B) : OpenML-CC18 inatteignable, PMLB substitué, déclaré avant le gel.
   La règle « `task_id` croissant » a été remplacée par l'ordre lexicographique, faute de liste
   autoritative vérifiable.
2. **Défaut du contrôle anti-identifiant, signalé et non corrigé.** La règle gelée du §4 retire
   toute colonne à ≥ 95 % de valeurs distinctes ; elle est inadaptée aux variables continues. Sur
   `Hill_Valley_with_noise` elle a retiré les **100** colonnes, rendant le jeu inéligible avec
   `p = 0`. Conséquence : **biais du pool vers les jeux discrets ou catégoriels**. Appliquée
   uniformément, elle reste gelée.
3. **Trois jeux sur quatre sont binaires**, si bien que `MCP_RISK`, `ENTROPY_RISK` et
   `MARGIN_RISK` y sont des transformations monotones l'une de l'autre et coïncident exactement.
   La baseline « trois scores » est donc en pratique un seul score sur 11 cellules sur 12.
   Conséquence du tirage aveugle.
4. **12 cellules sur 16**, dont 3 perdues sur `agaricus_lepiota` parce que RF, GBM et SVM y font
   **zéro erreur** sur CALIBRATION. Le jeu est séparable ; il ne contribue qu'une cellule.
5. **`GAMETES` est un jeu simulé**, retenu par la règle aveugle. L'amendement 1 a évité d'en
   retenir quatre variantes, mais une demeure, et c'est celle qui porte le plus gros « gain ».
6. `evaluate_on_test` n'est appelé qu'après la clôture complète de l'étape CALIBRATION ; aucune
   décision, aucun seuil, aucun hyperparamètre n'a vu le TEST.
7. **Aucune analyse exploratoire n'a été lancée.** `EXPLORATORY_APPENDIX` est vide, et
   `NO_RESCUE_ANALYSIS = TRUE` a été respecté : ISO inchangé, seuil 0,70 → sans objet ici, seuil
   opérationnel de 10 % inchangé, aucun autre quantile essayé, aucun modèle ajouté ou retiré,
   aucune sélection de jeu revue, aucun sous-groupe construit, aucune dérive temporelle
   recherchée, `NATURAL_TEMPORAL_SHIFT` jamais réutilisé, `ISO_FROZEN` jamais employé.

---

## L. Conclusion scientifique

Sur quatre jeux tabulaires entièrement nouveaux, disjoints de tout l'historique du dépôt, et
quatre familles de classifieurs, l'isolabilité label-free gelée en Phase 21 :

- **ordonne les futures erreurs mieux que le hasard sur la moitié des jeux** (AUROC 0,70–0,75 sur
  `adult` et `allhypo`), et pas du tout sur l'autre moitié ;
- **est moins bonne que n'importe quel score probabiliste standard prise isolément** (AUGRC
  médiane 0,0461 contre 0,0331) ;
- **apporte, ajoutée à ces scores, un gain médian de +0,0013 d'AUGRC et +0,4 point de
  pourcentage d'erreurs capturées** à budget de revue de 10 %, contre 5 points requis pour une
  utilité pratique ;
- **dégrade légèrement le triage dans la simulation de déploiement à seuil gelé** (médiane
  −0,4 point) ;
- et son apport apparent se concentre précisément sur le jeu où elle **n'a aucune capacité
  propre** à classer les erreurs.

La propriété découverte en Phase 21 — « ISO prédit les erreurs au-dessus du hasard », AUROC
médiane 0,731 sur son périmètre — **reste un résultat historique valide sur ce périmètre**. Elle
ne se réplique ici que partiellement, et surtout elle **n'apporte aucune information utile que
les scores standards d'incertitude ne fournissent pas déjà**. C'était la seule question qui
importait.

**BRANCH_DECISION: CLOSE_APPLICATIVE_ISO_BRANCH**

Aucune Phase 24 n'est proposée.

---

## M. Artefacts

| Fichier | Contenu |
|---|---|
| `PROTOCOLE_PHASE23_RT.md`, `PROTOCOL_SHA256.txt` | protocole gelé + amendement 1 |
| `EXCLUSION_HISTORIQUE.json` | inventaire automatique, 17 jetons, jeux exclus |
| `CANDIDATE_SCREENING.csv` | les 179 jeux du pool et leur sort |
| `DATA_GATE.json`, `DATA_GATE_SUMMARY.csv` | acquisition, empreintes, trail complet |
| `SPLIT_*.csv` | indices TRAIN/CALIB/TEST matérialisés |
| `UNIT_TESTS.json` | 13/13 tests du §17 |
| `CALIB_STAGE.csv`, `CALIB_STAGE.json` | hyperparamètres, seuils et exécutabilité, sans TEST |
| `CELL_SCORES.csv` | AUGRC, AURC, EC/RE/LIFT à 5/10/20 % pour 6 scores × 12 cellules |
| `DELTAS.csv` | Δ AUGRC, Δ EC@10, Δ RE@10, IC bootstrap 10 000, p brutes, Holm |
| `OPERATING_POINT.csv` | déploiement à seuil gelé CALIB → TEST |
| `PHASE23_RT_RESULTS.json` | agrégations, 5 gates, verdicts |
| `figures/fig1…fig4` | Δ AUGRC, AUROC d'ISO, gain opérationnel, motif central |
| `logs/` | sondage d'accès, gate, étape CALIB, étape TEST |

---

```
ERROR_RISK_REPLICATED:        NO
INCREMENTAL_TRIAGE:           YES
ROBUST_ACROSS_DATASETS:       NO
ROBUST_ACROSS_MODELS:         YES
OPERATIONAL_GAIN:             NO

PHASE23_RESULT:               FALSIFIED
BRANCH_DECISION:              CLOSE_APPLICATIVE_ISO_BRANCH
```
