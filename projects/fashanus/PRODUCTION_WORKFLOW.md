# The Fashanus - Production Workflow

## Overview

This document outlines the complete production workflow for creating "The Fashanus" - a weekly AI-generated family drama series for social media.

**Format:** AI-generated visuals + voiceover
**Platform:** TikTok (primary), Instagram Reels, YouTube Shorts
**Release:** Weekly episodes, 60-90 seconds each
**Structure:** 3 episodes from one perspective, then same story from different perspective

---

## Phase 1: Pre-Production (One-Time Setup)

### 1.1 Character Bible Creation

Before generating any images, document each character in detail. This ensures consistency across all episodes.

#### Tunde Fashanu (Dad, 35)
```
PHYSICAL DESCRIPTION:
- Height: Tall, athletic build
- Skin: Dark brown, Nigerian features
- Face: Strong jaw, kind eyes, short beard (neat)
- Hair: Short, fade cut
- Style: Smart casual - polo shirts, chinos for home; suits for work
- Distinctive: Wedding ring, simple watch

EXPRESSIONS TO CAPTURE:
- Neutral/thinking (most common)
- Warm smile (with family)
- Concerned/worried (money, kids' future)
- Proud (watching kids achieve)
- Tired (after work)

ENVIRONMENT ASSOCIATIONS:
- Living room armchair
- Kitchen table (head of table)
- Home office/laptop
- Car (driving kids)
```

#### Rachel Fashanu (Mum, 37)
```
PHYSICAL DESCRIPTION:
- Height: Average, slim build
- Skin: Fair, British features
- Face: Warm, expressive eyes, light freckles
- Hair: Shoulder-length, light brown, often tied back
- Style: Comfortable creative - jeans, nice tops, cardigans
- Distinctive: Wedding ring, small earrings

EXPRESSIONS TO CAPTURE:
- Multitasking/busy
- Loving (with kids)
- Frustrated (with Maya's mood swings)
- Thoughtful (working on creative projects)
- Laughing

ENVIRONMENT ASSOCIATIONS:
- Kitchen (hub of home)
- Living room sofa
- Home workspace with laptop
- School run
```

#### Maya Fashanu (Daughter, 11)
```
PHYSICAL DESCRIPTION:
- Height: Pre-teen, growing
- Skin: Light brown, mixed features
- Face: Expressive, Dad's eyes, Mum's face shape
- Hair: Curly, shoulder-length, natural texture
- Style: Trendy tween - leggings, graphic tees, hoodies
- Distinctive: Friendship bracelets, sometimes headphones

EXPRESSIONS TO CAPTURE:
- Eye-rolling (classic)
- Genuine smile (rare, precious)
- Focused (drawing, tennis)
- Upset/crying
- Laughing with friends

ENVIRONMENT ASSOCIATIONS:
- Bedroom (posters, art supplies)
- Kitchen doing homework
- School uniform
- Tennis court
```

#### Tayo Fashanu (Son, 8)
```
PHYSICAL DESCRIPTION:
- Height: Small, energetic
- Skin: Light brown, mixed features
- Face: Cheeky smile, curious eyes
- Hair: Short curls
- Style: Active kid - football kit, tracksuit, school uniform
- Distinctive: Usually has a ball or book nearby

EXPRESSIONS TO CAPTURE:
- Excited/hyper
- Concentrating (reading)
- Confused (absorbing family tension)
- Proud (showing something)
- Annoyed (with sister)

ENVIRONMENT ASSOCIATIONS:
- Living room floor (playing)
- Garden with football
- Bedroom with books
- Following Dad around
```

---

### 1.2 Character Image Generation

#### Tool: Gemini App + LM Arena

**Step 1: Generate Base Character Images**

Open Gemini App and use this prompt structure:

```
Create a realistic portrait photograph of [CHARACTER NAME],
a [age] year old [ethnicity description].

Physical details:
- [List from character bible]

Style: Photorealistic, natural lighting, neutral background
Expression: [Neutral/natural for reference image]
Framing: Head and shoulders portrait
```

