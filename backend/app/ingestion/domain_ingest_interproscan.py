"""
InterProScan domain ingestion — Route 4 for non-model organisms.

Translates CDS coordinates from GTF into protein sequences, then submits to
InterProScan web service for domain annotation. Used for species with sparse
UniProt/InterPro coverage (Octopus, Moss, Green alga, Black mould, King Cobra).

Flow:
  1. CDSTranslator: GTF + genome FASTA → protein sequences
  2. InterProScanClient: async submit → poll → retrieve domain results
  3. load results into Neo4j (same Domain schema as UniProt route)

Requirements:
  - genome FASTA file at data/genomes/{taxon_id}.fa.gz
  - INTERPROSCAN_EMAIL or CONTACT_EMAIL env var
  - pip install aiohttp tqdm biopython
"""

from __future__ import annotations

import asyncio
import gzip
import json
import logging
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_IPRSCAN_BASE = "https://www.ebi.ac.uk/Tools/services/rest/iprscan5"
_MAX_CONCURRENT = int(os.getenv("DOMAIN_INGEST_MAX_WORKERS", "4"))
_CACHE_DIR = Path("data/interproscan_cache")
_MIN_PROTEIN_LENGTH = 50  # aa

# Optional imports — gracefully degrade if not installed
try:
    import aiohttp
    _HAS_AIOHTTP = True
except ImportError:
    _HAS_AIOHTTP = False
    logger.warning("aiohttp not installed — InterProScan async client unavailable")

try:
    import importlib.util as _ilu
    _HAS_BIOPYTHON = _ilu.find_spec("Bio") is not None
except Exception:
    _HAS_BIOPYTHON = False
if not _HAS_BIOPYTHON:
    logger.warning("biopython not installed — CDSTranslator unavailable")

try:
    from tqdm import tqdm as _tqdm
    _HAS_TQDM = True
except ImportError:
    _HAS_TQDM = False


def _tqdm_wrap(iterable, **kwargs):
    if _HAS_TQDM:
        return _tqdm(iterable, **kwargs)
    return iterable


# ─────────────────────────────────────────────────────────────────────────────
# Standard genetic code (codon → amino acid)
# ─────────────────────────────────────────────────────────────────────────────

_CODON_TABLE = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}


def _reverse_complement(seq: str) -> str:
    complement = {"A": "T", "T": "A", "G": "C", "C": "G", "N": "N"}
    return "".join(complement.get(b.upper(), "N") for b in reversed(seq))


def _translate(nuc_seq: str) -> str:
    """Translate nucleotide sequence to protein, stopping at first stop codon."""
    aa = []
    for i in range(0, len(nuc_seq) - 2, 3):
        codon = nuc_seq[i:i + 3].upper()
        aa_char = _CODON_TABLE.get(codon, "X")
        if aa_char == "*":
            break
        aa.append(aa_char)
    return "".join(aa)


# ─────────────────────────────────────────────────────────────────────────────
# CDSTranslator
# ─────────────────────────────────────────────────────────────────────────────

