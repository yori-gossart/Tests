# RAPPORT PHASE 11 — REPRODUCTION EPA SOURCE-INVERSION

## Verdicts

| Portée | Verdict |
|---|---|
| `EPA_REPRODUCTION` | **EPA_REPRODUCTION_FAILED** |
| `FO_DIAGNOSTIC_EXTERNAL` | **NOT_EVALUATED** |
| `FO_RECONSTRUCTIBILITY_EXTERNAL` | **NOT_EVALUATED** |
| Optimiseur FO-v2 créé | **non** |

**`EPA_REPRODUCTION_FAILED` signifie ici NON TENTÉE, faute de données — pas
tentée-puis-divergente.** Aucune expérience n'a été exécutée, donc rien n'a été
comparé au XLSX officiel. La distinction est essentielle : ce verdict ne dit
rien sur la reproductibilité de Seth et al. 2016.

---

## Gate R0 — ÉCHEC : le ZIP n'est pas présent

Le prompt Phase 11 énonce « Tu disposes désormais du ZIP officiel ». **Ce n'est
pas le cas dans cet environnement.**

Le répertoire d'upload de la session ne contient que des `.md` :

```
d678be32-PROMPT_CLAUDE_CODE_PHASE10.md   5422 o
d74eb418-PROMPT_CLAUDE_CODE_PHASE11.md   2554 o
f3b58a5a-PROMPT_CLAUDE_CODE_PHASE11.md   2554 o   (copie identique)
```

Le prompt Phase 11 est arrivé **deux fois, à l'identique** ; le ZIP qui devait
l'accompagner n'est arrivé ni l'une ni l'autre fois.

Recherche effectuée : répertoire d'upload, dépôt, `/home/user`, `/tmp`,
`phase10_reset/data/epa_source_inversion/` (chemin de dépôt annoncé en Phase 10).
Aucun fichier `*pg4z*`, `*SourceInversion*`, `*Haxton*` ni archive
correspondante.

Nouvelle tentative de téléchargement, ce jour :

| cible | résultat |
|---|---|
| `pasteur.epa.gov/uploads/149/Dataset_A-pg4z_…zip` | `curl: (56) CONNECT tunnel failed, response 403` |
| `catalog.data.gov/api/3/action/package_show?id=A-pg4z-149` | `curl: (56) CONNECT tunnel failed, response 403` |

La politique de sortie réseau est inchangée depuis la Phase 10.

---

## Second artefact manquant : `REPRODUCTION_GATE_PROTOCOL.md`

Le point 2 du prompt le déclare **obligatoire** et fonde les Gates R0–R6 sur
lui. Il n'a jamais été fourni — même situation que
`PROTOCOLE_AUDIT_FORENSIQUE_BATTLEDIM.md` en Phase 10.

Les définitions de gates codées dans `run_phase11.py` sont **reconstruites à
partir des points 6 et 7 du prompt** et ne font pas autorité. Les critères de
succès (tolérances de comparaison au XLSX officiel, seuils de passage) sont
inconnus.

---

## Ce que je n'ai pas fait, et pourquoi

**Je n'ai pas implémenté R1–R5.** Leurs entrées sont la structure interne du
ZIP, les paramètres expérimentaux de Seth et al. 2016 et la configuration WST —
aucune n'est inférable sans les artefacts. Écrire du code contre une
arborescence imaginée produirait quelque chose qui s'exécute et ne signifie
rien.

**Je n'ai pas ouvert la phase FO.** Le point 8 l'interdit tant que R1–R5 ne
passent pas. `run_phase11.py` applique cette barrière en dur : la phase FO est
`NOT_OPENED`.

**Je n'ai substitué aucune simulation ad hoc**, conformément au point 47 du
prompt. `EVENT_LEVEL_SOURCE_INVERSION.csv`, `FO_DIAGNOSTIC_EXTERNAL.csv` et
`REPRODUCTION_SCORECARD.csv` sont livrés **avec leur schéma et zéro ligne**.

Le papier Seth et al. 2016 est également inaccessible : `doi.org` est refusé
(`CONNECT 403`).

---

## Ce qui a pu être fait

**Le Water Security Toolkit est récupéré** — c'est la seule partie du point 3
réalisable. `USEPA/Water-Security-Toolkit` @ `07f997cc`, clone superficiel de
313 Mo. 28 composants de source-inversion inventoriés
(`phase11_epa/WST_MANIFEST.json`), dont :

- `packages/pywst/pywst/inversion/` — pilote Python
- `models/pyomo/inversion_MIP.py`, `inversion_MIP_nd.py` — formulations MIP
- `models/ampl/inversion_MIP.mod`, `inversion_LP.mod` — modèles AMPL
- `packages/sim/merlion/applications/source_inversion/` — moteur C++ Merlion

**[limite]** Non compilé, non exécuté. Merlion exige une chaîne C++ complète et
les modèles Pyomo/AMPL un solveur ; rien n'a été tenté puisqu'il n'y a aucune
donnée sur laquelle tourner. Ce n'est donc **pas** une validation que WST est
praticable ici — seulement que le code est disponible.

**Le pipeline d'ingestion est prêt et testé sur son chemin d'échec.**
`run_phase11.py` :

- cherche le ZIP dans six emplacements, puis tente les quatre URL EPA ;
- calcule le SHA256, refuse les archives corrompues et les chemins d'évasion
  (`..`, chemins absolus) **avant** toute extraction ;
- déballe dans `phase11_epa/raw/` et passe l'arborescence en lecture seule ;
- inventorie chaque fichier avec sa taille et son SHA256.

Dès que le ZIP est déposé — n'importe où dans les chemins cherchés, ou via
`--zip <chemin>` — R0 passe sans autre modification.

---

## Pour débloquer

Déposer `Dataset_A-pg4z_TestSourceInversion_Haxton_20160728.zip` puis :

```bash
python3 run_phase11.py --zip /chemin/vers/le.zip
```

R0 s'exécutera réellement (hash, extraction, inventaire). R1–R5 resteront
`NOT_RUN` tant que manqueront **aussi** :

1. `REPRODUCTION_GATE_PROTOCOL.md` — les critères de passage ;
2. les paramètres expérimentaux de Seth et al. 2016 — inaccessibles via DOI ;
3. le XLSX officiel de référence — présumé *dans* le ZIP, à confirmer à
   l'ingestion.

Une fois R0 passé je pourrai inventorier le ZIP et dire précisément lesquels de
ces trois manquent encore, plutôt que de le supposer.

---

## Paramètres non résolus

Tout paramètre expérimental est actuellement
`UNRESOLVED_PARAMETER: specification unavailable`. Aucun n'a été fixé, et aucun
ne le sera pour améliorer FO — le point 5 l'interdit et rien dans cette phase
n'a produit de nombre susceptible d'être flatté.

## Statut des phases précédentes

Inchangé. FO-v1 reste **NOT_SUPPORTED** ; la Phase 10 reste
`FO_DIAGNOSTIC_NOT_SUPPORTED` et `NOT_EVALUATED_DATASET_UNAVAILABLE`. Rien ici
ne les modifie.
