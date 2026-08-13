# RAPPORT PHASE 10 — RESET / AUDIT / RECONSTRUCTIBILITÉ PURE

FO-v1 reste gelé et **NOT_SUPPORTED**. Rien ici ne le rejoue ni ne le modifie ;
la Phase A ne fait que lire ses sorties committées.

## Verdicts

| Portée | Verdict |
|---|---|
| `FO_DIAGNOSTIC` | **FO_DIAGNOSTIC_NOT_SUPPORTED** |
| `FO_RECONSTRUCTIBILITY` | **NOT_EVALUATED_DATASET_UNAVAILABLE** |
| FO-v1 (rappel, inchangé) | NOT_SUPPORTED |
| Optimiseur FO-v2 créé | **non** |

`FO_DIAGNOSTIC_NOT_SUPPORTED` signifie ici **non démontré**, pas réfuté. Le
signal 2018 est réel et fort ; ce qui manque est la confirmation hors
échantillon, et l'échantillon qui aurait pu la fournir est dégénéré.

Sur `FO_RECONSTRUCTIBILITY` : la consigne écrit la règle en binaire (« sinon
NOT_SUPPORTED »). Ce binaire porte sur le *résultat* d'un test exécuté. Un test
jamais exécuté ne soutient aucune des deux branches, et écrire NOT_SUPPORTED
présenterait une donnée absente comme un résultat négatif. J'émets donc un
statut distinct et je le signale ici pour que tu puisses imposer la lecture
littérale si tu la préfères.

---

## Classification des résultats

Chaque énoncé porte l'une de ces étiquettes :
**[reproduit]** re-exécuté ici · **[externe]** provient d'un artefact officiel ·
**[dérivé]** conséquence analytique · **[simulation]** issu du benchmark
reconstruit · **[hypothèse]** interprétation non prouvée · **[limite]**.

---

## PHASE A — Audit forensique

### A.0 Document de protocole manquant **[limite]**

`PROTOCOLE_AUDIT_FORENSIQUE_BATTLEDIM.md` n'a **pas** été fourni ; seul le
prompt de Phase 10 a été déposé. J'ai donc exécuté les points obligatoires
énumérés dans le prompt lui-même. Si ce document contient des exigences
supplémentaires, elles ne sont pas couvertes.

### A.1 Ce que BattLeDIM a réellement falsifié

C'est le résultat central de la Phase 10.

FO-v1 a montré que minimiser B n'achète pas de performance de détection. Deux
explications incompatibles restaient ouvertes : (a) B est un mauvais substitut ;
(b) B est correct mais l'endpoint était saturé. Elles se séparent en corrélant
**chaque** critère de conception à l'endpoint réalisé sur 1 000 designs
aléatoires par budget.

**[reproduit]** Spearman ρ entre critère de design et taux de faux oubli, 2018
(l'année dont l'endpoint a de la variance : 8 valeurs distinctes, σ = 0,085) :

| critère | k=4 | k=6 | k=8 | k=10 | k=12 |
|---|---|---|---|---|---|
| D-optimal rank-reduced | −0,500 | −0,583 | **−0,652** | **−0,652** | −0,637 |
| D-optimal bayésien / info-gain | −0,569 | −0,545 | −0,545 | −0,541 | −0,528 |
| A-optimal rank-reduced | −0,389 | −0,528 | −0,622 | −0,599 | −0,560 |
| goal-oriented OED | −0,437 | −0,581 | −0,592 | −0,534 | −0,471 |
| **B (critère FO)** | **−0,145** | **−0,166** | **−0,107** | **−0,072** | **−0,002** |
| **visibilité p05 (tie-break FO)** | **+0,130** | **+0,135** | +0,036 | +0,045 | +0,065 |

**[reproduit]** 2019 : l'endpoint a **exactement 1 valeur distincte** sur
1 000 designs (σ = 2,8·10⁻¹⁷). Aucun critère ne peut y corréler.

