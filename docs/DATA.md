# Data Documentation

## Overview
The Restaurant Voice Ordering Agent uses ingested restaurant menu content as the only source of truth for menu questions, prices, ingredients, modifications, dietary labels, allergens, and orderable items. 

The LLM and RAG layer must not invent menu facts.

## Data Sources
The system supports the following menu source types:
- committed raw HTML fixture for reproducible grading
- pasted text
- uploaded `.txt`, `.md`, `.html`, `.csv`, or `.json` file
- Simple static URL ingestion is supported only for publicly reachable HTML pages that return menu-like text in the initial HTTP response without requiring login, JavaScript rendering, CAPTCHA, third-party embedded menus, or PDF/image extraction. Live URL ingestion is not required for the default grading path.

## Default Grading Fixture
The default grading path uses the required fixture path:
```text
data/raw/sample_restaurant_menu.html
```
This fixture is a fictional project-created restaurant menu used for reproducible grading. The fictional restaurant name is:
```text
Cedar & Lime Taqueria
```
The fixture must contain enough menu data to support all user stories, including:
- taco menu question
- vegetarian menu question
- peanut allergy caution question
- chicken taco order
- no onions modification
- extra queso unsupported special instruction
- lemonade order
- ambiguous chicken taco removal

The fixture includes:
- at least 3 menu categories
- at least 10 menu items
- item names
- item descriptions
- prices
- ingredients where available
- at least 2 items with explicit dietary labels
- at least 2 items with allergen-relevant ingredients
- At least 3 known priced modifications total across the menu, including at least one known priced modification on a taco item.
- At least one unsupported modification scenario for a taco item, such as "extra queso", that is not listed as a priced modification and must be handled as an unpriced special instruction after caller confirmation.
- At least two similar chicken taco line items can be created during testing to exercise ambiguous removal.

## Restaurant-Provided Menu Inputs
Supported input types:
```text
.txt
.md
.html
.csv
.json
pasted plain text
simple static URL
```

Reliability order for ingestion:
1. Structured JSON
2. CSV
3. HTML
4. Markdown
5. Plain text
6. Simple static URL

Many real websites may not ingest reliably if they use JavaScript-only menus, third-party delivery embeds, images, PDFs, login walls, CAPTCHA, or anti-scraping controls.

## Required Data Paths

| Artifact | Path | Created By | Committed? | Purpose |
|---|---|---|---|---|
| Raw menu fixture | `data/raw/sample_restaurant_menu.html` | Team-created fixture | Yes | Reproducible menu source for grading |
| Processed menu JSON | `data/processed/menu.json` | `make reproduce` / menu ingestion | Generated | Canonical structured menu data |
| Menu chunks | `data/index/menu_chunks.json` | RAG index builder | Generated | Retrieval text chunks |
| Menu metadata | `data/index/menu_metadata.json` | RAG index builder | Generated | Index metadata and degraded-mode status |
| Embeddings | `data/index/embeddings.npy` | RAG index builder | Generated | Local vector embeddings |

## Canonical Menu Schema

Example canonical schema:
```json
{
  "restaurant": {
    "name": "Cedar & Lime Taqueria",
    "currency": "USD",
    "tax_rate": 0.0825,
    "service_fee_rate": 0.0
  },
  "items": [
    {
      "id": "chicken_tacos",
      "name": "Chicken Tacos",
      "aliases": ["chicken taco"],
      "category": "Tacos",
      "description": "Two corn tortillas with grilled chicken, cabbage, salsa verde, onions, and lime.",
      "base_price": 9.99,
      "available": true,
      "ingredients": ["corn tortillas", "grilled chicken", "cabbage", "salsa verde", "onions", "lime"],
      "dietary_tags": ["gluten_free_possible", "contains_chicken"],
      "allergens": [],
      "modifications": [
        {
          "name": "add avocado",
          "price_delta": 1.50
        },
        {
          "name": "extra salsa verde",
          "price_delta": 0.50
        }
      ],
      "source_text": "Chicken Tacos - Two corn tortillas with grilled chicken, cabbage, salsa verde, onions, and lime. $9.99",
      "source_type": "menu_label"
    }
  ]
}
```

