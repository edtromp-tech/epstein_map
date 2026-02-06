#!/usr/bin/env python3
"""
find_duplicate_pdfs_lsh.py

Scan a directory tree for PDF files, compute exact hashes and MinHash-based
text similarity, then group exact duplicates, near-duplicates and partial duplicates.

Also:
- Extract entities from a canonical file per group/singleton
- Auto-generate doc.json, people.json, org.json, edges.json, ref.json
- Write unresolved person clusters to unresolved.json

Outputs a JSON report (default: assets/data/pdf_duplicates.json).

Requires: PyPDF2, datasketch
Install: pip install PyPDF2 datasketch
"""

import argparse
import hashlib
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
import re
import shutil
import copy
import numpy as np

try:
    from PyPDF2 import PdfReader
except Exception:
    PdfReader = None

from datasketch import MinHash, MinHashLSH
from difflib import SequenceMatcher

from utilities import extract_data,normalize_text, sha256_file, find_pdfs,strip_middle_initial, find_index_people_in_text, score_person, BAD_NAME_TERMS, BAD_LAST_NAMES, PERSON_REGEX, ORG_REGEX, EMAIL_REGEX, URL_REGEX, extract_text_from_pdf, similarity


logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("pdf-dedupe-lsh")



PEOPLE_INDEX = extract_data("SELECT * FROM people")


def canonicalize_person(name: str, people_index: list[dict], threshold: float = 0.85) -> dict:
    norm = normalize_text(strip_middle_initial(name))

    best_match = None
    best_score = 0.0

    for person in people_index:
        for known in person["names"]:
            score = score_person(norm, known)
            if score > best_score:
                best_score = score
                best_match = person

    if best_match and best_score >= threshold:
        return {
            "id": best_match["id"],
            "confidence": round(best_score, 3),
            "matchedName": name,
        }

    return {
        "id": None,
        "confidence": round(best_score, 3),
        "matchedName": name,
    }


def cluster_people(unresolved: list[str]) -> list[list[str]]:
    clusters: list[list[str]] = []

    for name in unresolved:
        placed = False
        for cluster in clusters:
            if score_person(name, cluster[0]) > 0.85:
                cluster.append(name)
                placed = True
                break

        if not placed:
            clusters.append([name])

    return clusters


def clean_people_list(people: list[str]) -> list[str]:
    cleaned = []
    for p in people:
        low = p.lower()
        if low in BAD_NAME_TERMS:
            continue
        cleaned.append(p)
    return cleaned


def filter_bad_lastnames(people: list[str]) -> list[str]:
    out = []
    for p in people:
        last = p.split()[-1].lower()
        if last in BAD_LAST_NAMES:
            continue
        out.append(p)
    return out

def extract_entities_from_text(text: str) -> dict:
    # raw regex hits
    raw_people = list(set(PERSON_REGEX.findall(text)))
    orgs = list(set(ORG_REGEX.findall(text)))
    emails = list(set(EMAIL_REGEX.findall(text)))
    urls = list(set(URL_REGEX.findall(text)))

    # find known people directly in text
    index_hits = find_index_people_in_text(text, PEOPLE_INDEX)

    

    # flatten org tuples
    orgs = [o[0] for o in orgs]

    # normalize / filter people before canonicalization
    cleaned_people = filter_bad_lastnames(clean_people_list([strip_middle_initial(p) for p in raw_people]))

    # combine both sources
    combined_people = list(set(cleaned_people + index_hits))

    resolved_people = []
    unresolved_people = []

    for name in combined_people:
        result = canonicalize_person(name, PEOPLE_INDEX)
        if result["id"]:
            resolved_people.append(result)
        else:
            unresolved_people.append(normalize_text(name))

    clustered_unresolved = cluster_people(unresolved_people)

    return {
        "people": {
            "resolved": resolved_people,
            "unresolved_clusters": clustered_unresolved,
        },
        "organizations": list(orgs),
        "emails": list(emails),
        "urls": list(urls),
    }


# ---------------------- MINHASH / LSH ---------------------- #

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


# ---------------------- CORE REPORT BUILDING ---------------------- #

