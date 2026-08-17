# Phase 20-DR — Diagnostic Readiness sur banc physique ZeMA

**Rapport de résultats. Confirmatoire.**
Protocole gelé **avant** tout résultat, SHA-256 `2384e463ba58829bae8d078da027e984ab77210f29aa803d253cf47c5c950ce8`.

| Étape | Commit | Contenu |
|---|---|---|
| Protocole gelé | `925fd37` | aucun résultat |
| Amendement 1 (échelle du stresseur) | `62e5a24` | aucun résultat |
| Amendement 2 (référence saine TRAIN) | `ac563f4` | aucun résultat |
| Code d'exécution et d'analyse gelé | `894d2d5` | aucun endpoint |
| **Résultats** | ce commit | endpoints, figures, verdicts |

`src/fo_metrics.py` est **inchangé** (dernière modification : `304dce1`, Phase B ;
SHA-256 `f17cd735816c958279f66f3d6b03e69fc95ef259dba716e13d331565de486c79`). Il n'est
importé nulle part dans cette phase, et **aucune quantité FO ou B\* n'a été calculée**.
Le bruit additif employé ici est un **stresseur de robustesse du diagnostic standard** ;
il n'est pas un σ FO et n'est présenté comme tel nulle part.

---

## 1. Les huit verdicts

```
VISIBILITY_PHYSICAL_VALUE:          NO
ISOLABILITY_PHYSICAL_VALUE:         YES
ROBUSTNESS_PHYSICAL_VALUE:          YES
READINESS_FAILURE_PREDICTION:       NOT_SUPPORTED
FAILURE_CAUSE_ATTRIBUTION:          NOT_SUPPORTED
READINESS_GUIDED_ACTION:            EQUIVALENT
PHYSICAL_ARCHITECTURE_VALIDATION:   FAIL
PRODUCT_PROTOTYPE_JUSTIFIED:        NO
```

**La règle d'arrêt n° 1 du §10 du protocole est déclenchée**, littéralement et sans
interprétation : R7 ne bat pas la meilleure composante individuelle (il fait **moins bien**),
et `ACTION_READINESS_GUIDED` ne bat pas `ACTION_GENERIC`. Le protocole prescrit dans ce cas
l'**arrêt de la branche produit**. Le prototype Diagnostic Readiness Engine n'est pas justifié
par ces données.

---

## 2. Périmètre effectivement exécuté

| Élément | Valeur |
|---|---|
| Cycles stables retenus | 1 449 |
| Configurations | 144, exactement 12 par cellule vanne × pompe |
| Split par configuration, graine 20260817 | **849 TRAIN / 240 VALID / 360 TEST** cycles (7 / 2 / 3 configurations par cellule) |
| Caractéristiques | 17 capteurs × 8 statistiques = **136**, aucune sélection |
| Classifieur | `RandomForestClassifier(n_estimators=500, random_state=20260817)`, entraîné sur TRAIN seul, refit à chaque condition |
| Conditions pré-enregistrées | **38** |
| Conditions « restore-one » du test d'action | 17 |
| Lignes d'événements produites | **159 390** (110 124 sur les 38 conditions confirmatoires) |
| Bootstrap | 2 000 tirages **au niveau configuration** |

Taux d'échec du classifieur : 0,092 sur TRAIN+VALID, **0,211 sur TEST** (5 769 échecs).

---

## 3. Axe par axe — l'échelle de readiness R0–R7

Modèles ajustés sur **TRAIN + VALID uniquement**, cibles poolées, TEST ouvert une seule
fois pour ces endpoints.

### 3.1 Endpoints sur TEST

| Modèle | Contenu | AUROC | AUPRC | Brier | log-loss | pente de calibration |
|---|---|---|---|---|---|---|
| R0 | n capteurs (contrôle) | 0,524 | 0,221 | 0,1914 | 0,663 | 0,41 |
| R1 | Visibilité | 0,558 | 0,300 | 0,1867 | 0,652 | 0,20 |
| **R2** | **Isolabilité** | **0,845** | 0,519 | 0,1614 | 0,510 | 0,90 |
| R3 | Robustesse | 0,641 | 0,378 | 0,1876 | 0,648 | 1,48 |
| R4 | Vis + Iso | 0,812 | 0,472 | 0,1631 | 0,526 | 0,76 |
| R5 | Vis + Rob | 0,588 | 0,390 | 0,1852 | 0,649 | 0,67 |
| **R6** | **Iso + Rob** | **0,851** | 0,535 | 0,1615 | 0,512 | 0,93 |
| R7 | les trois | 0,818 | 0,480 | 0,1634 | 0,525 | 0,78 |

