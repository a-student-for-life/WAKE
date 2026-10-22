"""Vessel name normalisation shared by experiments 1 and 2 (STAGE_A_SPEC.md)."""
import re

PREFIXES = ["M/V", "MV", "F/V", "FV", "M/T", "MT", "T/V", "TUG", "OSV", "S/V",
            # added 2026-10-22 (ISSUES.md #2): seen as leading words on 37 NRC names
            "TUG BOAT", "TUGBOAT", "TOW BOAT", "TOWBOAT", "FISHING VESSEL", "VESSEL",
            "USNS", "M/S", "R/V", "P/V", "THE"]
# Not prefixes: "MS" (usually Miss, as in MS. DEBBIE) and the TowBoatUS brand.
_towboatus = re.compile(r"^TOW\s*BOAT\s*U\.?S\.?\b")
# longest first, so "TUG BOAT X" loses "TUG BOAT", not just "TUG"
_pref = re.compile(r"^\s*(?:" + "|".join(re.escape(p) for p in sorted(PREFIXES, key=len, reverse=True))
                   + r")(?:\s+|\.|$)")


def norm_name(s):
    """Upper case, drop leading prefixes (PREFIXES, repeatedly), keep A-Z and 0-9 only.
    A name that is nothing but prefixes keeps its original letters."""
    if s is None:
        return ""
    s = str(s).upper().strip().strip("\"'“”")
    s = _towboatus.sub("TOWBOATUS", s)
    orig = s
    prev = None
    while prev != s:  # e.g. "TUG M/V X" -> "X"
        prev = s
        s = _pref.sub("", s, count=1).strip()
    out = re.sub(r"[^A-Z0-9]", "", s)
    return out or re.sub(r"[^A-Z0-9]", "", orig)


def loose_match(needed, ais):
    """Needed name contained in the AIS name, at most 4 extra characters,
    needed name at least 5 characters. Both already normalised."""
    return (len(needed) >= 5 and needed != ais and needed in ais
            and len(ais) - len(needed) <= 4)