def build_report(
    files: List[Path],
    near_thresh: float,
    partial_thresh: float,
    min_pages: int,
    lsh_threshold: float = 0.8,
    num_perm: int = 128,
) -> Dict[str, Any]:
    """
    Build a report of duplicate / similar PDFs using:
    - exact SHA-256 for exact duplicates
    - MinHash + LSH for candidate near/partial duplicates
    - SequenceMatcher only on LSH candidates
    """
    items: List[Dict[str, Any]] = []
    logger.info(f"Scanning {len(files)} PDF files...")

    # Basic metadata
    for p in files:
        try:
            size = p.stat().st_size
        except Exception:
            size = 0
        items.append(
            {
                "path": str(p),
                "name": p.name,
                "size": size,
                "sha256": None,
                "text": None,
                "pages": None,
                "minhash": None,  # will store list[int] for signature
            }
        )

    # Compute sha256, pages, text, and MinHash
    logger.info("Extracting text, hashes, and MinHash signatures...")
    for it in items:
        path = Path(it["path"])
        it["sha256"] = sha256_file(path)

        if PdfReader is not None:
            try:
                reader = PdfReader(str(path))
                it["pages"] = len(reader.pages)
            except Exception:
                it["pages"] = None
        else:
            it["pages"] = None

        text = extract_text_from_pdf(path)
        it["text"] = normalize_text(text)

        m = build_minhash(text, num_perm=num_perm)
        it["minhash"] = [int(x) for x in m.hashvalues]

    # Filter by min_pages if provided
    if min_pages > 0:
        before = len(items)
        items = [i for i in items if (i["pages"] or 0) >= min_pages]
        logger.info(f"Filtered by min pages >= {min_pages}: {before} -> {len(items)}")

    # Group exact duplicates by sha256
    groups: List[Dict[str, Any]] = []
    seen = set()
    sha_map: Dict[str, List[Dict[str, Any]]] = {}
    for it in items:
        sha_map.setdefault(it["sha256"], []).append(it)

    for sha, group in sha_map.items():
        if len(group) > 1:
            groups.append(
                {
                    "type": "exact",
                    "sha256": sha,
                    "files": [
                        {
                            "path": g["path"],
                            "size": g["size"],
                            "text": g.get("text"),
                            "sha256": g["sha256"],
                            "pages": g["pages"],
                            "minhash": g["minhash"],
                        }
                        for g in group
                    ],
                }
            )
            for g in group:
                seen.add(g["path"])

    # Remaining files for near/partial detection
    remaining = [it for it in items if it["path"] not in seen]
    n = len(remaining)
    logger.info(f"Building LSH index for {n} remaining files...")

    lsh = MinHashLSH(threshold=lsh_threshold, num_perm=num_perm)
    minhashes: Dict[str, MinHash] = {}

    for it in remaining:
        m = MinHash(num_perm=num_perm)
        m.hashvalues = np.array(it["minhash"], dtype=np.uint64)
        key = it["path"]
        minhashes[key] = m
        lsh.insert(key, m)

    logger.info("Querying LSH for candidate near-duplicates...")
    used_in_group = set()

    for it in remaining:
        key = it["path"]
        if key in used_in_group:
            continue

        m = minhashes[key]
        candidates = lsh.query(m)
        if key not in candidates:
            candidates.append(key)

        group_items = [x for x in remaining if x["path"] in candidates and x["path"] not in used_in_group]
        if len(group_items) <= 1:
            continue

        final_group = [group_items[0]]
        for cand in group_items[1:]:
            sim = similarity(group_items[0]["text"], cand["text"])
            if sim >= partial_thresh:
                final_group.append(cand)

        if len(final_group) > 1:
            max_sim = 0.0
            for a in final_group:
                for b in final_group:
                    if a is b:
                        continue
                    max_sim = max(max_sim, similarity(a["text"], b["text"]))
            gtype = "near" if max_sim >= near_thresh else "partial"

            groups.append(
                {
                    "type": gtype,
                    "files": [
                        {
                            "path": g["path"],
                            "size": g["size"],
                            "text": g.get("text"),
                            "sha256": g["sha256"],
                            "pages": g["pages"],
                            "minhash": g["minhash"],
                        }
                        for g in final_group
                    ],
                }
            )
            for g in final_group:
                used_in_group.add(g["path"])

    # Singletons
    singletons = [it for it in items if it["path"] not in seen and it["path"] not in used_in_group]

    report = {
        "summary": {
            "total_files": len(files),
            "scanned": len(items),
            "exact_groups": sum(1 for g in groups if g["type"] == "exact"),
            "near_groups": sum(1 for g in groups if g["type"] == "near"),
            "partial_groups": sum(1 for g in groups if g["type"] == "partial"),
            "singletons": len(singletons),
        },
        "groups": groups,
        "singletons": [
            {
                "path": s["path"],
                "size": s["size"],
                "text": s.get("text"),
                "sha256": s.get("sha256"),
                "pages": s.get("pages"),
                "minhash": s.get("minhash"),
            }
            for s in singletons
        ],
    }
    return report


# ---------------------- METADATA BUILDERS ---------------------- #

def build_mentions(resolved_people: list[dict]) -> list[str]:
    # Use canonical IDs for mentions
    return [p["id"] for p in resolved_people if p.get("id")]


def build_people_json(doc_id: str, resolved_people: list[dict]) -> dict:
    return {
        "document_id": doc_id,
        "people": [
            {
                "id": p["id"],
                "name": p["matchedName"].lower(),
                "type": "other",
                "aliases": [],
                "roles": [],
                "tags": [],
                "confidence": p["confidence"],
            }
            for p in resolved_people
            if p.get("id")
        ],
    }


