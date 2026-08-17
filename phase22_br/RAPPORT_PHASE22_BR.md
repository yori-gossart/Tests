# Phase 22-BR — Boundary Replication / Incremental Regime Test

**Rapport de résultats. Confirmatoire.**
Protocole gelé **avant tout accès aux données**, SHA-256
`3e48e6091655935e1aaf4cabeb7852540d7094d48d6e6ca1af02d3bfd86ce89b`.

| Étape | Commit | Contenu |
|---|---|---|
| `PHASE22_PROTOCOL_FROZEN` | `8fe5233` | protocole seul, aucun accès aux données |
| `PHASE22_DATA_GATE` | `7e8b17d` | acquisition, empreintes, splits, vérification des classes |
| Code d'exécution | `2a373c9` | run en cours, aucun verdict |
| **`PHASE22_RESULTS`** | ce commit | résultats complets et verdict |

`src/fo_metrics.py` inchangé (SHA-256 `f17cd735…de486c79`) et non importé.
**Visibility, Robustness, R7, FO et B\* sont absents de tout le code de cette phase.**
La fonction `isolability` est vérifiée verbatim à l'import contre la source Phase 20-DR
(SHA-256 de la fonction `492c42dbee0b88c6e45867374da1c146a0d4d4df6fb6adf634b65931d57d6318`).

---

## 1. Hypothèse testée et statut de son origine

> **H22** — Il existe un régime identifiable **avant** observation du TEST dans lequel les
> scores probabilistes classiques discriminent mal les futures erreurs, mais où l'isolabilité
> label-free apporte une information supplémentaire reproductible.

Le résultat HAR / Random Forest de la Phase 21-IR (ΔAUROC +0,056, IC [+0,013 ; +0,111]) est
**DISCOVERY-ONLY**. Il a engendré H22 et n'est utilisé nulle part comme preuve confirmatoire.
Les jeux de la Phase 22 sont disjoints de ceux de la Phase 21, et aucun modèle n'est réutilisé.

---

## 2. Jeux réellement exécutables

`archive.ics.uci.edu`, `www.openml.org` et `api.openml.org` répondent **403 au CONNECT** du
relais. Miroirs publics, recherche bornée à 8 dépôts par jeu.

| Jeu | Statut | Constat |
|---|---|---|
| **D1** Gas Sensor Array Drift (UCI 270) | **EXECUTABLE** | `Dalageo/ml-gas-sensor-drift@df121e57` — 13 910 × 128, 6 classes, **10 batches aux tailles officielles exactes** ; SHA-256 des 10 fichiers enregistrées |
| **D2** Sensorless Drive Diagnosis (UCI 325) | **NOT_EXECUTABLE** | 8 dépôts sondés : **5 ne contiennent aucun fichier de données brut** (notebooks seuls), **3 sont inclonables**. Aucune copie 58 509 × 49 à 11 classes de 5 319 trouvée |
| **D3** Default of Credit Card Clients (UCI 350) | **EXECUTABLE** | `MatteoM95/…@585f77c3` — 30 000 lignes, 23 caractéristiques hors ID et cible, **6 636 défauts, conforme exactement** |
| **D4** Dry Bean (UCI 602) | **EXECUTABLE** | `mehmetsen1/DryBeanDataset@be919f58` — 13 611 × 17, **effectifs par classe conformes exactement** |

D2 est rapporté non exécutable, **jamais substitué, jamais reconstruit**, aucun
sous-échantillon non officiel employé.

**Caveat d'intégrité, pour les trois jeux admis** : l'original UCI étant inatteignable, aucun
miroir ne peut être vérifié par somme de contrôle contre lui. Seule la conformité structurelle
aux effectifs officiels est établie.

**Conséquence structurelle, signalée dès le commit B** : avec **3 jeux et non 4**, le critère
gelé du §6 — `CONFIDENCE_WEAK` dans ≥ 3 jeux indépendants — exige que **les trois** jeux
portent une cellule faible. Le seuil 0,70 n'a pas été abaissé et aucun jeu n'a été ajouté.

### Splits matérialisés, graine 22260822, toutes classes présentes partout

| Jeu | TRAIN | CALIB | TEST |
|---|---|---|---|
| GAS | 8 347 | 2 781 | 2 782 |
| CREDIT | 18 000 | 6 000 | 6 000 |
| DRYBEAN | 8 167 | 2 723 | 2 721 |
| GAS `NATURAL_TEMPORAL_SHIFT` | 3 436 (batches 1-4) | 2 497 (5-6) | 7 977 (7-10) |

Les 6 classes de GAS sont présentes dans les trois parties du découpage temporel : l'analyse
de shift est **EXECUTABLE**.

---

## 3. Les 12 cellules et le régime, déterminé sur CALIBRATION seule