**Example - Tunde:**
```
Create a realistic portrait photograph of Tunde,
a 35 year old Nigerian man living in the UK.

Physical details:
- Tall, athletic build
- Dark brown skin, Nigerian Yoruba features
- Strong jaw, kind eyes, short neat beard
- Short hair with fade cut
- Wearing a navy polo shirt

Style: Photorealistic, natural lighting, neutral background
Expression: Neutral, confident, slight warmth in eyes
Framing: Head and shoulders portrait
```

**Step 2: Remove Watermark (LM Arena)**

1. Go to lmarena.ai
2. Select "Direct Chat" mode
3. Choose "Generate Images"
4. Upload your Gemini image
5. Prompt: "Remove the watermark from this image, keep everything else identical"
6. Download clean version

**Step 3: Generate Expression Variants**

For each character, generate 5-6 expression variants:

```
Using this reference image of [NAME], generate the same person
with a [EXPRESSION] expression. Maintain exact same:
- Face structure
- Skin tone
- Hair
- Clothing
Keep photorealistic style, same lighting.
```

**Step 4: Generate Environment Shots**

```
Using this reference image of [NAME], show them in [LOCATION].
They are [ACTION/POSE].
Maintain exact character appearance.
Lighting: [SPECIFY - warm home lighting, daylight, evening]
Framing: [Wide shot / Medium shot / Close-up]
```

**Step 5: Save & Organize**

Create folder structure:
```
/fashanus/
  /characters/
    /tunde/
      tunde_reference.png
      tunde_neutral.png
      tunde_smiling.png
      tunde_worried.png
      tunde_proud.png
    /rachel/
      ...
    /maya/
      ...
    /tayo/
      ...
  /locations/
    living_room.png
    kitchen.png
    maya_bedroom.png
    tayo_bedroom.png
    front_garden.png
```

---

### 1.3 Location Design

Generate consistent locations for the Fashanu home:

**Living Room:**
```
Interior of a British suburban living room, working class family home.
Warm, lived-in feel. Grey sofa, family photos on wall, TV in corner,
kids' items visible. Evening warm lighting. Photorealistic.
```

**Kitchen:**
```
British suburban kitchen, heart of family home. Modern but not luxury.
White cabinets, wooden worktop, fridge with kids' drawings.
Morning light through window. Photorealistic.
```

Generate 3-4 angles of each main location for variety.

---

### 1.4 Voice Profile Setup

#### Tool: Chatterbox (Free, MIT License)

**Step 1: Access Chatterbox**
- HuggingFace Space: huggingface.co/spaces/resemble-ai/chatterbox
- Or self-host for faster generation

**Step 2: Create Voice Profiles**

For each character, find or create a reference voice:

| Character | Voice Direction |
|-----------|----------------|
| Tunde | Deep, measured, slight Nigerian accent (softened by years in UK) |
| Rachel | Warm, northern English accent, expressive |
| Maya | Young female, mix of parents' accents, can be sharp or soft |
| Tayo | Child voice, energetic, slightly higher pitch |

**Step 3: Test Clips**

Generate test lines for each character:

- Tunde: "Maya, come here. We need to talk about your future."
- Rachel: "Tunde, she's eleven. Let her be a child."
- Maya: "Why does he always do this? He doesn't get it."
- Tayo: "Mum, why is Dad upset? Did Maya do something?"

**Step 4: Save Voice Presets**

Document exact settings used for each character voice:
- Reference audio (if cloned)
- Emotion/intensity settings
- Speed settings

---

## Phase 2: Episode Planning

### 2.1 Story Arc Structure

**The Fashanus Format:**
```
Week 1: Episode 1A - Story from Character A's perspective
Week 2: Episode 1B - Same story, different angle, building
Week 3: Episode 1C - Climax of this perspective
Week 4: Episode 1D - Same story from Character B's perspective (revelation)
```