Field explanations:
- `restaurant`: Metadata regarding the business, currency, and tax specifics.
- `items`: An array of orderable items.
- `id`: A stable unique identifier for the item.
- `name`: The primary menu name of the item.
- `aliases`: Acceptable alternative spoken or written names for the item.
- `category`: The menu section the item belongs to.
- `description`: The provided description from the menu.
- `base_price`: The numerical price before tax, fees, or modifications.
- `available`: A boolean indicating if the item can be ordered.
- `ingredients`: An array of known ingredients.
- `dietary_tags`: Explicit dietary and lifestyle markers.
- `allergens`: Known allergen markers.
- `modifications`: Known priced customizations available for the item.
- `source_text`: The raw text used to derive the canonical item.
- `source_type`: The origin of the item definition.

## Menu Ingestion Pipeline

Transformation steps:
1. Load raw menu content.
2. Extract restaurant metadata.
3. Extract categories.
4. Extract item names.
5. Extract descriptions.
6. Extract prices.
7. Extract ingredients when present.
8. Extract explicit dietary labels and allergen labels.
9. Extract known priced modifications.
10. Normalize text.
11. Generate stable item IDs.
12. Generate aliases where straightforward.
13. Apply conservative dietary/allergen inference.
14. Validate against canonical menu schema.
15. Write `data/processed/menu.json`.
16. Build RAG index artifacts under `data/index/`.

The ingestion pipeline must not use the LLM to invent missing prices, ingredients, allergens, dietary tags, modifications, or availability.

## Dietary and Allergen Metadata Policy

Rules:
- Restaurant-provided dietary metadata is optional enrichment, not required.
- Explicit menu labels take priority.
- Conservative parser inference may add warnings and exclusions.
- Positive dietary claims require explicit evidence.
- Allergy-safe claims require explicit evidence.
- Absence of an allergen in text does not prove allergen-free.
- The system must use cautious language when evidence is incomplete.

Examples:

Allowed:
```text
This item is marked vegetarian on the menu.
```

Allowed:
```text
This item lists cheese, so it contains dairy.
```

Allowed:
```text
The menu does not list peanuts for this item, but I cannot guarantee it is peanut-free.
```

Not allowed:
```text
This is safe for your peanut allergy.
```
unless the canonical menu data explicitly provides that guarantee.

## RAG Index Artifacts

Canonical menu items become retrieval chunks. Each chunk should include:
- chunk ID
- item ID
- item name
- category
- retrieval text
- source text

Embedding model:
```text
sentence-transformers/all-MiniLM-L6-v2
```

Storage:
```text
data/index/embeddings.npy
```

Fallback:
If embeddings cannot be generated, the system shall continue with structured filtering and `rapidfuzz` lexical matching, and `data/index/menu_metadata.json` shall record degraded retrieval status.

## Data Reproducibility

Commands:
```bash
make download-data
make download-models
make reproduce
```

`make reproduce` regenerates the following when embeddings are available:
```text
data/processed/menu.json
data/index/menu_chunks.json
data/index/menu_metadata.json
data/index/embeddings.npy
```

## Licensing and Usage Assumptions

- The default sample menu is fictional project-created content.
- No real restaurant menu license is required for the default grading path.
- If a real restaurant menu is added later, document source URL, access date, license/usage assumption, and whether the data is committed or generated.

## Data Limitations

- The system can only answer from ingested menu data.
- It may not know real-time availability.
- It may not know off-menu substitutions.
- It may not know kitchen cross-contamination risk.
- It cannot guarantee allergy safety without explicit menu evidence.
- It does not promise universal website scraping.
- It does not process payment or live POS data.

## Data Success Criteria

- `data/raw/sample_restaurant_menu.html` exists.
- `make download-data` succeeds.
- `make reproduce` generates `data/processed/menu.json`.
- `make reproduce` generates RAG index files.
- Canonical menu JSON validates against schemas.
- Required user-story menu items exist.
- Dietary/allergen policy is documented.
- No undocumented data source is required for grading.
