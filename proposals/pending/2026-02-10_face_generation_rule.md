# Proposal: Add Face Generation Rule

**Date:** 2026-02-10
**Type:** new_rule
**Status:** pending
**Target:** .agent/rules/failures/face_distortion.json

---

## What I Learned

During Episode 1A and 1B production for The Fashanus, I attempted to generate photorealistic character images using the Pollinations.ai API (Flux model). While non-face elements rendered acceptably, human faces consistently showed:

- Misaligned eyes
- Warped facial features
- Uncanny valley effect
- Inconsistent proportions

The user stopped image generation partway through Episode 1B due to unacceptable face quality.

## Proposed Change

Add a structured rule to the rules library that:

1. **Triggers** when generating any image containing human faces
2. **Recommends** using web-based tools (DALL-E, Gemini, Microsoft Designer) instead of free APIs
3. **Allows** automation only for non-face images (objects, backgrounds, abstract art)
4. **Suggests** alternative art styles (illustration, cartoon) if automation required

## Evidence

| Attempt | Image | Result | Notes |
|---------|-------|--------|-------|
| 1 | tunde.png | Acceptable | Portrait, some minor issues |
| 2 | rachel.png | Acceptable | Portrait, some minor issues |
| 3 | scene1_corridor.png | Failed | Face distorted |
| 4 | scene2_dinner.png | Failed | Multiple faces distorted |
| 5+ | (stopped) | N/A | User intervention |

## Rule Content

```json
{
  "id": "rule_001",
  "trigger": "generating photorealistic human faces",
  "failure_mode": "faces come out distorted with free APIs",
  "fix": "use web-based tools for faces; automate only non-face images",
  "confidence": 0.95
}
```

## Risk Assessment

**Low risk.** This rule constrains behavior rather than expanding it. It prevents me from repeatedly failing at the same task.

## Recommendation

Approve this rule so I stop attempting to automate face generation with tools that can't handle it reliably.

---

**Approved by:** _______________
**Date approved:** _______________
**Notes:** _______________
