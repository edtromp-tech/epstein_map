# Project Restructuring Guide

## Overview

This project now uses a **source-of-truth** architecture where individual document data is stored separately, then consolidated into unified JSON files for the web UI.

## Directory Structure

```
epstein_map/
├── files/Dataset12/
│   ├── EFTA02730265/          # Document folder
│   │   ├── doc.json           # Document metadata
│   │   ├── people.json        # People mentioned in document
│   │   ├── edges.json         # Relationships found in document
│   │   ├── org.json           # Organizations mentioned
│   │   ├── ref.json           # Cases/references
│   │   └── EFTA02730265.pdf   # PDF file
│   ├── EFTA02730267/
│   ├── EFTA02730271/
│   └── [more documents...]
│
├── assets/
│   ├── data/                  # Consolidated data (generated)
│   │   ├── people.json        # All people merged
│   │   ├── edges.json         # All edges merged
│   │   ├── organizations.json # All organizations merged
│   │   ├── documents.json     # All documents
│   │   └── cases.json         # All cases
│   ├── css/
│   ├── js/
│   └── index.html
│
├── build.py                   # Build script (consolidates data)
└── setup.py                   # Setup script (creates folder structure)
```

## Workflow

### 1. Add New Documents

When you have a new document to add:

1. Create a folder: `files/Dataset12/EFTA{ID}/`
2. Add these JSON files:
   - `doc.json` - Document metadata
   - `people.json` - People entities with details
   - `edges.json` - Relationships between people
   - `org.json` - Organizations
   - `ref.json` - Cases/references
3. Place the PDF in the folder

### 2. Edit Document Data

Each folder contains independent data that can be edited anytime:
- Update `people.json` to add/modify person information
- Update `edges.json` to add/modify relationships
- Update `doc.json` with metadata

### 3. Build the Consolidated Data

When you're ready to rebuild the consolidated files:

```bash
python build.py
```

This will:
- Read all `files/Dataset12/EFTA*/` folders
- Merge all data by ID (deduplicating)
- Write consolidated JSON to `assets/data/`
- The web UI automatically uses these consolidated files

### 4. Run the Web UI

The web UI pulls from `assets/data/`:

```bash
python -m http.server 8080
```

Then open `http://localhost:8080`

## JSON File Formats

### doc.json
```json
{
  "id": "doc_Dataset12_EFTA02730265",
  "title": "Email chain about settlement agreement",
  "date": "2013-August-24",
  "source": "GMail",
  "filePath": "files/Dataset12/EFTA02730265/EFTA02730265.pdf",
  "mentions": ["jeffrey_epstein", "larry_cohen", "boris_nikolic"]
}
```

### people.json
```json
{
  "document_id": "doc_Dataset12_EFTA02730265",
  "people": [
    {
      "id": "jeffrey_epstein",
      "name": "Jeffrey Epstein",
      "DOB": "1953-01-20",
      "type": "accused",
      "role": ["financier", "intermediary"],
      "tags": ["central"],
      "notes": "Primary subject",
      "caseIds": ["case_2019_sdny"]
    }
  ]
}
```

### edges.json
```json
{
  "document_id": "doc_Dataset12_EFTA02730265",
  "edges": [
    {
      "source": "jeffrey_epstein",
      "target": "larry_cohen",
      "relationship": "communication",
      "weight": 2,
      "evidence": [
        {
          "document_id": "doc_Dataset12_EFTA02730265",
          "type": "email",
          "date": "2013-08-24",
          "excerpt": "Email chain content..."
        }
      ]
    }
  ]
}
```

### org.json
```json
[
  {
    "id": "org_bgc3",
    "name": "bgC3",
    "type": "organization",
    "aliases": ["bgc3"],
    "tags": ["organization"]
  }
]
```

### ref.json (Cases/References)
```json
[
  {
    "id": "case_2019_sdny",
    "name": "United States v. Jeffrey Epstein",
    "date": "2019",
    "court": "SDNY"
  }
]
```

## Important Notes

- **consolidated files are gitignored**: The `assets/data/*.json` files are generated and should not be committed
- **source data is the source of truth**: Keep all original data in `files/Dataset12/EFTA*/` folders
- **deduplication happens at build time**: If the same person appears in multiple documents, they're automatically merged by ID
- **evidence tracking**: Each edge includes evidence with document links

## Troubleshooting

**Build fails?**
- Ensure all JSON files are valid (use `python -m json.tool file.json`)
- Check that folder names match `EFTA*` pattern
- Verify file names are exactly: `doc.json`, `people.json`, `edges.json`, `org.json`, `ref.json`

**Data not showing in UI?**
- Run `python build.py` to regenerate consolidated files
- Check that `assets/data/` has recent JSON files (check modification time)
- Open browser console to check for loading errors
