# TEP — Validation du terrain FO

```
TEP_ACCESS:                        PASS
TEP_FO_SEMANTICS:                  VALID
INDEPENDENT_REPLICATION_GENERATION: PASS
FO_TEST_AUTHORIZED:                YES
```

Protocole gelé dans `PROTOCOLE_PREENREGISTRE_TEP.json`. **Aucun résultat FO n'a été calculé.**
FO n'a pas été modifié : `src/fo_metrics.py` est inchangé, vérifiable par `git diff`.

C'est le premier candidat, après EPA, LeakDB, GraphLeak et Digits, qui fournit les quantités
de FO **sans qu'aucune ait à être inventée**.

---

## 1. Accès et intégrité — PASS

Dépôt `camaramm/tennessee-eastman-profBraatz` @ `06433188`, cloné (30 Mo).

| Élément | Vérification |
|---|---|
| 44 fichiers de données | d00–d21 × {train, test} : **tous présents** |
| `d00.dat` | 52 × 500 — **transposé**, particularité du dataset, prise en compte |
| `d01`–`d21.dat` | 480 × 52 chacun |
| `d00_te`–`d21_te.dat` | 960 × 52 chacun |
| Sources simulateur | `temain.f` (boucle ouverte), `temain_mod.f` (boucle fermée), `teprob.f` |

### 2. Les 52 variables

