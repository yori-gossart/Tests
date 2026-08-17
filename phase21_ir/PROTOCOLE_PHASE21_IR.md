# Protocole Phase 21-IR — Independent Isolability Replication

**PRÉ-ENREGISTRÉ ET GELÉ. Écrit et commité AVANT toute exécution produisant un résultat.**

Objectif unique : **tenter de falsifier** la capacité du score d'isolabilité gelé en
Phase 20-DR à prédire, sans étiquette de test, les erreurs de classification hors de son
environnement de découverte.

Aucune amélioration de SIGMA. Aucune architecture nouvelle. `src/fo_metrics.py` reste
inchangé et non importé. **Visibility, Robustness, R7, FO et B\* sont interdits dans cette
phase** et ne sont calculés nulle part.

---

## 0. Deux constats bloquants établis AVANT le gel

Ces deux constats sont antérieurs à toute exécution de la Phase 21-IR. Ils sont inscrits ici
plutôt que découverts en cours de route, et ils contraignent le protocole.

### 0.1 Le score d'isolabilité gelé utilise l'étiquette VRAIE

Relecture de `src/phase20_dr_run.py` (gelé au commit `894d2d5`) :

```python
own    = np.array([ks.index(v) for v in y])       # y = etiquette VRAIE
d_own  = np.sqrt(d2[np.arange(len(y)), own])
d_near = np.sqrt(np.where(mask, d2, np.inf).min(axis=1))
cmin   = np.array([cd[own[i]].min() for i in range(len(y))])
```

Les **trois** variables (`iso_d_nearest`, `iso_margin_ratio`, `iso_centroid_min`) dérivent de
`own`, donc de l'étiquette vraie, y compris sur le TEST. Vérifié sur les données produites en
Phase 20-DR : `iso_centroid_min` ne prend que 3 valeurs distinctes pour 4 classes de vanne et
2 pour 3 classes de pompe — c'est une table de correspondance sur la classe vraie.

**Conséquence.** La prémisse de cette phase est fausse pour l'implémentation gelée telle
quelle. Un erratum a été ajouté au rapport Phase 20-DR dans le même commit que ce protocole.

**Traitement retenu, gelé ici.** Deux variantes, séparées et jamais confondues :

| Variante | `own` provient de | Statut |
|---|---|---|
| **ISO_FROZEN** | l'étiquette **vraie** | référence uniquement — **ne peut fonder aucun verdict** |
| **ISO_PRED** | l'étiquette **prédite par le classifieur** | **seule variante servant aux verdicts** |

`ISO_PRED` est la **seule adaptation d'interface** autorisée : la formule n'est pas touchée,
seule la source de l'argument `own` change. Elle est documentée au §1.3. Sans elle, il
n'existe aucune version exempte de fuite du score gelé, et la phase serait inexécutable.

`ISO_FROZEN` est calculé et rapporté parce que le taire reviendrait à masquer l'ampleur du
défaut ; il est étiqueté `ORACLE` dans tous les livrables.

### 0.2 Les quatre hôtes officiels sont bloqués par la politique réseau

Sondage effectué avant le gel, journalisé dans `phase21_ir/logs/` :

| Hôte | Réponse |
|---|---|
| `archive.ics.uci.edu` | **403 au CONNECT** (refus de politique du relais) |
| `www.openml.org` | **403 au CONNECT** |
| `api.openml.org` | **403 au CONNECT** |
| `raw.githubusercontent.com`, `github.com` (git), `api.github.com` | accessibles |

Aucun des quatre jeux de données ne peut donc être obtenu de sa source officielle. Des copies
existent dans des dépôts GitHub tiers, **d'intégrité non vérifiable par somme de contrôle
contre l'original**, et certaines sont démontrablement modifiées (un dépôt sondé porte un
fichier `aps_failure_training_set_SMALLER.csv` de 19 999 lignes au lieu de 60 000 ; un autre
un fichier de 36 188 lignes).

