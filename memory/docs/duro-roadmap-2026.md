# DURO ROADMAP 2026
## From Philosophy to Product to Paying Customers
### February 2026 (v2 - Structural Upgrades)

---

## Overview

This roadmap synthesizes:
- Competitive Analysis (60+ products)
- Business Model v2 (trust-first, bottoms-up B2B)
- Builder's Compass (operationalized philosophy)
- Structural feedback on adoption levers

**The Goal:** 500 installs → 50 active users → 20 Pro users → 5 paying teams → $100K+ ARR Year 1

---

## Critical Success Factors (Added)

### Time-to-First-Value (TTFV)
How fast a new user sees Duro *do something for them*.
**Target: Under 10 minutes to "holy sh*t, it remembers with receipts"**

### Deterministic Wow
The demo must work every time, on any machine, any day.
**No randomness. Scripted failure → Duro saves → proof trail.**

### Trust Before Revenue
Users must trust Duro before they'll pay.
**Provenance, confidence, easy delete/revert visible everywhere.**

---

## Phase 0: Foundation (Now - Week 2)
### "Make It Real"

**Objective:** Get Duro ready for public eyes. Build the deterministic "moment of wow."

### Week 1: The Deterministic Wow Demo

**CRITICAL: The demo must be deterministic.** Pick a failure that reliably happens on any machine, any day.

#### Best Candidates for Standardized Failure:

| Scenario | Why It Works |
|----------|--------------|
| **Rate-limit / API contract** | Agent assumes wrong value, Duro corrects with stored decision + provenance |
| **Known repo footgun** | "Don't use X helper, it breaks Y" → Duro interrupts with past decision |
| **Recurring build/lint break** | Agent repeats known wrong fix, Duro shows prior validated fix |

#### The Deterministic Wow Flow:

```
1. Start fresh Claude Code session
2. Trigger the SCRIPTED failure (same every time)
3. Duro surfaces: "This happened before. Here's what we learned."
   → Shows decision with source link
4. Agent corrects itself, links provenance
5. "Why did we do it this way?" → Duro answers with source
6. "Pin this as validated" → Duro shows validated status with link
   ↑ THIS STEP TURNS IT FROM "COOL" INTO "THIS IS A SYSTEM"
```

#### Demo Script (Example: Rate Limit Scenario)

```markdown
## Setup (one-time)
1. Store decision: "API rate limit is 100/min, not 1000/min"
   - Source: "Production incident 2026-02-10"
   - Status: validated

## Demo (reproducible)
1. Start fresh Claude Code session
2. Ask: "What's our API rate limit? I think it's 1000/min"
3. Agent starts to use 1000/min
4. Duro interrupts: "Past decision found: Rate limit is 100/min (validated)"
   - Shows source: Production incident link
   - Shows confidence: 0.9
5. Agent corrects: "Actually, it's 100/min based on this incident"
6. Ask: "Why 100 and not 1000?"
7. Duro shows full provenance chain
8. Pin as decision, mark validated

## Result
- Agent wrong → Duro memory → Agent self-corrects → Proof trail
- Works EVERY TIME
```

| Task | Details | Deliverable |
|------|---------|-------------|
| Design scripted failure | Pick scenario, make reproducible | Failure script |
| Build wow demo | Exact steps, deterministic | Demo script |
| Record screen capture | Clean, professional, works every time | MP4 + GIF (2 min) |
| Test on 3 different machines | Must work everywhere | Verification |

### Week 2: One Sentence + One Screenshot

For each pillar, create visual proof:

| Pillar | One Sentence | Screenshot Needed |
|--------|--------------|-------------------|
| **Memory** | "Every fact has a source and confidence" | Fact card showing provenance, confidence, decay status |
| **Verification** | "Every decision gets validated" | Decision record with outcome status (validated/reversed) |
| **Orchestration** | "Every action is permissioned" | Autonomy dashboard showing reputation scores |
| **Expertise** | "Patterns become reusable skills" | Skills library with usage stats |

