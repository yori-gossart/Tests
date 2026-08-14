# RAPPORT PHASE 11B — TEST DÉCISIF DE RECONSTRUCTIBILITÉ EXTERNE

## Verdict final

```
EPA_REPRODUCTION:        FAILED
FO_DIAGNOSTIC:           NOT_EVALUATED_REPRODUCTION_FAILED
FO_RECONSTRUCTIBILITY:   NOT_EVALUATED_REPRODUCTION_FAILED
FO_APPLICATION_BRANCH:   UNDECIDED
```

**La phase FO n'a pas été ouverte.** La règle de l'étape 4 s'applique : la reproduction
n'atteint pas le gate, donc aucun verdict FO externe n'est produit.
`FO_DIAGNOSTIC_EXTERNAL.csv`, `FO_RECONSTRUCTIBILITY_EXTERNAL.csv` et
`INCREMENTAL_INFORMATION_TEST.csv` sont livrés avec leur schéma et **zéro ligne**.

**La règle d'arrêt de l'étape 11 ne se déclenche pas.** Elle exige
`FO_DIAGNOSTIC_NOT_SUPPORTED` **et** `FO_RECONSTRUCTIBILITY_NOT_SUPPORTED`. Ici les deux
sont `NOT_EVALUATED` : rien n'a été testé, donc rien n'a été réfuté.
`APPLICATION_BRANCH_STOP_RECOMMENDED` n'est **pas** écrit. Aucun FO-v2 n'a été créé.

---

## 1. Le ZIP officiel n'est jamais arrivé

Le brief énonce « Nous disposons maintenant du dataset officiel EPA ». Ce n'est pas le cas
dans cet environnement. Le répertoire d'upload contient trois fichiers `.md` (le prompt
Phase 10 et deux copies identiques du prompt Phase 11), inchangé depuis 09:08. Aucun ZIP,
aucun fichier `pg4z` / `SourceInversion` / `Haxton` nulle part sur le système.

Tous les hôtes EPA restent refusés : `curl: (56) CONNECT tunnel failed, response 403` sur
`pasteur.epa.gov`, `catalog.data.gov`, `sciencehub.epa.gov`, `edg.epa.gov`, et `doi.org`
pour le papier.

**Conformément à la consigne, j'ai épuisé les alternatives officielles avant de conclure.**

---

## 2. Ce qui a été récupéré, et comment il a été identifié

### Les trois réseaux — récupérés et identifiés positivement

Obtenus depuis le dépôt officiel **USEPA/Water-Security-Toolkit** @ `07f997cc`, pas depuis
le ZIP. L'identification n'est pas supposée : les effectifs de nœuds correspondent **au
nœud près** aux valeurs annoncées dans le brief.

| réseau | nœuds totaux | attendu par le brief | jonctions | conduites | pompes | vannes |
|---|---|---|---|---|---|---|
| Net3 | **97** | ~97 | 92 | 117 | 2 | 0 |
| Net6 = « Network2 » | **3 358** | ~3 358 | 3 323 | 3 829 | 61 | 2 |
| BWSN_Network_2 | **12 527** | ~12 527 | 12 523 | 14 822 | 4 | 5 |

**« Network2.inp » du ZIP EPA est EPANET Net6.** Le brief ne le dit pas ; la correspondance
exacte des effectifs l'établit.

### La définition de la spécificité — retrouvée, pas devinée

Le brief donne pour Probability Based, sur trois réseaux de taille connue, **à la fois** la
spécificité et le nombre de nœuds aussi ou plus vraisemblables que la vraie source. Cela
sur-détermine la formule :

| réseau | n nœuds | n aussi/plus vraisemblables | 1 − n/N prédit | publié | écart |
|---|---|---|---|---|---|
| Net3 | 97 | 30 | **69,07 %** | 69,07 | +0,00 |
| Net6 | 3 358 | 32 | **99,05 %** | 99,05 | −0,00 |
| BWSN2 | 12 527 | 45 | **99,64 %** | 99,64 | +0,00 |

```
spécificité = 1 − rang_vraie_source / n_nœuds_totaux
```

Trois points indépendants, écart nul à deux décimales. Ce paramètre passe d'`UNRESOLVED`
à **résolu**.

### Les paramètres d'algorithme — récupérés du WST officiel

Depuis `raw/inversion_config.yml` et `raw/inversion_ex1.yml`, non inventés :

