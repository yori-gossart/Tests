# Protocole confirmatoire Phase 16 — PRÉ-ENREGISTRÉ ET GELÉ

**Écrit et commité AVANT la génération de la moindre graine Phase 16.** Le script de
génération `src/phase16_generate.py` refuse de démarrer si ce fichier est absent, et vérifie
la disjonction des graines avant toute simulation. Rien ci-dessous ne peut être modifié après
qu'un résultat Phase 16 existe ; un défaut découvert plus tard est consigné en amendement
daté, jamais en édition silencieuse.

`src/fo_metrics.py` reste inchangé. Aucun FO-v2. Aucune panne n'est retirée.

---

## 1. Ce que la Phase 15 a laissé à confirmer

L'exploration (rapport `phase15_tep/RAPPORT_PHASE15_EXPLORATOIRE.md`) a produit sept constats.
Ce sont des **hypothèses**, pas des résultats. La Phase 16 les teste en aveugle.

Les faits d'exploration qui déterminent les choix ci-dessous :

- `d_S` de FO est **identiquement** `max |δ|/σ` (écart maximal mesuré : 0,000e+00) ;
- FO est colinéaire à la norme L2 des canaux à ρ = 0,993 et **interchangeable** avec elle
  dans l'ensemble complet (0,9234 contre 0,9237) ;
- M10 − M9 = +0,0014 sur VALID, soit quatorze fois sous le seuil de pertinence ;
- B\* est battu par min/q05/CVaR sur le même support (0,635 contre 0,92).

---

## 2. Données confirmatoires

| | |
|---|---|
| Perturbations | **21** (IDV 1–21), aucune retirée, IDV 3, 9, 15 et 21 conservées |
| Graines | **50 nouvelles**, `2000000000 + 7919·i`, i = 0..49 |
| Disjonction Phase 14 | Phase 14 : `1000000000 + 7919·i`, maximum 1 000 388 031 → **aucun recouvrement**, vérifié en code avant génération |
| Réalisations nominales | **1 050** (+ 50 runs normaux appariés, partagés par graine) |
| Appariement | pour chaque graine, un unique run IDV=0 sert de contrefactuel aux 21 pannes, donc `δ = panne − normal` porte la **même réalisation de bruit** des deux côtés |
| Unité de réplication | la **graine**. Un pas temporel n'est jamais une observation indépendante |

### Cohorte de bruit confirmatoire — dimensionnée ici, avant génération

| | |
|---|---|
| Niveaux | σ ×2, ×4, ×8 |
| Graines par niveau | **20** (indices 0–19 des 50 nouvelles) |
| Réalisations par niveau | 21 × 20 = **420** |
| Runs simulateur | 3 × (20 + 420) = **1 320** |

Justification du dimensionnement : les hypothèses testées sur cette cohorte sont
**structurelles** (H4 : le support de B\* tient-il, B_dynamic s'effondre-t-il, la monotonie
est-elle préservée ?). Ce sont des propriétés de la métrique, pas des effets à détecter dans
le bruit d'échantillonnage ; 420 réalisations par niveau suffisent largement à observer un
support qui passe de 400 à quelques unités. Porter la cohorte à 50 graines triplerait le coût
sans changer le verdict structurel. Le nominal, lui, porte les hypothèses statistiques et
reçoit les 50 graines complètes.

Budget total : 1 100 + 1 320 = **2 420 runs**, ≈ 16 minutes à 4 cœurs au débit mesuré de
1,55 s/run.

---

## 3. Ce qui est réutilisé de Phase 14, et pourquoi

Ré-estimer l'un de ces objets sur les données Phase 16 ferait fuiter l'ensemble confirmatoire
dans le prédicteur. Tous sont donc **portés tels quels** :

