"""
Tests for bio_dictionary.py: the property types and species list that Agent A's
prompt shows must match what the loader actually writes.
"""

from app.agents.bio_dictionary import GENE_PROPERTY_TYPES, LOADED_SPECIES
from app.ingestion.dialect_detector import detect_dialect
from app.ingestion.feature_extractor import extract_features
from app.ingestion.gtf_parser import parse_gtf_streaming
from app.ingestion.run_ingest import SPECIES_REGISTRY

PYTHON_TYPES = {"string": str, "integer": int, "float": float}


def test_loader_registry_keys_taxon_ids_as_digit_strings():
    # ingest_species() writes these keys as Species.taxon_id and Gene.species_taxon.
    for taxon_id in SPECIES_REGISTRY:
        assert isinstance(taxon_id, str) and taxon_id.isdigit(), taxon_id


def test_loaded_species_match_the_loader_registry():
    for taxon_id, (common_name, scientific_name) in LOADED_SPECIES.items():
        assert taxon_id in SPECIES_REGISTRY, taxon_id
        assert SPECIES_REGISTRY[taxon_id]["common_name"] == common_name
        assert SPECIES_REGISTRY[taxon_id]["name"] == scientific_name


def test_declared_gene_property_types_match_the_loader(sample_human_gtf):
    taxon_id = "9606"
    assert taxon_id in SPECIES_REGISTRY
    records = parse_gtf_streaming(sample_human_gtf, detect_dialect(sample_human_gtf))
    genes, _, _ = extract_features(records, taxon_id)

    assert genes
    seen = set()
    for gene in genes:
        assert set(gene) == set(GENE_PROPERTY_TYPES)
        for prop, value in gene.items():
            if value is None:  # utr_cds_ratio is unset for a gene without CDS
                continue
            assert type(value) is PYTHON_TYPES[GENE_PROPERTY_TYPES[prop]], prop
            seen.add(prop)
    assert seen == set(GENE_PROPERTY_TYPES)  # every declared type was checked once
