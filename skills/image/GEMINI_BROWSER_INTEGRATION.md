# Gemini Browser Integration

**Free image generation via Gemini web interface using Playwright automation**

No API key needed. Uses `gemini.google.com/app` with Imagen 3.

---

## Quick Reference

| Item | Value |
|------|-------|
| URL | `https://gemini.google.com/app` |
| Generation time | ~30 seconds |
| Variants per generation | 1 (request more in chat) |
| Output resolution | High (typically 2048x2048, ~6MB) |
| Cost | Free |
| Auth | Google account (browser logged in) |

---

## Complete Workflow

### Step 1: Navigate to Gemini

```javascript
mcp__playwright__browser_navigate({
    url: "https://gemini.google.com/app"
})
```

### Step 2: Take Snapshot & Click "Create image"

```javascript
mcp__playwright__browser_snapshot({})
// Find "Create image" button ref

mcp__playwright__browser_click({
    ref: "<create_image_ref>",
    element: "Create image button"
})
```

### Step 3: Enter Prompt & Generate

```javascript
// After clicking Create image, a style picker appears
// Take another snapshot to find the textbox

mcp__playwright__browser_snapshot({})

mcp__playwright__browser_type({
    ref: "<textbox_ref>",
    text: "Modern minimalist coffee shop logo, warm brown colors",
    submit: true
})
```

### Step 4: Wait for Generation

```javascript
mcp__playwright__browser_wait_for({
    time: 30
})
```

### Step 5: Download Full Size Image

```javascript
mcp__playwright__browser_snapshot({})
// Find "Download full size image" button

mcp__playwright__browser_click({
    ref: "<download_button_ref>",
    element: "Download full size image"
})

mcp__playwright__browser_wait_for({
    time: 5
})
// File saves to .playwright-mcp/Gemini_Generated_Image_*.png
```

---

## Style Presets

Click a style before entering prompt to apply it:

| Style | Best For |
|-------|----------|
| Monochrome | B&W art, minimalist |
| Sketch | Hand-drawn look |
| Cinematic | Dramatic scenes |
| Oil painting | Classic art feel |
| Surreal | Abstract concepts |
| Soft portrait | People, headshots |
| Enamel pin | Icons, badges |
| Color block | Bold graphics |

**All 20 styles:** Monochrome, Color block, Runway, Risograph, Technicolor, Gothic clay, Dynamite, Salon, Sketch, Cinematic, Steampunk, Sunrise, Mythic fighter, Surreal, Moody, Enamel pin, Cyborg, Soft portrait, Old cartoon, Oil painting

---

## Getting Multiple Variants

Gemini generates 1 image per request. For variants:

**Option 1: Regenerate with same prompt**
```javascript
mcp__playwright__browser_type({
    ref: "<textbox_ref>",
    text: "generate another variation",
    submit: true
})
```

**Option 2: Request multiple in one prompt**
```javascript
mcp__playwright__browser_type({
    ref: "<textbox_ref>",
    text: "give me 3 different variations of this logo",
    submit: true
})
```

---

## Integration with image_project_manager

```python
from image_project_manager import run

# Create project
result = run(
    action='create_project',
    project_name='Coffee Brand Kit',
    project_type='brand_kit'
)
project_id = result['project_id']

# Add scene
run(action='add_scene',
    project_id=project_id,
    scene_name='Logo',
    prompt='Modern minimalist coffee shop logo',
    aspect_ratio='1:1')

# After generating in browser and downloading...
# Record variant
run(action='add_variant',
    project_id=project_id,
    scene_name='Logo',
    generation_params={
        'source': 'gemini',
        'timestamp': 1709461234567,
        'style': 'Sketch'
    },
    local_path='~/.playwright-mcp/Gemini_Generated_Image_abc123.png')

# Approve and export
run(action='approve_variant',
    project_id=project_id,
    scene_name='Logo',
    variant_id='<variant_id>')

run(action='export',
    project_id=project_id,
    format='individual',
    output_path='~/deliverables/')
```

---

## Comparison: Gemini vs ImageFX

| Aspect | Gemini | ImageFX |
|--------|--------|---------|
| URL | gemini.google.com/app | labs.google/fx/tools/image-fx |
| Status | Active | Sunset April 30, 2026 |
| Variants | 1 per request | 4 automatic |
| Resolution | ~2048x2048 (6MB) | 1408x768 (130KB) |
| Style presets | 20 visual styles | Seed/Model controls |
| Chat context | Yes (can iterate) | No |

**Recommendation:** Use Gemini. Higher quality, not being sunset, chat-based iteration.

---

## Troubleshooting

### "Create image" button not visible
- Scroll down or take full page snapshot
- May need to dismiss notices first

### Generation fails
- Check if logged into Google account
- Some prompts may be rejected (content policy)

### Download doesn't start
- Click button may need `cursor=pointer` check
- Wait for "Downloading..." indicator to appear

### File not in expected location
- Default: `.playwright-mcp/Gemini_Generated_Image_*.png`
- Check browser download settings

---

## File Locations

| Item | Path |
|------|------|
| Automation script | `~/.duro/skills/image/gemini_browser_automation.py` |
| Project manager | `~/.duro/skills/image/image_project_manager.py` |
| Downloads | `~/.playwright-mcp/Gemini_Generated_Image_*.png` |
| Projects | `~/image_projects/{project_id}/` |

---

**Last Updated:** 2026-03-03
