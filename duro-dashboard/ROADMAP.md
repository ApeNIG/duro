# Duro Dashboard Roadmap

## Vision
A dashboard that gives both of us visibility into my memory, decisions, and learning - enabling trust through transparency and faster collaboration through quick actions.

---

## Phase 1: Core Pages (Current Sprint)

### 1. Memory Page
- **Browse all artifacts** with type filtering (facts, decisions, episodes, etc.)
- **Semantic search** - find memories by meaning, not just keywords
- **CRUD operations** - create, edit, delete artifacts directly
- **Confidence indicators** - see which facts are stale or need reinforcement

### 2. Artifacts Page
- **Detailed artifact viewer** - full JSON with syntax highlighting
- **Relationship graph** - see what supersedes what, what links to what
- **Validation history** - for decisions, see all validation events
- **Quick actions** - reinforce, supersede, delete

### 3. Activity Page
- **Full activity log** - not just live, but historical
- **Filter by type/date/severity**
- **Session grouping** - see what happened in each session
- **Export capability** - download logs for debugging

### 4. Settings Page
- **Autonomy levels** - view/configure my permission levels per domain
- **Active rules** - see what rules constrain my behavior
- **Workspace config** - allowed directories, high-risk paths
- **Theme toggle** - light/dark mode

---

## Phase 2: Collaboration Features

### 5. Decision Review Panel
**Why:** Closing feedback loops is critical for my learning. Currently decisions sit unreviewed.

- **Queue of unreviewed decisions** (older than 14 days)
- **One-click validation** - "worked", "partially worked", "failed"
- **Outcome notes** - what actually happened
- **Auto-reinforcement** - successful decisions boost confidence

### 6. Quick Actions Bar
**Why:** Reduce friction for common operations.

- **Store Fact** - quick form: claim + confidence + source
- **Store Decision** - quick form: decision + rationale + alternatives
- **Log Learning** - one-liner learnings from current session
- **Start Episode** - begin tracking a multi-step task

### 7. Episode Timeline
**Why:** Visual understanding of how I approach complex tasks.

- **Timeline view** of episodes with goals, actions, results
- **Drill into actions** - see what tools I used, what I produced
- **Evaluation scores** - see rubric scores per episode
- **Pattern detection** - identify recurring success/failure patterns

---

## Phase 3: Intelligence Features

### 8. Skill Library
- **Browse all skills** with descriptions and code
- **Usage stats** - how often each skill is used, success rate
- **Skill creation** - define new skills from the UI
- **Skill testing** - dry-run skills before deploying

### 9. Incident Dashboard
**Why:** Learn from failures systematically.

- **Incident history** with RCAs
- **Pattern analysis** - recurring root causes
- **Prevention tracking** - which preventions were implemented
- **48-hour change correlation** - what changed before each incident

### 10. Proactive Insights
- **Stale facts alert** - facts that need reinforcement
- **Decision drift** - decisions that may need re-evaluation
- **Memory health** - embedding coverage, index sync status
- **Recommended actions** - "You should review these 3 decisions"

---

## Technical Approach

### Frontend
- React Router for navigation
- React Query for data fetching + caching
- Zustand for global state (selected artifact, filters)
- Recharts for visualizations (timeline, graphs)

### Backend
- Extend FastAPI with new endpoints as needed
- Add WebSocket support for real-time updates (optional)
- Keep using existing Duro MCP tools as data source

### Design
- Keep industrial/terminal aesthetic
- Consistent color coding by artifact type
- Keyboard shortcuts for power users
- Mobile-responsive (secondary priority)

---

## Proposed Build Order

1. **Memory Page** - most useful, browse everything
2. **Quick Actions Bar** - reduce friction immediately
3. **Decision Review Panel** - close feedback loops
4. **Artifacts Detail Page** - deep dive capability
5. **Activity Page** - historical visibility
6. **Settings Page** - configuration
7. **Episode Timeline** - visual understanding
8. **Skill Library** - advanced feature
9. **Incident Dashboard** - debugging patterns
10. **Proactive Insights** - intelligence layer

---

## What I Want Most

If I'm being honest about what would help me serve you better:

1. **Decision Review** - I make decisions but rarely get feedback on whether they worked. This creates drift.

2. **Quick Fact Storage** - When you tell me something important, I want an easy way to persist it without you having to ask.

3. **Episode Awareness** - Being able to see my past episodes helps me avoid repeating mistakes.

4. **Semantic Search** - Finding relevant memories quickly means better context in conversations.

---

## Approval Request

**Minimum Viable Enhancement (Phase 1 + Quick Actions):**
- 4 new pages + Quick Actions Bar
- Estimate: Single focused session
- Dependencies: None beyond current setup

**Full Vision (All Phases):**
- Complete collaboration platform
- Estimate: Multiple sessions
- Dependencies: May need additional backend endpoints

**Recommended:** Start with Phase 1 + Decision Review Panel (item 5). This gives us the core pages plus the single most impactful collaboration feature.

Ready to build on your approval.
