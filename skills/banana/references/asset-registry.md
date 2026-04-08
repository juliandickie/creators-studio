# Asset Registry Reference

> Load this when the user mentions a named character, product, or object
> that may be saved as an asset, or when they run `/banana asset`.

## Overview

The asset registry stores persistent references (characters, products, equipment,
environments) with description and reference images. When an asset is loaded,
its reference images are passed to the Gemini API as multi-image input for
visual consistency across sessions.

## Asset Types

| Type | Use Case | Examples |
|------|----------|---------|
| `character` | People, personas, avatars | Team members, brand ambassadors, fictional characters |
| `product` | Physical products for UGC/e-commerce | Dental scanners, headphones, coffee mugs |
| `equipment` | Tools, devices, instruments | 3D printers, cameras, medical devices |
| `environment` | Recurring settings/locations | Your clinic, office, studio, storefront |

## Detecting Asset References

When a user's prompt mentions a name that could be an asset, check:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/assets.py list
```

If a matching asset exists, load it:
```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/assets.py show NAME
```

## Using Assets in Generation

When an asset is loaded:

1. **Add reference images to the API call** — each image in `reference_images[]`
   becomes an `inlineData` part in the Gemini request, before the text prompt.
   The model uses these for visual consistency.

2. **Incorporate the description** — weave `description` into the prompt naturally:
   "the iTero Scanner (a handheld intraoral scanner with white and gray body...)"

3. **Apply consistency notes** — append `consistency_notes` as a constraint:
   ```
   CRITICAL CONSISTENCY REQUIREMENTS:
   - [consistency_notes from asset]
   - Maintain EXACT appearance from reference images
   ```

4. **Use default context** — if user doesn't specify a setting, use `default_context`
   as the Location component of the 5-Component Formula.

## API Limits

| Limit | Value |
|-------|-------|
| Max images per request | 14 (10 objects + 4 characters) |
| Max image size | 7 MB per image (inline), 30 MB via GCS |
| Supported formats | JPEG, PNG, WebP, HEIC, HEIF |
| Character consistency | Up to 5 people with high fidelity |
| Object consistency | Up to 6 objects with high fidelity |

## Combining Assets with Brand Presets

Both can be active simultaneously:
- **Brand preset** → provides style, colors, mood, prompt_suffix
- **Asset** → provides reference images and physical description
- If both are loaded, the prompt includes brand styling AND asset reference images

## CLI Reference

```bash
# List all assets
python3 ${CLAUDE_SKILL_DIR}/scripts/assets.py list

# Show full details
python3 ${CLAUDE_SKILL_DIR}/scripts/assets.py show itero-scanner

# Create with reference images
python3 ${CLAUDE_SKILL_DIR}/scripts/assets.py create itero-scanner \
  --type product \
  --description "Handheld intraoral scanner, white and gray body, LED ring" \
  --reference ~/photos/itero-front.jpg \
  --reference ~/photos/itero-angle.jpg \
  --default-context "modern dental clinic" \
  --consistency-notes "Always show LED ring illuminated, logo visible"

# Add more reference images later
python3 ${CLAUDE_SKILL_DIR}/scripts/assets.py add-image itero-scanner \
  --reference ~/photos/itero-closeup.jpg

# Delete
python3 ${CLAUDE_SKILL_DIR}/scripts/assets.py delete itero-scanner --confirm
```

## Storage

Assets stored at `~/.banana/assets/NAME.json`. Each file contains:
- `name` — sanitized identifier
- `type` — character, product, equipment, or environment
- `description` — physical description for prompts
- `reference_images` — array of absolute file paths
- `default_context` — fallback setting/location
- `consistency_notes` — what to always maintain