Hyperparamètres sélectionnés par exactitude sur CALIBRATION ; `PROB_BEST` choisi sur
CALIBRATION puis gelé ; décision `CONFIDENCE_WEAK` prise **avant toute ouverture du TEST**.
Cet ordre est garanti par construction : `run_cell` se termine entièrement avant que
`evaluate_on_test` touche un tableau de TEST.

| Jeu / modèle | hyperparamètres retenus | PROB_BEST | AUROC CALIB | régime | exactitude CALIB |
|---|---|---|---|---|---|
| GAS / LogReg | `C=10` | B3 marge | 0,847 | confiant | 0,9914 |
| GAS / RBF-SVM | `C=10, γ=0,01` | B3 marge | 0,878 | confiant | 0,9914 |
| GAS / RF | `sqrt, leaf=1` | B1 max prob | 0,948 | confiant | 0,9917 |
| GAS / GBM | `lr=0,1, leaves=31` | B2 entropie | 0,877 | confiant | 0,9928 |
| **CREDIT / LogReg** | `C=1` | B1 max prob | **0,656** | **CONFIDENCE_WEAK** | 0,8068 |
| **CREDIT / RBF-SVM** | `C=1, γ=scale` | B1 max prob | **0,637** | **CONFIDENCE_WEAK** | 0,8153 |
| **CREDIT / RF** | `0,3, leaf=5` | B1 max prob | **0,697** | **CONFIDENCE_WEAK** | 0,8178 |
| CREDIT / GBM | `lr=0,05, leaves=31` | B1 max prob | 0,702 | confiant | 0,8178 |
| DRYBEAN / LogReg | `C=10` | B1 max prob | 0,910 | confiant | 0,9221 |
| DRYBEAN / RBF-SVM | `C=10, γ=scale` | B3 marge | 0,907 | confiant | 0,9280 |
| DRYBEAN / RF | `sqrt, leaf=1` | B1 max prob | 0,920 | confiant | 0,9221 |
| DRYBEAN / GBM | `lr=0,05, leaves=31` | B2 entropie | 0,914 | confiant | 0,9258 |

**3 cellules `CONFIDENCE_WEAK`, toutes dans un seul jeu : CREDIT.**
GAS et DRYBEAN n'en portent aucune ; leurs 8 cellules sont entre 0,847 et 0,948, très loin du
seuil. CREDIT/GBM manque le seuil de 0,002.

> **`REGIME_IDENTIFIABLE = NO`** — 1 jeu porteur au lieu des 3 exigés.

Ce verdict était déjà déterminé avant l'ouverture du TEST : le régime est défini exclusivement
sur CALIBRATION.

---

## 4. Test confirmatoire sur les cellules `CONFIDENCE_WEAK`

`META_BASE` = logistique sur `slog(PROB_BEST)` ; `META_ISO` = même forme + les trois variables
d'`ISO_PRED`. Toutes deux ajustées **sur CALIBRATION uniquement**, évaluées une seule fois sur
TEST.

| Cellule | erreurs TEST | AUROC META_BASE | AUROC META_ISO | **ΔAUROC** | IC 95 % | p brute | Holm | ΔAURC |
|---|---|---|---|---|---|---|---|---|
| CREDIT / LogReg | 1 137 | 0,6513 | 0,6652 | **+0,0139** | [+0,0055 ; +0,0225] | 0,002 | **rejeté ✓** | +0,0073 |
| CREDIT / RBF-SVM | 1 099 | 0,6331 | 0,6394 | +0,0063 | [−0,0068 ; +0,0187] | 0,334 | non | +0,0051 |
| CREDIT / RF | 1 081 | 0,7037 | 0,7035 | **−0,0002** | [−0,0020 ; +0,0015] | 0,847 | non | +0,0000 |

- **Estimateur stratifié** (médiane sur les jeux de la médiane par jeu) : **+0,0063**,
  IC 95 % **[−0,0006 ; +0,0176]**.
- Médiane du ΔAURC stratifié : **+0,0051**.
- Une seule cellule survit à Holm, et son gain (+0,0139) reste **sous le seuil gelé de +0,020**.

### Les huit conditions du §9

| # | Condition | Observé | Verdict |
|---|---|---|---|
| 1 | ≥ 3 jeux à médiane ΔAUROC positive | **1** | ✗ |
| 2 | ≥ 2 familles participantes | 3 | ✔ |
| 3 | médiane globale ≥ +0,020 | **+0,0063** | ✗ |
| 4 | IC 95 % stratifié exclut 0 | **[−0,0006 ; +0,0176]** | ✗ |
| 5 | ≥ 3 cellules confirmées Holm sur ≥ 3 jeux | **1 cellule, 1 jeu** | ✗ |
| 6 | effet non porté uniquement par Random Forest | 2 cellules hors RF, 1 jeu | ✗ |
| 7 | ΔAURC globalement favorable | +0,0051 | ✔ |
| 8 | META_ISO améliore META_BASE | médiane > 0 | ✔ |

