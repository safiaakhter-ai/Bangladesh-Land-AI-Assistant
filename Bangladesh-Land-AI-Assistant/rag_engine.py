"""
rag_engine.py — Structured Relational RAG engine for Bangladesh land records.

Changes vs. the original version:
  1. Removed hardcoded Banglish->Bengali name lookup (kartik/ekramul); the LLM
     extractor is now explicitly instructed to transliterate names, and the
     rule-based fallback logs a warning instead of silently mismatching.
  2. All user-controlled text entering an FTS5 MATCH string is escaped.
  3. `query_gemini_api` omits `systemInstruction` instead of sending null.
  4. District/upazila extraction filters stray/short captures like mouza does.
  5. `ensure_fts_index` streams + batch-inserts instead of loading 1.14M rows
     into memory at once.
  6. Connections use WAL mode, a busy timeout, and `contextlib.closing`.
  7. Minor: full mouza string used for search instead of just its first word.
"""

import os
import re
import json
import sqlite3
import logging
import unicodedata
from contextlib import closing

import requests

# Automatically load .env if present
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip()

from land_knowledge_base import (
    is_out_of_scope,
    retrieve_relevant_knowledge,
    LAND_TERMS_GLOSSARY,
    SURVEY_HISTORIES,
    NAMJARI_GUIDE,
)

logger = logging.getLogger("rag_engine")

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite")
GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"

FTS_INSERT_BATCH_SIZE = 5000

# Words that regex captures can pick up as noise around a location/name and
# should never be treated as the actual value.
_LOCATION_STOPWORDS = {
    "er", "or", "of", "in", "the", "a", "an", "কি", "কে", "কোন", "এর", "টা",
    "koyta", "koyti", "ase", "ache", "how", "many", "count",
    "কয়টা", "কয়টি", "কতটি", "কতগুলো", "আছে", "মোট", "লিস্ট", "তালিকা", "list",
}


def clean_bengali_string(text: str) -> str:
    """Normalize decomposed Bengali characters into precomposed single Unicode characters."""
    if not text:
        return ""
    text = str(text).replace('\u09A1\u09BC', '\u09DC').replace('\u09A2\u09BC', '\u09DD').replace('\u09AF\u09BC', '\u09DF')
    text = text.replace('ড়', '\u09DC').replace('ঢ়', '\u09DD').replace('য়', '\u09DF')
    return text.strip()


def normalize_bengali_text(text: str) -> str:
    """Normalize Bengali Unicode text using standard precomposed characters and vowel cleanup."""
    if not text:
        return ""
    text = clean_bengali_string(text)
    text = text.replace('\u09C0', '\u09BF').replace('\u09C2', '\u09C1')
    text = text.replace('\u09DD', '\u09DC')
    text = re.sub(r'([\u09BE-\u09CD])\1+', r'\1', text)
    return text.strip()


def _canonical_match_text(text: str) -> str:
    """Normalize Bengali Unicode spelling variants for robust matching."""
    if not text:
        return ""
    text = normalize_bengali_text(str(text)).lower()
    text = text.replace('\u09DC', '\u09B0')  # ড় -> র
    text = text.replace('\u09A3', '\u09A8')  # ণ -> ন
    text = text.replace('\u09B7', '\u09B8').replace('\u09B6', '\u09B8')  # ষ, শ -> স
    text = text.replace('\u09AF', '\u09DF')  # য -> য়
    return re.sub(r"\s+", " ", text).strip()


def decompose_bengali_string(text: str) -> str:
    """Convert precomposed Bengali characters to decomposed nukta sequences."""
    if not text:
        return ""
    return str(text).replace('\u09DC', '\u09A1\u09BC').replace('\u09DD', '\u09A2\u09BC').replace('\u09DF', '\u09AF\u09BC')


def _generate_bengali_variants(text: str) -> list:
    """Generate common orthographic variants (i-kar/ee-kar, r/d, precomposed & decomposed) for search queries."""
    if not text:
        return []
    base = clean_bengali_string(text)
    variants = {base}
    for t in list(variants):
        if '\u09BF' in t:  # ি
            variants.add(t.replace('\u09BF', '\u09C0'))  # ী
        if '\u09C0' in t:  # ী
            variants.add(t.replace('\u09C0', '\u09BF'))  # ি
        if '\u09DC' in t:  # ড়
            variants.add(t.replace('\u09DC', '\u09A1'))  # ড
            variants.add(t.replace('\u09DC', '\u09B0'))  # র
        if '\u09A1' in t:  # ড
            variants.add(t.replace('\u09A1', '\u09DC'))  # ড়
        if '\u09DF' in t:  # য়
            variants.add(t.replace('\u09DF', '\u09AF'))  # য
        if '\u09AF' in t:  # য
            variants.add(t.replace('\u09AF', '\u09DF'))  # য়
        if '\u09B2' in t:  # ল
            variants.add(t.replace('\u09B2', '\u09AD'))  # ভ
        if '\u09AD' in t:  # ভ
            variants.add(t.replace('\u09AD', '\u09B2'))  # ল
            variants.add(t.replace('\u09AD', '\u09AC'))  # ব
        if '\u09AC' in t:  # ব
            variants.add(t.replace('\u09AC', '\u09AD'))  # ভ
        if '\u0997' in t:  # গ
            variants.add(t.replace('\u0997', '\u0998'))  # ঘ
        if '\u0998' in t:  # ঘ
            variants.add(t.replace('\u0998', '\u0997'))  # গ
        if '\u09B6' in t:  # শ
            variants.add(t.replace('\u09B6', '\u09B8'))  # স
        if '\u09B8' in t:  # স
            variants.add(t.replace('\u09B8', '\u09B6'))  # শ
        if '\u09A8' in t:  # ন
            variants.add(t.replace('\u09A8', '\u09A3'))  # ণ
        if '\u09A3' in t:  # ণ
            variants.add(t.replace('\u09A3', '\u09A8'))  # ন

    all_variants = set()
    for v in variants:
        if v:
            clean_v = clean_bengali_string(v)
            decomp_v = decompose_bengali_string(v)
            all_variants.add(clean_v)
            all_variants.add(decomp_v)
    return [v for v in all_variants if v]


def _fts_escape(token: str) -> str:
    """Escape a token for safe embedding inside a double-quoted FTS5 MATCH
    string. FTS5 string literals use "" to represent a literal double quote;
    without this, a name/mouza containing a quote breaks the MATCH syntax."""
    if not token:
        return ""
    return str(token).replace('"', '""')


def _clean_location_candidate(cand: str) -> str:
    if not cand:
        return ""
    cand = cand.strip()
    # A location regex can accidentally swallow a *different* location
    # keyword ahead of the one it anchored on — e.g. "ব্রাহ্মণবাড়িয়া জেলায়
    # কয়টি উপজেলা আছে" captures everything before "উপজেলা", including the
    # unrelated "জেলায়" clause. Keep only the text after the last rival
    # keyword, since that's almost always where the actual place name is.
    rival_kw_split = re.split(
        r'(?:জেলা(?:র|য়)?|উপজেলা(?:র)?|মৌজা(?:র|য়)?|district|upazila|mouza)\s+',
        cand, flags=re.IGNORECASE)
    if len(rival_kw_split) > 1:
        cand = rival_kw_split[-1].strip()
    cand = re.sub(r'^(?:er|or|of|in|এর)\s+', '', cand, flags=re.IGNORECASE).strip()
    cand = re.sub(
        r'\s+(?:er|or|of|in|koyta|koyti|ase|ache|how|many|কয়টি|কয়টা|কতটি|কতগুলো|আছে|এর)$',
        '', cand, flags=re.IGNORECASE).strip()
    return cand


def _is_meaningful_candidate(cand: str, min_len: int = 2) -> bool:
    if not cand or len(cand) < min_len:
        return False
    if cand.lower() in _LOCATION_STOPWORDS:
        return False
    return True


def _is_probable_owner_candidate(cand: str) -> bool:
    """Reject record-field labels captured by broad owner-name patterns."""
    if not _is_meaningful_candidate(cand):
        return False
    if re.search(r'\d|খতিয়ান|খতিয়ান|khatian|khatiyan|দাগ|dag|plot|নম্বর|number|no\.?', cand, re.IGNORECASE):
        return False
    return True


def _match_places_in_text(text_lower: str, place_map: dict, max_ngram: int = 4) -> dict:
    """Match known place names against `text_lower` using word n-grams and
    O(1) dict lookups instead of checking every place name as a substring
    of the query. This matters once `place_map` includes every mouza in a
    1.14M-record database (tens of thousands of entries) — a per-request
    "for every place: is it a substring?" scan would not stay fast at that
    size, and would also happily match a short place name that's merely a
    fragment of an unrelated word. Returns the longest matching n-gram
    found per field type, e.g. {"upazila": "সরাইল", "mouza": "বেতমোর"}."""
    tokens = re.findall(r'[\u0980-\u09FFA-Za-z0-9]+', text_lower)
    best = {}  # field_type -> (ngram_len, value)
    n = len(tokens)
    for i in range(n):
        for size in range(min(max_ngram, n - i), 0, -1):
            phrase = " ".join(tokens[i:i + size])
            hit = place_map.get(phrase)
            if hit:
                field_type, value = hit
                if field_type not in best or size > best[field_type][0]:
                    best[field_type] = (size, value)
    return {ft: val for ft, (_, val) in best.items()}


# Phrases that signal the user is deliberately abandoning whatever
# owner/location was being discussed and starting a fresh query — these
# should clear inherited context rather than let it leak into an unrelated
# new question.
_TOPIC_RESET_PHRASES = [
    'actually', 'never mind', 'nevermind', 'forget that', 'forget it',
    'different topic', 'different area', 'different place', 'new search',
    'notun kore', 'onno kisu', 'onno jaygay', 'bad den', 'baad den',
    'ভুলে যাও', 'ভুলে যান', 'অন্য কিছু', 'অন্য বিষয়', 'অন্য জায়গা',
    'আলাদা করে', 'নতুন করে', 'বাদ দেন', 'বাদ দিন',
]


def _is_topic_reset(query_lower: str) -> bool:
    return any(p in query_lower for p in _TOPIC_RESET_PHRASES)