### 3.2 Contrastes pré-enregistrés, IC 95 % bootstrap apparié au niveau configuration

| Contraste | Δ AUROC | IC 95 % | Verdict |
|---|---|---|---|
| R1 − R0 | +0,034 | [−0,090 ; +0,157] | **NO** |
| R2 − R0 | +0,322 | [+0,259 ; +0,376] | **YES** |
| R3 − R0 | +0,117 | [+0,055 ; +0,176] | **YES** |
| R7 − R0 | +0,294 | [+0,238 ; +0,347] | YES |
| **R7 − R2** (meilleure composante, choisie sur VALID) | **−0,027** | **[−0,058 ; +0,003]** | **NO** |
| R7 − R4 (meilleure paire, choisie sur VALID) | +0,007 | [−0,003 ; +0,017] | NO |
| R7 − R1 | +0,261 | [+0,130 ; +0,403] | YES |
| R7 − R3 | +0,177 | [+0,090 ; +0,255] | YES |

La meilleure composante individuelle et la meilleure paire ont été désignées **sur VALID**,
jamais sur TEST. Le choix sur VALID (R2, R4) coïncide avec le meilleur choix rétrospectif sur
TEST pour la composante (R2) ; pour la paire, VALID désignait R4 alors que TEST donne R6 —
cet écart est laissé tel quel, il n'a pas été corrigé après coup.

### 3.3 Lecture

- **Visibilité : sans valeur ici.** R1 − R0 a un IC qui contient 0. Pire, sur le sous-ensemble
  à appariement exact (§6), R1 tombe à **AUROC 0,356** avec une pente de calibration de
  **−0,70** : hors échantillon, l'axe Visibilité est *anti-prédictif*. Et l'ajouter dégrade :
  R5 (Vis+Rob, 0,588) fait moins bien que R3 seul (0,641), R7 (0,818) moins bien que R6 (0,851).
- **Isolabilité : c'est tout le signal.** R2 seule atteint 0,845 ; R6 = Iso + Rob atteint 0,851.
- **Robustesse : valeur réelle mais modeste**, +0,117 sur le contrôle, et elle n'apporte
  que +0,005 par-dessus l'Isolabilité.
- **L'architecture à trois axes est dominée par une seule de ses composantes.** C'est le
  résultat central, et il est défavorable à la thèse testée.

### 3.4 Par composant — le résultat n'est pas un artefact du pooling

Le pooling des deux cibles mélange des taux d'échec très différents (vanne 0,397, pompe 0,024
sur TEST) ; une part de l'AUROC poolée peut donc refléter la seule distinction
« ligne vanne / ligne pompe ». L'analyse par composant, modèles réajustés à l'intérieur de
chaque composant, écarte cette objection — et **confirme la conclusion** :

| Modèle | AUROC vanne | AUROC pompe |
|---|---|---|
| R0 | 0,490 | 0,733 |
| R1 | 0,550 | 0,897 |
| R2 | **0,661** | 0,966 |
| R3 | 0,633 | 0,955 |
| R6 | **0,669** | **0,976** |
| R7 | 0,577 | 0,975 |

Sur la vanne, R7 (0,577) est **très nettement en dessous** de R2 (0,661) et de R3 (0,633) :
l'ajout de la Visibilité détruit près de 0,09 d'AUROC. Sur la pompe, R7 ≈ R6, sans gain.

### 3.5 Par bloc de perturbation

AUROC des modèles poolés, restreinte aux lignes TEST de chaque famille
(`LADDER_PER_FAMILY.csv`) :