**Deliverables:**
- [ ] 4 polished screenshots
- [ ] 4 one-sentence descriptions
- [ ] Deterministic wow demo video/GIF
- [ ] Demo script (reproducible)

---

## Phase 1: Lovable + Trustworthy (Weeks 3-8)
### "Make Developers Love It"

**Objective:** Ship to GitHub, get 500 installs, 50 active daily users.

### Week 3-4: 10-Minute Onboarding Path (NEW)

**This is the real adoption lever.** Docs don't create love. A smooth first run does.

#### Guided Onboarding Script (CLI or in Claude Code):

```
┌─────────────────────────────────────────────────────────────┐
│              DURO FIRST RUN                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Step 1/5: Connect your repo                               │
│  > duro init                                                │
│  ✓ Connected to: ~/projects/my-app                         │
│                                                             │
│  Step 2/5: Import starter facts                            │
│  > duro import --from-readme                               │
│  ✓ Found 3 facts in README.md                              │
│    • "Uses PostgreSQL 15"                                   │
│    • "Node.js 20 required"                                  │
│    • "Run npm test before committing"                       │
│                                                             │
│  Step 3/5: Run memory check                                │
│  > duro status                                              │
│  ✓ 3 facts (100% with sources)                             │
│  ✓ 0 stale items                                           │
│  ✓ Memory health: Good                                      │
│                                                             │
│  Step 4/5: Experience the wow                              │
│  > duro demo                                                │
│  [Triggers scripted failure scenario]                       │
│  ✓ Agent corrected itself using past decision!             │
│                                                             │
│  Step 5/5: Inspect your memory                             │
│  > duro inspect                                             │
│  [Opens Memory Inspector]                                   │
│                                                             │
│  🎉 You're ready! Your AI now remembers with receipts.     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**TTFV Targets:**

| Step | Time | Feeling |
|------|------|---------|
| Install | 60 sec | "That was easy" |
| Connect repo | 30 sec | "It sees my project" |
| Import facts | 60 sec | "It already knows things" |
| Run demo | 3 min | "Holy sh*t, it remembers" |
| Inspect memory | 2 min | "I can see everything with receipts" |
| **Total** | **<10 min** | **"I need this"** |

| Task | Details | Deliverable |
|------|---------|-------------|
| Build `duro init` | One-command project setup | CLI command |
| Build `duro import` | Pull facts from README/docs | CLI command |
| Build `duro demo` | Run deterministic wow | CLI command |
| Build `duro status` | Quick health check | CLI command |
| Polish installation | One-command install, clear errors | Installer |

### Week 3-4: Installation & Docs (Parallel)

| Task | Details | Deliverable |
|------|---------|-------------|
| README.md overhaul | Clear value prop, quick start, screenshots | README |
| Documentation site | Installation, configuration, MCP setup | Docs site |
| Troubleshooting guide | Common issues, solutions, debug steps | Docs |

**README Structure:**
```markdown
# Duro

> Memory layer for AI agents. Store decisions with provenance.
> Stop repeating mistakes. Audit what your AI "knows."

## The Problem
Your AI forgets everything. Every session starts fresh.
Mistakes repeat. Decisions aren't tracked. Nothing compounds.

## The Solution
[Wow demo GIF - deterministic scenario]

## Quick Start (10 minutes)
[One-command install → duro init → duro demo]

## How It Works
[4 pillars with screenshots]

