# Audit scientifique rétrospectif — programme FO / B\* / ISO

**Audit indépendant, rétrospectif et contradictoire de l'intégralité du programme
expérimental.** 65 commits, deux campagnes pré-Phase 10, et les phases 10 à 23.

Cet audit ne cherche pas à sauver le programme. Il ne cherche pas non plus à le condamner.
Il applique à chaque affirmation le même traitement qu'à une hypothèse.

---

## 1. Résumé exécutif

Le programme a testé, pendant douze phases, une famille de constructions propriétaires
(FO, B\*, Visibilité, Isolabilité, Robustesse, « architecture de readiness ») sur huit
domaines. **Aucune revendication positive ne survit.** Ce qui survit est un ensemble de
résultats négatifs pré-enregistrés, un défaut métrique correctement identifié et réparé, et
un catalogue empirique de modes de défaillance protocolaires.

Trois constats dominent l'audit.

**Premier constat — la cible a changé, et le changement n'a jamais été nommé comme tel.**
FO a été conçu et testé comme un **critère de placement de capteurs**. Il a perdu contre huit
baselines d'optimal experimental design. La Phase 10 a ensuite établi que le critère `B` est
**structurellement dégénéré** : dans le problème de placement non contraint il vaut
exactement 0,0000 pour tout budget k ≥ 4, donc il ne peut ordonner aucun design. À ce moment
précis — commit `7ee0ecb`, phase 10 — la question « FO est-il un bon critère de conception »
était close, négativement et définitivement. Le programme a alors basculé vers « `d_S`
prédit-il la difficulté de reconstruction », qui est une **question différente** portant sur
une quantité générique, et ce basculement a été traité comme une continuité.

**Deuxième constat — le résultat qui a motivé les quatre dernières phases était un
artefact.** La Phase 20-DR a conclu que l'axe Isolabilité était « tout le signal »
(AUROC 0,845). La Phase 21 a découvert, par relecture du code gelé, que ce score
**utilisait l'étiquette vraie du TEST**. L'erratum a été publié, les verdicts n'ont pas
changé (ils étaient déjà défavorables), mais **la Phase 21 elle-même n'existait que parce que
ce chiffre contaminé avait été pris pour un survivant**. Aucun test unitaire n'interdisait
l'usage de `y_true` avant la Phase 23.

**Troisième constat — la construction survivante est une méthode connue depuis 2018.**
`iso_margin_ratio = d(classe concurrente la plus proche) / d(classe prédite)` est, à la
métrique et à un `+1` près, la définition exacte du **Trust Score** de Jiang, Kim, Guan &
Gupta (NeurIPS 2018). Cette méthode n'a **jamais** été utilisée comme baseline dans aucune
phase. Le résultat final de la Phase 23 — « ce score bat les distances mais perd contre la
probabilité maximale » — reproduit un constat déjà publié dans la littérature de *failure
prediction*.

Verdict global : **valeur scientifique faible mais non nulle**, décision
**ARCHIVE_AND_PUBLISH_NEGATIVE_RESULTS**.

---

## 2. Sources auditées, et sources manquantes

### Disponibles et utilisées

Historique git complet (65 commits, horodatés) ; `README.md` ;
`FO_DOSSIER_FALSIFICATION.md` (493 l.) ; `FO_BATTLEDIM_EXTERNAL_VALIDATION_FINAL.md`
(641 l.) ; 25 rapports de phase ; 5 protocoles gelés avec SHA-256 ; les amendements ; les
JSON/CSV de résultats ; 58 scripts ; les tests unitaires ; les figures ; les logs
d'exécution ; `src/fo_metrics.py` (définition canonique, inchangée depuis `304dce1`).

### Manquantes — signalées, jamais reconstruites

| Source | Statut | Conséquence pour l'audit |
|---|---|---|
| **Définition de SIGMA** | **ABSENTE du dépôt.** Le terme n'apparaît que dans les énoncés de mission des Phases 19, 21, 22 | Le cadre englobant nommé « SIGMA » ne peut pas être audité. Aucun document ne le définit, ne le motive ni ne le relie à FO |
| **Dérivation théorique de FO** | **ABSENTE.** Les trois documents citant « Frontière d'Oubli » donnent la *formule*, jamais son origine, sa motivation théorique ni sa sémantique visée | L'audit ne peut juger que ce que le code calcule, pas ce que la théorie prétendait |
| `PROTOCOLE_AUDIT_FORENSIQUE_BATTLEDIM.md` | **ABSENT.** Signalé en Phase 10 §A.0 | Des exigences d'audit ont pu ne pas être couvertes |
| Deux rapports ChatGPT (`chatgpt.com/share/6a8054c4…`, `…6a805536…`) | **INATTEIGNABLES**, egress bloqué | Les analyses antérieures d'un autre modèle ne sont pas auditables |
| SCADA publié BattLeDIM (Zenodo 4017659) | **INATTEIGNABLE** (constat F1) | Toute la campagne FO-v1 tourne sur données **régénérées** |
| Données LeakDB complètes, EPA sources, 3W réel suffisant, UCI officiel, OpenML-CC18 | **INATTEIGNABLES** | Six gates d'accès échoués ou dégradés en miroir |

**Aucun de ces éléments n'a été reconstruit silencieusement.** C'est un point de crédit
méthodologique constant du programme.

---

## 3. Chronologie complète

### Ère 0 — FO-v1, critère de placement (commits 1 à 27)

**A. Question** — Le critère FO sélectionne-t-il de meilleurs réseaux de capteurs que les
méthodes d'optimal experimental design ?
**B. Hypothèse falsifiable** — Minimiser `B` améliore la détection de fuite.
**C. Origine** — Équation personnelle antérieure. *Sa dérivation n'est documentée nulle part.*
**D. Test** — BattLeDIM 2020 / L-Town, 782 jonctions, 33 capteurs préinstallés, 14 fuites en
2018 et 23 en 2019, k ∈ {4,6,8,10,12}, 10 baselines OED et topologiques, scoring officiel
porté du MATLAB, bootstrap apparié 10 000, protocole gelé avec **garde runtime** patchant
`builtins.open` et `numpy.load`.
**E. Résultat** — `NOT_SUPPORTED` sur les trois tracks.
**F. Décision** — Audit forensique (Phase 10).
**G. Évaluation rétrospective** — **Test bien conçu, exécution honnête, décision correcte.**
Trois réserves lourdes, toutes consignées à l'époque : (F1) données régénérées faute d'accès ;
(F2) `L-TOWN_v2_Real.inp` ne porte que 365 jours de patterns, donc 2019 **répète 2018
verbatim** — l'endpoint Track B a **exactement une valeur distincte** sur 1 000 designs
(σ = 2,8·10⁻¹⁷), *Track B ne pouvait donc rien falsifier* ; (F4) la vérité terrain 2019 était
visible pendant l'inventaire obligatoire, **avant que le gel existe**. Le gel a été posé
9 minutes avant le commit des résultats 2019.

### Phase 10 — Audit forensique et réparation métrique

**A/B** — Pourquoi FO a-t-il perdu : `B` est-il un mauvais substitut (a) ou l'endpoint
était-il saturé (b) ?
**D** — Corrélation de Spearman entre chaque critère de design et l'endpoint réalisé, sur
1 000 designs aléatoires par budget.
**E** — Décisif :

| critère | k=4 | k=8 | k=12 |
|---|---|---|---|
| D-optimal rank-reduced | −0,500 | **−0,652** | −0,637 |
| D-optimal bayésien | −0,569 | −0,545 | −0,528 |
| **B (critère FO)** | **−0,145** | **−0,107** | **−0,002** |
| **visibilité p05 (tie-break FO)** | **+0,130** | +0,036 | +0,065 |

L'explication est **(a)**. Et trois constats supplémentaires :
- le tie-break primaire de FO a le **signe inverse** pour la détection ;
- FO a atteint l'**optimum global de son propre critère** (écart glouton 0,0 sur 40 920
  sous-ensembles à k=4) et a quand même perdu — il n'a pas perdu par sous-optimisation ;