**Traitement retenu, gelé ici : Gate A de conformité structurelle** (§2.2). Un jeu de données
n'est admis que si une copie **conforme aux effectifs officiellement documentés** est trouvée.
Sinon il est déclaré `NOT_EXECUTABLE` et **rapporté comme tel, jamais remplacé, jamais
réparé, jamais reconstruit**.

---

## 1. Le score d'isolabilité — implémentation exacte

### 1.1 Code gelé, repris verbatim de `src/phase20_dr_run.py`

```python
def isolability(X, y, cents, Sinv):
    ks = sorted(cents)
    C = np.stack([cents[k] for k in ks])
    diff = X[:, None, :] - C[None, :, :]
    d2 = np.maximum(np.einsum("nkc,cd,nkd->nk", diff, Sinv, diff), 0.0)
    own = np.array([ks.index(v) for v in y])
    mask = np.ones_like(d2, dtype=bool)
    mask[np.arange(len(y)), own] = False
    d_own = np.sqrt(d2[np.arange(len(y)), own])
    d_near = np.sqrt(np.where(mask, d2, np.inf).min(axis=1))
    cd = np.array([[np.sqrt(max((C[i] - C[j]) @ Sinv @ (C[i] - C[j]), 0.0))
                    for j in range(len(ks))] for i in range(len(ks))])
    np.fill_diagonal(cd, np.inf)
    cmin = np.array([cd[own[i]].min() for i in range(len(y))])
    return {"iso_d_nearest": d_near, "iso_margin_ratio": d_near / (d_own + 1.0),
            "iso_centroid_min": cmin}
```

**Aucun caractère de cette fonction n'est modifié.** Elle est copiée telle quelle dans
`src/phase21_ir_iso.py` et le fichier porte l'empreinte SHA-256 de la fonction source.

Estimateurs d'entrée, identiques à la Phase 20-DR :
`cents[k] = X_train[y_train == k].mean(0)` ; `Sinv = np.linalg.pinv(LedoitWolf(assume_centered=False).fit(X_train).covariance_)`.
Centroïdes et covariance viennent **du TRAIN seul**.

### 1.2 Adaptations d'interface, exhaustivement documentées

| # | Adaptation | Justification |
|---|---|---|
| A1 | `own` construit à partir de l'étiquette **prédite** (variante ISO_PRED) | seule manière d'obtenir une version sans fuite ; formule inchangée |
| A2 | `X` est la matrice de caractéristiques du jeu de données, non les 17 × 8 statistiques capteur du banc ZeMA | l'entrée de la fonction est une matrice `(n, p)` quelconque ; aucun changement mathématique |
| A3 | `cents` porte sur les classes du jeu de données (2 à 6 classes selon le cas) | idem |
| A4 | Pour K = 2 classes, `iso_centroid_min` est **constant** (une seule paire de centroïdes) et donc de variance nulle | déclaré ici : dégénérescence attendue sur APS et SECOM, la variable est conservée par fidélité et son inutilité est signalée dans le rapport |

Aucune autre adaptation ne sera introduite. Toute impossibilité rencontrée sera signalée, pas
contournée.

### 1.3 Score soumis au test

| Nom | Définition | Ajusté sur |
|---|---|---|
| **ISO_FIT** (primaire) | régression logistique sur `signe(x)·log1p(\|x\|)` des trois variables, prédisant ERROR | **CALIBRATION uniquement** |
| ISO_RAW (secondaire) | `− iso_margin_ratio` seul, orientation déclarée : isolabilité haute ⇒ erreur peu probable | aucun ajustement |

