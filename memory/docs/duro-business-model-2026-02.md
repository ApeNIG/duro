# DURO BUSINESS MODEL
## Personal Tool + Developer SDK → Sell to Companies
### February 2026 (v2 - Updated with GTM feedback)

---

## The Model

```
Developer loves Duro personally
        ↓
Brings it to work
        ↓
Company pays for trust/compliance/control
```

**Bottoms-up B2B.** Like Slack, Notion, Figma, GitHub Copilot.

---

## The One-Sentence Pitch

> **"Duro is a memory layer for AI agents: it stores decisions + facts with provenance, so agents stop repeating mistakes and you can audit what they 'know'."**

That's it. Everything else is packaging.

---

## Product Definition

**Duro** = Personal AI memory system that developers install locally

**Duro Pro** = Power user trust + workflow features:
- Inspect, diff, rollback memory
- Provenance tracking ("where did this come from?")
- Encrypted backup (cloud optional)

**Duro for Teams** = Control + audit (what managers actually buy):
- Namespace per repo/team
- Access control (reader/writer/admin)
- Audit logs (who changed what, when, why)
- GitHub integration
- Review flows (propose → approve → promoted)

---

## Key Insight: Trust Converts

**Developers buy features. Managers buy trust.**

When you say "shared memory," a manager hears: *"Cool, so the AI can leak secrets faster?"*

Team plan needs to scream:
- **Access control** (who can see/write which namespace)
- **Review flows** (propose → approve → promoted)
- **Audit log** (who changed what, when, why)
- **Retention rules** (delete after X days, legal hold)

Shared memory is the *feature*. Control + audit is the *purchase justification*.

---

## Buyer Journey

| Stage | Who | What They Do |
|-------|-----|--------------|
| 1. Discover | Individual dev | Finds Duro on GitHub/Twitter/HN |
| 2. Try | Individual dev | Installs free, uses with Claude Code |
| 3. Wow | Individual dev | Sees the "agent remembers past mistakes" demo |
| 4. Love | Individual dev | Can't live without it, uses daily |
| 5. Advocate | Individual dev | "We should use this at work" |
| 6. Buy | Engineering manager | Pays for **trust + control**, not features |
| 7. Expand | Company | More teams adopt |

---

## Pricing (Updated)

| Tier | Price | What You Get | Why They Pay |
|------|-------|--------------|--------------|
| **Free** | $0 | Full core, local only, single user | Try it, love it |
| **Pro** | $19/mo | Trust features: inspect, diff, rollback, provenance, encrypted backup, advanced search | "I need to trust + understand what my agent knows" |
| **Team** | $39/user/mo | Control features: namespaces, ACL, audit logs, GitHub integration, admin dashboard | "We need control + audit trail" |
| **Enterprise** | Custom | On-prem/VPC, retention policies, DLP hooks, SCIM, SLA | "We need compliance + governance" |

**Why $39 for Team (not $29):**
- If you have audit + ACL + GitHub integration, you're delivering real value
- $29 undersells; $39 is fair for what you get
- Still under expense report threshold

**Cloud sync positioning:**
- Still in Pro, but it's the *seatbelt*, not the *engine*
- End-to-end encrypted backup
- "Bring your own S3" option (devs love this)

---

## What Needs to Be Built (Prioritized)

### Priority #1: Reviewable Memory + Provenance (Pro/Team)

The conversion driver. This is where trust comes from.

| Feature | Purpose | Effort |
|---------|---------|--------|
| "Proposed" vs "Pinned" memory | Review flow for memory | 1-2 weeks |
| Confidence + source linking | "Came from PR #214", "from incident postmortem" | 2 weeks |
| Diff + rollback | See changes, undo mistakes | 1-2 weeks |
| "Why is this in memory?" inspector | Provenance visibility | 1 week |

### Priority #2: Team Namespaces + Permissions (Team)

Minimum viable "shared memory with control."

| Feature | Purpose | Effort |
|---------|---------|--------|
| Namespace per repo/team | Isolation | 2 weeks |
| Roles: reader/writer/admin | Access control | 1-2 weeks |
| Basic audit log | Compliance trail | 1-2 weeks |
| Admin dashboard | Team management | 2 weeks |

### Priority #3: Integrations That Make It Sticky (Pro/Team)

The "can't live without it" loop.

| Feature | Purpose | Effort |
|---------|---------|--------|
| GitHub integration | Auto-suggest memory updates on PR merge | 2-3 weeks |
| Attach decisions to issues | Context linking | 1 week |
| Incident → lessons learned | Auto-generate memory proposals | 2 weeks |

### Lower Priority: Cloud Sync

| Feature | Purpose | Effort |
|---------|---------|--------|
| E2E encrypted backup | Peace of mind | 2-3 weeks |
| "Bring your own S3" | Developer control | 1-2 weeks |
| Cross-machine sync | Convenience | Included |

---

## The "Moment of Wow"

**You need one demo that makes devs go: "…holy hell."**

### The Wow Flow:

```
1. Agent makes a mistake
        ↓
2. Duro shows: "This happened before. Here's the decision
   we made last time and why."
        ↓
3. Agent fixes itself and pins the new decision with source link
        ↓
4. Later: "Why did we do it this way?"
   → Duro answers with full provenance
```

**That's the emotional hook.** Without this demo, you're just another devtool.

---

## The Real Moat (Reframed)

The memory model (facts/decisions/episodes) is **copyable**. Mem0 could ship this in a quarter.

**What's NOT copyable:**