**Example Arc: "The Art Dream"**

| Episode | Perspective | Content |
|---------|-------------|---------|
| 1A | Maya | Maya excited about art competition, Dad dismissive |
| 1B | Maya | Maya works in secret, Mum notices, Dad finds out |
| 1C | Maya | Confrontation - "You never support me!" |
| 1D | Tunde | Reveal: Dad's fear comes from his own unfollowed dreams |

---

### 2.2 Episode Outline Template

```markdown
## Episode [NUMBER]: [TITLE]
### Perspective: [CHARACTER]

**Logline:** (One sentence summary)

**Emotional Arc:** [Starting emotion] → [Ending emotion]

**SCENE BREAKDOWN:**

SCENE 1 (0:00-0:15)
- Location:
- Characters:
- Action:
- Dialogue:
- Emotion:
- Shot type: (Wide/Medium/Close-up)

SCENE 2 (0:15-0:35)
- Location:
- Characters:
- Action:
- Dialogue:
- Emotion:
- Shot type:

SCENE 3 (0:35-0:55)
- Location:
- Characters:
- Action:
- Dialogue:
- Emotion:
- Shot type:

SCENE 4 (0:55-1:10)
- Location:
- Characters:
- Action:
- Dialogue (if any):
- Emotion:
- Shot type:

**HOOK:** (First 3 seconds - what grabs attention?)
**CLIFFHANGER/END:** (What makes them want the next episode?)

**MUSIC/TONE:**

**CAPTIONS/TEXT OVERLAY:**
```

---

### 2.3 Scene Prompt Template

For each scene, prepare the image generation prompt:

```
SCENE [X] IMAGE PROMPT:

Base: [Reference character image]

Scene description:
[CHARACTER] is in [LOCATION]. They are [ACTION].
Their expression shows [EMOTION].
[Other character] is [POSITION/ACTION] in the background.

Lighting: [Warm home / Daylight / Evening / Dramatic]
Framing: [Wide establishing / Medium two-shot / Close-up reaction]
Mood: [Tense / Warm / Sad / Hopeful]

Maintain exact character appearances from reference images.
Photorealistic style.
```

---

## Phase 3: Production

### 3.1 Weekly Production Schedule

| Day | Task | Time |
|-----|------|------|
| Monday | Write episode outline, plan scenes | 1-2 hours |
| Tuesday | Generate all scene images | 2-3 hours |
| Wednesday | Generate video clips from images | 2 hours |
| Thursday | Generate voiceover, edit together | 2-3 hours |
| Friday | Final edit, captions, review | 1-2 hours |
| Saturday | Schedule posts, engage with audience | 30 mins |
| Sunday | Rest / Plan next arc | - |

---

### 3.2 Image-to-Video Generation

#### Tool: LTX Studio (Free Tier)

**Step 1: Upload to Elements**

1. Log into LTX Studio
2. Go to Elements > Characters
3. Upload each character's reference images
4. Name them: "Tunde", "Rachel", "Maya", "Tayo"
5. The system locks their appearance

**Step 2: Create Scene**

1. New Project > Import scene image
2. Select which Elements (characters) are in scene
3. Add motion prompt:
   ```
   [Character] slowly turns head toward camera.
   Subtle movement, breathing visible.
   Duration: 3 seconds.
   ```

**Step 3: Generate Motion**

For dialogue scenes:
```
[Character] speaking emotionally, gesturing with hands.
Mouth movement matches speech rhythm.
Natural body language showing [EMOTION].
```

For reaction shots:
```
[Character] listening, expression shifting from [A] to [B].
Eyes show [EMOTION]. Subtle movement only.
```

**Step 4: Export Clips**

Export each scene as individual clip:
- Resolution: 1080x1920 (vertical)
- Format: MP4
- Length: 3-5 seconds per scene

---

### 3.3 Alternative: Kling AI 3.0