- **`B` sature à 0,0000 dès k=4** dans le problème non contraint à 782 candidats. *Un critère
  qui vaut zéro pour tout design raisonnable ne peut ordonner aucun design.*

Réparation : **B\***, à support gelé. Le défaut de `B` est démontré sur fixture synthétique —
à 8× de bruit, `B` annonce 26 % d'aveuglement là où B\* en mesure 74 %, parce que le bruit
éjecte les scénarios difficiles du dénominateur. Le rapport consigne que **la première version
du test échouait** parce qu'elle ne pouvait pas échouer.

**F/G** — Décision : porter FO ailleurs comme **prédicteur de difficulté**.
**Évaluation rétrospective : c'est la bifurcation la plus contestable du programme.** Elle
était disponible à l'époque : le §A.5 du rapport de Phase 10 établit lui-même que le critère
est dégénéré, et le §A.2 que tout le résultat Track A tient à **un seul événement sur 14**.
La lecture disponible à ce moment-là était « le critère est mort ». La lecture retenue a été
« la *famille* FO n'est pas sans signal ». Les deux sont défendables ; la seconde a été
choisie sans que la première soit explicitement écartée.

### Phases 11A–11D — Reproduction EPA

Quatre tentatives. R0 échoue (ZIP jamais reçu), 11B/11C échouent (URLs bloquées), 11D reçoit
le classeur officiel et **Gate R2 échoue quand même**, pour une raison structurelle établie :
la définition EPA d'« accuracy » est **indéterminée même avec le classeur officiel** (CSA à
20 % à 1 h contre 100 % à 24 h est impossible sous toute règle d'appartenance monotone). Les
cibles transcrites étaient exactes ; le cadre lui-même est sous-spécifié.
**Évaluation : décision d'arrêt correcte, et le diagnostic est de qualité.** FO n'a jamais été
testé. Coût : quatre sous-phases pour un gate d'accès.

### Phase 12A — LeakDB / GraphLeak

LeakDB : 14 critères sur 18 franchis, mais Zenodo bloqué → 10 scénarios sur 381.
GraphLeak : **aucun protocole d'évaluation figé**, métriques annoncées implémentées nulle
part. Deux `FAIL`, aucune expérimentation.
**Évaluation : correcte.** Le refus de remplacer les scénarios manquants par du synthétique
est un point de crédit.

### Phase 13A — Transposabilité sur digits

`FO_TRANSPOSABILITY: AMBIGUOUS`, test non autorisé.
**Évaluation : correcte, et peu coûteuse.** C'était le bon type de test — vérifier que la
sémantique de FO existe avant de la mesurer.

### Phase 14 — TEP, le seul terrain où FO était pleinement défini

**C. Origine de l'hypothèse** — TEP déclare son bruit de mesure (`XNS` dans le code Fortran).
C'est le **seul benchmark de tout le programme où σ est donné par le processus**, pas estimé.
**D/E** — 21 perturbations × 50 graines, split par graine, 120 designs, 63 000 lignes.

| Métrique | AUROC TEST | IC 95 % |
|---|---|---|
| Marge top1–top2 (RF) | **0,9231** | [0,9074 ; 0,9374] |
| Entropie (RF) | 0,9074 | [0,8858 ; 0,9283] |
| **FO `d_S`** | **0,8530** | [0,8121 ; 0,8898] |
| SNR moyen | 0,8481 | [0,8055 ; 0,8850] |

C2 et C3 échouent. `FO_SUPPORTED = false`. Mais le taux d'échec chute d'un facteur **13** le
long des déciles de `d_S` : **FO porte un signal réel**. Et FO ne bat le SNR moyen que de
**+0,005**.

**G. Évaluation rétrospective** — Test bien construit et bien interprété. Une nuance a été
correctement portée au dossier sans changer le verdict : marge et entropie interrogent le
classifieur, FO ne le voit jamais — avantage structurel. Le refus de requalifier les baselines
après coup est exemplaire.

### Phases 15–16 — Décomposition et confirmation aveugle

Phase 15 exploratoire, Phase 16 confirmatoire sur graines entièrement nouvelles, protocole
commité **avant** génération. Huit hypothèses, seuil ±0,02.

| ID | Comparaison | Δ AUROC | Verdict |
|---|---|---|---|
| H1 | FO seul contre l'échec | 0,8865 | YES |
| **H2** | **FO au-delà du SNR moyen** | **+0,0203** [0,0174 ; 0,0232] | **YES** |
| H7 | isolabilité au-delà de visibilité | +0,0195 | WEAK |
| H3 | FO au-delà de Mahalanobis + KL | +0,0122 | WEAK |
| **H8** | **apport propre au projet (M10 − M9)** | **+0,0012** [0,0008 ; 0,0016] | **WEAK** |
| H6 | B\* ajoute à FO | +0,0004 | WEAK |

**C'est le résultat le plus important de tout le programme, et il a été sous-exploité.**
H8 mesure exactement ce que le projet revendiquait : ce que FO + B\* ajoutent à un ensemble
de métriques standards. La réponse est **+0,0012 d'AUROC, dix-sept fois sous le seuil, et
négative sur 4 budgets de capteurs sur 6**. Le rapport le dit — « robustement négligeable »,
verdict `TECHNOLOGY_CANDIDATE: NOT_YET`, cas de décision D.

H2 mérite une lecture sévère : il franchit le seuil de **0,0003**, et seulement contre la
*moyenne* du SNR ; le rapport note lui-même que FO est interchangeable avec la norme L2
standard à 0,0003 d'AUROC près.

**G. Évaluation rétrospective — c'est ici qu'il fallait s'arrêter.** Avec les connaissances
disponibles au commit `14c5706`, la conclusion « aucune technologie propriétaire n'est
revendiquée » était déjà établie de façon confirmatoire, aveugle et répliquée. Les phases 17
à 23 n'ont jamais infirmé ce verdict ; elles l'ont confirmé sur d'autres domaines.

### Phases 17A et 19 — Gates de validation externe réelle

3W : `FO_3W_SEMANTICS: INVALID` — pas de contrefactuel, pas de σ.
ZeMA : `SIGMA_SOURCE = EFFECTIVE_VARIABILITY_ONLY`, sémantique physique `AMBIGUOUS`,
`PHASE20_AUTHORIZED: NO`.
**Évaluation : les deux décisions sont correctes**, et elles établissent un fait général
important (§5).

### Phase 20-DR — Le pivot, et l'artefact

Changement de cible explicite : « cette branche n'est plus une validation FO/B\* ».
Architecture Visibilité / Robustesse / Isolabilité sur le banc ZeMA.

Huit verdicts, **tous défavorables**. R7 (les trois axes) 0,818 < R2 (isolabilité seule)
0,845 < R6 0,851. Attribution de cause 0,260 contre 0,247 de hasard. Action guidée
équivalente à générique (+0,0010).

Défauts auto-signalés dans le rapport : biais **analytiquement inerte** (0,0000 exactement),
dérive quasi inerte, sous-échantillonnage **bénéfique** (+0,193) au lieu de dégradant —
**13 conditions sur 38 ne testaient rien ou testaient l'inverse**.

