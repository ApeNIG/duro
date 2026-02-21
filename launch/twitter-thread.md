# Twitter/X Launch Thread

## Thread 1: Main Launch

**Tweet 1 (hook):**
```
My AI coding agent kept making the same mistake.

A month after a production incident, it suggested the wrong rate limit again.

So I built Duro: memory for AI agents that actually compounds.

🧵 Here's what I learned building it:
```

**Tweet 2 (problem):**
```
The problem with AI agents:

→ Every conversation starts from zero
→ Past mistakes get repeated
→ Lessons learned disappear
→ No audit trail for what they "know"

Your agent has amnesia. And it's expensive.
```

**Tweet 3 (insight):**
```
The insight:

AI agents don't need more context.
They need structured memory with provenance.

Not "the rate limit is 100"
But "we learned it's 100/min from a prod incident, validated, confidence 0.95"

That's the difference between remembering and knowing.
```

**Tweet 4 (demo):**
```
Here's Duro in action:

> agent suggests 1000 req/min
$ duro recalls: "we learned it's 100/min"
  source: production incident
  status: [validated]
> agent self-corrects

Crisis averted. Intelligence compounds.
```

**Tweet 5 (four pillars):**
```
Duro is built on 4 pillars:

01/ memory – facts with sources
02/ verification – decisions get validated
03/ orchestration – actions are permissioned
04/ expertise – patterns become skills

Each one compounds on the others.
```

**Tweet 6 (tech):**
```
Tech details for builders:

• MCP server (Claude Code, Claude Desktop)
• Local-first: JSON + SQLite
• Semantic search via embeddings
• 48-hour debug rule built in
• MIT licensed

No cloud. No API keys. Your data stays yours.
```

**Tweet 7 (anti-pitch):**
```
What I'm NOT building:

✗ Another RAG system
✗ A vector DB wrapper
✗ Enterprise features nobody asked for
✗ Dashboards and analytics

Just memory that works.
```

**Tweet 8 (CTA):**
```
Duro is free, open source, and ready to use.

If you're building with Claude Code and tired of your agent forgetting everything:

GitHub: github.com/ApeNIG/duro
Docs: apenig.github.io/duro

Built by builders who don't ship nonsense.
```

---

## Thread 2: Technical Deep Dive

**Tweet 1:**
```
How does AI agent memory actually work?

I spent months building Duro. Here's the architecture that makes intelligence compound:

🧵
```

**Tweet 2:**
```
Layer 1: Artifact Storage

Everything is a typed artifact:
• Facts (claims with sources)
• Decisions (choices with rationale)
• Episodes (goal → actions → outcome)
• Incidents (RCA with prevention)

JSON files. Git-friendly. Human-readable.
```

**Tweet 3:**
```
Layer 2: Provenance

Every fact tracks:
• source_urls – where it came from
• evidence_type – quote, paraphrase, inference
• confidence – 0.0 to 1.0
• decay – unreinforced facts lose confidence

High confidence requires receipts.
```

**Tweet 4:**
```
Layer 3: Validation Loop

Store decision → Use it → Track outcome → Validate/Reverse

Decisions have states:
• pending (new)
• validated (worked)
• reversed (didn't work)
• superseded (replaced)

This is how you close the feedback loop.
```

**Tweet 5:**
```
Layer 4: Search

Hybrid search: semantic + keyword

"how to handle rate limits" finds:
• Facts about rate limits
• Decisions about API design
• Past incidents

Proactive recall surfaces relevant memory automatically.
```

**Tweet 6:**
```
Layer 5: The 48-Hour Rule

When debugging: query what changed in the last 48 hours.

Log every structural change:
• Config updates
• Schema migrations
• Deploys

When things break, the cause is usually recent.
```

**Tweet 7:**
```
The compound effect:

More memory → better decisions
Better decisions → faster validation
Faster validation → more trust
More trust → more autonomy

This is how AI agents actually get smarter.
```

---

## Standalone Tweets

**Tweet A (problem-focused):**
```
Your AI agent has amnesia.

Every conversation: fresh start.
Past mistakes: repeated.
Lessons learned: gone.

This is why I built memory for AI agents.

github.com/ApeNIG/duro
```

**Tweet B (demo-focused):**
```
Watch Duro prevent a production incident:

> agent: "rate limit is 1000/min"
$ duro: "actually, we learned it's 100/min"
  [validated] from prod incident last month
> agent: "you're right, using 100/min"

Memory that compounds.
```

**Tweet C (philosophy):**
```
Hot take: AI agents don't need more context.

They need structured memory with provenance.

Not "here's everything about rate limits"
But "we learned X from Y with Z confidence"

That's the difference.
```

**Tweet D (builder-focused):**
```
If you use Claude Code:

Your agent forgets everything between sessions.
Same mistakes. Same suggestions. No learning.

Duro fixes this:
• Store facts with sources
• Track decisions with rationale
• Validate what actually worked

github.com/ApeNIG/duro
```

---

## Hashtags & Mentions

**Hashtags:**
#AI #ClaudeCode #BuildInPublic #OpenSource #DevTools

**Accounts to consider tagging:**
- @AnthropicAI (Claude)
- @alexalbert__ (Claude Code creator)
- Relevant AI/dev accounts in your network

**Best posting times:**
- Weekdays 9-11am PT (tech Twitter active)
- Avoid Fridays and weekends for launch
