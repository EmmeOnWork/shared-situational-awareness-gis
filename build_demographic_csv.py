#!/usr/bin/env python3
"""Build a consolidated `demographic` seed CSV from the ISTAT bulletin tables.

Sources (semicolon-delimited, multi-row headers, paginated 'segue' blocks):
  Tabella_1_clean.csv  -> resident population (Italian/foreign/total) + age structure
  Tabella_4_clean.csv  -> demographic-balance migration rates (internal/foreign/total)

Output: data/demographic.csv  (one row per territory; comma-delimited; UTF-8)

Population values stay in ISTAT's published unit (thousands). The (S)/(P)
quality flags are column-uniform, so they are NOT stored per row; they belong
in the API response metadata.
"""
import csv
import os
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")

T1 = os.path.join(DATA, "Tabella_1_clean.csv")
T4 = os.path.join(DATA, "Tabella_4_clean.csv")
OUT = os.path.join(DATA, "demographic.csv")

# Raw ISTAT labels by level (anything not listed here is a province).
REGIONS = {
    "Piemonte", "Valle d'Aosta", "Lombardia", "Trentino-A. A.", "Veneto",
    "Friuli-V. G.", "Liguria", "Emilia-Romagna", "Toscana", "Umbria",
    "Marche", "Lazio", "Abruzzo", "Molise", "Campania", "Puglia",
    "Basilicata", "Calabria", "Sicilia", "Sardegna",
}
MACRO = {"Nord-ovest", "Nord-est", "Centro", "Sud", "Isole"}
NATIONAL = {"ITALIA"}

# Raw ISTAT label -> full official name (only where they differ).
NAME_NORMALIZE = {
    "Trentino-A. A.": "Trentino-Alto Adige",
    "Friuli-V. G.": "Friuli-Venezia Giulia",
    "ITALIA": "Italia",
}


def _norm_apos(s):
    return s.replace("’", "'")


def classify(raw):
    key = _norm_apos(raw)
    if key in NATIONAL:
        return "national"
    if key in MACRO:
        return "macro_area"
    if key in REGIONS:
        return "region"
    return "province"


def normalize_name(raw):
    return NAME_NORMALIZE.get(raw, raw)


def _is_float(s):
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False


def parse_table(path, indices):
    """Return OrderedDict raw_name -> {col: original_string}.

    `indices` maps output column name -> source field index. A line is a data
    row iff col0 is a territory label (non-empty; not a title/header/footnote)
    and every referenced field parses as a float.
    """
    rows = OrderedDict()
    max_idx = max(indices.values())
    with open(path, encoding="utf-8-sig", newline="") as fh:
        for line in fh:
            fields = [f.strip() for f in line.rstrip("\n").split(";")]
            name = fields[0] if fields else ""
            if (not name
                    or name.startswith("Tabella")
                    or name.startswith("Province")
                    or name.startswith("(")):
                continue
            if len(fields) <= max_idx:
                continue
            if not all(_is_float(fields[i]) for i in indices.values()):
                continue
            rows[name] = {col: fields[i] for col, i in indices.items()}
    return rows


def main():
    t1 = parse_table(T1, {
        "pop_italian": 1,
        "pop_foreign": 2,
        "pop_total": 3,
        "age_share_0_14": 5,
        "age_share_15_64": 6,
        "age_share_65_plus": 7,
    })
    t4 = parse_table(T4, {
        "mig_rate_internal": 4,
        "mig_rate_foreign": 5,
        "mig_rate_total": 6,
    })

    print("T1 data rows: %d" % len(t1))
    print("T4 data rows: %d" % len(t4))

    only_t1 = sorted(set(t1) - set(t4))
    only_t4 = sorted(set(t4) - set(t1))
    if only_t1:
        print("WARNING - in T1 but not T4: %r" % only_t1)
    if only_t4:
        print("WARNING - in T4 but not T1: %r" % only_t4)

    columns = [
        "territory_name", "territory_name_istat", "level",
        "pop_total", "pop_italian", "pop_foreign",
        "age_share_0_14", "age_share_15_64", "age_share_65_plus",
        "mig_rate_internal", "mig_rate_foreign", "mig_rate_total",
    ]

    level_counts = {}
    with open(OUT, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(columns)
        for raw, vals in t1.items():
            level = classify(raw)
            level_counts[level] = level_counts.get(level, 0) + 1
            mig = t4.get(raw, {})
            row = {
                "territory_name": normalize_name(raw),
                "territory_name_istat": raw,
                "level": level,
                "pop_total": vals["pop_total"],
                "pop_italian": vals["pop_italian"],
                "pop_foreign": vals["pop_foreign"],
                "age_share_0_14": vals["age_share_0_14"],
                "age_share_15_64": vals["age_share_15_64"],
                "age_share_65_plus": vals["age_share_65_plus"],
                "mig_rate_internal": mig.get("mig_rate_internal", ""),
                "mig_rate_foreign": mig.get("mig_rate_foreign", ""),
                "mig_rate_total": mig.get("mig_rate_total", ""),
            }
            w.writerow([row[c] for c in columns])

    total = sum(level_counts.values())
    print("Wrote %s: %d rows" % (OUT, total))
    print("Level counts: %r" % level_counts)


if __name__ == "__main__":
    main()
