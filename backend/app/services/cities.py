"""City recognition in any Indian script, and city-tier resolution.

Unicode lays out the Indic scripts (Devanagari, Bengali, Gurmukhi, Gujarati, Odia,
Tamil, Telugu, Kannada, Malayalam) on parallel 128-codepoint tables, so every
script can be folded onto Devanagari and reduced to a consonant "skeleton".
Latin spellings get the same treatment, so कोलकाता, கொல்கத்தா, "Kolkata" and
"Kolkatta" all become "klkt". Voiced/unvoiced pairs are merged because Tamil
writes k/g, t/d and p/b with one letter.
"""
from __future__ import annotations

import re
from functools import lru_cache

from rapidfuzz import fuzz

TIER1 = ["Mumbai", "Delhi", "New Delhi", "Bengaluru", "Bangalore", "Chennai", "Kolkata", "Hyderabad", "Pune",
         "Ahmedabad", "Gurugram", "Gurgaon", "Noida", "Navi Mumbai", "Thane"]
TIER2 = ["Kochi", "Ludhiana", "Nagpur", "Jaipur", "Visakhapatnam", "Vizag", "Lucknow", "Bhopal", "Surat", "Mysuru",
         "Mysore", "Coimbatore", "Indore", "Nashik", "Vadodara", "Patna", "Chandigarh", "Kanpur", "Agra", "Varanasi",
         "Madurai", "Rajkot", "Amritsar", "Bhubaneswar", "Guwahati", "Dehradun", "Ranchi", "Raipur",
         "Thiruvananthapuram", "Mangaluru", "Vijayawada", "Jodhpur", "Gwalior", "Jabalpur", "Aurangabad", "Meerut",
         "Faridabad", "Ghaziabad", "Hubli", "Tiruchirappalli", "Trichy", "Salem", "Tiruppur", "Kozhikode", "Thrissur",
         "Udaipur", "Ajmer", "Kota", "Bikaner", "Jalandhar", "Allahabad", "Prayagraj", "Bareilly", "Aligarh",
         "Moradabad", "Gorakhpur", "Jamshedpur", "Dhanbad", "Cuttack", "Siliguri", "Durgapur", "Asansol", "Belgaum",
         "Belagavi", "Davangere", "Gulbarga", "Warangal", "Guntur", "Nellore", "Kolhapur", "Solapur", "Sangli",
         "Jalgaon", "Bhavnagar", "Jamnagar", "Gandhinagar", "Anand", "Ujjain", "Sagar", "Bilaspur", "Srinagar",
         "Jammu", "Shimla", "Puducherry", "Pondicherry", "Goa", "Panaji", "Vellore", "Erode", "Hosur"]

# older or colloquial names -> official name
ALIASES = {"Bombay": "Mumbai", "Calcutta": "Kolkata", "Madras": "Chennai", "Amdavad": "Ahmedabad",
           "Poona": "Pune", "Baroda": "Vadodara", "Benares": "Varanasi", "Banaras": "Varanasi", "Kashi": "Varanasi",
           "Trivandrum": "Thiruvananthapuram", "Cochin": "Kochi", "Mangalore": "Mangaluru", "Calicut": "Kozhikode",
           "Bengalooru": "Bengaluru", "Gurgaon": "Gurugram", "Mysore": "Mysuru", "Vizag": "Visakhapatnam"}

SMALL_TOWN = re.compile(r"village|gaon|gaun|town|tehsil|taluka|kasba|गाँव|गांव|कस्बा|तहसील|ग्राम", re.I)

# Devanagari consonants -> skeleton letter (voicing merged, aspiration dropped; y, v, h dropped)
_DEVA = {
    0x15: "k", 0x16: "k", 0x17: "k", 0x18: "k", 0x19: "n",
    0x1A: "c", 0x1B: "c", 0x1C: "j", 0x1D: "j", 0x1E: "n",
    0x1F: "t", 0x20: "t", 0x21: "t", 0x22: "t", 0x23: "n",
    0x24: "t", 0x25: "t", 0x26: "t", 0x27: "t", 0x28: "n", 0x29: "n",
    0x2A: "p", 0x2B: "p", 0x2C: "p", 0x2D: "p", 0x2E: "m",
    0x2F: "", 0x30: "r", 0x31: "r", 0x32: "l", 0x33: "l", 0x34: "l", 0x35: "",
    0x36: "s", 0x37: "s", 0x38: "s", 0x39: "",
    0x58: "k", 0x59: "k", 0x5A: "k", 0x5B: "j", 0x5C: "t", 0x5D: "t", 0x5E: "p", 0x5F: "",
    0x01: "n", 0x02: "n",  # chandrabindu, anusvara
}
_INDIC = re.compile(r"[ऀ-෿]+")


