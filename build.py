#!/usr/bin/env python3
"""
Build script to consolidate document data from individual folders into unified JSON files.

Structure:
- Source: files/Dataset12/EFTA*/ (each contains doc.json, people.json, edges.json, org.json, ref.json)
- Output: assets/data/ (consolidated people.json, edges.json, organizations.json, documents.json, cases.json)
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any

def load_json(filepath: str) -> Any:
    """Load JSON file, return empty dict/list if not found."""
    if not os.path.exists(filepath):
        return [] if filepath.endswith('.json') else {}
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath: str, data: Any) -> None:
    """Save data to JSON file with nice formatting."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"Saved {filepath}")

def merge_documents(docs_list: List[Dict]) -> List[Dict]:
    """Merge documents, keeping unique by ID."""
    seen = {}
    for doc in docs_list:
        if doc.get('id') not in seen:
            seen[doc['id']] = doc
    return list(seen.values())

def merge_people(people_list: List[Dict]) -> List[Dict]:
    """Merge people, keeping unique by ID and merging their properties."""
    seen = {}
    
    for person in people_list:
        pid = person.get('id')
        
        if pid not in seen:
            # First occurrence: deep copy to avoid mutations
            seen[pid] = json.loads(json.dumps(person))
        else:
            # Merge with existing person
            existing = seen[pid]
            
            for key, value in person.items():
                if key == 'id':
                    continue  # Skip ID
                
                if key not in existing:
                    # Add new field
                    existing[key] = value
                else:
                    existing_val = existing[key]
                    
                    # Merge lists: combine and deduplicate
                    if isinstance(value, list) and isinstance(existing_val, list):
                        combined = existing_val + value
                        # Deduplicate while preserving order
                        seen_items = set()
                        deduped = []
                        for item in combined:
                            # Handle both hashable and unhashable items
                            try:
                                if item not in seen_items:
                                    seen_items.add(item)
                                    deduped.append(item)
                            except TypeError:
                                # Item is unhashable (dict/list), just add if not present
                                if item not in deduped:
                                    deduped.append(item)
                        existing[key] = deduped
                    
                    # Merge dicts: recursively merge
                    elif isinstance(value, dict) and isinstance(existing_val, dict):
                        for sub_key, sub_val in value.items():
                            if sub_key not in existing_val:
                                existing_val[sub_key] = sub_val
                    
                    # For scalar values: keep existing, prefer non-null/non-empty
                    elif not existing_val and value:
                        existing[key] = value
    
    return list(seen.values())

def merge_edges(edges_list: List[Dict]) -> List[Dict]:
    """
    Merge edges grouped by source and target.
    Combines edge_ids, relationships, and weights into lists.
    Calculates average weight for the edge.
    """
    # Group by (source, target)
    grouped = {}
    
    for edge in edges_list:
        source = edge.get('source')
        target = edge.get('target')
        key = (source, target)
        
        if key not in grouped:
            grouped[key] = {
                'source': source,
                'target': target,
                'edges': [],
                'weights': []
            }
        
        # Extract edge_id, relationship, weight
        edge_id = edge.get('edge_id', '')
        relationship = edge.get('relationship', 'unknown')
        weight = edge.get('weight', 1)
        
        # Add to edges list
        grouped[key]['edges'].append({
            'edge_id': edge_id,
            'relationship': relationship,
            'weight': weight
        })
        
        # Track weight for averaging
        grouped[key]['weights'].append(weight)
    
    # Convert to final format with calculated average weight
    result = []
    for (source, target), data in grouped.items():
        weights = data['weights']
        avg_weight = sum(weights) / len(weights) if weights else 0
        
        result.append({
            'source': source,
            'target': target,
            'edges': data['edges'],
            'avg_weight': round(avg_weight, 2)
        })
    
    return result

def merge_organizations(orgs_list: List[Dict]) -> List[Dict]:
    """Merge organizations, keeping unique by ID."""
    seen = {}
    for org in orgs_list:
        oid = org.get('id')
        if oid not in seen:
            seen[oid] = org
    return list(seen.values())

