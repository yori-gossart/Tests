# Phase 21-IR — Independent Isolability Replication

**Rapport de résultats. Confirmatoire.**
Protocole gelé **avant** toute exécution, SHA-256
`7d29354cc14ae5f26c4599d1213c70f7fea02f26fb4510ae741bf50a4513369f`.

| Étape | Commit | Contenu |
|---|---|---|
| Protocole gelé + erratum Phase 20-DR | `71980a4` | aucun résultat |
| Code d'exécution + Gate A | `c92e244` | acquisition seule, aucun endpoint |
| **Résultats** | ce commit | endpoints, figures, verdicts |

`src/fo_metrics.py` inchangé et non importé. **Visibility, Robustness, R7, FO et B\* sont
absents de tout le code de cette phase.** La fonction `isolability` est copiée caractère pour
caractère depuis `src/phase20_dr_run.py` et cette identité est vérifiée à l'import
(SHA-256 de la fonction `492c42dbee0b88c6e45867374da1c146a0d4d4df6fb6adf634b65931d57d6318`).

---

## 1. Les quatre verdicts

```
GENERALIZATION:     YES
INCREMENTAL_VALUE:  YES
NOVELTY_SIGNAL:     SUPPORTED
PHASE22_AUTHORIZED: YES
```

**Ces verdicts sont ceux que produisent les critères gelés au §9 du protocole, appliqués
littéralement. Ils sont rapportés tels quels. Ils sont aussi trompeurs si on les lit sans le
§5 de ce rapport, et je le dis avant de développer quoi que ce soit :**

- `GENERALIZATION = YES` est **solide** : le score prédit l'erreur au-dessus du hasard dans
  **12 cellules sur 12**, sur 3 jeux et 4 familles de modèles, et tient sans Random Forest.
- `INCREMENTAL_VALUE = YES` repose sur **une seule cellule sur douze**, et cette cellule est
  **Random Forest**. La médiane du gain est **négative** dans les deux contrastes.
  Le garde-fou anti-Random-Forest du critère 4 n'avait été écrit que pour
  `GENERALIZATION` ; s'il avait couvert `INCREMENTAL_VALUE`, le verdict aurait été `NO`.
  C'est un défaut de mon protocole, signalé au §6, et **non corrigé après coup**.

---

## 2. Deux constats bloquants, établis avant le gel

### 2.1 Le score gelé utilisait l'étiquette vraie

Établi par relecture de `src/phase20_dr_run.py` : `own = np.array([ks.index(v) for v in y])`
indexe l'étiquette **vraie**, TEST compris, et les trois variables en dérivent. Un erratum
retirant le §9 « Ce qui survit » de la Phase 20-DR a été commité en `71980a4`, avant toute
exécution ici.

Deux variantes ont donc été définies et **jamais confondues** :

| Variante | `own` | Rôle |
|---|---|---|
| **ISO_PRED** | étiquette **prédite** | seule variante portant les verdicts |
| ISO_FROZEN | étiquette **vraie** | référence, étiquetée `ORACLE`, aucun verdict |

`ISO_PRED` est la seule adaptation d'interface autorisée : la formule est intacte, seule la
source de `own` change.

### 2.2 Gate A — un jeu de données sur quatre est inexécutable

`archive.ics.uci.edu`, `www.openml.org` et `api.openml.org` répondent **403 au CONNECT** du
relais (journal dans `logs/host_probe.log`). Recherche de miroirs bornée à 6 dépôts par jeu :

| Jeu | Statut | Constat |
|---|---|---|
| **APS Failure at Scania Trucks** | **NOT_EXECUTABLE** | TEST officiel conforme (16 000 × 171, 375 pos / 15 625 neg) trouvé dans **2 miroirs indépendants**, mais **aucun TRAIN de 60 000 lignes sur les 6 dépôts** : copies de 19 999 lignes (fichier nommé `_SMALLER`) et de 36 188 lignes (1 000 pos / 35 188 neg) |
| SECOM | EXECUTABLE | 1 567 × 590 ; classes −1 : 1 463 / +1 : 104, **conforme exactement** |
| Steel Plates Faults | EXECUTABLE | 1 941 × 34 |
| HAR Smartphones | EXECUTABLE | 7 352 / 2 947 × 561 ; 6 activités ; 21 / 9 sujets **disjoints** |

APS est **rapporté non exécutable, jamais remplacé, jamais reconstruit**, et aucun
sous-échantillon non officiel n'a été substitué. Il reste 12 cellules, au-dessus du minimum
gelé de 4 cellules / 2 jeux / 2 familles.

