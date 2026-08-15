# Phase 12A — Dernière tentative d'acquisition LeakDB

```
LEAKDB_GATE0:       FAIL_FINAL_ACCESS
FO_TEST_AUTHORIZED: NO
```

Scénarios indépendants acquis lors de cette phase : **0**.
Total disponible localement : **10** (8 événements de fuite).
Cible minimale : 93. Cible préférable : 381.

FO n'a pas été testé. Aucune autre réparation LeakDB ne sera tentée.

---

## Route 1 — source SharePoint

L'URL fournie est bien celle que WaterBenchmarkHub référence : je l'ai retrouvée
à l'identique dans le registre du package, à `database.json → resources/kios-leakdb/download_url`.
L'information de départ était donc exacte.

| Sonde | Résultat |
|---|---|
| `GET` sur le dossier partagé | `CONNECT tunnel failed, response 403` |
| `GET` avec `&download=1` | `CONNECT tunnel failed, response 403` |
| `GET` sur `https://ucy-my.sharepoint.com/` | `CONNECT tunnel failed, response 403` |
| WebFetch (voie d'egress distincte) | `EGRESS_BLOCKED (ucy-my.sharepoint.com)` |

Le domaine entier est refusé, pas le lien de partage. Aucune variante d'URL ne
contournera cela.

---

## Route 2 — package `water-benchmark-hub`

**Le package s'installe et fonctionne.** `pypi.org` est sur la liste blanche du proxy,
donc l'installation a réussi et l'API se charge correctement :

```python
load("KIOS-LeakDB").load_data(scenarios_id=[1], use_net1=False)
```

L'appel a été réellement exécuté. Il échoue non pas dans le package mais au moment du
téléchargement, parce que **les données ne sont pas sur SharePoint** : le package les tire
d'un miroir pCloud.

```
requests.exceptions.ProxyError:
  HTTPSConnectionPool(host='filedn.com', port=443):
  .../EPyT-Flow/LeakDB-Original/Hanoi_CMH/Scenario-1.zip
  (Caused by ProxyError('Tunnel connection failed: 403 Forbidden'))
```

| Sonde | Résultat |
|---|---|
| `filedn.com/.../LeakDB-Original/Hanoi_CMH/` | 403 |
| `filedn.com/.../Hanoi_CMH/Scenario-1.zip` | 403 |
| `https://filedn.com/` | 403 |
| WebFetch sur le fichier scénario | `EGRESS_BLOCKED (filedn.com)` |

C'est donc un **troisième** hébergeur bloqué, après `zenodo.org` : le package ne contourne
pas l'obstacle, il le déplace.

---

## Route 3 — un sous-ensemble serait-il récupérable ?

**Oui, techniquement — et c'est la bonne nouvelle du dossier.** Le package ne télécharge
pas une archive monolithique. Il tire **un ZIP par scénario** :

```
https://filedn.com/.../EPyT-Flow/LeakDB-Original/Hanoi_CMH/Scenario-{id}.zip
```

avec 1 000 scénarios offerts, et les deux réseaux (`Hanoi_CMH`, `Net1_CMH`) séparés. On
pourrait donc demander Hanoi seul, ou exactement 93 ou 381 scénarios, sans toucher aux
~25 Go de l'archive complète.

**Ce n'est pas la granularité qui bloque, c'est l'hôte.** La distinction compte pour la
suite : le jour où `filedn.com` est autorisé, l'acquisition ciblée est immédiate et légère.

---

## Route 4 — décompte réel

| | |
|---|---|
| Nouveaux scénarios acquis en 12A | **0** |
| Disponibles localement (clone Git, Gate 0) | **10** |
| Événements de fuite | **8** |
| Cible minimale | 93 |
| Écart | **83 scénarios manquants** |

---

## Ce que je n'ai délibérément pas tenté

**Régénérer les scénarios.** Le dépôt embarque `Dataset_Generator_Py3`, et `epyt-flow` sait
synthétiser des scénarios de type LeakDB. Atteindre 93 scénarios par cette voie était à
portée technique immédiate.

Je ne l'ai pas fait, pour deux raisons qui vont dans le même sens :

1. un scénario régénéré n'est pas un scénario acquis — il ne fait pas partie du benchmark
   publié, donc un verdict FO obtenu dessus ne serait pas un verdict externe ;
2. c'est exactement le « remplacement synthétique d'un élément manquant » que la règle
   permanente interdit, et le brief de cette phase ne l'a pas listé parmi les tentatives
   autorisées.

Aucune autre chasse au miroir n'a été menée non plus : le brief restreignait cette phase à
la source SharePoint et au package.

---

## Verdict

```
LEAKDB_GATE0:       FAIL_FINAL_ACCESS
FO_TEST_AUTHORIZED: NO
```

Les trois hébergeurs officiels de LeakDB — `zenodo.org`, `ucy-my.sharepoint.com` et
`filedn.com` — sont refusés par le proxy d'egress. LeakDB reste admissible sur le fond :
le Gate 0 a établi que 14 critères sur 18 passent, que le code de scoring officiel
s'exécute, et que FO/B\* y serait calculable sans inventer de données. Seule l'acquisition
échoue, et elle échoue pour une raison entièrement extérieure au benchmark.

Deux gestes, et deux seulement, débloqueraient la situation :

1. **autoriser `filedn.com`** dans la politique réseau — c'est la voie la plus économique,
   puisque le téléchargement par scénario permet de ne prendre que 93 à 381 scénarios
   Hanoi au lieu des 25 Go ;
2. **déposer les scénarios dans la session**, comme le XLSX EPA en 11D.

Je n'entreprends rien de plus sur LeakDB sans instruction explicite.

---

## Fichiers produits

```
phase12_gate0/RAPPORT_PHASE12A_ACQUISITION.md          ce rapport
phase12_gate0/evidence/acquisition_attempt_12A.json    sondes et échec d'appel API horodatés
src/phase12a_acquisition_attempt.py                    tentative rejouable
```
