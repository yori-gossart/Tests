# Phase 12A — Gate 0 d'éligibilité du prochain benchmark externe

```
LEAKDB_GATE0:      FAIL
GRAPHLEAK_GATE0:   FAIL
BENCHMARK_SELECTED: NONE
FO_TEST_AUTHORIZED: NO
```

Branche EPA gelée, non rouverte. Aucune expérimentation lancée. FO n'a été ni testé, ni
modifié ; aucun FO-v2. Aucun élément manquant n'a été remplacé par du synthétique.

---

## Résumé exécutable

LeakDB échoue pour **une seule cause, précise et réparable** : le dataset complet est sur
Zenodo, que le proxy réseau refuse. Ce qui reste accessible — 10 scénarios — franchit
brillamment 14 critères sur 18 mais rend impossible tout verdict statistique.

GraphLeak échoue pour une cause **différente et non réparable par déblocage réseau** :
le benchmark n'a pas de protocole d'évaluation figé. Les métriques annoncées dans sa
documentation ne sont implémentées nulle part dans le dépôt.

Aucun des deux ne permet d'aller jusqu'à un verdict FO aujourd'hui.

---

## LeakDB — Gate 0 détaillé

Dépôt `KIOS-Research/LeakDB` @ `131144ba`, cloné (160 Mo).

| # | Critère | Statut | Preuve |
|---|---|---|---|
| 1 | Accès dépôt source | **PASS** | `git ls-remote` OK, clone complet |
| 2 | Accès dataset complet | **FAIL** | `zenodo.org` → CONNECT 403 (curl **et** WebFetch) |
| 3 | Téléchargement effectif | **PARTIEL** | benchmark Hanoi embarqué (79 Mo → 529 Mo, 1078 fichiers) téléchargé ; les ~500 scénarios du dépôt Zenodo non |
| 4 | Intégrité et formats | **PASS** | zip listé et extrait sans erreur ; CSV `Timestamp,Value` cohérents ; 17 520 pas de 30 min sur 8 760 h |
| 5 | Vérité terrain par scénario | **PASS** | `Labels.csv` binaire par pas de temps + `Scenario-N_info.csv` |
| 6 | Localisation réelle de chaque fuite | **PASS** | `Leak_<nœud>_info.csv` : nœud, aire, diamètre, type (abrupt/incipient), début, fin, pic |
| 7 | Observations capteurs | **PASS** | 32 pressions + 32 demandes + 34 débits par scénario |
| 8 | Topologie réseau | **PASS** | un `.inp` EPANET **par scénario** (31 jonctions, 1 réservoir, 34 conduites) |
| 9 | Nombre de scénarios utilisables | **FAIL** | **10** (4 sans fuite, 6 avec fuite, **8 événements de fuite**) |
| 10 | Définition complète des métriques | **PASS** | `scoring_algorithm.m` : F1, MCC, STPR, STNR, SED — entièrement spécifié, seuil SED 0,75, fenêtre `tw_ex=10` inclus |
| 11 | Code officiel de scoring | **PASS** | `Scoring Function/scoring_algorithm.m` présent |
| 12 | Exécuter un exemple officiel | **PASS** | **exécuté**, code MATLAB non modifié sous GNU Octave 8.4.0 |
| 13 | Dépendances logicielles | **PASS** | Octave 8.4.0 installé depuis l'archive de distribution ; wntr 1.5.0 + EPANET ; pandas |
| 14 | Absence de dépendance bloquante | **PASS** | MATLAB n'est pas requis : Octave exécute le scoring tel quel |
| 15 | Calcul ultérieur de FO/B* sans inventer de données | **PASS** | vérifié numériquement, voir ci-dessous |
| 16 | Vrai test hors échantillon | **FAIL** | un partage 50/50 laisse 3 fuites en test |
| 17 | Comparaison à des diagnostics simples | **PASS** | trois baselines officielles fournies avec leurs sorties : MNF, RAND, NULL |
| 18 | Verdict statistique avec IC | **FAIL** | voir le calcul de puissance |

### Item 12 — exécution réelle du scoring officiel