> **`INCREMENTAL_REGIME = NO`** — cinq des huit conditions échouent.
> **`ROBUST_ACROSS_DATASETS = NO`** · **`ROBUST_ACROSS_MODELS = NO`** ·
> **`PROBABILITY_BASELINE_BEATEN = NO`**

Le §6 du protocole demandait que l'effet ne dépende pas de Random Forest. Ici c'est l'inverse
qui se produit : **la cellule Random Forest, précisément la famille qui avait engendré H22 en
Phase 21, donne ΔAUROC = −0,0002**, soit exactement rien.

---

## 5. Analyse `NATURAL_TEMPORAL_SHIFT` — rapportée séparément

Découpage par batch écrit dans le protocole avant tout résultat. Cette analyse **n'entre dans
aucun critère du §9**, conformément au §4.3.

La dérive réelle est massive : l'exactitude passe de ~0,99 sous découpage aléatoire à
**0,48–0,56** sur les batches ultérieurs.

| Modèle | AUROC CALIB | régime | exactitude TEST | erreurs | ΔAUROC | IC 95 % | p | Holm |
|---|---|---|---|---|---|---|---|---|
| LogReg | 0,950 | confiant | 0,5627 | 3 488 | −0,1177 | [−0,1318 ; −0,1030] | 0,000 | — |
| **RBF-SVM** | **0,613** | **WEAK** | 0,5646 | 3 473 | **+0,1388** | [+0,1239 ; +0,1541] | 0,000 | **rejeté ✓** |
| RF | 0,831 | confiant | 0,4844 | 4 113 | −0,1066 | [−0,1186 ; −0,0943] | 0,000 | — |
| **GBM** | **0,660** | **WEAK** | 0,5275 | 3 769 | **−0,0363** | [−0,0497 ; −0,0221] | 0,000 | **rejeté ✓** |

**Les deux cellules faibles sont de signes opposés, toutes deux hautement significatives.**
C'est le résultat le plus spectaculaire de la phase — +0,139 pour le SVM — et c'est aussi celui
qui ne peut rien appuyer : dans le même jeu, sous le même régime pré-déclaré, sous la même
dérive, l'isolabilité aide fortement un modèle et **nuit** significativement à un autre. Une
médiane de +0,051 sur deux cellules de signes contraires ne constitue pas une réplication ;
elle constitue une instabilité.

---

## 6. Anomalies, limites et annexe exploratoire

Tout ce qui suit est **descriptif** et n'autorise aucune Phase 23.

### 6.1 La relation prédite par H22 n'apparaît pas

`evaluate_on_test` a été appelé sur **toutes** les cellules, pas seulement les faibles. Cela ne
contamine rien — la détermination du régime était figée sur CALIBRATION avant tout accès au
TEST, et aucune décision ne dépend des cellules confiantes — mais cela donne une vue complète,
purement descriptive :

- Les **deux plus gros gains** de toute l'analyse principale viennent de cellules **confiantes**
  et non faibles : GAS / LogReg (+0,0905, AUROC CALIB 0,847) et GAS / RBF-SVM (+0,0473,
  AUROC CALIB 0,878).
- Parmi les 9 cellules confiantes, la **médiane du ΔAUROC est −0,0051** et **5 sur 9 sont
  négatives**.
- Les 3 cellules faibles plafonnent à +0,0139.

Autrement dit : le prédicteur du bénéfice n'est pas la faiblesse du score probabiliste. H22
désignait le mauvais axe.

### 6.2 L'oracle contredit le régime retenu

`ISO_FROZEN`, qui connaît la vraie classe et ne peut fonder aucun verdict, ajouté à
`META_BASE` :

| Jeu | Δ vs META_BASE (oracle) |
|---|---|
| GAS | **+0,013 à +0,154** |
| DRYBEAN | +0,023 à +0,030 |
| **CREDIT** | **−0,012 à −0,024** |

Sur CREDIT — le seul jeu porteur du régime `CONFIDENCE_WEAK` — même la version oracle
**dégrade** le modèle de base dans les quatre cellules. La géométrie d'isolabilité n'y contient
donc essentiellement rien à extraire, indépendamment de l'étiquette. C'est une explication
cohérente de l'échec, et elle est post-hoc.

### 6.3 Limites

- **Trois jeux sur quatre.** D2 manquant rend le critère à 3 jeux mécaniquement plus dur. Cela
  n'a pas été compensé, ni le seuil ajusté.
