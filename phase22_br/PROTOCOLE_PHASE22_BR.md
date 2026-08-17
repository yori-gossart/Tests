# Protocole Phase 22-BR — Boundary Replication / Incremental Regime Test

**PRÉ-ENREGISTRÉ ET GELÉ. Écrit et commité AVANT tout accès aux données et avant tout
résultat.** Ce fichier est le contenu unique du commit A.

## Hypothèse unique testée

> **H22** — Il existe un régime identifiable **avant** observation du TEST dans lequel les
> scores probabilistes classiques discriminent mal les futures erreurs du classifieur, mais où
> l'isolabilité label-free gelée en Phase 21 apporte une information supplémentaire
> reproductible.

Cette phase n'améliore pas SIGMA, ne modifie pas la formule d'isolabilité, ne crée aucune
architecture physique nouvelle, et ne cherchera aucun score nouveau après observation des
résultats.

---

## 0. Statut de HAR / Random Forest

Le résultat HAR / Random Forest de la Phase 21-IR — ΔAUROC **+0,056**, IC 95 %
[+0,013 ; +0,111] — est déclaré **DISCOVERY-ONLY**. Il a servi à **générer** H22.

Il est **formellement interdit** de l'utiliser pour satisfaire un quelconque critère
confirmatoire de la Phase 22. Il ne peut être rappelé dans le rapport qu'en tant qu'origine de
l'hypothèse. Aucune cellule de la Phase 21 ne reparaît dans le décompte de la Phase 22 : les
quatre jeux de données de cette phase sont **disjoints** de ceux de la Phase 21 (SECOM, Steel
Plates Faults, HAR, APS Scania), et aucun modèle de la Phase 21 n'est réutilisé.

---

## 1. Le score d'isolabilité, gelé

### 1.1 Implémentation

La fonction `isolability` est celle de `src/phase21_ir_iso.py`, elle-même copiée caractère pour
caractère depuis `src/phase20_dr_run.py`. SHA-256 de la fonction :
`492c42dbee0b88c6e45867374da1c146a0d4d4df6fb6adf634b65931d57d6318`.
Le module vérifie cette identité à l'import et lève si elle diverge. **Aucune modification
mathématique n'est autorisée.**

Estimateurs d'entrée, identiques aux Phases 20-DR et 21-IR :
`cents[k] = X_train[y_train == k].mean(0)` ;
`Sinv = np.linalg.pinv(LedoitWolf(assume_centered=False).fit(X_train).covariance_)`.
Centroïdes et covariance viennent **du TRAIN seul**.

### 1.2 Variantes et leur statut

| Variante | `own` construit sur | Statut en Phase 22 |
|---|---|---|
| **ISO_PRED** | l'étiquette **prédite** par le classifieur | **score confirmatoire primaire** |
| ISO_FROZEN | l'étiquette **vraie** | **ORACLE / DESCRIPTIF UNIQUEMENT** — n'intervient dans aucun verdict |
| ISO_FIT | logistique sur les trois variables d'ISO_PRED, ajustée **sur CALIBRATION uniquement** | **analyse secondaire uniquement** ; définition déjà gelée au §1.3 du protocole Phase 21-IR, donc admissible à ce titre |

`ISO_PRED` désigne les **trois** variables produites par la fonction gelée
(`iso_d_nearest`, `iso_margin_ratio`, `iso_centroid_min`), calculées avec l'étiquette prédite.
L'étiquette vraie du TEST n'intervient que dans le calcul d'`ERROR`, au moment de l'évaluation.

### 1.3 Interdits absolus

`Visibility`, `Robustness`, `R7`, `FO`, `B*` sont interdits et ne sont calculés nulle part.
`src/fo_metrics.py` reste inchangé (SHA-256
`f17cd735816c958279f66f3d6b03e69fc95ef259dba716e13d331565de486c79`) et n'est importé nulle part.

---

## 2. Jeux de données confirmatoires — gelés avant tout calcul

Les quatre sont fixés. **Aucun ne peut être retiré parce que ses résultats sont défavorables.**
Effectifs officiels attendus, écrits ici avant tout accès aux données :

