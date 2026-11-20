"""Text helpers: language/script tagging and personal-data redaction."""

import re
import unicodedata
from functools import lru_cache

import config

# --------------------------------------------------------------------------
# Language / script tagging
# --------------------------------------------------------------------------
LATIN_TOKEN_RE = re.compile(r"[a-z]+")


@lru_cache(maxsize=1)
def romanized_words() -> frozenset[str]:
    words = set()
    for line in config.ROMANIZED_WORDS.read_text(encoding="utf-8").splitlines():
        word = line.split("#", 1)[0].strip().lower()
        if word:
            words.add(word)
    return frozenset(words)


def script_counts(text: str) -> tuple[int, int]:
    """Count Bengali-script and Latin-script letters (including combining vowel signs).

    A character is Bengali when its Unicode name starts with BENGALI.
    Digits, punctuation and emoji are ignored.
    """
    bengali = latin = 0
    for ch in text:
        if not (ch.isalpha() or unicodedata.category(ch).startswith("M")):
            continue
        name = unicodedata.name(ch, "")
        if name.startswith("BENGALI"):
            bengali += 1
        elif name.startswith("LATIN"):
            latin += 1
    return bengali, latin


def tag_language(text: str) -> dict:
    """Label a review as bangla, english, mixed, romanized, or other.

    bangla     >= 80% of letters are Bengali script
    mixed      both scripts, neither reaching 80%
    romanized  >= 80% Latin letters, with at least 2 romanized-Bangla words that
               make up at least 10% of the Latin tokens, or 1 such word making up
               at least 25% (short reviews such as "bkash app open hoina")
    english    >= 80% Latin letters otherwise
    other      no Bengali or Latin letters at all
    """
    bengali, latin = script_counts(text)
    letters = bengali + latin
    tokens = LATIN_TOKEN_RE.findall(text.casefold())
    vocab = romanized_words()
    hits = sum(1 for t in tokens if t in vocab)
    share = hits / len(tokens) if tokens else 0.0

    if letters == 0:
        group = "other"
    elif bengali / letters >= config.BANGLA_RATIO_MIN:
        group = "bangla"
    elif latin / letters >= config.LATIN_RATIO_MIN:
        is_romanized = (
            (hits >= config.ROMANIZED_MIN_HITS and share >= config.ROMANIZED_MIN_SHARE)
            or (hits >= 1 and share >= config.ROMANIZED_SINGLE_HIT_SHARE)
        )
        group = "romanized" if is_romanized else "english"
    else:
        group = "mixed"

    return {
        "lang_group": group,
        "bengali_share": round(bengali / letters, 3) if letters else 0.0,
        "romanized_hits": hits,
    }


# --------------------------------------------------------------------------
# Personal-data redaction
# --------------------------------------------------------------------------
# Digits may be written in Latin (0-9) or Bengali (U+09E6-U+09EF) numerals.
D = r"[0-9০-৯]"
NOT_D_BEFORE = r"(?<![0-9০-৯])"
NOT_D_AFTER = r"(?![0-9০-৯])"

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
# The providers' own support addresses (common in developer replies) are not personal data.
ORG_EMAIL_DOMAINS = ("bkash.com", "nagad.com.bd", "dutchbanglabank.com", "dbbl.com.bd", "upaybd.com", "ucb.com.bd")

# Bangladeshi mobile number: optional +88/0088 country code, then 01[3-9] and 8
# more digits, allowing single spaces, dots or dashes between digits.
PHONE_RE = re.compile(
    NOT_D_BEFORE
    + r"(?:(?:\+|00)?(?:88|৮৮)[\s.-]?)?"
    + r"[0০][\s.-]?[1১][\s.-]?[3-9৩-৯]"
    + rf"(?:[\s.-]?{D}){{8}}"
    + NOT_D_AFTER
)