`teprob.f:211` déclare `COMMON/PV/XMEAS(41),XMV(12)`. Le dataset publié en retient **52 =
41 XMEAS + 11 XMV** : `XMV(12)` (vitesse d'agitation) est maintenu constant par le
régulateur et n'est pas enregistré. Le réassemblage des 15 fichiers de sortie dans cet ordre
reproduit exactement le format publié — vérifié ci-dessous.

---

## 3. Compilation et exécution du simulateur officiel — PASS

```
gfortran -std=legacy -O2 -o te_sim temain_mod.f teprob.f
→ code retour 0, aucun avertissement bloquant
```

Exécution : **1,55 s par run** de 48 h simulées, sortie 960 × 52.

Contrôle contre les données publiées, IDV=1 :

| | premières colonnes |
|---|---|
| simulé | 0,2499 · 3642,6 · 4539,6 · 9,278 |
| `d01_te.dat` publié | 0,2502 · 3657,2 · 4520,1 · 9,397 |
| rapport des moyennes (10 premières colonnes) | 0,9991 – 1,0020 |

Et pour le régime normal IDV=0 contre `d00_te.dat` : rapport des moyennes 0,9995 – 1,0032.

Le simulateur reproduit donc les statistiques publiées à mieux de 0,4 %.

Les seules éditions faites sont celles que le simulateur documente lui-même en tête de
`temain_mod.f` : NPTS (l.220), SSPTS (l.226), IDV (l.367), chemins de sortie (l.346-360, « To
change the file name and path, modify lines 346-360 accordingly »), et la graine `G`
(`teprob.f:1187`, dont les valeurs historiques `d00_tr`…`d21_tr` figurent en commentaires
juste en dessous). Physique, régulateurs et définitions de pannes : intacts.

---

## 4. Réalisations indépendantes — PASS

| Test | Résultat |
|---|---|
| Même graine, deux exécutions | **bit-identiques**, max\|diff\| = 0,000e+00 |
| Graines différentes, même panne | toutes différentes, max\|diff\| 172 à 223 |
| Coût | **1,55 s / run** |

Le déterminisme et l'indépendance sont donc tous deux vérifiés, par la procédure documentée
(modification de la seule graine).

---

## 5. Les six quantités requises — toutes natives

### Baseline et delta : contrefactuel **apparié**, pas approché

C'est le résultat le plus important de cette phase. À graine égale, IDV=0 et IDV=k sont
**bit-identiques avant l'instant de panne** et ne divergent qu'après :

| Panne | Segment pré-panne (0–159) | Post-panne (160–959) |
|---|---|---|
| IDV=1 | **identique bit à bit** | max\|diff\| = 215,3 |
| IDV=2 | identique | 195,2 |
| IDV=4 | identique | 5,831 |
| IDV=6 | identique | 411,9 |
| IDV=13 | identique | 253,1 |

`delta = fault − normal` est donc exactement « l'écart causé par l'événement » au sens de FO,
sans aucune approximation. C'est la même qualité de contrefactuel que LeakDB, et l'inverse
de GraphLeak (pas de jumeau) et de Digits (pas d'état sans événement).

### σ : **déclaré** par le procédé, ni estimé ni planché

`teprob.f:1256-1296` déclare `XNS(1..41)`, l'écart-type du bruit de mesure **par canal**,
appliqué additivement via `TESUB6` :

```fortran
CALL TESUB6(XNS(I),XMNS)
XMEAS(I)=XMEAS(I)+XMNS
```

**41 valeurs sur 41, aucune nulle**, la plus petite valant 0,0012. Aucun plancher n'est
nécessaire — c'est précisément ce qui manquait sur Digits, où trois canaux morts imposaient
un `1e-9` arbitraire.

Contrôle de cohérence : le bruit empirique lag-1 sur régime normal donne un rapport médian
de **1,03** à la valeur déclarée. Le protocole utilise la valeur **déclarée** ; l'estimation
empirique ne sert que de contrôle.

> Restriction assumée : σ n'est déclaré que pour les 41 XMEAS. Les 11 XMV sont des sorties de
> régulateur sans bruit de mesure déclaré. Les inclure exigerait d'inventer un σ, ce que le
> brief interdit — **les designs de capteurs sont donc restreints aux 41 XMEAS**.

### Le reste

| Quantité | Disponibilité |
|---|---|
| Identité vraie de la perturbation | IDV(k), k ∈ 1..21, imposée par construction |
| Plusieurs canaux de mesure | 41 XMEAS |
| Plusieurs réalisations indépendantes | graines gelées, coût 1,55 s |

---

## 6. FO et B\* calculables sans compromis — VALID

| Interdit | Statut |
|---|---|
| plancher arbitraire | **non requis** — 41 σ déclarés, aucun nul |
| baseline inventée | **non requise** — contrefactuel apparié bit-identique |
| σ inventé | **non requis** — `XNS` déclaré dans la source |
| formule modifiée | **non requise** — `visibility`, `freeze_support`, `b_dynamic`, `b_star` appelés tels quels sur un tenseur (n_scen, 41, 800) |

L'axe temporel existe réellement ici : 800 échantillons post-panne. Le `max_t` de FO opère
sur une vraie dimension temporelle, pas sur un singleton comme dans Digits.

### E\* est sélectif, sans dégénérescence

Sur un pilote 21 pannes × 3 graines (63 scénarios), `d_R` s'étale de 0,000 à 1453
(médiane 286,5) :

| κ | 1 | 3 | 10 | 30 | 100 | 300 | 1000 |
|---|---|---|---|---|---|---|---|
| \|E\*\| / 63 | 0,952 | 0,952 | 0,905 | **0,794** | 0,667 | 0,492 | 0,159 |

Aucune dégénérescence à l'une ou l'autre extrémité. κ = 30 est gelé sur ce pilote, avant
qu'aucun résultat de diagnostic n'existe.

À noter : `d_R` vaut exactement 0 pour certaines réalisations — des pannes sans **aucun**
effet observable sur les 41 canaux. C'est exactement le régime de perte d'information que FO
prétend diagnostiquer, et il est présent nativement.

---

## 7. B\* exerce réellement sa différence — PASS

C'est le point sur lequel Digits avait échoué. Ici, l'axe de bruit est **physique** : `XNS`
est mis à l'échelle et les données sont **régénérées** à ce niveau de bruit réel, `sigma_eval`
suivant la même échelle.

16 scénarios (4 pannes × 4 graines), design de 6 canaux, κ = η = 3 :

| échelle bruit | support B\* | support B_dynamic | B\* | B_dyn | diffèrent |
|---|---|---|---|---|---|
| ×1 | 16 | 16 | 0,0000 | 0,0000 | non |
| ×2 | 16 | 16 | 0,0000 | 0,0000 | non |
| ×4 | 16 | 16 | 0,0000 | 0,0000 | non |
| ×8 | **16** | **4** | 1,0000 | 1,0000 | **oui** |

Dénominateur de B\* invariant : **oui**. Dénominateur de B_dynamic mobile : **oui**. Le défaut
que B\* corrige se manifeste donc réellement sur ce benchmark, et B\* y est testable pour ce
qu'il est.

*(Ces chiffres sont des contrôles structurels des préconditions de FO. Aucun score FO n'est
mis en relation avec un résultat de diagnostic dans cette phase.)*

---

## 8. Budget de réalisations

Mesuré à 1,55 s/run, chaque scénario coûtant deux runs (normal apparié + panne) :

| Plan | Runs | Durée |
|---|---|---|
| 21 pannes × 10 graines | 420 | 11 min |
| 21 pannes × 30 graines | 1 260 | 32 min |
| **21 pannes × 50 graines** | **2 100** | **54 min** |

Le protocole retient **50 graines par panne**, soit **1 050 réalisations indépendantes**.

---

## 9. L'unité d'indépendance

Le pas de temps **n'est pas** une expérience. Les 800 échantillons post-panne d'une
réalisation partagent une graine, une panne et une trajectoire. L'unité indépendante est la
réalisation `(panne, graine)`, et le protocole l'inscrit explicitement, y compris dans la
règle de découpage : **découpage par graine**, jamais par scénario, pour qu'une même
réalisation de bruit ne se retrouve pas des deux côtés.

Puissance obtenue, 1 050 réalisations réparties 525 / 210 / 315 :

| | demi-largeur IC 95 % à p = 0,5 |
|---|---|
| TRAIN (n=525) | 0,043 |
| VAL (n=210) | 0,067 |
| **TEST (n=315)** | **0,055** |

AUROC sur TEST, largeur d'IC 95 % : 0,098 à 0,172 selon l'équilibre échecs/succès. La borne
inférieure dépasse 0,5 dès une AUROC vraie de 0,70. C'est sans commune mesure avec les 10
scénarios de LeakDB (demi-largeur 0,263).

---

## 10. Protocole pré-enregistré

Gelé dans **`phase14_tep/PROTOCOLE_PREENREGISTRE_TEP.json`**. En résumé :

- **21 perturbations**, y compris les quasi-indétectables 3, 9 et 15 — les retirer
  supprimerait exactement le régime que FO prétend diagnostiquer ;
- **50 graines** par perturbation, liste explicite gelée, 1 050 réalisations ;
- **découpage par graine** 25 / 10 / 15 → 525 / 210 / 315 scénarios ; le test n'est ouvert
  qu'une fois, à la fin ;
- **inféreur indépendant** : RandomForest à hyperparamètres gelés, entraîné sur TRAIN seul,
  qui ne voit jamais FO et que FO ne voit jamais ;
- **endpoints** : AUROC/AUPRC de `d_S(z)` pour l'échec top-1 avec IC, Spearman avec log-loss
  et rang, calibration de B\*, taux d'échec par décile ;
- **six baselines simples** que FO doit battre, dont l'entropie, la marge top1–top2, un SNR
  brut et un contrôle de pure taille de design ;
- **critères de succès** : la borne **inférieure** de l'IC de FO doit dépasser l'estimation
  ponctuelle de la meilleure baseline — pas seulement la battre en moyenne ;
- **règles d'arrêt** : inféreur inapte, E\* dégénéré, ou moins de 30 échecs/succès en test →
  arrêt ou INCONCLUSIVE, sans lecture favorable de repli. Aucune variante FO, aucun FO-v2,
  aucune modification de formule n'est permise à aucun moment.

---

## Verdict

```
TEP_ACCESS:                        PASS
TEP_FO_SEMANTICS:                  VALID
INDEPENDENT_REPLICATION_GENERATION: PASS
FO_TEST_AUTHORIZED:                YES
```

Arrêt avant le test, comme demandé. FO reste `NOT_EVALUATED`.

---

## Fichiers produits

```
phase14_tep/RAPPORT_TEP_VALIDATION_TERRAIN.md   ce rapport
phase14_tep/PROTOCOLE_PREENREGISTRE_TEP.json    protocole gelé
phase14_tep/evidence/tep_validation.json        mesures brutes
src/phase14_tep_harness.py                      harness de génération rejouable
```

Le clone TEP (30 Mo) n'est pas versionné ; son commit est enregistré et le clone est
reproductible. `src/fo_metrics.py` est inchangé.