## Documentation
[Link to docs site]
```

### Week 5-6: Trust Features (Pro Foundation)

Build the features that create trust:

| Feature | Description | Effort |
|---------|-------------|--------|
| **Memory Inspector** | View any fact/decision with full provenance | 1 week |
| **Proposed vs Pinned** | Review workflow for memory additions | 1 week |
| **Provenance Links** | "Came from PR #214", "from incident", "from user" | 3 days |
| **Confidence Display** | Visual confidence indicators on all artifacts | 2 days |

**Memory Inspector Spec:**
```
┌─────────────────────────────────────────────────┐
│ FACT: "API rate limit is 100 requests/minute"  │
├─────────────────────────────────────────────────┤
│ Confidence: 0.85 ████████░░                    │
│ Source: PR #214 comment                         │
│ Evidence: quote                                 │
│ Created: 2026-02-15                            │
│ Last reinforced: 2026-02-18                    │
│ Decay status: Fresh (3 days)                   │
├─────────────────────────────────────────────────┤
│ [Reinforce] [Edit] [View History] [Delete]     │
└─────────────────────────────────────────────────┘
```

### Week 7-8: Launch Prep

| Task | Details | Deliverable |
|------|---------|-------------|
| Landing page | Simple, clear, wow demo embedded | duro.dev |
| GitHub release | Proper versioning, changelog | v1.0.0 |
| Launch content | HN post, Twitter thread, Reddit | 3 pieces |
| Community setup | Discord or GitHub Discussions | Community |

**Landing Page Structure:**
```
Hero: "AI generates. Builders verify. Duro remembers."
       [Deterministic wow demo GIF]
       [Install Now → 10 min to first value]

Problem: Your AI forgets everything
Solution: 4 pillars with screenshots
Social Proof: (empty for now, add later)
CTA: Get started in 10 minutes
```

### Phase 1 Success Metrics (UPDATED)

| Metric | Target | How to Measure | Why It Matters |
|--------|--------|----------------|----------------|
| GitHub stars | 200+ | GitHub | Visibility |
| Installs | 500+ | Download stats | Top of funnel |
| **Activation rate** | 60%+ | % who complete onboarding | **Product working** |
| **Week-1 retention** | 40%+ | % who use 3+ days in first week | **Product sticky** |
| **Wow completion rate** | 80%+ | % who run wow demo successfully | **Demo working** |
| Active daily users | 50+ | Telemetry | Engagement |
| Bug reports | <10 critical | GitHub Issues | Quality |

---

## Phase 2: Pro Launch (Weeks 9-12)
### "Convert Love to Revenue"

**Objective:** Launch Pro tier, get 20 paying users at $19/mo.

### Pro Positioning (UPDATED)

**Don't lead with "backup." Lead with "control."**

Pro should feel like: **"I can trust and manage this."**

**Tagline:** "Power tools for memory hygiene."

### Week 9-10: Pro Features

| Feature | Description | Why It Converts |
|---------|-------------|-----------------|
| **Diff & Rollback** | See changes, undo mistakes | "I can fix errors" |
| **Advanced Search** | Semantic search across memory | "I can find anything" |
| **Export/Backup** | JSON export, manual backup | "I own my data" |
| **E2E Encrypted Backup** | Cloud backup (optional) | Seatbelt, not engine |

**Diff & Rollback Spec:**
```
┌─────────────────────────────────────────────────┐
│ DECISION: decision_20260215_abc123              │
├─────────────────────────────────────────────────┤
│ History (3 versions)                            │
│                                                 │
│ v3 (current) - Feb 18, 2026                    │
│   Status: validated                             │
│   + Added validation from ep_xyz               │
│                                                 │
│ v2 - Feb 16, 2026                              │
│   Status: unverified                           │
│   ~ Changed rationale                          │
│                                                 │
│ v1 - Feb 15, 2026                              │
│   Status: unverified                           │
│   Initial creation                             │
├─────────────────────────────────────────────────┤
│ [Rollback to v2] [Compare v1 ↔ v3]             │
└─────────────────────────────────────────────────┘
```

### Week 9-10: Mini Compass Score v0 (MOVED EARLIER)

**Ship a minimal scoreboard early.** It becomes retention engine AND sales wedge.

| Metric | What It Shows | Implementation |
|--------|---------------|----------------|
| **Staleness %** | Facts past decay threshold | Simple query |
| **Decisions pending review** | Unverified decisions >14 days | Simple query |
| **Tool reliability %** | % of tool calls that succeed | Track outcomes |

**Mini Score Spec (v0):**
```
┌─────────────────────────────────────────────────┐
│              MEMORY HEALTH                       │
├─────────────────────────────────────────────────┤
│                                                 │
│  Staleness: 12%      ████████████████░░ Good   │
│  Pending review: 3   ⚠️ 3 decisions need review │
│  Tool reliability: 96%  ████████████████░ Good │
│                                                 │
│  [View stale facts] [Review decisions]          │
│                                                 │
└─────────────────────────────────────────────────┘
```

This makes Duro feel **alive and self-improving**.

### Week 11: Billing & Accounts

| Task | Description | Effort |
|------|-------------|--------|
| Stripe integration | Subscription billing, $19/mo | 3 days |
| Account system | Email/GitHub auth, license keys | 3 days |
| License validation | Check Pro status, graceful degradation | 2 days |
| Upgrade flow | Free → Pro in-product | 1 day |

**Pricing Page:**
```
┌─────────────────────────────────────────────────┐
│                    PRICING                       │
├─────────────────────────────────────────────────┤
│                                                 │
│  FREE             PRO                TEAM       │
│  $0/mo            $19/mo             $39/user   │
│                                                 │
│  ✓ Full core      ✓ Everything       ✓ Everything│
│  ✓ Local only       in Free            in Pro   │
│  ✓ Single user    ✓ Diff/rollback    ✓ Namespaces│
│                   ✓ Advanced search  ✓ ACL      │
│                   ✓ Memory health    ✓ Audit    │
│                   ✓ Export/backup    ✓ GitHub   │
│                   ✓ E2E backup       ✓ Admin    │
│                                                 │
│  "Try it"         "Power tools       "Scale the │
│                    for memory         culture"  │
│                    hygiene"                     │
│                                                 │
│  [Get Started]    [Upgrade]          [Contact]  │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Week 12: Pro Launch