| Moat | Why It's Defensible |
|------|---------------------|
| **Workflow integration** | How Duro plugs into daily dev life (PRs, CI, incident retros) |
| **Governance habits** | Teams build processes around propose/approve/audit |
| **Integration stickiness** | GitHub hooks, CI pipelines, tooling dependencies |
| **Accumulated knowledge** | Once your org's memory is in Duro, switching is painful |

**The defensible part isn't the data model. It's the workflow + governance + integration habits.**

---

## 6-Month Plan (Updated)

### Month 1-2: Lovable + Trustworthy

- Install polish
- Documentation
- **Memory inspector (provenance)** ← NEW PRIORITY
- **"Pinned vs Proposed" workflow** ← NEW PRIORITY
- Ship to GitHub, post on HN/Twitter
- **Build the "moment of wow" demo**
- **Goal:** 500 installs, 50 active users

### Month 3: Pro Launch

- Trust features (inspect, diff, rollback, provenance)
- Encrypted backup (cloud optional)
- Stripe billing
- Landing page
- **Goal:** 20 paying Pro users

### Month 4-5: Team Launch

- Namespaces + permissions
- Audit log
- **GitHub integration v1** ← Key stickiness feature
- Admin dashboard
- **Goal:** 5 paying teams

### Month 6: Enterprise Conversations

- Now you can say "audit + retention + control," not "shared memory vibes"
- Talk to larger companies using Duro
- Scope enterprise features based on real requests
- **Goal:** 2-3 enterprise pilots

---

## Revenue Projection (Updated)

| Month | Pro Users | Teams (avg 5 seats) | MRR |
|-------|-----------|---------------------|-----|
| 3 | 20 | 0 | $380 |
| 4 | 40 | 2 | $1,150 |
| 5 | 60 | 5 | $2,115 |
| 6 | 80 | 10 | $3,470 |
| 12 | 200 | 50 | $13,550 |

**Year 1 realistic:** ~$100-150K ARR (higher with $39 Team)

Not venture scale. But real business, bootstrappable, proves demand.

---

## Target Customers

### First Paying Customers (Specific Personas):

| Persona | Why They'd Pay | Where to Find Them |
|---------|----------------|-------------------|
| AI startup founder | Building agents, needs memory + audit | Twitter/X, YC community, Indie Hackers |
| Senior dev at AI company | Uses Claude Code daily, wants provenance | r/ClaudeAI, Discord servers |
| DevTools team lead | Team building AI features, needs control + audit | LinkedIn, tech meetups |
| Solo consultant | Builds AI solutions for clients, needs to show work | Freelance communities |

**First 10 customers = people you know or can reach directly.**

---

## The Pitches (Updated)

**One-liner:**
> "Duro is a memory layer for AI agents: it stores decisions + facts with provenance, so agents stop repeating mistakes and you can audit what they 'know'."

**To developers:**
> "Your AI forgets everything. Duro fixes that—and shows you exactly where every decision came from."

**To teams:**
> "Your team's AI agents need shared memory with control. Duro gives you namespaces, audit logs, and review flows—so you can trust what agents 'know'."

**To companies:**
> "AI agents without memory repeat mistakes and can't be audited. Duro adds institutional memory with full provenance, access control, and compliance trails."

---

## Current State vs Required State (Updated)

| Asset | Today | For Pro | For Team |
|-------|-------|---------|----------|
| Memory system | Yes | Yes | Yes |
| Decision validation | Yes | Yes | Yes |
| Episode tracking | Yes | Yes | Yes |
| MCP server | Yes | Yes | Yes |
| **Provenance tracking** | Partial | Required | Required |
| **Memory inspector** | No | Required | Required |
| **Propose/Pin workflow** | No | Required | Required |
| **Diff/rollback** | No | Required | Required |
| Encrypted backup | No | Required | Required |
| Namespaces | No | No | Required |
| ACL (roles) | No | No | Required |
| Audit log | No | No | Required |
| GitHub integration | No | No | Required |
| Admin dashboard | No | No | Required |
| Billing | No | Required | Required |

---

## Key Decisions Made

1. **Model:** Bottoms-up B2B (dev → team → company)
2. **Pricing:** Free / $19 Pro / $39 Team / Custom Enterprise
3. **First focus:** Trust features (provenance, inspect, review) before cloud sync
4. **Conversion driver:** "Trust converts" — provenance + audit + control
5. **Stickiness:** GitHub integration + workflow habits
6. **Target:** AI developers using Claude Code and similar tools
7. **GTM:** GitHub + content + community + "moment of wow" demo

---

## Next Actions (Updated Priority)

1. Build the "moment of wow" demo
2. Add memory inspector (provenance visibility)
3. Implement "proposed vs pinned" workflow
4. Polish free Duro for public release
5. Create landing page + docs site
6. Ship to GitHub with proper README
7. Post on HN / Twitter / relevant communities

---

## Lessons Learned (from GTM feedback)

1. **Cloud sync is a trap** — easy to explain, but not what companies pay for. It's a seatbelt, not the engine.

2. **"Shared memory" → "Control + Audit"** — Managers don't buy features, they buy trust. Reframe accordingly.

3. **The moat is workflow, not data model** — Facts/decisions/episodes are copyable. Integration habits are not.

4. **Trust converts** — Provenance, audit trails, reviewable memory. These are trust signals, not features.

5. **You need a "moment of wow"** — One demo that makes devs go "holy hell." Without it, you're just another devtool.

---

## Related Documents

- Competitive Analysis: `~/.agent/memory/docs/duro-competitive-analysis-2026-02.md`
- Builder's Compass Synthesis: `~/.agent/memory/docs/duro-builders-compass-synthesis.md`
- This document: `~/.agent/memory/docs/duro-business-model-2026-02.md`

---

*Last updated: February 20, 2026 (v2 - GTM feedback incorporated)*