**Conclusion [dérivé].** L'explication est (a), pas (b). Là où l'endpoint porte
du signal, les critères OED le suivent à ρ ≈ −0,5 à −0,65 et **B ne le suit pas**
— ρ ≈ −0,1, qui décroît vers 0 quand le budget augmente. Le tie-break primaire
de FO (5ᵉ percentile de visibilité) a le **signe inverse** : une meilleure
visibilité au 5ᵉ percentile va avec *plus* de faux oubli.

Donc : **Track A a falsifié quelque chose de réel sur B. Track B n'a rien
falsifié du tout** — son endpoint était constant par construction.

**[limite]** Sur la distance de localisation (endpoint continu), le tie-break
p05 est le seul critère de signe favorable et constant (ρ = −0,296 à k=4,
−0,190 à k=6). La famille FO n'est donc pas sans signal — elle en a pour la
localisation, pas pour la détection.

### A.2 L'événement qui fixe le plancher de FO

**[reproduit]** Le taux de 0,071 de FO à k≥6 en Track A est **un seul
événement : p232** (incipiente, ⌀ 0,0201 m, 2018-01-31 → 2018-02-10).

| budget | ff | événements manqués |
|---|---|---|
| k=4 | 0,143 | p232, p183 |
| k=6 … k=12 | 0,071 | **p232** |

À k=8, p232 est détecté par **9 des 10 baselines** ; seuls FO et `centrality`
le manquent. Avec 14 événements, un seul manque vaut 0,071.

**[limite]** Tout le résultat Track A de FO repose donc sur un unique événement.
C'est une base étroite, et l'IC à 95 % le reflète.

### A.3 Chronologie du gel **[reproduit]**

Vérifiée depuis l'historique git, pas affirmée :

| étape | commit | horodatage |
|---|---|---|
| gel corrigé (C-BIAS) | `b92b8e53` | 2026-08-13T14:36:35Z |
| résultats Track A + B | `6a16fce5` | 2026-08-13T14:45:23Z |
| résultats finaux | `71413217` | 2026-08-13T15:06:24Z |

Les résultats 2019 sont committés **9 minutes après** le gel. Le gel a été
réémis une fois (correction C-BIAS) ; le protocole superseded est committé.

### A.4 Audit des baselines → `AUDIT_BASELINES.md`

**Aucune baseline n'est mal implémentée d'une manière qui désavantagerait FO.**
Chaque défaut trouvé joue dans l'autre sens ou est neutre. Deux points
matériels :

- **[reproduit]** Les dix baselines ne sont pas dix designs. Mesuré :
  **8 designs distincts sur 11 méthodes à k=6 et k=8**, 9 à k=4 et k=12 —
  D-bayésien, A-bayésien, E-observable et info-gain sélectionnent le *même*
  sous-ensemble. Il y a donc **7 à 8 baselines distinctes, pas 10**. Le groupe
  qui a battu FO est précisément celui qui s'effondre.
- **[reproduit]** FO n'a pas perdu par sous-optimisation : à k=4, l'énumération
  exhaustive des 40 920 sous-ensembles donne un écart glouton de **0,0**. FO a
  atteint l'optimum global de son propre critère et a quand même perdu.

### A.5 33 capteurs préinstallés vs toutes les jonctions **[limite]**

FO-v1 sélectionne parmi les **33 capteurs de pression préinstallés de
BattLeDIM**, pas parmi les 782 jonctions. Ce sont deux problèmes différents : le
premier est un sous-problème très contraint (C(33,k)), le second est le problème
de placement complet.

Une bibliothèque de sensibilité *toutes jonctions* a été construite
(782 scénarios × **782 emplacements candidats**,
`phase10_reset/data/sensitivity_all_junctions.npz`) pour rendre la seconde
question adressable. **[reproduit]** :

