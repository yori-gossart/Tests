# RAPPORT PHASE 11C — REPRODUCTION EPA À PARTIR DES SOURCES « RETROUVÉES »

Reprise à partir du commit `06c0426`. **La tentative Phase 11B est conservée
intégralement** comme contrôle négatif de réimplémentation ; rien n'y a été supprimé ni
réinterprété.

## Verdict final

```
EPA_DATASET_RECOVERED:      NO
PAPER_PROTOCOL_RECOVERED:   PARTIAL
EPA_REPRODUCTION:           FAILED
  cause primaire:           FAILED_IMPLEMENTATION
  cause bloquante:          INSUFFICIENT_INFORMATION
FO_DIAGNOSTIC:              NOT_EVALUATED
FO_RECONSTRUCTIBILITY:      NOT_EVALUATED
FO_APPLICATION_BRANCH:      UNDECIDED
```

Aucun FO-v2 créé. Aucune définition FO modifiée. La phase FO n'a pas été ouverte.

---

## 1. Les quatre URL officielles sont inaccessibles depuis cet environnement

Les deux ressources annoncées comme « retrouvées » ont été testées immédiatement, ainsi que
les deux autres liens fournis. **Connaître l'URL ne donne pas l'accès** : la politique de
sortie réseau bloque les hôtes, pas les adresses.

| ressource | URL | résultat |
|---|---|---|
| Papier Seth et al. 2016 (OSTI) | `www.osti.gov/servlets/purl/1341749` | `curl: (56) CONNECT tunnel failed, response 403` |
| Dataset officiel EPA | `pasteur.epa.gov/uploads/149/…zip` | `CONNECT 403` |
| Catalogue Data.gov | `catalog.data.gov/dataset/…` | `CONNECT 403` |
| DOI | `doi.org/10.1061/(ASCE)WR.1943-5452.0000619` | `CONNECT 403` |

L'URL OSTI **n'avait jamais été testée** auparavant — c'était la piste la plus prometteuse
de cette mission. Elle est refusée comme les autres. Tentative également via l'autre voie
réseau disponible (`WebFetch`) : `{"error_type":"EGRESS_BLOCKED","domain":"www.osti.gov"}`.

État du proxy vérifié : `selective: false`, liste d'exemption limitée aux registres de
paquets et aux domaines Anthropic. Journal des refus :

```
www.osti.gov:443        -> gateway answered 403 to CONNECT (policy denial or upstream failure)
pasteur.epa.gov:443     -> gateway answered 403 to CONNECT
catalog.data.gov:443    -> gateway answered 403 to CONNECT
doi.org:443             -> gateway answered 403 to CONNECT
```

**Ce qu'il faudrait** : le contenu déposé dans la session (upload du ZIP et du PDF), ou une
modification de la liste d'autorisation du proxy. Fournir davantage d'URL ne débloquera rien.

### Étapes 1 à 3 de la mission : non exécutables

L'audit du ZIP, l'extraction du protocole depuis le papier avec numéros de page, et la table
de correspondance papier ↔ dataset supposent tous des fichiers que je n'ai pas. Aucune de ces
étapes n'a été simulée.

---

## 2. Mais la question de fond a pu être tranchée

La mission demande : *« déterminer si la reproduction échouait parce que la méthode était
incorrecte/incomplète, ou si même avec les matériaux officiels les résultats publiés restent
non reproductibles »*.

Cette question se teste **sans le papier**, par un balayage d'atteignabilité : la courbe
publiée est-elle dans l'ensemble des courbes que ma réimplémentation peut produire, sous une
paramétrisation quelconque des inconnues ?

**135 paramétrisations** balayées sur les quatre dimensions non résolues à fort impact —
départ d'injection {0, 1, 2 h} × durée {1, 2, 6 h} × concentration {100, 1 000, 10 000} ×
effectif de capteurs {5, 10, 20, 40, 92}.