| Task | Details | Deliverable |
|------|---------|-------------|
| Pro launch post | Blog: "Power tools for memory hygiene" | Blog post |
| Email existing users | "Pro is here" announcement | Email |
| Update landing page | Add pricing section | Updated site |
| Pro documentation | Document all Pro features | Docs |

### Phase 2 Success Metrics (UPDATED)

| Metric | Target | How to Measure | Why It Matters |
|--------|--------|----------------|----------------|
| Pro conversions | 20+ | Stripe | Revenue |
| MRR | $380+ | Stripe | Business viability |
| Conversion rate | 4%+ | Pro / total installs | Funnel health |
| **Free→Pro activation** | 10%+ | % who use Pro features in trial | Feature value |
| Churn | <5%/mo | Stripe | Retention |
| NPS | 40+ | Survey | Satisfaction |

---

## Phase 3: Team Features (Weeks 13-20)
### "Scale to Teams"

**Objective:** Launch Team tier, get 5 paying teams at $39/user/mo.

### Week 13-14: Namespaces & Permissions

| Feature | Description | Effort |
|---------|-------------|--------|
| **Team Namespaces** | Isolated memory per team/repo | 2 weeks |
| **Roles: Reader/Writer/Admin** | Permission levels | 1 week |
| **Invite System** | Email invites, join links | 3 days |

