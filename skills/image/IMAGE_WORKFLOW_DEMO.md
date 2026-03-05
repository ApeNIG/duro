# Minimalist Coffee Brand Kit - Image Workflow Demo

**Project Type:** Brand Asset Kit
**Created:** 2026-03-03
**Use Case:** Independent coffee shop needs complete brand identity package

## What We're Building

A complete brand kit using the Gemini image workflow with scene-based management:
- Logo (1:1)
- App Icon (1:1)
- Social Media Banner (16:9)
- Business Card Design (3:2)

---

## Phase 1: Project Setup ✓

```python
from image_project_manager import run

# Create project
result = run(
    action='create_project',
    project_name='Minimalist Coffee Brand Kit',
    description='Complete brand identity for artisan coffee shop',
    project_type='brand_kit',
    metadata={
        'client': 'The Daily Grind Cafe',
        'deadline': '2026-03-10',
        'budget': '$600'
    }
)
# → project_id: f4a2b8c1_892471

# Add Scene 1: Logo
run(
    action='add_scene',
    project_id='f4a2b8c1_892471',
    scene_name='Logo',
    scene_type='logo',
    prompt='Minimalist coffee shop logo, simple coffee bean icon, warm brown and cream colors, clean geometric design, modern typography',
    aspect_ratio='1:1'
)
# → scene_id: d8f3e2a1_892485

# Add Scene 2: App Icon
run(
    action='add_scene',
    project_id='f4a2b8c1_892471',
    scene_name='App Icon',
    scene_type='icon',
    prompt='Mobile app icon for coffee shop, simplified coffee cup icon, warm colors, recognizable at small size, rounded square',
    aspect_ratio='1:1'
)
# → scene_id: c7b4a9e2_892493

# Add Scene 3: Social Banner
run(
    action='add_scene',
    project_id='f4a2b8c1_892471',
    scene_name='Social Banner',
    scene_type='banner',
    prompt='Social media banner for artisan coffee shop, cozy cafe interior with latte art, warm natural lighting, inviting atmosphere',
    aspect_ratio='16:9'
)
# → scene_id: b6c5d8f3_892501

# Add Scene 4: Business Card
run(
    action='add_scene',
    project_id='f4a2b8c1_892471',
    scene_name='Business Card',
    scene_type='card',
    prompt='Business card design for coffee shop, minimalist layout, coffee bean pattern background, elegant typography',
    aspect_ratio='3:2'
)
# → scene_id: a5b6c7d8_892509
```

**Result:** Project created with 4 asset scenes

---

## Phase 2: Generate Scene 1 (Logo) ✓

**Via Gemini API:**

```python
from gemini_image_automation import run as gemini_run

# Generate Logo variants
result = gemini_run(
    action='generate',
    prompt='Minimalist coffee shop logo, simple coffee bean icon, warm brown and cream colors, clean geometric design, modern typography',
    num_variants=3,
    aspect_ratio='1:1',
    style='modern minimalist vector',
    negative_prompt='cluttered, dark, complex, realistic photo',
    output_dir='~/image_projects/f4a2b8c1_892471/scenes/logo'
)

# API generates 3 variants:
# - logo_v1_1709461234567.png (timestamp-based naming)
# - logo_v2_1709461234589.png
# - logo_v3_1709461234612.png
```

**Generation Parameters Captured:**
- Variant 1: timestamp 1709461234567, aspect_ratio 1:1
- Variant 2: timestamp 1709461234589, aspect_ratio 1:1
- Variant 3: timestamp 1709461234612, aspect_ratio 1:1

**Result:** 3 logo variants ready for review

---

## Phase 3: Record Variants ✓