**Caveat d'intégrité, valable pour les trois jeux admis** : l'original UCI étant inatteignable,
aucun miroir ne peut être vérifié par somme de contrôle contre lui. Seule la conformité
structurelle aux effectifs officiels est établie.

**Défaut du Gate A signalé** : `gate_secom` vérifiait le nombre de lignes mais pas les
effectifs par classe, que le protocole exigeait pour D2. La vérification a été faite
séparément et **passe exactement** (1 463 / 104) ; l'omission est signalée plutôt que
silencieusement comblée.

---

## 3. Périmètre exécuté

| Jeu | classes | TRAIN | CALIB | TEST | découpage |
|---|---|---|---|---|---|
| SECOM | 2 | 940 | 313 | 314 | stratifié 60/20/20, graine 21260821 |
| Steel Plates | 7 | 1 165 | 388 | 388 | stratifié 60/20/20, graine 21260821 |
| HAR | 6 | 5 280 | 2 072 | **2 947 officiel** | **par sujet** — 15 / 6 / 9 sujets disjoints |

Prétraitement appris **sur TRAIN seul** : colonnes constantes retirées, indicatrice de
manquant au-delà de 5 %, imputation par la médiane TRAIN, `StandardScaler`. SECOM : 590 → 526
colonnes (474 conservées + 52 indicatrices ; 41 951 valeurs manquantes au total).

Bootstrap apparié 2 000 tirages, unité = la ligne, **sauf HAR où c'est le sujet** — d'où des
IC beaucoup plus larges sur HAR (9 sujets seulement), ce qui est le choix conservateur.

Aucune cellule n'a été déclarée `NOT_EVALUABLE_LOW_EVENTS` : le minimum est 21 erreurs sur
TEST (SECOM), au-dessus du seuil gelé de 20. **C'est juste au-dessus** : trois cellules SECOM
sont à 21 erreurs exactement, et leurs IC sont larges en conséquence.

---

## 4. GENERALIZATION — le résultat positif, et il est réel

AUROC de prédiction d'ERREUR sur TEST, 12 cellules :

| Jeu / modèle | ISO_FIT | IC 95 % | meilleure baseline (choisie sur CALIB) | erreurs TEST |
|---|---|---|---|---|
| SECOM / LogReg | 0,666 | [0,580 ; 0,756] | 0,759 `B1` | 43 |
| SECOM / RBF-SVM | 0,714 | [0,613 ; 0,804] | 0,730 `B1` | 21 |
| SECOM / RandomForest | 0,667 | [0,543 ; 0,778] | 0,710 `B1` | 21 |
| SECOM / GradBoosting | 0,666 | [0,540 ; 0,778] | 0,731 `B1` | 21 |
| STEEL / LogReg | 0,727 | [0,670 ; 0,781] | 0,768 `B1` | 102 |
| STEEL / RBF-SVM | **0,752** | [0,693 ; 0,812] | 0,743 `B2` | 87 |
| STEEL / RandomForest | 0,733 | [0,673 ; 0,796] | 0,836 `B1` | 86 |
| STEEL / GradBoosting | 0,728 | [0,668 ; 0,792] | 0,805 `B2` | 79 |
| HAR / LogReg | 0,813 | [0,696 ; 0,896] | 0,901 `B3` | 172 |
| HAR / RBF-SVM | 0,823 | [0,698 ; 0,915] | 0,917 `B3` | 151 |
| HAR / RandomForest | 0,852 | [0,798 ; 0,923] | 0,904 `B3` | 239 |
| HAR / GradBoosting | 0,811 | [0,759 ; 0,875] | 0,919 `B3` | 205 |

Critères gelés du §9 :

| Critère | Exigence | Observé | Verdict |
|---|---|---|---|
| 1 | AUROC médiane ≥ 0,70 | **0,7306** | ✔ |
| 2 | ≥ ⅔ des cellules avec IC > 0,50 | **12/12 = 1,00** | ✔ |
| 3 | ≥ 2 jeux et ≥ 2 familles | **3 jeux, 4 familles** | ✔ |
| 4 | tient sans Random Forest | médiane **0,728**, 9/9 cellules, 3 jeux, 3 familles | ✔ |

**`GENERALIZATION = YES`.** Le constat est net et je le prends au sérieux : le score
d'isolabilité, privé de l'étiquette vraie et transporté hors du banc ZeMA sur trois jeux
tabulaires publics et quatre familles de classifieurs, prédit l'erreur au-dessus du hasard
**partout**, sans exception, y compris sur HAR où l'unité de bootstrap est le sujet.

