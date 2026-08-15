# Phase 11D — Gate R2 (Net3 Time Horizon) contre le classeur EPA officiel

**Verdict : GATE R2 — FAILED.** La branche de reproduction est arrêtée conformément à
l'instruction. FO n'a pas été testé, FO n'a pas été modifié, aucun FO-v2 n'a été créé,
aucun paramètre n'a été ajusté sur les résultats cibles.

Repris depuis le commit `76b8c45`.

---

## 1. Ce que les deux artefacts fournis ont changé

| Artefact | SHA256 | Rôle |
|---|---|---|
| `Data_A-pg4z_TestSourceInversion_Haxton_20160728.xlsx` | `3790e6b2…f53b38a6` | vérité de référence |
| `REPRODUCTION_GATE_PROTOCOL.md` | `0caf2e43…93a99162` | Gates préenregistrés |

Les deux fichiers sont versionnés inchangés dans `phase11_epa/official/`.

### Résultat inattendu et important : les cibles n'ont pas bougé

Les valeurs Time Horizon transcrites depuis le brief en Phase 11B sont **identiques**
à celles du classeur officiel pour la méthode Probability Based :

```
accuracy     1,  1, 44, 100, 100, 100
specificity 35, 52, 72,  90,  90,  90
```

Conséquence directe : l'échec de 11B/11C n'était pas causé par de mauvaises cibles, et la
borne d'atteignabilité établie en 11C se transporte telle quelle sur les données officielles.
Le classeur ne réhabilite pas la reproduction — il confirme le cadre dans lequel elle échouait.

---

## 2. Gate R0 — intégrité : PASSED

Les trois réseaux officiels (USEPA/Water-Security-Toolkit @07f997cc) reparsés :

| Fichier | Jonctions | Nœuds totaux | Attendu |
|---|---|---|---|
| `Net3.inp` | 92 | **97** | 97 ✔ |
| `Net6.inp` | 3323 | **3358** | 3358 ✔ |
| `BWSN_Network_2.inp` | **12523** | 12527 | 12523 (voir ci-dessous) |

La définition de spécificité est revérifiée sur le classeur officiel, exacte sur **9 cellules
sur 9** (3 méthodes × 3 réseaux), à 10⁻⁹ près :

```
specificite = 1 - n_ge / n_noeuds      n_ge = nb de candidats de score >= la vraie source
```

### Correction apportée aux phases antérieures

Les phases 11B/11C utilisaient 12 527 comme dénominateur BWSN2. Le classeur donne 12 523 :

```
1 - 45/12523 = 99.64066118342251   publié 99.64066118342251   EXACT
1 - 45/12527 = 99.64077592400416   publié 99.64066118342251   écart 1.1e-4
```

Le papier compte donc les jonctions seules pour BWSN2, mais tous les nœuds pour Net3 (97) et
Network2 (3358) — incohérence interne au papier. **Net3 n'est pas affecté, donc R2 non plus.**

---

## 3. Gate R2 — Time Horizon : FAILED sur les trois conditions

Reproduction rejouée sur Net3, 92 scénarios × 6 horizons × 2 méthodes = 1 104 lignes
(`phase11_epa/phase11d/EVENT_LEVEL_PHASE11D.csv`), aux paramètres **gelés en 11B et non
re-choisis ici**.

### Condition 1 — RMSE spécificité ≤ 5 points : **ÉCHEC**

| Méthode | RMSE spécificité | Gate | Statut |
|---|---|---|---|
| Probability Based | **31.95** | ≤ 5 | échec |
| Contaminant Status | **20.06** | ≤ 5 | échec |

Ce chiffre est honnêtement gonflé par un défaut du gel 11B : l'injection démarre à t = 2 h,
donc les horizons 1 h et 2 h ne contiennent **aucune observation par construction** (spécificité
bloquée à 5.15 %, les 92 candidats à égalité). Je le signale plutôt que de le masquer.

Ce défaut n'est cependant pas la cause de l'échec. Le balayage d'atteignabilité de 11C couvrait
`start_h ∈ {0, 1, 2}` :

