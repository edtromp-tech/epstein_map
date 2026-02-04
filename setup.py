#!/usr/bin/env python3
"""
Setup script to create folder structure for each document.
Creates EFTA* folders with template JSON files ready for manual data entry.
"""

import json
import os
from pathlib import Path

def create_document_folder(doc_id: str, doc_title: str, doc_date: str, mentions: list, pdf_file: str):
    """Create a document folder with template JSON files."""
    
    # Extract folder name from PDF file
    folder_name = pdf_file.split('/')[-1].replace('.pdf', '')
    folder_path = Path("files/Dataset12") / folder_name
    
    if folder_path.exists():
        print(f"⚠ Folder already exists: {folder_path}")
        return
    
    folder_path.mkdir(parents=True, exist_ok=True)
    
    # Create doc.json
    doc_json = {
        "id": doc_id,
        "title": doc_title,
        "date": doc_date,
        "source": "To be categorized",
        "filePath": pdf_file,
        "mentions": mentions
    }
    
    # Create people.json template
    people_json = {
        "document_id": doc_id,
        "people": [
            {
                "id": mention_id,
                "name": "TODO: Add name",
                "type": "other",
                "tags": ["to_be_categorized"]
            }
            for mention_id in mentions
        ]
    }
    
    # Create edges.json template
    edges_json = {
        "document_id": doc_id,
        "edges": []
    }
    
    # Create org.json template
    org_json = []
    
    # Create ref.json template (cases)
    ref_json = []
    
    # Save all files
    with open(folder_path / "doc.json", 'w') as f:
        json.dump(doc_json, f, indent=2)
    
    with open(folder_path / "people.json", 'w') as f:
        json.dump(people_json, f, indent=2)
    
    with open(folder_path / "edges.json", 'w') as f:
        json.dump(edges_json, f, indent=2)
    
    with open(folder_path / "org.json", 'w') as f:
        json.dump(org_json, f, indent=2)
    
    with open(folder_path / "ref.json", 'w') as f:
        json.dump(ref_json, f, indent=2)
    
    print(f"✓ Created {folder_path}")

def setup():
    """Create all document folders from current documents.json"""
    
    print("Setting up document folder structure...\n")
    
    # Load current documents
    with open("assets/data/documents.json", 'r') as f:
        documents = json.load(f)
    
    # Filter for Dataset12 documents that need folders
    dataset_docs = [d for d in documents if 'Dataset12' in d.get('filePath', '')]
    
    for doc in dataset_docs:
        # Only create if it's a PDF document (skip cases)
        if 'files/case_' not in doc.get('filePath', ''):
            create_document_folder(
                doc['id'],
                doc.get('title', 'Untitled'),
                doc.get('date', 'Unknown'),
                doc.get('mentions', []),
                doc['filePath']
            )
    
    print(f"\n✅ Setup complete! Created folders for {len(dataset_docs)} documents")
    print("Next steps:")
    print("1. Edit each folder's JSON files to add/organize data")
    print("2. Move PDF files into their respective folders")
    print("3. Run build.py to consolidate all data")

if __name__ == "__main__":
    setup()
