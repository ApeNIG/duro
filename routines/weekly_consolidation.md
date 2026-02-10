# Weekly Consolidation Routine

**Frequency:** Every Sunday or after 7 days of activity
**Duration:** ~30 minutes
**Purpose:** Prevent hoarder brain. Merge, prune, promote.

---

## Checklist

### 1. Review Eval Results (5 min)

- [ ] Pull results from `.agent/evals/results/`
- [ ] Calculate pass rate trend (up/down/flat)
- [ ] Identify lowest-performing evals
- [ ] Note any new failure patterns

### 2. Rule Consolidation (10 min)

**Merge duplicates:**
- [ ] Check for rules with overlapping triggers
- [ ] Combine into single, comprehensive rule
- [ ] Delete redundant entries

**Promote patterns:**
- [ ] Rules used 3+ times in 14 days → increase priority
- [ ] Rules with 90%+ success rate → mark as validated
- [ ] Multiple related rules → consider parent rule

**Demote or prune:**
- [ ] Rules never used in 30 days → mark as "rare"
- [ ] Rules with <50% success rate → review and fix or remove
- [ ] One-off fixes that haven't recurred → archive

**Update index:**
- [ ] Recalculate usage counts
- [ ] Update `last_used` timestamps
- [ ] Reorder by usefulness (frequency × impact)

### 3. Skill Consolidation (10 min)

**Identify unused skills:**
- [ ] Skills not used in 30 days → review necessity
- [ ] Skills with <80% success rate → debug or remove

**Promote composition:**
- [ ] If skill A always follows skill B → create combined skill
- [ ] Extract common patterns into utility functions

**Update metadata:**
- [ ] Recalculate success rates from logs
- [ ] Update `known_issues` from recent failures
- [ ] Mark untested skills for testing

### 4. Proposal Review (5 min)

**Pending → Trial:**
- [ ] Review `proposals/pending/`
- [ ] Select 1-3 for trial this week
- [ ] Move to `proposals/trial/` with trial period set

**Trial → Approved/Rejected:**
- [ ] Check trial end dates
- [ ] Run relevant evals
- [ ] Move based on results

**Clean up rejected:**
- [ ] Ensure rejection reason documented
- [ ] Archive old rejected proposals (>30 days)

### 5. Update Scoreboard (5 min)

- [ ] Regenerate `SCOREBOARD.md`
- [ ] Add weekly comparison row
- [ ] Update action items

---

## Promotion Criteria

**Rule promotion (rare → soft → hard):**
- Used 3+ times: promote from rare to soft
- 90%+ success over 10+ uses: promote to hard
- Prevents serious errors: promote to hard immediately

**Skill promotion (untested → tested → core):**
- Passes all tests: move to tested
- Used 10+ times with 95%+ success: move to core
- Core skills get priority in auto-selection

---

## Pruning Criteria

**Safe to remove:**
- Never used in 60 days AND not a safety rule
- Superseded by better rule/skill
- Documented as "obsolete" with replacement noted

**Archive instead of delete:**
- Might be useful later
- Contains useful failure analysis
- Part of historical record

---

## Consolidation Heuristics

**"Used 3x in 14 days" → Promote**
- Repeated use = validated usefulness

**"Failed 3x in 14 days" → Review**
- Either fix the rule/skill or remove it

**"Similar triggers, same action" → Merge**
- Reduce lookup overhead

**"Complex rule with many conditions" → Split**
- Simpler rules are easier to maintain

---

## Output

After consolidation, update:
1. `rules/index.json` - usage counts, ordering
2. `skills/index.json` - usage counts, ordering
3. `evals/SCOREBOARD.md` - weekly summary
4. `memory/consolidation/` - synthesis notes

---

*Routine established: 2026-02-10*