| k | B, placement libre (782 candidats) | B, contraint aux 33 | recouvrement du choix libre avec les 33 |
|---|---|---|---|
| 4 | **0,0000** | 0,0000 | 2 / 4 |
| 6 | **0,0000** | 0,0000 | 3 / 6 |
| 8 | **0,0000** | 0,0000 | 4 / 8 |
| 12 | **0,0000** | 0,0000 | 5 / 12 |

**[dérivé]** Dans le problème non contraint, B **sature à zéro dès k=4** : avec
782 emplacements disponibles on trouve toujours 4 nœuds qui voient tous les
scénarios éligibles au-dessus de 3σ. Le critère n'a alors **aucun pouvoir de
résolution** — il classe tous les bons designs ex æquo. Il n'est non trivial que
dans le régime contraint des 33 capteurs, et même là sa valeur optimale est de
l'ordre de 0,001, soit **un scénario sur 770**.

C'est une limite structurelle du critère et non un artefact du benchmark : un
critère qui vaut 0 pour tout design raisonnable ne peut pas ordonner des
designs. **Aucune conclusion de FO-v1 ne s'étend au cas non contraint**, et le
peu qu'on puisse en dire est défavorable au critère, pas favorable.

---

## PHASE B — Réparation diagnostique minimale

Deux métriques, pas un nouvel optimiseur.

**Le défaut de B [dérivé].** `E_kappa` est recalculé à partir du σ qu'on lui
passe. σ décrit les *conditions de mesure* ; la population que la métrique
prétend décrire change donc silencieusement avec le bruit, et deux valeurs de B
sous bruits différents sont des fractions de dénominateurs différents.

**B\*** gèle le support une fois, depuis la référence riche sous σ nominal de
TRAIN. `|E*|` est une constante de l'étude.

**[reproduit]** `test_b_star_denominator_invariance`, sur un tenseur synthétique
(aucune dépendance à un fichier de données), bruit d'évaluation de 0,25× à 8× :

| bruit × | 0,25 | 0,5 | 1 | 2 | 4 | 8 |
|---|---|---|---|---|---|---|
| support B | 281 | 238 | 199 | 165 | 120 | **70** |
| support B\* | 199 | 199 | 199 | 199 | 199 | **199** |
| valeur B | 0,036 | 0,042 | 0,035 | 0,103 | 0,092 | **0,257** |
| valeur B\* | 0,000 | 0,000 | 0,035 | 0,256 | 0,452 | **0,739** |

**Le biais a une direction, et elle flatte la métrique [dérivé].** Monter le
bruit éjecte les scénarios discrets et difficiles hors de `E_kappa`, ne laissant
que les bruyants et faciles : B s'améliore pour une raison qui n'a rien à voir
avec le réseau de capteurs. À 8× de bruit, **B annonce 26 % d'aveuglement là où
B\* en mesure 74 %**.

**[limite honnête]** Le test a **échoué** sur ma première version : les
amplitudes de scénarios y étaient tirées dans une plage trop étroite, tous les
scénarios restaient loin au-dessus de κ à tous les niveaux de bruit, le support
dynamique ne bougeait jamais et le test serait passé à vide. La fixture couvre
maintenant trois décades d'amplitude. Consigné parce qu'un test qui ne peut pas
échouer n'est pas une preuve.

B\* n'a servi à sélectionner **aucun** hyperparamètre sur **aucun** jeu de test.

---

## PHASE C — Dataset EPA : BLOQUÉ

**[externe]** `Dataset_A-pg4z_TestSourceInversion_Haxton_20160728.zip` n'a pas
pu être acquis. Détail exhaustif dans `EPA_DATA_MANIFEST.json`.

| ordre | cible | résultat | erreur exacte |
|---|---|---|---|
| 1 | `pasteur.epa.gov/uploads/149/…zip` | ÉCHEC | `curl: (56) CONNECT tunnel failed, response 403` |
| 2 | `catalog.data.gov` + endpoint CKAN | ÉCHEC | `curl: (56) CONNECT tunnel failed, response 403` |
| 3 | ScienceHub / Pasteur / EDG / epa.gov | ÉCHEC | `CONNECT 403` sur les quatre hôtes |
| 4 | tout miroir intégral vérifiable | ÉCHEC | aucun miroir n'existe sur un hôte atteignable |

