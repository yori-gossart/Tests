# FO-P11 — Protocole de reproduction EPA avant test FO

## Statut
Pré-enregistré après inspection du ZIP officiel et avant toute nouvelle optimisation FO.

## Constat sur le ZIP
Le ZIP EPA contient :
- trois réseaux EPANET (`EPANET_Net3.inp`, `Network2.inp`, `BWSN_Network_2.inp`);
- un classeur de résultats agrégés du papier Seth et al. (2016).

Il ne contient pas les mesures événementielles, les postérieurs par source, ni les fichiers de configuration WST
nécessaires pour calculer directement FO scénario par scénario.

## Règle absolue
Aucun résultat FO issu d'une reconstruction n'est accepté tant que la reproduction n'a pas retrouvé les
résultats publiés avec une précision prédéfinie.

## Gate R0 — intégrité
- conserver les quatre fichiers originaux inchangés;
- enregistrer SHA256;
- parser les trois réseaux et vérifier les nombres de nœuds;
- utiliser WST ou un moteur EPANET/WNTR validé.

## Gate R1 — Network size
Reproduire les trois cas de la feuille `Network Size`.
Condition d'acceptation :
- accuracy publiée reproduite à ±2 points;
- spécificité moyenne à ±3 points;
- ordre de grandeur du nombre de nœuds aussi ou plus probables que la vraie source cohérent.

## Gate R2 — Time horizon
Reproduire 1, 2, 4, 8, 16, 24 h sur le cas nominal.
Condition :
- plateau d'accuracy à 100 % à partir de 8 h pour les trois méthodes;
- RMSE sur les six valeurs d'accuracy <= 5 points;
- RMSE sur les six spécificités <= 5 points.

## Gate R3 — Measurement error
Reproduire la grille FPR x FNR = {0,.1,.2,.3,.4}².
Condition :
- direction d'effet correcte;
- RMSE des 25 cases <= 7 points pour accuracy et spécificité par méthode;
- reproduire l'asymétrie documentée entre méthodes.

## Gate R4 — Modeling error
Reproduire erreurs de demande {0,1,2,4,8,10,20}%.
Condition :
- Spearman entre erreur et performance de même signe que le dataset;
- RMSE <= 5 points sur accuracy et spécificité.

## Gate R5 — Sensor placement
Reproduire densités {2,4,6,10,20}% pour placement optimal et random.
Condition :
- accuracy=100% dans le régime publié;
- RMSE spécificité <= 6 points;
- random exécuté avec suffisamment de réplications pour retrouver les écarts-types publiés.

## Gate R6 — seulement après R1–R5
Exporter les données événementielles :
- source vraie;
- sources candidates;
- posterior / score par source;
- rang de la vraie source;
- mesures par capteur et temps;
- design de capteurs;
- conditions de bruit/modèle.

Puis calculer FO/B* sans modifier leurs définitions après consultation des endpoints.

## Endpoints corrects
Ne pas utiliser l'« accuracy » du papier comme top-1 : le fichier montre qu'elle peut valoir 100 % alors que
30 à 214 nœuds sont aussi ou plus vraisemblables que la vraie source.

Endpoints primaires :
- rang de la vraie source;
- reciprocal rank;
- taille de l'ensemble candidat;
- posterior de la vraie source;
- log-loss si posterior normalisé;
- distance réseau vraie source -> MAP;
- top-1 et top-k explicitement recalculés.

## Diagnostic FO
Tester FO comme prédicteur d'ambiguïté/échec :
- AUROC/AUPRC pour top-1 failure;
- Spearman avec log-loss, rang et taille candidat;
- calibration;
- taux d'échec par décile FO;
- comparaison entropie, marge top1-top2, SNR, plus petite valeur singulière/conditionnement si applicable.

## Règle d'arrêt
Si la reproduction ne franchit pas les Gates R1–R5, aucun verdict FO sur ce benchmark n'est autorisé.