La tentative de falsification a échoué sur ce point précis.

---

## 5. INCREMENTAL_VALUE — ce que le verdict recouvre réellement

### 5.1 ISO_FIT contre la meilleure baseline

| | Valeur |
|---|---|
| Médiane Δ AUROC | **−0,0706** |
| Gains confirmés ≥ +0,02 | **0 sur 12** |
| Pertes significatives (IC excluant 0) | **5 sur 12** |

Les cinq pertes significatives : SECOM/LogReg (−0,093), STEEL/RandomForest (−0,103),
STEEL/GradBoosting (−0,077), HAR/LogReg (−0,087), HAR/GradBoosting (−0,108).
La seule cellule où ISO_FIT dépasse la baseline est STEEL/RBF-SVM, de **+0,009**, IC contenant 0.

### 5.2 COMBO (meilleure baseline + isolabilité) contre la baseline seule

| | Valeur |
|---|---|
| Médiane Δ AUROC | **−0,0142** |
| Gains confirmés ≥ +0,02 | **1 sur 12** — HAR / RandomForest, +0,056, IC [+0,013 ; +0,111] |
| Pertes significatives | 1 sur 12 — SECOM / RandomForest, −0,024 |

Une cellule supplémentaire est significative mais **sous le seuil de pertinence** :
STEEL/RBF-SVM, +0,0096, IC [+0,003 ; +0,017].

### 5.3 Comment le verdict `YES` est produit

Le §9 du protocole exigeait « gain ≥ +0,02 … confirmé par IC 95 % apparié » **sans préciser
sur combien de cellules**. Mon code gelé a implémenté la lecture la plus faible admissible :
**au moins une cellule**. Une seule cellule qualifie — HAR / RandomForest — et
`INCREMENTAL_VALUE` bascule à `YES`, entraînant `NOVELTY_SIGNAL = SUPPORTED` et
`PHASE22_AUTHORIZED = YES`.

**Je ne modifie pas ce verdict après avoir vu les résultats.** Je rapporte, à côté, ce
qu'auraient donné des lectures plus strictes, écrites ici pour que le lecteur juge :

| Lecture du critère | Résultat |
|---|---|
| ≥ 1 cellule (implémentée, gelée) | **YES** |
| ≥ 2 jeux **et** ≥ 2 familles, comme le critère 3 | **NO** (1 jeu, 1 famille) |
| Ne doit pas dépendre uniquement de Random Forest, comme le critère 4 | **NO** |
| Majorité des cellules | **NO** (1/12) |
| Médiane du gain ≥ +0,02 | **NO** (−0,014) |

Toute lecture autre que la plus permissive donne `NO`. **La valeur incrémentale du score
n'est pas établie par ces données.**

---

## 6. Défauts de mon protocole, signalés et non réparés

1. **§9, INCREMENTAL_VALUE_PASS ne quantifiait pas le nombre de cellules requis.** Le critère 3
   le faisait pour `GENERALIZATION` (≥ 2 jeux, ≥ 2 familles) et le critère 4 y ajoutait un
   garde-fou anti-Random-Forest ; ni l'un ni l'autre n'a été répliqué pour
   `INCREMENTAL_VALUE`. C'est la cause directe d'un `PHASE22_AUTHORIZED = YES` porté par une
   cellule unique.
2. **`gate_secom` ne vérifiait pas les effectifs par classe**, que le protocole exigeait pour
   D2. Vérifiés séparément, ils passent exactement.
3. **Le tableau `iso_vs_best` du JSON annonce `n_cells: 24`** : quand la meilleure baseline sur
   CALIB et celle sur TEST coïncident, le même contraste est compté deux fois. Le décompte
   correct est **12 cellules distinctes**, utilisé partout dans ce rapport.
