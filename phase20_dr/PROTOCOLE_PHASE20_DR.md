# Protocole Phase 20-DR — Diagnostic Readiness sur banc physique ZeMA

**PRÉ-ENREGISTRÉ ET GELÉ. Écrit et commité AVANT tout résultat.**

---

## 0. Ce que cette phase n'est pas

Cette branche **n'est plus une validation FO/B\***. FO et B\* sont gelés :
`src/fo_metrics.py` n'est ni modifié ni importé, et **aucune quantité FO ou B\* n'est calculée
dans cette phase**. Aucune revendication de nouveauté mathématique n'est faite : toutes les
métriques employées sont standards et référencées.

L'objet du test est une architecture explicable à trois axes — **Visibilité, Robustesse,
Isolabilité** — et trois questions :

1. prévoit-elle qu'un diagnostic va échouer ?
2. identifie-t-elle **pourquoi** il va échouer ?
3. recommande-t-elle le **type d'action** correct ?

---

## 1. Périmètre confirmatoire

La Phase 19 a mesuré que le banc est un **plan par blocs** : 144 configurations réalisées en
194 blocs contigus, P(cycles consécutifs de même configuration) = 0,912.

Sont **exclus du test confirmatoire** les composants dont le plan n'autorise pas un véritable
hors-échantillon :

| Composant | Plages contiguës | Décision |
|---|---|---|
| **Vanne** | 145 | **inclus** |
| **Pompe** | 37 | **inclus** |
| Accumulateur | 12 (3 par niveau) | **exclu** — hors-échantillon marginal |
| Refroidisseur | **3 (1 par niveau)** | **exclu** — aucune réplication indépendante |

Refroidisseur et accumulateur restent présents comme **variables de nuisance** dans le
contexte expérimental ; ils ne sont jamais des cibles.

### Cycles retenus

Seuls les **1 449 cycles à drapeau de stabilité = 0** sont utilisés. Motif déclaré à
l'avance : le drapeau 1 signale que « static conditions might not have been reached yet » ;
inclure ces cycles confondrait l'étude de perturbations avec la montée en régime du banc.

Sur ces cycles, le plan est exactement équilibré : **144 configurations, 36 par niveau de
vanne, 48 par niveau de pompe, 12 configurations par cellule vanne × pompe**, médiane
10 cycles par configuration.

---

## 2. Découpage sans fuite

**Unité de découpage : la configuration** (144 unités). Une configuration reste entière d'un
seul côté, ce qui est **plus strict** que garder les blocs entiers, puisqu'une configuration
peut couvrir plusieurs blocs non contigus.

Interdits explicites : découper à l'intérieur d'un cycle ; traiter les points temporels d'un
cycle comme des répétitions ; traiter les cycles d'une même configuration comme indépendants.

| Split | Configurations par cellule vanne × pompe | Total configurations |
|---|---|---|
| TRAIN | 7 | 84 |
| VALID | 2 | 24 |
| TEST | 3 | 36 |

Stratification sur les 12 cellules vanne × pompe, graine **20260817**, tirage effectué avant
tout calcul. Le TEST n'est ouvert qu'une fois, à la fin.

**Bootstrap : 2 000 rééchantillonnages au niveau CONFIGURATION**, jamais au niveau cycle.

---

## 3. Caractéristiques et classifieur de référence

### Caractéristiques, gelées

Par capteur (17) et par cycle, 8 statistiques : moyenne, écart-type, minimum, maximum,
quartiles q25 / médiane / q75, et pente d'une régression linéaire sur l'indice temporel
intra-cycle. **136 caractéristiques**. Aucune sélection de variables.

### Classifieur, gelé

`RandomForestClassifier(n_estimators=500, random_state=20260817, n_jobs=-1)`.
Entraîné sur TRAIN uniquement pour chaque cible et chaque condition de perturbation.
Aucun réglage d'hyperparamètre, aucun seuil ajusté après résultat.

### Cibles

- **vanne** : 4 classes (73, 80, 90, 100 %)
- **pompe** : 3 classes (0, 1, 2)

### Métriques rapportées

Exactitude équilibrée, macro-F1, AUROC one-vs-rest (macro), log-loss, Brier (multiclasse),
matrice de confusion, courbe de calibration.

**Événement d'échec** : `top-1 incorrect`. C'est la cible du modèle de readiness.

---

## 4. Les trois axes — métriques standards uniquement

Toutes sont calculées **sans aucun σ instrumental**, et aucune n'est appelée FO.

### 4.1 VISIBILITY — le défaut est-il séparé du régime sain ?