class CDSTranslator:
    """
    Extracts and translates CDS features from a parsed GTF for one species.

    Requires genome FASTA at genome_fasta_path. If None, all sequences are
    marked unavailable and skipped.
    """

    def __init__(self, gtf_path: str, genome_fasta_path: str | None = None):
        self.gtf_path = gtf_path
        self.genome_fasta_path = genome_fasta_path
        self._genome: dict[str, str] = {}  # chr → sequence
        self._stats = {
            "total_genes_in_gtf": 0,
            "genes_with_complete_cds": 0,
            "genes_with_protein_ge_50aa": 0,
            "genes_skipped_stop_codon_issues": 0,
        }

    def _load_genome(self) -> bool:
        """Load genome FASTA into memory. Returns False if unavailable."""
        if not self.genome_fasta_path or not os.path.exists(self.genome_fasta_path):
            return False

        logger.info("Loading genome FASTA: %s", self.genome_fasta_path)
        opener = gzip.open if self.genome_fasta_path.endswith(".gz") else open
        with opener(self.genome_fasta_path, "rt", encoding="utf-8") as f:
            current_chr = None
            seq_parts = []
            for line in f:
                line = line.rstrip()
                if line.startswith(">"):
                    if current_chr:
                        self._genome[current_chr] = "".join(seq_parts)
                    # Parse chromosome name (first word after >)
                    current_chr = line[1:].split()[0]
                    seq_parts = []
                else:
                    seq_parts.append(line)
            if current_chr:
                self._genome[current_chr] = "".join(seq_parts)

        logger.info("Loaded %d chromosomes/scaffolds", len(self._genome))
        return True

    def _parse_cds_features(self) -> dict[str, list[dict]]:
        """
        Parse GTF and collect CDS features per gene.
        Returns {gene_id: [{"chr", "start", "end", "strand", "phase"}, ...]}
        """
        import gzip as _gzip

        gene_cds: dict[str, list[dict]] = defaultdict(list)
        gene_strands: dict[str, str] = {}

        opener = _gzip.open if self.gtf_path.endswith(".gz") else open
        with opener(self.gtf_path, "rt", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#"):
                    continue
                parts = line.rstrip().split("\t")
                if len(parts) < 9:
                    continue
                feature_type = parts[2]
                if feature_type not in ("CDS", "gene"):
                    continue

                chrom = parts[0]
                start = int(parts[3])  # 1-based
                end = int(parts[4])
                strand = parts[6]
                attrs_str = parts[8]

                # Parse gene_id
                gene_id = None
                for token in attrs_str.split(";"):
                    token = token.strip()
                    if token.startswith("gene_id"):
                        gene_id = token.split('"')[1] if '"' in token else token.split("=")[-1]
                        break

                if not gene_id:
                    continue

                if feature_type == "gene":
                    self._stats["total_genes_in_gtf"] += 1
                    gene_strands[gene_id] = strand

                elif feature_type == "CDS":
                    phase = int(parts[7]) if parts[7].isdigit() else 0
                    gene_cds[gene_id].append({
                        "chr": chrom,
                        "start": start,
                        "end": end,
                        "strand": strand,
                        "phase": phase,
                    })

        return gene_cds, gene_strands

    def get_protein_sequences(self, min_length: int = 50) -> dict[str, str]:
        """
        Returns {gene_id: amino_acid_sequence} for all genes with
        complete CDS and translated protein >= min_length aa.
        """
        if not self._load_genome():
            logger.warning("Genome FASTA not available — no proteins to translate")
            return {}

        gene_cds, gene_strands = self._parse_cds_features()
        proteins: dict[str, str] = {}

        for gene_id, cds_list in gene_cds.items():
            if not cds_list:
                continue

            strand = gene_strands.get(gene_id, cds_list[0]["strand"])

            # Sort CDS fragments: forward strand by start, reverse by end (descending)
            if strand == "+":
                cds_sorted = sorted(cds_list, key=lambda x: x["start"])
            else:
                cds_sorted = sorted(cds_list, key=lambda x: x["end"], reverse=True)

            # Concatenate CDS nucleotides
            nuc_seq_parts = []
            ok = True
            for seg in cds_sorted:
                chrom = seg["chr"]
                if chrom not in self._genome:
                    ok = False
                    break
                chrom_seq = self._genome[chrom]
                # Convert to 0-based
                seg_seq = chrom_seq[seg["start"] - 1: seg["end"]]
                nuc_seq_parts.append(seg_seq)

            if not ok:
                continue

            self._stats["genes_with_complete_cds"] += 1
            nuc_seq = "".join(nuc_seq_parts)

            # Reverse complement for minus strand
            if strand == "-":
                nuc_seq = _reverse_complement(nuc_seq)

            # Translate
            try:
                aa_seq = _translate(nuc_seq)
            except Exception:
                self._stats["genes_skipped_stop_codon_issues"] += 1
                continue

            if len(aa_seq) >= min_length:
                self._stats["genes_with_protein_ge_50aa"] += 1
                proteins[gene_id] = aa_seq

        logger.info(
            "CDSTranslator stats: total_genes=%d, complete_cds=%d, "
            "protein_ge_%daa=%d, skipped_stop_issues=%d",
            self._stats["total_genes_in_gtf"],
            self._stats["genes_with_complete_cds"],
            min_length,
            self._stats["genes_with_protein_ge_50aa"],
            self._stats["genes_skipped_stop_codon_issues"],
        )
        return proteins


# ─────────────────────────────────────────────────────────────────────────────
# InterProScanClient
# ─────────────────────────────────────────────────────────────────────────────

class InterProScanClient:
    """
    Async client for the InterProScan 5 REST web service.

    Usage:
        client = InterProScanClient(email="you@example.com")
        results = asyncio.run(client.run_batch(gene_protein_map))
    """

    BASE_URL = _IPRSCAN_BASE
    MAX_CONCURRENT = _MAX_CONCURRENT

    def __init__(self, email: str | None = None, max_concurrent: int | None = None):
        self.email = (
            email
            or os.getenv("INTERPROSCAN_EMAIL")
            or os.getenv("CONTACT_EMAIL")
        )
        if not self.email:
            raise ValueError(
                "InterProScan requires an email address. "
                "Set INTERPROSCAN_EMAIL or CONTACT_EMAIL env var."
            )
        self.max_concurrent = max_concurrent or self.MAX_CONCURRENT
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ── Submission ──────────────────────────────────────────────────────────

    async def submit_sequence(
        self,
        gene_id: str,
        aa_sequence: str,
        session: "aiohttp.ClientSession",
    ) -> str:
        """POST one protein sequence to InterProScan. Returns job_id."""
        url = f"{self.BASE_URL}/run"
        data = {
            "email": self.email,
            "title": f"gene_intel__{gene_id}",
            "sequence": aa_sequence,
            "goterms": "false",
            "pathways": "false",
            "applications": "Pfam,CDD,SMART",
        }

        for attempt in range(2):
            async with session.post(url, data=data) as resp:
                if resp.status == 429:
                    logger.warning("InterProScan 429 — waiting 60s…")
                    await asyncio.sleep(60)
                    continue
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(
                        f"InterProScan submit failed for {gene_id}: "
                        f"HTTP {resp.status}: {text[:200]}"
                    )
                job_id = (await resp.text()).strip()
                return job_id

        raise RuntimeError(f"InterProScan submit failed for {gene_id} after retries")

    # ── Polling ─────────────────────────────────────────────────────────────

    async def poll_job(
        self,
        job_id: str,
        session: "aiohttp.ClientSession",
        timeout_sec: int = 1200,
    ) -> str:
        """
        Poll /status/{job_id} every 30s until FINISHED or ERROR.
        Raises TimeoutError if timeout_sec exceeded.
        """
        url = f"{self.BASE_URL}/status/{job_id}"
        start = time.monotonic()

        while True:
            elapsed = time.monotonic() - start
            if elapsed > timeout_sec:
                raise TimeoutError(f"InterProScan job {job_id} timed out after {timeout_sec}s")

            async with session.get(url) as resp:
                if resp.status != 200:
                    await asyncio.sleep(30)
                    continue
                status = (await resp.text()).strip()

            if status in ("FINISHED", "ERROR", "FAILURE", "NOT_FOUND"):
                return status

            await asyncio.sleep(30)

    # ── Retrieve results ────────────────────────────────────────────────────

    async def get_results(
        self,
        job_id: str,
        session: "aiohttp.ClientSession",
    ) -> list[dict[str, Any]]:
        """GET /result/{job_id}/json and parse domain matches."""
        url = f"{self.BASE_URL}/result/{job_id}/json"
        async with session.get(url) as resp:
            if resp.status != 200:
                logger.warning("Could not retrieve results for job %s: HTTP %d", job_id, resp.status)
                return []
            data = await resp.json(content_type=None)

        domains = []
        try:
            for seq_result in data.get("results", []):
                for match in seq_result.get("matches", []):
                    sig = match.get("signature", {})
                    sig_acc = sig.get("accession", "")
                    sig_name = sig.get("name", "")

                    for loc in match.get("locations", []):
                        start = loc.get("start")
                        end = loc.get("end")
                        score = loc.get("score")
                        domains.append({
                            "pfam_acc":    sig_acc,
                            "domain_name": sig_name,
                            "start_aa":    int(start) if start else None,
                            "end_aa":      int(end) if end else None,
                            "e_value":     score,
                            "source_db":   "interproscan",
                        })
        except (KeyError, TypeError) as exc:
            logger.warning("Error parsing InterProScan results for %s: %s", job_id, exc)

        return domains

    # ── Batch orchestration ─────────────────────────────────────────────────

    def _cache_path(self, taxon_id: int, gene_id: str) -> Path:
        return _CACHE_DIR / f"{taxon_id}_{gene_id}.json"

    def _load_from_cache(self, taxon_id: int, gene_id: str) -> list[dict] | None:
        path = self._cache_path(taxon_id, gene_id)
        if path.exists():
            try:
                with path.open() as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return None
        return None

    def _save_to_cache(self, taxon_id: int, gene_id: str, domains: list[dict]):
        path = self._cache_path(taxon_id, gene_id)
        try:
            with path.open("w") as f:
                json.dump(domains, f)
        except OSError as exc:
            logger.warning("Could not write cache for %s: %s", gene_id, exc)

    async def run_batch(
        self,
        gene_protein_map: dict[str, str],
        taxon_id: int = 0,
    ) -> dict[str, list[dict]]:
        """
        Submit, poll, and retrieve results for all genes concurrently.

        Args:
            gene_protein_map: {gene_id: aa_sequence}
            taxon_id: used for cache file naming

        Returns:
            {gene_id: [domain_dict, ...]}
        """
        if not _HAS_AIOHTTP:
            logger.error("aiohttp not installed — cannot run InterProScan batch")
            return {}

        results: dict[str, list[dict]] = {}
        to_submit: dict[str, str] = {}

        # Check cache first
        for gene_id, aa_seq in gene_protein_map.items():
            cached = self._load_from_cache(taxon_id, gene_id)
            if cached is not None:
                results[gene_id] = cached
            else:
                to_submit[gene_id] = aa_seq

        logger.info(
            "InterProScan batch: %d total, %d from cache, %d to submit",
            len(gene_protein_map), len(results), len(to_submit),
        )

        if not to_submit:
            return results

        sem = asyncio.Semaphore(self.max_concurrent)
        done_count = 0
        total = len(to_submit)

        async def process_one(gene_id: str, aa_seq: str, session) -> None:
            nonlocal done_count
            async with sem:
                try:
                    job_id = await self.submit_sequence(gene_id, aa_seq, session)
                    status = await self.poll_job(job_id, session)
                    if status == "FINISHED":
                        domains = await self.get_results(job_id, session)
                    else:
                        logger.warning("Job %s for %s ended with status: %s", job_id, gene_id, status)
                        domains = []
                    results[gene_id] = domains
                    self._save_to_cache(taxon_id, gene_id, domains)
                except Exception as exc:
                    logger.error("InterProScan failed for %s: %s", gene_id, exc)
                    results[gene_id] = []
                finally:
                    done_count += 1
                    if done_count % 10 == 0 or done_count == total:
                        logger.info("InterProScan: %d/%d genes processed", done_count, total)

        async with aiohttp.ClientSession() as session:
            tasks = [
                process_one(gene_id, aa_seq, session)
                for gene_id, aa_seq in to_submit.items()
            ]
            await asyncio.gather(*tasks)

        return results


# ─────────────────────────────────────────────────────────────────────────────
# run_interproscan_ingest
# ─────────────────────────────────────────────────────────────────────────────

def run_interproscan_ingest(
    taxon_id: int,
    driver,
    gtf_path: str,
    fasta_path: str | None = None,
) -> dict[str, Any]:
    """
    Main entry point for InterProScan domain ingestion for one species.

    1. Check FASTA availability.
    2. Translate CDS using CDSTranslator.
    3. Run InterProScanClient.run_batch().
    4. Load results into Neo4j.
    5. Return stats dict.
    """
    if not fasta_path:
        fasta_path = str(Path("data/genomes") / f"{taxon_id}.fa.gz")

    if not os.path.exists(fasta_path):
        logger.warning(
            "InterProScan skipped for taxon %d: no genome FASTA. "
            "Download with: bash scripts/download_genome_fasta.sh %d",
            taxon_id, taxon_id,
        )
        return {"taxon_id": taxon_id, "skipped": True, "reason": "no_fasta"}

    translator = CDSTranslator(gtf_path, fasta_path)
    proteins = translator.get_protein_sequences(min_length=_MIN_PROTEIN_LENGTH)

    if not proteins:
        logger.warning("No proteins translated for taxon %d", taxon_id)
        return {"taxon_id": taxon_id, "skipped": True, "reason": "no_proteins"}

    client = InterProScanClient()
    domain_results = asyncio.run(client.run_batch(proteins, taxon_id=taxon_id))

    # Flatten and load to Neo4j
    all_domains = []
    for gene_id, domain_list in domain_results.items():
        for d in domain_list:
            if not d.get("pfam_acc") or not d.get("start_aa"):
                continue
            domain_id = f"{gene_id}__{d['pfam_acc']}__{d['start_aa']}"
            all_domains.append({
                "gene_name":    gene_id,
                "pfam_acc":     d["pfam_acc"],
                "domain_name":  d.get("domain_name", ""),
                "domain_id":    domain_id,
                "start_aa":     d["start_aa"],
                "end_aa":       d.get("end_aa"),
                "e_value":      d.get("e_value"),
                "source_db":    "interproscan",
                "species_taxon": taxon_id,
            })

    from app.ingestion.domain_ingest_uniprot import load_domains_to_neo4j_accurate
    stats = load_domains_to_neo4j_accurate(all_domains, driver)

    logger.info(
        "InterProScan ingest for taxon %d: %d domains loaded from %d genes",
        taxon_id, stats["loaded"], len(proteins),
    )
    return {"taxon_id": taxon_id, "genes_translated": len(proteins), **stats}