Enregistrements côté proxy : `connect_rejected — gateway answered 403 to CONNECT
(policy denial or upstream failure)` pour `pasteur.epa.gov:443`,
`catalog.data.gov:443`, `sciencehub.epa.gov:443`, `edg.epa.gov:443`,
`www.epa.gov:443`, `doi.org:443`.

GitHub est le seul hôte non-paquet atteignable. `USEPA/Water-Security-Toolkit`
est accessible — c'est **l'outil d'inversion**, pas le dataset. Le ZIP n'est
dans aucun dépôt.

**Aucun dataset synthétique n'a été substitué.** `PURE_RECONSTRUCTIBILITY_RESULTS.csv`
est livré avec son schéma et **0 ligne**.

**Pipeline prêt** : déposer le ZIP dans
`phase10_reset/data/epa_source_inversion/` et lancer `python3 run_phase10.py
--phase D`. Sans le ZIP, la phase signale BLOCKED et sort sans rien fabriquer.

---

## PHASE D — NON EXÉCUTÉE

Impossible sans les cas de test officiels. Aucun endpoint de reconstruction de
source (top-1, top-5, NLL, rang, distance réseau, entropie postérieure, Brier)
n'a été calculé. **[limite]**

---

## PHASE E — FO comme diagnostic (substitut BattLeDIM, clairement étiqueté)

La Phase E telle que spécifiée appartient au dataset EPA. Sa question centrale
reste posable sur BattLeDIM et l'a été : **le score FO prédit-il qu'un scénario
donné va échouer ?** C'est une question différente de celle de FO-v1 (le score
fait-il de meilleurs designs — non).

**[simulation]** AUROC pour la prédiction d'échec de détection par scénario :

| année | prédicteur | AUROC | IC 95 % | prévalence d'échec |
|---|---|---|---|---|
| 2018 | **visibilité FO** | **0,821** | [0,768 – 0,868] | 0,055 |
| 2018 | marge d'isolabilité | 0,562 | [0,487 – 0,638] | |
| 2018 | SNR | 0,507 | [0,431 – 0,581] | |
| 2018 | plus petite v.s. | 0,314 | [0,230 – 0,405] | |
| 2019 | visibilité FO | 0,478 | [0,431 – 0,525] | 0,087 |
| 2019 | SNR | 0,771 | [0,736 – 0,805] | |

**Sur 2018, FO est un bon prédicteur d'échec et domine largement les
diagnostics simples.** C'est le résultat le plus favorable à FO de toute
l'étude, et il porte sur un usage — le diagnostic — que FO-v1 n'avait pas testé.

**Pourquoi cela ne suffit pas [dérivé] :**

1. **2019 est dégénéré.** Ses deux événements en échec (p523, p827) échouent
   dans **55 configurations de design sur 55**. L'issue est fixée par
   l'événement, pas par le réseau de capteurs. Aucun score dépendant du design
   ne peut y être évalué, même en principe. Le 0,478 de FO n'est **pas** une
   preuve contre FO, et le 0,771 du SNR n'est **pas** une preuve pour lui.
2. **Le gradient par décile n'est pas monotone** sur 2018 : 0,00 0,00 0,03 0,00
   0,00 0,01 0,01 **0,22** 0,06 **0,21** — 78 % de pas non décroissants, là où
   la règle exige un gradient monotone clair.
3. **Le test hors échantillon requis est la Phase D/E sur le dataset EPA**, qui
   est bloqué.

D'où `FO_DIAGNOSTIC_NOT_SUPPORTED` = **non démontré**.

