# Rep Log: 2026-02-11 (Rep 4)

## Session: Elegance Compression - User Profile Card

**Domain**: Design
**Method**: Elegance Compression
**Time**: 15 min

---

## Compression Sequence

### V0: Full (bloated)
- Avatar with initials (64px)
- Name (16px bold)
- Role (13px gray)
- Status dot + "Online" text
- Card container with 20px padding
- **Size: 280x140**

### V1: First pass (-30%)
- Avatar without initials (48px)
- Name (15px)
- Role kept
- Status dot only (no text)
- Card with 16px padding
- **Size: 220x80**
- **Lost**: Initials, status text
- **Still works**: Yes

### V2: Second pass (-50%)
- Smaller avatar (32px)
- Name only (14px)
- No role
- Status dot (6px)
- Card with 12px padding
- **Size: 160x56**
- **Lost**: Role
- **Still works**: Yes

### V3: Third pass (-70%)
- Small avatar (28px)
- Name (13px)
- Status dot (6px)
- NO card/container
- **Size: 140x40**
- **Lost**: Container
- **Still works**: Yes - this is the elegance point

### V4: Breaking point (-80%)
- Tiny avatar (24px)
- Name only
- NO status dot
- **Size: 120x32**
- **Lost**: Status functionality
- **BREAKS**: Lost actual information, not just decoration

---

## Definition of Done Check

- [x] Constraint: Remove 30% repeatedly until clarity breaks
- [x] Reference: Standard profile card patterns
- [x] Risk: Removing container entirely (V3)
- [x] Critique pass: Identified exact breaking point (V4)

**Status**: Final

---

## What I Learned

### Load-bearing elements identified:
1. **Avatar** - Identity anchor (cannot remove)
2. **Name** - Identity text (cannot remove)
3. **Status dot** - Functional information (removing loses meaning)

### Fluff identified:
1. Initials in avatar - color is enough
2. Status text "Online" - dot communicates same info
3. Role - context-dependent, not always needed
4. Card container - elements can float
5. Generous padding - tighter works

### The snap point
V3 → V4 is where it breaks. Not because V4 looks bad, but because it **loses information**. The status dot isn't decoration - it's data.

---

## New Heuristic

> "Elegance isn't minimum elements - it's minimum elements that preserve meaning."

V4 has fewer elements but says less. V3 is the optimal point: maximum reduction with zero information loss.

---

## Micro-pattern extracted

**The Status Dot Pattern**: A 6-8px colored circle can replace "Online/Offline/Away" text. The color carries the meaning. Saves space without losing information.