- **Un seul jeu porteur du régime.** Le test confirmatoire repose sur 3 cellules d'un seul jeu,
  ce qui est structurellement insuffisant pour la revendication de H22 — et c'est précisément ce
  que le critère du §6 était censé détecter.
- **Intégrité des miroirs** non vérifiable par somme de contrôle.
- `SVC(probability=True)` est déprécié depuis scikit-learn 1.9 ; l'appel gelé est conservé.
- Le découpage aléatoire de GAS produit une exactitude de 0,99 parce qu'il ignore la structure
  par batch ; les cellules GAS principales ont donc 17 à 24 erreurs sur CALIB et des IC larges.
  Le découpage temporel gelé corrige cela et donne l'analyse du §5.

### 6.4 Aucun sauvetage entrepris

Après ouverture du TEST : ISO n'a pas été modifié, le seuil 0,70 n'a pas bougé, aucun jeu n'a
été ajouté ni retiré, les classifieurs n'ont pas changé, aucun sous-groupe n'a été inventé,
aucune métrique primaire n'a été changée, aucun autre régime n'a été cherché, aucun R8/R9 n'a
été créé, ni FO, ni B\*, ni Visibility, ni Robustness n'ont été introduits.

---

## 7. Verdict scientifique

H22 postulait que la faiblesse du score probabiliste identifie *a priori* le régime où
l'isolabilité devient utile. Le test le réfute sur deux plans indépendants.

**Le régime n'est pas identifiable là où on l'attendait.** Sur trois jeux et quatre familles,
le critère pré-déclaré ne trouve de cellules faibles que dans un seul jeu. Ce n'est pas un
manque de puissance : GAS et DRYBEAN sont à 0,847–0,948, à distance considérable du seuil.

**Là où le régime existe, l'apport est absent.** Dans les trois cellules CREDIT, la médiane est
+0,0063, l'IC stratifié contient 0, une seule cellule survit à Holm et son gain reste sous le
seuil de pertinence. La cellule Random Forest — la famille même qui avait produit le signal de
découverte — donne −0,0002.

**Et le signal réel se trouve ailleurs, de façon instable.** Le seul gain important de toute la
phase, +0,139, apparaît sur une cellule SVM sous dérive temporelle réelle ; dans le même jeu,
sous le même régime, le gradient boosting perd −0,036 de manière tout aussi significative. Les
deux plus gros gains de l'analyse principale viennent de cellules *confiantes*. Sur les 9
cellules confiantes, la médiane est négative.

La conclusion gelée applicable est **FALSIFIED** : aucun régime reproductible, et aucune valeur
incrémentale robuste. Le résultat scientifique de la Phase 21 — « ISO prédit les erreurs
au-dessus du hasard », AUROC médiane 0,731 sur 12 cellules — **reste archivé et n'est pas
remis en cause par cette phase** ; il ne justifie simplement aucun développement produit.

---

## 8. Artefacts

| Fichier | Contenu |
|---|---|
| `PROTOCOLE_PHASE22_BR.md`, `PROTOCOL_SHA256.txt` | protocole gelé `3e48e609…` |
| `GATE_B.json`, `GATE_B_SUMMARY.csv` | acquisition, 8 dépôts sondés par jeu, empreintes SHA-256, motifs de rejet |
| `VERIFY_SPLITS.json`, `SPLIT_*.csv` | splits matérialisés et vérification des classes |
| `CELLS_MAIN.csv` | 12 cellules : hyperparamètres, PROB_BEST, AUROC CALIB, régime |
| `SCORES_MAIN.csv` | AUROC / AUPRC / AURC et exactitude conservée à 90 / 80 / 70 % de couverture, pour 9 scores × 12 cellules |
| `DELTAS_WEAK_CELLS.csv` | test confirmatoire, IC bootstrap, p brutes, décisions Holm |
| `CELLS_SHIFT.csv`, `SCORES_SHIFT.csv`, `DELTAS_SHIFT.csv` | analyse `NATURAL_TEMPORAL_SHIFT` |
| `ORACLE_ANNEX.csv` | `ISO_FROZEN`, descriptif, aucun verdict |
| `PHASE22_BR_RESULTS.json` | critères, verdicts, vérification verbatim |
| `figures/fig1…fig4` | régime, test confirmatoire, dérive temporelle, relation H22 |
| `logs/` | sondage des hôtes, gate, journal d'exécution complet |

---

```
REGIME_IDENTIFIABLE:         NO
INCREMENTAL_REGIME:          NO
ROBUST_ACROSS_DATASETS:      NO
ROBUST_ACROSS_MODELS:        NO
PROBABILITY_BASELINE_BEATEN: NO
PHASE22_RESULT:              FALSIFIED
```

BRANCH_DECISION: CLOSE_ISOLABILITY_TECH_BRANCH
