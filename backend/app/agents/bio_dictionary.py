"""
Bio-Dictionary: Natural Language Concepts → Cypher Fragment Mappings

This is Gene-Intel's semantic core. It bridges the gap between what users SAY
and what the graph CONTAINS.

ELI15: Think of this as the app's translation dictionary. If a user asks about
"cutting enzymes", this dictionary tells Agent A: "the user means genes with
Pfam domain PF00082 or genes whose name contains PCSK or FURIN".

How it connects to the rest of the app:
  - Consumed by: agent_a_semantic.py — injected into Claude's system prompt
  - Extended by: add new entries below to expand query vocabulary
  - Tested by: tests/test_agent_a.py — verifies Agent A uses dictionary concepts
"""

BIO_DICTIONARY = {

    # ── GENE SIZE & STRUCTURE ─────────────────────────────────────────────────

    "drug-like peptides": {
        "description": "Small secreted proteins in the range suitable for drug development",
        "cypher_where": "g.biotype = 'protein_coding' AND g.cds_length >= 150 AND g.cds_length <= 600",
        "example_nl": "Find drug-like peptides in zebrafish",
    },
    "large genes": {
        "description": "Genes with genomic span over 100kb — often complex, multi-domain",
        "cypher_where": "g.length > 100000",
        "example_nl": "Show me large genes in human",
    },
    "compact genes": {
        "description": "Genes with genomic span under 1kb — typical of bacteria and yeast",
        "cypher_where": "g.length < 1000",
        "example_nl": "List compact genes in E. coli",
    },
    "complex splicing": {
        "description": "Transcripts with high exon count, indicating alternative splicing",
        "cypher_where": "t.exon_count > 8",
        "cypher_match": "MATCH (g)-[:HAS_TRANSCRIPT]->(t:Transcript)",
        "example_nl": "Which Xenopus tropicalis genes show complex splicing?",
    },
    "minimal transcripts": {
        "description": "Single-exon genes — often retrotransposed pseudogenes or simple ORFs",
        "cypher_where": "t.exon_count = 1",
        "cypher_match": "MATCH (g)-[:HAS_TRANSCRIPT]->(t:Transcript)",
        "example_nl": "Find single-exon genes in yeast",
    },

    # ── UTR / REGULATORY STYLE ────────────────────────────────────────────────

    "regulatory style": {
        "description": "Comparison of UTR-to-CDS ratio as a proxy for post-transcriptional regulation",
        "cypher_where": "g.utr_cds_ratio IS NOT NULL",
        "example_nl": "Which genes have a regulatory style similar to insulin?",
    },
    "utr-heavy genes": {
        "description": "Genes where UTR length exceeds CDS — heavily regulated at mRNA level",
        "cypher_where": "g.utr_cds_ratio > 1.0",
        "example_nl": "Find UTR-heavy genes in Arabidopsis",
    },
    "minimal utr": {
        "description": "Genes with very short UTRs — common in bacteria and minimally regulated genes",
        "cypher_where": "g.utr5_length < 50 AND g.utr3_length < 100",
        "example_nl": "Show genes with minimal UTRs in E. coli",
    },

    # ── DOMAIN / FUNCTION CONCEPTS ────────────────────────────────────────────

    "cutting enzymes": {
        "description": "Proteases that cleave peptide bonds — includes subtilases, PCSK family",
        "cypher_match": "MATCH (g)-[:HAS_DOMAIN]->(d:Domain)",
        "cypher_where": "d.domain_id = 'Pfam:PF00082' OR g.name =~ '(?i).*(PCSK|FURIN|CASP).*'",
        "example_nl": "Find cutting enzymes near drug-like peptides in human",
    },
    "kinases": {
        "description": "Enzymes that phosphorylate substrates — critical in signalling cascades",
        "cypher_match": "MATCH (g)-[:HAS_DOMAIN]->(d:Domain)",
        "cypher_where": "d.domain_id IN ['Pfam:PF00069', 'Pfam:PF07714'] OR g.name =~ '(?i).*kinase.*'",
        "example_nl": "Show kinases conserved across human and zebrafish",
    },
    "transcription factors": {
        "description": "Proteins that bind DNA and regulate gene expression",
        "cypher_match": "MATCH (g)-[:HAS_DOMAIN]->(d:Domain)",
        "cypher_where": "d.domain_id IN ['Pfam:PF00096', 'Pfam:PF00447', 'Pfam:PF00010']",
        "example_nl": "List transcription factors in Arabidopsis with orthologs in moss",
    },
    "photosynthesis genes": {
        "description": "Genes encoding proteins involved in photosynthetic light reactions",
        "cypher_match": "MATCH (g)-[:HAS_DOMAIN]->(d:Domain)",
        "cypher_where": "d.domain_id IN ['Pfam:PF00016', 'Pfam:PF00051'] OR g.name =~ '(?i).*(PSB|PSA|RUB|RBCS).*'",
        "example_nl": "Compare photosynthesis genes between algae and moss",
    },
    "metabolic enzymes": {
        "description": "Enzymes in core metabolic pathways — glycolysis, TCA cycle, etc.",
        "cypher_match": "MATCH (g)-[:HAS_DOMAIN]->(d:Domain)",
        "cypher_where": "d.source = 'KEGG' OR g.biotype = 'protein_coding' AND g.name =~ '(?i).*(dehydrogenase|synthase|reductase).*'",
        "example_nl": "Find conserved metabolic enzymes between yeast and E. coli",
    },

    # ── SPATIAL / NEIGHBOURHOOD CONCEPTS ─────────────────────────────────────

    "functional team": {
        "description": "Genes that co-occur within 10kb — potentially co-regulated or in an operon",
        "cypher_match": "MATCH (g1:Gene)-[:CO_LOCATED_WITH]-(g2:Gene)",
        "example_nl": "Find the functional team around BRCA2 in human",
    },
    "tight neighbourhood": {
        "description": "Gene pairs within 2kb of each other — very likely co-regulated",
        "cypher_match": "MATCH (g1:Gene)-[r:CO_LOCATED_WITH]-(g2:Gene)",
        "cypher_where": "r.distance_bp < 2000",
        "example_nl": "Show tight neighbourhoods around protease genes in E. coli",
    },
    "conserved neighbourhood": {
        "description": "A gene and its neighbours that are structurally similar across species",
        "cypher_match": "MATCH (g1:Gene)-[:CO_LOCATED_WITH]-(n1:Gene), (g2:Gene)-[:CO_LOCATED_WITH]-(n2:Gene)",
        "cypher_where": "g1.species_taxon <> g2.species_taxon",
        "example_nl": "Which species has the most conserved neighbourhood for insulin?",
    },

    # ── GENE STATUS CONCEPTS ──────────────────────────────────────────────────

    "uncharacterized": {
        "description": "Genes with no functional annotation — potential novel discoveries",
        "cypher_where": "g.name =~ '(?i).*(uncharacterized|hypothetical|LOC[0-9]+|orf[0-9]+).*'",
        "example_nl": "Find uncharacterized genes near kinases in chimpanzee",
    },
    "pseudogenes": {
        "description": "Non-functional copies of genes — useful for evolutionary analysis",
        "cypher_where": "g.biotype = 'pseudogene' OR g.biotype = 'processed_pseudogene'",
        "example_nl": "Compare pseudogene density between human and chimpanzee",
    },
    "long non-coding rna": {
        "description": "lncRNA genes — regulatory role, often tissue-specific",
        "cypher_where": "g.biotype = 'lncRNA'",
        "example_nl": "Show lncRNA genes near transcription factors in human",
    },

    # ── CROSS-SPECIES CONCEPTS ────────────────────────────────────────────────

    "functional twins": {
        "description": "Genes in different species sharing domain composition and neighbourhood context",
        "cypher_match": """
            MATCH (g1:Gene)-[:HAS_DOMAIN]->(d:Domain)<-[:HAS_DOMAIN]-(g2:Gene)
            WHERE g1.species_taxon <> g2.species_taxon
        """,
        "example_nl": "Find functional twins of GLP-1 across all species",
    },
    "structural twins": {
        "description": "Genes with similar exon count and CDS length across species (no sequence alignment needed)",
        "cypher_where": "abs(g1.cds_length - g2.cds_length) < 100 AND abs(g1.exon_count - g2.exon_count) <= 2",
        "example_nl": "Find structural twins of insulin across plants and animals",
    },
}