| paramètre | valeur | rôle |
|---|---|---|
| `positive threshold` | 100,0 | seuil de mesure positive |
| `negative threshold` | 0,1 | seuil de mesure négative |
| `measurement failure` | 0,05 | probabilité qu'un capteur se trompe |
| `num injections` | 1 | nombre d'injections |
| `feasible nodes` | null | tous les nœuds sont candidats |

Ces configurations confirment aussi que les trois méthodes du papier sont exactement les
trois algorithmes WST : `bayesian` (= Probability Based), `csa` (= Contaminant Status
Algorithm), `optimization`.

---

## 3. Pourquoi WST n'a pas pu être exécuté

Le toolkit est récupéré et inventorié (28 composants de source-inversion) mais **inutilisable
tel quel** :

- `pywst` est en **Python 2** (instructions `print`), et ne fait que du marshalling de fichiers ;
- les trois algorithmes vivent dans du **C/C++ compilé** — `inversionsim`, `csarun`, moteur
  Merlion. Le code Python le dit explicitement : *« the profile file is actually printed by
  the c++ code for the probability algorithm »* ;
- la méthode `optimization` exige en plus un **solveur MIP** via Pyomo/AMPL.

La règle 3 du brief s'applique donc : repli sur WNTR/EPANET avec réimplémentation, et
documentation de toute divergence algorithmique.

**Divergence algorithmique principale** : le bayésien est réimplémenté comme un modèle de
Bernoulli sur lectures discrétisées — chaque couple (capteur, instant) s'accorde avec la
prédiction d'un candidat avec probabilité 1 − 0,05, prior uniforme. Le WST original utilise
le modèle de transport Merlion et une formulation dont le détail n'est pas lisible sans
compiler le C++. **Ce n'est pas la même implémentation**, et l'écart observé lui est en
partie imputable.

---

## 4. Reproduction Net3 Time Horizon — résultat

92 scénarios (une par jonction) × 6 horizons, 552 lignes dans
`event_level/EVENT_LEVEL_SOURCE_INVERSION.csv`.

### Spécificité reproduite contre publiée

| n capteurs | 1 h | 2 h | 4 h | 8 h | 16 h | 24 h | Spearman | RMSE |
|---|---|---|---|---|---|---|---|---|
| 5 | 5,15 | 5,15 | 40,74 | 46,34 | 81,23 | 81,24 | +0,924 | 31,95 |
| 10 | 5,15 | 5,15 | 81,13 | 83,84 | 84,28 | 86,74 | +0,924 | 23,28 |
| 20 | 5,15 | 5,15 | 91,65 | 92,31 | 93,56 | 94,72 | +0,924 | 24,19 |
| 40 | 5,15 | 5,15 | 95,53 | 95,75 | 95,93 | 95,97 | +0,924 | 24,98 |
| **publié** | **35** | **52** | **72** | **90** | **90** | **90** | — | — |

Avec injection démarrant à t = 0 au lieu de 2 h (les deux rapportées, aucune sélectionnée) :

| départ injection | 1 h | 2 h | 4 h | 8 h | 16 h | 24 h | Spearman | RMSE |
|---|---|---|---|---|---|---|---|---|
| 0 h | 53,64 | 79,59 | 85,09 | 85,12 | 85,51 | 87,18 | +0,941 | **14,90** |
| 2 h | 5,15 | 5,15 | 81,13 | 83,84 | 84,28 | 86,74 | +0,924 | 23,28 |

### Ce qui est reproduit, et ce qui ne l'est pas

**Reproduit** — la forme. La spécificité croît de façon monotone avec l'horizon puis
plafonne, exactement comme le papier. Spearman +0,92 à +0,94 contre la courbe publiée,
**stable à travers toutes les variantes testées**.

**Non reproduit** — les niveaux. RMSE de 14,9 points au mieux, contre un gate de ≤ 5. Aucune
combinaison testée ne s'en approche.