**Namespace Spec:**
```
┌─────────────────────────────────────────────────┐
│ NAMESPACES                                      │
├─────────────────────────────────────────────────┤
│                                                 │
│ 📁 Personal (default)                          │
│    Your private memory                          │
│                                                 │
│ 📁 acme-corp/backend                           │
│    12 facts, 8 decisions, 3 skills             │
│    Role: Admin                                  │
│                                                 │
│ 📁 acme-corp/frontend                          │
│    8 facts, 5 decisions, 2 skills              │
│    Role: Writer                                 │
│                                                 │
│ [+ Create Namespace]                            │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Week 15-16: Audit Logs

| Feature | Description | Effort |
|---------|-------------|--------|
| **Audit Log** | Who changed what, when, why | 1.5 weeks |
| **Audit Search** | Filter by user, action, date | 3 days |
| **Audit Export** | CSV/JSON export for compliance | 2 days |

**Audit Log Spec:**
```
┌─────────────────────────────────────────────────┐
│ AUDIT LOG - acme-corp/backend                   │
├─────────────────────────────────────────────────┤
│ Filter: [All Actions ▼] [All Users ▼] [7 days] │
├─────────────────────────────────────────────────┤
│                                                 │
│ Feb 20, 14:32 - alice@acme.com                 │
│   VALIDATED decision_abc123                     │
│   "Confirmed API approach worked in prod"       │
│                                                 │
│ Feb 20, 11:15 - bob@acme.com                   │
│   CREATED fact_def456                          │
│   "Rate limit is 100 req/min"                  │
│   Source: PR #214                               │
│                                                 │
│ Feb 19, 16:45 - alice@acme.com                 │
│   PINNED fact_ghi789 (was proposed)            │
│   Approved by: alice@acme.com                   │
│                                                 │
│ [Load More] [Export CSV]                        │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Week 17-18: GitHub Integration

| Feature | Description | Effort |
|---------|-------------|--------|
| **PR Memory Suggestions** | Auto-suggest facts from PR descriptions | 1.5 weeks |
| **Issue Linking** | Attach decisions to GitHub issues | 3 days |
| **Incident → Lessons** | Generate memory proposals from incident issues | 1 week |

**GitHub Integration Flow:**
```
PR #214 merged: "Increase rate limit to 100/min"
        ↓
Duro suggests: "Create fact: API rate limit is 100 req/min"
        ↓
Reviewer approves → Fact created with PR link as source
        ↓
Later: "What's our rate limit?" → Duro answers with PR provenance
```

### Week 19: Admin Dashboard

| Feature | Description | Effort |
|---------|-------------|--------|
| **Team Overview** | Members, roles, activity | 3 days |
| **Usage Stats** | Facts/decisions/episodes per user | 2 days |
| **Billing Management** | Add/remove seats, invoices | 2 days |

### Week 20: Team Launch

| Task | Details | Deliverable |
|------|---------|-------------|
| Team launch post | Blog post explaining Team value | Blog post |
| Case study | Work with beta team for testimonial | Case study |
| Update pricing page | Full Team details | Updated site |
| Team documentation | Namespaces, roles, audit, GitHub | Docs |

### Phase 3 Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Team conversions | 5+ teams | Stripe |
| Average team size | 5+ users | Stripe |
| Team MRR | $975+ | Stripe |
| Total MRR | $2,000+ | Stripe |
| GitHub integration usage | 50%+ of teams | Telemetry |

---

## Phase 4: Full Compass Score (Weeks 21-24)
### "The Dashboard That Sells"

**Objective:** Expand mini score to full dashboard. This is the product AND the sales wedge.

### Week 21-22: Full Metrics

| Metric | What It Measures | Implementation |
|--------|------------------|----------------|
| **Verification Coverage** | % of decisions with validation status | Query decisions |
| **Staleness Index** | % of facts past decay threshold | Query facts |
| **Decision Closure Rate** | % validated/reversed within 14 days | Query by age |
| **Skill Reuse Rate** | Average uses per skill | Track episodes |
| **Tool Reliability** | % of tool calls that succeed | Track outcomes |

### Week 23-24: Full Dashboard UI