| # | Jeu | UCI | Effectifs officiels attendus | Cible |
|---|---|---|---|---|
| **D1** | Gas Sensor Array Drift at Different Concentrations | 270 | **13 910 × 128**, 6 classes, **10 batches** de tailles 445 / 1 244 / 1 586 / 161 / 197 / 2 300 / 3 613 / 294 / 470 / 3 600 | 6 gaz |
| **D2** | Dataset for Sensorless Drive Diagnosis | 325 | **58 509 × 48**, **11 classes de 5 319 chacune** | 11 états |
| **D3** | Default of Credit Card Clients | 350 | **30 000 × 23** caractéristiques (hors ID et cible), binaire, **6 636 défauts** | défaut oui/non |
| **D4** | Dry Bean | 602 | **13 611 × 16**, 7 classes : Dermason 3 546, Sira 2 636, Seker 2 027, Horoz 1 928, Cali 1 630, Barbunya 1 322, Bombay 522 | 7 variétés |

### 2.1 Contexte d'accès, connu avant le gel

Les Phases 19, 21 ont établi que `archive.ics.uci.edu`, `www.openml.org` et `api.openml.org`
répondent **403 au CONNECT** du relais réseau de cet environnement. `github.com` (clone git),
`raw.githubusercontent.com` et `api.github.com` sont accessibles. Les jeux seront donc
recherchés dans des miroirs publics, **d'intégrité non vérifiable par somme de contrôle contre
l'original**.

### 2.2 Gate de données (commit B) — conformité structurelle

Recherche **bornée à 8 dépôts candidats par jeu**, chacun journalisé avec son URL et son commit.
Une copie est admise si et seulement si :

- le nombre de lignes et de colonnes est **exactement** celui du tableau ci-dessus ;
- les effectifs par classe sont **exactement** ceux documentés (D2, D3, D4) ;
- pour D1, les **10 batches** sont présents avec **exactement** les tailles documentées ;
- aucune colonne n'est ajoutée, renommée, imputée, rééchelonnée ou réordonnée par le miroir ;
- aucun nom de fichier ne signale une transformation (`_smaller`, `_processed`, `_clean`,
  `_balanced`, `_sample`, `_reduced`, `_subset`, `_smote`, `_tidy`, `_undersampl`, `_oversampl`).

Résultat par jeu : `EXECUTABLE` ou **`NOT_EXECUTABLE`** avec le motif exact, les empreintes
SHA-256 des fichiers retenus et les journaux. **Aucune substitution après observation des
résultats. Aucune reconstruction, aucun sous-échantillon non officiel.**

Si aucun jeu n'est exécutable, `PHASE22_RESULT = INCONCLUSIVE_ACCESS`.

---

## 3. Familles de classifieurs

Quatre familles par jeu exploitable, soit **jusqu'à 16 cellules confirmatoires**
dataset × modèle. **Aucun modèle de la Phase 21 n'est réutilisé** : les hyperparamètres sont
ici sélectionnés, alors qu'ils étaient fixés en Phase 21.

Grilles gelées, sélection par **exactitude sur CALIBRATION**, égalité tranchée par l'ordre de
la grille. **Le TEST n'intervient jamais dans la sélection.**

| # | Famille | Implémentation | Grille gelée |
|---|---|---|---|
| M1 | Logistic Regression | `LogisticRegression(max_iter=5000)` | `C ∈ {0,01 ; 0,1 ; 1 ; 10}` |
| M2 | RBF-SVM | `SVC(kernel="rbf")` | `C ∈ {1 ; 10}` × `gamma ∈ {"scale" ; 0,01}` |
| M3 | Random Forest | `RandomForestClassifier(n_estimators=500)` | `max_features ∈ {"sqrt" ; 0,3}` × `min_samples_leaf ∈ {1 ; 5}` |
| M4 | Gradient Boosting | `HistGradientBoostingClassifier` | `learning_rate ∈ {0,05 ; 0,1}` × `max_leaf_nodes ∈ {31 ; 63}` |

Deux règles d'exécution déclarées ici :

- **M4** est réalisé par `HistGradientBoostingClassifier`, variante histogramme du gradient
  boosting de scikit-learn. Choix d'implémentation de la famille, pas changement de famille.
