# Audit des métriques standards — formules, références, indépendance vis-à-vis de FO

Ce document est écrit **avant** l'analyse des résultats. Il fixe ce que chaque métrique
calcule, d'où elle vient, et pourquoi elle est légitime comme concurrente de FO.

`src/tep_metrics.py` n'importe pas `fo_metrics` et ne réutilise aucune de ses lignes. FO est
calculé séparément, par `fo_metrics.visibility`, non modifié.

---

## Notation commune

Pour une réalisation `z` (une paire panne × graine) et un design de capteurs `S` :

```
W[j,t] = delta[z,j,t] / σ_j        écart blanchi par le bruit de mesure déclaré
v[j]   = max_t |W[j,t]|            visibilité par canal, maximisée sur le temps
m[j]   = mean_t W[j,t]             écart blanchi moyen
```

`delta` est le contrefactuel apparié `panne − normal` à graine identique, et `σ = XNS(1..41)`
est l'écart-type du bruit de mesure **déclaré par le simulateur** (`teprob.f:1256-1296`).
Aucun σ n'est estimé, aucun plancher n'est introduit.

---

## Famille VISIBILITÉ / DÉTECTABILITÉ

| Nom | Formule | Référence |
|---|---|---|
| `max_abs` | `max_{j∈S} v[j]` | — |
| `mean_abs` | `mean_{j∈S,t} \|W\|` | rapport signal/bruit élémentaire |
| `rms` | `sqrt(mean_{j∈S,t} W²)` | énergie moyenne du signal blanchi |
| `l2_channels` | `‖v_S‖₂` | norme L2 du vecteur de visibilité |
| `mahalanobis` | `mᵀ_S (Σₙ[S,S])⁻¹ m_S` | Mahalanobis (1936) ; statistique T² de Hotelling (1931) |
| `kl_gauss` | `½[tr(Σₙ⁻¹Σ_f) + mᵀΣₙ⁻¹m − k + ln(det Σₙ/det Σ_f)]` | Kullback & Leibler (1951), forme close gaussienne |

### Trois remarques qui comptent pour l'interprétation

**1. `max_abs` EST `d_S` de FO.** Ce n'est pas une approximation ni un proxy : par
construction, `fo_metrics.visibility` calcule `|delta|.max(axis=temps)/σ`, et `d_S` en prend
le maximum sur les canaux du design. La colonne `max_abs` est donc incluse **pour que
l'identité apparaisse dans les tables**, plutôt que d'être affirmée en prose. Le contrôle
numérique est rapporté dans `PHASE15_TABLES.json → A_identity_check`.

**2. `rms` et la norme L2 sur `(j,t)` sont rang-équivalentes.** Elles ne diffèrent que du
facteur constant `sqrt(|S|·T)`, donc à design fixé elles produisent la même AUROC. Pour
éviter une colonne redondante, la norme L2 rapportée est celle **sur les canaux** du vecteur
`v`, qui n'est pas une transformation monotone de `rms`.

**3. KL sous covariance commune se réduit à Mahalanobis.** Si l'on impose `Σ_f = Σₙ`, alors
`KL = ½·D²_Mahalanobis`, donc une transformation monotone : AUROC identique, information
nulle en plus. Ce qui rend `kl_gauss` distinct ici est l'estimation d'un `Σ_f` **par
réalisation** : la divergence devient alors sensible à un changement de **structure de
covariance**, pas seulement de moyenne. C'est la raison d'être de son inclusion.

### Estimation des covariances

- `Σₙ` (covariance nulle) : estimée **une seule fois**, sur les 25 runs normaux de TRAIN,
  chacun centré sur sa propre moyenne, avec rétrécissement de **Ledoit-Wolf (2004)**. Cet
  estimateur est sans paramètre libre : aucune constante de ridge n'est choisie à la main.
- `Σ_f` (covariance par réalisation) : covariance d'échantillon classique sur la fenêtre
  post-panne centrée. Avec `T = 800` observations pour au plus `C = 41` canaux, l'estimation
  est bien conditionnée, et le même estimateur sert pour toutes les réalisations.

---

## Famille ISOLABILITÉ / CONFUSABILITÉ

Point méthodologique imposé par la mission : **les métriques utilisant le RandomForest sont
des diagnostics aval**, pas des métriques de readiness. Elles ne peuvent pas servir à décider
d'une instrumentation avant qu'un classifieur existe.

