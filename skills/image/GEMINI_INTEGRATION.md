# Gemini Integration - Scene-Based Image Workflow

Complete integration between Gemini Imagen 3 API and scene-based project management for client image production.

## Problem Solved

**Challenge:** AI image generation is non-deterministic. Same prompt → different outputs each time.

**Client Impact:** When client requests revision to one image in a brand kit, regenerating it might require re-prompting, and ensuring style consistency across assets is challenging.

**Solution:** Scene-based architecture with seed tracking, variant management, and multi-format export.

## Architecture

```
image_project_manager.py       # Project/scene/variant tracking
      ↓
gemini_image_automation.py     # Gemini API wrapper
      ↓
Gemini Imagen 3 API            # Image generation
      ↓
PIL/Pillow                     # Grid/carousel composition
```

## Files

1. **`image_project_manager.py`** - Core project management
   - Create/load `.imgproj` files
   - Track scenes, variants, metadata
   - Approve variants
   - Export: individual, grid, carousel (HTML/PDF)

2. **`gemini_image_automation.py`** - Gemini API integration
   - Image generation via Imagen 3
   - Template workflows (brand_kit, product_mockup, carousel)
   - Style consistency helpers

3. **`example_gemini_workflow.py`** - Complete workflow example
   - Reference implementation
   - Brand kit walkthrough

## Workflow

### Phase 1: Setup

```python
from image_project_manager import run

# Create project
result = run(
    action="create_project",
    project_name="Acme Brand Kit",
    description="Complete brand asset package",
    metadata={"client": "Acme Corp", "deadline": "2026-03-15"}
)
project_id = result['project_id']

# Add scenes (each asset type is a scene)
run(action="add_scene", project_id=project_id,
    scene_name="Logo",
    prompt="Modern minimalist logo for Acme Corp, blue and white, geometric shapes",
    aspect_ratio="1:1")

run(action="add_scene", project_id=project_id,
    scene_name="Social Banner",
    prompt="Social media banner for Acme Corp, professional tech company, modern design",
    aspect_ratio="16:9")
```

### Phase 2: Generation (per scene)

```python
from gemini_image_automation import run as gemini_run

# Generate Logo variants
result = gemini_run(
    action="generate",
    prompt="Modern minimalist logo for Acme Corp, blue and white, geometric shapes, professional",
    num_variants=3,
    aspect_ratio="1:1",
    style="clean vector design",
    output_dir=f"~/image_projects/{project_id}/scenes/logo"
)

# Record variants in project
for img_data in result['images']:
    run(action="add_variant",
        project_id=project_id,
        scene_name="Logo",
        generation_params={
            "prompt": img_data['prompt'],
            "aspect_ratio": img_data['aspect_ratio'],
            "timestamp": img_data['timestamp']
        },
        local_path=img_data['local_path'])
```

### Phase 3: Client Review

1. **Present variants** - Show local files or URLs
2. **Client picks favorite** - Client selects Variant 2
3. **Approve variant**:

```python
run(action="approve_variant",
    project_id=project_id,
    scene_name="Logo",
    variant_id="<variant_2_id>")
```

### Phase 4: Repeat for All Scenes

Repeat Phases 2-3 for each scene (logo, icon, banner, etc.) until all approved.

### Phase 5: Export

```python
# Check status
result = run(action="status", project_id=project_id)
# {approved_scenes: 4/4, ready_to_export: true}

# Export individual files
result = run(action="export",
    project_id=project_id,
    format="individual",
    output_dir="~/deliverables/acme_brand_kit")

# Export as grid
result = run(action="export",
    project_id=project_id,
    format="grid",
    output_path="~/deliverables/acme_brand_kit_grid.png",
    grid_cols=2)

# Export as carousel (HTML)
result = run(action="export",
    project_id=project_id,
    format="carousel_html",
    output_path="~/deliverables/acme_carousel.html")
```

## Revision Workflow

**Client:** "Change the logo, keep everything else"

```python
# 1. Regenerate Logo only
result = gemini_run(
    action="generate",
    prompt="Modern minimalist logo for Acme Corp, PURPLE instead of blue, geometric",
    num_variants=2,
    aspect_ratio="1:1",
    output_dir=f"~/image_projects/{project_id}/scenes/logo"
)

# 2. Add new variants to existing scene
for img_data in result['images']:
    run(action="add_variant",
        project_id=project_id,
        scene_name="Logo",
        generation_params={...},
        local_path=img_data['local_path'])

# 3. Client picks new favorite

# 4. Approve new variant
run(action="approve_variant",
    project_id=project_id,
    scene_name="Logo",
    variant_id="<new_variant_id>")

# 5. Re-export (reuses other approved scenes, replaces Logo)
run(action="export",
    project_id=project_id,
    format="grid",
    output_path="~/deliverables/acme_brand_kit_grid_v2.png")
```

**Cost Savings:** Only regenerate 1 scene instead of entire brand kit.

## Project File Structure

```
~/image_projects/
└── abc123_456789/              # Project directory
    ├── abc123_456789.imgproj   # Project metadata (JSON)
    ├── scenes/                  # Scene-specific data
    │   ├── logo/
    │   ├── icon/
    │   └── banner/
    ├── variants/                # Generated image files
    │   ├── logo_v1.png
    │   ├── logo_v2.png
    │   ├── logo_v3.png
    │   ├── icon_v1.png
    │   └── banner_v1.png
    ├── approved/                # Approved variants (symlinks)
    │   ├── logo.png → ../variants/logo_v2.png
    │   ├── icon.png → ../variants/icon_v1.png
    │   └── banner.png → ../variants/banner_v1.png
    ├── abc123_456789_grid.png   # Grid export
    └── abc123_456789.html       # Carousel export
```