| statistique | valeur |
|---|---|
| meilleur RMSE atteignable | **8,72 points** |
| gate | ≤ 5 |
| paramétrisations franchissant le gate | **0 / 135** |
| Spearman (tendance) du meilleur ajustement | **+0,94** |
| biais du meilleur ajustement | **−4,48** points |
| erreur maximale du meilleur ajustement | 17,61 points |

Meilleure courbe atteinte : `36,5 ; 58,3 ; 64,2 ; 72,4 ; 85,3 ; 85,4`
Courbe publiée : `35,0 ; 52,0 ; 72,0 ; 90,0 ; 90,0 ; 90,0`

### Lecture précise, et une nuance que je dois faire

**Chaque point publié est individuellement atteignable.** L'enveloppe du balayage va de 5,2 %
à 99,0 % à tous les horizons ; aucun point publié n'en sort. Il serait faux de dire que la
réimplémentation « ne peut pas produire ces valeurs ».

**Ce qui échoue est l'ajustement conjoint.** Aucune paramétrisation unique ne reproduit les
six points ensemble. Le meilleur compromis suit bien la forme générale (Spearman +0,94) mais
sous-estime systématiquement — biais négatif dans les six meilleures paramétrisations — et
rate surtout la montée rapide entre 4 h et 8 h (publié 72 → 90 ; obtenu 64 → 72).

C'est une **contrainte de forme**, pas de niveau. Ma réimplémentation ne peut pas être à la
fois aussi peu spécifique aux horizons courts et aussi spécifique à 8 h que la méthode
publiée.

### Conclusion diagnostique

L'écart n'est **pas** imputable au choix des paramètres d'injection ou du nombre de capteurs.
Il est structurel : le modèle de vraisemblance que j'ai écrit — Bernoulli sur lectures
discrétisées, prior uniforme — n'a pas la même réponse à l'horizon que la formulation WST /
Merlion.

D'où la classification demandée par la mission :

- **`FAILED_IMPLEMENTATION`** — cause primaire. La réimplémentation n'est pas l'algorithme WST
  et sa réponse à l'horizon diffère structurellement.
- **`INSUFFICIENT_INFORMATION`** — cause bloquante. Corriger l'implémentation exige soit le
  papier (formulation), soit la compilation du C++ WST (Merlion + `inversionsim`), et ni l'un
  ni l'autre n'est accessible.
- **`FAILED_DATA_MATCH`** — non applicable, aucune donnée officielle n'a pu être confrontée.
- **`FAILED_PUBLISHED_REPRODUCTION`** — **non établi.** Je ne peux pas affirmer que les
  résultats publiés sont irreproductibles ; j'ai seulement montré que *ma* réimplémentation
  ne les reproduit pas.

**Première divergence identifiée** : la pente entre 4 h et 8 h. C'est là que l'enveloppe se
décolle le plus de la courbe publiée, et c'est le premier point où aucun réglage ne rattrape.

---

## 3. Ce qui reste acquis de la Phase 11B

Conservé sans modification, et toujours valable :

- **Les trois réseaux** récupérés du dépôt officiel USEPA/Water-Security-Toolkit @ `07f997cc`,
  identifiés au nœud près : Net3 = 97, Net6 = 3 358, BWSN2 = 12 527. Le `Network2.inp` du ZIP
  est EPANET **Net6**.
- **La définition de la spécificité**, dérivée et vérifiée sur trois réseaux avec écart nul :
  `spécificité = 1 − rang_vraie_source / n_nœuds_totaux`.
- **Les paramètres d'algorithme** issus des configurations d'inversion officielles WST
  (seuils positif/négatif, probabilité d'échec capteur, nombre d'injections, nœuds faisables),
  qui confirment aussi que les trois méthodes du papier sont `bayesian` / `csa` /
  `optimization`.
- **552 lignes événementielles** Net3 (92 scénarios × 6 horizons) avec rang, reciprocal rank,
  top-1, top-5, taille d'ensemble candidat, postérieur, NLL, entropie et marge top1–top2.

`PAPER_PROTOCOL_RECOVERED: PARTIAL` reflète exactement cela : la spécificité et les
paramètres d'algorithme sont récupérés ; la définition de l'accuracy, le plan expérimental,
le plan de capteurs et la formulation exacte de la vraisemblance ne le sont pas.