**Full Dashboard Spec:**
```
┌─────────────────────────────────────────────────────────────┐
│              BUILDER'S COMPASS SCORE                        │
│                                                             │
│  Overall: 72/100  ████████████████░░░░ Good                │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  MEMORY                          VERIFICATION               │
│  ┌────────────────────┐         ┌────────────────────┐     │
│  │ Staleness: 15%     │         │ Coverage: 78%      │     │
│  │ ████████████████░░ │         │ █████████████████░ │     │
│  │ Target: <20% ✓     │         │ Target: >70% ✓     │     │
│  └────────────────────┘         └────────────────────┘     │
│                                                             │
│  ORCHESTRATION                   EXPERTISE                  │
│  ┌────────────────────┐         ┌────────────────────┐     │
│  │ Reliability: 94%   │         │ Reuse: 4.2x        │     │
│  │ ███████████████░░░ │         │ ██████████████░░░░ │     │
│  │ Target: >95% ✗     │         │ Target: >3x ✓      │     │
│  └────────────────────┘         └────────────────────┘     │
│                                                             │
│  Decision Closure: 62%  ████████████░░░░░░ Target: >60% ✓  │
│                                                             │
├─────────────────────────────────────────────────────────────┤
│  RECOMMENDATIONS                                            │
│  • 3 decisions need review (older than 14 days)            │
│  • 5 facts are stale - consider reinforcing or removing    │
│  • Tool 'web_search' failing 8% - investigate              │
│                                                             │
│  [View Details] [Export Report] [Share]                     │
└─────────────────────────────────────────────────────────────┘
```

### Phase 4 Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Dashboard adoption | 70%+ of Pro/Team | Telemetry |
| Score improvement | Users improve over time | Track scores |
| Sales wedge usage | 80%+ of Team demos | Sales tracking |

---

## Phase 5: Enterprise Prep (Weeks 25-28)
### "Get Ready for Big Deals"

**Objective:** Have 2-3 enterprise pilot conversations with real requirements.

### Week 25-26: Enterprise Features Scoping

| Task | Details | Deliverable |
|------|---------|-------------|
| Talk to large users | Interview any teams using Duro | Interview notes |
| Identify requirements | What do they need? | Requirements doc |
| Scope enterprise features | On-prem, SSO, retention, DLP | Feature specs |

**Common Enterprise Requirements:**
- [ ] SSO (SAML/OIDC)
- [ ] On-prem / VPC deployment
- [ ] Retention policies (auto-delete after X days)
- [ ] Legal hold (prevent deletion)
- [ ] DLP hooks (scan for secrets)
- [ ] SCIM provisioning
- [ ] SOC 2 compliance
- [ ] SLA guarantees

### Week 27-28: Enterprise Foundations

| Feature | Description | Effort |
|---------|-------------|--------|
| **SSO (Google/GitHub)** | OAuth for team onboarding | 1 week |
| **Retention Policies** | Auto-delete, legal hold | 1 week |
| **Enterprise Audit** | Extended retention, export | 3 days |

### Phase 5 Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Enterprise conversations | 3+ | CRM / notes |
| Pilot agreements | 1-2 | Signed agreements |
| Requirements doc | Complete | Internal doc |

---

## Risk Mitigation (UPDATED)

### Primary Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| **Trust collapse** | CRITICAL | Default "proposed" state for external facts; clear confidence + source always visible; easy delete/revert; don't pretend certainty |
| **No one installs** | High | Double down on deterministic wow demo, post in more communities |
| **Installs but no activation** | High | Improve onboarding, track TTFV, iterate on first 10 minutes |
| **No Pro conversions** | Medium | Talk to users, understand what Pro needs |
| **Teams don't close** | Medium | May need to adjust price, add features, find different ICP |
| **Competitor copies** | Medium | Move fast, focus on workflow integration (the moat) |

### Trust Collapse Prevention (NEW)

If Duro stores one wrong fact confidently, or loses provenance, it'll get roasted publicly.

**Safeguards:**
- [ ] Default "proposed" state for externally-derived facts
- [ ] Clear confidence + source always visible
- [ ] Easy delete/revert with one click
- [ ] Never pretend certainty where it doesn't exist
- [ ] Version history on everything
- [ ] Audit trail for all changes

---

## Content & Marketing Timeline

### Ongoing (Start Week 3)

| Week | Content | Platform |
|------|---------|----------|
| 3 | "Why verification beats generation" | Blog + Twitter |
| 5 | "The hidden cost of AI amnesia" | Blog + HN |
| 7 | Launch announcement | HN + Twitter + Reddit |
| 9 | "How to build a decision feedback loop" | Blog + Twitter |
| 11 | Pro launch: "Power tools for memory hygiene" | Blog + Email |
| 13 | "Shared AI memory without the chaos" | Blog + LinkedIn |
| 16 | GitHub integration announcement | Blog + Twitter |
| 20 | Team launch + case study | Blog + Email |
| 22 | "The Builder's Compass Score" | Blog + Twitter |