# ── PROPERTY WHITELIST ──────────────────────────────────────────────────────
# Used by cypher_validator.py to reject hallucinated property names.

ALLOWED_NODE_LABELS = {"Species", "Gene", "Transcript", "Feature", "Domain"}

ALLOWED_RELATIONSHIP_TYPES = {
    "HAS_GENE", "HAS_TRANSCRIPT", "HAS_FEATURE", "HAS_DOMAIN", "CO_LOCATED_WITH"
}

# Gene properties with the type the loader stores for each
# (app/ingestion/feature_extractor.py). Agent A's prompt shows the types,
# because Neo4j never treats a string as equal to a number: the stored
# species_taxon '9606' does not match the integer 9606.
GENE_PROPERTY_TYPES = {
    "gene_id": "string",
    "name": "string",
    "biotype": "string",
    "chromosome": "string",       # '1', 'X', 'MT'
    "start": "integer",
    "end": "integer",
    "strand": "string",           # '+' or '-'
    "length": "integer",
    # cds_length to utr_cds_ratio describe the gene's canonical transcript
    "cds_length": "integer",
    "exon_count": "integer",
    "utr5_length": "integer",
    "utr3_length": "integer",
    "utr_cds_ratio": "float",
    "canonical_transcript_id": "string",
    "canonical_source": "string",  # 'Ensembl_canonical', 'longest_cds', 'longest_transcript'
    "species_taxon": "string",    # NCBI taxon ID, e.g. '9606'
}