class LandRecordRAG:
    def __init__(self, db_path: str = "khatians.db"):
        self.db_path = db_path
        self._fts_initialized = False
        self._api_key = os.environ.get("GEMINI_API_KEY", "")

    # -------------------------------------------------------------------
    # Connection handling
    # -------------------------------------------------------------------
    def _get_connection(self):
        if not os.path.exists(self.db_path):
            return None
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        # WAL lets read queries proceed while the FTS index (or anything
        # else) is being written, and a busy_timeout avoids immediate
        # "database is locked" errors under concurrent Flask requests.
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=30000")
        return conn

    def ensure_fts_index(self) -> bool:
        """Create and populate the SQLite FTS5 index over khatian_details.
        Streams rows and inserts in batches instead of materializing the
        full 1.14M-row result set as a Python list."""
        if self._fts_initialized:
            return True

        conn = self._get_connection()
        if not conn:
            return False

        try:
            with closing(conn):
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='khatian_fts'"
                )
                if cursor.fetchone():
                    self._fts_initialized = True
                    return True

                logger.info("Initializing FTS5 search index on %s ...", self.db_path)
                cursor.execute('''
                    CREATE VIRTUAL TABLE khatian_fts USING fts5(
                        khatian_id UNINDEXED,
                        khatian_no,
                        owners,
                        mouza_name,
                        upazila_name,
                        district_name,
                        survey_name,
                        dags
                    )
                ''')

                read_cursor = conn.cursor()
                read_cursor.execute(
                    "SELECT khatian_id, survey_name, detail_json FROM khatian_details"
                )

                batch = []
                total = 0
                while True:
                    rows = read_cursor.fetchmany(FTS_INSERT_BATCH_SIZE)
                    if not rows:
                        break
                    for row in rows:
                        k_id, survey, detail_str = row[0], row[1] or "", row[2]
                        if not detail_str:
                            continue
                        try:
                            d = json.loads(detail_str)
                        except (TypeError, json.JSONDecodeError):
                            continue
                        batch.append((
                            k_id,
                            str(d.get("KHATIAN_NO", "")),
                            str(d.get("OWNERS", "")),
                            str(d.get("MOUZA_NAME", "")),
                            str(d.get("UPAZILA_NAME", "")),
                            str(d.get("DISTRICT_NAME", "")),
                            survey,
                            str(d.get("DAGS", "")),
                        ))
                    if batch:
                        cursor.executemany('''
                            INSERT INTO khatian_fts
                                (khatian_id, khatian_no, owners, mouza_name,
                                 upazila_name, district_name, survey_name, dags)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', batch)
                        conn.commit()
                        total += len(batch)
                        batch.clear()

                logger.info("FTS5 index populated with %d records.", total)

            self._fts_initialized = True
            return True
        except Exception as e:
            logger.error("FTS5 indexing error: %s", e)
            return False

    # -------------------------------------------------------------------
    # Small helpers
    # -------------------------------------------------------------------
    @staticmethod
    def detect_language(text: str) -> str:
        if re.search(r'[\u0980-\u09FF]', text):
            return 'bn'
        return 'en'

    @staticmethod
    def bn_to_en_digits(text):
        if not text:
            return text
        return str(text).translate(str.maketrans('০১২৩৪৫৬৭৮৯', '0123456789'))

    @staticmethod
    def en_to_bn_digits(text):
        if not text:
            return text
        return str(text).translate(str.maketrans('0123456789', '০১২৩৪৫৬৭৮৯'))

    # -------------------------------------------------------------------
    # STEP 1: ENTITY EXTRACTION
    # -------------------------------------------------------------------
    def extract_search_entities_llm(self, query: str):
        """LLM-based structured entity extraction. This is the primary path
        for Banglish name transliteration — the model is asked to convert
        Banglish owner names into Bengali script itself, rather than relying
        on a hardcoded lookup table."""
        if not self._api_key:
            return None

        system_instruction = (
            "Extract search entities from the user's land-records question. The user may write "
            "in Bengali, Banglish, or English, possibly mixed.\n"
            "Return ONLY a JSON object with these fields:\n"
            "{\n"
            '  "owner_name": string or null,\n'
            '  "division": string or null,\n'
            '  "district": string or null,\n'
            '  "upazila": string or null,\n'
            '  "mouza": string or null,\n'
            '  "jl_number": string or null,\n'
            '  "khatian_no": string or null,\n'
            '  "dag_no": string or null,\n'
            '  "survey_type": "CS" | "RS" | "BS" | null,\n'
            '  "intent": "single_lookup" | "list_all" | "clarification_reply" | "general_question"\n'
            "}\n"
            "- If the question is a conceptual, legal, educational, or general question about what a survey is, how a process works, or differences between terms (e.g. 'BS record ki', 'CS khatian mane ki', 'what is RS survey', 'e-mutation rules', 'how to rectify error', 'CS vs RS', 'khatian ki'), set intent to 'general_question' and leave specific lookup fields (owner_name, khatian_no, dag_no, mouza, upazila, district) as null.\n"
            "- Set intent to 'clarification_reply' if user is picking a location/option in response "
            "to a previous prompt.\n"
            "- NEVER treat conversational commands or phrases as owner names (e.g. 'can you check it now', 'check again', 'see now', 'please check', 'tell me', 'i mean check for', 'ekhon dekho', 'dekho to', 'bujhlam na'). Set owner_name to null if no actual human name is present.\n"
            "- If owner_name is written in Banglish (Bengali words spelled with Latin letters), "
            "transliterate it into Bengali (Unicode) script — the database stores names in Bengali "
            "script, so a Latin-script owner_name will never match. If you are not confident of the "
            "correct Bengali spelling, still provide your best-effort transliteration.\n"
            "- Set intent to 'list_all' if user asks for all land / list all land / talika / how many mouzas / koyta mouza in an area.\n"
            "- If user asks how many mouzas or lists mouzas in an upazila/district (e.g. 'Sarail er koyta mouza ase', 'how many mouzas in Sarail'), extract upazila/district, set mouza to null, and set intent to 'list_all'. Never extract words like 'koyta', 'koyti', or 'how many' as the mouza name.\n"
            "- If the message is just a bare number (e.g. '20', '২০') with no other words, treat it as khatian_no and set intent to 'clarification_reply' — the user is almost certainly answering a previous prompt that listed khatian numbers to choose from.\n"
            "- If the message is just a bare place name with no other words (e.g. 'সরাইল', 'Betmor'), treat it as the most specific location field that name could plausibly be (mouza, then upazila, then district) and set intent to 'clarification_reply'.\n"
            "- Extract any owner name dynamically without hardcoded dictionary restriction."
        )

        payload = {
            "contents": [{"role": "user", "parts": [{"text": query}]}],
            "systemInstruction": {"parts": [{"text": system_instruction}]},
            "generationConfig": {"responseMimeType": "application/json"},
        }

        try:
            r = requests.post(GEMINI_URL, params={"key": self._api_key}, json=payload, timeout=10)
            r.raise_for_status()
            text = r.json()['candidates'][0]['content']['parts'][0]['text']
            return json.loads(text)
        except requests.RequestException as e:
            logger.warning("LLM entity extraction request failed: %s", e)
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            logger.warning("LLM entity extraction returned unexpected shape: %s", e)
        return None

    def _get_dynamic_place_map(self):
        """Dynamically build place map from all unique Upazilas, Districts, and Mouzas
        in khatians.db plus standard Banglish transliterations."""
        if hasattr(self, "_dynamic_place_map_cache") and self._dynamic_place_map_cache:
            return self._dynamic_place_map_cache

        self.ensure_fts_index()
        place_map = {}

        def _register(name, field_type):
            if not name or len(name) < 3:
                return
            clean = normalize_bengali_text(name.strip())
            for variant in (clean.lower(), f"{clean.lower()}র", f"{clean.lower()}ের", f"{clean.lower()}ে"):
                # Don't let a shorter/looser match clobber an already-registered
                # entry for the same key (first registration wins == more
                # authoritative source, since upazila/district are added first).
                place_map.setdefault(variant, (field_type, clean))

        conn = self._get_connection()
        if conn:
            try:
                with closing(conn):
                    cursor = conn.cursor()
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='khatian_fts'")
                    if cursor.fetchone():
                        cursor.execute("SELECT DISTINCT upazila_name, district_name FROM khatian_fts")
                        for u, d in cursor.fetchall():
                            _register(u, "upazila")
                            _register(d, "district")
                        # Also index every real mouza name in the database, not
                        # just a hand-picked handful — this is what lets a bare
                        # "Betmor" style reply resolve to *any* mouza that
                        # actually exists, not only the ones we happened to
                        # hardcode.
                        cursor.execute("SELECT DISTINCT mouza_name FROM khatian_fts")
                        for (m,) in cursor.fetchall():
                            _register(m, "mouza")
            except Exception as e:
                logger.warning("Failed building dynamic place map from DB: %s", e)

        banglish_rules = {
            "sarail": ("upazila", "সরাইল"),
            "bhandaria": ("upazila", "ভান্ডারিয়া"),
            "mathbaria": ("upazila", "মঠবাড়িয়া"),
            "bamna": ("upazila", "বামনা"),
            "nasirnagar": ("upazila", "নাসিরনগর"),
            "nabinagar": ("upazila", "নবীনগর"),
            "savar": ("upazila", "সাভার"),
            "bramhanbaria": ("district", "ব্রাহ্মণবাড়িয়া"),
            "brahmanbaria": ("district", "ব্রাহ্মণবাড়িয়া"),
            "pirojpur": ("district", "পিরোজপুর"),
            "barguna": ("district", "বরগুনা"),
            "barisal": ("district", "বরিশাল"),
            "rajshahi": ("district", "রাজশাহী"),
            "রাজশাহী": ("district", "রাজশাহী"),
            "রাজশাহীর": ("district", "রাজশাহী"),
            "feni": ("district", "ফেনী"),
            "chandpur": ("district", "চাঁদপুর"),
            "faridpur": ("district", "ফরিদপুর"),
            "cumilla": ("district", "কুমিল্লা"),
            "comilla": ("district", "কুমিল্লা"),
            "bhat baria": ("mouza", "ভাট বাড়ীয়া"),
            "bhatbaria": ("mouza", "ভাট বাড়ীয়া"),
            "betmor": ("mouza", "বেতমোর"),
            "betmor rajpara": ("mouza", "বেতমোর"),
            "ramna": ("mouza", "রামনা"),
            "sonakhali": ("mouza", "সোনাখালী"),
            "kolagachia": ("mouza", "কলাগাছিয়া"),
        }
        for k, v in banglish_rules.items():
            k_norm = normalize_bengali_text(k)
            place_map.setdefault(k_norm, v)
            target_norm = normalize_bengali_text(v[1])
            place_map.setdefault(target_norm, v)
            place_map.setdefault(f"{target_norm}র", v)
            place_map.setdefault(f"{target_norm}ের", v)
            place_map.setdefault(f"{target_norm}ে", v)

        self._dynamic_place_map_cache = place_map
        return place_map

    def extract_search_entities_rule_based(self, query: str):
        """Dynamic rule-based fallback parser, used only when no Gemini API
        key is configured. NOTE: this path cannot transliterate arbitrary
        Banglish owner names into Bengali script (that needs either an LLM
        or a proper phonetic transliteration model) — it captures the raw
        text and logs a warning so the limitation is visible rather than
        silently returning zero matches."""
        lang = self.detect_language(query)
        entities = {
            "owner_name": None,
            "division": None,
            "district": None,
            "upazila": None,
            "mouza": None,
            "jl_number": None,
            "khatian_no": None,
            "dag_no": None,
            "survey_type": None,
            "intent": "single_lookup",
            "is_mouza_list_request": False,
            "is_upazila_list_request": False,
            "raw_query": query,
            "lang": lang,
        }

        query_lower = normalize_bengali_text(query.lower().strip())

        list_keywords = [
            'list of', 'all land', 'all mouza', 'mouza list', 'mouzas in', 'mouza in',
            'upazila list', 'upazilas in', 'upazila in', 'upazilas of', 'all upazila', 'all upazilas',
            'shob upazila', 'sob upazila', 'upazila talika', 'upazila list dao',
            'shob', 'sob', 'talika', 'talika dao', 'shob khtaian', 'shob khatian', 'all khatian',
            'khatian list', 'khatian er talika', 'সব জমি', 'সব খতিয়ান', 'লিস্ট দাও', 'লিস্ট',
            'সকল জমি', 'সব মৌজা', 'সব উপজেলা', 'সকল উপজেলা', 'উপজেলা তালিকা', 'উপজেলার তালিকা', 'তালিকা', 'তালিকা দাও', 'খতিয়ানের তালিকা',
            'koyta mouza', 'koyti mouza', 'mouza ase', 'mouza ache', 'how many mouza', 'how many mouzas',
            'koyta upazila', 'koyti upazila', 'upazila ase', 'upazila ache', 'how many upazila',
            'কয়টি মৌজা', 'কয়টা মৌজা', 'কয়টি মৌজা আছে', 'কয়টা মৌজা আছে', 'কতটি মৌজা', 'কতগুলো মৌজা',
            'কয়টি উপজেলা', 'কয়টা উপজেলা', 'কতটি উপজেলা', 'কতগুলো উপজেলা',
            'koyta', 'koyti', 'কয়টি', 'কয়টা', 'কতটি', 'কতগুলো',
        ]

        concept_keywords = [
            'ki', 'কী', 'ki?', 'কী?', 'mane ki', 'মানে কি', 'kake bole', 'কাকে বলে',
            'what is', 'what are', 'explain', 'difference', 'diff', 'পার্থক্য', 'অমিল',
            'ইতিহাস', 'history', 'আইনি ভিত্তি', 'আইনি গুরুত্ব', 'গুরুত্ব', 'নিয়ম', 'পদ্ধতি', 'ফি কত'
        ]

        if any(kw in query_lower for kw in list_keywords):
            entities["intent"] = "list_all"
            if any(kw in query_lower for kw in ['upazila list', 'upazilas in', 'upazila in', 'upazilas of', 'all upazila', 'all upazilas', 'shob upazila', 'sob upazila', 'উপজেলা তালিকা', 'উপজেলার তালিকা', 'সব উপজেলা', 'সকল উপজেলা', 'koyta upazila', 'koyti upazila']):
                entities["is_upazila_list_request"] = True
            else:
                entities["is_mouza_list_request"] = True
        elif any(kw in query_lower for kw in concept_keywords):
            entities["intent"] = "general_question"

        survey_match = re.search(r'\b(CS|RS|SA|BS|BRS)\b', query, re.IGNORECASE)
        if survey_match:
            s_type = survey_match.group(1).upper()
            entities["survey_type"] = "BS" if s_type == "BRS" else s_type
        elif 'সিএস' in query or 'সি এস' in query or 'ক্যাডাস্ট্রাল' in query:
            entities["survey_type"] = "CS"
        elif 'এসএ' in query or 'এস এ' in query or 'স্টেট একুইজিশন' in query:
            entities["survey_type"] = "SA"
        elif 'আরএস' in query or 'আর এস' in query or 'রিভিশনাল' in query:
            entities["survey_type"] = "RS"
        elif 'বিএস' in query or 'বি এস' in query or 'বাংলাদেশ সার্ভে' in query:
            entities["survey_type"] = "BS"

        district_match = re.search(r'([\u0980-\u09FFa-zA-Z\s\-]+?)\s*(?:জেলা|district)', query, re.IGNORECASE)
        if district_match:
            cand = _clean_location_candidate(district_match.group(1))
            if _is_meaningful_candidate(cand):
                entities["district"] = cand

        upazila_match = re.search(r'([\u0980-\u09FFa-zA-Z\s\-]+?)\s*(?:উপজেলা|উপজেলার|upazila|thana)', query, re.IGNORECASE)
        if upazila_match:
            cand = _clean_location_candidate(upazila_match.group(1))
            if _is_meaningful_candidate(cand):
                entities["upazila"] = cand

        mouza_match = re.search(r'([\u0980-\u09FFa-zA-Z\s\-]+?)\s*(?:মৌজা|মৌজার|mouza|mauza)', query, re.IGNORECASE)
        if mouza_match:
            cand = _clean_location_candidate(mouza_match.group(1))
            cand = re.sub(r'\b(?:er|koyta|koyti|ase|ache|how|many|কয়টি|কয়টা|কতটি|কতগুলো|আছে)\b', '', cand, flags=re.IGNORECASE).strip()
            cand = _clean_location_candidate(cand)
            if _is_meaningful_candidate(cand) and cand.lower() not in ['all', 'shob', 'sob', 'koyta', 'koyti']:
                entities["mouza"] = cand

        place_matches = _match_places_in_text(query_lower, self._get_dynamic_place_map())
        for field_type, target_val in place_matches.items():
            if not entities[field_type]:
                entities[field_type] = target_val
            elif field_type == "mouza" and normalize_bengali_text(entities[field_type]).lower() != normalize_bengali_text(target_val).lower():
                # A DB-verified mouza match is more trustworthy than the
                # generic regex capture that ran earlier.
                entities["mouza"] = target_val
        for loc_key in ("upazila", "district"):
            loc_val = place_matches.get(loc_key)
            if loc_val and entities.get("mouza") and normalize_bengali_text(entities["mouza"]).lower() == normalize_bengali_text(loc_val).lower():
                # The mouza regex accidentally captured an upazila/district
                # name (e.g. "সরাইল উপজেলা" partially matched as a mouza).
                entities["mouza"] = None

        khatian_match = re.search(
            r'(?:খতিয়ান|খতিয়ান|khatian|khatiyan|খতিয়ান\s*নং|খতিয়ান\s*নং|খতিয়ান\s*নম্বর|খতিয়ান\s*নম্বর|khatian\s*no|kh|#)\s*[:\-\s]*([০-৯0-9]+)',
            query, re.IGNORECASE)
        if khatian_match:
            entities["khatian_no"] = self.bn_to_en_digits(khatian_match.group(1))
        else:
            khatian_alt = re.search(r'([০-৯0-9]+)\s*(?:no|নং)?\s*(?:khatian|khatiyan|খতিয়ান|খতিয়ান)', query, re.IGNORECASE)
            if khatian_alt:
                entities["khatian_no"] = self.bn_to_en_digits(khatian_alt.group(1))

        dag_match = re.search(r'(?:দাগ|dag|plot|দাগ\s*নং|দাগ\s*নম্বর|dag\s*no|plot\s*no)\s*[:\-\s]*([০-৯0-9]+)', query, re.IGNORECASE)
        if dag_match:
            entities["dag_no"] = self.bn_to_en_digits(dag_match.group(1))
        else:
            dag_alt = re.search(r'([০-৯0-9]+)\s*(?:no|নং|number|নম্বর)?\s*(?:dag|plot|দাগ)', query, re.IGNORECASE)
            if dag_alt:
                entities["dag_no"] = self.bn_to_en_digits(dag_alt.group(1))

        jl_match = re.search(r'(?:jl|জেএল|জেএল\s*নং)\s*[:\-\s]*([০-৯0-9]+)', query, re.IGNORECASE)
        if jl_match:
            entities["jl_number"] = self.bn_to_en_digits(jl_match.group(1))

        # A reply that is *just* a number (e.g. the user typing "20" after
        # being shown a list of candidate khatians) previously matched none
        # of the keyword-anchored regexes above and fell through to nothing.
        # Treat a short bare-digit reply as a khatian number clarification.
        bare_digits = re.fullmatch(r'\s*[০-৯0-9]{1,6}\s*', query)
        if bare_digits and not entities["khatian_no"] and not entities["dag_no"]:
            entities["khatian_no"] = self.bn_to_en_digits(query.strip())
            entities["intent"] = "clarification_reply"

        if entities["intent"] != "list_all" and not entities["is_mouza_list_request"]:
            if not entities["owner_name"]:
                owner_pattern_possessive = re.search(
                    r'([\u0980-\u09FFa-zA-Z\s\-]+?)\s*(?:এর\s+টা|এর\s+টা\s+দাও|এর\s+নামের|এর\s+জমি|এর\s+খতিয়ান|'
                    r'এর\s+রেকর্ড|এর\s+তথ্য|এর\s+বিবরণ|er\s+ta\s+dao|er\s+ta|er\s+din|er\s+dakhaw|'
                    r'er\s+jomir|er\s+jomi|er\s+khatian|er\s+record|er\s+info|er\s+details|'
                    r'এর\s+জমির\s+মোট\s+পরিমাণ|এর\s+জমির\s+পরিমাণ|এর\s+জমির\s+তথ্য|এর\s+জমি\s+কোথায়)',
                    query, re.IGNORECASE)
                if owner_pattern_possessive:
                    cand = owner_pattern_possessive.group(1).strip()
                    cand = re.sub(
                        r'^.*?[\u0980-\u09FFa-zA-Z\s\-]+?\s*(?:উপজেলা|উপজেলার|উপজিলা|জেলা|জেলার|মৌজা|মৌজার|মৌজায়|thana|district|upazila|mouza)\s*',
                        '', cand, flags=re.IGNORECASE).strip()
                    cand = re.sub(
                        r'\b(সরাইল|সরাইলের|ব্রাহ্মণবাড়িয়া|ব্রাহ্মণবাড়িয়ার|ভাট|বাড়ীয়া|ভাটবাড়ীয়া|'
                        r'রাজশাহী|রাজশাহীর|উপজেলা|জেলা|মৌজা|খতিয়ান|দাগ|sarail|bhat|baria)\b',
                        '', cand, flags=re.IGNORECASE).strip()
                    cand = _clean_location_candidate(cand)
                    cand = re.sub(r'^(?:র|ের|এর|য়|য়)\s*', '', cand).strip()
                    if (_is_probable_owner_candidate(cand)
                            and cand.lower() not in ['name', 'details', 'sob', 'amr', 'amar']):
                        entities["owner_name"] = cand
                        if self.detect_language(cand) == 'en':
                            logger.warning(
                                "Rule-based fallback extracted a Latin-script owner name (%r) — "
                                "this will not match Bengali-script records without an LLM key "
                                "configured for transliteration.", cand
                            )

            if not entities["owner_name"]:
                owner_pattern_er = re.search(r'([\u0980-\u09FF\s\-]+?)ের\s+(?:জমি|জমির|খতিয়ান|রেকর্ড|তথ্য|বিবরণ|মোট|পরিমাণ|কোথায়)', query, re.IGNORECASE)
                if owner_pattern_er:
                    cand = owner_pattern_er.group(1).strip()
                    cand = re.sub(
                        r'^.*?[\u0980-\u09FFa-zA-Z\s\-]+?\s*(?:উপজেলা|উপজেলার|উপজিলা|জেলা|জেলার|মৌজা|মৌজার|মৌজায়|thana|district|upazila|mouza)\s*',
                        '', cand, flags=re.IGNORECASE).strip()
                    cand = re.sub(
                        r'\b(সরাইল|সরাইলের|ব্রাহ্মণবাড়িয়া|ব্রাহ্মণবাড়িয়ার|ভাট|বাড়ীয়া|ভাটবাড়ীয়া|'
                        r'রাজশাহী|রাজশাহীর|উপজেলা|জেলা|মৌজা|খতিয়ান|দাগ|sarail|bhat|baria)\b',
                        '', cand, flags=re.IGNORECASE).strip()
                    cand = _clean_location_candidate(cand)
                    cand = re.sub(r'^(?:র|ের|এর|য়|য়)\s*', '', cand).strip()
                    if _is_probable_owner_candidate(cand):
                        entities["owner_name"] = cand

            if not entities["owner_name"] and "মালিকানা" not in query_lower and "মালিকের" not in query_lower:
                owner_pattern = re.search(r'(?:মালিক|owner|malik)\s*[:\-\s]+([\u0980-\u09FFa-zA-Z\s\-]+)', query, re.IGNORECASE)
                if owner_pattern:
                    cand = owner_pattern.group(1).strip()
                    if (_is_probable_owner_candidate(cand)
                            and cand.lower() not in ['name', 'details', 'কি', 'কে']):
                        entities["owner_name"] = cand

            if (not entities["owner_name"] and not entities["khatian_no"] and not entities["dag_no"]
                    and not entities["mouza"] and not entities["upazila"] and not entities["district"]):
                words = query.strip().split()
                non_name_kw = [
                    'list', 'lisa', 'sob', 'shob', 'talika', 'all', 'help', 'hi', 'hello',
                    'how', 'what', 'where', 'why', 'who', 'ke', 'kothay', 'koto', 'kototuku', 'poriman',
                    'tar', 'onar', 'tader', 'oi', 'oitar', 'sheitar', 'etar', 'er', 'his', 'her', 'their', 'its', 'this', 'that',
                    'jomi', 'jomir', 'dags', 'dag', 'plot', 'khatian', 'khotian', 'details', 'info', 'din', 'dao', 'bolo', 'dekhao',
                    'কেমন', 'লিস্ট', 'নিয়ম', 'ফি', 'হ্যাঁ', 'yes', 'না', 'no', 'সরাইলেরটা', 'টা', 'পরিমাণ', 'কত', 'কতটুকু',
                    'জমি', 'জমির', 'তার', 'উনার', 'কোথায়', 'আসে', 'আছে', 'বিবরণ', 'তথ্য', 'দাগ', 'খতিয়ান', 'খতিয়ান', 'মালিক', 'কে'
                ]
                if (1 <= len(words) <= 4 and not any(w.lower() in non_name_kw for w in words)
                        and not re.search(r'\d+', query)):
                    entities["owner_name"] = query.strip()

        return entities

    def extract_search_entities(self, query: str, history=None):
        """Step 1 entrypoint: LLM extraction first, rule-based fallback second."""
        extracted = self.extract_search_entities_llm(query)
        if not extracted:
            extracted = self.extract_search_entities_rule_based(query)

        owner = extracted.get("owner_name") or extracted.get("owner")
        survey = extracted.get("survey_type") or extracted.get("survey")

        params = {
            "owner": owner,
            "owner_name": owner,
            "division": extracted.get("division"),
            "district": extracted.get("district"),
            "upazila": extracted.get("upazila"),
            "mouza": extracted.get("mouza"),
            "jl_number": self.bn_to_en_digits(extracted.get("jl_number")),
            "khatian_no": self.bn_to_en_digits(extracted.get("khatian_no")),
            "dag_no": self.bn_to_en_digits(extracted.get("dag_no")),
            "survey": survey,
            "survey_type": survey,
            "intent": extracted.get("intent", "single_lookup"),
            "is_mouza_list_request": extracted.get("is_mouza_list_request", False),
            "is_upazila_list_request": extracted.get("is_upazila_list_request", False),
            "raw_query": query,
            "lang": self.detect_language(query),
        }

        if (params.get("intent") == "list_all" or params.get("is_mouza_list_request")) and params.get("mouza"):
            mz_raw = params["mouza"].strip()
            mz_lower = mz_raw.lower()
            mz_clean = re.sub(r'\b(?:উপজেলা|উপজেলার|জেলা|upazila|thana|district|er|mouza|mauza|list)\b', '', mz_raw, flags=re.IGNORECASE).strip()
            u_name = params.get("upazila") or ""
            d_name = params.get("district") or ""

            if (not mz_clean or any(w in mz_lower for w in ['koyta', 'koyti', 'how many', 'কয়টি', 'কয়টা', 'কতটি', 'কতগুলো'])
                    or (u_name and normalize_bengali_text(u_name.lower()) in normalize_bengali_text(mz_lower))
                    or (d_name and normalize_bengali_text(d_name.lower()) in normalize_bengali_text(mz_lower))
                    or (u_name and normalize_bengali_text(mz_clean) == normalize_bengali_text(u_name))):
                params["mouza"] = None

        # Check if the query is a general law/process FAQ/survey concept question without specific DB filters
        has_specific_db_filter = bool(
            params.get("owner_name") or params.get("khatian_no") or params.get("dag_no") or params.get("jl_number")
            or params.get("mouza") or params.get("upazila") or params.get("district")
        )
        faq_kw = ['ই-নামজারি', 'ফি কত', 'সরকারি ফি', 'সময়সীমা কত', 'আবেদনের নিয়ম', 'আবেদনের নিয়ম',
                  'ট্রাইব্যুনালে আবেদনের', 'কাগজপত্র কি', 'কাগজপত্র কি কি', 'mutation fee', 'rectification procedure', 'e-mutation',
                  'ki', 'কী', 'ki?', 'কী?', 'mane ki', 'মানে কি', 'kake bole', 'কাকে বলে', 'what is', 'what are',
                  'difference', 'diff', 'পার্থক্য', 'অমিল', 'ইতিহাস', 'history', 'আইনি ভিত্তি']
        is_faq_q = any(kw in query.lower() for kw in faq_kw)

        if (extracted.get("intent") in ["general_question", "general_inquiry"] or is_faq_q) and not has_specific_db_filter:
            params["intent"] = "general_question"

        is_general_q = params.get("intent") == "general_question"
        is_list_req = params.get("intent") == "list_all" or params.get("is_mouza_list_request") or params.get("is_upazila_list_request")

        query_lower_full = query.lower()
        topic_reset = _is_topic_reset(query_lower_full)

        location_keywords = [
            'location', 'lokeshon', 'loakshan', 'লোকেশন', 'অবস্থান', 'কোথায়', 'কোথায়', 'map', 'ম্যাপ', 'পিন', 'pin', 'dekhao', 'দেখাও', 'দেখান',
            'tar', 'onar', 'tader', 'oi', 'oitar', 'sheitar', 'etar', 'his', 'her', 'their', 'its',
            'poriman', 'kototuku', 'koto tuku', 'koto jomi', 'total land', 'area',
            'পরিমাণ', 'কতটুকু', 'কত জমি', 'মোট জমি', 'তার', 'উনার', 'জমির'
        ]

        is_followup = not is_list_req and not is_general_q and (
            any(w in query_lower_full for w in location_keywords) or (
                not params.get("owner_name") and not params.get("khatian_no") and not params.get("dag_no")
                and not params.get("mouza") and not params.get("district") and not params.get("upazila")
                and not params.get("survey")
            )
        )

        if history and not topic_reset and not is_general_q:
            has_new_owner = bool(extracted.get("owner_name"))
            has_new_location = bool(extracted.get("mouza") or extracted.get("upazila") or extracted.get("district"))
            has_new_khatian = bool(extracted.get("khatian_no"))
            has_new_dag = bool(extracted.get("dag_no"))
            is_asking_owner = any(w in query_lower_full for w in ['মালিক', 'owner', 'malik', 'কার', 'who'])
            is_clarification = params.get("intent") == "clarification_reply"

            # If user asks a pronoun/follow-up question (e.g. "tar jomir poriman koto" or "jomir location dekhao"), inherit active khatian & location
            if is_followup:
                for turn in reversed(history):
                    prev_params = (turn.get("metadata") or {}).get("extracted_params") or {}
                    if not prev_params or prev_params.get("intent") == "general_question":
                        continue
                    if not params.get("khatian_no") and prev_params.get("khatian_no"):
                        params["khatian_no"] = prev_params["khatian_no"]
                    if not params.get("dag_no") and prev_params.get("dag_no"):
                        params["dag_no"] = prev_params["dag_no"]
                    if not params.get("survey") and prev_params.get("survey"):
                        params["survey"] = prev_params["survey"]
                        params["survey_type"] = prev_params["survey"]
                    if not params.get("owner_name") and prev_params.get("owner_name"):
                        params["owner_name"] = prev_params["owner_name"]
                        params["owner"] = prev_params["owner_name"]
                    if not params.get("mouza") and prev_params.get("mouza"):
                        params["mouza"] = prev_params["mouza"]
                    if not params.get("upazila") and prev_params.get("upazila"):
                        params["upazila"] = prev_params["upazila"]
                    if not params.get("district") and prev_params.get("district"):
                        params["district"] = prev_params["district"]
                    params["intent"] = "single_lookup"
                    break

            owner_inherited = False
            location_inherited = False

            for turn in reversed(history):
                prev_params = (turn.get("metadata") or {}).get("extracted_params") or {}
                if prev_params.get("intent") == "general_question":
                    continue

                is_option_selection = bool(
                    prev_params.get("owner_name") and
                    not prev_params.get("upazila") and
                    not prev_params.get("mouza")
                )
                allow_owner_despite_new_location = is_option_selection or is_clarification

                if not owner_inherited and not params["owner_name"] and prev_params.get("owner_name") and not is_list_req:
                    if not ((has_new_khatian or has_new_dag) and is_asking_owner):
                        if not has_new_location or allow_owner_despite_new_location:
                            params["owner_name"] = prev_params["owner_name"]
                            params["owner"] = prev_params["owner_name"]
                            owner_inherited = True

                if (not location_inherited and not has_new_location and not is_list_req
                        and not (params["mouza"] or params["upazila"] or params["district"])):
                    prev_has_location = prev_params.get("mouza") or prev_params.get("upazila") or prev_params.get("district")
                    if prev_has_location:
                        params["mouza"] = prev_params.get("mouza")
                        params["upazila"] = prev_params.get("upazila")
                        params["district"] = prev_params.get("district")
                        location_inherited = True

                if owner_inherited and (location_inherited or has_new_location):
                    break

        return params

    # Legacy alias for backward compatibility
    def extract_search_params(self, query):
        return self.extract_search_entities(query)

    # -------------------------------------------------------------------
    # STEP 2: STRUCTURED QUERY ENGINE
    # -------------------------------------------------------------------
    def search_upazila_list(self, district: str):
        """Query distinct upazilas in a given district."""
        conn = self._get_connection()
        if not conn or not district:
            return []
        upazilas = []
        try:
            with closing(conn):
                cursor = conn.cursor()
                d_vars = _generate_bengali_variants(district)
                clauses = ["district_name LIKE ?"] * len(d_vars)
                cursor.execute(
                    f"SELECT DISTINCT upazila_name FROM khatian_fts WHERE ({' OR '.join(clauses)}) AND upazila_name IS NOT NULL",
                    [f"%{v}%" for v in d_vars]
                )
                upazilas = [r[0] for r in cursor.fetchall() if r[0]]
        except Exception as e:
            logger.error("Error fetching upazila list: %s", e)
        return upazilas

    def search_mouza_list(self, district=None, upazila=None, limit=1000):
        conn = self._get_connection()
        if not conn:
            return {}

        grouped = {}
        try:
            with closing(conn):
                cursor = conn.cursor()
                query_sql = (
                    "SELECT json_extract(detail_json, '$.UPAZILA_NAME'), "
                    "json_extract(detail_json, '$.MOUZA_NAME'), "
                    "json_extract(detail_json, '$.JL_NUMBER'), "
                    "json_extract(detail_json, '$.DISTRICT_NAME'), COUNT(*) "
                    "FROM khatian_details WHERE 1=1"
                )
                sql_args = []

                if district:
                    d_vars = _generate_bengali_variants(district)
                    d_clauses = ["json_extract(detail_json, '$.DISTRICT_NAME') LIKE ?"] * len(d_vars)
                    query_sql += f" AND ({' OR '.join(d_clauses)})"
                    sql_args.extend([f"%{v}%" for v in d_vars])

                if upazila:
                    u_vars = _generate_bengali_variants(upazila)
                    u_clauses = ["json_extract(detail_json, '$.UPAZILA_NAME') LIKE ?"] * len(u_vars)
                    query_sql += f" AND ({' OR '.join(u_clauses)})"
                    sql_args.extend([f"%{v}%" for v in u_vars])

                query_sql += (
                    " GROUP BY json_extract(detail_json, '$.UPAZILA_NAME'), "
                    "json_extract(detail_json, '$.MOUZA_NAME') LIMIT ?"
                )
                sql_args.append(limit)

                cursor.execute(query_sql, sql_args)
                for u_name, m_name, jl, d_name, cnt in cursor.fetchall():
                    if not m_name:
                        continue
                    u_name = u_name or "অন্যান্য উপজেলা"
                    grouped.setdefault(u_name, []).append({
                        "mouza_name": m_name,
                        "jl_number": jl or "N/A",
                        "district_name": d_name or "N/A",
                        "total_khatians": cnt,
                    })
        except Exception as e:
            logger.error("Error fetching mouza list: %s", e)
        return grouped

    def search_records(self, params: dict, limit: int = 50):
        """Search khatian_details using FTS5 first, falling back to LIKE."""
        conn = self._get_connection()
        if not conn:
            return [], "Database not found."

        records = []
        try:
            with closing(conn):
                cursor = conn.cursor()
                self.ensure_fts_index()

                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='khatian_fts'")
                has_fts = cursor.fetchone() is not None

                owner_query = params.get("owner_name") or params.get("owner")
                khatian_no = params.get("khatian_no")
                dag_no = params.get("dag_no")
                mouza = params.get("mouza")
                upazila = params.get("upazila")
                district = params.get("district")
                survey = params.get("survey") or params.get("survey_type")

                mouza_search = mouza.strip() if mouza else None
                upazila_search = upazila.strip() if upazila else None
                district_search = district.strip() if district else None

                owner_token_groups = []
                owner_tokens = set()
                if owner_query:
                    norm_owner = normalize_bengali_text(owner_query)
                    for orig_token in re.split(r'\s+', norm_owner):
                        orig_token = orig_token.strip()
                        if len(orig_token) < 2:
                            continue
                        owner_tokens.add(orig_token)
                        variants = set([orig_token])
                        for v in list(variants):
                            if 'স' in v: variants.add(v.replace('স', 'ছ'))
                            if 'ছ' in v: variants.add(v.replace('ছ', 'স'))
                            if 'চ্ছ' in v: variants.add(v.replace('চ্ছ', 'ছ')); variants.add(v.replace('চ্ছ', 'স'))
                            if '্দু' in v: variants.add(v.replace('্দু', 'দু'))
                            if 'দু' in v: variants.add(v.replace('দু', '্দু'))
                            if 'ু' in v: variants.add(v.replace('ু', ''))
                            if 'নুদ' in v: variants.add(v.replace('নুদ', 'নদ্'))
                            if 'নদ্' in v: variants.add(v.replace('নদ্', 'নুদ'))
                            if 'মোহাম্মদ' in v: variants.add(v.replace('মোহাম্মদ', 'মহম্মদ')); variants.add(v.replace('মোহাম্মদ', 'মোঃ'))
                has_specific_target = bool(
                    mouza_search or khatian_no or dag_no or owner_token_groups
                    or upazila_search or district_search
                )

                if not has_specific_target:
                    return [], None

                if has_fts and has_specific_target:
                    fts_conditions = []
                    if khatian_no:
                        k_en = self.bn_to_en_digits(khatian_no)
                        k_bn = self.en_to_bn_digits(khatian_no)
                        fts_conditions.append(f'(khatian_no:"{_fts_escape(k_en)}" OR khatian_no:"{_fts_escape(k_bn)}")')
                    if mouza_search:
                        mz_tokens = [w for w in re.split(r'\s+', mouza_search) if len(w) >= 2]
                        if mz_tokens:
                            tok_clauses = []
                            for tok in mz_tokens:
                                v_list = _generate_bengali_variants(tok)
                                v_clauses = [f'mouza_name:"{_fts_escape(v)}"*' for v in v_list]
                                tok_clauses.append("(" + " OR ".join(v_clauses) + ")")
                            fts_conditions.append("(" + " AND ".join(tok_clauses) + ")")
                        else:
                            fts_conditions.append(f'mouza_name:"{_fts_escape(mouza_search)}"*')
                    if upazila_search:
                        u_tokens = [w for w in re.split(r'\s+', upazila_search) if len(w) >= 2]
                        if u_tokens:
                            tok_clauses = []
                            for tok in u_tokens:
                                v_list = _generate_bengali_variants(tok)
                                v_clauses = [f'upazila_name:"{_fts_escape(v)}"*' for v in v_list]
                                tok_clauses.append("(" + " OR ".join(v_clauses) + ")")
                            fts_conditions.append("(" + " AND ".join(tok_clauses) + ")")
                        else:
                            fts_conditions.append(f'upazila_name:"{_fts_escape(upazila_search)}"*')
                    if district_search:
                        d_tokens = [w for w in re.split(r'\s+', district_search) if len(w) >= 2]
                        if d_tokens:
                            tok_clauses = []
                            for tok in d_tokens:
                                v_list = _generate_bengali_variants(tok)
                                v_clauses = [f'district_name:"{_fts_escape(v)}"*' for v in v_list]
                                tok_clauses.append("(" + " OR ".join(v_clauses) + ")")
                            fts_conditions.append("(" + " AND ".join(tok_clauses) + ")")
                        else:
                            fts_conditions.append(f'district_name:"{_fts_escape(district_search)}"*')
                    if survey:
                        fts_conditions.append(f'survey_name:"{_fts_escape(survey)}"')
                    if dag_no:
                        d_en = self.bn_to_en_digits(dag_no)
                        d_bn = self.en_to_bn_digits(dag_no)
                        fts_conditions.append(f'(dags:"{_fts_escape(d_en)}"* OR dags:"{_fts_escape(d_bn)}"*)')
                    if owner_token_groups:
                        tok_and_clauses = []
                        for variants in owner_token_groups:
                            v_or_clauses = [f'owners:"{_fts_escape(v)}"*' for v in variants if len(v) >= 2]
                            if v_or_clauses:
                                tok_and_clauses.append("(" + " OR ".join(v_or_clauses) + ")")
                        if tok_and_clauses:
                            fts_conditions.append("(" + " AND ".join(tok_and_clauses) + ")")

                    match_clause = " AND ".join(fts_conditions)
                    try:
                        cursor.execute(
                            f"SELECT khatian_id FROM khatian_fts WHERE khatian_fts MATCH ? LIMIT {limit}",
                            (match_clause,)
                        )
                        matching_ids = [r[0] for r in cursor.fetchall()]
                        if matching_ids:
                            placeholders = ",".join("?" for _ in matching_ids)
                            cursor.execute(
                                f"SELECT khatian_id, jl_number_id, survey_name, detail_json "
                                f"FROM khatian_details WHERE khatian_id IN ({placeholders})",
                                matching_ids
                            )
                            for row in cursor.fetchall():
                                if row[3]:
                                    try:
                                        records.append({
                                            "khatian_id": row[0],
                                            "jl_number_id": row[1],
                                            "survey_name": row[2],
                                            "details": json.loads(row[3]),
                                        })
                                    except json.JSONDecodeError:
                                        pass
                    except sqlite3.OperationalError as fts_err:
                        logger.warning("FTS match query failed, falling back to LIKE: %s", fts_err)

                if not records and (mouza_search or khatian_no or dag_no or owner_token_groups or survey or upazila_search or district_search):
                    query_sql = "SELECT khatian_id, jl_number_id, survey_name, detail_json FROM khatian_details WHERE 1=1"
                    sql_args = []

                    if survey:
                        query_sql += " AND UPPER(survey_name) = UPPER(?)"
                        sql_args.append(survey)
                    if khatian_no:
                        k_en = self.bn_to_en_digits(khatian_no)
                        k_bn = self.en_to_bn_digits(khatian_no)
                        query_sql += " AND (json_extract(detail_json, '$.KHATIAN_NO') = ? OR json_extract(detail_json, '$.KHATIAN_NO') = ?)"
                        sql_args.extend([k_en, k_bn])
                    if mouza_search:
                        query_sql += " AND json_extract(detail_json, '$.MOUZA_NAME') LIKE ?"
                        sql_args.append(f'%{mouza_search}%')
                    if upazila_search:
                        query_sql += " AND json_extract(detail_json, '$.UPAZILA_NAME') LIKE ?"
                        sql_args.append(f'%{upazila_search}%')
                    if district_search:
                        query_sql += " AND json_extract(detail_json, '$.DISTRICT_NAME') LIKE ?"
                        sql_args.append(f'%{district_search}%')
                    if dag_no:
                        d_en = self.bn_to_en_digits(dag_no)
                        d_bn = self.en_to_bn_digits(dag_no)
                        query_sql += " AND (json_extract(detail_json, '$.DAGS') LIKE ? OR json_extract(detail_json, '$.DAGS') LIKE ?)"
                        sql_args.extend([f'%{d_en}%', f'%{d_bn}%'])
                    if owner_token_groups:
                        for variants in owner_token_groups:
                            v_clauses = ["json_extract(detail_json, '$.OWNERS') LIKE ?"] * len(variants)
                            query_sql += f" AND ({' OR '.join(v_clauses)})"
                            sql_args.extend(f'%{v}%' for v in variants)
                    elif owner_query:
                        query_sql += " AND json_extract(detail_json, '$.OWNERS') LIKE ?"
                        sql_args.append(f'%{owner_query}%')

                    query_sql += " LIMIT ?"
                    sql_args.append(limit)
                    cursor.execute(query_sql, sql_args)
                    for row in cursor.fetchall():
                        if row[3]:
                            try:
                                records.append({
                                    "khatian_id": row[0],
                                    "jl_number_id": row[1],
                                    "survey_name": row[2],
                                    "details": json.loads(row[3]),
                                })
                            except Exception:
                                pass

            if records and (owner_query or khatian_no or dag_no or mouza_search):
                if khatian_no:
                    requested_khatian = self.bn_to_en_digits(str(khatian_no))
                    records = [
                        r for r in records
                        if self.bn_to_en_digits(str(r.get('details', {}).get('KHATIAN_NO', ''))) == requested_khatian
                    ]
                if mouza_search:
                    mouza_variants = set(_generate_bengali_variants(mouza_search))
                    mouza_variants.add(_canonical_match_text(mouza_search))
                    records = [
                        r for r in records
                        if any(
                            _canonical_match_text(v) in _canonical_match_text(r.get('details', {}).get('MOUZA_NAME', ''))
                            or _canonical_match_text(r.get('details', {}).get('MOUZA_NAME', '')) in _canonical_match_text(v)
                            for v in mouza_variants
                        )
                    ]

                def score_record(r):
                    d = r.get('details', {})
                    score = 0
                    if owner_query:
                        owners_str = str(d.get('OWNERS', '')).lower()
                        norm_owners_str = normalize_bengali_text(owners_str)
                        if owner_query.lower() in owners_str or owner_query.lower() in norm_owners_str:
                            score -= 10
                        else:
                            tokens = [t for t in owner_tokens if len(t) > 1]
                            score -= sum(3 for t in tokens if t.lower() in owners_str or t.lower() in norm_owners_str)
                    if khatian_no and str(d.get('KHATIAN_NO', '')) == str(khatian_no):
                        score -= 10
                    if dag_no and str(dag_no) in str(d.get('DAGS', '')):
                        score -= 5
                    return score

                records.sort(key=score_record)

            # Only associate geometry if the record itself has a trustworthy mouza
            # code. A dag number is not globally unique across Bangladesh.
            if records:
                spatial_conn = self._get_connection()
                if spatial_conn:
                    with closing(spatial_conn) as spatial_conn:
                        existing = {row[0] for row in spatial_conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                        if {"plot_spatial_info", "plot_polygons"}.issubset(existing):
                            cursor = spatial_conn.cursor()
                            for r in records:
                                d = r.get("details", {})
                                mouza_code = d.get("MOUZA_CODE") or d.get("mauza_code")
                                dags = str(d.get("DAGS", ""))
                                dag = next((x.strip() for x in dags.replace("...", "").split(",") if x.strip()), None)
                                if not mouza_code or not dag:
                                    continue
                                cursor.execute("""
                                    SELECT s.major_class, s.sub_class, s.landuse_zone,
                                           s.center_lat, s.center_lon, p.geojson_geometry,
                                           s.mauza_code, s.plot_no
                                    FROM plot_spatial_info s
                                    LEFT JOIN plot_polygons p
                                      ON s.mauza_code = p.mauza_code AND s.plot_no = p.plot_no
                                    WHERE s.mauza_code = ? AND s.plot_no = ? LIMIT 1
                                """, (str(mouza_code), str(dag)))
                                row = cursor.fetchone()
                                if row:
                                    r["spatial_info"] = {
                                        "major_class": row[0], "sub_class": row[1],
                                        "landuse_zone": row[2], "center_lat": row[3],
                                        "center_lon": row[4],
                                        "geometry": json.loads(row[5]) if row[5] else None,
                                        "mauza_code": row[6], "plot_no": row[7],
                                    }

            return records, None
        except Exception as e:
            logger.error("search_records error: %s", e)
            return [], str(e)

    # -------------------------------------------------------------------
    # STEP 4: ANSWER SYNTHESIS
    # -------------------------------------------------------------------
    def query_gemini_api(self, prompt: str, system_instruction: str = "", history=None):
        if not self._api_key:
            return None

        contents = []
        if history:
            for msg in history[-6:]:
                role = "user" if msg.get("sender") == "user" else "model"
                text = msg.get("content", "")
                if text:
                    contents.append({"role": role, "parts": [{"text": text}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {"contents": contents}
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}

        try:
            r = requests.post(GEMINI_URL, params={"key": self._api_key}, json=payload, timeout=15)
            r.raise_for_status()
            return r.json()['candidates'][0]['content']['parts'][0]['text']
        except requests.RequestException as e:
            logger.warning("Gemini API call failed: %s", e)
        except (KeyError, IndexError) as e:
            logger.warning("Gemini API returned unexpected shape: %s", e)
        return None

    def synthesize_answer_fallback(self, user_query, params, records, knowledge_text, lang='bn', mouza_list_grouped=None, upazila_list=None):
        owner_name = params.get("owner_name") or params.get("owner")
        khatian_no = params.get("khatian_no")
        dag_no = params.get("dag_no")
        mouza = params.get("mouza")
        upazila = params.get("upazila")
        district = params.get("district")
        survey = params.get("survey") or params.get("survey_type")
        intent = params.get("intent", "single_lookup")

        if upazila_list:
            d_label = district or "উক্ত"
            if lang == 'bn':
                count_bn = self.en_to_bn_digits(str(len(upazila_list)))
                lines = [f"**{d_label}** জেলায় সর্বমোট **{count_bn}**টি উপজেলা পাওয়া গেছে:\n"]
                for idx, u in enumerate(upazila_list, 1):
                    lines.append(f"{self.en_to_bn_digits(str(idx))}. **{u}** উপজেলা")
                return "\n".join(lines)
            else:
                lines = [f"Found **{len(upazila_list)}** upazila(s) in **{d_label}** district:\n"]
                for idx, u in enumerate(upazila_list, 1):
                    lines.append(f"{idx}. **{u} Upazila**")
                return "\n".join(lines)

        if mouza_list_grouped:
            total_mouzas = sum(len(m_list) for m_list in mouza_list_grouped.values())
            loc_label = upazila or district or "উক্ত এলাকা"
            if lang == 'bn':
                count_bn = self.en_to_bn_digits(str(total_mouzas))
                lines = [f"**{loc_label}** এলাকায় সর্বমোট **{count_bn}**টি মৌজা পাওয়া গেছে:\n"]
                idx = 1
                for u_name, m_list in mouza_list_grouped.items():
                    for m in m_list:
                        m_name = m.get("mouza_name", "")
                        jl_no = self.en_to_bn_digits(str(m.get("jl_number", "N/A")))
                        cnt_bn = self.en_to_bn_digits(str(m.get("total_khatians", 0)))
                        lines.append(f"{self.en_to_bn_digits(str(idx))}. **{m_name}** মৌজা (জেএল নং: {jl_no}, সর্বমোট খতিয়ান: {cnt_bn}টি)")
                        idx += 1
                return "\n".join(lines)
            else:
                count_en = self.bn_to_en_digits(str(total_mouzas))
                lines = [f"Found **{count_en}** mouza(s) in **{loc_label}**:\n"]
                idx = 1
                for u_name, m_list in mouza_list_grouped.items():
                    for m in m_list:
                        m_name = m.get("mouza_name", "")
                        jl_no = self.bn_to_en_digits(str(m.get("jl_number", "N/A")))
                        cnt_en = self.bn_to_en_digits(str(m.get("total_khatians", 0)))
                        lines.append(f"{idx}. **{m_name} Mouza** (JL No: {jl_no}, Total Khatians: {cnt_en})")
                        idx += 1
                return "\n".join(lines)

        if not records:
            if knowledge_text and (intent == "general_question" or not (owner_name or khatian_no or dag_no or mouza or upazila or district)):
                return knowledge_text

            loc = mouza or upazila or district
            loc_str = f" in {loc}" if (loc and lang == 'en') else (f" ({loc} এলাকায়)" if (loc and lang == 'bn') else "")
            if lang == 'bn':
                if owner_name:
                    return (f"এই নামে ({owner_name}){loc_str} কোনো রেকর্ড খুঁজে পাইনি। নামের বানান বা এলাকা "
                            f"(উপজেলা/জেলা) একটু নিশ্চিত করে দিলে আবার খুঁজে দেখতে পারি।")
                return (f"এই তথ্যের ভিত্তিতে{loc_str} কোনো রেকর্ড খুঁজে পাইনি। অনুগ্রহ করে নামের বানান, এলাকা "
                        f"(উপজেলা/জেলা), অথবা সঠিক দাগ/খতিয়ান নম্বর উল্লেখ করে আবার চেষ্টা করুন।")
            return (f"No record was found for '{owner_name if owner_name else user_query}'{loc_str}. "
                    f"Please check the spelling or provide the specific upazila/district/mouza/dag number "
                    f"to refine the search.")

        if any(w in user_query.lower() for w in ['পরিমাণ', 'মোট জমি', 'কত জমি', 'কতটুকু', 'poriman', 'total area', 'area', 'koto tuku', 'kototuku', 'koto jomi', 'how much']):
            rec = records[0]['details']
            tot_land = rec.get("TOTAL_LAND")
            if not tot_land:
                k_no = rec.get("KHATIAN_NO")
                dags = rec.get("DAGS", "N/A")
                if lang == 'bn':
                    return (f"এই খতিয়ানে মোট জমির পরিমাণ রেকর্ড করা নেই। তবে দাগ নম্বর {self.en_to_bn_digits(str(dags))}সহ কয়েকটি দাগ "
                            f"এই খতিয়ানের (নং {self.en_to_bn_digits(str(k_no))}) অন্তর্ভুক্ত — চাইলে প্রতিটি "
                            f"দাগের তথ্য আলাদাভাবে দেখাতে পারি।")
                return (f"The total land area is not recorded for this khatian (Khatian No. {self.bn_to_en_digits(str(k_no))}). "
                        f"However, it includes plot/dag number(s) {self.bn_to_en_digits(str(dags))} — we can inspect individual "
                        f"plot records if needed.")

        # A district or upazila alone is not specific enough when the same
        # owner/khatian/dag appears in multiple mouzas. Only a mouza resolves
        # that location ambiguity.
        if not mouza:
            unique_locations = []
            for r in records:
                d = r['details']
                loc_tuple = (d.get('DISTRICT_NAME', ''), d.get('UPAZILA_NAME', ''), d.get('MOUZA_NAME', ''))
                if loc_tuple not in unique_locations:
                    unique_locations.append(loc_tuple)

            if len(unique_locations) > 1:
                if owner_name:
                    item_label = f"**{owner_name}** নামে"
                elif dag_no:
                    item_label = f"**দাগ নম্বর {self.en_to_bn_digits(str(dag_no))}**"
                elif khatian_no:
                    item_label = f"**খতিয়ান নম্বর {self.en_to_bn_digits(str(khatian_no))}**"
                else:
                    item_label = "**আপনার বর্ণিত রেকর্ডের**"

                if lang == 'bn':
                    loc_items = [f"• **{dist} জেলা**, **{upa} উপজেলা** ({mz} মৌজা)" for dist, upa, mz in unique_locations[:3]]
                    return (f"{item_label} একাধিক এলাকায় রেকর্ড পাওয়া যাচ্ছে। নিচে সম্ভাব্য কয়েকটি স্থানের "
                            f"তালিকা দেওয়া হলো:\n\n" + "\n".join(loc_items) +
                            "\n\nআপনি কোন জেলা, উপজেলা বা মৌজার রেকর্ড দেখতে চান?")
                loc_items = [f"• **{dist} District**, **{upa} Upazila** ({mz} Mouza)" for dist, upa, mz in unique_locations[:3]]
                return (f"Multiple records were found for {item_label} across different locations:\n\n" +
                        "\n".join(loc_items) + "\n\nPlease specify which district, upazila, or mouza you would like to inspect.")

        if intent == "list_all" or "সব জমি" in user_query or "list" in user_query.lower() or "talika" in user_query.lower() or "তালিকা" in user_query:
            count = len(records)
            loc_label = mouza or upazila or district or 'উক্ত এলাকা'
            count_str = self.en_to_bn_digits(str(count)) if lang == 'bn' else self.bn_to_en_digits(str(count))
            if count <= 10:
                if lang == 'bn':
                    lines = [f"**{loc_label}** এলাকায় সর্বমোট {count_str}টি খতিয়ান রেকর্ড পাওয়া গেছে:\n"]
                    for idx, r in enumerate(records, 1):
                        d = r['details']
                        idx_bn = self.en_to_bn_digits(str(idx))
                        k_no_bn = self.en_to_bn_digits(str(d.get('KHATIAN_NO', '')))
                        lines.append(f"{idx_bn}. **মালিক:** {d.get('OWNERS', 'N/A')} | **খতিয়ান নং:** "
                                      f"{k_no_bn} | **মৌজা:** {d.get('MOUZA_NAME', 'N/A')}")
                    return "\n".join(lines)
                lines = [f"Found {count_str} khatians in **{loc_label}**:\n"]
                for idx, r in enumerate(records, 1):
                    d = r['details']
                    k_no_en = self.bn_to_en_digits(str(d.get('KHATIAN_NO', '')))
                    lines.append(f"{idx}. **Owner:** {d.get('OWNERS', 'N/A')} | **Khatian No:** {k_no_en} | **Mouza:** {d.get('MOUZA_NAME', 'N/A')}")
                return "\n".join(lines)

            mouza_sample = records[0]['details'].get('MOUZA_NAME', 'বিভিন্ন')
            survey_sample = records[0]['details'].get('SURVEY_NAME', 'RS')
            if lang == 'bn':
                lines = [f"**{loc_label}** এলাকায় সর্বমোট {count_str}টিরও বেশি খতিয়ান রেকর্ড পাওয়া গেছে "
                         f"(যেমন {mouza_sample} মৌজা, {survey_sample} জরিপ):\n"]
                for idx, r in enumerate(records[:10], 1):
                    d = r['details']
                    idx_bn = self.en_to_bn_digits(str(idx))
                    k_no_bn = self.en_to_bn_digits(str(d.get('KHATIAN_NO', '')))
                    lines.append(f"{idx_bn}. **মালিক:** {d.get('OWNERS', 'N/A')} | **খতিয়ান নং:** "
                                  f"{k_no_bn} | **মৌজা:** {d.get('MOUZA_NAME', 'N/A')}")
                lines.append("\n💡 *তালিকায় প্রথম ১০টি রেকর্ড প্রদর্শিত হয়েছে। নির্দিষ্ট কোনো মালিক বা খতিয়ান "
                              "নম্বর দিয়ে অনুসন্ধান করে স্পষ্ট তথ্য পেতে পারেন।*" )
                return "\n".join(lines)
            return f"A total of {count_str} khatians were found in **{loc_label}** across multiple mouzas (e.g. {mouza_sample} mouza). Showing top records."

        if len(records) > 1 and not survey and ("মালিকানা" in user_query or "বদলেছে" in user_query or "difference" in user_query.lower()):
            cs_row = next((r['details'] for r in records if r.get('survey_name') == 'CS' or r['details'].get('SURVEY_NAME') == 'CS'), None)
            rs_row = next((r['details'] for r in records if r.get('survey_name') == 'RS' or r['details'].get('SURVEY_NAME') == 'RS'), None)
            if cs_row and rs_row:
                if lang == 'bn':
                    return (f"সিএস (CS) জরিপ অনুযায়ী এই দাগের মালিক ছিলেন {cs_row.get('OWNERS', 'N/A')}। আরএস (RS) "
                            f"জরিপে একই দাগের জন্য ভিন্ন মালিকানা তথ্য পাওয়া যাচ্ছে — অর্থাৎ সময়ের সাথে মালিকানা "
                            f"পরিবর্তনের সম্ভাবনা আছে। বিস্তারিত কোন জরিপ অনুযায়ী দেখতে চান?")
                return (f"According to the CS survey, the owner was {cs_row.get('OWNERS')}. However, the RS survey "
                        f"records a different owner ({rs_row.get('OWNERS')}), indicating ownership change over time. "
                        f"Which survey details would you like to inspect?")

        rec = records[0]['details']
        k_no = rec.get("KHATIAN_NO", "")
        owners = rec.get("OWNERS", "N/A")
        dags = rec.get("DAGS", "N/A")
        m_name = rec.get("MOUZA_NAME", "N/A")
        u_name = rec.get("UPAZILA_NAME", "N/A")
        d_name = rec.get("DISTRICT_NAME", "N/A")
        jl_no = rec.get("JL_NUMBER", "N/A")
        survey_type = rec.get("SURVEY_NAME") or records[0].get("survey_name", "CS")

        if lang == 'en':
            return (f"In {u_name} upazila, mouza {m_name}, dag no. {self.bn_to_en_digits(str(dags))} is recorded under {owners}'s "
                    f"khatian (khatian no. {self.bn_to_en_digits(str(k_no))}, {survey_type} survey), JL number {self.bn_to_en_digits(str(jl_no))}, {d_name} district.")
        return (f"{u_name} উপজেলার {m_name} মৌজায় {owners} এর নামে একটি {survey_type} খতিয়ান "
                f"(নং {self.en_to_bn_digits(str(k_no))}) আছে। এই খতিয়ানের দাগ নম্বর "
                f"{self.en_to_bn_digits(str(dags))}সহ আরও কয়েকটি দাগ এর অন্তর্ভুক্ত। এটি জেএল নম্বর "
                f"{self.en_to_bn_digits(str(jl_no))}-এর অধীনে, {d_name} জেলায়।")

    def generate_followup_pills(self, user_query, params, records_or_mouza, knowledge_text, lang='bn'):
        pills = []

        if isinstance(records_or_mouza, dict) and records_or_mouza:
            all_items = [(m['mouza_name'], u_name) for u_name, m_list in records_or_mouza.items() for m in m_list]
            for m_name, u_name in all_items[:3]:
                if lang == 'bn':
                    pills.append(f"{m_name} মৌজার খতিয়ান ও বিবরণ ({u_name})")
                else:
                    pills.append(f"Khatian Details for {m_name} Mouza ({u_name})")
            return pills[:3]

        records = records_or_mouza if isinstance(records_or_mouza, list) else []
        if records:
            rec0 = records[0].get('details', records[0])
            mouza = rec0.get("MOUZA_NAME", rec0.get("mouza_name", ""))
            u_name = rec0.get("UPAZILA_NAME", rec0.get("upazila_name", ""))
            k_no0 = rec0.get("KHATIAN_NO", params.get("khatian_no", ""))
            owner0 = rec0.get("OWNERS", "")

            other_khatians = [r.get('details', r).get("KHATIAN_NO") for r in records if r.get('details', r).get("KHATIAN_NO")]

            if lang == 'bn':
                if k_no0:
                    pills.append(f"{mouza} মৌজার খতিয়ান {self.en_to_bn_digits(str(k_no0))} এর জমি নামজারি নিয়ম")
                if len(other_khatians) > 1 and other_khatians[1]:
                    pills.append(f"{mouza} মৌজার খতিয়ান {self.en_to_bn_digits(str(other_khatians[1]))} এর বিবরণ")
                elif owner0 and len(owner0) > 3:
                    pills.append(f"{owner0.split(',')[0].strip()} এর নামের জমি খতিয়ান")
                else:
                    pills.append(f"{mouza} মৌজার সিএস ও আরএস রেকর্ড")
                pills.append(f"{mouza} মৌজার অন্যান্য খতিয়ান রেকর্ড ({u_name})")
            else:
                if k_no0:
                    pills.append(f"e-Mutation procedure for Khatian {self.bn_to_en_digits(str(k_no0))} in {mouza}")
                if len(other_khatians) > 1 and other_khatians[1]:
                    pills.append(f"Details for Khatian {self.bn_to_en_digits(str(other_khatians[1]))} in {mouza}")
                else:
                    pills.append(f"CS and RS records for {mouza} Mouza")
                pills.append(f"Other Khatians in {mouza} Mouza ({u_name})")

            return pills[:3]

        if lang == 'bn':
            return [
                "ই-নামজারির সরকারি ফি ও সময়সীমা কত?",
                "সিএস ও আরএস খতিয়ানে মিল না থাকলে কি করণীয়?",
                "খতিয়ান ভুল সংশোধন ট্রাইব্যুনালে আবেদনের নিয়ম",
            ]
        return [
            "What are the official fees for e-Mutation?",
            "What to do if CS and RS records do not match?",
            "Procedure for rectifying Khatian errors",
        ]

    def process_query(self, user_query: str, conversation_history=None, override_params=None):
        # Auto-detect if user typed GPS coordinates in chat (e.g. "Latitude: 24.0608, Longitude: 91.1324" or "24.0608, 91.1324")
        coord_match = re.search(r'(?:lat(?:itude)?\s*[:=]?\s*)?([12]\d\.\d+)[^\d]+?(?:lon(?:gitude)?|lng\s*[:=]?\s*)?([89]\d\.\d+)', user_query, re.IGNORECASE)
        if coord_match and not override_params:
            try:
                lat_val = float(coord_match.group(1))
                lon_val = float(coord_match.group(2))
                if 20.0 <= lat_val <= 27.0 and 88.0 <= lon_val <= 94.0:
                    return self.process_spatial_location_query(lat_val, lon_val, conversation_history=conversation_history)
            except Exception as e:
                logger.warning("Coordinate extraction error: %s", e)

        lang = self.detect_language(user_query)

        out_of_scope, oos_info = is_out_of_scope(user_query)
        if out_of_scope:
            if lang == 'bn':
                answer = (
                    "👋 **আমি বাংলাদেশ ভূমি রেকর্ড ও সম্পত্তি আইন সংক্রান্ত এআই সহকারী।**\n\n"
                    f"আপনার প্রশ্নটি (**'{user_query}'**) ভূমি বা জমি সংক্রান্ত বিষয়ের বাইরে। "
                    "আমি আপনাকে খতিয়ান রেকর্ড অনুসন্ধান, নামজারি আবেদন প্রক্রিয়া, দাগ নম্বর, মৌজা ও ভূমি আইন সংক্রান্ত তথ্যে সাহায্য করতে পারি।\n\n"
                    "💡 **আপনি নিচের যেসকল বিষয়ে অনুসন্ধান করতে পারেন:**\n"
                    "- 📜 **খতিয়ান ও মালিকানার তথ্য:** যেমন: *'ভাট বাড়ীয়া মৌজার খতিয়ান ৩ এর মালিক কে?'*\n"
                    "- 📝 **ই-নামজারি (e-Mutation):** আবেদন করার নিয়ম, সরকারি ফি ও প্রয়োজনীয় কাগজপত্র\n"
                    "- 🔍 **সার্ভে সংক্রান্ত:** CS, RS, SA ও BS খতিয়ানের পার্থক্য ও আইনি মান\n"
                    "- ⚖️ **আইনি পরামর্শ:** খতিয়ান ভুল সংশোধন বা সিএস-আরএস অমিল সমাধান"
                )
            else:
                answer = (
                    "👋 **I am your AI Assistant for Bangladesh Land Records & Property Law.**\n\n"
                    f"Your request (**'{user_query}'**) appears to be outside the scope of Bangladesh land & real estate domain. "
                    "I am specifically trained to assist with Land Record searches (CS/RS/BS Khatians), e-Mutation procedures, Plot/Dag ownership, and Property Laws.\n\n"
                    "💡 **Here are some topics you can ask me about:**\n"
                    "- 📜 **Record Lookup:** *'Who is the owner of Khatian 3 in Bhat Baria Mouza?'*\n"
                    "- 📝 **e-Mutation (ই-নামজারি):** Process, current official fees (verify on the government portal), and required documents\n"
                    "- 🔍 **Survey Differences:** Comparison of CS, RS, SA, and BRS surveys\n"
                    "- ⚖️ **Dispute Resolution:** How to rectify Khatian errors or missing names"
                )

            pills = oos_info.get("suggested_topics", [
                "ভাট বাড়ীয়া মৌজার খতিয়ান ৩",
                "ই-নামজারির ফি ও নিয়ম",
                "CS ও RS খতিয়ানের পার্থক্য"
            ]) if lang == 'bn' else [
                "Owner of Khatian 3 in Bhat Baria",
                "e-Mutation fees & procedure",
                "Difference between CS and RS"
            ]

            return {
                "answer": answer,
                "is_out_of_scope": True,
                "records_found": 0,
                "records": [],
                "clarification_options": pills
            }

        # Step 1: Extract Search Entities
        params = self.extract_search_entities(user_query, history=conversation_history)
        if override_params:
            for k, v in override_params.items():
                if v is not None:
                    params[k] = v

        # Handle Upazila / Mouza Listing Queries
        mouza_list_grouped = {}
        upazila_list = []
        if params.get("is_upazila_list_request") and params.get("district"):
            upazila_list = self.search_upazila_list(params.get("district"))
        elif params.get("intent") == "list_all" and (params.get("district") or params.get("upazila")) and not params.get("mouza") and not params.get("owner_name") and not params.get("dag_no") and not params.get("khatian_no"):
            mouza_list_grouped = self.search_mouza_list(district=params.get("district"), upazila=params.get("upazila"), limit=1000)

        # Step 2: Structured Query against Database
        records = []
        if not mouza_list_grouped and not upazila_list and params.get("intent") != "general_question":
            records, err = self.search_records(params, limit=50)

        knowledge_text = retrieve_relevant_knowledge(user_query)

        # Step 3 & 4: Answer Synthesis with Zero-Hallucination Grounding
        has_data = bool(records or mouza_list_grouped or upazila_list or knowledge_text)

        # Direct Zero-Hallucination Gate: If no records and no domain knowledge match, DO NOT hallucinate via LLM
        if not has_data and params.get("intent") != "general_question":
            ai_answer = self.synthesize_answer_fallback(
                user_query, params, [], "", lang,
                mouza_list_grouped=mouza_list_grouped,
                upazila_list=upazila_list
            )
            return {
                "answer": ai_answer,
                "is_out_of_scope": False,
                "extracted_params": params,
                "records_found": 0,
                "records": [],
                "clarification_options": self.generate_followup_pills(user_query, params, [], "", lang)
            }

        system_instruction = (
            "You are a precise, friendly, and trustworthy AI Land Records Assistant for Bangladesh (বাংলাদেশ ভূমি রেকর্ড সহায়তাকারী).\n\n"
            "## ABSOLUTE GROUNDING RULES:\n"
            "1. You must answer using ONLY the retrieved database records and context provided below. Never invent, hallucinate, or extrapolate facts, names, khatian numbers, or plot numbers not present in the records.\n"
            "2. If the user is asking a general definition, legal, or concept question (e.g. 'what is BS record', 'CS khatian ki', 'rules for e-mutation'), answer the question directly using the domain knowledge context. Do NOT invent, assume, or attach random mouzas, plots, or khatian numbers.\n"
            "3. If there are NO database records provided below for a requested Dag number, Khatian number, or Person, you MUST plainly and directly state that no matching record exists in the database. NEVER invent hypothetical names, fictitious khatian numbers (e.g., do NOT invent numbers like 3372 or 405), or imagined co-owners.\n"
            "4. If any field (such as total land area) is null or missing, state plainly that total area is not recorded in this official survey.\n"
            "5. Match the user's language: if written in Banglish or Bengali, reply in natural Bengali script. If in English, reply in English keeping Bengali terms (মৌজা, দাগ, খতিয়ান).\n"
            "6. If a specific mouza was requested (or if only records for one mouza are provided), directly answer about that specific mouza. Only list alternative candidate locations if no location was specified at all and multiple locations matched.\n"
            "7. For bulk/list requests, state total count. If count is small (<=10), list them briefly. If large, summarize and offer to narrow down. Never claim full list if truncated.\n"
            "8. Never use raw internal field names like JL_NUMBER_ID or IS_LOCKED.\n"
            "9. When the user asks a follow-up question (e.g., using pronouns like 'tar', 'onar', 'his', 'her' or following up on a specific owner), use the exact retrieved database records provided below."
        )

        grounding_context = ""
        if upazila_list:
            grounding_context += f"### Upazilas Available in {params.get('district')}:\n" + json.dumps(upazila_list, ensure_ascii=False) + "\n\n"
        if mouza_list_grouped:
            grounding_context += f"### Mouzas Available in Area:\n" + json.dumps(mouza_list_grouped, ensure_ascii=False, indent=2) + "\n\n"
        if records and params.get("intent") != "general_question":
            grounding_context += f"### Retrieved Database Records ({len(records)} found):\n" + json.dumps(records, ensure_ascii=False, indent=2) + "\n\n"
        if knowledge_text:
            grounding_context += f"### Domain Knowledge Base Context:\n{knowledge_text}\n\n"

        prompt = (
            f"User Question: {user_query}\n"
            f"Extracted Entities: {json.dumps(params, ensure_ascii=False)}\n\n"
            f"{grounding_context}\n"
            "Provide a natural, conversational answer using strictly the retrieved records and context above."
        )

        gemini_response = self.query_gemini_api(prompt, system_instruction=system_instruction, history=conversation_history)

        if gemini_response:
            ai_answer = gemini_response
        else:
            ai_answer = self.synthesize_answer_fallback(user_query, params, records, knowledge_text, lang, mouza_list_grouped=mouza_list_grouped, upazila_list=upazila_list)

        pills = self.generate_followup_pills(user_query, params, records if records else mouza_list_grouped, knowledge_text, lang)
        if upazila_list:
            pills = [f"{u} উপজেলা er mouza list" for u in upazila_list[:3]]

        # Clean card payload: for list requests, attach up to 10 record cards!
        card_records = []
        if records and params.get("intent") != "general_question":
            if params.get("intent") == "list_all" or params.get("is_mouza_list_request"):
                card_records = records[:10]
            elif params.get("owner_name") or params.get("khatian_no") or params.get("dag_no"):
                card_records = records[:1]
            else:
                card_records = records[:5]

        return {
            "answer": ai_answer,
            "is_out_of_scope": False,
            "extracted_params": params,
            "records_found": len(records) if records else sum(len(m) for m in mouza_list_grouped.values()),
            "records": card_records,
            "clarification_options": pills
        }

    def process_spatial_location_query(self, lat: float, lon: float, conversation_history=None,
                                       mauza_code=None, plot_no=None, district_name=None,
                                       upazila_name=None, mouza_name=None, custom_prompt=None):
        """
        Reverse-geocodes a dropped map pin (lat, lon) to spatial plot metadata.
        Uses exact clicked/selected Mouza and Plot metadata if provided from the active map view,
        or calculates nearest plot in khatians.db with distance thresholding.
        """
        matched_plot = str(plot_no).strip() if plot_no not in (None, '', 'N/A', 'undefined', 'null') else None
        matched_mauza_code = str(mauza_code).strip() if mauza_code not in (None, '', 'N/A', 'undefined', 'null') else None
        major_class = "আবাদী জমি"
        sub_class = "কৃষি"
        landuse_zone = "কৃষি অঞ্চল"

        # If plot is not explicitly provided, try local spatial index with distance check
        if not (matched_plot and matched_mauza_code):
            with closing(self._get_connection()) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT mauza_code, plot_no, major_class, sub_class, landuse_zone, center_lat, center_lon,
                           ((center_lat - ?)*(center_lat - ?) + (center_lon - ?)*(center_lon - ?)) AS dist
                    FROM plot_spatial_info
                    ORDER BY dist ASC
                    LIMIT 1
                """, (lat, lat, lon, lon))
                row = cursor.fetchone()

            if row:
                m_code, p_no, maj, sub, zone, c_lat, c_lon, dist = row
                # Check distance threshold (~0.05 degrees, approx 5km)
                if dist <= 0.005:
                    matched_mauza_code = matched_mauza_code or m_code
                    matched_plot = matched_plot or p_no
                    major_class = maj or major_class
                    sub_class = sub or sub_class
                    landuse_zone = zone or landuse_zone

        # If mouza_name is missing but matched_mauza_code is known, resolve mouza name from DB
        if not mouza_name and matched_mauza_code:
            try:
                jl_suffix = str(int(matched_mauza_code[-3:])) if matched_mauza_code[-3:].isdigit() else None
                with closing(self._get_connection()) as conn:
                    cursor = conn.cursor()
                    if jl_suffix:
                        cursor.execute("""
                            SELECT json_extract(detail_json, '$.MOUZA_NAME'), json_extract(detail_json, '$.UPAZILA_NAME'), json_extract(detail_json, '$.DISTRICT_NAME')
                            FROM khatian_details
                            WHERE json_extract(detail_json, '$.JL_NO') = ? AND json_extract(detail_json, '$.UPAZILA_NAME') = 'সরাইল'
                            LIMIT 1
                        """, (jl_suffix,))
                        m_row = cursor.fetchone()
                        if m_row:
                            mouza_name = m_row[0]
                            upazila_name = upazila_name or m_row[1]
                            district_name = district_name or m_row[2]
            except Exception as e:
                logger.warning("Error resolving mouza from code: %s", e)

        # Clean mouza name (strip numeric prefixes like '069-')
        clean_mouza = mouza_name
        if clean_mouza:
            clean_mouza = re.sub(r'^\d+[\s\-_]*', '', clean_mouza).strip()

        # Construct specific location query for RAG
        loc_parts = []
        if district_name: loc_parts.append(f"{district_name} জেলার")
        if upazila_name: loc_parts.append(f"{upazila_name} উপজেলার")
        if clean_mouza: loc_parts.append(f"{clean_mouza} মৌজায়")
        location_clause = " ".join(loc_parts)

        # Sanitize custom_prompt to remove any literal 'N/A' dag references
        clean_custom_prompt = custom_prompt
        if clean_custom_prompt:
            clean_custom_prompt = clean_custom_prompt.replace("দাগ নম্বর N/A এর ", "").replace("দাগ নম্বর N/A ", "")

        if clean_custom_prompt:
            query = f"{location_clause} {clean_custom_prompt}".strip()
        elif matched_plot and location_clause:
            query = f"{location_clause} দাগ নম্বর {matched_plot} এর বিবরণ ও মালিক কে?"
        elif matched_plot:
            query = f"দাগ নম্বর {matched_plot} এর বিবরণ ও মালিক কে?"
        elif location_clause:
            query = f"{location_clause} ভূমির শ্রেণী, সামগ্রিক রেকর্ড ও খতিয়ান সংক্রান্ত তথ্য দিন"
        else:
            query = f"ম্যাপ লোকেশন ({lat:.4f}, {lon:.4f}) এলাকার ভূমির বিবরণ ও তথ্য"

        # Explicitly lock spatial filter parameters to guarantee precision without multi-mouza confusion
        spatial_overrides = {}
        if district_name: spatial_overrides["district"] = district_name
        if upazila_name: spatial_overrides["upazila"] = upazila_name
        if clean_mouza: spatial_overrides["mouza"] = clean_mouza
        if matched_plot: spatial_overrides["dag_no"] = str(matched_plot)

        res = self.process_query(query, conversation_history=conversation_history, override_params=spatial_overrides)
        res["spatial_location"] = {
            "lat": lat,
            "lon": lon,
            "matched_plot": matched_plot,
            "mauza_code": matched_mauza_code,
            "major_class": major_class,
            "sub_class": sub_class,
            "landuse_zone": landuse_zone
        }

        if matched_plot:
            plot_header = f"🗺️ **দাগ নম্বর:** {matched_plot}" + (f" (মৌজা কোড: {matched_mauza_code})" if matched_mauza_code else "")
        else:
            plot_header = f"🗺️ **চিহ্নিত এলাকা:** {clean_mouza or mouza_name or 'মৌজা'}" + (f" (মৌজা কোড: {matched_mauza_code})" if matched_mauza_code else "")

        res["answer"] = (
            f"📍 **ম্যাপ পিন লোকেশন চিহ্নিত করা হয়েছে** (Latitude: {lat:.4f}, Longitude: {lon:.4f})\n\n"
            f"{plot_header}\n"
            f"🌾 **ভূমি শ্রেণী:** {major_class} ({sub_class}) - **অঞ্চল:** {landuse_zone}\n\n"
            f"{res['answer']}"
        )
        return res


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    rag = LandRecordRAG()
    res = rag.process_query("Sarail er Kartik Nath er jomir details din")
    print("Test Answer:\n", res["answer"])
    print("Follow-up Pills:\n", res["clarification_options"])