# Rep Log: 2026-02-11 (Rep 2)

## Session: One Weird Rule - Diagonal Notification

**Domain**: Design
**Method**: One Weird Rule
**Time**: 10 min
**Constraint**: "Everything aligns to an invisible diagonal"

---

## Output

Notification card where text elements step right as they descend:
- Icon + title: x:24/56, y:20/22
- Detail: x:72, y:48
- Timestamp: x:88, y:72
- Dismiss: x:220, y:84

Creates a top-left to bottom-right flow.

---

## Definition of Done Check

- [x] Constraint: "Everything aligns to an invisible diagonal"
- [x] Reference: Terminal Minimal aesthetic (from Taste Vault)
- [ ] Risk: Diagonal is subtle - doesn't commit hard enough
- [x] Critique pass: Red-Team applied

**Status**: Competent Draft (risk too subtle)

---

## Red-Team Findings

1. **Generic**: Green accent bar on left is standard notification pattern
2. **AI-smooth**: Copy is functional ("verification_complete") but not distinctive
3. **Safe**: Diagonal exists but reads as "slightly misaligned" not "intentionally flowing"

---

## What I Learned

**The constraint wasn't bold enough.** "Everything aligns to a diagonal" is a structural rule, but it needed more visual reinforcement:
- Could have added a diagonal line or gradient
- Could have rotated elements slightly
- Could have made the step-increment larger (more dramatic)

**Lesson**: One Weird Rule works best when the rule is VISIBLE, not just structural. If someone can't see the rule at a glance, it doesn't register as intentional.

---

## New Heuristic

> "Invisible constraints read as mistakes. Make the weird visible."

If your deliberate rule isn't obvious, viewers assume error not intention. The rule should be detectable within 2 seconds of looking.

---

## Next Iteration Ideas

- Add a subtle diagonal gradient in the background
- Rotate the entire card 2-3 degrees
- Make the x-offset per line much larger (e.g., 32px steps instead of 16px)