Les métriques ci-dessous sont calculées **uniquement à partir des signatures de panne et de
`Σₙ`**. Elles existent avant tout entraînement de classifieur.

| Nom | Formule | Lecture |
|---|---|---|
| `iso_d_nearest` | `min_{k'≠k} sqrt((m_S − c_{k'})ᵀ Σₙ⁻¹ (m_S − c_{k'}))` | distance à la panne concurrente la plus proche |
| `iso_d_mean_others` | moyenne de ces distances sur toutes les autres pannes | séparation moyenne |
| `iso_kl_nearest` | `½ · min_{k'≠k} D²` | KL gaussienne vers le concurrent le plus proche, sous `Σₙ` partagée |
| `iso_margin_ratio` | `iso_d_nearest / (iso_d_own + 1)` | séparabilité sans échelle |
| `iso_d_own` | distance au centroïde de sa propre panne | typicité |

`c_k` est le profil blanchi moyen de la panne `k`, calculé **sur TRAIN uniquement**.

> `iso_kl_nearest` est, sous covariance partagée, la moitié du carré de `iso_d_nearest`. Elle
> est rapportée pour complétude et **signalée comme redondante** : elle ne peut pas apporter
> d'information au-delà de `iso_d_nearest`. La signaler vaut mieux que de gonfler un ensemble
> de métriques avec une colonne qui n'en est pas une.

---

## Famille DIAGNOSTICS AVAL (rapportée séparément, jamais mélangée aux readiness)

| Nom | Origine |
|---|---|
| `rf_entropy` | entropie des postériors du RandomForest |
| `rf_margin` | écart top1 − top2 des postériors |

Ces deux quantités interrogent le classifieur sur lui-même. Elles ont un avantage structurel
sur toute métrique de readiness, puisqu'elles ont accès à l'observateur dont on prédit
l'échec. Elles servent de **plafond de référence**, pas de concurrentes légitimes pour une
décision d'instrumentation.

---

## Statistiques de queue sur support fixe (comparaison à B\*)

La question posée est : la valeur de B\* vient-elle de sa construction propre, ou du simple
fait d'appliquer **n'importe quelle** statistique de queue à un support fixe ? Toutes les
colonnes ci-dessous sont calculées sur **le même** support gelé `E*` et sur les **mêmes**
valeurs `d_S`.

| Nom | Formule |
|---|---|
| `b_star_equiv` | `P[d_S ≤ η \| E*]` — reproduit B\* à partir des mêmes entrées |
| `q05`, `q10` | quantiles 5 % et 10 % de `d_S` sur `E*` |
| `minimum` | `min d_S` sur `E*` |
| `mean` | `mean d_S` sur `E*` |
| `cvar05`, `cvar10` | moyenne des 5 % (resp. 10 %) plus basses valeurs — expected shortfall (Rockafellar & Uryasev, 2000) |

Si `q05` ou `cvar05` classent les designs aussi bien que `b_star_equiv`, alors la valeur
opérationnelle est celle du **support fixe**, pas celle du seuil `η` ni de la forme
particulière de B\*.

---

## Transformations d'entrée des modèles

Déclarées une fois, appliquées partout de façon identique : toute statistique d'échelle entre
en `signe(x)·log1p(|x|)`. La famille de visibilité couvre quatre ordres de grandeur (`d_S` va
de 0 à ≈ 1450) ; un terme logistique linéaire serait dominé par la queue haute. B\* est une
proportion et entre tel quel.

---

## Références

- Mahalanobis, P. C. (1936). *On the generalised distance in statistics.* Proc. Natl. Inst. Sci. India.
- Hotelling, H. (1931). *The generalization of Student's ratio.* Ann. Math. Statist.
- Kullback, S. & Leibler, R. A. (1951). *On information and sufficiency.* Ann. Math. Statist.
- Ledoit, O. & Wolf, M. (2004). *A well-conditioned estimator for large-dimensional covariance matrices.* J. Multivariate Anal.
- Rockafellar, R. T. & Uryasev, S. (2000). *Optimization of conditional value-at-risk.* J. Risk.
- Chiang, L. H., Russell, E. L. & Braatz, R. D. (2001). *Fault Detection and Diagnosis in Industrial Systems.* Springer — le cadre T²/Q dont TEP est le banc d'essai de référence.