`scoring_algorithm.m` exécuté sans modification sur les trois jeux de labels officiels :

```
MNF    F1 55.9188   STPR 38.8579   STNR 99.9777   SED 30.8309
RAND   F1 23.6526   STPR 50.2418   STNR 49.7742   SED  0
NULL   F1  0        STPR  0        STNR 100       SED  0
```

L'ordre attendu est retrouvé (MNF > RAND > NULL en F1, NULL dégénéré). Je n'ai **pas**
cherché à égaler la Table 1 du papier : celle-ci porte sur un ensemble plus large (le
papier parle de ~500 scénarios) alors que le dépôt en embarque 10. Ce sont deux
populations différentes, et prétendre les comparer serait une reproduction fictive.

### Item 15 — FO/B* est calculable sans inventer quoi que ce soit

C'est le point le plus favorable du dossier, et il a été vérifié plutôt que supposé.

`fo_metrics.py` exige un tenseur `delta[scénario, capteur, temps]` — l'écart de pression
causé par l'événement — plus un σ par capteur. Il faut donc un contrefactuel sans fuite,
apparié au scénario.

Test : le débit de fuite est stocké **séparément** (`Leak_19_demand.csv`) et n'est pas
inclus dans la demande nodale — vérifié, la demande moyenne pendant la fenêtre de fuite
(17,80) n'est pas supérieure à celle hors fenêtre (19,58). J'ai donc simulé le `.inp`
fourni sous EPANET/wntr et comparé au fichier de pression fourni, nœud 19, scénario 3 :

| | écart |
|---|---|
| hors fenêtre de fuite | moyenne **0,017 m**, max 0,175 m |
| pendant la fuite | moyenne **0,265 m** (chute systématique) |

Le `.inp` livré **est** le contrefactuel sans fuite. `delta` est donc directement
calculable à partir des seuls artefacts officiels, et le résidu hors fenêtre fournit un
plancher de bruit empirique pour σ. Aucune donnée inventée.

### Items 9, 16, 18 — la cause du rejet

L'unité indépendante est le **scénario**, pas le pas de temps : les 17 520 pas d'un
scénario partagent une réalisation de réseau, une série de demandes et une fuite. Ce ne
sont pas 17 520 observations indépendantes. L'échantillon réel est donc n = 10 scénarios
et 8 événements de fuite.

**Intervalles de confiance de Wilson à 95 %**

| n | k | p | IC 95 % | demi-largeur |
|---|---|---|---|---|
| 8 | 4 | 0,50 | [0,215 ; 0,785] | **0,285** |
| 10 | 5 | 0,50 | [0,237 ; 0,763] | **0,263** |
| 10 | 8 | 0,80 | [0,490 ; 0,943] | 0,227 |

**AUROC de FO comme prédicteur d'échec** (Hanley–McNeil) : avec 8 positifs et 2 négatifs,
une AUROC vraie de 0,90 donne un IC 95 % de **[0,686 ; 1,000]**. Une AUROC de 0,75 donne
**[0,393 ; 1,000]** — l'intervalle contient 0,5, donc ne distingue même pas FO du hasard.

**Granularité de B\*** : B\* est une proportion sur le support gelé E\*. Avec |E\*| ≤ 8, il ne
peut prendre que 9 valeurs, et **deux designs de capteurs ne peuvent pas différer de moins
de 12,5 points**. Comparer des designs est hors de portée.

**Taille requise** pour une demi-largeur de ±0,10 à p = 0,5 : **93 scénarios**. Pour
±0,05 : **381 scénarios**. Disponibles : 10.

**Test hors échantillon** : un partage 50/50 donne 3 fuites en apprentissage et 3 en test ;
sur 3 événements, l'IC à 95 % d'une proportion de 2/3 est [0,208 ; 0,939], largeur 0,731.

### Cause de rejet LeakDB — énoncé exact

