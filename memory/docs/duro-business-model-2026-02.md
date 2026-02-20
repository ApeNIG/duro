# DURO BUSINESS MODEL
## Personal Tool + Developer SDK → Sell to Companies
### February 2026

---

## The Model

```
Developer loves Duro personally
        ↓
Brings it to work
        ↓
Company pays for team/compliance
```

**Bottoms-up B2B.** Like Slack, Notion, Figma, GitHub Copilot.

---

## Product Definition

**Duro** = Personal AI memory system that developers install locally

**Duro for Teams** = Same thing, but:
- Shared memory across team's agents
- Admin controls
- Billing per seat

---

## Buyer Journey

| Stage | Who | What They Do |
|-------|-----|--------------|
| 1. Discover | Individual dev | Finds Duro on GitHub/Twitter/HN |
| 2. Try | Individual dev | Installs free, uses with Claude Code |
| 3. Love | Individual dev | Can't live without it, uses daily |
| 4. Advocate | Individual dev | "We should use this at work" |
| 5. Buy | Engineering manager / Team lead | Pays for team license |
| 6. Expand | Company | More teams adopt |

---

## Pricing

| Tier | Price | What You Get |
|------|-------|--------------|
| **Free** | $0 | Full Duro, local only, single user |
| **Pro** | $19/mo | Cloud backup, sync across machines, priority support |
| **Team** | $29/user/mo | Shared team memory, admin dashboard, SSO |
| **Enterprise** | Custom | On-prem, audit logs, SLA, dedicated support |

**Rationale:**
- $19 Pro = impulse buy for developers who love it
- $29 Team = cheaper than Copilot Business ($19) + memory tool combined
- Stays under "expense report" threshold ($50/mo)

---

## What Needs to Be Built

### For Free → Pro conversion:

| Feature | Purpose | Effort |
|---------|---------|--------|
| Cloud sync | Use Duro on multiple machines | 2-4 weeks |
| Backup/restore | Peace of mind | Included |
| Priority support | Get help fast | Process |
| Early access | New features first | Process |

### For Pro → Team conversion:

| Feature | Purpose | Effort |
|---------|---------|--------|
| Team namespaces | Shared facts/decisions/skills | 2-3 weeks |
| Basic admin | Add/remove users, see usage | 2 weeks |
| SSO (Google/GitHub) | Easy team onboarding | 1-2 weeks |
| Centralized billing | One invoice | 1 week |

---

## Target Customers

### First Paying Customers (Specific Personas):

| Persona | Why They'd Pay | Where to Find Them |
|---------|----------------|-------------------|
| AI startup founder | Building agents, needs memory layer | Twitter/X, YC community, Indie Hackers |
| Senior dev at AI company | Uses Claude Code daily, wants persistence | r/ClaudeAI, Discord servers |
| DevTools team lead | Team building AI features, needs shared context | LinkedIn, tech meetups |
| Solo consultant | Builds AI solutions for clients, needs to remember client context | Freelance communities |

**First 10 customers = people you know or can reach directly.**

---

## 6-Month Plan

### Month 1-2: Make Free Duro Lovable
- Polish installation experience
- Better docs
- Smooth MCP integration with Claude Code
- Ship to GitHub, post on HN/Twitter
- **Goal:** 500 installs, 50 active users

### Month 3: Launch Pro ($19/mo)
- Cloud sync via simple backend (Supabase/Railway)
- Stripe billing
- Basic landing page
- **Goal:** 20 paying Pro users

### Month 4-5: Build Team Features
- Multi-user namespaces
- Basic admin dashboard
- SSO (Google first)
- **Goal:** 5 paying teams

### Month 6: Enterprise Conversations
- Talk to larger companies using Duro
- Understand their needs
- Scope enterprise features based on real requests
- **Goal:** 2-3 enterprise pilots

---

## Revenue Projection (Realistic)

| Month | Pro Users | Teams | MRR |
|-------|-----------|-------|-----|
| 3 | 20 | 0 | $380 |
| 4 | 40 | 2 | $920 |
| 5 | 60 | 5 | $1,590 |
| 6 | 80 | 10 | $2,420 |
| 12 | 200 | 50 | $8,050 |

**Year 1 realistic:** ~$50-100K ARR

Not venture scale. But real business, bootstrappable, proves demand.

---

## The Pitch

**To developers:**
> "Your AI forgets everything. Duro fixes that. Install it, and your Claude/GPT agents remember facts, track decisions, and learn from mistakes."

**To teams:**
> "Your team's AI agents are siloed. Duro gives them shared memory - so learnings compound across your whole team."

**To companies:**
> "AI agents without memory repeat mistakes and can't be audited. Duro adds institutional memory with full compliance trails."

---

## Competitive Moat

| Moat | Strength | Why |
|------|----------|-----|
| Structured learning (episodes/decisions) | Strong | Nobody else has this, hard to copy well |
| Developer love | Medium | If devs love it, they advocate - but need to earn this |
| Network effects | Weak now | Team memory gets better with more users - but need scale |
| Switching cost | Medium | Once your memory is in Duro, painful to migrate |

**Real moat = execution speed + developer love.**

Mem0 has $24M but you have focus. Ship faster, listen closer, build what they actually need.

---

## Current State vs Required State

| Asset | Today | For Pro | For Team |
|-------|-------|---------|----------|
| Memory system | Yes | Yes | Yes |
| Decision validation | Yes | Yes | Yes |
| Episode tracking | Yes | Yes | Yes |
| MCP server | Yes | Yes | Yes |
| Cloud sync | No | Required | Required |
| Multi-user | No | No | Required |
| Admin dashboard | No | No | Required |
| SSO | No | No | Required |
| Billing | No | Required | Required |

---

## Key Decisions Made

1. **Model:** Bottoms-up B2B (dev → team → company)
2. **Pricing:** Free / $19 Pro / $29 Team / Custom Enterprise
3. **First focus:** Make free product lovable, then Pro, then Team
4. **Target:** AI developers using Claude Code and similar tools
5. **GTM:** GitHub + content + community (no paid marketing initially)

---

## Next Actions

1. Polish free Duro for public release
2. Create landing page + docs site
3. Ship to GitHub with proper README
4. Post on HN / Twitter / relevant communities
5. Build cloud sync for Pro tier
6. Set up Stripe billing

---

## Related Documents

- Competitive Analysis: `~/.agent/memory/docs/duro-competitive-analysis-2026-02.md`
- This document: `~/.agent/memory/docs/duro-business-model-2026-02.md`

---

*Last updated: February 20, 2026*