def build_org_json(doc_id: str, orgs: list[str]) -> dict:
    return {
        "document_id": doc_id,
        "organizations": [
            {
                "id": "org_" + o.lower().replace(" ", "_"),
                "type": "organization",
                "name": o.lower(),
                "aliases": [],
                "tags": ["organization"],
            }
            for o in orgs
        ],
    }


def build_edges_json(doc_id: str, person_ids: list[str]) -> dict:
    edges = []
    for i, p1 in enumerate(person_ids):
        for p2 in person_ids[i + 1 :]:
            edges.append(
                {
                    "edge_id": f"edge_{doc_id}_{len(edges)+1}",
                    "source": p1,
                    "target": p2,
                    "relationship": "co_mentioned",
                    "weight": 1,
                }
            )
    return {
        "document_id": doc_id,
        "edges": edges,
    }


def build_doc_json(doc_id: str, canonical: dict, mentions: list[str], group_files: list[dict]) -> dict:
    return {
        "id": doc_id,
        "title": canonical["path"].split("/")[-1].replace(".pdf", ""),
        "date": None,
        "source": "Unknown",
        "filePath": canonical["path"],
        "mentions": mentions,
        "sha256": canonical.get("sha256"),
        "grouped_files": [{k: v for k, v in f.items() if k != "minhash"} for f in group_files],
    }


# ---------------------- ORGANIZATION: GROUPS & SINGLETONS ---------------------- #


def process_singletons_to_db(report: Dict[str, Any]) -> None:
    singletons = report.get("singletons", [])
    logger.info(f"Processing {len(singletons)} singletons into SQLite...")

    for s in singletons:
        text = s.get("text", "") or ""
        entities = extract_entities_from_text(text)

        doc_id = f"doc_Dataset12_{Path(s['path']).stem}"

        store_document_in_db(
            doc_id=doc_id,
            canonical=s,
            text=text,
            entities=entities
        )

    logger.info("Singletons stored in SQLite.")



# ---------------------- CLI ---------------------- #

def main():
    p = argparse.ArgumentParser(
        description="Find duplicate or similar PDF files under a directory using MinHash + LSH."
    )
    p.add_argument("--root", default="sourcefiles", help="Root folder to scan (default: sourcefiles)")
    p.add_argument("--out", default="assets/data/pdf_duplicates.json", help="Output JSON report path")
    p.add_argument(
        "--near",
        type=float,
        default=0.90,
        help="Similarity threshold for near-duplicates (SequenceMatcher, default 0.90)",
    )
    p.add_argument(
        "--partial",
        type=float,
        default=0.60,
        help="Similarity threshold for partial duplicates (SequenceMatcher, default 0.60)",
    )
    p.add_argument("--min-pages", type=int, default=0, help="Minimum page count to include (default 0)")
    p.add_argument(
        "--lsh-threshold",
        type=float,
        default=0.8,
        help="LSH Jaccard threshold for candidate retrieval (default 0.8)",
    )
    p.add_argument("--num-perm", type=int, default=128, help="Number of permutations for MinHash (default 128)")
    # organization options
    p.add_argument("--move", dest="move", action="store_true", help="Move grouped files into folders (default)")
    p.add_argument("--no-move", dest="move", action="store_false", help="Do not move files, copy instead")
    p.add_argument("--dry-run", action="store_true", help="Show actions without moving files")
    p.add_argument("--target-root", default=None, help="Optional root folder to create group folders under")
    p.add_argument("--organize", dest="organize", action="store_true", help="Create folders and organize files")
    p.add_argument("--no-organize", dest="organize", action="store_false", help="Do not create folders")
    p.add_argument("--skip-report", action="store_true", help="Do not write JSON report to disk")
    p.add_argument(
        "--singletons-only",
        action="store_true",
        help="If set, organize only singletons (not groups).",
    )
    p.set_defaults(move=True, organize=True)
    args = p.parse_args()

    root = Path(args.root)
    if not root.exists():
        logger.error(f"Root not found: {root}")
        return

    files = find_pdfs(root)
    report = build_report(
        files,
        near_thresh=args.near,
        partial_thresh=args.partial,
        min_pages=args.min_pages,
        lsh_threshold=args.lsh_threshold,
        num_perm=args.num_perm,
    )

    if args.organize:
        if args.singletons_only:
            organize_singletons(report, move=args.move, target_root=args.target_root, dry_run=args.dry_run)
        else:
            organize_groups(report, move=args.move, target_root=args.target_root, dry_run=args.dry_run)
            organize_singletons(report, move=args.move, target_root=args.target_root, dry_run=args.dry_run)

    if not args.skip_report:
        outp = Path(args.out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        with outp.open("w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        logger.info(f"Wrote report to {outp}")

    logger.info(json.dumps(report["summary"], indent=2))


if __name__ == "__main__":
    main()