> Le dataset complet (~500 scénarios/réseau) est publié sur `zenodo.org`, refusé par le
> proxy d'egress de l'environnement (CONNECT 403 sur `curl` comme sur WebFetch, sur
> l'API, sur la page d'enregistrement et via le DOI). Ce qui est embarqué dans le dépôt
> Git est une démonstration de 10 scénarios contenant 8 événements de fuite. Cet
> échantillon ne permet ni test hors échantillon réel (3 fuites en test), ni intervalle de
> confiance exploitable (demi-largeur ≥ 0,26), ni comparaison de designs de capteurs
> (granularité de B\* = 0,125). **Aucun autre critère n'est en cause.**

---

## GraphLeak — Gate 0 détaillé

Dépôt `gasiepgodoy/WDN-Models-and-Data-Sets` @ `d07cde23`, cloné (6,6 Go).

| # | Critère | Statut | Preuve |
|---|---|---|---|
| 1 | Accès dépôt source | **PASS** | `git ls-remote` OK, clone complet |
| 2 | Accès dataset complet | **PASS** | les données sont dans le dépôt, pas derrière un hébergeur externe |
| 3 | Téléchargement effectif | **PASS** | 420 fichiers CSV extraits pour le seul Case 1 (2,4 Go) |
| 4 | Intégrité et formats | **PASS** | extraction RAR5 intègre après installation d'`unrar` 7.00 |
| 5 | Vérité terrain par scénario | **PASS** | colonnes 50-54, label binaire par nœud de fuite |
| 6 | Localisation réelle de chaque fuite | **PASS** | colonnes 50-54 (nœud) + 55-57 (coordonnées x-y-z) |
| 7 | Observations capteurs | **PASS** | débit, pression, volume sur 8 nœuds monitorés |
| 8 | Topologie réseau | **PASS** | `.inp` EPANET + matrice d'adjacence (Case 1 : 44 jonctions ; Case 2 : 68) |
| 9 | Nombre de scénarios utilisables | **PASS** | 10 graines × 600 jours × 7 tailles de fuite × 6 pas d'échantillonnage |
| 10 | Définition complète des métriques | **FAIL** | voir ci-dessous |
| 11 | Code officiel de scoring | **FAIL** | aucune fonction de scoring autonome dans le dépôt |
| 12 | Exécuter un exemple officiel | **FAIL** | aucune valeur de référence atteignable |
| 13 | Dépendances logicielles | **PASS** | torch/numpy/pandas ; `unrar` non libre nécessaire mais installable |
| 14 | Absence de dépendance bloquante | **PARTIEL** | la régénération des données exige MATLAB + EPANET-Matlab Toolkit |
| 15 | Calcul de FO/B* sans inventer de données | **FAIL** | pas de contrefactuel apparié, voir ci-dessous |
| 16 | Vrai test hors échantillon | **PASS** | graines indépendantes disponibles |
| 17 | Comparaison à des diagnostics simples | **PARTIEL** | modèles GNN fournis, aucune baseline triviale de référence |
| 18 | Verdict statistique avec IC | **PASS** | ~6 000 jours-scénarios par configuration |

### Item 10 et 11 — le protocole d'évaluation n'existe pas

La documentation annonce « accuracy, precision, recall, F1-score » et « MAPE ». Recherche
exhaustive dans tout le dépôt :

```
f1_score | classification_report | confusion_matrix | precision_recall
→ 0 occurrence dans les fichiers .py
```

Ce qui existe réellement est une exactitude top-1 calculée en ligne dans la boucle
d'entraînement K-fold de `main-cena1-aum-600d.py`. Il n'y a **aucun** découpage
apprentissage/test figé, **aucune** règle d'agrégation entre graines, et **aucune**
définition de ce qu'est une localisation correcte (nœud exact ? plus proche voisin ?
distance ?). La documentation confond par ailleurs MAPE et erreur absolue moyenne.

C'est exactement le mode d'échec qui a coulé la branche EPA : une métrique publiée dont la
définition n'est pas récupérable. La différence est qu'ici c'est constatable **avant** de
commencer, ce qui est précisément l'objet de ce Gate 0.

### Item 12 — aucun ancrage vérifiable