```python
# Variant 1
run(
    action='add_variant',
    project_id='f4a2b8c1_892471',
    scene_name='Logo',
    generation_params={
        'prompt': 'Minimalist coffee shop logo...',
        'aspect_ratio': '1:1',
        'timestamp': 1709461234567
    },
    local_path='~/image_projects/f4a2b8c1_892471/scenes/logo/logo_v1_1709461234567.png'
)
# → variant_id: e4f5a6b7_194123

# Variant 2
run(
    action='add_variant',
    project_id='f4a2b8c1_892471',
    scene_name='Logo',
    generation_params={
        'prompt': 'Minimalist coffee shop logo...',
        'aspect_ratio': '1:1',
        'timestamp': 1709461234589
    },
    local_path='~/image_projects/f4a2b8c1_892471/scenes/logo/logo_v2_1709461234589.png'
)
# → variant_id: d5e6f7a8_194145

# Variant 3
run(
    action='add_variant',
    project_id='f4a2b8c1_892471',
    scene_name='Logo',
    generation_params={
        'prompt': 'Minimalist coffee shop logo...',
        'aspect_ratio': '1:1',
        'timestamp': 1709461234612
    },
    local_path='~/image_projects/f4a2b8c1_892471/scenes/logo/logo_v3_1709461234612.png'
)
# → variant_id: c6d7e8f9_194167
```

**Status:** Scene 1 moved to "review" status with 3 variants

---

## Phase 4: Client Approval ✓

**Client Decision:**
- Reviewed all 3 logo variants
- **Selected:** Variant 2 (clean, professional, memorable)
- **Rejected:** Variant 1 (too simple), Variant 3 (too complex)

**System Action:**
```python
run(
    action='approve_variant',
    project_id='f4a2b8c1_892471',
    scene_name='Logo',
    variant_id='d5e6f7a8_194145'
)
```

**Result:**
- Scene 1 (Logo): ✓ APPROVED
- Variant 2: status → approved
- Variant 1 & 3: status → rejected (automatic)
- Project: 25% complete (1/4 scenes approved)

---

## Phase 5: Generate Remaining Scenes

### App Icon (Same Process)

```python
# Generate variants
result = gemini_run(
    action='generate',
    prompt='Mobile app icon for coffee shop, simplified coffee cup icon, warm colors, recognizable at small size, rounded square',
    num_variants=2,
    aspect_ratio='1:1',
    style='flat design icon',
    output_dir='~/image_projects/f4a2b8c1_892471/scenes/icon'
)

# Record variants
for img in result['images']:
    run(action='add_variant',
        scene_name='App Icon',
        generation_params={...},
        local_path=img['local_path'])

# Client approves favorite
run(action='approve_variant',
    scene_name='App Icon',
    variant_id='<selected_variant>')
```

**Progress:** 50% complete (2/4 scenes approved)

### Social Banner

```python
# Generate 16:9 banner variants
result = gemini_run(
    action='generate',
    prompt='Social media banner for artisan coffee shop, cozy cafe interior with latte art, warm natural lighting, inviting atmosphere',
    num_variants=3,
    aspect_ratio='16:9',
    style='lifestyle photography',
    output_dir='~/image_projects/f4a2b8c1_892471/scenes/banner'
)

# Record + approve
# ...
```

**Progress:** 75% complete (3/4 scenes approved)

### Business Card

```python
# Generate 3:2 card design variants
result = gemini_run(
    action='generate',
    prompt='Business card design for coffee shop, minimalist layout, coffee bean pattern background, elegant typography',
    num_variants=2,
    aspect_ratio='3:2',
    style='print design minimalist',
    output_dir='~/image_projects/f4a2b8c1_892471/scenes/card'
)

# Record + approve
# ...
```

**Progress:** 100% complete (4/4 scenes approved) ✓

---

## Phase 6: Export Deliverables ✓

### Check Status

```python
result = run(action='status', project_id='f4a2b8c1_892471')
# {
#   'approved_scenes': 4,
#   'total_scenes': 4,
#   'ready_to_export': True,
#   'completion_percentage': 100
# }
```

### Export Individual Files

```python
result = run(
    action='export',
    project_id='f4a2b8c1_892471',
    format='individual',
    output_dir='~/deliverables/coffee_brand_kit'
)

# Creates:
# ~/deliverables/coffee_brand_kit/
#   ├── logo.png
#   ├── app_icon.png
#   ├── social_banner.png
#   └── business_card.png
```

### Export as Grid

```python
result = run(
    action='export',
    project_id='f4a2b8c1_892471',
    format='grid',
    output_path='~/deliverables/coffee_brand_kit_overview.png',
    grid_cols=2,
    spacing=30,
    background='#FAF9F6'
)

# Creates single image with 2x2 grid layout
```

### Export as Carousel

```python
# HTML carousel for client presentation
result = run(
    action='export',
    project_id='f4a2b8c1_892471',
    format='carousel_html',
    output_path='~/deliverables/coffee_carousel.html'
)

# Interactive web page with all assets
```

