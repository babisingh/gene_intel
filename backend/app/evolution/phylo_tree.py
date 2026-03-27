"""
Hardcoded phylogenetic tree for the 17 Gene-Intel species.
Used for domain gain/loss reconstruction (Dollo parsimony) and domain age
classification. Divergence times from TimeTree (Kumar et al. 2022).

Topology:
  Root (LUCA, ~3500 Mya)
  ├── E. coli (Bacteria)
  └── Eukaryotes (~1500 Mya)
      ├── Archaeplastida: Green alga → Moss → Arabidopsis/Rice
      └── Opisthokonta (~900 Mya)
          ├── Fungi: Aspergillus, Yeast
          └── Metazoa (~700 Mya)
              ├── Ecdysozoa: Fly, Worm
              └── Vertebrata (~430 Mya)
                  ├── Zebrafish
                  └── Tetrapoda (~360 Mya)
                      ├── Frog
                      └── Amniota (~300 Mya)
                          ├── Reptilia/Aves: Chicken, King Cobra
                          └── Mammalia (~87 Mya)
                              ├── Mouse, Cow
                              └── Primates (~6 Mya): Human, Chimp
"""

# ── Species ordering (top → bottom in phylo tree visualization) ───────────────

SPECIES_ORDER = [
    "9606",    # Human
    "9598",    # Chimpanzee
    "10090",   # Mouse
    "9913",    # Cow
    "9031",    # Chicken
    "8665",    # King Cobra
    "8364",    # Frog
    "7955",    # Zebrafish
    "7227",    # Fruit fly
    "6239",    # C. elegans
    "3702",    # Arabidopsis
    "4530",    # Rice
    "3218",    # Moss
    "3055",    # Green alga
    "162425",  # Aspergillus
    "4932",    # Yeast
    "511145",  # E. coli
]

SPECIES_META: dict[str, dict] = {
    "9606":    {"common": "Human",               "short": "Human",         "kingdom": "Mammalia"},
    "9598":    {"common": "Chimpanzee",           "short": "Chimp",         "kingdom": "Mammalia"},
    "10090":   {"common": "Mouse",               "short": "Mouse",         "kingdom": "Mammalia"},
    "9913":    {"common": "Cow",                 "short": "Cow",           "kingdom": "Mammalia"},
    "9031":    {"common": "Chicken",             "short": "Chicken",       "kingdom": "Aves"},
    "8665":    {"common": "King Cobra",          "short": "Cobra",         "kingdom": "Reptilia"},
    "8364":    {"common": "Western clawed frog", "short": "Frog",          "kingdom": "Amphibia"},
    "7955":    {"common": "Zebrafish",           "short": "Zebrafish",     "kingdom": "Actinopterygii"},
    "7227":    {"common": "Fruit fly",           "short": "Fly",           "kingdom": "Insecta"},
    "6239":    {"common": "C. elegans",          "short": "Worm",          "kingdom": "Nematoda"},
    "3702":    {"common": "Arabidopsis",         "short": "Arabidopsis",   "kingdom": "Plantae"},
    "4530":    {"common": "Rice",                "short": "Rice",          "kingdom": "Plantae"},
    "3218":    {"common": "Moss",                "short": "Moss",          "kingdom": "Bryophyta"},
    "3055":    {"common": "Green alga",          "short": "Alga",          "kingdom": "Chlorophyta"},
    "162425":  {"common": "Aspergillus",         "short": "Aspergillus",   "kingdom": "Fungi"},
    "4932":    {"common": "Yeast",               "short": "Yeast",         "kingdom": "Fungi"},
    "511145":  {"common": "E. coli K-12",        "short": "E. coli",       "kingdom": "Bacteria"},
}

# ── Phylogenetic tree ─────────────────────────────────────────────────────────
# Leaf nodes: {"name", "taxon_id", "label", "time_mya": 0}
# Internal nodes: {"name", "label", "time_mya", "children": [...]}