Référence saine = cycles du même split dont **le composant cible est à l'optimum** et dont les
**trois autres composants sont aux mêmes états** (appariement expérimental, couverture 100 %
établie en Phase 19).

| Nom | Définition | Référence |
|---|---|---|
| `vis_mahalanobis` | `(x − μ_sain)ᵀ Σ_sain⁻¹ (x − μ_sain)`, Σ estimée par Ledoit-Wolf sur TRAIN | Mahalanobis 1936 ; Hotelling 1931 |
| `vis_effect_size` | max sur canaux de `\|x_j − μ_j\| / s_j`, `s_j` = écart-type intra-référence | d de Cohen standardisé |
| `vis_wasserstein` | moyenne sur canaux de la distance de Wasserstein-1 entre la distribution intra-cycle et la distribution saine appariée | Kantorovich-Rubinstein |

### 4.2 ISOLABILITY — les défauts sont-ils séparés entre eux ?

**Indépendantes du classifieur**, calculées à partir des centroïdes de classe TRAIN :

| Nom | Définition |
|---|---|
| `iso_d_nearest` | distance de Mahalanobis au centroïde de la classe concurrente la plus proche |
| `iso_margin_ratio` | `iso_d_nearest / (d_own + 1)` |
| `iso_centroid_min` | distance minimale entre le centroïde de la vraie classe et les autres centroïdes |

**Aval, rapportées séparément et jamais mélangées aux readiness** : `rf_margin` (écart
top1 − top2) et `rf_entropy`.

### 4.3 ROBUSTNESS — le diagnostic tient-il si l'instrumentation se dégrade ?

Calculées **sur les données observées**, sans connaître la perturbation appliquée :

| Nom | Définition |
|---|---|
| `rob_loco_min` | minimum sur les canaux disponibles du rapport `iso_d_nearest` sans ce canal / `iso_d_nearest` avec tous — pire perte relative en laissant un canal de côté |
| `rob_effective_rank` | rang effectif `exp(H(λ))` du spectre de la covariance blanchie des canaux |
| `rob_redundancy` | R² moyen de la prédiction de chaque canal par les autres |

---

## 5. Perturbations pré-enregistrées

**Le bruit artificiel introduit ici est un stresseur de robustesse du diagnostic standard.
Il n'est en aucun cas un σ FO et ne sera jamais présenté comme tel.**

L'échelle du bruit est exprimée en multiples de l'écart-type intra-configuration mesuré en
Phase 19 (`STRESS_SCALE`), une grandeur descriptive du banc.

| Famille | Conditions | Nombre |
|---|---|---|
| Référence | aucune perturbation | 1 |
| Suppression d'un capteur | chacun des 17 | 17 |
| Suppression d'un groupe | pressions PS1-6, températures TS1-4, débits FS1-2, autres (EPS1, VS1, SE, CE, CP) | 4 |
| Bruit additif | `STRESS_SCALE` × 2, × 4, × 8 sur tous les canaux | 3 |
| Sous-échantillonnage | conserver 1 point sur 2, 5, 10 | 3 |
| Capteur biaisé | décalage constant de 2 × `STRESS_SCALE` sur PS1, PS3, TS1, FS1, EPS1 | 5 |
| Capteur dérivant | rampe linéaire de 0 à 4 × `STRESS_SCALE` sur PS1, PS3, TS1, FS1, EPS1 | 5 |
| **Total** | | **38** |

Pour chaque condition et chaque cible, les trois axes, le classifieur et les endpoints sont
recalculés. Graine de bruit : **20260817**, gelée.

---

## 6. Modèle de readiness

Régression logistique interprétable, ajustée **sur TRAIN + VALID uniquement**, prédisant
`échec du classifieur`. Elle ne reçoit jamais la classe vraie du test, ni les erreurs futures,
ni aucune information issue du TEST.

Toute statistique d'échelle entre en `signe(x)·log1p(|x|)`, comme aux phases précédentes.

| Modèle | Contenu |
|---|---|
| **R0** | nombre de capteurs disponibles seulement (contrôle) |
| **R1** | Visibilité |
| **R2** | Isolabilité |
| **R3** | Robustesse |
| **R4** | Visibilité + Isolabilité |
| **R5** | Visibilité + Robustesse |
| **R6** | Isolabilité + Robustesse |
| **R7** | Visibilité + Robustesse + Isolabilité |

### Question majeure

R7 apporte-t-il une amélioration **hors échantillon** par rapport à la meilleure composante
individuelle (max de R1, R2, R3) et par rapport à la meilleure paire (max de R4, R5, R6) ?

Endpoints : AUROC, AUPRC, Brier, log-loss, pente de calibration.
IC : bootstrap apparié à 2 000 tirages **au niveau configuration**.