`ISO_FIT` reproduit la construction du modèle R2 de la Phase 20-DR (logistique sur les trois
variables d'isolabilité). C'est lui qui porte les verdicts.

---

## 2. Jeux de données pré-enregistrés

Les quatre sont fixés. **Aucun ne pourra être retiré après observation d'un résultat.** Un
jeu de données ne peut sortir que par le Gate A, qui ne regarde que des effectifs et
s'exécute avant tout ajustement de modèle.

| # | Jeu | Réf. | Effectifs officiels attendus | Cible |
|---|---|---|---|---|
| D1 | APS Failure at Scania Trucks | UCI 421 | TRAIN 60 000 × 171 (1 000 pos / 59 000 neg) ; TEST 16 000 × 171 (375 pos / 15 625 neg) | binaire `pos`/`neg` |
| D2 | SECOM | UCI 179 | `secom.data` 1 567 × 590 ; `secom_labels.data` 1 567 lignes, 104 pos / 1 463 neg | binaire −1/+1 |
| D3 | Steel Plates Faults | UCI 198 | 1 941 × 34 (27 caractéristiques + 7 indicatrices de défaut) | 7 classes |
| D4 | Human Activity Recognition Using Smartphones | UCI 240 | `X_train` 7 352 × 561, `X_test` 2 947 × 561 ; 6 activités ; 30 sujets, 21 en TRAIN / 9 en TEST | 6 classes |

### 2.1 Sources d'acquisition, ordre gelé

1. Hôte officiel (`archive.ics.uci.edu`) — connu bloqué, tenté et journalisé quand même.
2. `openml.org` — connu bloqué, tenté et journalisé quand même.
3. Miroirs GitHub publics, par clone `git` ou `raw.githubusercontent.com`. La recherche de
   miroirs est **bornée à 6 dépôts candidats par jeu de données**, journalisés avec leur URL,
   leur commit et le résultat du Gate A. Au-delà, le jeu est déclaré `NOT_EXECUTABLE`.

### 2.2 Gate A — conformité structurelle, avant tout modèle

Une copie est admise si et seulement si **tous** les points suivants sont vérifiés :

- nombre de lignes et de colonnes **exactement** égal à l'effectif officiel du tableau ci-dessus ;
- effectifs par classe exactement égaux quand la documentation officielle les donne (D1, D2) ;
- pour D1 et D4, découpage officiel TRAIN/TEST présent et intact ;
- aucune colonne ajoutée, renommée, imputée, rééchelonnée ou réordonnée par le miroir ;
- aucun fichier dont le nom signale une transformation (`_SMALLER`, `_processed`, `_clean`,
  `_balanced`, `_sample`).

Résultat consigné par jeu : `EXECUTABLE` ou `NOT_EXECUTABLE` avec le motif exact.
**L'impossibilité est un résultat rapportable, pas un problème à réparer.** Le caveat
d'intégrité — aucune vérification par somme de contrôle contre l'original UCI n'est possible
depuis cet environnement — est répété dans le rapport final pour chaque jeu admis.

---

## 3. Familles de classifieurs pré-enregistrées

Les quatre sont fixées. **Aucune ne pourra être retirée après observation d'un résultat.**
Hyperparamètres gelés, aucun réglage, aucune recherche.

| # | Famille | Implémentation gelée |
|---|---|---|
| M1 | Logistic Regression | `LogisticRegression(max_iter=5000, C=1.0, random_state=21260821)` |
| M2 | RBF-SVM | `SVC(C=1.0, gamma="scale", probability=True, random_state=21260821)` |
| M3 | Random Forest | `RandomForestClassifier(n_estimators=500, random_state=21260821, n_jobs=-1)` |
| M4 | Gradient Boosting | `HistGradientBoostingClassifier(random_state=21260821)` |

Deux points déclarés à l'avance :

- **M4** est réalisé par `HistGradientBoostingClassifier`, variante histogramme du gradient
  boosting de scikit-learn, retenue pour sa capacité à traiter 60 000 × 170 et les valeurs
  manquantes. C'est un choix d'implémentation de la famille, pas un changement de famille.
- **M2** est en O(n²) : si `n_train > 20 000`, le SVM est ajusté sur un sous-échantillon
  stratifié de **20 000** lignes de TRAIN, graine **21260821**. Règle gelée, appliquée
  uniformément, indépendante de tout résultat.

Une cellule dataset × modèle qui ne converge pas ou dépasse un budget de **90 minutes** est
déclarée `NOT_EXECUTABLE` avec son motif, et **n'est pas remplacée**.

---

## 4. Découpage

**Le découpage officiel est préservé partout où il existe.**

| Jeu | TRAIN | CALIBRATION | TEST |
|---|---|---|---|
| D1 APS | découpage officiel : 80 % du TRAIN officiel | 20 % du TRAIN officiel, stratifié, graine 21260821 | **TEST officiel, 16 000 lignes, intact** |
| D2 SECOM | 60 % | 20 % | 20 % — stratifié, graine 21260821 (aucun découpage officiel) |
| D3 Steel | 60 % | 20 % | 20 % — stratifié, graine 21260821 (aucun découpage officiel) |
| D4 HAR | sujets du TRAIN officiel, 15 sujets | sujets du TRAIN officiel, 6 sujets | **TEST officiel, 9 sujets, intact** |

Pour D4, la coupure TRAIN/CALIBRATION est faite **par sujet**, jamais par fenêtre : les
fenêtres d'un même sujet restent entières du même côté. C'est l'unité d'indépendance de ce
jeu, et le TEST officiel est déjà disjoint en sujets.

Le TEST n'est ouvert qu'une fois, pour les endpoints finaux.

---

## 5. Prétraitement

Tout est appris **sur TRAIN uniquement**, puis appliqué tel quel à CALIBRATION et TEST.

1. Colonnes constantes sur TRAIN : supprimées.
2. Valeurs manquantes : imputation par la **médiane de TRAIN** ; une indicatrice de manquant
   est ajoutée pour toute colonne dont le taux de manquants sur TRAIN dépasse 5 %.
3. Standardisation : `StandardScaler` ajusté sur TRAIN.
4. Aucune sélection de variables, aucun rééquilibrage de classes, aucune augmentation.

Le même TRAIN sert au classifieur, aux centroïdes, à la covariance Ledoit-Wolf et aux
baselines. Aucun de ces objets ne voit CALIBRATION ni TEST.

---

## 6. Définition de l'événement à prédire

```
ERROR = 1[ prediction != verite ]
```

L'étiquette vraie du TEST n'intervient **que** dans le calcul de `ERROR`, au moment de
l'évaluation finale. Elle n'entre ni dans ISO_PRED, ni dans une baseline, ni dans un
prétraitement, ni dans un ajustement.

---

## 7. Baselines obligatoires

Toutes calculées sur TEST à partir d'objets ajustés sur TRAIN ou CALIBRATION seulement.

| # | Baseline | Score orienté « erreur probable » |
|---|---|---|
| B1 | Max predicted probability | `− max_k p_k` |
| B2 | Predictive entropy | `− Σ p_k log p_k` |
| B3 | Top-1 / top-2 margin | `− (p_(1) − p_(2))` |
| B4 | kNN training-distance | distance euclidienne moyenne aux **k = 10** plus proches voisins de TRAIN |
| B5 | Mahalanobis class-conditionnel standard | `min_k (x − μ_k)ᵀ Σ⁻¹ (x − μ_k)`, μ_k et Σ (Ledoit-Wolf) estimés sur TRAIN — **minimum sur toutes les classes, sans étiquette** |
| B6 | Adaptive Prediction Sets (conformal) | taille de l'ensemble de prédiction APS au niveau α = 0,10, seuil calibré sur CALIBRATION (Romano, Sesia & Candès 2020) |

B5 est la baseline la plus proche parente d'ISO_PRED et son contraste est le plus informatif.

---

## 8. Mesures

Par cellule dataset × modèle :

- **AUROC** de prédiction d'ERROR ;
- **AUPRC** ;
- **risk-coverage** et **AURC** ;
- **IC 95 % bootstrap apparié**, 2 000 rééchantillonnages ; unité de rééchantillonnage :
  la ligne de TEST, sauf pour D4 où c'est le **sujet** ;
- **Δ AUROC** = ISO_FIT − meilleure baseline. La meilleure baseline est désignée **sur
  CALIBRATION**, jamais sur TEST ; le contraste contre la meilleure baseline *a posteriori*
  sur TEST est également rapporté, comme borne conservatrice ;
- **Combinaison** : régression logistique sur (meilleure baseline, ISO_FIT), ajustée **sur
  CALIBRATION uniquement**, évaluée sur TEST ; contraste contre la meilleure baseline seule.

Une cellule dont le TEST contient moins de **20 erreurs** est déclarée
`NOT_EVALUABLE_LOW_EVENTS` et exclue des médianes, avec son effectif rapporté. Seuil gelé ici.

---

## 9. Critères gelés avant tout calcul

### GENERALIZATION_PASS

1. AUROC **médiane** d'ISO_FIT ≥ **0,70** sur les cellules exploitables ;
2. **majorité forte** — au moins **⅔** — des cellules exploitables avec IC 95 % strictement
   au-dessus de 0,50 ;
3. effet présent dans **au moins 2 jeux de données** et **au moins 2 familles de modèles** ;
4. **aucun résultat positif ne dépend uniquement de Random Forest** : si l'on retire M3, les
   points 1 à 3 doivent encore tenir.

`YES` si les quatre points tiennent. `PARTIAL` si le point 1 tient mais pas les autres, ou
l'inverse. `NO` sinon.

### INCREMENTAL_VALUE_PASS

- gain ≥ **+0,02** d'AUROC contre la meilleure baseline, **ou**
- gain ≥ **+0,02** lorsque ISO_FIT est ajouté à la meilleure baseline ;
- dans les deux cas, le gain doit être **confirmé par IC 95 % apparié** excluant 0.

`YES` si l'une des deux conditions est remplie et confirmée. `NO` sinon.

### NOVELTY_SIGNAL

`SUPPORTED` seulement si `GENERALIZATION = YES` **et** `INCREMENTAL_VALUE = YES`.
`NOT_SUPPORTED` dans tous les autres cas.

---

## 10. Verdicts autorisés

```
GENERALIZATION:     YES / PARTIAL / NO
INCREMENTAL_VALUE:  YES / NO
NOVELTY_SIGNAL:     SUPPORTED / NOT_SUPPORTED
PHASE22_AUTHORIZED: YES / NO
```

### Règle d'arrêt

- `GENERALIZATION = NO` → **fermeture définitive de cette branche**.
- `GENERALIZATION = PARTIAL` → rapport de portée limitée, **aucune architecture nouvelle**.
- `GENERALIZATION = YES` et `INCREMENTAL_VALUE = NO` → résultat potentiellement réel, mais
  **aucun avantage démontré sur l'existant**.
- `PHASE22_AUTHORIZED = YES` **uniquement si** `GENERALIZATION = YES` **et**
  `INCREMENTAL_VALUE = YES`.

Si le nombre de cellules exploitables est inférieur à **4**, ou si moins de 2 jeux de données
ou moins de 2 familles de modèles sont exécutables, alors `GENERALIZATION = NO` par
insuffisance de matière, et le rapport le dit explicitement au lieu d'extrapoler.

---

## 11. Interdits

- Modifier une ligne de la fonction `isolability`.
- Utiliser l'étiquette vraie du TEST ailleurs que dans le calcul d'ERROR.
- Fonder un verdict sur `ISO_FROZEN`.
- Calculer Visibility, Robustness, R7, FO ou B\*.
- Importer ou modifier `src/fo_metrics.py`.
- Retirer un jeu de données ou une famille de modèles après avoir vu un résultat.
- Ajuster un seuil, un hyperparamètre, une baseline ou un critère après ouverture du TEST.
- Remplacer une source de données manquante par une reconstruction, une simulation ou un
  sous-échantillon non officiel.
- Revendiquer une nouveauté mathématique : Mahalanobis (1936), Hotelling (1931), Ledoit-Wolf
  (2004), APS conformal (Romano, Sesia & Candès 2020), risk-coverage (El-Yaniv & Wiener 2010)
  sont tous standards.

## 12. Portée

Ces quatre jeux sont des **jeux tabulaires publics standards**, sans rapport avec le banc
ZeMA. Un résultat positif y constituerait une réplication hors environnement de découverte.
Un résultat négatif ferme la branche. Dans les deux cas, rien n'est généralisé au-delà des
cellules effectivement exécutées, et rien n'est dit de FO ou de B\*, absents de cette phase.

---

**Graine globale : 21260821. Bootstrap : 2 000. Seuil de pertinence pratique : 0,02 d'AUROC.**
