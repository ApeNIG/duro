# Flow Integration - Scene-Based Video Workflow

Complete integration between Google Flow (Veo2) and scene-based project management for client video production.

## Problem Solved

**Challenge:** AI video generation is non-deterministic. Same prompt → different outputs each time.

**Client Impact:** When client requests revision to Scene 2, regenerating it also changes Scenes 1 & 3 (if done as one video).

**Solution:** Scene-based architecture with seed tracking and incremental composition.

## Architecture

```
video_project_manager.py       # Project/scene/variant tracking
      ↓
flow_project_automation.py     # Flow automation wrapper
      ↓
Playwright MCP                  # Browser automation
      ↓
Google Flow (Veo2)              # Video generation
```

## Files

1. **`video_project_manager.py`** - Core project management
   - Create/load `.vidproj` files
   - Track scenes, variants, metadata
   - Approve variants
   - Compose final video with ffmpeg

2. **`flow_project_automation.py`** - Flow automation helpers
   - Network monitoring setup
   - Seed extraction from requests
   - Workflow instructions

3. **`example_flow_workflow.py`** - Complete workflow example
   - Reference implementation
   - Client project walkthrough

## Workflow

### Phase 1: Setup

```python
from video_project_manager import run

# Create project
result = run(
    action="create_project",
    project_name="Client Product Video",
    description="15-second product launch video",
    metadata={"client": "Acme Corp", "deadline": "2026-03-10"}
)
project_id = result['project_id']

# Add scenes
run(action="add_scene", project_id=project_id,
    scene_name="Hero Shot",
    prompt="Cinematic hero shot of product...")

run(action="add_scene", project_id=project_id,
    scene_name="Feature Demo",
    prompt="Close-up of product features...")
```

### Phase 2: Generation (per scene)

**Via Claude Code with Playwright MCP:**

```javascript
// 1. Navigate to Flow
mcp__playwright__browser_navigate({
    url: "https://labs.google/fx/tools/flow/project/<YOUR_PROJECT_ID>"
})

// 2. Setup network monitoring
mcp__playwright__browser_run_code({
    code: `async (page) => {
        window.capturedRequests = [];
        page.on('request', request => {
            const url = request.url();
            if (url.includes('batchAsyncGenerateVideoText')) {
                page.evaluate((data) => {
                    window.capturedRequests.push(data);
                }, {
                    url: url,
                    postData: request.postData()
                });
            }
        });
        return "Monitoring active";
    }`
})

// 3. Generate video
mcp__playwright__browser_type({
    ref: "e263",
    text: "Cinematic hero shot of product..."
})
mcp__playwright__browser_click({ref: "e269"})  // Create button

// 4. Wait for generation (90-120 seconds)
mcp__playwright__browser_wait_for({time: 120})

// 5. Extract seeds
mcp__playwright__browser_run_code({
    code: `async (page) => {
        const requests = await page.evaluate(() => window.capturedRequests);
        const seeds = [];
        for (const req of requests) {
            const data = JSON.parse(req.postData);
            for (const r of data.requests || []) {
                if (r.seed) seeds.push(r.seed);
            }
        }
        return seeds;
    }`
})
// Returns: [5816, 14619]
```

**Back to Python:**

```python
# Record variants with captured seeds
seeds = [5816, 14619]
urls = [
    "https://labs.google/fx/tools/flow/project/xxx/edit/yyy",
    "https://labs.google/fx/tools/flow/project/xxx/edit/zzz"
]

for seed, url in zip(seeds, urls):
    run(action="add_variant",
        project_id=project_id,
        scene_name="Hero Shot",
        seed=seed,
        flow_url=url)
```

### Phase 3: Client Review

1. **Present variants** - Send Flow URLs to client
2. **Client picks favorite** - Client selects Variant 2
3. **Download video** - Download from Flow
4. **Approve variant**:

```python
run(action="approve_variant",
    project_id=project_id,
    scene_name="Hero Shot",
    variant_id="<variant_2_id>",
    local_path="/path/to/hero_shot.mp4")
```

### Phase 4: Repeat for All Scenes

Repeat Phases 2-3 for each scene until all approved.

### Phase 5: Composition

```python
# Check status
result = run(action="status", project_id=project_id)
# {approved_scenes: 3/3, ready_to_compose: true}

# Compose final video
result = run(action="compose",
    project_id=project_id,
    output_path="/path/to/final.mp4")
# Uses ffmpeg to concatenate approved scenes
```

## Revision Workflow

**Client:** "Change Scene 2, keep Scene 1 & 3"

