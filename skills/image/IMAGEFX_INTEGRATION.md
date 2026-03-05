# ImageFX Integration - Browser-Based Image Workflow

Complete integration between Gemini ImageFX (free web interface) and scene-based project management for client image production using Playwright browser automation.

**No API key required** - uses the free web interface at https://aitestkitchen.withgoogle.com/tools/image-fx

## Problem Solved

**Challenge:** AI image generation is non-deterministic and API costs add up quickly for client projects.

**Client Impact:** When client requests revision to one image in a brand kit, regenerating via paid API is expensive.

**Solution:** Scene-based architecture with browser automation (free) + seed/metadata tracking.

## Architecture

```
image_project_manager.py       # Project/scene/variant tracking
      ↓
imagefx_automation.py          # Browser automation instructions
      ↓
Playwright MCP                  # Browser automation
      ↓
ImageFX Web Interface           # Free image generation
      ↓
PIL/Pillow                      # Grid/carousel composition
```

## Comparison: API vs Browser

| Aspect | Gemini API | ImageFX Browser |
|--------|-----------|-----------------|
| Cost | Paid per image | Free |
| Speed | ~15-20s per image | ~30-45s per 4 images |
| Variants | Specify count | Always generates 4 |
| Control | Full API control | Browser automation |
| Limits | Rate limits | Daily usage limits |
| Setup | Requires API key | Just need Google account |

**Best for:** Client projects with budget constraints, prototyping, high-volume asset generation

## Workflow

### Phase 1: Project Setup

```python
from image_project_manager import run

# Create project (same as API version)
result = run(
    action="create_project",
    project_name="Coffee Brand Kit",
    description="Complete brand asset package",
    metadata={"client": "The Daily Grind", "deadline": "2026-03-15"}
)
project_id = result['project_id']

# Add scenes
run(action="add_scene", project_id=project_id,
    scene_name="Logo",
    prompt="Modern minimalist coffee shop logo...",
    aspect_ratio="1:1")
```

### Phase 2: Generation (via Browser)

**Step 1: Navigate to ImageFX**

```python
# Via Claude Code with Playwright MCP
mcp__playwright__browser_navigate({
    url: "https://aitestkitchen.withgoogle.com/tools/image-fx"
})
```

**Step 2: Setup Network Monitoring**

```javascript
mcp__playwright__browser_run_code({
    code: `async (page) => {
        await page.evaluate(() => {
            window.capturedRequests = [];
            window.capturedResponses = [];
        });

        page.on('request', request => {
            const url = request.url();
            if (url.includes('generateImages') || url.includes('imagen')) {
                page.evaluate((data) => {
                    window.capturedRequests.push(data);
                }, {
                    url: url,
                    postData: request.postData(),
                    timestamp: Date.now()
                });
            }
        });

        page.on('response', async response => {
            const url = response.url();
            if (url.includes('generateImages') || url.includes('imagen')) {
                try {
                    const data = await response.json();
                    await page.evaluate((d) => {
                        window.capturedResponses.push(d);
                    }, {url: url, data: data, timestamp: Date.now()});
                } catch (e) {}
            }
        });

        return "Network monitoring active";
    }`
})
```

**Step 3: Generate Images**

```javascript
// Take snapshot to find UI elements
mcp__playwright__browser_snapshot({})

// Type prompt (use ref from snapshot)
mcp__playwright__browser_type({
    ref: "e125",  // Prompt textbox ref
    text: "Modern minimalist coffee shop logo, simple coffee bean icon, warm brown and cream colors, clean geometric design"
})

// Click generate (use ref from snapshot)
mcp__playwright__browser_click({ref: "e132"})

// Wait for generation (30-45 seconds)
mcp__playwright__browser_wait_for({time: 45})
```

**Step 4: Extract Metadata and URLs**