# Transaction ID announced by a keyword, e.g. "TrxID: BKJ5L2M9XQ", "txn id 71AB3CDE",
# "ট্রানজেকশন আইডি ...". The keyword must name an ID/number (so "transaction 100000
# taka" keeps its amount) and the ID must contain a digit.
TRX_KEYWORD_RE = re.compile(
    r"(?i)(\b(?:trx|trnx|txn|tran[sx]?action|transection)\s*(?:id|number|nmbr|no)\b\.?"
    r"|\b(?:trxid|txnid)\b"
    r"|(?:ট্রানজেকশন|ট্রাঞ্জেকশন|লেনদেন)\s*(?:আইডি|নম্বর|নাম্বার))"
    r"(\s*[:#\-=]?\s*)((?=[A-Za-z0-9]*[0-9])[A-Za-z0-9]{6,})"
)

# Stand-alone transaction-style code: 8-12 upper-case letters and digits with at
# least two of each (bKash TrxIDs are 10 such characters).
TRX_CODE_RE = re.compile(r"\b(?=(?:[A-Z]*[0-9]){2})(?=(?:[0-9]*[A-Z]){2})[A-Z0-9]{8,12}\b")

# Any remaining run of 8+ digits: NID (10/13/17 digits), account or card numbers.
LONG_NUMBER_RE = re.compile(NOT_D_BEFORE + rf"{D}{{8,}}" + NOT_D_AFTER)

# Greeting at the start of a developer reply, e.g. "Dear Rahim," -> "Dear [NAME],"
# (প্রিয় is matched with both encodings of য়: U+09DF and U+09AF U+09BC.)
GREETING_RE = re.compile(
    r"^(\s*(?:dear|hello|hi|hey|প্রি(?:য়|য়))\s+)"
    r"([^,!।\n]{1,40}?)(\s*[,!।])",
    re.IGNORECASE,
)
GENERIC_ADDRESSEES = {
    "sir", "madam", "sir/madam", "sir / madam", "customer", "valued customer", "user", "users",
    "concern", "গ্রাহক", "সম্মানিত গ্রাহক", "স্যার", "ম্যাডাম",
}


def redact(text: str, is_reply: bool = False) -> tuple[str, dict]:
    """Replace phone numbers, IDs, transaction IDs and e-mails with placeholders.

    Returns the redacted text and a count per placeholder type. Personal names
    inside reviews cannot be detected reliably; coders flag those manually.
    """
    counts = {}

    def sub(pattern, repl, s, label):
        s, n = pattern.subn(repl, s)
        if n:
            counts[label] = counts.get(label, 0) + n
        return s

    def email(match):
        domain = match.group(0).split("@", 1)[1].lower()
        if domain.startswith(ORG_EMAIL_DOMAINS):  # also catches run-ons like "bkash.comwith"
            return match.group(0)
        counts["EMAIL"] = counts.get("EMAIL", 0) + 1
        return "[EMAIL]"

    text = EMAIL_RE.sub(email, text)
    text = sub(PHONE_RE, "[PHONE]", text, "PHONE")
    text = sub(TRX_KEYWORD_RE, r"\1\2[TRX_ID]", text, "TRX_ID")
    text = sub(TRX_CODE_RE, "[TRX_ID]", text, "TRX_ID")
    text = sub(LONG_NUMBER_RE, "[ID_NUMBER]", text, "ID_NUMBER")

    if is_reply:
        match = GREETING_RE.match(text)
        if match and match.group(2).strip().lower() not in GENERIC_ADDRESSEES:
            text = GREETING_RE.sub(r"\1[NAME]\3", text, count=1)
            counts["NAME"] = counts.get("NAME", 0) + 1
    return text, counts


# --------------------------------------------------------------------------
# Length and duplicate helpers
# --------------------------------------------------------------------------
WS_RE = re.compile(r"\s+")


def normalize_whitespace(text: str) -> str:
    return WS_RE.sub(" ", text).strip()


def word_count(text: str) -> int:
    return len(text.split())


def dedup_key(text: str) -> str:
    """Case-, spacing- and punctuation-insensitive key for spotting duplicate texts."""
    text = unicodedata.normalize("NFKC", text).casefold()
    kept = [ch if unicodedata.category(ch)[0] in "LMN" else " " for ch in text]
    return normalize_whitespace("".join(kept))
