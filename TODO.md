# Gene-Intel — Feature Roadmap & TODO

> This file is the single source of truth for planned work.
> Update checkboxes as features are completed.
> Each section maps to a Claude Code prompt session.

---

## Phase 1 — Data Foundation (current sprint)
- [x] 15-species GTF ingestion pipeline
- [x] Neo4j graph schema (Gene, Transcript, Exon, UTR, CDS, Domain)
- [x] CO_LOCATED_WITH edges (10kb neighbourhood)
- [x] Two-agent AI pipeline (Agent A: NL→Cypher, Agent C: explanation)
- [x] Sigma.js v3 WebGL graph frontend
- [x] FastAPI backend with 5 endpoints
- [x] Docker + Railway deployment
- [x] InterPro REST domain ingestion (Route 1)
- [x] UniProt REST domain ingestion (Route 2 — primary)
- [x] EMBL-EBI FTP bulk domain ingestion (Route 3 — production)
- [x] InterProScan domain ingestion (Route 4 — exotic species)
- [x] Species 16: Cow (Bos taurus, taxon 9913)
- [x] Species 17: King Cobra (Ophiophagus hannah, taxon 8665)
- [x] API connectivity test suite (scripts/test_api_connectivity.py)
- [x] Domain coverage report command

---

## Phase 2 — Cold Start Fix (next sprint)
- [ ] **Embedded demo dataset** — pre-processed SQLite/JSON snapshot for
      Human + Zebrafish + Cow (~5,000 genes with domains), bundled in repo.
      Zero-setup, works without Neo4j credentials.
      _Prompt: "Build an embedded demo dataset for Gene-Intel that works
      without Neo4j. Use SQLite with the same query interface."_

- [ ] **Graceful degradation** — never blank screen. If Neo4j is down,
      fall back to demo dataset automatically. Show data source banner.
      _Prompt: "Add graceful degradation to Gene-Intel: fall back to demo
      data when Neo4j is unavailable, show a status banner."_

- [ ] **Ensembl REST fallback** — for simple gene lookups, query Ensembl
      REST directly without requiring local GTF ingestion.
      _Prompt: "Add Ensembl REST API fallback for basic gene queries when
      Neo4j is not yet populated."_

---

## Phase 3 — UX Overhaul (ask Bee before starting)
- [ ] **Guided discovery mode** — replace blank search box with:
      - Species multi-select toggle bar (17 species pills)
      - Pathway category chips (Signalling, Metabolism, DNA repair, etc.)
      - Pre-built query templates organised by research intent
      - Progressive disclosure: show advanced NL input only after basics
      _Prompt: "Design and implement guided discovery mode for Gene-Intel
      as described in TODO.md Phase 3."_

- [ ] **Streaming responses** — Agent A and Agent C stream token-by-token
      using SSE (Server-Sent Events). User sees Cypher query building live,
      then explanation appearing word by word.
      _Prompt: "Add SSE streaming to the /api/search endpoint and update
      the React frontend to display streamed results progressively."_

- [ ] **Shareable graph URLs** — encode query + viewport state into URL.
      Decode on load and replay the query automatically.
      _Prompt: "Add shareable URL state to Gene-Intel: encode search query
      and Sigma.js viewport into URL params, decode on load."_

- [ ] **Locus diagram view** — for a selected gene, render an interactive
      track diagram showing Exon/UTR/CDS/Domain positions to scale.
      Use the existing /api/gene/{gene_id} endpoint.
      _Prompt: "Build a locus diagram component for Gene-Intel using D3 or
      SVG that shows gene structure to scale with domain overlays."_

- [ ] **Persona selector UI** — visible toggle in the search bar for
      Investor / Student / Researcher persona. Currently only in API params.
      _Prompt: "Add a persona toggle to the Gene-Intel search UI: three
      buttons (Investor/Student/Researcher) that set the persona param."_

---

## Phase 4 — Data Enrichment
- [ ] **UniProt live enrichment** — at query time, enrich Domain nodes with
      protein function, disease associations, and GO terms from UniProt REST.

- [ ] **STRING PPI edges** — pull protein-protein interaction scores from
      STRING DB and create PPI_INTERACTS_WITH edges in Neo4j.

- [ ] **KEGG pathway context** — overlay known KEGG pathways onto graph results.
      Show pathway names in Agent C explanation for Researcher persona.

- [ ] **Upload your own GTF** — let users upload a custom GTF/GFF3 and query
      it immediately against the existing graph.

---

## Phase 5 — Big Bets (discuss prioritisation)
- [ ] **Hosted SaaS version** — deploy with all 17 species pre-loaded.
      Users access at a URL with no setup required.

- [ ] **Jupyter notebook export** — export any query result as .ipynb with
      graph data pre-loaded as a NetworkX object.

- [ ] **Multi-agent comparison** — Agent A generates 3 Cypher variants for
      ambiguous queries, Agent C compares and explains differences.

- [ ] **Variant annotation layer** — map SNPs/mutations onto Gene + Exon nodes.
      Clinical researchers can ask which variants fall inside structural twins.

---

## Known Issues & Tech Debt
- [ ] BioMart API removed — replaced by 4-route domain strategy (Phase 1)
- [ ] Demo seed only loads 2 species — update to 3 after Phase 1 complete
- [ ] No test coverage for Sigma.js frontend components
- [ ] InterProScan route requires genome FASTA (large download) — document clearly
- [ ] King Cobra (taxon 8665) has lower domain coverage — mark in UI
- [ ] No retry logic in original GTF download scripts — add --retry flag

---

## Species Coverage Status

| # | Species | Taxon | GTF | Domains (UniProt) | Domains (InterPro) | InterProScan |
|---|---------|-------|-----|-------------------|--------------------|--------------|
| 1 | Human | 9606 | ✅ | ✅ | ✅ | — |
| 2 | Mouse | 10090 | ✅ | ✅ | ✅ | — |
| 3 | Zebrafish | 7955 | ✅ | ✅ | ✅ | — |
| 4 | Chicken | 9031 | ✅ | ✅ | ✅ | — |
| 5 | Octopus | 175781 | ✅ | ⚠️ low | ⚠️ low | 🔲 needs FASTA |
| 6 | Chimpanzee | 9598 | ✅ | ✅ | ✅ | — |
| 7 | Fruit fly | 7227 | ✅ | ✅ | ✅ | — |
| 8 | Roundworm | 6239 | ✅ | ✅ | ✅ | — |
| 9 | Arabidopsis | 3702 | ✅ | ✅ | ✅ | — |
| 10 | Rice | 4530 | ✅ | ✅ | ✅ | — |
| 11 | Moss | 3218 | ✅ | ⚠️ low | ⚠️ low | 🔲 needs FASTA |
| 12 | Green alga | 3055 | ✅ | ⚠️ low | ⚠️ low | 🔲 needs FASTA |
| 13 | Black mould | 162425 | ✅ | ⚠️ low | ⚠️ low | 🔲 needs FASTA |
| 14 | Yeast | 4932 | ✅ | ✅ | ✅ | — |
| 15 | E. coli | 511145 | ✅ | ✅ | ✅ | — |
| 16 | Cow | 9913 | 🔲 | 🔲 | 🔲 | — |
| 17 | King cobra | 8665 | 🔲 | 🔲 | 🔲 | 🔲 needs FASTA |

Legend: ✅ done · 🔲 todo · ⚠️ partial