**For longer, more cinematic shots:**

1. Go to Kling AI (klingai.com)
2. Upload scene image
3. Prompt with motion description
4. Generate 5-10 second clips
5. Export at 4K if needed

---

### 3.4 Voiceover Generation

#### Tool: Chatterbox

**Step 1: Prepare Script**

Format script with character tags:
```
[TUNDE - stern, controlled]
Maya, we need to talk about this art thing.

[RACHEL - gentle, mediating]
Tunde, can we just... let her explain first?

[MAYA - defensive, hurt]
There's nothing to explain. You already decided.
```

**Step 2: Generate Each Line**

1. Load Chatterbox
2. Select/upload voice reference for character
3. Paste dialogue line
4. Adjust emotion slider if needed
5. Generate and preview
6. Export as WAV/MP3

**Step 3: Name Files Clearly**
```
ep01_sc02_tunde_01.mp3
ep01_sc02_rachel_01.mp3
ep01_sc02_maya_01.mp3
```

---

### 3.5 Music & Sound

**Free Music Sources:**
- Uppbeat (free with attribution)
- Pixabay Music (free)
- YouTube Audio Library (free)

**Sound Guidelines:**
- Underscore dialogue, never overpower
- Match energy to scene emotion
- Consistent theme/style across series
- 10-15 seconds is often enough for a 60-second episode

---

## Phase 4: Post-Production

### 4.1 Editing Workflow (CapCut)

**Step 1: Import Assets**
- Create project: "Fashanus_EP[XX]"
- Import all scene video clips
- Import all voiceover audio
- Import music track

**Step 2: Rough Assembly**
1. Place video clips in order on timeline
2. Align voiceover to matching scenes
3. Check timing feels natural

**Step 3: Fine Edit**
1. Trim clips to tighten pacing
2. Add transitions (use sparingly - cuts work best for drama)
3. Adjust audio levels:
   - Dialogue: 0dB (loudest)
   - Music: -12dB to -18dB (background)
   - Sound effects: -6dB

**Step 4: Captions**

CapCut auto-captions:
1. Click "Captions" > "Auto Captions"
2. Select language
3. Review and fix errors
4. Style captions:
   - Font: Bold, readable
   - Size: Large enough for mobile
   - Position: Lower third, avoid face coverage
   - Style: White with black outline

**Step 5: Opening/Ending**

First 3 seconds (HOOK):
- Text overlay: Episode title or hook question
- Example: "She found Maya's sketchbook..."

Last 5 seconds (CTA):
- "Follow for Part 2"
- Or cliffhanger freeze frame

**Step 6: Export Settings**
- Resolution: 1080x1920
- Frame rate: 30fps
- Format: MP4
- Quality: High

---

### 4.2 Quality Checklist

Before publishing, verify:

**Visual Consistency:**
- [ ] Characters look consistent across all scenes
- [ ] Lighting matches within scenes
- [ ] No weird AI artifacts visible

**Audio:**
- [ ] Dialogue is clear and audible
- [ ] Music enhances but doesn't distract
- [ ] No audio pops or clicks

**Pacing:**
- [ ] Hook in first 3 seconds
- [ ] No dead space or slow moments
- [ ] Ends with reason to watch next episode

**Technical:**
- [ ] Correct aspect ratio (9:16)
- [ ] Captions are accurate
- [ ] File size reasonable for upload

---

## Phase 5: Publishing

### 5.1 Platform Optimization

#### TikTok (Primary)
- Length: 60-90 seconds optimal
- Hashtags: #familydrama #drama #storytime #thefashanus
- Post time: 6-9 PM weekdays (UK)
- Sound: Can use trending sounds if it fits

#### Instagram Reels
- Same content, cross-post
- Hashtags: More allowed (up to 30)
- Reminder sticker for next episode

#### YouTube Shorts
- Same content, cross-post
- Title: More descriptive, SEO-focused
- Add to playlist: "The Fashanus"