---

## 4. Conséquence sur FO — inchangée

La reproduction ne franchit pas le gate, donc **FO n'a pas été testé**, conformément à la
règle de la mission. `FO_DIAGNOSTIC_EXTERNAL.csv`, `FO_RECONSTRUCTIBILITY_EXTERNAL.csv` et
`INCREMENTAL_INFORMATION_TEST.csv` restent livrés avec leur schéma et zéro ligne.

La Phase 11C **renforce** la justification de ce refus. En 11B on pouvait encore espérer que
l'écart tenait à des paramètres mal devinés. Le balayage montre que non : l'écart est
structurel. Un test FO adossé à cette réimplémentation mesurerait la réponse à l'horizon de
*mon* modèle de vraisemblance, pas celle de la méthode publiée — et donc ne dirait rien de FO
sur le benchmark EPA.

La règle d'arrêt de l'étape 11 de la Phase 11B **ne se déclenche toujours pas** : elle exige
les deux verdicts FO en `NOT_SUPPORTED`, ils sont `NOT_EVALUATED`.
`APPLICATION_BRANCH_STOP_RECOMMENDED` n'est pas écrit.

---

## 5. Comparaison avec la Phase 11B (contrôle négatif)

| | Phase 11B | Phase 11C |
|---|---|---|
| paramétrisations testées | 6 | **135** |
| meilleur RMSE | 14,90 | **8,72** |
| gate franchi | non | non |
| Spearman | +0,92 à +0,94 | +0,94 à +0,95 |
| conclusion | échec, cause indéterminée | échec, **cause identifiée comme structurelle** |

La Phase 11B n'est pas invalidée : son RMSE de 14,90 était le meilleur de son propre balayage,
plus étroit. Le balayage élargi améliore à 8,72 sans jamais franchir le gate, ce qui est
précisément l'information qui manquait.

---

## 6. Contrôles anti-biais

- Le balayage d'atteignabilité est un **diagnostic**, pas une calibration. Son résultat n'est
  utilisé pour aucune revendication de reproduction, et le meilleur ajustement n'est pas
  présenté comme « la » reproduction. Les 135 paramétrisations sont toutes conservées dans
  `results/attainability_sweep.csv`.
- Aucun paramètre n'a été figé sur la base de la courbe cible pour un usage ultérieur.
- Aucun résultat défavorable supprimé : les 135 échouent, les 135 sont publiées.
- Graine fixe `20260814`, versions épinglées.
- FO-v1, Phase 10 et Phase 11B restent gelées et inchangées.

## 7. Limites

- Le balayage couvre quatre dimensions. Il ne couvre **pas** la stratégie de placement des
  capteurs (tirage aléatoire graine fixe, pas le placement « optimal » du papier), le jeu de
  scénarios, le traitement des égalités, ni la forme de la vraisemblance. La conclusion
  « structurelle » est conditionnelle à ces dimensions non balayées.
- Les valeurs publiées servant de cible sont **transcrites du brief**, pas lues dans le
  classeur officiel. Une erreur de transcription se propagerait silencieusement.
- Seul le bayésien a été implémenté ; CSA et Optimization ne l'ont pas été, le gate ayant
  échoué sur la première méthode.
- Net6 et BWSN2 n'ont pas été traités.

## 8. Pour débloquer

Par ordre d'utilité décroissante :

1. **Déposer le PDF du papier dans la session** (upload). Il donne la formulation de la
   vraisemblance et la définition de l'accuracy — les deux pièces qui manquent réellement.
2. **Déposer le ZIP** (upload). Il permet la vérification d'intégrité, la table de
   correspondance, et confirmerait que les réseaux récupérés sont bit-identiques.
3. Autoriser `osti.gov`, `pasteur.epa.gov` et `doi.org` dans la politique de sortie.

Les options 1 et 2 sont sous ton contrôle direct et suffisent. L'option 3 relève d'un
administrateur.