### Seuil de pertinence pratique, repris de la Phase 16

```
YES    IC apparié exclut 0  ET  Δ AUROC ≥ 0,02
WEAK   IC exclut 0  MAIS  Δ AUROC < 0,02
NO     IC contient 0
```

---

## 7. Attribution de la cause d'échec

Seuils = **tertiles calculés sur TRAIN**, gelés avant tout résultat de test.

| Cause | Règle |
|---|---|
| **A. LOW_VISIBILITY** | visibilité dans le tertile bas, isolabilité et robustesse non |
| **B. LOW_ISOLABILITY** | isolabilité dans le tertile bas, visibilité et robustesse non |
| **C. LOW_ROBUSTNESS** | robustesse dans le tertile bas, visibilité et isolabilité non |
| **D. CLASSIFIER_LIMITED** | les trois axes hors tertile bas, et pourtant échec |
| **E. MIXED / UNKNOWN** | au moins deux axes dans le tertile bas |

### Test de validité de l'attribution

L'attribution est confrontée aux perturbations réellement appliquées, dont la cause attendue
est déclarée **ici, avant les résultats** :

| Perturbation appliquée | Cause attendue |
|---|---|
| Bruit additif ×2/×4/×8 | LOW_VISIBILITY et/ou LOW_ROBUSTNESS |
| Suppression du capteur le plus discriminant | LOW_ISOLABILITY |
| Suppression d'un groupe de capteurs | LOW_ROBUSTNESS et/ou LOW_ISOLABILITY |
| Sous-échantillonnage | LOW_VISIBILITY |
| Capteur biaisé ou dérivant | LOW_ROBUSTNESS |
| Aucune perturbation, échec malgré tout | CLASSIFIER_LIMITED |

Mesure : information mutuelle normalisée et exactitude d'appariement entre cause attribuée et
cause attendue, plus la matrice de contingence complète.

---

## 8. Test d'action

