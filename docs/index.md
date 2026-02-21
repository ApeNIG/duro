---
layout: home

hero:
  name: Duro
  text: Memory for AI Agents
  tagline: Every fact has a source. Every decision gets validated. Intelligence compounds.
  image:
    src: /logo.svg
    alt: Duro
  actions:
    - theme: brand
      text: Get Started
      link: /guide/getting-started
    - theme: alt
      text: View on GitHub
      link: https://github.com/ApeNIG/duro

features:
  - icon: 🧠
    title: Memory
    details: Store facts, decisions, and episodes with full provenance. Know where knowledge came from and how confident you should be.
    link: /concepts/memory
  - icon: ✓
    title: Verification
    details: Track outcomes. Validate what worked. Reverse what didn't. Build institutional memory that's actually correct.
    link: /concepts/verification
  - icon: 🎛️
    title: Orchestration
    details: Reputation-based autonomy. Agents earn trust through successful outcomes. High-risk actions require approval.
    link: /concepts/orchestration
  - icon: 🔧
    title: Expertise
    details: Codify knowledge into skills and rules. What works once becomes repeatable. Expertise compounds.
    link: /concepts/expertise
---

## The Problem

Every conversation with your AI agent starts from zero. Past mistakes get repeated. Lessons learned disappear. There's no audit trail for what your agent "knows."

**Without memory:**
- Agent suggests 1000 req/min → ships broken code → production incident
- Same mistake happens again next month
- No one knows why decisions were made

## The Solution

Duro gives your AI agents **structured memory with provenance**. Every fact has a source. Every decision can be validated. Intelligence compounds instead of resetting.

```
> agent suggests 1000 req/min
$ duro recalls: "we learned it's 100/min after a production incident"
> agent self-corrects
[validated] decision with provenance
```

## Quick Start

```bash
# Clone the repo
git clone https://github.com/ApeNIG/duro.git ~/.agent

# Add to Claude Code MCP config
# Then restart Claude Code
```

[Get started in 10 minutes →](/guide/getting-started)

## Who It's For

**Builders who care about correctness.** Teams that want learning to compound. Those who don't want to ship nonsense.

- AI developers using Claude Code daily
- Teams building AI-powered products
- Anyone who wants to audit what their AI "knows"