| | valeur |
|---|---|
| paramétrisations balayées | 135 |
| couvre `start_h = 0` | oui |
| **meilleur RMSE spécificité atteignable** | **8.72** |
| gate | ≤ 5 |
| paramétrisations passantes | **0 / 135** |

Meilleure courbe atteignable vs publiée :

```
horizon      1h    2h    4h    8h   16h   24h
publié     35.0  52.0  72.0  90.0  90.0  90.0
meilleur   36.5  58.3  64.2  72.4  85.3  85.4
```

L'écart est une contrainte de **forme** concentrée sur la montée 4 h → 8 h (publié 72 → 90,
meilleur atteignable 64.2 → 72.4), pas un décalage de niveau.

### Densité de capteurs nominale — récupérée, non ajustée

Le classeur permet pour la première fois de trianguler la configuration nominale, en croisant
les quatre feuilles qui rapportent un cas Net3 non perturbé :

| Feuille | Condition | Spécificité PB |
|---|---|---|
| Measurement Error | FPR = FNR = 0 | 90.0 |
| Modeling Error | erreur de demande 0 % | 89.0 |
| Time Horizon | plateau 8/16/24 h | 90.0 |
| Sensor Placement | densité optimale 10 % | 89.0 |

La densité nominale Probability Based est donc **10 %** (≈ 10 capteurs sur Net3). Ce n'est pas
un paramètre ajusté sur la cible : il est déduit de la cohérence croisée du classeur.
Or dans le balayage 11C, les configurations à 10 capteurs plafonnent à **RMSE 13.86** — l'échec
persiste, d'un facteur ≈ 2.8, à la densité nominale indépendamment récupérée.

### Condition 2 — RMSE accuracy ≤ 5 points : **NON ÉVALUABLE**

La définition d'« accuracy » reste indéterminée **même avec le classeur officiel**. Ce n'est
plus une lacune documentaire, c'est un résultat démontrable :

1. Le classeur exclut le top-1 unique — feuille Network Size : accuracy 100 % alors que
   30 nœuds sont aussi ou plus vraisemblables que la vraie source.
2. Il exclut aussi toute règle d'appartenance à un ensemble sur une information croissante.
   Feuille Time Horizon, méthode CSA : accuracy 20 % à 1 h et 100 % à 24 h.
   - Un CSA par consistance sur données non bruitées retient **toujours** la vraie source →
     accuracy 100 % à tout horizon. Ma réimplémentation le confirme : 100 % aux six horizons.
   - Un CSA bruité capable d'écarter la vraie source à 1 h l'écarterait **davantage** à 24 h,
     les lectures s'accumulant. Le classeur rapporte l'inverse.

   Aucune règle d'appartenance monotone ne produit les deux. La définition publiée n'est donc
   pas récupérable depuis les artefacts fournis.

Les deux hypothèses testées et rapportées (sans jamais servir à régler quoi que ce soit) —
appartenance à l'argmax avec ex æquo (H1), appartenance à l'ensemble candidat à 25 % du max
(H2) — donnent respectivement RMSE 73.29 et 66.03 pour PB. Elles sont rapportées comme
réfutées, pas comme candidates.

### Condition 3 — plateau à 100 % dès 8 h pour les trois méthodes : **NON ÉVALUABLE**

Deux méthodes sur trois sont implémentées. La méthode Optimization de WST exige un solveur MIP
compilé (Merlion / Pyomo), indisponible ici. La condition porte explicitement sur les trois
méthodes : elle ne peut pas être évaluée.

---

## 4. Un fait supplémentaire que seul le classeur révèle

Le cas nominal Net3 n'est **pas le même d'une feuille à l'autre** :

| Méthode | Time Horizon (plateau) | Network Size (Net3) | Écart |
|---|---|---|---|
| Probability Based | 90.00 (n_ge = 9.7) | 69.07 (n_ge = 30) | **20.93 pts** |
| Contaminant Status | 77.67 (n_ge = 21.7) | 64.95 (n_ge = 34) | 12.72 pts |
| Optimization | 90.00 (n_ge = 9.7) | 69.07 (n_ge = 30) | **20.93 pts** |

