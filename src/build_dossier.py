import base64, pathlib

def b64(p):
    return base64.b64encode(pathlib.Path(p).read_bytes()).decode()

IMG = {
    "surrogate": b64("phase10_reset/figures/surrogate_correlation_2018.png"),
    "bstar": b64("phase10_reset/figures/b_vs_bstar_noise.png"),
    "auroc": b64("phase10_reset/figures/diagnostic_auroc.png"),
    "tracka": b64("figures/track_a_false_forgetting.png"),
}

HTML = """<title>Frontière d'Oubli — Dossier de Falsification</title>
<style>
  :root{
    color-scheme: light;
    --ground:#f4f6f7; --surface:#ffffff; --surface-2:#eceff1;
    --ink:#131a1f; --ink-2:#4d5964; --ink-3:#78848d;
    --rule:#d7dde1; --rule-strong:#b4bec5;
    --accent:#12557f; --accent-soft:#e3edf4;
    --neg:#9c3529; --neg-soft:#f6e6e3;
    --caution:#7d5a0b; --caution-soft:#f7efdc;
    --pos:#1c6141;
    --serif: "Iowan Old Style", "Palatino Linotype", Palatino, Georgia, "Times New Roman", serif;
    --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    --mono: ui-monospace, "SF Mono", SFMono-Regular, Menlo, Consolas, "Liberation Mono", monospace;
  }
  @media (prefers-color-scheme: dark){
    :root:not([data-theme="light"]){
      color-scheme: dark;
      --ground:#0e1418; --surface:#151d23; --surface-2:#1c262d;
      --ink:#e9eef1; --ink-2:#a3b0b9; --ink-3:#7d8a93;
      --rule:#26333b; --rule-strong:#3a4a54;
      --accent:#69a8d2; --accent-soft:#16303f;
      --neg:#dd7d6d; --neg-soft:#33201c;
      --caution:#d3a63f; --caution-soft:#2e2614;
      --pos:#6bbd93;
    }
  }
  :root[data-theme="dark"]{
    color-scheme: dark;
    --ground:#0e1418; --surface:#151d23; --surface-2:#1c262d;
    --ink:#e9eef1; --ink-2:#a3b0b9; --ink-3:#7d8a93;
    --rule:#26333b; --rule-strong:#3a4a54;
    --accent:#69a8d2; --accent-soft:#16303f;
    --neg:#dd7d6d; --neg-soft:#33201c;
    --caution:#d3a63f; --caution-soft:#2e2614;
    --pos:#6bbd93;
  }

  *{box-sizing:border-box;}
  body{
    margin:0; background:var(--ground); color:var(--ink);
    font-family:var(--sans); font-size:16px; line-height:1.65;
    -webkit-font-smoothing:antialiased;
  }
  .wrap{max-width:60rem; margin:0 auto; padding:clamp(1.5rem,4vw,4rem) clamp(1.1rem,4vw,2.5rem) 6rem;}
  .prose{max-width:38rem;}

  h1,h2,h3{font-family:var(--serif); font-weight:600; text-wrap:balance; margin:0;}
  h1{font-size:clamp(2rem,5vw,3.1rem); line-height:1.1; letter-spacing:-.015em;}
  h2{font-size:clamp(1.4rem,3vw,1.9rem); line-height:1.2; margin-top:.2em;}
  h3{font-size:1.12rem; line-height:1.3; color:var(--ink);}
  p{margin:0;}
  a{color:var(--accent);}

  .eyebrow{
    font-family:var(--mono); font-size:.72rem; letter-spacing:.14em;
    text-transform:uppercase; color:var(--ink-3);
  }
  .lede{font-size:1.12rem; color:var(--ink-2); max-width:38rem;}

  header.head{
    display:flex; flex-direction:column; gap:1.1rem;
    padding-bottom:2rem; border-bottom:2px solid var(--rule-strong);
  }
  .meta{
    display:flex; flex-wrap:wrap; gap:.4rem 1.5rem;
    font-family:var(--mono); font-size:.75rem; color:var(--ink-3);
  }

  section{display:flex; flex-direction:column; gap:1.15rem; padding-top:3.2rem;}
  .sec-head{display:flex; flex-direction:column; gap:.35rem;}

  /* verdict ledger */
  .ledger{display:flex; flex-direction:column; gap:0; border:1px solid var(--rule); border-radius:2px; overflow:hidden; background:var(--surface);}
  .ledger-row{
    display:grid; grid-template-columns:minmax(0,1fr) auto; gap:.6rem 1.2rem;
    align-items:baseline; padding:.85rem 1.1rem; border-bottom:1px solid var(--rule);
  }
  .ledger-row:last-child{border-bottom:none;}
  .ledger-row .what{display:flex; flex-direction:column; gap:.15rem;}
  .ledger-row .scope{font-family:var(--mono); font-size:.82rem; color:var(--ink);}
  .ledger-row .note{font-size:.85rem; color:var(--ink-2);}
  .verdict{
    font-family:var(--mono); font-size:.78rem; letter-spacing:.02em;
    padding:.25rem .6rem; border-radius:2px; white-space:nowrap;
    border:1px solid currentColor;
  }
  .v-neg{color:var(--neg); background:var(--neg-soft);}
  .v-caution{color:var(--caution); background:var(--caution-soft);}
  .v-none{color:var(--ink-2); background:var(--surface-2); border-color:var(--rule-strong);}

  /* tables */
  .tablewrap{overflow-x:auto; border:1px solid var(--rule); border-radius:2px; background:var(--surface);}
  table{border-collapse:collapse; width:100%; font-size:.86rem;}
  th,td{padding:.55rem .8rem; text-align:right; border-bottom:1px solid var(--rule); white-space:nowrap;}
  th:first-child,td:first-child{text-align:left; white-space:normal;}
  thead th{
    font-family:var(--mono); font-size:.7rem; letter-spacing:.08em; text-transform:uppercase;
    color:var(--ink-3); font-weight:500; border-bottom:1px solid var(--rule-strong);
  }
  tbody tr:last-child td{border-bottom:none;}
  td.num{font-family:var(--mono); font-variant-numeric:tabular-nums;}
  tr.hi td{background:var(--neg-soft);}
  tr.hi td:first-child{font-weight:600;}
  .strong{font-weight:600;}

  /* callouts */
  .call{
    border-left:3px solid var(--accent); background:var(--accent-soft);
    padding:.95rem 1.2rem; display:flex; flex-direction:column; gap:.5rem; border-radius:0 2px 2px 0;
  }
  .call.neg{border-left-color:var(--neg); background:var(--neg-soft);}
  .call .call-label{
    font-family:var(--mono); font-size:.7rem; letter-spacing:.12em;
    text-transform:uppercase; color:var(--ink-2);
  }

  figure{margin:0; display:flex; flex-direction:column; gap:.6rem;}
  figure img{width:100%; height:auto; display:block; border:1px solid var(--rule); border-radius:2px; background:#fcfcfb;}
  figcaption{font-size:.85rem; color:var(--ink-2); max-width:38rem;}

  code{font-family:var(--mono); font-size:.88em; background:var(--surface-2); padding:.08em .34em; border-radius:2px;}
  pre{
    font-family:var(--mono); font-size:.8rem; line-height:1.5; overflow-x:auto;
    background:var(--surface); border:1px solid var(--rule); border-radius:2px;
    padding:.9rem 1.1rem; margin:0; color:var(--ink-2);
  }
  ul{margin:0; padding-left:1.15rem; display:flex; flex-direction:column; gap:.45rem; max-width:38rem;}
  li::marker{color:var(--ink-3);}

  .tag{
    font-family:var(--mono); font-size:.68rem; letter-spacing:.06em; text-transform:uppercase;
    color:var(--ink-3); border:1px solid var(--rule-strong); padding:.1rem .38rem; border-radius:2px;
    white-space:nowrap;
  }
  .grid2{display:grid; grid-template-columns:repeat(auto-fit,minmax(15rem,1fr)); gap:1rem;}
  .card{background:var(--surface); border:1px solid var(--rule); border-radius:2px; padding:1rem 1.1rem; display:flex; flex-direction:column; gap:.4rem;}
  .card .k{font-family:var(--mono); font-size:1.45rem; font-variant-numeric:tabular-nums; color:var(--ink);}
  .card .l{font-size:.85rem; color:var(--ink-2);}
  hr{border:none; border-top:1px solid var(--rule); margin:0;}
  footer{margin-top:4rem; padding-top:1.5rem; border-top:2px solid var(--rule-strong); font-size:.85rem; color:var(--ink-2); display:flex; flex-direction:column; gap:.6rem;}
</style>

<div class="wrap">

<header class="head">
  <div class="eyebrow">Validation externe · BattLeDIM / L-Town · EPA source inversion</div>
  <h1>Frontière d'Oubli :<br>dossier de falsification</h1>
  <p class="lede">Trois campagnes successives ont testé le critère FO comme règle de placement de capteurs,
  puis audité pourquoi il échoue, puis tenté de le porter sur un jeu de données externe.
  Le critère perd, et l'audit explique la raison plutôt que de l'excuser.</p>
  <div class="meta">
    <span>FO-v1 · Phase 10 · Phase 11</span>
    <span>Protocole gelé <code>09b55304…</code></span>
    <span>Aucun optimiseur FO-v2 créé</span>
  </div>
</header>

<section>
  <div class="sec-head">
    <div class="eyebrow">Registre des verdicts</div>
    <h2>Où en est FO</h2>
  </div>
  <div class="ledger">
    <div class="ledger-row">
      <div class="what"><span class="scope">FO-v1 — placement de capteurs</span>
      <span class="note">Trois tracks indépendants, protocole pré-enregistré et gelé avant l'ouverture du test</span></div>
      <span class="verdict v-neg">NOT_SUPPORTED</span>
    </div>
    <div class="ledger-row">
      <div class="what"><span class="scope">FO_DIAGNOSTIC — prédiction d'échec</span>
      <span class="note">Signal réel sur 2018, sans confirmation hors échantillon exploitable</span></div>
      <span class="verdict v-caution">NOT_SUPPORTED</span>
    </div>
    <div class="ledger-row">
      <div class="what"><span class="scope">FO_RECONSTRUCTIBILITY</span>
      <span class="note">Jeu de données EPA jamais reçu ni téléchargeable</span></div>
      <span class="verdict v-none">NOT_EVALUATED</span>
    </div>
    <div class="ledger-row">
      <div class="what"><span class="scope">EPA_REPRODUCTION (Phase 11)</span>
      <span class="note">Non tentée faute de données — pas tentée-puis-divergente</span></div>
      <span class="verdict v-none">FAILED&nbsp;/&nbsp;NON&nbsp;TENTÉE</span>
    </div>
  </div>
  <div class="call">
    <span class="call-label">Lecture des verdicts négatifs</span>
    <p><span class="strong">NOT_SUPPORTED</span> sur le diagnostic signifie <em>non démontré</em>, pas réfuté.
    <span class="strong">NOT_EVALUATED</span> et <span class="strong">FAILED</span> en Phase 11 signalent une donnée
    absente, jamais un résultat négatif mesuré. Ces distinctions sont maintenues partout : une expérience
    non exécutée ne compte pas comme une expérience ratée.</p>
  </div>
</section>

<section>
  <div class="sec-head">
    <div class="eyebrow">Campagne 1 · FO-v1</div>
    <h2>FO perd sur ce pour quoi il a été conçu</h2>
  </div>
  <div class="prose" style="display:flex;flex-direction:column;gap:1rem;">
    <p>Le critère FO minimise <code>B</code>, le taux d'angle mort : la part des scénarios visibles par
    une référence riche que le sous-ensemble de capteurs ne voit pas. Il a été comparé à dix baselines
    d'optimal experimental design et topologiques, toutes passant par le <span class="strong">même détecteur</span>,
    sur des budgets k ∈ {4, 6, 8, 10, 12}.</p>
  </div>

  <div class="tablewrap">
    <table>
      <caption class="sr-only"></caption>
      <thead><tr><th>Taux de faux oubli — Track A, 14 événements</th><th>k=4</th><th>k=6</th><th>k=8</th><th>k=10</th><th>k=12</th></tr></thead>
      <tbody>
        <tr class="hi"><td>FO</td><td class="num">0,143</td><td class="num">0,071</td><td class="num">0,071</td><td class="num">0,071</td><td class="num">0,071</td></tr>
        <tr><td>Meilleure baseline OED</td><td class="num">0,000</td><td class="num">0,000</td><td class="num">0,000</td><td class="num">0,000</td><td class="num">0,000</td></tr>
        <tr><td>Aléatoire (moyenne de 100)</td><td class="num">0,144</td><td class="num">0,091</td><td class="num">0,061</td><td class="num">0,058</td><td class="num">0,043</td></tr>
      </tbody>
    </table>
  </div>
  <p class="prose">FO ne bat aucune baseline à aucun budget, et se situe <span class="strong">sous le placement
  aléatoire moyen</span> à k = 8, 10 et 12.</p>

  <figure>
    <img src="data:image/png;base64,__TRACKA__" alt="Taux de faux oubli par budget de capteurs, Track A : FO reste à 0,071 tandis que plusieurs baselines atteignent 0,000.">
    <figcaption>Track A — validation événementielle par exclusion successive des 14 fuites de 2018.
    Le protocole complet (modèle nominal, σ, seuil d'alarme, sélection de capteurs) est réappris sans
    l'événement évalué à chaque pli.</figcaption>
  </figure>

  <div class="call neg">
    <span class="call-label">Track B — plafond total</span>
    <p>Sur l'année 2019 reconstruite, <span class="strong">toutes les méthodes et tous les budgets rendent
    exactement 0,087</span>, en manquant les deux mêmes événements. Aucune discrimination n'existe.
    Ce track ne peut soutenir aucune conclusion, dans un sens ou dans l'autre.</p>
  </div>
</section>

<section>
  <div class="sec-head">
    <div class="eyebrow">Campagne 2 · Phase 10</div>
    <h2>Pourquoi il perd</h2>
  </div>
  <div class="prose"><p>Deux explications restaient ouvertes : soit <code>B</code> est un mauvais substitut,
  soit il est correct mais l'endpoint était saturé. On les sépare en corrélant <em>chaque</em> critère de
  conception à l'endpoint réalisé, sur 1 000 designs aléatoires par budget.</p></div>

  <figure>
    <img src="data:image/png;base64,__SURROGATE__" alt="Corrélations de Spearman entre critères de design et taux de faux oubli réalisé : les critères OED atteignent −0,5 à −0,65, B reste près de zéro, le tie-break FO est positif.">
    <figcaption>Sur 2018 — la seule année dont l'endpoint possède de la variance — les critères OED suivent
    le résultat réel à ρ ≈ −0,5 à −0,65. <span class="strong">B reste près de zéro et y décroît</span>. Sur 2019,
    l'endpoint ne prend qu'une seule valeur distincte sur 1 000 designs.</figcaption>
  </figure>

  <div class="grid2">
    <div class="card"><span class="k">ρ = −0,65</span><span class="l">Meilleur critère OED (D-optimal rank-reduced, k=8)</span></div>
    <div class="card"><span class="k">ρ = −0,11</span><span class="l">Critère B de FO au même budget</span></div>
    <div class="card"><span class="k">ρ = +0,13</span><span class="l">Tie-break FO (5<sup>e</sup> percentile) — signe inverse</span></div>
    <div class="card"><span class="k">1</span><span class="l">Valeur distincte de l'endpoint 2019 sur 1 000 designs</span></div>
  </div>

  <div class="call">
    <span class="call-label">Conclusion de l'audit</span>
    <p>L'explication est la première. Là où l'endpoint porte du signal, les critères OED le suivent et
    <span class="strong">B ne le suit pas</span> ; son tie-break primaire pousse même dans la mauvaise
    direction pour la détection. Track A a donc falsifié quelque chose de réel sur B ;
    <span class="strong">Track B n'a rien falsifié du tout</span>.</p>
  </div>

  <h3>Trois explications commodes écartées</h3>
  <ul>
    <li><span class="tag">baselines</span> Aucune baseline n'est mal implémentée d'une façon qui désavantage FO ;
    chaque défaut trouvé joue dans l'autre sens. Mesuré, il y a <span class="strong">7 à 8 designs distincts,
    pas 10</span> — quatre critères bayésiens sélectionnent le même sous-ensemble.</li>
    <li><span class="tag">optimisation</span> FO n'a pas perdu par recherche insuffisante : à k=4,
    l'énumération exhaustive des 40 920 sous-ensembles donne un écart glouton de <span class="strong">0,0</span>.
    Il a atteint l'optimum global de son propre critère et a perdu quand même.</li>
    <li><span class="tag">un seul événement</span> Tout le plancher de FO en Track A tient à
    <span class="strong">une seule fuite, p232</span>, détectée par 9 baselines sur 10. Base étroite,
    signalée comme telle.</li>
  </ul>

  <h3>Le défaut de la métrique est directionnel</h3>
  <div class="prose"><p>L'ensemble conditionnant de <code>B</code> est recalculé à partir du σ qu'on lui passe.
  Comme σ décrit les conditions de mesure, la population que la métrique prétend décrire change avec le bruit.
  <code>B*</code> gèle ce support une fois pour toutes.</p></div>

  <figure>
    <img src="data:image/png;base64,__BSTAR__" alt="À gauche, le dénominateur de B s'effondre de 281 à 70 quand le bruit augmente alors que celui de B* reste à 199 ; à droite, B sous-estime l'aveuglement.">
    <figcaption>Le biais flatte la métrique : monter le bruit éjecte les scénarios discrets et difficiles
    hors du dénominateur. À 8× de bruit, <span class="strong">B annonce 26 % d'aveuglement là où B* en mesure 74 %</span>.
    Prouvé par test unitaire sur tenseur synthétique.</figcaption>
  </figure>

  <h3>Et hors du régime contraint, B ne classe plus rien</h3>
  <div class="prose"><p>FO-v1 choisit parmi les 33 capteurs préinstallés de BattLeDIM. Sur le problème de
  placement complet — 782 emplacements candidats — <span class="strong">B sature à 0,0000 dès k = 4</span> :
  on trouve toujours quatre nœuds qui voient tous les scénarios éligibles. Un critère qui vaut zéro pour
  tout design raisonnable ne peut pas ordonner des designs.</p></div>
</section>

<section>
  <div class="sec-head">
    <div class="eyebrow">Le seul résultat favorable</div>
    <h2>FO comme diagnostic, pas comme règle de placement</h2>
  </div>
  <div class="prose"><p>Question différente de celle testée par FO-v1 : le score FO prédit-il qu'un
  scénario donné va échouer ? Sur 2018, oui, et nettement mieux que les diagnostics simples.</p></div>

  <figure>
    <img src="data:image/png;base64,__AUROC__" alt="AUROC de quatre prédicteurs d'échec : la visibilité FO atteint 0,82 sur 2018, loin devant les concurrents ; les barres 2019 sont estompées car cette année est dégénérée.">
    <figcaption>AUROC 0,821 (IC 95 % 0,768–0,868) contre 0,562 pour le meilleur concurrent.
    Les barres 2019 sont estompées à dessein : <span class="strong">ses deux échecs surviennent dans
    55 configurations de design sur 55</span>, donc aucun score dépendant du design n'y est évaluable.</figcaption>
  </figure>

  <div class="call">
    <span class="call-label">Pourquoi cela ne suffit pas</span>
    <p>La confirmation hors échantillon manque : la seule année disponible est dégénérée, et le gradient
    par décile sur 2018 n'est pas monotone (78 % de pas non décroissants). Le test qui trancherait est
    précisément celui que le blocage réseau empêche.</p>
  </div>
</section>

<section>
  <div class="sec-head">
    <div class="eyebrow">Campagne 3 · Phase 11</div>
    <h2>Le jeu de données EPA n'est jamais arrivé</h2>
  </div>
  <div class="prose"><p>La reproduction de Seth et al. 2016 devait fournir le test externe manquant.
  Le ZIP officiel n'est présent ni dans les fichiers déposés, ni téléchargeable.</p></div>

  <div class="tablewrap">
    <table>
      <thead><tr><th>Tentative</th><th>Résultat</th></tr></thead>
      <tbody>
        <tr><td>Fichiers déposés dans la session</td><td class="num">3 fichiers <code>.md</code>, aucun ZIP</td></tr>
        <tr><td><code>pasteur.epa.gov</code> (URL primaire)</td><td class="num">CONNECT 403</td></tr>
        <tr><td><code>catalog.data.gov</code></td><td class="num">CONNECT 403</td></tr>
        <tr><td><code>sciencehub.epa.gov</code>, <code>edg.epa.gov</code></td><td class="num">CONNECT 403</td></tr>
        <tr><td><code>doi.org</code> (le papier)</td><td class="num">CONNECT 403</td></tr>
        <tr><td>Miroir intégral vérifiable</td><td class="num">aucun</td></tr>
      </tbody>
    </table>
  </div>

  <div class="call neg">
    <span class="call-label">Ce qui n'a pas été fait, délibérément</span>
    <p>Les gates R1–R5 ne sont pas implémentés : leurs entrées sont l'arborescence du ZIP, les paramètres
    du papier et la configuration WST, aucune inférable. La phase FO n'est pas ouverte — la barrière est
    appliquée en dur dans le code. Les trois CSV de résultats sont livrés
    <span class="strong">schéma seul, zéro ligne</span>. Aucune simulation ad hoc n'a été substituée.</p>
  </div>

  <div class="prose"><p>Un second artefact obligatoire manque aussi : <code>REPRODUCTION_GATE_PROTOCOL.md</code>,
  qui définit les critères de passage. Les définitions codées sont reconstruites à partir de la consigne
  et ne font pas autorité.</p></div>

  <h3>Ce qui a tout de même avancé</h3>
  <ul>
    <li>Le <span class="strong">Water Security Toolkit est récupéré</span> (<code>USEPA/Water-Security-Toolkit</code> @ <code>07f997cc</code>),
    28 composants de source-inversion inventoriés. Non compilé, non exécuté — donc pas une preuve qu'il soit praticable ici.</li>
    <li>Le pipeline d'ingestion est complet et testé sur son chemin d'échec : SHA256, refus des archives
    corrompues et des chemins d'évasion avant extraction, déballage en lecture seule, inventaire hashé.</li>
  </ul>

  <pre># Pour débloquer, une fois le ZIP déposé :
python3 run_phase11.py --zip /chemin/vers/Dataset_A-pg4z_TestSourceInversion_Haxton_20160728.zip</pre>
</section>

<section>
  <div class="sec-head">
    <div class="eyebrow">Intégrité</div>
    <h2>Ce qui rend ces résultats vérifiables</h2>
  </div>
  <ul>
    <li><span class="tag">provenance</span> Les SCADA publiés de BattLeDIM sont inaccessibles (Zenodo et le site
    officiel bloqués). Les données sont régénérées avec le générateur, le modèle et le calendrier de fuites
    <em>officiels</em>, récupérés du dépôt des organisateurs.</li>
    <li><span class="tag">fidélité</span> Les débits de fuite régénérés reproduisent les
    <span class="strong">23 séries officielles à 4,05·10⁻⁵</span> d'écart relatif sur les moyennes — ce qui
    établit au passage que la répétition annuelle des demandes est une propriété du benchmark réel,
    pas de la reconstruction.</li>
    <li><span class="tag">barrière</span> Le gel est appliqué deux fois : par l'ordre des étapes, et par un
    garde runtime qui fait échouer toute lecture d'un artefact 2019 pendant le gel. Chronologie vérifiée
    depuis l'historique git, pas affirmée.</li>
    <li><span class="tag">correction</span> Le gel a été réémis une fois, avant que l'année de test n'existe,
    pour corriger un défaut de spécification du détecteur. Le protocole superseded est committé pour audit.</li>
    <li><span class="tag">tests</span> Le modèle de fuite EPANET est vérifié contre <code>add_leak</code> de wntr
    à 4,6·10⁻⁷ ; la simulation par tronçons est bit-identique à la référence ; le glouton atteint l'optimum
    exhaustif à k=4.</li>
  </ul>
</section>

<section>
  <div class="sec-head">
    <div class="eyebrow">Réserves</div>
    <h2>Ce que ce dossier ne dit pas</h2>
  </div>
  <ul>
    <li>Le verdict est lié au détecteur imposé par le protocole. Un détecteur ou un espace de scénarios
    différent pourrait donner un autre résultat ; rien ici ne l'exclut.</li>
    <li>Track A repose sur 14 événements et Track B sur 23 : les intervalles de confiance sont larges et
    un seul événement les déplace.</li>
    <li>La localisation n'atteint jamais le seuil de 300 m de BattLeDIM, pour aucune méthode. Le score
    économique officiel est donc peu discriminant, et il est rapporté séparément de la détection.</li>
    <li>La question de la reconstructibilité pure reste <span class="strong">entièrement ouverte</span>.</li>
    <li>Les seuils de décision (réduction relative de 20 %, marge de rappel de 2 points, AUROC 0,70)
    sont des règles internes au projet, pas des normes du domaine.</li>
  </ul>
</section>

<footer>
  <p><span class="strong">Si FO perd, le dire.</span> Comme critère de placement, B n'est pas seulement
  inférieur aux baselines OED : il est quasi non corrélé à l'endpoint qu'il prétend améliorer. La Phase 10
  ne sauve pas FO-v1 — elle explique son échec et écarte les excuses. Le seul signal encourageant est
  ailleurs que là où FO a été conçu, et le test qui le trancherait est bloqué.</p>
  <p style="color:var(--ink-3);">Rapports détaillés, données, protocoles gelés et sommes de contrôle :
  <code>FO_BATTLEDIM_EXTERNAL_VALIDATION_FINAL.md</code>, <code>phase10_reset/</code>, <code>phase11_epa/</code>.</p>
</footer>

</div>
"""

for k, v in IMG.items():
    HTML = HTML.replace("__" + {"surrogate":"SURROGATE","bstar":"BSTAR","auroc":"AUROC","tracka":"TRACKA"}[k] + "__", v)

out = pathlib.Path("FO_DOSSIER_FALSIFICATION.html")
out.write_text(HTML, encoding="utf-8")
print(f"wrote {out} — {out.stat().st_size/1024:.0f} KB")
