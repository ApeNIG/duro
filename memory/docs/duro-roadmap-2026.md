# DURO ROADMAP 2026
## From Philosophy to Product to Paying Customers
### February 2026

---

## Overview

This roadmap synthesizes:
- Competitive Analysis (60+ products)
- Business Model v2 (trust-first, bottoms-up B2B)
- Builder's Compass (operationalized philosophy)

**The Goal:** 500 installs → 50 active users → 20 Pro users → 5 paying teams → $100K+ ARR Year 1

---

## Phase 0: Foundation (Now - Week 2)
### "Make It Real"

**Objective:** Get Duro ready for public eyes. Build the "moment of wow."

#### Week 1: The Moment of Wow

| Task | Details | Deliverable |
|------|---------|-------------|
| Build the wow demo | Agent fails → Duro shows past decision → Agent self-corrects with provenance | 2-minute video/GIF |
| Script the demo | Write exact steps, make it reproducible | Demo script |
| Record screen capture | Clean, professional, no fumbling | MP4 + GIF |

**The Wow Flow:**
```
1. Start fresh Claude Code session
2. Ask it to do something it will get wrong
3. Duro surfaces: "This happened before. Here's what we learned."
4. Agent corrects itself, links provenance
5. "Why did we do it this way?" → Duro answers with source
```

#### Week 2: One Sentence + One Screenshot

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
- [ ] Wow demo video/GIF

---

## Phase 1: Lovable + Trustworthy (Weeks 3-8)
### "Make Developers Love It"

**Objective:** Ship to GitHub, get 500 installs, 50 active daily users.

### Week 3-4: Installation & Docs

| Task | Details | Owner |
|------|---------|-------|
| Polish installation | One-command install, clear error messages | Dev |
| README.md overhaul | Clear value prop, quick start, screenshots | Dev |
| Documentation site | Installation, configuration, MCP setup, tutorials | Dev |
| Troubleshooting guide | Common issues, solutions, debug steps | Dev |

**README Structure:**
```markdown
# Duro

> Memory layer for AI agents. Store decisions with provenance.
> Stop repeating mistakes. Audit what your AI "knows."

## The Problem
Your AI forgets everything. Every session starts fresh.
Mistakes repeat. Decisions aren't tracked. Nothing compounds.

## The Solution
[Screenshot of wow demo]

## Quick Start
[One-command install]

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
| Landing page | Simple, clear, wow demo embedded | duro.dev or similar |
| GitHub release | Proper versioning, changelog, release notes | v1.0.0 |
| Launch content | HN post, Twitter thread, Reddit posts | 3 pieces |
| Community setup | Discord or GitHub Discussions | Community space |

**Landing Page Structure:**
```
Hero: "AI generates. Builders verify. Duro remembers."
       [Wow demo GIF]
       [Install Now button]

Problem: Your AI forgets everything
Solution: 4 pillars with screenshots
Social Proof: (empty for now, add later)
CTA: Get started in 60 seconds
```

**Launch Checklist:**
- [ ] GitHub repo public with proper README
- [ ] Landing page live
- [ ] Docs site live
- [ ] Wow demo embedded
- [ ] HN post drafted
- [ ] Twitter thread drafted
- [ ] r/ClaudeAI post drafted

### Phase 1 Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| GitHub stars | 200+ | GitHub |
| Installs | 500+ | Download stats / npm |
| Active daily users | 50+ | Telemetry (opt-in) |
| Discord members | 100+ | Discord |
| Bug reports | <10 critical | GitHub Issues |

---

## Phase 2: Pro Launch (Weeks 9-12)
### "Convert Love to Revenue"

**Objective:** Launch Pro tier, get 20 paying users at $19/mo.

### Week 9-10: Pro Features

| Feature | Description | Effort |
|---------|-------------|--------|
| **Diff & Rollback** | See changes to any artifact, undo mistakes | 1 week |
| **Advanced Search** | Semantic search across all memory | 3 days |
| **Export/Backup** | JSON export, manual backup | 2 days |
| **E2E Encrypted Backup** | Cloud backup (optional), encrypted client-side | 1 week |

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
│  FREE           PRO              TEAM           │
│  $0/mo          $19/mo           $39/user/mo    │
│                                                 │
│  ✓ Full core    ✓ Everything     ✓ Everything   │
│  ✓ Local only     in Free          in Pro       │
│  ✓ Single user  ✓ Memory         ✓ Namespaces   │
│                   inspector      ✓ ACL          │
│                 ✓ Diff/rollback  ✓ Audit logs   │
│                 ✓ Provenance     ✓ GitHub       │
│                 ✓ E2E backup       integration  │
│                 ✓ Advanced       ✓ Admin        │
│                   search           dashboard    │
│                                                 │
│  [Get Started]  [Upgrade]        [Contact]      │
│                                                 │
└─────────────────────────────────────────────────┘
```