def build():
    """Main build function."""
    print("Building consolidated data files...\n")
    
    # Paths
    dataset_dir = Path("files/Dataset12")
    output_dir = Path("assets/data")
    
    if not dataset_dir.exists():
        print(f"ERROR: Dataset directory not found: {dataset_dir}")
        return
    
    # Initialize consolidated data
    all_documents = []
    all_people = []
    all_edges = []
    all_organizations = []
    all_cases = []
    
    # Find all document folders (EFTA*)
    doc_folders = sorted([d for d in dataset_dir.iterdir() if d.is_dir() and d.name.startswith('EFTA')])
    
    if not doc_folders:
        print(f"Warning: No EFTA* folders found in {dataset_dir}")
        return
    
    print(f"Found {len(doc_folders)} document folders:\n")
    
    # Process each document folder
    for folder in doc_folders:
        folder_name = folder.name
        print(f"  Processing {folder_name}...")
        
        # Load data from this document
        doc_file = folder / "doc.json"
        people_file = folder / "people.json"
        edges_file = folder / "edges.json"
        org_file = folder / "org.json"
        ref_file = folder / "ref.json"  # cases/references
        
        # Load documents
        doc_data = load_json(str(doc_file))
        if isinstance(doc_data, dict) and doc_data.get('id'):
            all_documents.append(doc_data)
        
        # Load people
        people_data = load_json(str(people_file))
        if isinstance(people_data, dict) and 'people' in people_data:
            all_people.extend(people_data['people'])
        elif isinstance(people_data, list):
            all_people.extend(people_data)
        
        # Load edges
        edges_data = load_json(str(edges_file))
        if isinstance(edges_data, dict) and 'edges' in edges_data:
            all_edges.extend(edges_data['edges'])
        elif isinstance(edges_data, dict) and 'edge' in edges_data:
            # Handle singular "edge" key
            all_edges.extend(edges_data['edge'])
        elif isinstance(edges_data, list):
            all_edges.extend(edges_data)
        
        # Load organizations
        orgs_data = load_json(str(org_file))
        if isinstance(orgs_data, list):
            all_organizations.extend(orgs_data)
        elif isinstance(orgs_data, dict) and 'organizations' in orgs_data:
            all_organizations.extend(orgs_data['organizations'])
        
        # Load cases/references
        ref_data = load_json(str(ref_file))
        if isinstance(ref_data, list):
            all_cases.extend(ref_data)
        elif isinstance(ref_data, dict) and 'cases' in ref_data:
            all_cases.extend(ref_data['cases'])
    
    print("\nLoaded all documents\n")
    
    # Merge and deduplicate
    print("Consolidating data...\n")
    consolidated_documents = merge_documents(all_documents)
    consolidated_people = merge_people(all_people)
    consolidated_edges = merge_edges(all_edges)
    consolidated_organizations = merge_organizations(all_organizations)
    consolidated_cases = merge_documents(all_cases)  # Reuse merge_documents logic
    
    # Save consolidated files
    print("Writing output files:\n")
    save_json(str(output_dir / "documents.json"), consolidated_documents)
    save_json(str(output_dir / "people.json"), consolidated_people)
    save_json(str(output_dir / "edges.json"), consolidated_edges)
    save_json(str(output_dir / "organizations.json"), consolidated_organizations)
    save_json(str(output_dir / "cases.json"), consolidated_cases)
    
    # Summary
    print("\nSummary:")
    print(f"  Documents: {len(consolidated_documents)}")
    print(f"  People: {len(consolidated_people)}")
    print(f"  Edges: {len(consolidated_edges)}")
    print(f"  Organizations: {len(consolidated_organizations)}")
    print(f"  Cases: {len(consolidated_cases)}")
    print("\nBuild complete!")

if __name__ == "__main__":
    build()