PHYLO_TREE: dict = {
    "name": "root", "label": "LUCA", "time_mya": 3500,
    "children": [
        {"name": "ecoli", "taxon_id": "511145", "label": "E. coli K-12", "time_mya": 0},
        {
            "name": "eukaryotes", "label": "Common Eukaryote Ancestor", "time_mya": 1500,
            "children": [
                {
                    "name": "archaeplastida", "label": "Plant/Algae Ancestor", "time_mya": 1000,
                    "children": [
                        {"name": "green_alga", "taxon_id": "3055", "label": "Green alga", "time_mya": 0},
                        {
                            "name": "land_plants", "label": "Land Plant Ancestor", "time_mya": 470,
                            "children": [
                                {"name": "moss", "taxon_id": "3218", "label": "Moss", "time_mya": 0},
                                {
                                    "name": "angiosperms", "label": "Angiosperm Ancestor", "time_mya": 150,
                                    "children": [
                                        {"name": "arabidopsis", "taxon_id": "3702", "label": "Arabidopsis", "time_mya": 0},
                                        {"name": "rice", "taxon_id": "4530", "label": "Rice", "time_mya": 0},
                                    ],
                                },
                            ],
                        },
                    ],
                },
                {
                    "name": "opisthokonta", "label": "Opisthokonta Ancestor", "time_mya": 900,
                    "children": [
                        {
                            "name": "fungi", "label": "Fungal Ancestor", "time_mya": 500,
                            "children": [
                                {"name": "aspergillus", "taxon_id": "162425", "label": "Aspergillus", "time_mya": 0},
                                {"name": "yeast", "taxon_id": "4932", "label": "Yeast", "time_mya": 0},
                            ],
                        },
                        {
                            "name": "metazoa", "label": "Metazoan Ancestor", "time_mya": 700,
                            "children": [
                                {
                                    "name": "ecdysozoa", "label": "Ecdysozoan Ancestor", "time_mya": 700,
                                    "children": [
                                        {"name": "fly", "taxon_id": "7227", "label": "Fruit fly", "time_mya": 0},
                                        {"name": "worm", "taxon_id": "6239", "label": "C. elegans", "time_mya": 0},
                                    ],
                                },
                                {
                                    "name": "vertebrates", "label": "Vertebrate Ancestor", "time_mya": 430,
                                    "children": [
                                        {"name": "zebrafish", "taxon_id": "7955", "label": "Zebrafish", "time_mya": 0},
                                        {
                                            "name": "tetrapods", "label": "Tetrapod Ancestor", "time_mya": 360,
                                            "children": [
                                                {"name": "frog", "taxon_id": "8364", "label": "Frog", "time_mya": 0},
                                                {
                                                    "name": "amniotes", "label": "Amniote Ancestor", "time_mya": 300,
                                                    "children": [
                                                        {
                                                            "name": "reptiles_birds", "label": "Reptile/Bird Ancestor", "time_mya": 280,
                                                            "children": [
                                                                {"name": "chicken", "taxon_id": "9031", "label": "Chicken", "time_mya": 0},
                                                                {"name": "king_cobra", "taxon_id": "8665", "label": "King Cobra", "time_mya": 0},
                                                            ],
                                                        },
                                                        {
                                                            "name": "mammals", "label": "Mammalian Ancestor", "time_mya": 87,
                                                            "children": [
                                                                {"name": "mouse", "taxon_id": "10090", "label": "Mouse", "time_mya": 0},
                                                                {"name": "cow", "taxon_id": "9913", "label": "Cow", "time_mya": 0},
                                                                {
                                                                    "name": "primates", "label": "Primate Ancestor", "time_mya": 6,
                                                                    "children": [
                                                                        {"name": "human", "taxon_id": "9606", "label": "Human", "time_mya": 0},
                                                                        {"name": "chimp", "taxon_id": "9598", "label": "Chimp", "time_mya": 0},
                                                                    ],
                                                                },
                                                            ],
                                                        },
                                                    ],
                                                },
                                            ],
                                        },
                                    ],
                                },
                            ],
                        },
                    ],
                },
            ],
        },
    ],
}