- **M2** est en O(n²). La sélection de grille se fait **sans** estimation de probabilités
  (exactitude seule) ; le refit final active `probability=True`. Si `n_train > 10 000`, le SVM
  est ajusté sur un **sous-échantillon stratifié de 10 000 lignes de TRAIN**, graine
  **22260822**. Règle uniforme, indépendante de tout résultat.

Une cellule qui ne converge pas ou dépasse **120 minutes** est déclarée `NOT_EXECUTABLE` avec
son motif, et **n'est pas remplacée**.

---

## 4. Découpage

Séparation stricte **TRAIN / CALIBRATION / TEST**. Graine globale **22260822**.

| Analyse | TRAIN | CALIBRATION | TEST |
|---|---|---|---|
| Principale, D1 à D4 | 60 % | 20 % | 20 % — tirage **stratifié par classe** |
| `NATURAL_TEMPORAL_SHIFT`, D1 seulement | **batches 1 à 4** | **batches 5 et 6** | **batches 7 à 10** |

### 4.1 Scellement du TEST

Le TEST est **scellé** jusqu'à ce que soient terminés et figés : l'entraînement, le
prétraitement, les hyperparamètres, les scores ISO, les baselines, le choix de `PROB_BEST` et
la détermination du régime `CONFIDENCE_WEAK`. Il est ensuite ouvert **une seule fois**.

### 4.2 Prétraitement

Tout est appris **sur TRAIN uniquement**, puis appliqué tel quel à CALIBRATION et TEST :
colonnes constantes retirées ; indicatrice de manquant pour toute colonne dont le taux de
manquants sur TRAIN dépasse 5 % ; imputation par la **médiane de TRAIN** ; `StandardScaler`
ajusté sur TRAIN. Aucune sélection de variables, aucun rééquilibrage, aucune augmentation.
La colonne `ID` de D3 est retirée : ce n'est pas une caractéristique.

La **calibration probabiliste** (B4, B5) est ajustée **sur CALIBRATION uniquement**.

### 4.3 Analyse `NATURAL_TEMPORAL_SHIFT`

Découpage par batch écrit ci-dessus, **avant toute ouverture de résultat**. Vérification
obligatoire : les **6 classes** doivent être représentées dans chacune des trois parties. Si
ce n'est pas le cas, l'analyse de shift est déclarée **`NOT_EXECUTABLE`**, sans aucun
changement opportuniste du découpage. Cette analyse est rapportée **séparément** et n'entre
pas dans le décompte des critères du §9.

---

## 5. Baselines de confiance

Toutes calculées à partir d'objets ajustés sur TRAIN ou CALIBRATION seulement. Score orienté
« erreur probable ».

| # | Baseline | Score |
|---|---|---|
| B1 | Max predicted probability | `− max_k p_k` |
| B2 | Predictive entropy | `− Σ_k p_k log p_k` |
| B3 | Top-1 / top-2 margin | `− (p_(1) − p_(2))` |
| B4 | Calibration sigmoïde (Platt) | `− max_k p̃_k`, `p̃` recalibré par `CalibratedClassifierCV(cv="prefit", method="sigmoid")` ajusté **sur CALIBRATION** |
| B5 | Calibration isotonique | `− max_k p̃_k`, idem avec `method="isotonic"` |

B4 et B5 sont calculées lorsqu'elles sont mathématiquement applicables ; toute inapplicabilité
est signalée par cellule et la baseline est simplement absente du choix pour cette cellule.

**`PROB_BEST`** = la baseline parmi B1…B5 qui maximise `AUROC_CALIB(baseline → ERROR)`.
Choisie **uniquement sur CALIBRATION**, puis **gelée** pour le TEST. Égalité tranchée par
l'ordre B1 → B5.

---

## 6. Définition préalable du régime

`ERROR = 1[prédiction incorrecte]`.

Pour chaque cellule dataset × modèle, sur **CALIBRATION uniquement** :

```
CONFIDENCE_WEAK  ⟺  AUROC_CALIB(PROB_BEST → ERROR) < 0,70
```

**Le seuil 0,70 est gelé.** Aucun autre seuil ne sera essayé si celui-ci donne trop peu de
cellules. Le régime n'est **jamais** défini à partir d'une performance sur TEST.

