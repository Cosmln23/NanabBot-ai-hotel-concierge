import re
import unicodedata
from difflib import SequenceMatcher
from typing import Iterable, Set

LEET_MAP = str.maketrans(
    {
        "0": "o",
        "1": "i",
        "2": "z",
        "3": "e",
        "4": "a",
        "5": "s",
        "7": "t",
        "8": "b",
        "9": "g",
    }
)

SUFFIXES = [
    "urilor",
    "elor",
    "ilor",
    "urile",
    "ului",
    "ile",
    "ele",
    "uri",
    "le",
    "ul",
    "es",
    "s",
    "a",
    "e",
    "i",
]


def normalize_text(text: str) -> str:
    if not text:
        return ""
    lowered = text.lower().translate(LEET_MAP)
    lowered = unicodedata.normalize("NFKD", lowered)
    lowered = "".join(ch for ch in lowered if not unicodedata.combining(ch))
    lowered = re.sub(r"(.)\1+", r"\1", lowered)
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def tokenize(text: str) -> list[str]:
    normalized = normalize_text(text)
    if not normalized:
        return []
    return [tok for tok in normalized.split(" ") if tok]


def stem_variants(token: str) -> Set[str]:
    variants = {token}
    for suffix in SUFFIXES:
        if token.endswith(suffix):
            root = token[: -len(suffix)]
            if len(root) >= 2:
                variants.add(root)
    return variants


def expand_tokens(tokens: Iterable[str]) -> Set[str]:
    expanded: Set[str] = set()
    for token in tokens:
        if not token:
            continue
        for variant in stem_variants(token):
            expanded.add(variant)
    return expanded


# Romanian singular → plural mappings for common food/drink items (after normalization)
ROMANIAN_PLURAL_MAP = {
    "apa": "ape",  # apă → ape (water)
    "bere": "beri",  # bere → beri (beer)
    "cafea": "cafele",  # cafea → cafele (coffee)
    "supa": "supe",  # supă → supe (soup)
    "ciorba": "ciorbe",  # ciorbă → ciorbe (sour soup)
    "pizza": "pizze",  # pizza → pizze
    "paste": "paste",  # paste (already plural, pasta)
    "suc": "sucuri",  # suc → sucuri (juice)
    "vin": "vinuri",  # vin → vinuri (wine)
}


def extract_menu_tokens(menu_text: str) -> Set[str]:
    tokens: Set[str] = set()
    if not menu_text:
        return tokens
    for raw_line in menu_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        # Remove bullet points (-, *, •) from the beginning
        line = line.lstrip("-*• ")
        name_part = re.split(r"[:\-–—]", line, maxsplit=1)[0]
        for token in tokenize(name_part):
            if len(token) >= 2 and not token.isdigit():
                tokens.add(token)
                # Add plural variant if exists in mapping
                if token in ROMANIAN_PLURAL_MAP:
                    tokens.add(ROMANIAN_PLURAL_MAP[token])
    return tokens


def fuzzy_match_tokens(
    tokens: Iterable[str], candidates: Iterable[str], threshold: float = 0.85
) -> bool:
    token_set = {t for t in tokens if t}
    candidate_set = {c for c in candidates if c}
    if not token_set or not candidate_set:
        return False
    if token_set.intersection(candidate_set):
        return True
    for token in token_set:
        if len(token) < 3:
            continue
        for candidate in candidate_set:
            if len(candidate) < 3:
                continue
            if SequenceMatcher(None, token, candidate).ratio() >= threshold:
                return True
    return False


def text_claims_task_creation(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    phrases = [
        "am creat",
        "am inregistrat",
        "am trimis",
        "am deschis",
        "bilet",
        "tichet",
        "ticket",
        "created a ticket",
        "created a request",
        "request created",
        "request submitted",
        "i created",
        "i have created",
        "we created",
        "we have created",
    ]
    return any(phrase in normalized for phrase in phrases)