ALLOWED_GENE_PROPERTIES = set(GENE_PROPERTY_TYPES)

ALLOWED_TRANSCRIPT_PROPERTIES = {
    "transcript_id", "type", "exon_count", "cds_length", "support_level", "is_canonical",
}

ALLOWED_DOMAIN_PROPERTIES = {"domain_id", "source", "description"}

ALLOWED_RELATIONSHIP_PROPERTIES = {"distance_bp"}


# ── SPECIES IN THE GRAPH ────────────────────────────────────────────────────
# Taxon ID to (common name, scientific name) for the 15 :Species nodes in the
# deployed graph (checked against /api/species on 2026-11-27). Taxon IDs are
# strings, in Species.taxon_id and Gene.species_taxon alike, because the
# loader's SPECIES_REGISTRY (app/ingestion/run_ingest.py) is keyed by string.
# The registry also lists cow (9913) and king cobra (8665), but neither has a
# GTF file, so neither is loaded.

LOADED_SPECIES = {
    "9606": ("Human", "Homo sapiens"),
    "10090": ("Mouse", "Mus musculus"),
    "7955": ("Zebrafish", "Danio rerio"),
    "9031": ("Chicken", "Gallus gallus"),
    "8364": ("Western clawed frog", "Xenopus tropicalis"),
    "9598": ("Chimpanzee", "Pan troglodytes"),
    "7227": ("Fruit fly", "Drosophila melanogaster"),
    "6239": ("Roundworm", "Caenorhabditis elegans"),
    "3702": ("Thale cress", "Arabidopsis thaliana"),
    "4530": ("Rice", "Oryza sativa"),
    "3218": ("Moss", "Physcomitrium patens"),
    "3055": ("Green alga", "Chlamydomonas reinhardtii"),
    "162425": ("Black mould", "Aspergillus niger"),
    "4932": ("Yeast", "Saccharomyces cerevisiae"),
    "511145": ("E. coli K-12", "Escherichia coli K-12"),
}