Pour chaque cas dégradé, une action corrective est simulée en **restaurant un capteur
supprimé** (ou en n'en restaurant aucun), puis le classifieur gelé est réévalué.

| Stratégie | Règle de choix |
|---|---|
| **ACTION_RANDOM** | capteur tiré uniformément parmi les supprimés, graine 20260817 |
| **ACTION_GENERIC** | capteur de plus fort pouvoir discriminant univarié **global**, classement établi sur TRAIN, identique pour tous les cas |
| **ACTION_READINESS_GUIDED** | selon la cause attribuée : LOW_VISIBILITY → canal de séparation sain/dégradé maximale pour ce cas ; LOW_ISOLABILITY → canal séparant le mieux les deux classes concurrentes de ce cas ; LOW_ROBUSTNESS → canal dont la perte dégrade le plus le système ; CLASSIFIER_LIMITED → **aucune restauration** |

**Endpoint principal** : amélioration réelle de l'exactitude équilibrée après action, sur le
TEST, avec IC bootstrap au niveau configuration.

Le contraste décisif est **ACTION_READINESS_GUIDED contre ACTION_GENERIC**. Battre
ACTION_RANDOM ne suffit pas : une stratégie générique fixe est la vraie baseline industrielle.

---

## 9. Verdicts à produire

```
VISIBILITY_PHYSICAL_VALUE:          YES / WEAK / NO
ISOLABILITY_PHYSICAL_VALUE:         YES / WEAK / NO
ROBUSTNESS_PHYSICAL_VALUE:          YES / WEAK / NO
READINESS_FAILURE_PREDICTION:       SUPPORTED / PARTIAL / NOT_SUPPORTED
FAILURE_CAUSE_ATTRIBUTION:          SUPPORTED / PARTIAL / NOT_SUPPORTED
READINESS_GUIDED_ACTION:            BETTER / EQUIVALENT / WORSE
PHYSICAL_ARCHITECTURE_VALIDATION:   PASS / PARTIAL / FAIL
PRODUCT_PROTOTYPE_JUSTIFIED:        YES / NOT_YET / NO
```

---

## 10. Règles d'arrêt, fixées à l'avance

1. Si **R7 ne bat pas** la meilleure composante individuelle **et** que
   `ACTION_READINESS_GUIDED` ne bat pas `ACTION_GENERIC` → **arrêt de la branche produit**.
2. Si la **prédiction** est bonne mais l'**attribution de cause** est mauvaise → ne conserver
   qu'un **score de risque**, jamais un moteur prescriptif.
3. Si l'attribution fonctionne **et** que les actions guidées améliorent réellement la
   performance → autoriser la construction d'un prototype Diagnostic Readiness Engine.

## 11. Interdits

- Modifier `src/fo_metrics.py`, ou calculer la moindre quantité FO / B\*.
- Présenter le bruit artificiel comme un σ FO.
- Ajuster un seuil, une caractéristique, un hyperparamètre ou un modèle après consultation du
  TEST.
- Utiliser refroidisseur ou accumulateur comme cible confirmatoire.
- Traiter les points temporels intra-cycle comme des répétitions indépendantes.
- Revendiquer une nouveauté mathématique.

## 12. Portée

Le banc ZeMA est un **banc d'essai physique de laboratoire**. Un résultat positif y constitue
une validation sur système physique réel et contrôlé — ce qui est strictement plus fort qu'un
simulateur, et strictement plus faible qu'un déploiement industriel. Aucune généralisation à
d'autres domaines ne sera tirée.

---

## AMENDEMENT 1 — 2026-08-17, avant tout résultat

**Objet : définition de `STRESS_SCALE`.**

Le §5 indiquait que l'échelle du stresseur de bruit serait « l'écart-type intra-configuration
mesuré en Phase 19 ». Vérification faite avant toute exécution, cette grandeur est une
dispersion **de moyennes de cycles**, et non une échelle du signal brut :

| Capteur | Écart-type Phase 19 (moyennes de cycles) | Écart-type intra-cycle du signal brut | Rapport |
|---|---|---|---|
| PS1 | 0,0159 | 14,73 | **925 ×** |
| FS1 | 0,0049 | 2,98 | 607 × |
| PS3 | 0,0057 | 0,887 | 154 × |
| EPS1 | 1,92 | 196,1 | 102 × |
| TS1 | 0,0288 | 0,193 | 6,7 × |
| VS1 | 0,0046 | 0,0323 | 7,0 × |

Injecté sur chaque échantillon brut, un bruit à cette échelle déplacerait la moyenne du cycle
de `échelle / √n`, soit **2·10⁻⁴ à 2·10⁻²** unités — numériquement inerte. Les conditions de
bruit ×2/×4/×8 auraient été indiscernables de la référence, et l'axe Robustesse n'aurait rien
mesuré.

**Correction retenue** : `STRESS_SCALE_j` = **médiane sur les cycles de l'écart-type
intra-cycle du capteur j sur le signal brut**. C'est l'échelle du niveau auquel la
perturbation est appliquée. Elle reste une grandeur purement descriptive du banc, et **n'est
en aucun cas un σ FO**.

Les conditions de biais (2 × `STRESS_SCALE`) et de dérive (rampe 0 → 4 × `STRESS_SCALE`)
utilisent la même définition corrigée.

Aucun résultat n'existait au moment de cet amendement : il est commité avant l'exécution, et
la chronologie est vérifiable dans l'historique git.

---

## AMENDEMENT 2 — 2026-08-17, avant tout résultat

**Objet : provenance de la référence saine pour l'axe Visibilité.**

Le §4.1 disait « cycles du **même split** ». Vérification faite avant exécution, cette
formulation pose deux problèmes.

**(i) Fuite au test.** Pour un cycle de TEST, prendre la référence saine dans le TEST revient
à supposer connu quels cycles du jour sont sains — précisément ce que le diagnostic cherche à
établir. C'est circulaire. **La référence saine est donc prise dans TRAIN uniquement**, ce qui
correspond aussi à la réalité d'un déploiement, où la ligne de base vient de la mise en
service.

**(ii) Couverture incomplète.** Le tirage du split, gelé, ne garantit pas qu'un contexte
(états des trois autres composants) présent au TEST ait un homologue sain dans TRAIN.
Couverture mesurée :

| Cible | TRAIN | VALID | TEST |
|---|---|---|---|
| vanne | 0,571 | 0,722 | 0,519 |
| pompe | 0,554 | 0,688 | 0,583 |

**Règle de repli, à deux niveaux, déclarée ici :**

1. référence = cycles sains de TRAIN au **contexte exactement identique** (états des trois
   autres composants) ;
2. à défaut, référence = **ensemble marginal** des cycles sains de TRAIN pour cette cible, tous
   contextes confondus.

Le **taux de recours au repli est rapporté** pour chaque split et chaque cible, et une analyse
de sensibilité compare les résultats sur le sous-ensemble à appariement exact contre
l'ensemble complet.

Aucun résultat n'existait au moment de cet amendement. Le split lui-même n'est pas modifié :
il reste celui gelé au §2, graine 20260817, et la répartition obtenue est exactement
7 / 2 / 3 configurations par cellule vanne × pompe, soit 849 / 240 / 360 cycles.