**Non testable** — l'accuracy. Sa définition n'a jamais été retrouvée, et le brief interdit
explicitement de l'assimiler au top-1. L'hypothèse testée (vraie source retenue dans
l'ensemble candidat) ne reproduit que le point à 8 h et échoue partout ailleurs.

### Diagnostic de l'écart

Le plancher à 5,15 % aux horizons courts est identifiable : 5,15 % = 1 − 92/97, c'est-à-dire
**tous les candidats à égalité**. À 1–2 h, aucun capteur n'a été atteint, donc le postérieur
est uniforme. Le papier annonce 35 % à 1 h, donc sa méthode discrimine déjà à cet horizon —
ce qui implique une différence dans le calendrier d'injection, le traitement des égalités, ou
la formulation de la vraisemblance.

Faire démarrer l'injection à t = 0 fait passer le RMSE de 23,3 à 14,9 sans franchir le gate.
**Je n'ai pas poursuivi le réglage.** Chercher les valeurs qui reproduisent la courbe publiée
serait de l'ajustement sur la cible, pas de la reproduction.

---

## 5. Verdict de reproduction : `FAILED`

Le gate TH exigeait RMSE ≤ 5 points sur accuracy **et** specificity. Obtenu : 14,9 au mieux
sur la spécificité, et l'accuracy n'est pas testable faute de définition.

J'ai retenu `FAILED` plutôt que `PARTIALLY_VALIDATED` malgré la concordance de tendance,
pour une raison de fond : **je n'ai jamais eu le papier, ni le XLSX, ni le plan expérimental,
ni la définition de l'accuracy.** Ce qui a été reproduit est une tendance qualitative au
moyen d'une réimplémentation de ma conception. Appeler cela « partiellement validé »
suggérerait qu'une partie de Seth et al. 2016 a été retrouvée. Ce n'est pas le cas.

Sept paramètres restent `UNRESOLVED` (voir `UNRESOLVED_PARAMETERS.csv`), dont trois à impact
élevé : la définition de l'accuracy, le plan de capteurs, et le traitement des égalités aux
horizons courts.

---

## 6. Conséquence sur FO

La reproduction n'étant pas suffisamment fidèle, **aucun test FO n'a été exécuté**. Ni le
score FO, ni B\*, ni les diagnostics concurrents, ni le test d'information incrémentale.

C'est la conséquence voulue par le protocole. Un test FO adossé à une reproduction dont le
RMSE est trois fois le gate n'aurait rien établi : un résultat favorable aurait été
inexploitable, un résultat défavorable aurait été imputable à ma réimplémentation plutôt
qu'à FO. **Dans les deux sens, cela n'aurait pas pu condamner ni sauver la branche
applicative.**

L'infrastructure est toutefois en place : le pipeline événementiel produit déjà rang,
reciprocal rank, top-1, top-5, taille d'ensemble candidat, postérieur de la vraie source,
NLL, entropie postérieure et marge top1–top2 par scénario et par horizon. Il ne manque que
la fidélité de reproduction pour que le test FO devienne interprétable.

---

## 7. Ce qu'il faudrait pour débloquer réellement

Par ordre d'importance :

1. **Le XLSX officiel** — seul artefact permettant de comparer autre chose que des valeurs
   transcrites à la main dans le brief, et seul moyen de retrouver la définition de
   l'accuracy.
2. **Le papier Seth et al. 2016** — plan expérimental, plan de capteurs, caractéristiques
   d'injection.
3. Le ZIP lui-même, pour confirmer que les réseaux récupérés du dépôt WST sont bien
   bit-identiques à ceux qu'il contient (les effectifs concordent, les empreintes ne sont pas
   vérifiables).

Sans 1 et 2, le gate de reproduction restera hors d'atteinte quelle que soit la qualité de
la réimplémentation.

---

## 8. Contrôles anti-biais appliqués

- Graines fixes (`SEED = 20260814`), toutes les variantes rapportées, **aucune sélectionnée**.
- Analyse de sensibilité pré-spécifiée sur les deux paramètres non résolus à plus fort
  impact (effectif de capteurs, départ d'injection) — grille complète publiée dans
  `results/`.
- Aucun paramètre ajusté pour améliorer un résultat, ni pour améliorer FO.
- Aucun résultat défavorable supprimé : les quatre effectifs de capteurs échouent le gate et
  les quatre sont rapportés.
- Aucun seuil choisi sur la cible.
- SHA256 de tous les fichiers, versions épinglées dans `requirements.lock`.
- FO-v1 et Phase 10 restent gelés et inchangés.

## 9. Limites

- Le bayésien est une **réimplémentation**, pas WST. L'écart mesuré lui est en partie
  imputable et cette part n'est pas séparable sans compiler Merlion.
- CSA et Optimization n'ont pas été implémentés : le gate a échoué sur la première méthode,
  et les implémenter aurait ajouté des divergences sans lever le blocage.
- Net6 et BWSN2 n'ont pas été traités : le brief demande de maîtriser Net3 d'abord.
- Les valeurs publiées utilisées comme cible sont **transcrites du brief**, pas lues dans le
  classeur officiel. Une erreur de transcription se propagerait silencieusement.
- L'observation est sans bruit ; seul le modèle de vraisemblance porte la probabilité
  d'échec capteur de 0,05.