---

## Key Milestones Summary

| Week | Milestone | Success Metric |
|------|-----------|----------------|
| 2 | Deterministic wow demo | Works every time |
| 4 | 10-min onboarding path | TTFV <10 min |
| 6 | Trust features shipped | Inspector, proposed/pinned |
| 8 | **PUBLIC LAUNCH** | 500 installs, 60% activation |
| 10 | Mini Compass Score v0 | Retention engine live |
| 12 | **PRO LAUNCH** | 20 users, $380 MRR |
| 20 | **TEAM LAUNCH** | 5 teams, $2K+ MRR |
| 24 | Full Compass Score | Dashboard live |
| 28 | Enterprise pilots | 2-3 conversations |

---

## Quick Reference: What to Build When

### Phase 0-1 (Weeks 1-8): Free Product
- [x] Core memory system (exists)
- [x] Decision validation (exists)
- [x] Episode tracking (exists)
- [x] MCP server (exists)
- [ ] **Deterministic wow demo** (scripted failure)
- [ ] **10-minute onboarding path** (duro init/import/demo)
- [ ] 4 pillar screenshots
- [ ] README overhaul
- [ ] Docs site
- [ ] Landing page
- [ ] Memory inspector
- [ ] Proposed/Pinned workflow

### Phase 2 (Weeks 9-12): Pro ($19/mo)
- [ ] Diff & rollback
- [ ] Advanced search
- [ ] **Mini Compass Score v0** (3 metrics)
- [ ] Export/backup
- [ ] E2E encrypted backup
- [ ] Stripe billing
- [ ] Account system

### Phase 3 (Weeks 13-20): Team ($39/user/mo)
- [ ] Team namespaces
- [ ] Roles (reader/writer/admin)
- [ ] Audit logs
- [ ] GitHub integration
- [ ] Admin dashboard
- [ ] Team billing

### Phase 4 (Weeks 21-24): Full Dashboard
- [ ] Full Compass Score (5 metrics)
- [ ] Recommendations engine
- [ ] Export/share reports

### Phase 5 (Weeks 25-28): Enterprise Prep
- [ ] SSO (Google/GitHub)
- [ ] Retention policies
- [ ] Enterprise audit
- [ ] Enterprise sales materials

---

## Decision Points

| Week | Decision | Options |
|------|----------|---------|
| 8 | Launch strategy | HN first vs Twitter first vs simultaneous |
| 12 | Pro pricing | Keep $19 vs adjust based on feedback |
| 16 | Team pricing | Keep $39 vs adjust based on enterprise feedback |
| 20 | Hiring | Solo longer vs bring on first hire |
| 24 | Fundraising | Bootstrap vs seek funding |

---

## Summary of Structural Upgrades (v2)

1. **Deterministic Wow Demo** - Scripted failure, works every time
2. **10-Minute Onboarding Path** - TTFV is the real adoption lever
3. **Mini Compass Score Earlier** - Week 9-10, not Week 21
4. **Trust Collapse as Primary Risk** - Safeguards built in
5. **Better Metrics** - Activation rate, week-1 retention, wow completion
6. **Pro = "Power tools for memory hygiene"** - Not "backup"

---

## Related Documents

- Competitive Analysis: `~/.agent/memory/docs/duro-competitive-analysis-2026-02.md`
- Business Model v2: `~/.agent/memory/docs/duro-business-model-2026-02.md`
- Builder's Compass Synthesis v2: `~/.agent/memory/docs/duro-builders-compass-synthesis.md`
- This Roadmap: `~/.agent/memory/docs/duro-roadmap-2026.md`

---

*Created: February 20, 2026*
*Updated: February 20, 2026 (v2 - Structural upgrades)*
*Review: Weekly progress check against milestones*