### Week 12: Pro Launch

| Task | Details | Deliverable |
|------|---------|-------------|
| Pro launch post | Blog post explaining Pro value | Blog post |
| Email existing users | "Pro is here" announcement | Email |
| Update landing page | Add pricing section | Updated site |
| Pro documentation | Document all Pro features | Docs |

### Phase 2 Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Pro conversions | 20+ | Stripe |
| MRR | $380+ | Stripe |
| Conversion rate | 4%+ | Pro users / total installs |
| Churn | <5%/mo | Stripe |
| NPS | 40+ | Survey |

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
| Team MRR | $975+ | Stripe (5 teams × 5 users × $39) |
| Total MRR | $2,000+ | Stripe |
| GitHub integration usage | 50%+ of teams | Telemetry |

---

## Phase 4: Builder's Compass Score (Weeks 21-24)
### "The Dashboard That Sells"

**Objective:** Build the scoreboard. This becomes the product AND the sales wedge.

### Week 21-22: Core Metrics

| Metric | What It Measures | Implementation |
|--------|------------------|----------------|
| **Verification Coverage** | % of decisions with validation status | Query decisions, calculate % validated/reversed |
| **Staleness Index** | % of facts past decay threshold | Query facts, check last_reinforced |
| **Decision Closure Rate** | % validated/reversed within 14 days | Query decisions by age and status |
| **Skill Reuse Rate** | Average uses per skill | Track skill usage in episodes |
| **Tool Reliability** | % of tool calls that succeed | Track orchestrator outcomes |

### Week 23-24: Dashboard UI

**Dashboard Spec:**
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
| Dashboard adoption | 70%+ of Pro/Team users | Telemetry |
| Score improvement | Users improve score over time | Track scores |
| Feature in sales convos | Used in 80%+ of Team demos | Sales tracking |

---

## Phase 5: Enterprise Prep (Weeks 25-28)
### "Get Ready for Big Deals"

**Objective:** Have 2-3 enterprise pilot conversations with real requirements.

### Week 25-26: Enterprise Features Scoping

| Task | Details | Deliverable |
|------|---------|-------------|
| Talk to large users | Interview any teams using Duro | Interview notes |
| Identify requirements | What do they need that we don't have? | Requirements doc |
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
| **Enterprise Audit** | Extended audit retention, export | 3 days |

### Phase 5 Success Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Enterprise conversations | 3+ | CRM / notes |
| Pilot agreements | 1-2 | Signed agreements |
| Enterprise requirements doc | Complete | Internal doc |

---

## Content & Marketing Timeline

### Ongoing (Start Week 3)

| Week | Content | Platform |
|------|---------|----------|
| 3 | "Why verification beats generation" | Blog + Twitter |
| 5 | "The hidden cost of AI amnesia" | Blog + HN |
| 7 | Launch announcement | HN + Twitter + Reddit |
| 9 | "How to build a decision feedback loop" | Blog + Twitter |
| 11 | Pro launch announcement | Blog + Email |
| 13 | "Shared AI memory without the chaos" | Blog + LinkedIn |
| 16 | GitHub integration announcement | Blog + Twitter |
| 20 | Team launch + case study | Blog + Email |
| 22 | "The Builder's Compass Score" | Blog + Twitter |