---

## Project File Structure (Final)

```
~/image_projects/f4a2b8c1_892471/
├── f4a2b8c1_892471.imgproj              # Project metadata
├── scenes/                               # Scene organization
│   ├── logo/
│   │   ├── logo_v1_1709461234567.png (rejected)
│   │   ├── logo_v2_1709461234589.png (approved) ✓
│   │   └── logo_v3_1709461234612.png (rejected)
│   ├── icon/
│   │   ├── icon_v1_1709461245678.png (rejected)
│   │   └── icon_v2_1709461245701.png (approved) ✓
│   ├── banner/
│   │   ├── banner_v1_1709461256789.png (rejected)
│   │   ├── banner_v2_1709461256812.png (rejected)
│   │   └── banner_v3_1709461256835.png (approved) ✓
│   └── card/
│       ├── card_v1_1709461267890.png (approved) ✓
│       └── card_v2_1709461267913.png (rejected)
├── approved/                             # Symlinks to approved variants
│   ├── logo.png → ../scenes/logo/logo_v2_1709461234589.png
│   ├── icon.png → ../scenes/icon/icon_v2_1709461245701.png
│   ├── banner.png → ../scenes/banner/banner_v3_1709461256835.png
│   └── card.png → ../scenes/card/card_v1_1709461267890.png
└── exports/
    ├── coffee_brand_kit_overview.png    # Grid export
    └── coffee_carousel.html              # Carousel export
```

---

## .imgproj File (Final State)

```json
{
  "id": "f4a2b8c1_892471",
  "name": "Minimalist Coffee Brand Kit",
  "description": "Complete brand identity for artisan coffee shop",
  "project_type": "brand_kit",
  "scenes": [
    {
      "id": "d8f3e2a1_892485",
      "name": "Logo",
      "scene_type": "logo",
      "order": 0,
      "status": "approved",
      "prompt": "Minimalist coffee shop logo...",
      "aspect_ratio": "1:1",
      "variants": [
        {
          "id": "e4f5a6b7_194123",
          "status": "rejected",
          "local_path": "~/image_projects/.../logo_v1_1709461234567.png",
          "generation_params": {
            "prompt": "...",
            "aspect_ratio": "1:1",
            "timestamp": 1709461234567
          },
          "generated_at": "2026-03-03T08:00:34Z"
        },
        {
          "id": "d5e6f7a8_194145",
          "status": "approved",
          "local_path": "~/image_projects/.../logo_v2_1709461234589.png",
          "generation_params": {...},
          "generated_at": "2026-03-03T08:00:34Z",
          "approved_at": "2026-03-03T08:15:00Z"
        },
        {
          "id": "c6d7e8f9_194167",
          "status": "rejected",
          "local_path": "~/image_projects/.../logo_v3_1709461234612.png",
          "generation_params": {...},
          "generated_at": "2026-03-03T08:00:34Z"
        }
      ],
      "approved_variant_id": "d5e6f7a8_194145"
    },
    {
      "id": "c7b4a9e2_892493",
      "name": "App Icon",
      "status": "approved",
      "approved_variant_id": "...",
      "variants": [...]
    },
    {
      "id": "b6c5d8f3_892501",
      "name": "Social Banner",
      "status": "approved",
      "approved_variant_id": "...",
      "variants": [...]
    },
    {
      "id": "a5b6c7d8_892509",
      "name": "Business Card",
      "status": "approved",
      "approved_variant_id": "...",
      "variants": [...]
    }
  ],
  "created_at": "2026-03-03T07:55:00Z",
  "updated_at": "2026-03-03T09:30:00Z",
  "metadata": {
    "client": "The Daily Grind Cafe",
    "deadline": "2026-03-10",
    "budget": "$600"
  }
}
```

---

## Revision Workflow Example

**Scenario:** Client says "Logo looks great, but make the social banner darker and moodier"

### Option A: Regenerate Banner Only

