# Frontière d'Oubli — dossier de falsification complet

Document autonome. Consolide trois campagnes : FO-v1 (validation externe sur BattLeDIM),
Phase 10 (audit forensique + réparation métrique), Phase 11 (tentative de portage sur le
jeu de données EPA source-inversion).

Aucun optimiseur FO-v2 n'a été créé à aucun stade.

---

## 1. Registre des verdicts

| Portée | Verdict | Sens exact |
|---|---|---|
| **FO-v1** — FO comme règle de placement de capteurs | `NOT_SUPPORTED` | Testé, a perdu |
| **FO_DIAGNOSTIC** — FO comme prédicteur d'échec | `NOT_SUPPORTED` | **Non démontré**, pas réfuté |
| **FO_RECONSTRUCTIBILITY** | `NOT_EVALUATED` | Jeu de données jamais obtenu |
| **EPA_REPRODUCTION** (Phase 11) | `FAILED` | **Non tentée** faute de données, pas tentée-puis-divergente |

Ces distinctions sont maintenues partout. Une expérience non exécutée n'est pas une
expérience ratée. `VALIDATED_EXTERNALLY` n'a jamais été atteignable et est absent du code
(assertion sur la liste des verdicts autorisés).

---

## 2. Ce qui a été testé

**Critère FO.** Pour un scénario latent `z`, un réseau de capteurs `S`, une référence riche `R` :

```
d_S(z)        = max_t max_{j in S} |Δp[z, j, t]| / σ_j       (visibilité en unités de bruit)
E_κ           = { z : d_ref(z) ≥ κ }                          (scénarios visibles par R)
B_{κ,η}(S)    = P[ d_S(z) ≤ η | z ∈ E_κ ]                     (taux d'angle mort)
```

Sélection : minimiser `B` ; à égalité, maximiser le 5ᵉ percentile de visibilité, puis le
10ᵉ, puis la moyenne. Gelé : κ = η = 3.

**Benchmark.** BattLeDIM 2020 / L-Town. 782 jonctions, 909 conduites, 33 capteurs de
pression préinstallés. 14 événements de fuite en 2018, 23 en 2019.

**Budgets.** k ∈ {4, 6, 8, 10, 12}.

**Baselines (10).** D/A/E-optimal bayésien, Bayesian information gain, D/A/E-optimal
rank-reduced, goal-oriented OED, dispersion topologique, centralité, random (100 réplications).