| Famille | n | taux d'échec | R0 | R1 | R2 | R3 | R6 | R7 |
|---|---|---|---|---|---|---|---|---|
| aucune perturbation | 720 | 0,175 | 0,500 | 0,458 | 0,842 | 0,588 | **0,846** | 0,803 |
| biais | 3 600 | 0,175 | 0,500 | 0,458 | 0,842 | 0,588 | **0,846** | 0,803 |
| dérive | 3 600 | 0,170 | 0,500 | 0,472 | 0,835 | 0,566 | **0,839** | 0,796 |
| suppression d'un capteur | 12 240 | 0,187 | 0,500 | 0,470 | 0,834 | 0,568 | **0,838** | 0,798 |
| suppression d'un groupe | 2 880 | 0,220 | 0,440 | 0,481 | 0,809 | 0,529 | **0,813** | 0,779 |
| sous-échantillonnage | 2 160 | 0,079 | 0,500 | 0,515 | 0,736 | 0,624 | **0,751** | 0,712 |
| bruit | 2 160 | 0,606 | 0,500 | 0,477 | 0,874 | 0,507 | **0,884** | **0,884** |

**R6 ≥ R7 dans les sept familles.** R2 seule bat R7 dans six familles sur sept ; la seule
exception est la famille « bruit », où R7 (0,884) dépasse R2 (0,874) et égale R6 (0,884).
R1 est **sous 0,5 dans cinq familles sur sept**. La ligne « biais » est numériquement
identique à la ligne « aucune perturbation » — première trace du défaut analysé au §7.

---

## 4. Attribution de la cause d'échec