```python
# 1. Regenerate Scene 2 only in Flow (see Phase 2)
# 2. Capture new seeds/URLs
# 3. Add new variants to existing scene
run(action="add_variant",
    project_id=project_id,
    scene_name="Feature Demo",  # Scene 2
    seed=20241,
    flow_url="...")

# 4. Client picks new favorite
# 5. Approve new variant
run(action="approve_variant",
    project_id=project_id,
    scene_name="Feature Demo",
    variant_id="<new_variant_id>",
    local_path="/path/to/feature_demo_v2.mp4")

# 6. Re-compose (reuses Scene 1 & 3, replaces Scene 2)
run(action="compose",
    project_id=project_id,
    output_path="/path/to/final_revised.mp4")
```

**Cost Savings:** Only regenerate 1 scene instead of entire video.

## Project File Structure

```
~/video_projects/
└── abc123_456789/              # Project directory
    ├── abc123_456789.vidproj   # Project metadata (JSON)
    ├── scenes/                  # Scene-specific data
    ├── variants/                # Downloaded variant files
    │   ├── hero_shot_v1.mp4
    │   ├── hero_shot_v2.mp4
    │   └── feature_demo_v1.mp4
    ├── approved/                # Approved variants (symlinks)
    │   ├── scene_01.mp4 → ../variants/hero_shot_v2.mp4
    │   └── scene_02.mp4 → ../variants/feature_demo_v1.mp4
    ├── concat_list.txt          # ffmpeg concat input
    └── abc123_456789_final.mp4  # Final composed video
```

## .vidproj File Format

```json
{
  "id": "abc123_456789",
  "name": "Client Product Video",
  "description": "15-second product launch video",
  "scenes": [
    {
      "id": "scene_001",
      "name": "Hero Shot",
      "prompt": "Cinematic hero shot...",
      "order": 0,
      "status": "approved",
      "variants": [
        {
          "id": "var_001",
          "seed": 5816,
          "status": "rejected",
          "flow_url": "https://...",
          "local_path": null,
          "generated_at": "2026-03-03T06:45:00Z"
        },
        {
          "id": "var_002",
          "seed": 14619,
          "status": "approved",
          "flow_url": "https://...",
          "local_path": "/path/to/hero_shot_v2.mp4",
          "generated_at": "2026-03-03T06:45:00Z",
          "approved_at": "2026-03-03T07:00:00Z"
        }
      ],
      "approved_variant_id": "var_002"
    }
  ],
  "output_path": "/path/to/final.mp4",
  "created_at": "2026-03-03T06:00:00Z",
  "updated_at": "2026-03-03T08:00:00Z"
}
```

## Seed Tracking

Seeds are captured from Flow's API requests:

```json
POST https://aisandbox-pa.googleapis.com/v1/video:batchAsyncGenerateVideoText
{
  "requests": [{
    "seed": 5816,
    "textInput": {
      "structuredPrompt": {
        "parts": [{"text": "Cinematic hero shot..."}]
      }
    },
    "videoModelKey": "veo_3_1_t2v_fast"
  }]
}
```

**Purpose:** Document exact parameters for reproducibility research. Even though we can't control seeds, tracking them enables:
- Forensic analysis of what was generated
- Model version tracking
- Future reproducibility if Flow adds seed control

## Benefits

✅ **Incremental revisions** - Only regenerate changed scenes
✅ **Cost efficient** - No wasted generations
✅ **Client control** - Scene-by-scene approval
✅ **Version history** - All variants tracked
✅ **Metadata tracking** - Seeds, prompts, timestamps
✅ **Reproducible** - Full audit trail

## Example Projects

Run the example:

```bash
cd .duro/skills/video
python example_flow_workflow.py
```

This generates:
- Workflow summary
- `flow_workflow_template.json` - Complete workflow template

## Dependencies

- **Python 3.8+**
- **ffmpeg** - For video composition
- **Playwright MCP** - For browser automation (via Claude Code)
- **Google Flow access** - labs.google/fx/tools/flow

## Future Enhancements

- [ ] Automatic video download via Playwright
- [ ] Parallel scene generation
- [ ] Template library for common video types
- [ ] Cost tracking per project
- [ ] Client approval interface (web UI)
- [ ] Direct Flow API integration (if/when available)

## Troubleshooting

**Q: Seeds aren't being captured**
A: Ensure network monitoring is set up BEFORE clicking Create

**Q: Videos won't compose**
A: Check all scenes have approved variants with valid local_path

**Q: Download from Flow fails**
A: Flow doesn't expose direct download URLs - use browser save-as

**Q: ffmpeg error "Invalid data found"**
A: Ensure all videos have same codec/resolution

## Support

Created: 2026-03-03
Version: 1.0.0
Contact: Check .duro/skills/video/ for latest updates