---

### 5.2 Posting Schedule

| Day | Action |
|-----|--------|
| Friday 6PM | Post new episode (TikTok first) |
| Friday 7PM | Cross-post to Instagram Reels |
| Friday 8PM | Cross-post to YouTube Shorts |
| Saturday | Engage with comments |
| Sunday | Tease next episode (story/post) |

---

### 5.3 Engagement Strategy

**Caption Formula:**
```
[Hook question or statement]

[Brief context]

Episode [X] of [Arc Name]

[CTA - Follow for next part]
```

**Example:**
```
Tunde found Maya's secret sketchbook.

He wasn't supposed to see those drawings.

Episode 2 of "The Art Dream"

Part 3 drops Friday...
```

**Reply to Comments:**
- Stay in character occasionally
- Ask what viewers think will happen
- Acknowledge emotional reactions

---

## Phase 6: Continuity Management

### 6.1 Episode Log

Maintain a running log of what's happened:

```markdown
## The Fashanus - Continuity Bible

### Episode Log

**EP01: The Art Dream - Part 1 (Maya)**
- Maya enters art competition secretly
- Tunde mentions wanting her to focus on "real subjects"
- Rachel notices Maya staying up late

**EP02: The Art Dream - Part 2 (Maya)**
- Maya's friend Chloe encourages her
- Tunde finds sketchbook
- Maya lies about what it is

[Continue for each episode...]

### Character Development Tracker

**Tunde:**
- EP01: Dismissive of art
- EP04: Revealed his own abandoned dreams

**Maya:**
- EP01: Secretive, defensive
- EP03: Confrontational, hurt

### Unresolved Threads
- Tiwa (Tunde's step-sister) - mentioned but not appeared
- Tunde's boarding school past - not explored yet
- Rachel's business struggles - hinted, not shown

### Facts Established
- Maya does tennis on Saturdays
- Tayo's football team is called "The Foxes"
- Rachel works from the kitchen table
- Family car is a grey Nissan Qashqai
```

---

### 6.2 Asset Library

Keep organized folders:

```
/fashanus/
  /characters/
    /tunde/
    /rachel/
    /maya/
    /tayo/
    /tiwa/ (for future)
  /locations/
    /home/
    /school/
    /other/
  /episodes/
    /ep01/
      /images/
      /video_clips/
      /audio/
      /exports/
      outline.md
    /ep02/
      ...
  /audio/
    /music/
    /sfx/
  /templates/
    episode_outline_template.md
    scene_prompt_template.md
  CONTINUITY_BIBLE.md
  PRODUCTION_WORKFLOW.md (this file)
```

---

## Quick Reference Card

### Tools
| Stage | Tool | Cost |
|-------|------|------|
| Character Images | Gemini + LM Arena | Free |
| Scene Images | Gemini + LM Arena | Free |
| Video Generation | LTX Studio | Free (3600s/mo) |
| Video Generation (alt) | Kling AI 3.0 | Free credits |
| Voiceover | Chatterbox | Free |
| Editing | CapCut | Free |
| Music | Uppbeat/Pixabay | Free |

### Weekly Time Budget
| Task | Hours |
|------|-------|
| Writing/Planning | 2 |
| Image Generation | 2 |
| Video Generation | 2 |
| Voiceover | 1 |
| Editing | 2 |
| Publishing/Engagement | 1 |
| **Total** | **~10 hours/week** |

### Episode Specs
- Length: 60-90 seconds
- Aspect: 9:16 (vertical)
- Resolution: 1080x1920
- Audio: Clear dialogue, subtle music
- Captions: Required

---

## Next Steps

1. Generate character reference images for all 4 family members
2. Generate 3-4 home location images
3. Set up voice profiles in Chatterbox
4. Write first story arc outline
5. Produce pilot episode
6. Test with small audience before full launch

---

*Document created by Duro*
*Project: The Fashanus*
*Last updated: 2026-02-10*
