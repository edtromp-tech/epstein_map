import sqlite3
import re
from datasketch import MinHash, MinHashLSH
from difflib import SequenceMatcher
import hashlib
import logging
from pathlib import Path
from typing import List, Dict, Any
try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None



# ---------------------- CONFIG / CONSTANTS ---------------------- #

# PERSON_REGEX: matches first [middle initial] last name, excludes place name prefixes and street/city suffixes
PERSON_REGEX = re.compile(
    r"\b(?!New\b|North\b|South\b|East\b|West\b)"
    r"([A-Z][a-z]+ (?:[A-Z]\.? )?[A-Z][a-z]+)"
    r"\b(?!\s+(?:Street|St|Avenue|Ave|Road|Rd|Lane|Ln|Drive|Dr|Boulevard|Blvd|City|County|Province|State|privileged|district|region|States))"
)
ORG_REGEX = re.compile(r"\b([A-Z][A-Za-z]+ (Inc|LLC|Corp|Foundation|Institute|Agency))\b")
EMAIL_REGEX = re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w+\b")
URL_REGEX = re.compile(r"https?://\S+")

# Path to your database file
DB_PATH = "tools/epstein.db"

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("utilities")

# ---------------------- Utilities ---------------------- #
def extract_data(query: str):
    # Connect to the database
    conn = sqlite3.connect(DB_PATH)

    # This lets you access columns by name instead of index
    conn.row_factory = sqlite3.Row

    # Create a cursor
    cur = conn.cursor()

    # Run a query
    cur.execute(query)
    table = [dict(row) for row in cur.fetchall()]

    # Always close when done
    conn.close()

    return table

def find_pdfs(root: Path) -> List[Path]:
    pdfs = []
    for p in root.rglob("*.pdf"):
        if p.is_file():
            pdfs.append(p)
    return sorted(pdfs)

def normalize_text(text: str) -> str:
    text = text.replace("\n", " ")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)  # broken OCR joins
    return text.strip()

def similarity(a: str, b: str) -> float:
    """Fallback expensive similarity (SequenceMatcher) used only on LSH candidates."""
    if not a and not b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()

def sha256_file(path: Path, chunk_size: int = 8192) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()

def text_to_shingles(text: str, k: int = 3) -> List[str]:
    """Convert text into k-word shingles."""
    words = text.split()
    if len(words) < k:
        return [" ".join(words)] if words else []
    return [" ".join(words[i:i + k]) for i in range(len(words) - k + 1)]

def build_minhash(text: str, num_perm: int = 128) -> MinHash:
    m = MinHash(num_perm=num_perm)
    shingles = text_to_shingles(text, k=3)
    if not shingles:
        m.update(b"")
        return m
    for sh in shingles:
        m.update(sh.encode("utf-8"))
    return m 

def strip_middle_initial(name: str) -> str:
    """
    Remove middle initials like 'A.' or 'A' from names such as:
    'John A. Smith' -> 'John Smith'
    'Mary B Smith' -> 'Mary Smith'
    """
    parts = name.split()
    if len(parts) == 3:
        first, mid, last = parts
        if re.fullmatch(r"[A-Z]\.?", mid):
            return f"{first} {last}"
    return name

def score_person(candidate: str, known_name: str) -> float:
    return SequenceMatcher(None, candidate, known_name).ratio()

def extract_text_from_pdf(path: Path) -> str:
    """Extract textual content from PDF using PyPDF2. If unavailable, return empty string."""
    if PdfReader is None:
        return ""
    try:
        reader = PdfReader(str(path))
        texts = []
        for p in reader.pages:
            try:
                txt = p.extract_text() or ""
            except Exception:
                txt = ""
            texts.append(txt)
        return "\n".join(texts)
    except Exception as e:
        logger.debug(f"Failed to extract text from {path}: {e}")
        return ""
    

def similarity(a: str, b: str) -> float:
    """Fallback expensive similarity (SequenceMatcher) used only on LSH candidates."""
    if not a and not b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def find_pdfs(root: Path) -> List[Path]:
    pdfs = []
    for p in root.rglob("*.pdf"):
        if p.is_file():
            pdfs.append(p)
    return sorted(pdfs)

def find_index_people_in_text(text: str, people_index: list[dict]) -> list[str]:
    text_low = text.lower()
    hits = []

    for person in people_index:
        for known in person["names"]:
            if known.lower() in text_low:
                hits.append(known)
                break  # avoid duplicates if multiple aliases match

    return hits

def store_document_in_db(doc_id, canonical, text, entities):
    # canonical: dict with path, sha256, size, pages, etc.
    # entities: output of extract_entities_from_text()

    resolved = entities["people"]["resolved"]
    unresolved = entities["people"]["unresolved_clusters"]
    orgs = entities["organizations"]
    emails = entities["emails"]
    urls = entities["urls"]

    # Insert into documents table
    execute_sql("""
        INSERT OR IGNORE INTO documents (id, title, sha256, filePath, text)
        VALUES (?, ?, ?, ?, ?)
    """, (
        doc_id,
        canonical["path"].split("/")[-1].replace(".pdf", ""),
        canonical.get("sha256"),
        canonical["path"],
        text
    ))

    # Insert resolved people
    for p in resolved:
        execute_sql("""
            INSERT OR IGNORE INTO document_people (document_id, person_id, matched_name, confidence)
            VALUES (?, ?, ?, ?)
        """, (doc_id, p["id"], p["matchedName"], p["confidence"]))

    # Insert unresolved clusters
    for cluster in unresolved:
        execute_sql("""
            INSERT INTO unresolved_people (document_id, cluster)
            VALUES (?, ?)
        """, (doc_id, json.dumps(cluster)))

    # Insert orgs
    for o in orgs:
        execute_sql("""
            INSERT OR IGNORE INTO document_orgs (document_id, org_name)
            VALUES (?, ?)
        """, (doc_id, o))

    # Insert edges
    person_ids = [p["id"] for p in resolved if p["id"]]
    for i, p1 in enumerate(person_ids):
        for p2 in person_ids[i+1:]:
            execute_sql("""
                INSERT OR IGNORE INTO edges (document_id, source, target, relationship)
                VALUES (?, ?, ?, 'co_mentioned')
            """, (doc_id, p1, p2))