Les deux papiers de référence sont sur `sba.org.br`, refusé par le proxy (CONNECT 403),
et les données brutes d'origine sont sur Google Drive, également refusé. Il n'existe donc
aucune valeur publiée atteignable contre laquelle vérifier qu'un pipeline est correctement
câblé. LeakDB fournit cet ancrage (j'ai exécuté son scoring officiel) ; GraphLeak non.

### Item 15 — pas de contrefactuel apparié

Le schéma de colonnes officiel — que j'ai vérifié empiriquement sur les CSV — livre débit,
pression, volume, coordonnées, labels, coordonnées de fuite, jour de semaine. Les profils
de demande journaliers sont tirés **au hasard à l'intérieur du générateur MATLAB** et ne
sont pas exportés. Un jour avec fuite n'a donc pas de jumeau sans fuite dans les données
publiées, et en reconstruire un exigerait de relancer le générateur — c'est-à-dire une
régénération, pas le jeu publié. La règle de la mission l'interdit.

`delta` devrait alors être défini contre une référence non appariée (moyenne diurne des
jours sans fuite), ce qui change la définition de FO plutôt que de l'appliquer.

### Cause de rejet GraphLeak — énoncé exact

> GraphLeak dispose des données, de la vérité terrain de localisation et de l'échelle
> nécessaires, mais n'est pas un benchmark évaluable : aucune fonction de scoring
> officielle, aucune métrique publiée implémentée dans le dépôt, aucun protocole de
> partage figé, et aucune valeur de référence atteignable (papiers et données brutes
> derrière des domaines refusés par le proxy). De plus, l'absence de contrefactuel sans
> fuite apparié empêche de calculer `delta` pour FO/B* à partir des seules données
> publiées.

---

## Ce qui débloquerait la situation

Par ordre de coût croissant, et sans aucune réparation de code :

1. **Autoriser `zenodo.org` dans la politique réseau de l'environnement**, ou **déposer le
   ZIP LeakDB complet dans la session** — exactement comme le XLSX EPA l'a été en 11D.
   LeakDB passerait alors de FAIL à PASS : les 14 critères déjà franchis le resteraient, et
   les trois critères en échec (9, 16, 18) sont tous des conséquences directes du seul
   nombre de scénarios. Avec ~500 scénarios, la demi-largeur d'IC tombe sous 0,05.
2. Autoriser `sba.org.br` et `drive.google.com` ne suffirait **pas** à sauver GraphLeak :
   son absence de protocole de scoring figé est intrinsèque au dépôt, pas un problème
   d'accès.

Je ne rouvre aucune de ces deux branches sans instruction explicite, conformément à la
consigne de ne pas tenter de réparation pendant plusieurs phases.

---

## Verdict

```
LEAKDB_GATE0:      FAIL   (cause unique : dataset complet inaccessible -> n=10 scénarios,
                           8 fuites ; items 9, 16, 18 impossibles)
GRAPHLEAK_GATE0:   FAIL   (causes : items 10, 11, 12 et 15 -- pas de protocole
                           d'évaluation officiel, pas de contrefactuel apparié)
BENCHMARK_SELECTED: NONE
FO_TEST_AUTHORIZED: NO
```

Arrêt ici, comme demandé. FO reste `NOT_EVALUATED`.

---

## Fichiers produits

```
phase12_gate0/RAPPORT_PHASE12A_GATE0.md            ce rapport
phase12_gate0/evidence/accessibility_probe.json    sondes git + HTTP horodatées
phase12_gate0/evidence/inventory.json              inventaire mesuré des deux candidats
phase12_gate0/evidence/statistical_power_leakdb.json  IC de Wilson, AUROC, tailles requises
phase12_gate0/evidence/official_scoring_run.txt    sortie du scoring officiel sous Octave
phase12_gate0/evidence/lblben.csv                  labels de référence, 10 x 17520
phase12_gate0/evidence/lblalg_{MNF,RAND,NULL}.csv  labels des trois baselines officielles
src/phase12_gate0_probe.py                         sonde rejouable
```

Les deux dépôts candidats ne sont pas versionnés ici (160 Mo et 6,6 Go) ; leurs commits
exacts sont enregistrés dans `inventory.json` et le clone est reproductible.
