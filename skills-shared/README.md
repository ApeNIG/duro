# skills-shared

Shared skill files that are synced via git. The main `skills/` directory is
gitignored (machine-local with stats, caches, etc).

## Setup on a new machine

Copy these into your local `skills/` directory and register them in `skills/index.json`:

```bash
# From the repo root:
cp -r skills-shared/memory/* skills/memory/
```

Then add entries to `skills/index.json` for each skill (IDs: skill_memory_001 through skill_memory_007).

## Skill Index Entries

Add these to the `"skills"` array in `skills/index.json`:

```json
{
  "id": "skill_memory_001",
  "name": "graduate_logs",
  "path": "memory/graduate_logs.py",
  "description": "Scan logs for graduation candidates (facts, decisions, insights)",
  "tier": "tested",
  "keywords": ["logs", "graduate", "promote", "facts", "decisions", "mining"]
},
{
  "id": "skill_memory_002",
  "name": "emerge",
  "path": "memory/emerge.py",
  "description": "Surface latent patterns from tag census and semantic probing",
  "tier": "tested",
  "keywords": ["patterns", "emerge", "latent", "tags", "census"]
},
{
  "id": "skill_memory_003",
  "name": "trace_concept",
  "path": "memory/trace_concept.py",
  "description": "Trace a concept's chronological arc through the knowledge base",
  "tier": "tested",
  "keywords": ["trace", "concept", "timeline", "arc", "history"]
},
{
  "id": "skill_memory_004",
  "name": "drift_report",
  "path": "memory/drift_report.py",
  "description": "Detect decision drift — unfollowed, contradicted, or undecided themes",
  "tier": "tested",
  "keywords": ["drift", "decisions", "follow-through", "contradictions"]
},
{
  "id": "skill_memory_005",
  "name": "connect_domains",
  "path": "memory/connect_domains.py",
  "description": "Find bridges between two knowledge domains",
  "tier": "tested",
  "keywords": ["domains", "bridges", "cross-domain", "connections"]
},
{
  "id": "skill_memory_006",
  "name": "idea_generation",
  "path": "memory/idea_generation.py",
  "description": "Generate ideas from gaps, staleness, and cross-domain opportunities",
  "tier": "tested",
  "keywords": ["ideas", "gaps", "opportunities", "generation"]
},
{
  "id": "skill_memory_007",
  "name": "orphan_detection",
  "path": "memory/orphan_detection.py",
  "description": "Find orphaned, stale, and duplicate artifacts in the knowledge base",
  "tier": "tested",
  "keywords": ["orphans", "hygiene", "duplicates", "stale", "cleanup"]
}
```