Si **moins de 3 jeux de données indépendants** possèdent au moins une cellule
`CONFIDENCE_WEAK`, alors `REGIME_IDENTIFIABLE = NO` et la revendication générale H22 ne peut
pas être validée. **Le seuil n'est pas abaissé.**

---

## 7. Test principal — information incrémentale

Pour chaque cellule `CONFIDENCE_WEAK`, deux modèles meta de même forme, régression logistique
régularisée `LogisticRegression(penalty="l2", C=1.0, max_iter=5000)`, ajustés **sur
CALIBRATION uniquement**, sans aucune interaction ni ingénierie de variables :

| Modèle | Entrées |
|---|---|
| **META_BASE** | `slog(PROB_BEST)` |
| **META_ISO** | `slog(PROB_BEST)` + `slog(iso_d_nearest)` + `slog(iso_margin_ratio)` + `slog(iso_centroid_min)` |

avec `slog(x) = signe(x)·log1p(|x|)`, comme aux phases précédentes. Les entrées sont
standardisées par un `StandardScaler` ajusté sur CALIBRATION.

Évaluation **unique sur TEST**.

- **Contraste principal** : `ΔAUROC = AUROC(META_ISO) − AUROC(META_BASE)`.
- **Contraste secondaire** : `ΔAURC = AURC(META_BASE) − AURC(META_ISO)` — positif = amélioration.
- Également mesurés : `AUPRC(ERROR)`, la courbe risque-couverture, et l'**exactitude conservée**
  aux couvertures **90 %, 80 %, 70 %** (les points les moins confiants étant rejetés d'abord).

---

## 8. Statistique

- **Bootstrap apparié 95 %** par cellule, 2 000 rééchantillonnages ; unité = la ligne de TEST.
  Pour l'analyse `NATURAL_TEMPORAL_SHIFT`, unité = la ligne, le batch étant déjà la variable de
  découpage.
- **p-value bilatérale** issue du bootstrap apparié :
  `p = 2 · min( P(Δ ≤ 0), P(Δ ≥ 0) )`, bornée à 1.
- **Correction de Holm** sur l'ensemble des tests confirmatoires ΔAUROC, un par cellule
  `CONFIDENCE_WEAK`. Sont rapportés : estimations brutes, IC 95 %, p-values brutes, et
  **décisions après Holm**. Un résultat nominalement significatif qui échoue après correction
  **n'est jamais** présenté comme confirmé.
- **Agrégation hiérarchique stratifiée**, pour que le plus grand jeu ne domine pas :
  l'estimateur global est la **médiane, sur les jeux, de la médiane par jeu** des ΔAUROC des
  cellules `CONFIDENCE_WEAK`. Son IC 95 % est obtenu par bootstrap apparié qui rééchantillonne
  les lignes de TEST **à l'intérieur de chaque cellule** et recalcule la statistique
  hiérarchique. Chaque jeu pèse donc autant, quel que soit son effectif.

---

## 9. Critère de succès strict

### REGIME_IDENTIFIABLE

`YES` **seulement si** `CONFIDENCE_WEAK` est détecté sur CALIBRATION dans **≥ 3 jeux de données
indépendants**. `NO` sinon.

### INCREMENTAL_REGIME

`YES` **seulement si les huit conditions passent toutes** :

1. **≥ 3 jeux** indépendants montrent une **médiane ΔAUROC positive** ;
2. **≥ 2 familles** différentes de classifieurs participent au résultat ;
3. la **médiane globale** des ΔAUROC des cellules `CONFIDENCE_WEAK` est **≥ +0,020** ;
4. l'**IC 95 % stratifié** de cette amélioration **exclut 0** ;
5. **≥ 3 cellules individuelles**, réparties sur **≥ 3 jeux**, ont un gain **confirmé après
   correction de Holm** ;
6. l'effet **n'est pas uniquement porté par Random Forest** — le retrait de M3 laisse les
   conditions 1, 2, 3 et 5 satisfaites ;
7. **ΔAURC est également favorable globalement** (médiane stratifiée > 0) ;
8. **META_ISO améliore META_BASE** : il ne suffit pas qu'ISO_PRED seul paraisse bon.

**Une seule cellule positive ne peut jamais donner `YES`.**

### Verdicts dérivés

- `ROBUST_ACROSS_DATASETS = YES` si les conditions 1 et 5 passent.
- `ROBUST_ACROSS_MODELS = YES` si les conditions 2 et 6 passent.
- `PROBABILITY_BASELINE_BEATEN = YES` si les conditions 3, 4 et 8 passent.

---

## 10. Verdicts autorisés

```
REGIME_IDENTIFIABLE:         YES / NO
INCREMENTAL_REGIME:          YES / NO
ROBUST_ACROSS_DATASETS:      YES / NO
ROBUST_ACROSS_MODELS:        YES / NO
PROBABILITY_BASELINE_BEATEN: YES / NO
PHASE22_RESULT:              CONFIRMED / LIMITED / FALSIFIED / INCONCLUSIVE_ACCESS
```

---

## 11. Interprétation gelée

**CONFIRMED** — si `REGIME_IDENTIFIABLE = YES` **et** `INCREMENTAL_REGIME = YES` **et**
`ROBUST_ACROSS_DATASETS = YES` **et** `ROBUST_ACROSS_MODELS = YES`.
Seule interprétation autorisée : « Une mesure géométrique d'isolabilité apporte une information
complémentaire reproductible dans certains régimes où les indicateurs probabilistes de
confiance discriminent mal les erreurs. »

**LIMITED** — un signal existe mais échoue à au moins un critère de réplication.
Interprétation : résultat **local et conditionnel**. Aucune revendication technologique
générale.

**FALSIFIED** — aucun régime reproductible, ou aucune valeur incrémentale robuste.
Conséquence : **fermeture de la branche ISO comme technologie différenciante**. Le résultat
scientifique de la Phase 21 — « ISO prédit les erreurs au-dessus du hasard » — reste archivé,
mais aucun développement produit n'est justifié.

**INCONCLUSIVE_ACCESS** — si l'accès ou l'intégrité des données empêche d'exécuter le test.

---

## 12. Interdiction de sauvetage

Après ouverture du TEST, il est **interdit** de : modifier ISO ; modifier le seuil 0,70 ;
ajouter un jeu de données ; retirer un jeu défavorable ; changer les classifieurs ; inventer un
nouveau sous-groupe ; changer les métriques primaires ; rechercher un autre régime ; créer
R8 / R9 / etc. ; introduire FO, B\*, Visibility ou Robustness ; optimiser spécifiquement le
résultat négatif.

Toute observation intéressante hors protocole va en **ANNEXE EXPLORATOIRE** et **n'autorise
aucune Phase 23**.

---

## 13. Commits obligatoires

| Commit | Contenu | Règle |
|---|---|---|
| **A** `PHASE22_PROTOCOL_FROZEN` | ce fichier seul — protocole, critères, splits, seuils, jeux, modèles, métriques, règles d'arrêt | poussé **avant tout résultat** |
| **B** `PHASE22_DATA_GATE` | acquisition, empreintes, contrôles d'intégrité, splits matérialisés, vérification des classes — **aucun résultat confirmatoire** | distinct de A |
| **C** `PHASE22_RESULTS` | résultats complets et verdict | distinct de A et B |

---

## 14. Livrable final

Rapport unique `RAPPORT_PHASE22_BR.md` contenant : empreinte du protocole gelé ; jeux
réellement exécutables ; tableau des 16 cellules ; cellules `CONFIDENCE_WEAK` déterminées
uniquement sur CALIBRATION ; AUROC / AUPRC / AURC ; Δ META_ISO contre META_BASE ; IC bootstrap ;
correction de Holm ; résultats par jeu ; résultats par famille de modèle ; analyse
`NATURAL_TEMPORAL_SHIFT` séparée ; anomalies et limites ; verdicts littéraux ; verdict
scientifique final.

Se terminant obligatoirement par les six verdicts, puis **une seule phrase** :
`BRANCH_DECISION: CONTINUE_TO_VALIDATION` ou
`BRANCH_DECISION: CLOSE_ISOLABILITY_TECH_BRANCH`.

**Aucune Phase 23 ne sera exécutée automatiquement.**

---

**Graine globale : 22260822. Bootstrap : 2 000. Seuil de régime : AUROC_CALIB < 0,70.
Seuil de pertinence pratique : ΔAUROC ≥ +0,020. Correction : Holm.**