**[hypothèse]** Lecture qui reste à tester : FO capte les échecs *limités par la
visibilité* et pas les échecs *limités par le masquage*. En 2019, quatre fuites
courent depuis le 1ᵉʳ janvier et masquent les deux suivantes ; c'est un
phénomène temporel, qu'un score de visibilité ne peut pas voir par construction.

---

## PHASE F — Règles de verdict appliquées

| condition (diagnostic) | satisfaite ? |
|---|---|
| AUROC > 0,70 hors entraînement | **non** — le seul hors-échantillon disponible est dégénéré |
| AUPRC > prévalence, IC favorable | 2018 oui ; hors échantillon non évaluable |
| gradient monotone par décile | **non** (78 %) |
| conservé sous erreur de mesure ET de modèle | **non testé** (exige la Phase D) |
| non dominé par une métrique simple | **oui sur 2018** (0,821 vs 0,562) |

→ `FO_DIAGNOSTIC_NOT_SUPPORTED`.

`FO_RECONSTRUCTIBILITY` : aucune des conditions n'est évaluable sans le dataset.
→ `NOT_EVALUATED_DATASET_UNAVAILABLE`.

**Aucun optimiseur FO-v2 n'a été créé.**

---

## Ce que la Phase 10 a réellement établi

1. **[dérivé]** BattLeDIM Track B n'a rien falsifié — endpoint constant sur
   1 000 designs.
2. **[reproduit]** Track A a falsifié quelque chose de réel : là où l'endpoint
   varie, les critères OED le prédisent (ρ ≈ −0,5 à −0,65) et **B non**
   (ρ ≈ −0,1 → 0). Le tie-break de FO a le signe inverse pour la détection.
3. **[reproduit]** Le plancher de FO en Track A tient à **un seul événement**,
   p232.
4. **[dérivé]** B est **biaisé de façon flatteuse** sous bruit croissant ; B\*
   corrige le dénominateur et l'invariance est prouvée par test.
5. **[reproduit]** Les baselines sont saines ; il y en a 7–8 distinctes, pas 10 ;
   FO n'a pas perdu par sous-optimisation.
6. **[simulation]** FO a un **signal diagnostique réel sur 2018** (AUROC 0,821),
   non démontré hors échantillon.
7. **[limite]** La question de reconstructibilité pure reste **entièrement
   ouverte** : le dataset qui devait la trancher est inaccessible.

## Si FO perd, le dire

**FO perd, à nouveau, sur ce pour quoi il a été conçu.** Comme critère de
placement de capteurs, B n'est pas seulement inférieur aux baselines OED : il
est **quasi non corrélé à l'endpoint qu'il prétend améliorer**, et son
tie-break pousse dans la mauvaise direction pour la détection. La Phase 10 ne
sauve pas FO-v1 ; elle explique *pourquoi* il a échoué et écarte les
explications commodes (baselines truquées, sous-optimisation, saturation).

Le seul résultat encourageant est ailleurs que là où FO a été conçu : comme
**diagnostic par scénario** sur 2018, FO bat nettement les alternatives simples.
Cela mérite le test hors échantillon prévu — et ce test est précisément celui
que le blocage réseau empêche.

---

## Limites

- `PROTOCOLE_AUDIT_FORENSIQUE_BATTLEDIM.md` non fourni.
- Phases C et D non exécutées ; aucun endpoint de reconstruction de source.
- Phase E exécutée sur un substitut BattLeDIM, pas sur le dataset prévu.
- Les corrélations de substitution portent sur 1 000 designs **aléatoires** par
  budget ; les designs optimisés vivent dans la queue de cette distribution et
  pourraient s'y comporter autrement.
- L'endpoint 2018 ne prend que 8 valeurs distinctes (14 événements) ; les ρ sont
  estimés sur une échelle grossière.
- FO-v1 sélectionne parmi 33 capteurs préinstallés ; rien ici ne se transporte
  au placement libre sur 782 jonctions.
- Les seuils de verdict (0,70 d'AUROC, monotonie) sont des règles internes.
