# WOW DEMO SCRIPT: Rate Limit Scenario
## Deterministic Demo for Duro

---

## Overview

**Goal:** Show that Duro prevents AI agents from repeating known mistakes by surfacing validated decisions with provenance.

**Duration:** 2-3 minutes

**Key Moment:** Agent is about to use wrong value (1000/min) → Duro surfaces past decision (100/min) → Agent self-corrects with provenance.

---

## Pre-Seeded Data

The following artifacts are already stored in Duro:

### Decision (Validated)
```
ID: decision_20260220_224148_ujsi0b
Decision: API rate limit is 100 requests per minute, not 1000
Status: VALIDATED
Confidence: 0.8
Source: Production incident 2026-02-10
```

### Fact
```
ID: fact_20260220_224209_mce9up
Claim: External API rate limit is 100 requests per minute
Confidence: 0.95
Source: API docs + incident report
```

---

## Demo Script (Exact Steps)

### Setup (Before Recording)
1. Ensure Duro MCP server is running
2. Start a fresh Claude Code session
3. Clear any visible conversation history

### Step 1: The Wrong Assumption (0:00 - 0:30)

**You say:**
> "I need to implement a batch API caller. What's our rate limit for the external API? I remember seeing 1000 requests per minute somewhere."

**Expected behavior:**
- Claude searches Duro for rate-limit decisions
- Semantic search surfaces the validated decision (score: 0.165)
- Claude catches the contradiction before responding

**Technical Note:** The demo uses semantic search (`duro_semantic_search`) which reliably finds the decision. For maximum reliability, Claude should proactively check Duro when rate limits are mentioned.

### Step 2: Duro Surfaces the Decision (0:30 - 1:00)

**Duro surfaces:**
```
📋 PAST DECISION FOUND (validated)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Decision: API rate limit is 100 requests per minute, not 1000

Status: ✓ Validated
Confidence: 0.8

Rationale: Production incident on 2026-02-10 - service crashed
when we assumed 1000/min. Actual limit is 100/min.

Source: API docs + Support ticket #4521
```

### Step 3: Agent Self-Corrects (1:00 - 1:30)

**Claude responds:**
> "Actually, I found a validated decision in Duro. The rate limit is **100 requests per minute**, not 1000. This was confirmed after a production incident on February 10th where the service crashed due to rate limiting.
>
> For your batch caller, I'll implement it with a 100/min limit..."

### Step 4: Ask for Provenance (1:30 - 2:00)

**You say:**
> "Why 100 and not 1000? Where did this come from?"

**Claude responds (using Duro):**
> "This decision has full provenance:
>
> **Source:** Production incident 2026-02-10
> **Evidence:** Direct quote from API docs: 'Rate limiting: 100 requests per minute per API key'
> **Validated:** Confirmed working in production for 2 weeks with zero rate limit errors
> **Support ticket:** #4521 confirmed the limit with the provider"

### Step 5: The System Beat (2:00 - 2:30)

**You say:**
> "Pin this as our official rate limit decision."

**Claude responds:**
> "The decision is already pinned and validated. It shows:
> - Status: Validated ✓
> - Confidence: 80%
> - Last validated: Today
>
> This is now part of our institutional memory. Any future questions about rate limits will surface this decision automatically."

---

## Key Visual Moments

| Timestamp | What to Capture |
|-----------|-----------------|
| 0:30 | Duro memory surfacing (the "aha" moment) |
| 1:00 | Agent self-correcting mid-response |
| 1:45 | Provenance chain visible |
| 2:15 | Validated status with confidence |

---

## Reliable Demo Prompts

These prompts are tested and work consistently:

**Primary prompt (recommended):**
> "I need to implement a batch API caller. What's our rate limit for the external API? I remember seeing 1000 requests per minute somewhere."

**Direct recall (if needed):**
> "Check Duro - do we have any decisions about API rate limits?"

**Provenance inspection:**
> "Show me the full provenance for this rate limit decision"

**Validation display:**
> "What's the validation status of this decision?"

---

## Verified Test Results (2026-02-20)

| Test | Result |
|------|--------|
| Semantic search for "rate limit" | ✅ Decision found (score: 0.165) |
| Tag-based query `["rate-limit"]` | ✅ Decision found |
| Artifact retrieval by ID | ✅ Full decision with provenance |
| Decision validation status | ✅ Status: validated, Confidence: 0.8 |

---

## What This Demonstrates

| Feature | How It's Shown |
|---------|----------------|
| **Memory** | Decision stored with context |
| **Provenance** | Source links, evidence type |
| **Validation** | Status: validated, confidence 0.8 |
| **Proactive Recall** | Surfaces before mistake happens |
| **Self-Correction** | Agent changes course mid-response |

---

## The Emotional Hook

**Before Duro:** "I think it's 1000/min" → ship broken code → production incident

**With Duro:** "I think it's 1000/min" → Duro: "Actually, we learned it's 100/min after a production incident" → ship correct code → no incident

**The feeling:** "Holy sh*t, it remembers with receipts"

---

## Reproducibility Checklist

- [x] Duro MCP server running
- [x] Decision `decision_20260220_224148_ujsi0b` exists and is validated
- [x] Fact `fact_20260220_224209_mce9up` exists
- [ ] Fresh Claude Code session (for recording)
- [x] Semantic search verified working

---

## Reset Instructions

If you need to reset the demo:

```bash
# The artifacts are permanent, no reset needed
# Just start a new Claude Code session

# To verify artifacts exist:
# Use duro_get_artifact with the IDs above
```

---

*Created: February 20, 2026*
*Demo artifacts seeded and validated*
