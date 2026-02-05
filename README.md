# epstein_map

Compilation of Epstein files in an exploratory degree of separation map.

An interactive network visualization tool that maps relationships and connections found in the Epstein Files dataset. The project uses a source-of-truth architecture where individual document data is maintained separately and consolidated for the web interface.

## Quick Start

### View the Map

https://edtromp-tech.github.io/epstein_map/


**Features:**
- 🔍 Search for people by name
- 📊 Interactive network graph showing degrees of separation
- 🏷️ Filter by person type (Victim, Accused, Other) and risk score
- 📄 Click on people to see details and linked documents
- 📱 Responsive design with toggle-able sidebars for mobile viewing

## Getting Involved

### Understanding the Structure

This project uses a **source-of-truth** architecture. Start by reading [RESTRUCTURING.md](RESTRUCTURING.md) to understand:
- How data is organized
- The JSON file formats for each data type
- The build and consolidation process

### Contributing Documents

To add new documents to the dataset:

1. **Create a document folder:**
   ```
   files/Dataset12/EFTA{ID}/
   ```

2. **Add these JSON files:**
   - `doc.json` - Document metadata (title, date, source, etc.)
   - `people.json` - People mentioned in the document
   - `edges.json` - Relationships between people
   - `org.json` - Organizations mentioned
   - `ref.json` - Cases and references

3. **Include the PDF:**
   - Place the PDF file in the same folder

4. **See examples:**
   - Check existing folders in `files/Dataset12/` for reference formats
   - Refer to [RESTRUCTURING.md](RESTRUCTURING.md) for detailed JSON schemas

### Editing Existing Data

You can edit document data anytime:
- Modify `people.json` to add/update person information
- Modify `edges.json` to add/update relationships
- Modify `doc.json` with metadata corrections

### Building the Consolidated Data

After adding or modifying documents:

```bash
python build.py
```

This consolidates all document data into unified JSON files in `assets/data/` which the web UI uses.


## Project Structure

```
epstein_map/
├── files/Dataset*/              # Source document data
│   └── EFTA*/                   # Individual document folders
│       ├── doc.json
│       ├── people.json
│       ├── edges.json
│       ├── org.json
│       ├── ref.json
│       └── *.pdf                # PDF files
├── assets/
│   ├── data/                    # Consolidated data (auto-generated)
│   ├── css/
│   ├── js/
│   └── index.html
├── build.py                     # Consolidation script
├── setup.py                     # Setup script
├── README.md                    # This file
└── RESTRUCTURING.md             # Detailed architecture guide
```

## Contributing Guidelines

- **Source of truth:** Keep original data in `files/Dataset*/EFTA*/` folders
- **Data integrity:** Ensure all JSON files are valid before building
- **Deduplication:** The build script automatically merges duplicate people by ID across documents
- **Evidence tracking:** Include source information and document references in edges

## Troubleshooting

**Data not showing in UI?**
- Run `python build.py` to regenerate consolidated files
- Check browser console for loading errors
- Verify JSON files are valid: `python -m json.tool file.json`

**Build script fails?**
- Ensure folder names match `EFTA*` pattern
- Check file names are exactly: `doc.json`, `people.json`, `edges.json`, `org.json`, `ref.json`
- Validate JSON file syntax

## Future Updates

Planned features and improvements:

### 📱 Enhanced Mobile View
- Improved phone layout with better touch interactions
- Full-screen graph mode for smaller devices
- Swipe gestures for navigation
- Optimized sidebar toggle for mobile users

### 📄 PDF Viewer Integration
- Built-in document viewer with page navigation
- PDF highlighting and annotation support
- Full-text search across documents
- Link documents directly to graph nodes

### 🔎 Advanced Filtering
- Filter by relationship types (associate, coordinator, benefactor, etc.)
- Date range filtering for temporal analysis
- Multi-select person type filters
- Custom tag-based filtering
- Organization and case-based filtering

## For More Information

- See [RESTRUCTURING.md](RESTRUCTURING.md) for detailed architecture and JSON schemas
- Check existing document folders for data format examples 