**Détecteur identique pour toutes les méthodes.** Modèle nominal ridge sur entrées exogènes
(3 débits d'entrée, niveau de cuve, harmoniques journalières, jour de semaine), résidus
standardisés par MAD robuste, CUSUM bilatéral par capteur avec re-calibrage, localisation par
similarité cosinus contre la bibliothèque de signatures. **Seul le sous-ensemble de capteurs varie.**

---

## 3. Provenance des données et quatre constats critiques

**Les SCADA publiés de BattLeDIM sont inaccessibles.** Zenodo (record 4017659) et
`battledim.ucy.ac.cy` sont refusés par la politique de sortie réseau
(`curl: (56) CONNECT tunnel failed, response 403`). Aucun miroir des CSV n'existe sur un
hôte atteignable (5 dépôts candidats sondés).

**Ce qui a été récupéré** depuis le dépôt officiel des organisateurs
(`KIOS-Research/BattLeDIM` @ `ea81f544`) : les trois modèles EPANET, les calendriers de
fuites 2018 et 2019, le générateur officiel, le code de scoring MATLAB officiel, et les
23 séries officielles de débit de fuite 2019.

Les SCADA sont donc **régénérés** avec le générateur, le modèle et le calendrier officiels —
pipeline qui ne contient aucun tirage aléatoire.

### Les quatre constats

- **F1** — Les CSV SCADA publiés n'ont jamais pu être obtenus.
- **F2** — `L-TOWN_v2_Real.inp` ne contient que 365 jours de patrons de demande à pas de
  300 s, alors que la configuration demande deux ans. EPANET indexe les patrons modulo leur
  longueur : **une régénération de 2019 répète les demandes de 2018 à l'identique.**
- **F3** — Le générateur publié n'applique **aucun bruit de mesure**. Il définit une plage
  d'incertitude qu'il n'utilise jamais — ce n'est donc pas la version exacte qui a produit
  les CSV publiés.
- **F4** — Les organisateurs livrent la vérité terrain 2019 **dans le même fichier** que la
  configuration 2018. Elle était donc visible pendant l'inventaire obligatoire des données,
  avant l'existence du gel. Consigné, non dissimulé.

### F2 vaut pour le vrai benchmark, pas seulement pour la reconstruction

Les 23 fichiers `Leak_p*.xlsx` officiels livrés avec le code de scoring sont des sorties du
générateur des organisateurs (105 120 échantillons chacun). Comparaison avec notre régénération :

| statistique | valeur |
|---|---|
| séries comparées | 23 |
| pire écart relatif d'une moyenne de série | **4,05·10⁻⁵** |
| fraction d'échantillons dans l'arrondi 0,01 du générateur | 0,949 |
| pire écart absolu max | 0,24 m³/h |

Comme q = C·√p, reproduire ces débits exige que les pressions — donc les demandes pilotant
tout le réseau — coïncident avec la campagne officielle. Des demandes différentes ne
laisseraient pas les moyennes concorder à 4·10⁻⁵. **La répétition annuelle des demandes est
une propriété du jeu de données BattLeDIM publié**, pas un artefact de la reconstruction.

Cela relève la valeur du track 2019 mais n'en fait pas une validation sur le SCADA publié :
les mesures de pression publiées, et le bruit que les organisateurs y ont ajouté (F3),
restent inaccessibles.

---

## 4. FO-v1 — résultats

### Track A — validation événementielle par exclusion (14 événements 2018)

À chaque pli, le modèle nominal, σ, le seuil d'alarme et la sélection de capteurs de chaque
méthode sont réappris **sans** l'événement évalué.

Taux de faux oubli (plus bas = mieux) :

| méthode | k=4 | k=6 | k=8 | k=10 | k=12 |
|---|---|---|---|---|---|
| **FO** | **0,143** | **0,071** | **0,071** | **0,071** | **0,071** |
| D-optimal bayésien | 0,071 | 0,000 | 0,000 | 0,000 | 0,000 |
| A-optimal bayésien | 0,071 | 0,000 | 0,000 | 0,000 | 0,000 |
| E-observable subspace | 0,000 | 0,000 | 0,000 | 0,000 | 0,000 |
| Bayesian info gain | 0,071 | 0,000 | 0,000 | 0,000 | 0,000 |
| D-optimal rank-reduced | 0,071 | 0,000 | 0,000 | 0,000 | 0,000 |
| A-optimal rank-reduced | 0,214 | 0,071 | 0,000 | 0,000 | 0,000 |
| E-optimal rank-reduced | 0,143 | 0,000 | 0,000 | 0,000 | 0,000 |
| goal-oriented OED | 0,143 | 0,071 | 0,071 | 0,000 | 0,000 |
| dispersion topologique | 0,071 | 0,071 | 0,071 | 0,071 | 0,000 |
| centralité | 0,143 | 0,143 | 0,143 | 0,071 | 0,071 |
| **random (moy. 100)** | 0,144 | 0,091 | **0,061** | **0,058** | **0,043** |

**FO ne bat aucune des 10 baselines, à aucun budget. Il est moins bon que le placement
aléatoire moyen à k = 8, 10 et 12.**

Verdict Track A : `NOT_SUPPORTED` (FO bat 0 baseline sur 10 à chaque budget, IC bootstrap
apparié 10 000 rééchantillonnages).

### Track B — 2019 reconstruit (23 événements) : plafond total

Toutes les méthodes, tous les budgets : **exactement 0,087**, en manquant les deux mêmes
événements (p523, p827). Aucune discrimination n'existe. Le random moyen donne 0,087 aussi.

Détail à k=8 (là où les méthodes se séparent enfin, sur les endpoints secondaires) :

| méthode | rappel | précision | FP | délai moy. (h) | localisation moy. (m) | TP officiels | score BattLeDIM (€) |
|---|---|---|---|---|---|---|---|
| FO | 0,913 | 0,512 | 20 | 301 | 1223 | 7 | 80 127 |
| D/A/E-bayésien, info-gain | 0,913 | 0,457 | 25 | 155 | 1631 | 12 | 161 264 |
| D-optimal rank-reduced | 0,913 | 0,467 | 24 | 172 | 1848 | 7 | 157 322 |
| A-optimal rank-reduced | 0,913 | 0,447 | 26 | 178 | 1543 | 6 | 72 604 |
| E-optimal rank-reduced | 0,913 | 0,457 | 25 | 156 | 1499 | 8 | 149 909 |
| goal-oriented OED | 0,913 | 0,447 | 26 | 151 | 1409 | 8 | **188 416** |
| dispersion topologique | 0,913 | 0,457 | 25 | 177 | 1611 | 5 | 97 610 |
| centralité | 0,913 | 0,500 | 21 | 266 | 1284 | 6 | 84 820 |

Sur le score économique officiel, **FO est dans la moitié basse** (80 127 € contre 161 264 €
pour le groupe OED bayésien et 188 416 € pour goal-oriented OED).

Verdict Track B : `NOT_SUPPORTED`.

### Track C — étude de robustesse synthétique

Bruit capteur × {0, 1, 2, 4} et perturbation de demande × {0, 0,5, 1}, 5 graines, distributions
gelées depuis 2018. FO est au moins aussi bon que toutes les baselines dans **7 cellules sur
60 (12 %)**.

Verdict Track C : `NOT_SUPPORTED`.

### Verdict global FO-v1 : `NOT_SUPPORTED`

**FO minimise son propre critère de conception quasi parfaitement** — B tombe à ~0 dès k=6,
très en dessous de toutes les baselines — **et cet avantage ne se transfère pas** en
performance de détection sous détecteur identique.

### Anomalies conservées

- La localisation n'atteint le seuil de 300 m de BattLeDIM pour **aucune méthode**
  (0 à 14 % des localisations sous 300 m). Le score économique officiel est donc peu
  discriminant, et détection et localisation sont rapportées séparément.
- Dans Track C, **ajouter du bruit fait baisser** le taux de faux oubli : le seuil est gelé et
  non recalibré par cellule, donc plus de bruit = plus d'alarmes = plus d'événements appariés,
  et plus de faux positifs. Le point de fonctionnement se déplace entre cellules.
- Le contrôle de permutation d'étiquettes est **inopérant** pour un endpoint temporel :
  permuter les labels de conduite laisse l'appariement temporel invariant par construction.
  Rapporté comme faiblesse du contrôle, pas comme contrôle réussi.

---

## 5. Phase 10 — pourquoi FO perd

### 5.1 Le résultat central : B est un mauvais substitut

Deux explications restaient ouvertes : (a) B est un mauvais substitut ; (b) B est correct mais
l'endpoint était saturé. On les sépare en corrélant **chaque** critère de conception à
l'endpoint réalisé, sur **1 000 designs aléatoires par budget**.

Spearman ρ entre critère de design et taux de faux oubli réalisé, **2018** (seule année dont
l'endpoint a de la variance : 8 valeurs distinctes, σ = 0,085) :

| critère | k=4 | k=6 | k=8 | k=10 | k=12 |
|---|---|---|---|---|---|
| D-optimal rank-reduced | −0,500 | −0,583 | **−0,652** | **−0,652** | −0,637 |
| D-optimal bayésien / info-gain | −0,569 | −0,545 | −0,545 | −0,541 | −0,528 |
| A-optimal rank-reduced | −0,389 | −0,528 | −0,622 | −0,599 | −0,560 |
| goal-oriented OED | −0,437 | −0,581 | −0,592 | −0,534 | −0,471 |
| A-optimal bayésien | −0,541 | −0,485 | −0,464 | −0,440 | −0,404 |
| E-optimal rank-reduced | −0,387 | −0,524 | −0,611 | −0,564 | −0,501 |
| E-observable subspace | −0,364 | −0,230 | −0,124 | −0,124 | −0,103 |
| dispersion topologique | −0,287 | −0,139 | −0,076 | −0,105 | −0,126 |
| **B (critère FO)** | **−0,145** | **−0,166** | **−0,107** | **−0,072** | **−0,002** |
| **visibilité p05 (tie-break FO)** | **+0,130** | **+0,135** | +0,036 | +0,045 | +0,065 |
| centralité moyenne | −0,005 | +0,123 | +0,142 | +0,086 | +0,095 |

**2019** : l'endpoint a **exactement 1 valeur distincte** sur 1 000 designs (σ = 2,8·10⁻¹⁷).
Aucun critère ne peut y corréler.

**Conclusion.** L'explication est (a). Là où l'endpoint porte du signal, les critères OED le
suivent à ρ ≈ −0,5 à −0,65 et **B ne le suit pas** (ρ ≈ −0,1, décroissant vers 0 avec le
budget). Le tie-break primaire de FO a le **signe inverse** : meilleure visibilité au 5ᵉ
percentile ↔ *plus* de faux oubli.

**Donc : Track A a falsifié quelque chose de réel sur B. Track B n'a rien falsifié du tout.**

Nuance : sur la **distance de localisation** (endpoint continu), le tie-break p05 est le seul
critère de signe favorable et constant (ρ = −0,296 à k=4, −0,190 à k=6). La famille FO a du
signal pour la localisation, pas pour la détection.

### 5.2 Le plancher de FO tient à un seul événement

| budget | taux de faux oubli | événements manqués |
|---|---|---|
| k=4 | 0,143 | p232, p183 |
| k=6 … k=12 | 0,071 | **p232** |

**p232** : incipiente, ⌀ 0,0201 m, 2018-01-31 → 2018-02-10. À k=8, elle est détectée par
**9 des 10 baselines** ; seuls FO et `centralité` la manquent. Avec 14 événements, un seul
manque vaut 0,071. Base étroite, signalée comme telle.

### 5.3 Trois explications commodes écartées

**Les baselines ne sont pas truquées.** Audit formule par formule : aucune baseline n'est mal
implémentée d'une manière qui désavantage FO ; chaque défaut trouvé joue dans l'autre sens ou
est neutre.

Deux points matériels :

- **Les dix baselines ne sont pas dix designs.** Mesuré : 8 designs distincts sur 11 méthodes
  à k=6 et k=8, 9 à k=4 et k=12. D-bayésien, A-bayésien, E-observable et info-gain
  sélectionnent le **même** sous-ensemble (ce sont des transformations monotones l'une de
  l'autre dans le régime linéaire-gaussien). Il y a donc **7 à 8 baselines distinctes, pas 10**.
  Le groupe qui a battu FO est précisément celui qui s'effondre.
- **E-optimalité bayésienne littérale est dégénérée** ici : pour k < n, λ_min(HᵀH/σ² + I/τ²)
  = 1/τ² pour *tout* sous-ensemble. Une implémentation littérale aurait renvoyé une constante
  et classé tous les designs à égalité. Détecté, renommé `E_optimal_observable_subspace`,
  documenté.

**FO n'a pas perdu par sous-optimisation.** À k=4, énumération exhaustive des 40 920
sous-ensembles : écart glouton **0,0**, avec 203 sous-ensembles ex æquo à l'optimum. FO a
atteint l'optimum global de son propre critère et a perdu quand même.

**L'endpoint n'était pas saturé partout.** Track A avait de la variance (voir 5.1) ; c'est
Track B seul qui était saturé.

### 5.4 Le défaut de la métrique est directionnel, et il flatte

`E_κ` est recalculé à partir du σ qu'on passe à la métrique. Comme σ décrit les **conditions
de mesure**, la population que la métrique prétend décrire change silencieusement avec le
bruit : deux valeurs de B sous bruits différents sont des fractions de **dénominateurs
différents**.

`B*` gèle le support une fois, depuis la référence riche sous σ nominal d'entraînement.

Test unitaire sur tenseur synthétique, bruit d'évaluation de 0,25× à 8× nominal :

| bruit × | 0,25 | 0,5 | 1 | 2 | 4 | 8 |
|---|---|---|---|---|---|---|
| support de B | 281 | 238 | 199 | 165 | 120 | **70** |
| support de B\* | 199 | 199 | 199 | 199 | 199 | **199** |
| valeur de B | 0,036 | 0,042 | 0,035 | 0,103 | 0,092 | **0,257** |
| valeur de B\* | 0,000 | 0,000 | 0,035 | 0,256 | 0,452 | **0,739** |

Monter le bruit éjecte les scénarios discrets et difficiles hors de `E_κ`, ne laissant que les
bruyants et faciles : **B s'améliore pour une raison qui n'a rien à voir avec le réseau de
capteurs**. À 8× de bruit, B annonce 26 % d'aveuglement là où B\* en mesure 74 %.

*Note d'honnêteté* : ce test a **échoué** sur la première fixture, dont les amplitudes de
scénarios étaient tirées dans une plage trop étroite — le support dynamique ne bougeait jamais
et le test serait passé à vide. La fixture couvre maintenant trois décades. Consigné parce
qu'un test qui ne peut pas échouer n'est pas une preuve.

`B*` n'a servi à sélectionner **aucun** hyperparamètre sur **aucun** jeu de test.

### 5.5 Hors du régime contraint, B ne classe plus rien

FO-v1 sélectionne parmi les **33 capteurs préinstallés**, pas parmi les 782 jonctions. Une
bibliothèque de sensibilité toutes-jonctions (782 scénarios × 782 emplacements candidats) a
été construite pour adresser le problème complet :

| k | B, placement libre (782 candidats) | B, contraint aux 33 | recouvrement |
|---|---|---|---|
| 4 | **0,0000** | 0,0000 | 2/4 |
| 6 | **0,0000** | 0,0000 | 3/6 |
| 8 | **0,0000** | 0,0000 | 4/8 |
| 12 | **0,0000** | 0,0000 | 5/12 |

Dans le problème non contraint, **B sature à zéro dès k=4** : avec 782 emplacements on trouve
toujours 4 nœuds qui voient tous les scénarios éligibles au-dessus de 3σ. Le critère n'a alors
**aucun pouvoir de résolution**. Il n'est non trivial que dans le régime contraint des 33
capteurs, et même là son optimum vaut ~0,001, soit un scénario sur 770.

C'est une limite structurelle du critère, pas un artefact du benchmark.

### 5.6 Le seul résultat favorable à FO

Question différente de celle testée par FO-v1 : **le score FO prédit-il qu'un scénario donné
va échouer ?** C'est un usage diagnostique, pas de conception.

AUROC pour la prédiction d'échec de détection par scénario :

| année | prédicteur | AUROC | IC 95 % | prévalence d'échec |
|---|---|---|---|---|
| 2018 | **visibilité FO** | **0,821** | [0,768 – 0,868] | 0,055 |
| 2018 | marge d'isolabilité | 0,562 | [0,487 – 0,638] | |
| 2018 | SNR | 0,507 | [0,431 – 0,581] | |
| 2018 | plus petite valeur singulière | 0,314 | [0,230 – 0,405] | |
| 2019 | visibilité FO | 0,478 | [0,431 – 0,525] | 0,087 |
| 2019 | SNR | 0,771 | [0,736 – 0,805] | |

Sur 2018, **FO est un bon prédicteur d'échec et domine largement les diagnostics simples**.

**Pourquoi cela ne suffit pas :**

1. **2019 est dégénéré.** Ses deux événements en échec (p523, p827) échouent dans **55
   configurations de design sur 55**. L'issue est fixée par l'événement, pas par le réseau de
   capteurs. Aucun score dépendant du design n'y est évaluable, même en principe. Le 0,478 de
   FO n'est pas une preuve contre FO, et le 0,771 du SNR n'est pas une preuve pour lui.
2. **Le gradient par décile n'est pas monotone** sur 2018 : 0,00 0,00 0,03 0,00 0,00 0,01 0,01
   **0,22** 0,06 **0,21** — 78 % de pas non décroissants, là où la règle exige un gradient
   monotone clair.
3. **Le test hors échantillon requis** est la reproduction EPA, bloquée.

D'où `FO_DIAGNOSTIC_NOT_SUPPORTED` = **non démontré**.

*Hypothèse non prouvée* : FO capterait les échecs limités par la **visibilité** et pas ceux
limités par le **masquage**. En 2019, quatre fuites courent depuis le 1ᵉʳ janvier et masquent
les deux suivantes — phénomène temporel qu'un score de visibilité ne peut pas voir par
construction.

---

## 6. Phase 11 — reproduction EPA : bloquée

Objectif : reproduire Seth et al. 2016 (source inversion, Water Security Toolkit) pour fournir
le test externe manquant, puis calculer les diagnostics FO sur des données événementielles
validées.

### Le ZIP officiel n'est jamais arrivé

`Dataset_A-pg4z_TestSourceInversion_Haxton_20160728.zip` n'est pas présent. Le répertoire
d'upload de la session ne contient que trois fichiers `.md` (le prompt Phase 10 et deux copies
identiques du prompt Phase 11). Recherche effectuée dans le dépôt, `/home/user`, `/tmp` et le
chemin de dépôt annoncé : aucun fichier correspondant.

| tentative | résultat |
|---|---|
| `pasteur.epa.gov/uploads/149/…zip` (URL primaire) | `curl: (56) CONNECT tunnel failed, response 403` |
| `catalog.data.gov` + endpoint CKAN | `CONNECT 403` |
| `sciencehub.epa.gov`, `edg.epa.gov`, `www.epa.gov` | `CONNECT 403` |
| `doi.org` (le papier Seth et al. 2016) | `CONNECT 403` |
| miroir intégral vérifiable par SHA256 | aucun n'existe sur hôte atteignable |

### Second artefact obligatoire manquant

`REPRODUCTION_GATE_PROTOCOL.md`, déclaré obligatoire et définissant les critères de passage
des gates R0–R6, n'a jamais été fourni. Les définitions codées sont reconstruites à partir de
la consigne elle-même et **ne font pas autorité**.

(Même situation qu'en Phase 10 avec `PROTOCOLE_AUDIT_FORENSIQUE_BATTLEDIM.md`, également
jamais fourni.)

### Ce qui n'a pas été fait, délibérément

- **R1–R5 non implémentés.** Leurs entrées sont l'arborescence interne du ZIP, les paramètres
  expérimentaux du papier et la configuration WST — aucune inférable. Du code écrit contre une
  arborescence imaginée s'exécuterait et ne signifierait rien.
- **Phase FO non ouverte.** La consigne l'interdit tant que R1–R5 ne passent pas ; la barrière
  est appliquée en dur (`FO_phase = NOT_OPENED`).
- **Aucune simulation ad hoc substituée.** Les trois CSV de résultats sont livrés avec leur
  schéma et **zéro ligne**.
- Tout paramètre expérimental est marqué `UNRESOLVED_PARAMETER: specification unavailable`.

### Ce qui a avancé

- **Le Water Security Toolkit est récupéré** — seule partie exécutable de la consigne.
  `USEPA/Water-Security-Toolkit` @ `07f997cc`, 28 composants de source-inversion inventoriés
  (pilote `pywst/inversion`, modèles MIP/LP Pyomo et AMPL, moteur C++ Merlion). **Non compilé,
  non exécuté** faute de données — ce n'est donc pas une preuve qu'il soit praticable.
- **Le pipeline d'ingestion est complet et testé sur son chemin d'échec** : six emplacements
  cherchés, quatre URL tentées, SHA256, refus des archives corrompues et des chemins d'évasion
  *avant* extraction, déballage en lecture seule, inventaire hashé fichier par fichier.

### Pour débloquer

```bash
python3 run_phase11.py --zip /chemin/vers/Dataset_A-pg4z_TestSourceInversion_Haxton_20160728.zip
```

R0 s'exécutera réellement. R1–R5 resteront bloqués tant que manqueront aussi
`REPRODUCTION_GATE_PROTOCOL.md` et les paramètres du papier. Une fois R0 passé, l'inventaire du
ZIP dira précisément lesquels de ces éléments s'y trouvent déjà.

---

## 7. Ce qui rend ces résultats vérifiables

**Barrière anti-contamination, appliquée deux fois.** Par l'ordre des étapes (l'étape 2019
refuse de s'exécuter sans le protocole gelé et son empreinte sur disque), et par un garde
runtime qui patche `open` et `numpy.load` pour faire échouer toute lecture d'un artefact 2019
pendant le gel. Chronologie vérifiée depuis l'historique git :

| étape | commit | horodatage |
|---|---|---|
| gel corrigé | `b92b8e53` | 2026-08-13T14:36:35Z |
| résultats Track A + B | `6a16fce5` | 2026-08-13T14:45:23Z |

Les résultats 2019 sont committés **9 minutes après** le gel.

**Une correction de protocole, décidée avant que l'année de test n'existe.** Le premier gel
calibrait un seuil d'alarme absurde (h = 4094). Diagnostic : l'année d'entraînement n'est pas
sans fuite (une fuite court depuis le 8 janvier 2018), donc le modèle nominal est
systématiquement biaisé — sur l'année de contrôle sans fuite, le résidu standardisé vaut
+0,37σ en médiane et jusqu'à +2,45σ sur 6 des 33 capteurs. Un CUSUM de marge k diverge dès que
|moyenne| > k. Correction : soustraire un biais par capteur estimé sur l'année de contrôle sans
fuite. Seuil ramené à 359. Le protocole superseded est committé pour audit ; la régénération
2019 en était au chunk 24/25 quand le gel corrigé s'est terminé.

**Trois affirmations testées plutôt qu'assertées :**

- Le modèle de fuite EPANET (émetteur) reproduit `add_leak` de wntr à **4,6·10⁻⁷** d'écart
  relatif — la physique est identique à celle du benchmark.
- La simulation par tronçons résumables est **bit-identique** à l'implémentation de référence
  en un bloc : `max_abs_diff = 0,0` sur les cinq canaux publiés.
- Le glouton atteint l'optimum exhaustif à k=4 (écart 0,0 sur 40 920 sous-ensembles).

**Statistiques.** Bootstrap apparié par événement, 10 000 rééchantillonnages, graines fixes.

**Reproductibilité.** Une commande (`python3 run_full_validation.py`), 9 étapes, chacune sautée
si sa sortie existe. Versions épinglées. SHA256 de toutes les données et de tous les résultats.

---

## 8. Limites

- Le verdict est lié au **détecteur unique** imposé par le protocole. Correct pour la
  comparaison, mais un détecteur ou un espace de scénarios différent pourrait donner un autre
  résultat ; rien ici ne l'exclut.
- **14 événements en Track A, 23 en Track B** : intervalles de confiance larges, un seul
  événement les déplace.
- L'espace de scénarios est au niveau **jonction**, projeté vers les conduites en moyennant les
  signatures des extrémités, plutôt que simulé à mi-conduite.
- Recherche **gloutonne** au-delà de k=4 ; l'écart n'est mesuré qu'à k=4.
- Les corrélations de substitution portent sur 1 000 designs **aléatoires** par budget ; les
  designs optimisés vivent dans la queue de cette distribution et pourraient s'y comporter
  autrement.
- L'endpoint 2018 ne prend que **8 valeurs distinctes** ; les ρ sont estimés sur une échelle
  grossière.
- Les seuils de décision (réduction relative de 20 %, marge de rappel de 2 points, AUROC 0,70,
  monotonie des déciles) sont des **règles internes au projet**, pas des normes du domaine.
- Le SCADA publié n'ayant jamais été obtenu, aucun résultat ici ne porte littéralement sur
  « BattLeDIM tel que publié », mais sur une reconstruction dont la fidélité est établie
  au niveau des débits de fuite (§3).

---

## 9. Bilan

**FO perd sur ce pour quoi il a été conçu.** Comme critère de placement de capteurs, B n'est
pas seulement inférieur aux baselines OED : il est **quasi non corrélé à l'endpoint qu'il
prétend améliorer**, et son tie-break pousse dans la mauvaise direction pour la détection.
Hors du régime contraint, il sature à zéro et ne classe plus rien du tout.

La Phase 10 ne sauve pas FO-v1. Elle explique *pourquoi* il a échoué et écarte les
explications commodes : les baselines sont saines, FO a atteint l'optimum global de son propre
critère, et l'endpoint n'était pas saturé là où la falsification a eu lieu.

**Le seul résultat encourageant est ailleurs que là où FO a été conçu** : comme diagnostic par
scénario sur 2018, FO bat nettement les alternatives simples (AUROC 0,821 contre 0,562). Cela
mérite le test hors échantillon prévu — et ce test est précisément celui que le blocage réseau
empêche.

**Questions ouvertes :**

1. La reconstructibilité pure reste **entièrement non évaluée**.
2. La valeur diagnostique de FO reste **non démontrée hors échantillon**.
3. Le comportement de FO en placement libre (782 candidats) est **non testé sur endpoint
   réel** — on sait seulement que son critère y est dégénéré.