```javascript
mcp__playwright__browser_run_code({
    code: `async (page) => {
        const requests = await page.evaluate(() => window.capturedRequests || []);
        const responses = await page.evaluate(() => window.capturedResponses || []);

        // Extract parameters
        const params = [];
        for (const req of requests) {
            try {
                const data = JSON.parse(req.postData || '{}');
                params.push({
                    prompt: data.prompt || data.textInput,
                    timestamp: req.timestamp
                });
            } catch (e) {}
        }

        // Extract image URLs
        let imageUrls = [];
        for (const resp of responses) {
            if (resp.data && resp.data.images) {
                for (const img of resp.data.images) {
                    if (img.url) imageUrls.push(img.url);
                }
            }
        }

        // Fallback: Extract from DOM
        if (imageUrls.length === 0) {
            imageUrls = await page.evaluate(() => {
                const imgs = Array.from(document.querySelectorAll('img[src*="googleusercontent"]'));
                return imgs.map(img => img.src);
            });
        }

        return {
            generation_params: params,
            image_urls: imageUrls,
            count: imageUrls.length
        };
    }`
})
// Returns: {generation_params: [...], image_urls: [url1, url2, url3, url4], count: 4}
```

**Step 5: Download Images**

Option A - Automated (preferred):
```javascript
mcp__playwright__browser_run_code({
    code: `async (page) => {
        const urls = ["url1", "url2", "url3", "url4"];
        const outputDir = "C:/Users/username/image_projects/abc123/logo";

        const downloads = [];
        for (let i = 0; i < urls.length; i++) {
            const response = await page.evaluate(async (url) => {
                const resp = await fetch(url);
                const blob = await resp.blob();
                const reader = new FileReader();
                return new Promise((resolve) => {
                    reader.onloadend = () => resolve(reader.result);
                    reader.readAsDataURL(blob);
                });
            }, urls[i]);

            // Save via Node.js fs in browser context or return base64
            downloads.push({
                variant_index: i + 1,
                url: urls[i],
                base64: response
            });
        }
        return downloads;
    }`
})
```

Option B - Manual:
- Right-click each image
- Save as `logo_v1.png`, `logo_v2.png`, etc.

**Step 6: Record Variants**

```python
# Back to Python - record downloaded variants
image_data = [
    {"url": "url1", "local_path": "~/image_projects/abc123/logo/logo_v1.png"},
    {"url": "url2", "local_path": "~/image_projects/abc123/logo/logo_v2.png"},
    {"url": "url3", "local_path": "~/image_projects/abc123/logo/logo_v3.png"},
    {"url": "url4", "local_path": "~/image_projects/abc123/logo/logo_v4.png"}
]

for i, img in enumerate(image_data):
    run(action="add_variant",
        project_id=project_id,
        scene_name="Logo",
        generation_params={
            "prompt": "Modern minimalist coffee shop logo...",
            "timestamp": 1709461234567 + i,
            "source": "imagefx_browser"
        },
        local_path=img['local_path'])
```

### Phase 3: Client Review & Approval

```python
# Client reviews 4 variants, picks favorite
run(action="approve_variant",
    project_id=project_id,
    scene_name="Logo",
    variant_id="<selected_variant_id>")
```

### Phase 4: Repeat for All Scenes

Repeat Phases 2-3 for each asset in your brand kit.

### Phase 5: Export

```python
# Export grid
run(action="export",
    project_id=project_id,
    format="grid",
    output_path="~/deliverables/brand_kit_overview.png",
    grid_cols=2)

# Export individual files
run(action="export",
    project_id=project_id,
    format="individual",
    output_dir="~/deliverables/brand_kit")
```

## Helper: Using imagefx_automation.py

Get pre-built workflow instructions:

```python
from imagefx_automation import run as imagefx_run

# Get complete workflow for a scene
result = imagefx_run(
    action="workflow",
    scene_name="Logo",
    prompt="Modern minimalist coffee shop logo...",
    output_dir="~/image_projects/abc123/logo",
    num_variants=4
)

# Returns: Detailed Playwright MCP instructions for setup → generate → download
print(result['instructions'])
```

## ImageFX Specifics

### URL
https://aitestkitchen.withgoogle.com/tools/image-fx

### Generation Pattern
- Always generates **4 variants** per prompt
- Takes ~30-45 seconds
- Aspect ratios: Square (1:1), Landscape (16:9), Portrait (9:16)
- Style can be specified in prompt text

### Prompt Best Practices
- Be specific with style (e.g., "minimalist vector design", "photorealistic", "watercolor painting")
- Include negative constraints in prompt (e.g., "no text, no clutter")
- Specify colors explicitly
- Use descriptive adjectives

### Network Monitoring
ImageFX API endpoints to monitor:
- `generateImages` - Generation request
- `imagen` - Image service
- Look for `googleusercontent.com` URLs in responses