Même réseau, même méthode, deux configurations expérimentales différentes — et le classeur ne
documente pas le design de capteurs par expérience. La cible Time Horizon n'est donc pas
identifiable à partir du classeur seul, même pour une réimplémentation parfaite.

---

## 5. Classification de l'échec

| Cause | Statut |
|---|---|
| `FAILED_IMPLEMENTATION` | **PRIMAIRE** — la réponse en horizon de ma vraisemblance de Bernoulli sur lectures discrétisées diffère structurellement de la formulation WST/Merlion |
| `INSUFFICIENT_INFORMATION` | **BLOQUANTE ET AGGRAVÉE** — deux des trois conditions de R2 sont désormais démontrées inévaluables depuis les artefacts fournis, quelle que soit la qualité de l'implémentation |
| `FAILED_DATA_MATCH` | NON APPLICABLE |
| `FAILED_PUBLISHED_REPRODUCTION` | **NON ÉTABLI** — il est montré que *cette* réimplémentation échoue, pas que Seth et al. (2016) est irreproductible |

Ce que 11D ajoute à 11C : en 11C on pouvait encore espérer que le classeur manquant lèverait
l'indétermination. Il est arrivé, et il ne la lève pas — il la **démontre**. R2 n'est pas
franchissable avec les artefacts en main, indépendamment de l'effort d'implémentation.

---

## 6. Conséquence sur FO

**FO n'a pas été testé.** Deux règles convergent :

- la règle d'arrêt du protocole préenregistré : « Si la reproduction ne franchit pas les Gates
  R1–R5, aucun verdict FO sur ce benchmark n'est autorisé » ;
- l'instruction reçue : « FO ne doit être testé que si les Gates requis sont franchis ».

| | |
|---|---|
| `FO_DIAGNOSTIC` | `NOT_EVALUATED_REPRODUCTION_FAILED` |
| `FO_RECONSTRUCTIBILITY` | `NOT_EVALUATED_REPRODUCTION_FAILED` |
| `FO_APPLICATION_BRANCH` | `UNDECIDED` |
| FO modifié | non |
| FO-v2 créé | non |
| Paramètres ajustés sur les cibles | non |

Un résultat FO favorable obtenu sur une reproduction six fois hors de son gate mesurerait la
réponse en horizon de ma propre vraisemblance, pas celle de la méthode publiée. Un résultat
défavorable serait imputable à ma réimplémentation. Dans les deux cas il serait inutilisable.

---

## 7. Ce qu'il faudrait pour rouvrir la branche

Par ordre de valeur décroissante :

1. **Les données événementielles** (postérieurs par source, rang de la vraie source, mesures par
   capteur et par temps, design de capteurs) — le classeur n'agrège que des moyennes.
2. **Le papier** (`10.1061/(ASCE)WR.1943-5452.0000619`) pour la définition d'« accuracy » et le
   design de capteurs par expérience. Le domaine reste bloqué par le proxy réseau ; un dépôt du
   PDF dans la session suffirait.
3. **Un WST compilé** avec solveur MIP, pour la troisième méthode.

Sans (1) ou (2), R2 restera inévaluable, et il n'y a pas de contournement méthodologique
honnête — c'est précisément ce que la présente phase établit.

---

## Fichiers produits

```
phase11_epa/official/                       les deux artefacts, inchangés
phase11_epa/phase11d/GATE_R2_RESULT.json    verdict R2 machine-lisible
phase11_epa/phase11d/OFFICIAL_TIME_HORIZON.csv          cibles lues dans le XLSX
phase11_epa/phase11d/SPECIFICITY_DEFINITION_CHECK.csv   9/9 exact
phase11_epa/phase11d/REPRODUCTION_SCORECARD_11D.csv     reproduit vs publié
phase11_epa/phase11d/EVENT_LEVEL_PHASE11D.csv           1104 lignes
phase11_epa/phase11d/CROSSSHEET_*.csv|json              analyse inter-feuilles
src/phase11d_reproduce.py                   reproduction R2
src/phase11d_crosssheet.py                  analyse de cohérence du classeur
phase11_epa/logs/11d_*.log                  journaux d'exécution
```

Les phases 11B et 11C sont préservées intactes comme contrôle négatif. Rien n'a été supprimé
ni réinterprété.