**Et le défaut non vu : l'isolabilité utilisait `y_true` du TEST.** `own = ks.index(v) for v
in y`. Les trois variables en dépendent ; `iso_centroid_min` ne prend que 3 valeurs distinctes
pour 4 classes — c'est une table de correspondance sur l'étiquette.

### Phase 21-IR — Réplication de l'isolabilité

Erratum publié en ouverture. `ISO_PRED` (étiquette prédite substituée) sur 3 jeux × 4 modèles.

- `GENERALIZATION: YES` — médiane 0,731, 12/12 au-dessus du hasard, tient sans RF. **Solide.**
- `INCREMENTAL_VALUE: YES` — **sur 1 cellule sur 12, et c'est Random Forest.** Médiane du delta
  contre la meilleure baseline : **−0,071**. ISO perd dans 11 cellules sur 12, significativement
  dans 5.

Le rapport signale lui-même le défaut de critère : le §9 n'avait pas quantifié le nombre de
cellules, et le code a implémenté « au moins une ».

### Phase 22-BR — Le régime

H22 : existe-t-il un régime, identifiable *avant* le TEST, où les scores probabilistes sont
faibles mais ISO ajoute de l'information ? `CONFIDENCE_WEAK` n'apparaît que dans **1 jeu sur
3**. Médiane +0,0063, IC stratifié contenant 0. Sous dérive temporelle, les deux cellules
faibles sont de **signes opposés**, toutes deux hautement significatives (+0,139 et −0,036).
`FALSIFIED`.

### Phase 23-RT — Triage prospectif

4 jeux entièrement nouveaux, AUGRC, bootstrap 10 000, Holm, 13 tests unitaires, simulation de
déploiement à seuil gelé.

- `ERROR_RISK_REPLICATED: NO` — 7 cellules sur 12 seulement ont un IC au-dessus du hasard.
- `OPERATIONAL_GAIN: NO` — **+0,004 contre +0,05 exigés**, et **−0,004** au seuil de
  déploiement gelé.
- Motif central : là où ISO a du signal il n'apporte rien ; là où il « apporte » quelque chose
  il n'a pas de signal.

`FALSIFIED`, `CLOSE_APPLICATIVE_ISO_BRANCH`.

---

## 4. Arbre des hypothèses

```
FO : minimiser B choisit de meilleurs capteurs
├─ TEST BattLeDIM, 10 baselines OED ................... FALSIFIÉ (NOT_SUPPORTED)
├─ AUDIT Phase 10 : pourquoi ?
│  ├─ B ne corrèle pas à l'endpoint (ρ −0,15 → 0) ..... FALSIFIÉ, cause identifiée
│  ├─ B sature à 0 en placement libre ................. FALSIFIÉ STRUCTURELLEMENT
│  ├─ tie-break p05, signe inverse en détection ....... FALSIFIÉ
│  └─ tie-break p05, signe favorable en LOCALISATION .. ⚠ JAMAIS RETESTÉ (§8)
├─ B a un défaut de dénominateur → B\* ................. RÉPARATION VALIDE (H6 : +0,0004)
│
└─ REFORMULATION 1 : d_S prédit la difficulté ......... question DIFFÉRENTE
   ├─ EPA ......................... gate d'accès/sémantique FAIL
   ├─ LeakDB / GraphLeak .......... gate FAIL
   ├─ digits ...................... AMBIGUOUS
   ├─ TEP ......................... FO 0,853 < marge 0,923 → FALSIFIÉ
   │  └─ mais signal réel (facteur 13 sur les déciles)
   ├─ 3W .......................... sémantique INVALID
   ├─ ZeMA ........................ σ non identifiable
   │
   └─ REFORMULATION 2 : décomposition Vis/Iso/Rob ..... question DIFFÉRENTE
      ├─ Phase 16 : apport propre +0,0012 ............. FALSIFIÉ (négligeable)
      │
      └─ REFORMULATION 3 : architecture de readiness .. CHANGEMENT DE SUJET ASSUMÉ
         ├─ Phase 20-DR : 8 verdicts négatifs ......... FALSIFIÉ
         │  └─ « survivant » R2 = 0,845 ............... ARTEFACT (fuite d'étiquette)
         │
         └─ REFORMULATION 4 : ISO prédit les erreurs .. question DIFFÉRENTE
            ├─ Phase 21 : généralise (0,731) mais perd
            │   contre les baselines dans 11/12 ....... PARTIELLEMENT FALSIFIÉ
            │   └─ « survivant » HAR/RF, 1 cellule/12 . SÉLECTION POST-HOC
            ├─ Phase 22 : régime introuvable .......... FALSIFIÉ
            └─ Phase 23 : triage prospectif ........... FALSIFIÉ
                                                        ↳ BRANCHE FERMÉE
```

**Réponse à la question centrale du §IV.** Le programme a progressé par **réduction
rationnelle à l'intérieur de chaque phase**, avec une rigueur qui s'améliore continûment. Mais
**entre les phases**, il a procédé quatre fois par reformulation de la cible après
falsification. Trois de ces quatre reformulations changent la question scientifique, pas
seulement le terrain. Le programme n'a donc pas testé une théorie de plus en plus finement :
il a testé **quatre thèses successives**, liées par une formule commune plutôt que par une
hypothèse commune.

---

## 5. Audit du « survivor chasing »

| Transition | Sous-résultat repris | Pré-enregistré ? | Effet | Testable indépendamment ? | **Cas** |
|---|---|---|---|---|---|
| FO-v1 → FO diagnostic | « la famille FO n'est pas sans signal » | non | ρ ≈ 0,3 sur un endpoint secondaire | oui | **B** (dérive) |
| TEP → décomposition 15/16 | « FO porte un vrai signal » (facteur 13) | non, mais Phase 16 **est** confirmatoire aveugle | fort et interprétable | oui, et il l'a été | **A** |
| Phase 16 → Phase 20-DR | « la décomposition readiness est SUPPORTED » | non | H8 = +0,0012 | oui | **B** |
| Phase 20-DR → Phase 21 | R2 = 0,845, « l'isolabilité est tout le signal » | non | **artefact de fuite** | oui | **B, aggravé** |
| Phase 21 → Phase 22 | HAR/RF +0,056 | non, explicitement DISCOVERY-ONLY ensuite | 1 cellule sur 12, RF seul | oui | **B** |
| Phase 22 → Phase 23 | aucun — question reposée à neuf | oui | — | oui | **A** |

**Quatre transitions sur six relèvent du cas B.** La plus grave est Phase 20-DR → Phase 21 :
le sous-résultat promu au rang d'hypothèse principale n'existait pas.

À la décharge du programme : deux mécanismes de correction ont effectivement fonctionné.
La Phase 22 a **déclaré HAR/RF `DISCOVERY-ONLY`** et interdit son usage confirmatoire, ce qui
est la bonne réponse au cas B. Et l'erratum de la Phase 21 a retiré publiquement le §9 de la
Phase 20-DR.

---

## 6. Audit conceptuel des constructions

### FO / `d_S`

1. `d_S(z) = max_{j∈S} max_t |δ[z,j,t]| / σ_j`
2. **Sémantique annoncée** : « frontière d'oubli », visibilité en unités de bruit
3. **Quantité réellement mesurée** : norme **L∞** du signal standardisé
4. Unité : écarts-types de bruit (sans dimension)
5–6. Observable ; identifiable **seulement si σ est fourni par le processus** — vrai sur TEP
   (`XNS`), faux sur 3W, ZeMA, LeakDB
7. **Aucune dépendance aux labels** — point réel et constant à son crédit
8. Dépend de TRAIN via σ et la référence
9. Invariances : homogène de degré 1 en δ ; invariant par permutation temporelle
10. **Ambiguïté majeure** : « oubli » suggère une perte d'information irréversible ; la
    quantité est un rapport signal/bruit maximal
11. Falsifiable : oui, et falsifié
12. **Relation à l'existant** : L∞ standardisé. Phase 16 le montre interchangeable avec L2 à
    **0,0003** d'AUROC
13. **Écart sémantique : élevé.** Un nom évoquant une frontière informationnelle recouvre une
    statistique de SNR

### `B` et `B*`

`B_{κ,η}(S) = P[d_S ≤ η | d_ref ≥ κ]`. **Défaut établi** : le dénominateur `E_κ` bouge avec σ,
donc deux valeurs de `B` sous bruits différents sont des fractions de dénominateurs différents,
et le biais **flatte la métrique**. B\* gèle `E*`. **C'est une réparation correcte et
généralisable** à toute métrique « fraction sous seuil » à dénominateur dépendant des données.
Valeur propre mesurée : **+0,0004** (H6). Écart sémantique : faible — B\* fait ce qu'il dit.
`B` est en outre **structurellement dégénéré** (sature à 0).

### Visibility (Phase 20-DR)

Écart standardisé à une référence saine **reconstruite dans les mêmes conditions dégradées**.
**Conséquence analytique** : aveugle à toute dégradation touchant référence et mesure ensemble.
Mesuré : AUROC 0,558 poolé, **0,356 sur appariement exact — sous le hasard**, pente de
calibration −0,70. **Construction invalide telle que définie.**

### Isolability / `ISO_PRED`

`iso_margin_ratio = d_near / (d_own + 1)`, distances de Mahalanobis aux centroïdes de classe.
**Écart sémantique : élevé, et le plus coûteux du programme.** Le nom suggère une propriété de
diagnosticabilité au sens du *fault isolation* ; la quantité est le **Trust Score** de Jiang
et al. (2018) — ratio distance à la classe concurrente la plus proche sur distance à la classe
prédite — avec une métrique de Mahalanobis au lieu d'un voisinage k-NN. Voir §7.

### Robustness

LOCO + rang effectif + redondance. **Contaminée** par `iso_full` (donc par l'étiquette) dans
`rob_loco_min`. Apport au-delà de l'isolabilité : **+0,005**. Largement redondante.

### « Architecture de readiness », « attribution de cause », « action guidée »

Trois noms à forte connotation prescriptive et causale recouvrant : une régression logistique
à 3 variables ; un découpage en tertiles ; et un choix de capteur à restaurer. Mesuré :
R7 < R2 ; attribution 0,260 contre 0,247 de hasard ; action guidée +0,0010 contre générique.
**Écart sémantique : très élevé.**

---

## 7. Audit des baselines et de la littérature

### Ce qui a été testé

OED (D/A/E-optimal, bayésien, info-gain, goal-oriented), dispersion topologique, centralité,
random ; SNR moyen, canaux > 3σ, plus petite valeur singulière ; Mahalanobis class-conditionnel,
KL gaussien, Wasserstein-1, CVaR, rang effectif ; max-probabilité, entropie, marge top1–top2 ;
kNN training-distance ; **conformal APS** (Phase 21) ; calibration Platt et isotonique
(Phase 22). **C'est un ensemble sérieux**, et il s'est enrichi à chaque phase.

### Ce qui manquait — et le manque est décisif

| Méthode | Pourquoi elle était le concurrent naturel | Conséquence de son absence |
|---|---|---|
| **Trust Score** (Jiang, Kim, Guan & Gupta, NeurIPS 2018) | **Définition quasi identique à `iso_margin_ratio`** | **Décisive.** La construction survivante du programme est une variante d'une méthode publiée en 2018 et jamais comparée |
| Mahalanobis OOD (Lee et al., NeurIPS 2018) | `iso_d_nearest` en est la forme class-conditionnelle | La nouveauté de l'axe Isolabilité n'a jamais été établie |
| Deep ensembles (Lakshminarayanan 2017), MC-dropout (Gal 2016) | Standards de l'estimation d'incertitude | Aucune conséquence sur les verdicts, tous négatifs |
| ConfidNet / learned confidence (Corbière 2019) | État de l'art de la *failure prediction* | Idem |
| Density / kNN-density OOD | Famille des scores géométriques | Partiellement couvert par B4 en Phase 21 |

**Verdict : `IMPORTANT_BASELINE_MISSING = YES`, `IMPORTANT_LITERATURE_MISSING = YES`.**

L'absence n'a **pas** conduit à surestimer une découverte — les verdicts finaux sont négatifs
et le resteraient. Mais elle a coûté du temps : comparer `iso_margin_ratio` au Trust Score dès
la Phase 20 aurait immédiatement reclassé la construction comme « variante connue », et la
question des Phases 21 à 23 serait devenue « notre variante Mahalanobis bat-elle le Trust
Score k-NN ? » — question étroite, à une seule expérience, au lieu de trois phases.

Second point : le constat final du programme (« ce score perd contre la probabilité
maximale ») **reproduit un résultat déjà établi** dans la littérature de *failure prediction*,
où MSP est une baseline notoirement difficile à battre.

---

## 8. Audit statistique

**Tailles d'effet.** Presque toutes les quantités « positives » du programme sont d'un ordre
de grandeur inférieur au seuil de pertinence que le programme s'était lui-même fixé :

| Résultat ayant motivé une suite | Valeur | Seuil déclaré | Rapport |
|---|---|---|---|
| H2, FO au-delà du SNR (Phase 16) | +0,0203 | 0,02 | **×1,015** |
| H8, apport propre du projet | +0,0012 | 0,02 | ×0,06 |
| HAR/RF (Phase 21) → Phase 22 | +0,056 | — | 1 cellule / 12 |
| Phase 22, médiane | +0,0063 | 0,02 | ×0,32 |
| Phase 23, gain opérationnel | +0,0041 | 0,05 | **×0,08** |

**Réponse à la question du §VIII** : *non*. Les résultats positifs qui ont motivé une phase
suivante avaient une **significativité statistique sans magnitude suffisante**. H2 franchit son
seuil de 0,0003. HAR/RF est une cellule sur douze. Aucun des deux ne justifiait, en
magnitude, la phase qu'il a déclenchée. **C'est l'échec statistique le plus conséquent du
programme.**

**Multiplicité entre phases : jamais contrôlée.** Chaque phase corrige en son sein (Holm en
21, 22, 23 ; IC appariés partout depuis la Phase 14). Mais le programme a exécuté ~12 phases
comportant chacune de 3 à 10 hypothèses, en réutilisant la même famille de constructions. Un
contrôle au niveau du programme aurait éliminé H2 et HAR/RF. **Aucune phase ne le mentionne.**

**Pooling.** Phase 20-DR poole vanne (échec 0,347) et pompe (0,003) ; une partie de l'AUROC
poolée mesure « quel composant est-ce ». Le rapport l'a détecté (§3.4) mais l'a attribué aux
axes en général plutôt qu'à `iso_centroid_min`, qui en est la cause exacte — c'est une table
de correspondance sur l'étiquette.

**Puissance et effectifs.** Trois cellules SECOM à 21 erreurs (Phase 21) ; seuil ≥ 20 erreurs
gelé en 21 et 23 ; Track A à 14 événements dont **un seul** porte tout le résultat FO ;
Track B à endpoint constant. Les IC sont larges et correctement rapportés partout.

**Réutilisation de TEST.** Aucune détectée après la Phase 14. Avant : F4 expose la vérité
terrain 2019 pendant l'inventaire, **avant l'existence du gel** — exposition réelle, consignée.

**Sélection d'hyperparamètres.** Sur CALIB seule depuis la Phase 22. Avant, ils étaient fixés
a priori. Correct dans les deux régimes.

**Régression vers la moyenne.** Non contrôlée explicitement, mais le motif est visible : les
plus gros effets apparaissent systématiquement dans les cellules les plus bruitées (GAMETES
en Phase 23, accuracy 0,47–0,65 ; GAS/SVM sous dérive en Phase 22). Le rapport de Phase 23
l'identifie correctement comme la meilleure explication du « gain » observé.

---

## 9. Audit exploration / confirmation

| Phase | Classe | Gel avant TEST | Commits séparés | Défaut |
|---|---|---|---|---|
| FO-v1 | CONFIRMATOIRE | oui, + garde runtime | oui | **F4** : vérité 2019 vue avant le gel |
| Phase 10 | **EXPLORATOIRE** (audit) | sans objet | oui | aucun |
| 11–13, 17A, 19 | gates d'accès, **NON CLASSABLE** | sans objet | oui | aucun |
| Phase 14 | CONFIRMATOIRE | oui (`cb307f9`) | oui | 2 conventions fixées après le gel, **déclarées** |
| Phase 15 | **EXPLORATOIRE**, étiqueté | sans objet | oui | aucun |
| Phase 16 | **CONFIRMATOIRE AVEUGLE** | oui, avant génération des graines | oui | défaut H4 **auto-signalé** dans le rapport |
| Phase 20-DR | CONFIRMATOIRE | oui, 2 amendements datés | oui | **fuite d'étiquette** |
| Phase 21 | CONFIRMATOIRE | oui | oui | critère `INCREMENTAL_VALUE` non quantifié, **auto-signalé** |
| Phase 22 | CONFIRMATOIRE | oui | oui | aucun |
| Phase 23 | CONFIRMATOIRE + **RÉPLICATION INDÉPENDANTE** | oui, 13 tests unitaires | 3 commits + amendement | déviation de pool **déclarée avant gel** |

**Double usage des données : une seule occurrence.** La Phase 16 réutilise le simulateur TEP
de la Phase 14, mais sur des **graines entièrement nouvelles**, avec protocole commité avant
génération — c'est une réplication interne légitime, pas un double usage. Le seul vrai double
usage évité de justesse est HAR/RF, neutralisé par la déclaration `DISCOVERY-ONLY`.

**La discipline confirmatoire est le point fort du programme**, et elle s'améliore de façon
monotone : gel → gel + hash → gel + hash + amendements datés → gel + hash + amendements +
tests unitaires + vérification verbatim + simulation de déploiement.

---

## 10. Audit des tests choisis

**Stress inertes ou inversés — Phase 20-DR.** Établi analytiquement et confirmé
numériquement : un biais constant appliqué à TRAIN **et** TEST translate les seuils de coupure
d'une forêt à l'identique. Les 5 conditions de biais donnent **exactement** 0,6528 et 0,9972,
macro-F1 et AUROC comprises. Dérive quasi inerte. Sous-échantillonnage **bénéfique** (+0,193).
**Bilan : 13 conditions sur 38 ne testaient rien ou testaient l'inverse.**

**Tests impossibles à réussir.** Track B de FO-v1 : endpoint à une seule valeur distincte.
Ce n'est pas un test difficile, c'est un test vide, et il a été compté comme un des trois
tracks.

**Métriques inadéquates.** Aucune détectée après la Phase 14 ; AUGRC (Phase 23) est le bon
choix, correctement implémenté et vérifié par tests unitaires.

**Sélection involontaire du pool.** Phase 23 : la règle anti-identifiant (retrait des colonnes
à ≥ 95 % de valeurs distinctes) a supprimé **les 100 colonnes continues** de
`Hill_Valley_with_noise`. Biais du pool vers les jeux discrets. Auto-signalé.
Autre : 3 des 4 jeux retenus sont binaires, donc max-probabilité, entropie et marge y sont des
transformations monotones l'une de l'autre — **la baseline « trois scores » est en pratique un
seul score sur 11 cellules sur 12**.

**Expériences apparemment négatives mais dont le protocole ne pouvait pas tester
l'hypothèse** — il y en a deux, et elles doivent être retirées du passif :
- **Track B de FO-v1** (endpoint dégénéré) ;
- **Les 13 conditions inertes de la Phase 20-DR**, qui ne pouvaient pas dégrader le diagnostic.

---

## 11. Audit des résultats négatifs — portée exacte de chaque falsification

| Résultat | Ce qu'il falsifie | Ce qu'il ne falsifie **pas** |
|---|---|---|
| FO-v1 `NOT_SUPPORTED` | FO comme règle de placement, **sur ce benchmark, dans le régime contraint à 33 capteurs** | FO comme mesure descriptive |
| `B` sature à 0 (§A.5) | **Le critère `B` lui-même**, dans tout problème de placement non contraint. Falsification **structurelle**, indépendante du benchmark | B\*, qui est une métrique d'évaluation et non de sélection |
| TEP `FO_SUPPORTED = false` | FO comme **meilleur** prédicteur d'échec | FO comme prédicteur d'échec **réel** (facteur 13 établi) |
| H8 = +0,0012 | **La revendication technologique propriétaire**, de façon confirmatoire et aveugle | Que les axes soient descriptivement utiles |
| Phase 20-DR, 8 verdicts | L'architecture à trois axes **sur ce banc** | Rien sur ISO — la partie isolabilité était contaminée |
| Visibilité, AUROC 0,356 | **La définition de la Visibilité**, pas seulement son implémentation | Une visibilité définie contre une référence non co-dégradée |
| Phase 22 `FALSIFIED` | L'existence d'un **régime identifiable a priori** où ISO aide | Que ISO ordonne les erreurs |
| Phase 23 `FALSIFIED` | **L'utilité opérationnelle et incrémentale** d'ISO, sur 4 jeux et 4 familles | Que ISO porte un signal sur certains jeux (établi : 2 sur 4) |

**Sur-falsification à éviter** : le programme n'a pas montré que la géométrie de classe est
inutile pour prédire les erreurs. Il a montré qu'**elle est redondante avec les probabilités
du classifieur**, ce qui est plus précis et plus utile.

**Sous-falsification à éviter** : après la Phase 16, conserver « une version plus petite de la
même idée » était exactement ce qui se passait. Trois phases y ont été consacrées.

---

## 12. Résultats éventuellement oubliés

Recherche systématique dans les 25 rapports et les JSON.

### 12.1 Le signal de localisation — la seule vraie candidate

**Phase 10, §A.1, étiqueté `[limite]`** : sur la distance de localisation — un endpoint
continu, distinct de la détection — le tie-break p05 de FO est **le seul critère de signe
favorable et constant** : ρ = −0,296 à k=4, −0,190 à k=6. Le rapport écrit : « la famille FO
n'est donc pas sans signal — elle en a pour la localisation, pas pour la détection ».

**Pourquoi il a été abandonné** : aucune justification n'est donnée dans aucun rapport. La
phase suivante (11) porte sur la reproduction EPA. **Aucune des douze phases suivantes n'a
testé la localisation** ; toutes ont testé la détection, la prédiction d'échec ou le triage.

**Cette décision était-elle correcte ?** *Non, pas telle qu'elle a été prise* — elle n'a pas
été prise, elle s'est produite par changement de sujet. Un signal identifié comme le seul
favorable de toute la famille méritait au minimum une phrase d'écartement motivée.

**Mérite-t-il une réouverture ?** Application stricte des cinq critères du §XII :

| Critère | Verdict |
|---|---|
| effet important | **NON** — ρ ≈ 0,3, décroissant avec k, sur un seul jeu et un seul endpoint |
| non expliqué par un artefact évident | oui |
| insuffisamment testé | **oui**, jamais retesté |
| scientifiquement distinct des branches falsifiées | **oui**, la localisation n'a jamais été testée |
| test décisif identifiable | oui — mais il porterait sur un critère dont la Phase 10 a établi qu'il **sature à zéro** dans le problème non contraint |

**Deux critères sur cinq échouent. Pas de réouverture.** L'effet n'est pas important, et il
appartient à une construction structurellement dégénérée. Le consigner suffit.

### 12.2 Autres candidats examinés et écartés

- **Facteur 13 sur les déciles de `d_S` (TEP)** — répliqué en Phase 16 (H1 = 0,8865), puis
  correctement expliqué : c'est un effet SNR, obtenu à +0,005 près par le SNR moyen. Rien
  d'oublié.
- **`B_STAR_ADDS_VALUE: YES` (Phase 14)** — repris et quantifié en Phase 16 : +0,0004. Clos.
- **`ISOLABILITY_PHYSICAL: VALID` (Phase 19)** — c'est le seul verdict positif de la Phase 19,
  et il a directement motivé la Phase 20-DR. Correctement suivi.
- **Le biais analytiquement inerte (Phase 20-DR)** — c'est un **résultat méthodologique
  réel**, pas une anomalie à réexplorer. Il est conservé au §14.A.
- **ISO bat les baselines de distance de 0,19 d'AUROC (Phase 21 : 0,731 contre 0,539)** —
  seul écart de grande magnitude jamais observé en faveur d'une construction du projet.
  **Mais** il compare deux variantes de la même famille géométrique, et le concurrent naturel
  (Trust Score) n'a jamais été testé. Ce n'est pas un résultat oublié, c'est un résultat dont
  la baseline manquait.

---

## 13. RED TEAM

| # | Objection | Statut | Justification factuelle |
|---|---|---|---|
| 1 | **HARKing** : l'hypothèse a été reformulée après chaque falsification | **VALID** | Quatre reformulations documentées au §4 ; trois changent la question |
| 2 | **Survivor chasing** : les phases 21–23 partent d'une cellule isolée | **VALID** | Phase 22 part de HAR/RF = 1 cellule sur 12, Random Forest |
| 3 | **Le résultat fondateur de la Phase 21 était un artefact** | **VALID** | Fuite d'étiquette établie, erratum publié |
| 4 | **Absence de baseline décisive** : le Trust Score n'a jamais été testé | **VALID** | `iso_margin_ratio` en est une variante de métrique |
| 5 | **Manque de nouveauté** : `d_S` est une norme L∞ standardisée | **VALID** | Phase 16 : interchangeable avec L2 à 0,0003 |
| 6 | **Noms causaux sur quantités statistiques** | **VALID** | « frontière d'oubli », « readiness », « attribution de cause », « action guidée » |
| 7 | **Multiplicité entre phases non contrôlée** | **VALID** | ~12 phases, aucune correction au niveau programme |
| 8 | **Décisions motivées par la significativité, pas la magnitude** | **VALID** | H2 franchit son seuil de 0,0003 |
| 9 | **p-hacking au sens strict** (essais répétés jusqu'au succès) | **NOT_SUPPORTED** | Aucun cas. Les seuils sont gelés avant TEST et jamais abaissés — Phase 22 refuse explicitement d'abaisser 0,70 |
| 10 | **Suppression de résultats défavorables** | **NOT_SUPPORTED** | IDV 3, 9, 15 conservées ; aucun jeu retiré ; défauts auto-signalés à chaque phase |
| 11 | **Tests mal construits** | **PARTIALLY_VALID** | Track B dégénéré, 13/38 conditions inertes, règle anti-ID destructrice — tous auto-signalés, aucun exploité en sa faveur |
| 12 | **Métriques choisies après coup** | **NOT_SUPPORTED** | AUGRC, AUROC, AURC, Holm, seuils : tous gelés avant ouverture du TEST depuis la Phase 14 |
| 13 | **Circularité** | **PARTIALLY_VALID** | Une seule occurrence réelle : `rob_loco_min` construite à partir d'`iso_full` contaminée |
| 14 | **Absence d'application** | **VALID** | Gain opérationnel final : +0,004 contre +0,05 requis, et −0,004 en déploiement |
| 15 | **Overfitting conceptuel** : la construction a été redéfinie pour survivre | **PARTIALLY_VALID** | `ISO_PRED` (étiquette prédite au lieu de vraie) est une redéfinition — mais elle était **forcée** et déclarée : sans elle il n'existait aucune version exempte de fuite |

---

## 14. BLUE TEAM

Le meilleur argument défendable, sans exagération.

**1. La discipline confirmatoire est réelle, vérifiable et supérieure à la pratique
courante.** Protocoles hashés en SHA-256 et commités avant les données ; amendements datés et
poussés avant tout résultat ; garde runtime patchant `builtins.open` pour rendre une
contamination *impossible* et non seulement interdite ; vérification verbatim d'une fonction
par empreinte à l'import ; 13 tests unitaires dont un qui vérifie explicitement qu'aucune
étiquette de TEST n'entre dans le score ; simulation de déploiement à seuil gelé. **Cela se
vérifie par `git diff`, pas par déclaration.**

**2. Les résultats négatifs sont solides et transférables.** « Un score géométrique de marge
de classe, calculé sans étiquette, porte un signal d'erreur réel (AUROC médiane 0,70–0,73) mais
est redondant avec les scores de probabilité du classifieur et n'apporte aucun gain
opérationnel » — établi sur **7 jeux de données, 4 familles de modèles, 2 phases confirmatoires
indépendantes**, avec pré-enregistrement, Holm, bootstrap apparié et simulation de déploiement.
C'est un résultat de réplication publiable dans la littérature de *selective classification*.

**3. B\* est une contribution méthodologique correcte.** Le défaut identifié — dénominateur
mobile d'une métrique « fraction sous seuil » — est réel, démontré sur fixture, à direction
connue (il flatte la métrique), et **le correctif se généralise** à toute métrique de cette
forme. Le rapport consigne même que la première version du test ne pouvait pas échouer.

**4. Le catalogue de modes de défaillance protocolaires est un actif réutilisable**, chaque
item démontré numériquement : perturbations analytiquement inertes quand elles s'appliquent
symétriquement à TRAIN et TEST ; référence co-dégradée rendant une mesure de visibilité
aveugle ; fuite d'étiquette par un index construit sur `y` ; pooling de cibles hétérogènes
gonflant l'AUROC ; heuristique anti-identifiant supprimant les variables continues ; endpoint
dégénéré rendant un track entier vide.

**5. Le programme s'auto-corrige.** L'erratum de la Phase 21 retire publiquement une
conclusion de la phase précédente. La Phase 22 neutralise son propre résultat fondateur en le
déclarant `DISCOVERY-ONLY`. Les Phases 21 et 23 signalent des défauts de leurs **propres**
critères gelés sans les corriger après coup. C'est rare.

---

## 15. Synthèse contradictoire

*Si ce travail était soumis aujourd'hui à un comité scientifique indépendant :*

**Serait jugé crédible** — la méthodologie confirmatoire et sa traçabilité ; les résultats
négatifs des Phases 21 à 23 ; l'analyse du défaut de dénominateur de `B` et sa réparation ; le
diagnostic des stress inertes ; l'audit forensique de la Phase 10, en particulier la
démonstration que `B` sature à zéro.

**Serait jugé intéressant mais insuffisant** — la décomposition Visibilité / Isolabilité /
Robustesse, qui est une grille de lecture raisonnable mais dont la Phase 20-DR montre qu'elle
est dominée par une seule composante ; le constat que la géométrie de classe est redondante
avec les probabilités, qui demanderait une comparaison au Trust Score pour être publiable.

**Serait rejeté** — toute revendication de nouveauté sur FO, `d_S`, B\* comme *critère*, la
Visibilité telle que définie, l'« architecture de readiness », l'attribution de cause et
l'action guidée. Et la Phase 20-DR dans sa forme publiée, à cause de la fuite d'étiquette —
même corrigée par erratum, un comité demanderait la ré-exécution complète.

**Le reproche central d'un comité** serait celui-ci : *le programme a passé douze phases à
tester des variantes d'une construction dont la Phase 10 avait déjà établi la dégénérescence
structurelle, et dont la Phase 16 avait déjà mesuré l'apport propre à +0,0012.*

---

## 16. Réponses aux questions du §XIV

1. **Phase la plus informative** — **Phase 10.** Elle explique *pourquoi* FO a perdu (ρ ≈ 0
   contre −0,6), établit la dégénérescence structurelle de `B`, montre que FO avait atteint
   l'optimum global de son propre critère, et produit la seule réparation métrique valide du
   programme. Second : **Phase 16**, qui répond à la question du projet (+0,0012) de façon
   confirmatoire et aveugle.
2. **Phase la plus redondante** — **Phase 22.** Elle teste une hypothèse construite sur une
   cellule isolée, et son résultat était largement prévisible depuis la Phase 21 (ISO perd
   dans 11 cellules sur 12).
3. **Phase remplaçable par plus simple** — **Phase 20-DR.** 38 conditions, 55 cellules, 159 390
   lignes d'événements. Une comparaison directe des trois axes contre max-probabilité sur les
   deux composants aurait donné la même conclusion, et un test unitaire anti-fuite aurait
   évité l'artefact.
4. **Où arrêter plus tôt** — **au commit `14c5706`, fin de Phase 16.** `TECHNOLOGY_CANDIDATE:
   NOT_YET` avec un apport propre de +0,0012 mesuré en aveugle était la réponse.
   Secondairement, **au §A.5 de la Phase 10** pour la branche « critère de placement ».
5. **Où continuer était juste** — de FO-v1 à la Phase 10. Une falsification sans diagnostic
   n'est pas un résultat ; l'audit forensique a transformé un échec en connaissance.
   Également : **la Phase 23**, qui pose enfin la bonne question (utilité incrémentale
   opérationnelle) avec le bon dispositif.
6. **Bifurcation la plus justifiée** — Phase 13A → Phase 14 (TEP). Le raisonnement est
   explicite et correct : TEP est le seul benchmark où σ est **déclaré par le processus**,
   donc le seul où FO est pleinement défini. C'est du bon design expérimental.
7. **Bifurcation la plus fragile** — Phase 20-DR → Phase 21, fondée sur un artefact.
8. **Résultat initialement surinterprété** — `R2 = 0,845` (Phase 20-DR), présenté comme « ce
   qui survit » alors qu'il lisait l'étiquette. Et, à un moindre degré, H2 (+0,0203).
9. **Résultat initialement sous-estimé** — **H8 = +0,0012** (Phase 16). Il répondait
   exactement à la question du projet, en aveugle, et il a été enregistré comme `WEAK` plutôt
   que comme la conclusion du programme. Second : la saturation de `B` à zéro (Phase 10 §A.5),
   enterrée dans une sous-section d'audit.
10. **Avons-nous testé la théorie initiale ?** — **Non, pas au-delà de la Phase 10.** La
    théorie initiale portait sur le placement de capteurs. Elle a été testée une fois,
    falsifiée, puis remplacée par quatre thèses successives partageant une formule mais pas une
    hypothèse.

---

## 17. Contrefactuel scientifique

*Avec toutes les connaissances acquises mais sans connaître les résultats TEST, quel programme
minimal aurait produit les mêmes décisions ?*

| # | Expérience | Décision qu'elle tranche |
|---|---|---|
| **1** | FO-v1 sur BattLeDIM contre les baselines OED, **avec** la corrélation critère↔endpoint sur designs aléatoires **et** l'évaluation de `B` en placement libre | FO comme critère de placement. Verdict : falsifié, avec cause. **Fusionne l'Ère 0 et la Phase 10.** |
| **2** | Gate de sémantique : sur quels benchmarks σ est-il **fourni par le processus** ? | Répond en une passe à ce que les Phases 11, 12, 13A, 17A, 19 ont établi en cinq. Réponse : TEP seul |
| **3** | TEP, confirmatoire aveugle, avec la question posée d'emblée comme **« qu'ajoute FO+B\* à un ensemble standard ? »** et le Trust Score parmi les baselines | Fusionne les Phases 14, 15 et 16. Verdict attendu : +0,001, donc fin de la revendication technologique |
| **4** | Réplication prospective du meilleur survivant sur 4 jeux publics neufs, avec AUGRC, seuil opérationnel gelé et Trust Score en comparateur | Fusionne les Phases 20 à 23 |

**Quatre expériences au lieu de douze phases.** Le programme réellement exécuté a produit les
mêmes décisions.

**Où le temps était-il incompressible ?** Les six gates d'accès (EPA, LeakDB, GraphLeak, 3W,
ZeMA, OpenML) ne pouvaient pas être anticipés : l'indisponibilité réseau n'est pas une
information scientifique. Environ un tiers du programme a été consacré à établir qu'on ne
pouvait pas tester, et **c'était nécessaire**.

**Où a-t-il été perdu ?** Trois endroits, tous après une réponse déjà obtenue : les Phases 20
à 23 après H8 ; la Phase 22 après la Phase 21 ; l'absence du Trust Score, qui aurait
court-circuité les Phases 21 à 23.

---

## 18. Inventaire final des actifs scientifiques

### A. Résultats robustes à conserver

| Résultat | Preuve | Portée | Originalité | Utilité |
|---|---|---|---|---|
| Un score géométrique de marge de classe sans étiquette porte un signal d'erreur réel mais **redondant** avec les probabilités du classifieur, et sans gain opérationnel | **réplication indépendante** (Phases 21 et 23), 7 jeux, 4 familles, Holm, déploiement simulé | plusieurs jeux, plusieurs modèles, tabulaire | **variation connue** (Trust Score) | **scientifique** (réplication négative publiable) |
| `B` sature à zéro en placement non contraint → aucun pouvoir de résolution | dérivé + mesuré sur 782 candidats | le critère lui-même, tout benchmark | originale démontrée, mais négative | **méthodologique** |
| Le dénominateur mobile de `B` biaise la métrique dans un sens favorable ; B\* le corrige | test synthétique falsifiable | toute métrique « fraction sous seuil » | **potentiellement originale** | **méthodologique** |
| Une perturbation appliquée symétriquement à TRAIN et TEST peut être analytiquement inerte | mesuré : 0,0000 exactement sur 5 conditions | toute étude de robustesse | probablement connue, rarement démontrée | **méthodologique** |
| Une « visibilité » définie contre une référence co-dégradée est aveugle à la dégradation | AUROC 0,356, sous le hasard | la définition | originale démontrée, négative | **méthodologique** |

### B. Résultats intéressants mais non établis

| Résultat | Test manquant exact |
|---|---|
| ISO bat les baselines de distance de +0,19 d'AUROC (0,731 contre 0,539) | **Comparaison directe au Trust Score de Jiang et al. (2018)**, k-NN et Mahalanobis, sur les mêmes cellules |
| Le tie-break p05 corrèle à la distance de **localisation** (ρ −0,296) | Réplication sur un second réseau, avec la localisation comme endpoint primaire |
| ISO se réplique sur `adult` et `allhypo` mais pas sur `GAMETES` et `agaricus` | Caractérisation *a priori* des jeux où il se réplique — **explicitement non recommandée**, c'est la question de la Phase 22, déjà falsifiée |

### C. Résultats falsifiés

FO comme critère de placement (falsifié **et** structurellement dégénéré) · FO comme meilleur
prédicteur d'échec (TEP) · l'apport propre FO+B\* à un ensemble standard (+0,0012, aveugle) ·
l'architecture readiness à trois axes · la Visibilité telle que définie · l'attribution de
cause (0,260 contre 0,247) · l'action guidée par readiness · l'existence d'un régime
identifiable *a priori* où ISO aide · l'utilité opérationnelle d'ISO en triage.

### D. Sans valeur scientifique suffisante

`R2 = 0,845` et tout ce qui en dépend (artefact de fuite) · `rob_loco_min` (contaminée) ·
Track B de FO-v1 (endpoint dégénéré) · les 13 conditions inertes de la Phase 20-DR ·
`iso_centroid_min` pour K = 2 (constante par construction) · H2 (+0,0203 contre un seuil de
0,02, contre la *moyenne* du SNR seulement) · HAR/RF (1 cellule sur 12) · la baseline « trois
scores » de la Phase 23 sur les jeux binaires (un seul score déguisé en trois).

---

## 19. Valeur réelle

**Scientifique** — *modeste et réelle*. Une réplication négative propre sur la redondance des
scores géométriques de marge avec les scores de probabilité, plus quatre résultats
méthodologiques. Publiable comme *negative results / replication*, pas comme découverte.

**Technique** — *faible*. Aucun artefact logiciel réutilisable au-delà du dépôt lui-même, à
l'exception du harnais de pré-enregistrement (garde runtime, vérification verbatim, gates
d'accès) qui est de bonne facture et transposable à d'autres programmes.

**Commerciale** — *nulle*. Établi par les données du programme lui-même : gain opérationnel
+0,004 contre +0,05 requis, et **négatif** au seuil de déploiement gelé. La construction
centrale est une variante d'une méthode publiée en 2018. Il n'y a ni avantage concurrentiel,
ni brevetabilité plausible, ni produit.

**Distinction à maintenir** : le programme a une valeur de *curiosité scientifique* et une
valeur *méthodologique*. Il n'a ni valeur de publication majeure, ni valeur commerciale. Ces
quatre choses ont été correctement distinguées par les rapports de phase eux-mêmes, qui n'ont
jamais revendiqué de technologie.

---

## 20. Verdicts

```
MISSED_MAJOR_RESULT:          NO
MISSED_NECESSARY_TEST:        YES
WRONG_BRANCH_DECISION:        YES
OVERPURSUED_WEAK_BRANCH:      YES
PREMATURELY_CLOSED_BRANCH:    POSSIBLE
IMPORTANT_BASELINE_MISSING:   YES
IMPORTANT_LITERATURE_MISSING: YES
CONFIRMATORY_INTEGRITY:       ACCEPTABLE
SCIENTIFIC_PROGRAM_VALUE:     LOW

FINAL_PROGRAM_DECISION:       ARCHIVE_AND_PUBLISH_NEGATIVE_RESULTS
```

**Justifications.**

`MISSED_MAJOR_RESULT: NO` — aucun résultat de grande magnitude n'a été laissé sans suite. Le
seul écart important jamais observé en faveur du projet (ISO +0,19 contre les distances) n'est
pas un résultat manqué mais un résultat dont la baseline décisive manquait.

`MISSED_NECESSARY_TEST: YES` — deux tests nécessaires manquaient. **(a)** Un test anti-fuite
d'étiquette avant la Phase 20-DR : il existe depuis la Phase 23 (test n° 8) et aurait évité
l'artefact fondateur des Phases 21 à 23. **(b)** La comparaison au Trust Score, concurrent
direct de la construction survivante.

`WRONG_BRANCH_DECISION: YES` — Phase 20-DR → Phase 21, fondée sur un chiffre contaminé.

`OVERPURSUED_WEAK_BRANCH: YES` — quatre phases après que H8 = +0,0012 eut répondu à la
question du projet en aveugle.

`PREMATURELY_CLOSED_BRANCH: POSSIBLE` — le signal de localisation de la Phase 10 a été
abandonné sans justification écrite. Il **n'atteint pas** le seuil de réouverture (§12.1).

`IMPORTANT_BASELINE_MISSING: YES` et `IMPORTANT_LITERATURE_MISSING: YES` — Trust Score
(NeurIPS 2018) et Mahalanobis OOD (NeurIPS 2018).

`CONFIRMATORY_INTEGRITY: ACCEPTABLE` — et non `STRONG`, pour deux raisons factuelles : la fuite
d'étiquette a survécu à une phase confirmatoire entière, et le constat F4 établit que la vérité
terrain 2019 était visible avant l'existence du gel. Pour les phases 14 à 23 prises isolément,
l'intégrité serait `STRONG`.

`SCIENTIFIC_PROGRAM_VALUE: LOW` — et non `NEGLIGIBLE` : cinq résultats robustes subsistent au
§18.A, tous négatifs ou méthodologiques, obtenus sous pré-enregistrement et répliqués. Mais
aucune revendication positive ne survit, et la construction centrale est connue depuis 2018.

`FINAL_PROGRAM_DECISION: ARCHIVE_AND_PUBLISH_NEGATIVE_RESULTS` — et non
`ONE_FINAL_CONFIRMATORY_TEST` : la seule hypothèse insuffisamment testée (localisation)
échoue au critère « effet important » et appartient à un critère structurellement dégénéré. Ce
serait une hypothèse de sauvetage, et le protocole d'audit l'interdit.

---

```
TOP_5_THINGS_WE_ACTUALLY_LEARNED:
1. Un score géométrique de marge de classe calculé sans étiquette porte un signal d'erreur
   réel (AUROC 0,70–0,73) mais il est redondant avec les probabilités du classifieur et
   n'apporte aucun gain opérationnel — établi sur 7 jeux, 4 familles, 2 phases confirmatoires.
2. Le critère B est structurellement dégénéré : il sature à zéro pour tout design raisonnable
   en placement non contraint, donc il ne peut ordonner aucun design.
3. Une métrique « fraction sous seuil » dont le dénominateur dépend du bruit se flatte
   elle-même quand les conditions se dégradent ; geler le support corrige exactement ce biais.
4. Une perturbation appliquée symétriquement à TRAIN et TEST peut être analytiquement inerte —
   mesuré à 0,0000 exactement — et une « visibilité » mesurée contre une référence co-dégradée
   est aveugle par construction à ce qu'elle prétend détecter.
5. FO n'est pas une frontière informationnelle : c'est une norme L∞ standardisée,
   interchangeable avec la norme L2 à 0,0003 d'AUROC près.

TOP_5_MISTAKES_OR_WEAKNESSES:
1. Une fuite d'étiquette a survécu à une phase confirmatoire entière et a fondé les trois
   phases suivantes ; aucun test unitaire ne l'interdisait avant la Phase 23.
2. Le concurrent direct de la construction survivante — le Trust Score, publié en 2018 — n'a
   jamais été testé comme baseline.
3. Les décisions de continuer ont été prises sur la significativité et non sur la magnitude :
   H2 a franchi son seuil de 0,0003 et a déclenché une phase ; HAR/RF, une cellule sur douze,
   en a déclenché une autre.
4. Le programme a continué quatre phases après que H8 = +0,0012, mesuré en aveugle, eut
   répondu à la question du projet.
5. Des noms à forte connotation physique ou causale — frontière d'oubli, readiness,
   attribution de cause, action guidée — ont recouvert des quantités purement statistiques,
   ce qui a entretenu l'idée qu'il restait quelque chose à valider.

WHAT_WE_WOULD_DO_DIFFERENTLY_IF_STARTING_TODAY:
1. Poser la question du projet en premier et non en dernier : « qu'ajoute cette construction à
   un ensemble standard bien choisi ? », avec un seuil de magnitude fixé d'avance et un
   endpoint opérationnel, pas un endpoint de classement.
2. Identifier le concurrent le plus proche dans la littérature avant d'écrire la première
   ligne de code, et le mettre dans les baselines dès la première phase.
3. Écrire les tests unitaires anti-fuite et anti-inertie avant les protocoles : « aucune
   étiquette de TEST n'entre dans le score » et « chaque perturbation change effectivement les
   prédictions » auraient éliminé deux défauts majeurs.
4. Exécuter un gate de sémantique unique — sur quels benchmarks sigma est-il fourni par le
   processus ? — au lieu de cinq gates d'accès successifs.
5. Fixer une règle d'arrêt au niveau du programme, pas seulement au niveau de la phase : après
   une mesure aveugle et confirmatoire d'apport propre sous le seuil de pertinence, la branche
   se ferme, quel que soit le sous-résultat qui semble survivre.
```

---

**Sources littérature citées** : Jiang, Kim, Guan & Gupta, *To Trust Or Not To Trust A
Classifier*, NeurIPS 2018 (arXiv:1805.11783) ; Lee, Lee, Lee & Shin, *A Simple Unified
Framework for Detecting Out-of-Distribution Samples and Adversarial Attacks*, NeurIPS 2018 ;
Romano, Sesia & Candès, *Classification with Valid and Adaptive Coverage*, NeurIPS 2020 ;
El-Yaniv & Wiener, *On the Foundations of Noise-free Selective Classification*, JMLR 2010 ;
Traub et al., *Overcoming Common Flaws in the Evaluation of Selective Classification Systems*,
2024 ; Ledoit & Wolf 2004 ; Holm 1979.