def is_indic(text: str) -> bool:
    return bool(_INDIC.search(text or ""))


def _tidy(s: str) -> str:
    s = s.replace("np", "mp")  # anusvara before p/b is an m (मुंबई = Mumbai)
    return re.sub(r"(.)\1+", r"\1", s)


def indic_skeleton(text: str) -> str:
    out = []
    for ch in text:
        cp = ord(ch)
        if 0x0900 <= cp < 0x0E00:
            out.append(_DEVA.get((cp - 0x0900) % 0x80, ""))
    return _tidy("".join(out))


def latin_skeleton(text: str) -> str:
    s = re.sub(r"[^a-z]", "", (text or "").lower())
    s = s.replace("ch", "C").replace("sh", "s").replace("ck", "k")  # C = the 'ch' sound (च)
    s = s.replace("q", "k").replace("x", "ks").replace("z", "j").replace("f", "p")
    s = s.replace("c", "k").replace("C", "c")
    s = s.replace("g", "k").replace("d", "t").replace("b", "p")
    s = re.sub(r"[aeiouyhwv]", "", s)  # vowels, aspiration and semivowels carry little across scripts
    return _tidy(s)


def skeleton(text: str) -> str:
    return indic_skeleton(text) if is_indic(text) else latin_skeleton(text)


@lru_cache
def _known() -> dict[str, tuple[str, int]]:
    """skeleton -> (display name, tier). Dataset tiers win over the static lists."""
    from app.data.loader import get_dataset

    table: dict[str, tuple[str, int]] = {}
    for tier, names in ((2, TIER2), (1, TIER1)):
        for n in names:
            table[latin_skeleton(n)] = (n, tier)
    for city, tier in get_dataset().city_tiers.items():
        table[latin_skeleton(city)] = (city.title(), tier)
    for alias, official in ALIASES.items():
        hit = table.get(latin_skeleton(official))
        if hit:
            table.setdefault(latin_skeleton(alias), hit)
    return table


def resolve(name: str | None) -> tuple[str, int] | None:
    """Known city for a name in any script or spelling, else None."""
    if not name or not name.strip():
        return None
    sk = skeleton(name)
    if len(sk) < 2:
        return None
    known = _known()
    if sk in known:
        return known[sk]
    if len(sk) >= 4:
        best = max(known, key=lambda k: fuzz.ratio(sk, k))
        if fuzz.ratio(sk, best) >= 86:
            return known[best]
    return None


_CITY_CUE_LATIN = re.compile(r"\b(?:in|at|from|near|city|based in|located in)\s+([a-z][a-z .]{1,30})", re.I)
_CITY_CUE_INDIC = re.compile(r"([ऀ-෿]{2,})\s*(?:में|मे|से|शहर|नगर|இல்|ல்|তে|માં|ਵਿੱਚ|లో|ನಲ್ಲಿ|ൽ)")


def find_in_text(text: str, expecting_city: bool = False) -> str | None:
    """Known city mentioned in a message. Without a cue ("in X", "X में") only exact
    names are accepted, so ordinary words are never read as cities."""
    low = (text or "").lower()
    for display, _ in sorted(_known().values(), key=lambda v: -len(v[0])):
        if re.search(rf"\b{re.escape(display.lower())}\b", low):
            return display
    candidates = [m.group(1) for m in _CITY_CUE_INDIC.finditer(text or "")]
    candidates += [w for m in _CITY_CUE_LATIN.finditer(low) for w in (m.group(1).split()[0], m.group(1))]
    if expecting_city:
        candidates += _INDIC.findall(text or "") + re.findall(r"[a-z]{3,}", low)
    for c in candidates:
        hit = resolve(c)
        if hit:
            return hit[0]
    return None


def tier_for(name: str | None, model_tier: int | None = None, context: str = "") -> int | None:
    """Known list first, then the model's guess, then 'small town' wording, else tier 2."""
    if not name:
        return model_tier
    hit = resolve(name)
    if hit:
        return hit[1]
    if model_tier in (1, 2, 3):
        # every tier-1 metro is on the known list, so an unknown city is at most tier 2
        return max(model_tier, 2)
    return 3 if SMALL_TOWN.search(f"{name} {context}") else 2