| Objet | Source |
|---|---|
| σ par canal | `XNS(1..41)` déclaré dans `teprob.f`, jamais estimé |
| Covariance nulle `Σₙ` | Ledoit-Wolf sur les 25 runs normaux de Phase 14 TRAIN |
| Centroïdes de panne | profils blanchis moyens, Phase 14 TRAIN |
| Les 120 designs | graine 20260816, liste identique |
| Support `E*` | gelé sur Phase 14 TRAIN, κ = 30 |
| B\*(S) par design | calculé sur Phase 14 TRAIN, η = 3 |
| RandomForest | 500 arbres, `random_state` 20260816, entraîné sur Phase 14 TRAIN |
| Coefficients des 15 modèles | ajustés sur Phase 14 TRAIN+VALID, figés dans `FROZEN_MODELS.json` |

**Aucun réajustement n'a lieu en Phase 16.** Le script applique les coefficients gelés à des
réalisations issues de graines qui n'existent pas encore au moment de ce commit.

---

## 4. Modèles gelés

Quinze modèles, définis dans `FROZEN_MODELS.json` (features, μ, σ, coefficients, ordonnée).

| Modèle | Contenu |
|---|---|
| `M0_SNR` | SNR moyen |
| `M1_FO` | FO `d_S` |
| `M2_BSTAR` | B\* |
| `M3_FO_BSTAR` | FO + B\* |
| `M4_SNR_FO` | SNR + FO |
| `M5_SNR_FO_BSTAR` | SNR + FO + B\* |
| `M6_SNR_FO_BSTAR_INT` | + interaction FO×B\* |
| `M7_SNR_MAHA_ISO` | SNR + Mahalanobis + isolabilité |
| `M8_KL_ISO` | KL + isolabilité KL |
| **`M9_STANDARD_FULL`** | **ensemble standard complet, sans FO ni B\*** |
| **`M10_STANDARD_PLUS_FO_BSTAR`** | **M9 + FO + B\* + interaction** |
| `MD_DET_STD` | détectabilité standard : SNR + Mahalanobis + KL |
| `MD_DET_STD_FO` | + FO |
| `MI_VIS_ONLY` | SNR + FO |
| `MI_VIS_ISO` | + isolabilité standard |

`M9` est la **baseline technologique critique**.

---

## 5. Endpoint primaire

**AUROC pour l'échec de reconstruction** (`top-1 du RandomForest incorrect`), sur la cohorte
nominale Phase 16, poolée sur les 120 designs.

Endpoints secondaires obligatoires : AUPRC, score de Brier, log-loss, pente de calibration.

**Intervalles de confiance** : bootstrap apparié à 2 000 tirages, **rééchantillonnant la
graine** — l'unité de génération. Les 21 pannes d'une graine partagent la même séquence de
bruit ; les traiter comme indépendantes gonflerait la précision.

---

## 6. Hypothèses confirmatoires

| ID | Comparaison | Attendu si vraie |
|---|---|---|
| **H1** `FO_SIGNAL` | AUROC de `−d_S` seul contre l'échec | borne inférieure de l'IC > 0,5 |
| **H2** `FO_BEYOND_SNR` | `M4_SNR_FO` > `M0_SNR` | Δ ≥ 0,02 et IC > 0 |
| **H3** `FO_BEYOND_KL_MAHALANOBIS` | `MD_DET_STD_FO` > `MD_DET_STD` | Δ ≥ 0,02 et IC > 0 |
| **H4** `B_STAR_STRUCTURAL` | support de B\* constant, support de B_dynamic décroissant, B\* monotone en bruit | les trois |
| **H5** `B_STAR_OPERATIONAL` | \|ρ\| de B\* contre le taux d'échec du design ≥ \|ρ\| de la meilleure statistique de queue (min, q05, q10, CVaR 5 %, CVaR 10 %) sur le **même** support | B\* au moins à égalité |
| **H6** `FO_BSTAR_SYNERGY` | `M3_FO_BSTAR` > `M1_FO` | Δ ≥ 0,02 et IC > 0 |
| **H7** `ISOLABILITY_COMPLEMENT` | `MI_VIS_ISO` > `MI_VIS_ONLY` | Δ ≥ 0,02 et IC > 0 |
| **H8** `PROJECT_SPECIFIC_INCREMENT` | **`M10` > `M9`** | Δ ≥ 0,02 et IC > 0 |