### Content Themes

| Theme | Articles |
|-------|----------|
| **Philosophy** | Why verification > generation, The compounding advantage |
| **Practical** | Decision feedback loops, Memory hygiene, Debugging with context |
| **Product** | Feature announcements, How-tos, Case studies |
| **Thought Leadership** | Future of AI agents, Why memory matters |

---

## Key Milestones Summary

| Week | Milestone | Success Metric |
|------|-----------|----------------|
| 2 | Wow demo complete | Video/GIF ready |
| 4 | Docs & README done | Clear, professional |
| 6 | Trust features shipped | Inspector, proposed/pinned |
| 8 | **PUBLIC LAUNCH** | 500 installs |
| 12 | **PRO LAUNCH** | 20 paying users, $380 MRR |
| 20 | **TEAM LAUNCH** | 5 teams, $2K+ MRR |
| 24 | Compass Score shipped | Dashboard live |
| 28 | Enterprise pilots | 2-3 conversations |

---

## Resource Requirements

### Solo Founder Path

| Phase | Focus | Hours/Week |
|-------|-------|------------|
| 0-1 | Build + docs | 40-50 |
| 2 | Build + launch | 40-50 |
| 3 | Build + sales | 30 build, 10 sales |
| 4-5 | Build + enterprise | 20 build, 20 sales |

### With Help

| Role | When Needed | Why |
|------|-------------|-----|
| Part-time designer | Week 3 | Landing page, screenshots |
| Part-time content | Week 5 | Blog posts, docs |
| First hire (eng) | Week 16+ | Team features, scale |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| **No one installs** | Double down on wow demo, post in more communities |
| **Installs but no active users** | Interview churned users, improve onboarding |
| **No Pro conversions** | Talk to users, understand what Pro would need to have |
| **Teams don't close** | May need to lower price, add features, or find different ICP |
| **Competitor copies features** | Move fast, focus on workflow integration (the moat) |

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

## Quick Reference: What to Build When

### Phase 0-1 (Weeks 1-8): Free Product
- [x] Core memory system (exists)
- [x] Decision validation (exists)
- [x] Episode tracking (exists)
- [x] MCP server (exists)
- [ ] Wow demo
- [ ] 4 pillar screenshots
- [ ] README overhaul
- [ ] Docs site
- [ ] Landing page
- [ ] Memory inspector
- [ ] Proposed/Pinned workflow

### Phase 2 (Weeks 9-12): Pro ($19/mo)
- [ ] Diff & rollback
- [ ] Advanced search
- [ ] E2E encrypted backup
- [ ] Stripe billing
- [ ] Account system
- [ ] License validation

### Phase 3 (Weeks 13-20): Team ($39/user/mo)
- [ ] Team namespaces
- [ ] Roles (reader/writer/admin)
- [ ] Audit logs
- [ ] GitHub integration
- [ ] Admin dashboard
- [ ] Team billing

### Phase 4 (Weeks 21-24): Dashboard
- [ ] Verification coverage metric
- [ ] Staleness index metric
- [ ] Decision closure rate
- [ ] Skill reuse rate
- [ ] Tool reliability
- [ ] Compass Score dashboard

### Phase 5 (Weeks 25-28): Enterprise Prep
- [ ] SSO (Google/GitHub)
- [ ] Retention policies
- [ ] Enterprise audit
- [ ] Enterprise sales materials

---

## Related Documents

- Competitive Analysis: `~/.agent/memory/docs/duro-competitive-analysis-2026-02.md`
- Business Model v2: `~/.agent/memory/docs/duro-business-model-2026-02.md`
- Builder's Compass Synthesis v2: `~/.agent/memory/docs/duro-builders-compass-synthesis.md`
- This Roadmap: `~/.agent/memory/docs/duro-roadmap-2026.md`

---

*Created: February 20, 2026*
*Review: Weekly progress check against milestones*
