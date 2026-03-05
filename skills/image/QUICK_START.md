# ImageFX Workflow - Quick Start

**Free browser-based image generation for client projects**

No API key needed • Uses ImageFX web interface • Same pattern as Flow video workflow

---

## 5-Minute Setup

```bash
# Install dependencies
pip install pillow

# That's it! No API key required.
```

---

## Complete Workflow (3 Commands)

### 1. Create Project (Python)

```python
from image_project_manager import run

# Create project
result = run(
    action='create_project',
    project_name='My Brand Kit',
    project_type='brand_kit'
)
project_id = result['project_id']

# Add scene
run(action='add_scene',
    project_id=project_id,
    scene_name='Logo',
    prompt='Modern minimalist logo for tech company',
    aspect_ratio='1:1')
```

### 2. Generate in Browser (Playwright via Claude Code)

**Navigate:**
```javascript
mcp__playwright__browser_navigate({
    url: "https://aitestkitchen.withgoogle.com/tools/image-fx"
})
```

**Setup monitoring:**
```javascript
mcp__playwright__browser_run_code({code: `async (page) => {
    await page.evaluate(() => { window.capturedResponses = []; });
    page.on('response', async response => {
        if (response.url().includes('imagen')) {
            try {
                const data = await response.json();
                await page.evaluate((d) => window.capturedResponses.push(d), data);
            } catch (e) {}
        }
    });
    return "Monitoring active";
}`})
```

**Generate:**
```javascript
// Get snapshot to find UI refs
mcp__playwright__browser_snapshot({})

// Type prompt
mcp__playwright__browser_type({
    ref: "<prompt_textbox_ref>",
    text: "Modern minimalist logo for tech company"
})

// Click generate
mcp__playwright__browser_click({ref: "<generate_button_ref>"})

// Wait 45 seconds
mcp__playwright__browser_wait_for({time: 45})
```

**Extract URLs:**
```javascript
mcp__playwright__browser_run_code({code: `async (page) => {
    return await page.evaluate(() => {
        const imgs = Array.from(document.querySelectorAll('img[src*="googleusercontent"]'));
        return imgs.map(img => img.src);
    });
}`})
// Returns: ["url1", "url2", "url3", "url4"]
```

**Download:** Right-click save each image as `logo_v1.png`, `logo_v2.png`, etc.

### 3. Record & Export (Python)

```python
# Record variants
for i in range(1, 5):
    run(action='add_variant',
        project_id=project_id,
        scene_name='Logo',
        generation_params={'source': 'imagefx', 'timestamp': 1709461234567 + i},
        local_path=f'~/image_projects/{project_id}/scenes/logo/logo_v{i}.png')

# Client approves favorite
run(action='approve_variant',
    project_id=project_id,
    scene_name='Logo',
    variant_id='<selected_variant>')

# Export
run(action='export',
    project_id=project_id,
    format='grid',
    output_path='~/deliverables/brand_kit_grid.png')
```

---

## Helper: Get Pre-Built Instructions

```python
from imagefx_automation import run as imagefx_run

# Get complete workflow instructions
result = imagefx_run(
    action='workflow',
    scene_name='Logo',
    prompt='Modern minimalist logo...',
    output_dir='~/image_projects/abc123/logo'
)

print(result['instructions'])
```

---

## Cheat Sheet

| Task | Command |
|------|---------|
| Create project | `run(action='create_project', ...)` |
| Add scene | `run(action='add_scene', scene_name='Logo', ...)` |
| Generate (browser) | Navigate → Setup monitoring → Type prompt → Generate → Wait → Extract URLs → Download |
| Record variant | `run(action='add_variant', local_path='...')` |
| Approve variant | `run(action='approve_variant', variant_id='...')` |
| Export grid | `run(action='export', format='grid', ...)` |
| Export individual | `run(action='export', format='individual', ...)` |

---

## Typical Brand Kit (4 Assets)

```python
# Setup
project_id = run(action='create_project', ...)['project_id']
scenes = ['Logo', 'Icon', 'Banner', 'Card']
for scene in scenes:
    run(action='add_scene', scene_name=scene, ...)

# For each scene (in browser):
#   1. Generate → Get 4 variants
#   2. Download
#   3. Record variants
#   4. Client approves

# Export
run(action='export', format='grid', ...)
```

**Time:** ~20 minutes
**Cost:** $0

---

## Common Patterns

### Revision
```python
# Only regenerate changed scene
# Navigate to ImageFX → Generate new variants for that scene
# Record new variants → Client approves → Re-export
```

### Multiple Projects
```python
# Each project gets unique project_id
# All projects stored in ~/image_projects/
```

### Style Consistency
```python
# Use same style keywords across all scenes
# Example: "modern minimalist", "warm colors", "clean geometric"
```

---

## File Locations

- **Code:** `~/.duro/skills/image/`
- **Projects:** `~/image_projects/{project_id}/`
- **Deliverables:** `~/deliverables/`

---

## Documentation

- **Complete guide:** `IMAGEFX_INTEGRATION.md`
- **Example:** `example_imagefx_workflow.py`
- **Browser automation:** `imagefx_automation.py`
- **Project manager:** `image_project_manager.py`

---

## ImageFX URL

https://aitestkitchen.withgoogle.com/tools/image-fx

Sign in with Google account → Start generating (no setup needed)

---

## Comparison: Video vs Image

Same pattern, different media:

| Aspect | Flow (Video) | ImageFX (Image) |
|--------|-------------|-----------------|
| URL | labs.google/.../flow | aitestkitchen.../image-fx |
| Generation time | 90-120s | 30-45s |
| Variants | 2-3 | 4 (automatic) |
| Seed capture | ✓ | ✓ |
| Cost | Free | Free |

Both use: Scene-based architecture + Browser automation + Project management

---

**Quick Start Updated:** 2026-03-03