```python
# 1. Generate new banner variants with adjusted prompt
result = gemini_run(
    action='generate',
    prompt='Social media banner for artisan coffee shop, DARK MOODY ATMOSPHERE, dim cafe interior with candlelight, intimate evening setting, deep shadows',
    num_variants=2,
    aspect_ratio='16:9',
    style='moody lifestyle photography',
    output_dir='~/image_projects/f4a2b8c1_892471/scenes/banner'
)
# Captures new timestamps: [1709468901234, 1709468901256]

# 2. Add new variants to existing Banner scene
for img in result['images']:
    run(action='add_variant',
        scene_name='Social Banner',
        generation_params={...},
        local_path=img['local_path'])

# 3. Client reviews and picks favorite new variant

# 4. Approve new variant
run(action='approve_variant',
    scene_name='Social Banner',
    variant_id='<new_variant_id>')

# 5. Re-export (reuses Logo, Icon, Card; replaces Banner)
run(action='export',
    format='grid',
    output_path='~/deliverables/coffee_brand_kit_v2.png')
```

**Cost Savings:**
- Only regenerated 1 asset (Social Banner)
- Logo, Icon, Card (approved variants) unchanged
- No wasted work

---

## Key Benefits Demonstrated

✓ **Asset-by-Asset Approval**
- Client reviews and approves each asset independently
- No "all or nothing" regeneration

✓ **Generation Tracking**
- Captured exact parameters (timestamps, prompts, aspect ratios)
- Full reproducibility audit trail

✓ **Version History**
- All variants tracked (10 total variants generated, 4 approved)
- Can trace back to exact generation

✓ **Incremental Workflow**
- Approved assets locked in
- Unapproved assets can be regenerated independently

✓ **Revision-Friendly**
- Only regenerate changed assets
- Approved assets remain untouched

✓ **Multi-Format Export**
- Individual files for production use
- Grid for client presentation
- Carousel for interactive review

---

## Cost & Time Comparison

**Traditional Approach (Full Kit Each Time):**
- Generate full kit: 4 assets × 3 variants = 12 images
- Client wants change → Regenerate full kit: 12 more images
- Total: 24 images generated
- Time: ~10 minutes (if 25 seconds per image)

**Scene-Based Approach:**
- Generate Logo (3 variants) = 3 images
- Client approves Logo ✓
- Generate Icon (2 variants) = 2 images
- Client approves Icon ✓
- Generate Banner (3 variants) = 3 images
- Client approves Banner ✓
- Generate Card (2 variants) = 2 images
- Client approves Card ✓
- Client wants Banner revision → Only regenerate Banner (2 variants) = 2 images
- Total: 12 images generated (vs 24 traditional)
- Time: ~5 minutes
- **Savings: 50% fewer images, 50% less time**

**Value:** More control, better workflow, cleaner revisions, lower cost

---

## Template Workflow Benefits

Using the built-in `brand_kit` template:

```python
from gemini_image_automation import run as gemini_run

# One command creates entire workflow
result = gemini_run(
    action='generate_brand_kit',
    brand_name='The Daily Grind Cafe',
    brand_description='Artisan coffee shop with cozy atmosphere',
    style_guide={
        'colors': ['#8B4513', '#F5DEB3', '#FFFFFF'],
        'style': 'modern minimalist',
        'mood': 'warm and inviting'
    },
    output_dir='~/image_projects/f4a2b8c1_892471'
)

# Automatically generates:
# - Logo (3 variants)
# - Icon (2 variants)
# - Social Banner (2 variants)
# - Business Card (2 variants)
# Total: 9 images in one batch
```

**Benefit:** Consistent style across all assets from shared style guide

---

## Next: Production Use

To use this workflow for real client projects:

1. **Setup:**
   ```bash
   export GEMINI_API_KEY="your-api-key"
   pip install google-generativeai pillow
   ```

2. **Create Project:**
   ```python
   from image_project_manager import run
   result = run(action='create_project', ...)
   ```

3. **Generate Assets:**
   ```python
   from gemini_image_automation import run as gemini_run
   result = gemini_run(action='generate', ...)
   ```

4. **Manage & Export:**
   ```python
   run(action='approve_variant', ...)
   run(action='export', format='grid', ...)
   ```

**Estimated time for 4-asset brand kit:** 15-20 minutes (5-8 minutes generation + 10 minutes client review)

---

**Demo created:** 2026-03-03 09:45 UTC
**Project location:** `~/.duro/skills/image/image_project_manager.py`
**Integration docs:** `~/.duro/skills/image/GEMINI_INTEGRATION.md`
**Example workflow:** `~/.duro/skills/image/example_gemini_workflow.py`