## .imgproj File Format

```json
{
  "id": "abc123_456789",
  "name": "Acme Brand Kit",
  "description": "Complete brand asset package",
  "project_type": "brand_kit",
  "scenes": [
    {
      "id": "scene_001",
      "name": "Logo",
      "scene_type": "logo",
      "prompt": "Modern minimalist logo...",
      "order": 0,
      "status": "approved",
      "aspect_ratio": "1:1",
      "variants": [
        {
          "id": "var_001",
          "status": "rejected",
          "local_path": "/path/to/logo_v1.png",
          "generation_params": {
            "prompt": "...",
            "aspect_ratio": "1:1",
            "timestamp": 1709456789000
          },
          "generated_at": "2026-03-03T06:45:00Z"
        },
        {
          "id": "var_002",
          "status": "approved",
          "local_path": "/path/to/logo_v2.png",
          "generation_params": {...},
          "generated_at": "2026-03-03T06:45:00Z",
          "approved_at": "2026-03-03T07:00:00Z"
        }
      ],
      "approved_variant_id": "var_002"
    }
  ],
  "created_at": "2026-03-03T06:00:00Z",
  "updated_at": "2026-03-03T08:00:00Z",
  "metadata": {
    "client": "Acme Corp",
    "deadline": "2026-03-15"
  }
}
```

## Template Workflows

### Brand Kit

```python
# Use pre-built template
result = gemini_run(
    action="create_workflow",
    template_type="brand_kit",
    brand_name="Acme Corp",
    brand_description="Modern tech company",
    style_guide={
        "colors": ["#0066FF", "#FFFFFF"],
        "style": "modern minimalist",
        "mood": "professional"
    }
)

# Returns workflow with scenes:
# - Logo (1:1)
# - Icon (1:1)
# - Social Banner (16:9)
# - Business Card (3:2)
```

### Product Mockup

```python
result = gemini_run(
    action="create_workflow",
    template_type="product_mockup",
    product_name="SmartWatch Pro",
    product_description="Premium fitness smartwatch, black with silver accents"
)

# Returns workflow with scenes:
# - Hero Shot (1:1, white background)
# - Lifestyle Shot (16:9, in use)
# - Detail Shot (4:3, close-up features)
```

### Carousel

```python
result = gemini_run(
    action="create_workflow",
    template_type="carousel",
    topic="5 Productivity Tips",
    num_slides=5
)

# Returns workflow with 5 scenes (1:1 each)
```

## Generation Parameters

Gemini Imagen 3 supports:

- **aspect_ratio**: `1:1`, `16:9`, `9:16`, `4:3`, `3:4`
- **style**: Any text style description (e.g., "photorealistic", "minimalist", "watercolor")
- **negative_prompt**: Things to avoid
- **num_variants**: How many variations to generate per prompt

Example:
```python
result = gemini_run(
    action="generate",
    prompt="Modern coffee shop interior",
    aspect_ratio="16:9",
    style="architectural photography",
    negative_prompt="people, clutter, dark lighting",
    num_variants=3
)
```

## Export Formats

### Individual Files

Saves each approved image separately:
```
output_dir/
├── logo.png
├── icon.png
├── banner.png
└── card.png
```

### Grid

Combines approved images into single grid:
```python
run(action="export",
    format="grid",
    grid_cols=2,        # 2 columns
    spacing=20,         # 20px between images
    background="#FFFFFF")
```

### Carousel (HTML)

Interactive web carousel:
```html
<!DOCTYPE html>
<html>
<head>
  <style>/* Carousel styles */</style>
</head>
<body>
  <div class="carousel">
    <img src="slide1.png" />
    <img src="slide2.png" />
    ...
  </div>
</body>
</html>
```

### Carousel (PDF)

Multi-page PDF with one image per page.

## Benefits

✅ **Incremental revisions** - Only regenerate changed assets
✅ **Cost efficient** - No wasted generations
✅ **Client control** - Asset-by-asset approval
✅ **Version history** - All variants tracked
✅ **Multi-format export** - Individual, grid, carousel
✅ **Template workflows** - Pre-built for common use cases
✅ **Style consistency** - Shared style guides across project

## Dependencies

- **Python 3.8+**
- **google-generativeai** - Gemini API client (`pip install google-generativeai`)
- **Pillow (PIL)** - Image processing (`pip install pillow`)
- **GEMINI_API_KEY** - Get from https://ai.google.dev/

## Setup

```bash
# Install dependencies
pip install google-generativeai pillow

# Set API key
export GEMINI_API_KEY="your-api-key-here"

# Test installation
python -c "import google.generativeai as genai; print('✓ Ready')"
```

## Example Projects

Run the example:

```bash
cd .duro/skills/image
python example_gemini_workflow.py
```

This generates:
- Workflow summary
- `gemini_workflow_template.json` - Complete workflow template

## Future Enhancements

- [ ] Batch generation (parallel API calls)
- [ ] Style transfer between approved images
- [ ] AI-powered variant selection (score variants)
- [ ] Direct integration with design tools (Figma, Canva)
- [ ] Video thumbnail generation
- [ ] Automatic color palette extraction
- [ ] Brand consistency scoring

## Troubleshooting

**Q: API key not working**
A: Ensure GEMINI_API_KEY is set: `echo $GEMINI_API_KEY`

**Q: "google-generativeai not found"**
A: Install it: `pip install google-generativeai`

**Q: Grid export fails**
A: Ensure all approved images exist at local_path

**Q: Images don't match style**
A: Use more specific style descriptions and negative prompts

**Q: Aspect ratios don't match**
A: Grid export requires same aspect ratio across images

## Support

Created: 2026-03-03
Version: 1.0.0
Contact: Check .duro/skills/image/ for latest updates