### Download URLs
Generated images are hosted on `*.googleusercontent.com` with temporary URLs. Download them immediately after generation.

## Project File Structure

```
~/image_projects/
└── abc123_456789/
    ├── abc123_456789.imgproj
    ├── scenes/
    │   └── logo/
    │       ├── logo_v1.png (from ImageFX)
    │       ├── logo_v2.png (from ImageFX)
    │       ├── logo_v3.png (from ImageFX)
    │       └── logo_v4.png (from ImageFX)
    ├── approved/
    │   └── logo.png → ../scenes/logo/logo_v2.png
    └── exports/
        └── brand_kit_grid.png
```

## Revision Workflow

**Client:** "Logo looks great, but make the banner darker"

```python
# 1. Navigate back to ImageFX (Phases 2.1-2.2)

# 2. Enter revised prompt
mcp__playwright__browser_type({
    ref: "e125",
    text: "Social media banner for coffee shop, DARK MOODY ATMOSPHERE, dim cafe interior with candlelight"
})

# 3. Generate, extract URLs, download (Phases 2.3-2.5)

# 4. Record new variants
for img in new_images:
    run(action="add_variant",
        scene_name="Social Banner",
        generation_params={...},
        local_path=img['local_path'])

# 5. Client approves new favorite
run(action="approve_variant",
    scene_name="Social Banner",
    variant_id="<new_variant_id>")

# 6. Re-export (keeps Logo, replaces Banner)
run(action="export", format="grid", ...)
```

**Cost:** Free (no API charges)

## Benefits

✅ **Zero API Cost** - Uses free ImageFX web interface
✅ **Scene-Based Control** - Only regenerate changed assets
✅ **Batch Generation** - 4 variants per prompt automatically
✅ **Browser Automation** - Reproducible workflow via Playwright
✅ **Metadata Tracking** - Capture generation parameters from network
✅ **Multi-Format Export** - Grid, individual, carousel

## Dependencies

- **Python 3.8+**
- **Pillow (PIL)** - Image processing (`pip install pillow`)
- **Playwright MCP** - Browser automation (via Claude Code)
- **Google Account** - For ImageFX access

## Setup

```bash
# Install dependencies
pip install pillow

# Ensure Playwright MCP is available in Claude Code
# Navigate to ImageFX and sign in with Google account
```

## Limitations

1. **Daily Limits** - ImageFX has daily generation limits (typically generous)
2. **4 Variants Only** - Cannot control variant count (always 4)
3. **Manual Workflow** - Requires browser interaction (not fully automated)
4. **Temporary URLs** - Must download images immediately after generation
5. **No Seed Control** - Cannot set specific seeds (same as Flow)

## When to Use API vs Browser

**Use ImageFX Browser When:**
- Budget is limited
- Client project with <50 images
- Prototyping phase
- Learning the workflow

**Use Gemini API When:**
- Need full automation
- High-volume generation (>100 images)
- Production environment with CI/CD
- Need programmatic control

## Troubleshooting

**Q: Network monitoring not capturing URLs**
A: Ensure monitoring is set up BEFORE clicking generate

**Q: Download fails**
A: Use manual right-click save as fallback

**Q: Images expired (404)**
A: URLs are temporary - download immediately after generation

**Q: Daily limit reached**
A: Wait 24 hours or use different Google account

**Q: Generation takes too long**
A: ImageFX can take 45-60s during high traffic, be patient

## Example: Complete Brand Kit

```python
# 1. Create project with 4 scenes
project_id = run(action='create_project', ...)['project_id']

# 2. For each scene:
for scene in ["Logo", "Icon", "Banner", "Card"]:
    # Generate via browser (Playwright steps)
    # → Get 4 variants

    # Download images
    # → Save to scenes/scene_name/

    # Record variants
    for i in range(4):
        run(action='add_variant', scene_name=scene, ...)

    # Client picks favorite
    run(action='approve_variant', scene_name=scene, ...)

# 3. Export deliverables
run(action='export', format='grid', ...)
```

**Total Cost:** $0 (vs ~$8-12 with API)
**Total Time:** ~20 minutes (4 scenes × 5 minutes)

## Support

Created: 2026-03-03
Version: 1.0.0
Location: .duro/skills/image/
Related: video workflow uses same pattern with Flow