Seuils = tertiles calculés **sur TRAIN**, gelés : visibilité −0,267, isolabilité −0,361,
robustesse −0,073 (scores d'axe standardisés, orientés « haut = meilleur »).

Sur les 5 769 échecs de TEST, 3 626 relèvent d'une condition dont la cause attendue avait été
**déclarée avant les résultats** (les 16 suppressions de capteur autres que le capteur le plus
discriminant n'ont pas d'attente déclarée et sont exclues du décompte).

| Mesure | Valeur |
|---|---|
| Exactitude stricte (cause attribuée ∈ cause attendue) | **0,260** |
| Exactitude indulgente (MIXED accepté pour une attente à deux causes) | 0,353 |
| **Niveau de hasard** (distribution marginale des causes attribuées) | **0,247** |
| Information mutuelle normalisée | **0,157** |

**0,260 contre un hasard de 0,247.** L'attribution n'apporte pratiquement rien.

### Par famille

| Famille | n | strict | indulgent |
|---|---|---|---|
| bruit | 1 310 | 0,357 | 0,379 |
| suppression de groupe | 635 | 0,312 | 0,798 |
| dérive | 611 | 0,160 | 0,160 |
| biais | 630 | 0,135 | 0,135 |
| sous-échantillonnage | 171 | 0,275 | 0,275 |
| suppression du capteur le plus discriminant (FS1) | 143 | 0,161 | 0,161 |
| aucune perturbation | 126 | 0,190 | 0,190 |

La matrice de contingence complète (`ATTRIBUTION_CONTINGENCY.csv`, figure 4) montre le mode
d'échec : pour les 1 310 échecs sous bruit, dont la cause attendue était
`LOW_VISIBILITY` ou `LOW_ROBUSTNESS`, l'architecture attribue **`CLASSIFIER_LIMITED` dans
57 % des cas** et `LOW_VISIBILITY` dans **0 %**. Autrement dit : sous le stresseur qui détruit
le plus le diagnostic, l'architecture conclut que les trois axes vont bien.

**Explication mécanique, formulée après coup et donnée comme telle** — elle n'a servi à
modifier ni le protocole ni un résultat. Le protocole exige (§4.3) que les axes soient
calculés « sur les données observées, sans connaître la perturbation appliquée ». La référence
saine est donc reconstruite **dans les mêmes conditions dégradées**. Un bruit additif uniforme
déplace le cycle et sa référence de la même façon et gonfle les deux dispersions : le score de
visibilité *relatif* ne baisse pas, alors même que l'information de classe a disparu. La
conception d'une visibilité en écart standardisé à une référence co-dégradée est aveugle à une
dégradation qui touche référence et mesure ensemble. C'est un défaut de l'architecture testée,
pas un incident d'exécution.

---

## 5. Test d'action

Huit cas dégradés (4 groupes de capteurs supprimés × 2 composants). Le contraste décisif
déclaré à l'avance est **guidé contre générique**.

| Cas | Cause attribuée | Aléatoire | Générique | Guidé |
|---|---|---|---|---|
| PRESSURE / vanne | LOW_ISOLABILITY | PS2 | PS5 | PS3 |
| PRESSURE / pompe | CLASSIFIER_LIMITED | PS2 | PS5 | — |
| TEMPERATURE / vanne | LOW_ISOLABILITY | TS3 | TS1 | TS1 |
| TEMPERATURE / pompe | CLASSIFIER_LIMITED | TS3 | TS1 | — |
| FLOW / vanne | LOW_ISOLABILITY | FS2 | FS1 | FS1 |
| FLOW / pompe | CLASSIFIER_LIMITED | FS2 | FS1 | — |
| OTHER / vanne | CLASSIFIER_LIMITED | CE | VS1 | — |
| OTHER / pompe | CLASSIFIER_LIMITED | CE | VS1 | — |

### Endpoints sur TEST, exactitude équilibrée moyennée sur les 8 cas

| Stratégie | Valeur |
|---|---|
| Dégradé, aucune action | 0,7795 |
| ACTION_GENERIC | 0,7830 |
| ACTION_READINESS_GUIDED | 0,7840 |
| ACTION_RANDOM (tirage gelé, une réalisation) | 0,8063 |

| Contraste | Δ | IC 95 % | Significatif |
|---|---|---|---|
| **guidé − générique** | **+0,0010** | **[−0,0033 ; +0,0055]** | **non** |
| guidé − dégradé | +0,0045 | [−0,0032 ; +0,0130] | non |
| générique − dégradé | +0,0035 | [−0,0046 ; +0,0127] | non |
| guidé − aléatoire | −0,0222 | [−0,0327 ; −0,0124] | oui, défavorable |

**READINESS_GUIDED_ACTION = EQUIVALENT.** Le guidage ne fait pas mieux que la stratégie
générique fixe, qui est la vraie baseline industrielle. Il ne fait pas non plus mieux que
l'absence d'action.

### Le contraste défavorable contre l'aléatoire, et ce qu'il vaut

Le tirage aléatoire gelé bat le guidage de manière significative. Ce résultat doit être
rapporté, mais aussi correctement pondéré : `ACTION_RANDOM` est **une seule réalisation** par
cas (le protocole ne prévoyait qu'un tirage, graine 20260817), et le bootstrap au niveau
configuration ne capture pas l'aléa du tirage de capteur. La totalité de l'écart vient d'un
seul cas : PRESSURE / vanne, où le tirage est tombé sur **PS2**, le seul capteur du groupe qui
aide vraiment (0,636 contre 0,411 dégradé), tandis que les cinq autres restent entre 0,400 et
0,497.

La grille complète des 17 restaurations possibles a été calculée (figure 6). Elle permet de
comparer au **niveau attendu** d'un tirage aléatoire plutôt qu'à une réalisation chanceuse.
Cette comparaison est **descriptive et post-hoc**, elle ne remplace pas l'endpoint
pré-enregistré :

| | Exactitude équilibrée, moyenne des 8 cas |
|---|---|
| Dégradé | 0,7795 |
| Générique | 0,7830 |
| Guidé | 0,7840 |
| **Espérance d'un tirage aléatoire** | **0,7894** |
| Meilleure restauration possible (oracle) | 0,8233 |

Le guidage reste **sous l'espérance de l'aléatoire** et loin de l'oracle. Le verdict
pré-enregistré (EQUIVALENT contre générique) n'en est pas adouci ; la lecture la plus honnête
est que le guidage n'a aucune valeur démontrable ici, dans aucune des deux comparaisons.

### Pourquoi le guidage n'a presque rien pu faire

Quatre cas sur huit ont été attribués `CLASSIFIER_LIMITED`, ce qui déclenche par protocole
**aucune restauration** : les trois cas pompe (dont le classifieur est déjà à 0,99 et n'échoue
jamais) et OTHER / vanne. Sur les trois cas où le guidage a agi, il a choisi le même capteur
que la stratégie générique dans deux cas (TS1, FS1) et un capteur strictement pire dans le
troisième (PS3 à 0,400 contre PS5 à 0,406, l'optimum PS2 étant à 0,636). Le guidage était donc
quasi indiscernable du générique **par construction du résultat**, pas par hasard.

---

## 6. Sensibilité à l'amendement 2 et écart de couverture constaté

L'amendement 2 imposait une référence saine issue de **TRAIN seul**, avec repli marginal.
Taux de recours au repli effectivement observés :

| Cible | TRAIN | VALID | TEST |
|---|---|---|---|
| vanne | 0,318 | 0,458 | **0,611** |
| pompe | 0,295 | 0,542 | **0,611** |

**Écart à signaler.** L'amendement annonçait une couverture TEST de 0,519 (vanne) et 0,583
(pompe), soit des taux de repli de 0,481 et 0,417. Les taux observés sont 0,611 dans les deux
cas. La cause est identifiée : le script gelé exige **au moins 3 cycles sains** dans le
contexte TRAIN pour former une référence de contexte, condition plus stricte que la simple
existence d'un homologue mesurée dans l'amendement. Cette exigence figurait dans le code gelé
au commit `894d2d5` mais n'avait pas été répercutée dans le texte de l'amendement. Elle est
signalée ici plutôt que corrigée après coup.

Analyse de sensibilité pré-déclarée, sur les 10 640 lignes TEST à appariement **exact** :

| Modèle | AUROC (toutes lignes) | AUROC (appariement exact) |
|---|---|---|
| R0 | 0,524 | 0,514 |
| R1 | 0,558 | **0,356** |
| R2 | 0,845 | 0,861 |
| R3 | 0,641 | 0,626 |
| R6 | 0,851 | 0,870 |
| R7 | 0,818 | 0,825 |

La conclusion est **inchangée et renforcée** : R7 < R6 et R7 < R2 dans les deux cas, et l'axe
Visibilité passe franchement sous le hasard quand on ne retient que les cycles dont la
référence saine est exactement appariée.

---

## 7. Ce que la grille de perturbations a réellement testé — défaut à déclarer

Le comportement du classifieur gelé sous les 38 conditions (figure 3,
`CLASSIFIER_DEGRADATION_TEST.csv`) révèle un **défaut de conception du protocole que je n'avais
pas anticipé au moment du gel**. Il est rapporté ici intégralement, comme le prévoit la règle
« rapporter tous les résultats, favorables comme défavorables ».

| Famille | Δ exactitude équilibrée vs référence, vanne | pompe | Effet réel |
|---|---|---|---|
| Biais (5 conditions) | **+0,0000 exactement** | **+0,0000 exactement** | **inerte** |
| Dérive (5 conditions) | +0,012 | −0,002 | quasi inerte |
| Sous-échantillonnage (3) | **+0,193** | −0,001 | **bénéfique**, pas dégradant |
| Suppression d'un capteur (17) | −0,022 | −0,001 | faible |
| Suppression d'un groupe (4) | −0,089 | −0,002 | modéré |
| Bruit (3) | **−0,604** | −0,259 | catastrophique |

**Le biais est inerte par construction.** Un décalage constant appliqué à tous les échantillons
de tous les cycles translate `mean`, `min`, `max`, `q25`, `median`, `q75` d'une même constante
et laisse `std` et `slope` inchangés. Comme la perturbation est appliquée à TRAIN **et** à TEST
et que le classifieur est réentraîné dessus, les seuils de coupure de la forêt se translatent
à l'identique : les prédictions sont rigoureusement les mêmes. On lit exactement 0,6528 et
0,9972 pour les cinq conditions de biais comme pour la référence, macro-F1 et AUROC compris.
La dérive, rampe identique pour chaque cycle, est une translation elle aussi ; les écarts
résiduels de ±0,006 s'expliquent par la précision `float32`.

**Le sous-échantillonnage améliore le diagnostic de la vanne** (0,653 → 0,908 à 1 point sur 10).
Il agit comme un lissage : cela indique que le classifieur de référence exploitait en partie du
bruit intra-cycle. C'est une information utile sur le banc, mais cela signifie que 3 conditions
de plus ne testaient pas ce qu'elles étaient censées tester.

**Bilan : sur 38 conditions pré-enregistrées, 10 sont inertes ou quasi inertes (biais, dérive),
3 agissent en sens inverse (sous-échantillonnage), 21 sont faibles à modérées, et 3 sont
catastrophiques.** L'espace de stress réellement exploré est donc bien plus étroit que ce que
le protocole laissait croire, et il est très déséquilibré. Cela ne change aucun verdict — les
verdicts sont défavorables — mais cela **limite la portée d'un éventuel résultat favorable
qu'on aurait pu en tirer**, et doit être corrigé dans toute reprise ultérieure.

Note complémentaire sur le bruit : chez la vanne, l'exactitude équilibrée tombe à 0,039–0,058
et l'AUROC à 0,29–0,30, **sous le hasard**. Une performance sous le hasard n'est pas du bruit
pur : elle indique que la forêt s'accroche, dans TRAIN, à des motifs de bruit corrélés aux
blocs de configuration, motifs qui s'inversent sur les configurations disjointes du TEST.
C'est une confirmation directe que le découpage par configuration est réellement contraignant.

---

## 8. Justification de chaque verdict

**VISIBILITY_PHYSICAL_VALUE : NO.** R1 − R0 = +0,034, IC [−0,090 ; +0,157], contient 0.
Sur appariement exact, AUROC 0,356 < 0,5. L'ajout de la Visibilité dégrade R3 → R5 et R6 → R7.

**ISOLABILITY_PHYSICAL_VALUE : YES.** R2 − R0 = +0,322, IC [+0,259 ; +0,376], au-delà du seuil
de 0,02. Confirmé par composant (vanne 0,661 vs 0,490 ; pompe 0,966 vs 0,733).

**ROBUSTNESS_PHYSICAL_VALUE : YES.** R3 − R0 = +0,117, IC [+0,055 ; +0,176]. Valeur réelle
mais largement redondante avec l'Isolabilité (R6 − R2 = +0,005).

**READINESS_FAILURE_PREDICTION : NOT_SUPPORTED.** La question majeure du §6 était : R7
apporte-t-il une amélioration hors échantillon par rapport à la meilleure composante
individuelle ? Réponse : **non, il fait moins bien** (−0,027, IC [−0,058 ; +0,003]). Le fait
que R7 batte largement le contrôle R0 (+0,294) ne répond pas à la question posée : c'est
l'Isolabilité seule qui produit ce gain.

**FAILURE_CAUSE_ATTRIBUTION : NOT_SUPPORTED.** 0,260 strict contre 0,247 de hasard, NMI 0,157.
Sur la famille la plus destructrice (bruit), la cause attendue `LOW_VISIBILITY` est attribuée
0 fois sur 1 310.

**READINESS_GUIDED_ACTION : EQUIVALENT.** Guidé − générique = +0,0010, IC [−0,0033 ; +0,0055].
Et sous l'espérance de l'aléatoire en analyse descriptive.

**PHYSICAL_ARCHITECTURE_VALIDATION : FAIL.** R7 ne bat pas la meilleure composante seule, et
les actions guidées ne battent pas la stratégie générique. Les deux clauses de la règle
d'arrêt n° 1 sont satisfaites simultanément.

**PRODUCT_PROTOTYPE_JUSTIFIED : NO.** Conséquence directe de la règle d'arrêt n° 1, appliquée
telle qu'elle a été écrite avant les résultats.

---

## 9. Ce qui survit

Un seul élément, et il est modeste :

> Sur ce banc, une mesure d'**isolabilité** — distance de Mahalanobis au centroïde de la classe
> concurrente la plus proche, marge relative, séparation minimale entre centroïdes — calculée
> **sans étiquette de test et sans connaître la perturbation appliquée**, prédit l'échec du
> diagnostic à AUROC 0,845 sur des configurations entièrement disjointes de l'entraînement,
> contre 0,524 pour le simple décompte de capteurs disponibles.

Cela justifie, tout au plus, un **score de risque** mono-axe. Cela ne justifie ni une
architecture à trois axes, ni un moteur prescriptif : la règle d'arrêt n° 2 du protocole
(« si la prédiction est bonne mais l'attribution de cause est mauvaise, ne conserver qu'un
score de risque, jamais un moteur prescriptif ») décrit exactement la situation observée, à
ceci près que la prédiction n'est bonne que pour une composante et non pour l'architecture.

Aucune nouveauté mathématique n'est revendiquée : la distance de Mahalanobis (1936), la
statistique T² de Hotelling (1931), l'estimateur de covariance de Ledoit-Wolf (2004), le rang
effectif spectral et la validation croisée par blocs sont tous standards.

---

## 10. Portée

Le banc ZeMA est un **banc d'essai physique de laboratoire**. Ce résultat est négatif sur un
système physique réel et contrôlé, ce qui est plus informatif qu'un résultat négatif sur
simulateur. Il ne se généralise **pas** à d'autres domaines, ni à un déploiement industriel, ni
à quoi que ce soit hors de ce banc et de ces deux composants (vanne, pompe). Le refroidisseur
et l'accumulateur ont été exclus dès le protocole faute de réplication indépendante et ne
figurent que comme variables de nuisance.

Cette phase ne dit **rien** sur FO ou B\*, qui n'y ont pas été calculés.

---

## 11. Artefacts

| Fichier | Contenu |
|---|---|
| `PROTOCOLE_PHASE20_DR.md` | protocole gelé + amendements 1 et 2 |
| `PROTOCOL_SHA256.txt` | `2384e463…c950ce8` |
| `SPLIT_ASSIGNMENT.csv` | split par configuration, 1 449 cycles |
| `STRESS_SCALE.json` | échelle du stresseur (amendement 1) |
| `READINESS_EVENTS.csv.gz` | 159 390 lignes : 3 axes, prédictions, échec, repli |
| `CLASSIFIER_METRICS.csv` | 5 métriques × 55 conditions × 2 cibles × 3 splits |
| `CONFUSION_MATRICES.csv` | matrices de confusion TEST, toutes conditions |
| `LADDER_TEST.csv`, `LADDER_VALID.csv` | endpoints R0–R7 |
| `LADDER_TEST_EXACT_MATCH_ONLY.csv` | sensibilité amendement 2 |
| `LADDER_CONTRASTS.csv` | contrastes + IC bootstrap |
| `LADDER_PER_TARGET.csv`, `LADDER_PER_FAMILY.csv` | analyses par composant et par bloc |
| `ATTRIBUTION_ROWS.csv.gz` | scores d'axe et cause attribuée par cycle |
| `ATTRIBUTION_CONTINGENCY.csv`, `ATTRIBUTION_BY_FAMILY.csv` | validité de l'attribution |
| `SENSOR_RANKING.csv` | classement univarié global sur TRAIN |
| `ACTION_CASES.csv`, `ACTION_PER_CASE.csv`, `ACTION_CONTRASTS.csv` | test d'action |
| `CLASSIFIER_DEGRADATION_TEST.csv` | dégradation par condition |
| `PHASE20_DR_RESULTS.json` | tous les endpoints et les 8 verdicts |
| `figures/fig1…fig6` | échelle, contrastes, dégradation, attribution, action, grille de restauration |
| `logs/run_main.log`, `logs/analyse.log` | journaux d'exécution complets |

Opérationnalisations que le protocole ne fixait pas explicitement (score d'axe, tertile bas,
sélection de la meilleure composante sur VALID, classement univarié des capteurs, règle
d'action pour MIXED, endpoint du test d'action) : écrites dans `OPERATIONALISATIONS` en tête de
`src/phase20_dr_analyse.py`, **commité au `894d2d5` avant tout endpoint**.

---

## 12. Recommandation

Appliquer la règle d'arrêt n° 1 : **arrêter la branche produit**. Si une reprise devait avoir
lieu un jour, elle devrait d'abord réparer trois choses établies ici :

1. **La grille de stress.** Biais et dérive doivent être appliqués à l'exploitation seule, pas
   au réentraînement, sinon ils sont analytiquement inertes.
2. **L'axe Visibilité.** Une visibilité mesurée en écart standardisé à une référence
   reconstruite dans les mêmes conditions dégradées ne peut pas détecter une dégradation qui
   touche la référence et la mesure ensemble. Telle que définie, elle est anti-prédictive.
3. **L'axe Robustesse.** Il est presque entièrement redondant avec l'Isolabilité (+0,005).

Aucune de ces réparations n'est entreprise ici : ce serait ajuster l'architecture après avoir
vu les résultats du test, ce que le protocole interdit.

---

# ERRATUM — ajouté à l'ouverture de la Phase 21-IR

**Objet : l'axe Isolabilité de la Phase 20-DR utilise l'étiquette vraie du TEST.
La conclusion du §9 « Ce qui survit » est retirée.**

Cet erratum est écrit avant toute exécution de la Phase 21-IR et n'a été motivé par aucun
résultat de la Phase 21. Il résulte d'une relecture du code gelé `src/phase20_dr_run.py`.

## Le défaut

```python
def isolability(X, y, cents, Sinv):
    ...
    own = np.array([ks.index(v) for v in y])          # <-- y = etiquette VRAIE
    d_own  = np.sqrt(d2[np.arange(len(y)), own])
    d_near = np.sqrt(np.where(mask, d2, np.inf).min(axis=1))
    cmin   = np.array([cd[own[i]].min() for i in range(len(y))])
    return {"iso_d_nearest": d_near,
            "iso_margin_ratio": d_near / (d_own + 1.0),
            "iso_centroid_min": cmin}
```

`y` est `prof[target].to_numpy()`, l'étiquette vraie de **tous** les cycles, TEST compris.
L'indice `own` en dérive, et les **trois** variables d'isolabilité en dépendent :
`iso_d_nearest` exclut la classe vraie, `iso_margin_ratio` divise par la distance à la classe
vraie, `iso_centroid_min` est une simple table de correspondance sur la classe vraie.

Vérification sur les données produites :

| Cible | classes vraies | valeurs distinctes de `iso_centroid_min` |
|---|---|---|
| vanne | 4 | **3** |
| pompe | 3 | **2** |

`iso_centroid_min` vaut 0,714–0,866 pour tout cycle de vanne et 1,414–1,561 pour tout cycle de
pompe. Poolées, les deux cibles ont des taux d'échec de 0,347 et 0,003. Un modèle logistique
sur ces variables peut donc atteindre une AUROC élevée **en lisant l'étiquette vraie pour
identifier le composant**, sans rien prédire.

## Ce qui est invalidé

- **La phrase du §3.3 « Isolabilité : c'est tout le signal » et le §9 « Ce qui survit » sont
  retirés.** L'AUROC de 0,845 de R2 n'est pas une prédiction d'échec sans étiquette.
- Toute affirmation du rapport selon laquelle l'isolabilité est « calculée sans étiquette de
  test » est **fausse** et doit être lue comme retirée. Elle apparaît au §3.3, au §9 et dans le
  message du commit `473b47d`.
- Les modèles R2, R4, R6 et R7 sont contaminés, ainsi que les contrastes qui les impliquent.

## Ce qui n'est pas affecté

- **Les huit verdicts sont inchangés**, et pour la plupart renforcés. Ils étaient déjà
  défavorables ; la contamination jouait *en faveur* de l'architecture. R7 perd contre R2 alors
  même que R2 triche : le constat d'échec est plus net, pas moins.
- L'axe **Visibilité** (`vis_mahalanobis`, `vis_effect_size`, `vis_wasserstein`) n'utilise pas
  l'étiquette : `mu` et `sd` viennent des cycles sains de TRAIN via le contexte expérimental.
  Son verdict `NO`, et sa performance sous le hasard en appariement exact, tiennent.
- L'axe **Robustesse** hérite du défaut par `iso_full` passé à `rob_loco_min` ;
  `rob_effective_rank` et `rob_redundancy` en sont exempts. Le verdict `YES` de
  ROBUSTNESS_PHYSICAL_VALUE doit donc être lu comme **partiellement contaminé**.
- Les §7 (grille de perturbations inerte), §5 (test d'action) et §6 (sensibilité) ne dépendent
  pas de l'isolabilité et tiennent intégralement.

## Conséquence pour la Phase 21-IR

La prémisse de la Phase 21-IR — « le score d'isolabilité prédit les erreurs sans étiquette de
test » — est **fausse pour l'implémentation gelée telle quelle**. La Phase 21-IR ne peut donc
pas la répliquer directement. Le traitement retenu, déclaré dans son protocole gelé, est de
tester deux variantes séparées : la variante gelée telle quelle, réservée à la référence et
incapable de fonder un verdict, et une variante où l'étiquette vraie est remplacée par
l'étiquette **prédite** — seule adaptation d'interface, sans changement mathématique.
