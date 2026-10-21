"""Vessel name normalisation shared by experiments 1 and 2 (STAGE_A_SPEC.md)."""
import re

PREFIXES = ["M/V", "MV", "F/V", "FV", "M/T", "MT", "T/V", "TUG", "OSV", "S/V"]
_pref = re.compile(r"^\s*(?:" + "|".join(re.escape(p) for p in PREFIXES) + r")(?:\s+|\.|$)")


def norm_name(s):
    """Upper case, drop a leading prefix (M/V, MV, F/V, FV, M/T, MT, T/V, TUG, OSV, S/V),
    keep A-Z and 0-9 only."""
    if s is None:
        return ""
    s = str(s).upper().strip().strip("\"'“”")
    prev = None
    while prev != s:  # e.g. "TUG M/V X" -> "X"
        prev = s
        s = _pref.sub("", s, count=1).strip()
    return re.sub(r"[^A-Z0-9]", "", s)


def loose_match(needed, ais):
    """Needed name contained in the AIS name, at most 4 extra characters,
    needed name at least 5 characters. Both already normalised."""
    return (len(needed) >= 5 and needed != ais and needed in ais
            and len(ais) - len(needed) <= 4)