# ── Tree utilities ────────────────────────────────────────────────────────────

def get_leaves(node: dict) -> list[str]:
    """Return all taxon_ids reachable from this node."""
    if "taxon_id" in node:
        return [node["taxon_id"]]
    return [leaf for child in node.get("children", []) for leaf in get_leaves(child)]


def find_lca(taxon_ids: set, node: dict | None = None) -> dict | None:
    """
    Lowest common ancestor of the given taxon_id set via Dollo parsimony:
    domain assumed gained once at this node, independently lost in absent subtrees.
    """
    if not taxon_ids:
        return None
    if node is None:
        node = PHYLO_TREE

    subtree_leaves = set(get_leaves(node))
    if not (taxon_ids & subtree_leaves):
        return None
    if "taxon_id" in node:
        return node if node["taxon_id"] in taxon_ids else None

    matching = [c for c in node.get("children", []) if taxon_ids & set(get_leaves(c))]
    if len(matching) > 1:
        return node
    if len(matching) == 1:
        return find_lca(taxon_ids, matching[0]) or node
    return None


def compute_domain_events(domain_id: str, taxon_ids_present: set) -> list[dict]:
    """
    Apply Dollo parsimony: domain gained once at LCA, independently lost in
    any descendant subtree where all leaves are absent.
    Returns list of {"type", "domain_id", "node", "node_label", "time_mya"} dicts.
    """
    if not taxon_ids_present:
        return []

    lca = find_lca(taxon_ids_present)
    if not lca:
        return []

    events = [{
        "type": "gain",
        "domain_id": domain_id,
        "node": lca.get("name"),
        "node_label": lca.get("label", lca.get("name", "?")),
        "time_mya": lca.get("time_mya", 0),
    }]

    all_lca_leaves = set(get_leaves(lca))
    absent = all_lca_leaves - taxon_ids_present
    if absent:
        for child in lca.get("children", []):
            child_leaves = set(get_leaves(child))
            if child_leaves & absent and not (child_leaves & taxon_ids_present):
                events.append({
                    "type": "loss",
                    "domain_id": domain_id,
                    "node": child.get("name"),
                    "node_label": child.get("label", child.get("name", "?")),
                    "time_mya": child.get("time_mya", 0),
                    "species": [
                        SPECIES_META.get(t, {}).get("short", t)
                        for t in sorted(child_leaves & absent)
                    ],
                })

    return events


# Age classification tiers (oldest → newest; first match wins)
_AGE_TIERS: list[tuple] = [
    ("Ancient (>3.5 Gya)",    3500, {"511145"}),
    ("Eukaryotic (~1.5 Gya)", 1500, {"4932", "162425", "3055", "3218", "3702", "4530"}),
    ("Metazoan (~700 Mya)",    700,  {"7227", "6239"}),
    ("Vertebrate (~500 Mya)",  500,  {"7955"}),
    ("Tetrapod (~360 Mya)",    360,  {"8364"}),
    ("Amniote (~300 Mya)",     300,  {"9031", "8665"}),
    ("Mammalian (~170 Mya)",   170,  {"10090", "9913"}),
    ("Primate (~6 Mya)",         6,  {"9606", "9598"}),
]


def classify_domain_age(taxon_ids_present: set) -> dict:
    """Return age label + time_mya for a domain based on its deepest occurrence."""
    for label, time_mya, indicators in _AGE_TIERS:
        if taxon_ids_present & indicators:
            return {"label": label, "time_mya": time_mya}
    if taxon_ids_present:
        return {"label": "Unknown origin", "time_mya": 0}
    return {"label": "Unknown", "time_mya": 0}


def tree_for_frontend(node: dict) -> dict:
    """Serialize tree to JSON-safe dict for the frontend."""
    out: dict = {
        "name": node.get("name"),
        "label": node.get("label"),
        "time_mya": node.get("time_mya", 0),
    }
    if "taxon_id" in node:
        out["taxon_id"] = node["taxon_id"]
    if "children" in node:
        out["children"] = [tree_for_frontend(c) for c in node["children"]]
    return out