4. `SVC(probability=True)` est déprécié depuis scikit-learn 1.9 (avertissement à l'exécution).
   L'appel gelé fonctionne toujours ; il est conservé tel quel.

---

## 7. Analyses descriptives, ajoutées après ouverture du TEST et signalées comme telles

Elles ne portent aucun verdict et n'ont modifié aucun critère.

AUROC **médiane** sur les 12 cellules, par score :

| Score | Médiane |
|---|---|
| B1 max probability | **0,786** |
| B2 entropie prédictive | 0,782 |
| B3 marge top-1/top-2 | 0,781 |
| **ISO_FIT** | **0,731** |
| ISO_RAW (`− iso_margin_ratio` seul) | 0,719 |
| B6 conformal APS | 0,609 |
| B4 kNN training-distance | 0,577 |
| B5 Mahalanobis class-conditionnel | **0,539** |
| COMBO | 0,788 |
| ISO_FROZEN (oracle, étiquette vraie) | 0,835 |

Deux observations, données comme descriptives :

- **ISO_PRED bat nettement les baselines de distance.** 0,731 contre 0,539 pour le Mahalanobis
  class-conditionnel standard et 0,577 pour le kNN. Sur ces jeux, les scores de distance
  classiques sont proches du hasard, et la construction d'isolabilité en extrait beaucoup plus.
  C'est la seule chose que ces données disent en faveur du score.
- **Il reste sous les baselines de probabilité**, qui sont gratuites : elles se lisent
  directement dans la sortie du classifieur, sans centroïdes, sans covariance, sans inversion
  de matrice. Le coût de calcul d'ISO_PRED est sans commune mesure pour une performance
  inférieure.
- **Même l'oracle ne domine pas.** `ISO_FROZEN`, qui a accès à l'étiquette vraie, ne gagne
  significativement que dans 3 cellules et **perd** significativement dans 1 (HAR/GradBoosting,
  −0,145). L'étiquette vraie n'achète donc pas un prédicteur d'erreur fiable non plus.

---

## 8. Conclusion et suite

La règle d'arrêt gelée donne, littéralement :

> `GENERALIZATION = YES` et `INCREMENTAL_VALUE = YES` → `PHASE22_AUTHORIZED = YES`.

C'est le verdict, et il est enregistré. Ma lecture des données, que je donne séparément parce
qu'elle n'est pas un verdict :

- **Ce qui est établi.** Le score d'isolabilité, sans étiquette de test, prédit l'erreur de
  classification au-dessus du hasard dans 12 cellules sur 12, hors de son environnement de
  découverte, avec une AUROC médiane de 0,731. Ce n'est pas un artefact du banc ZeMA, ce n'est
  pas la fuite d'étiquette corrigée en Phase 20-DR, et cela survit au retrait de Random Forest.
- **Ce qui n'est pas établi.** Qu'il apporte quoi que ce soit par rapport à ce qui existe. Il
  perd contre la meilleure baseline dans 11 cellules sur 12, significativement dans 5, et son
  apport en combinaison n'est confirmé que dans une cellule Random Forest sur douze.
- **La situation décrite par la règle d'arrêt n° 3 du protocole** — « `GENERALIZATION = YES` et
  `INCREMENTAL_VALUE = NO` → résultat potentiellement réel, mais aucun avantage démontré sur
  l'existant » — **est celle qui décrit fidèlement ces résultats**, même si le critère tel que
  je l'ai codé ne l'a pas déclenchée.

Une Phase 22 qui partirait de `PHASE22_AUTHORIZED = YES` sans lire le §5 partirait sur une base
fausse. Si elle a lieu, la question à trancher n'est pas « le score généralise-t-il » — c'est
réglé, oui — mais « existe-t-il un régime où il bat max-probability », et le seul indice
disponible pointe vers les cas où les probabilités du classifieur sont peu informatives.

Aucune nouveauté mathématique n'est revendiquée : Mahalanobis (1936), Hotelling (1931),
Ledoit-Wolf (2004), APS conformal (Romano, Sesia & Candès 2020), risk-coverage
(El-Yaniv & Wiener 2010) sont standards.

---

## 9. Artefacts

| Fichier | Contenu |
|---|---|
| `PROTOCOLE_PHASE21_IR.md`, `PROTOCOL_SHA256.txt` | protocole gelé, `7d29354c…` |
| `GATE_A.json`, `GATE_A_SUMMARY.csv` | acquisition, 6 dépôts sondés par jeu, motifs de rejet |
| `CELL_SCORES.csv` | AUROC / AUPRC / AURC des 10 scores × 12 cellules |
| `CELL_CONTRASTS.csv` | contrastes + IC bootstrap apparié |
| `CELL_SUMMARY.csv` | effectifs, exactitude, meilleure baseline, IC d'ISO_FIT |
| `PHASE21_IR_RESULTS.json` | critères, incréments, 4 verdicts, vérification verbatim |
| `figures/fig1…fig3` | cellules, contrastes, comparaison des scores |
| `logs/host_probe.log`, `logs/gate_a.log`, `logs/run.out` | journaux complets |