**H8 est l'hypothèse technologique décisive.**

---

## 7. Seuil de pertinence pratique

Pré-enregistré, et interne au projet — ce n'est pas une norme du domaine :

```
YES    l'IC apparié à 95 % exclut 0  ET  Δ AUROC ≥ 0,02
WEAK   l'IC exclut 0  MAIS  Δ AUROC < 0,02
NO     l'IC contient 0
```

Une différence statistiquement positive mais inférieure à 0,02 est **WEAK, jamais YES**.

---

## 8. Analyses de robustesse obligatoires

Toutes rapportées, favorables ou non :

- global ; par panne ; par budget de capteurs (6 tailles) ; par niveau de bruit ;
- pannes visibles / invisibles, isolables / confusables (seuils = médianes Phase 14 TRAIN) ;
- **leave-one-fault-out** sur la comparaison H8 : Δ recalculé 21 fois, une panne exclue à
  chaque fois ;
- sensibilité à l'exclusion d'une panne : si le signe de Δ dépend d'une ou deux pannes, le
  résultat est déclaré fragile ;
- bootstrap apparié par graine partout.

---

## 9. Règles d'arrêt et interdits

1. Aucun réajustement de modèle sur les données Phase 16.
2. Aucun seuil, coefficient, design ou hypothèse modifié après le premier résultat.
3. Aucune panne retirée, en particulier pas IDV 3, 9, 15 ni 21.
4. Aucune métrique défavorable remplacée par une autre.
5. Aucun FO-v2, aucune modification de formule, quel que soit le résultat.
6. Si la cohorte nominale produit moins de 30 échecs ou moins de 30 succès, le verdict est
   INCONCLUSIVE — aucune lecture favorable de repli.
7. Si un run est tronqué (arrêt d'urgence du procédé), il est rapporté et exclu **des seules
   comparaisons qui exigent une population identique entre niveaux**, jamais des analyses
   nominales.

---

## 10. Règles de décision, fixées à l'avance

| Cas | Condition | Conséquence |
|---|---|---|
| **A** | `H3 = YES` et/ou `H8 = YES`, et `H5 ≥ WEAK` | poursuivre vers un second système externe |
| **B** | FO n'apporte rien au-delà des standards, mais B\* a une valeur opérationnelle robuste | abandonner FO comme élément différenciant ; continuer B\* seul |
| **C** | ni FO ni B\* n'apportent au-delà des standards | **fermer la branche technologique FO/B\*** ; ne conserver que les résultats scientifiques et négatifs ; ne créer aucune formule |
| **D** | la décomposition Visibilité/Robustesse/Isolabilité est meilleure, mais tout le gain vient de métriques standards | reconnaître l'architecture comme utile mais **non spécifique à FO** ; ne revendiquer aucune technologie propriétaire |

---

## 11. Verdicts à produire

```
FO_SIGNAL_REPLICATED:               YES / PARTIAL / NO
FO_BEYOND_SNR:                      YES / WEAK / NO
FO_BEYOND_KL_MAHALANOBIS:           YES / WEAK / NO
B_STAR_STRUCTURAL_VALUE:            YES / PARTIAL / NO
B_STAR_OPERATIONAL_VALUE:           YES / WEAK / NO
FO_BSTAR_SYNERGY:                   YES / WEAK / NO
ISOLABILITY_COMPLEMENTS_FO:         YES / WEAK / NO
PROJECT_SPECIFIC_INCREMENT:         YES / WEAK / NO
DIAGNOSTIC_READINESS_DECOMPOSITION: SUPPORTED / PARTIAL / NOT_SUPPORTED
TECHNOLOGY_CANDIDATE:               YES / NOT_YET / NO
```

---

## 12. Rappel de portée

TEP est un **benchmark simulé externe standard**. Un résultat positif y constitue un soutien
mécanistique contrôlé, **pas** une validation dans le monde réel. Aucune conclusion
commerciale, aucune généralisation à l'ADN, aux réseaux réels ou à un autre domaine ne sera
tirée de la Phase 16.
