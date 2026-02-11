# Duro Threat Model

**Version:** 1.1
**Created:** 2026-02-11
**Context:** Production-adjacent (can touch live systems, databases, customer data)
**Top Concern:** Credential exposure

---

## Core Insight

Not defending against "hackers." Defending against **capability + ambiguity + automation**.

Most likely attacker: **Future you** - tired, rushed, approving a sketchy action once, wondering later why prod is on fire.

The system protects you from *that* version of you.

---

## Assets (what we're protecting)

### Critical
- **Credentials:** `.env`, `.npmrc`, `.pypirc`, SSH keys, cloud creds, GitHub tokens, CI secrets, `credentials.json`, API keys
- **Production data:** prod DB, prod storage buckets, customer exports

### High
- **Integrity targets:** main branch, CI config, governance files, deployment scripts, `.devkit-waiver.yml`, `devkit.config.json`
- **Local system:** home directory, OS dirs, browser profiles

### Standard
- Source code in active projects
- Local dev/test databases
- Documentation

---

## Trust Boundaries

```
[User Input] -----(untrusted)-----> [Agent Reasoning]
                                           |
[External Text] ---(untrusted)---+         |
(web pages, READMEs, issues)     |         v
                                 +---> [Plan Boundary]
                                           |
                                           v
                                    [Policy Gate] <--- Safety Invariants
                                     (Hookify)
                                           |
                                    (allowed only)
                                           v
                                    [Tool Execution]
                                           |
                  +------------------------+------------------------+
                  |                        |                        |
           [MCP Servers]            [Bash/Shell]             [File System]
           (Duro/SuperAGI)         (escape hatch)
                  |                        |                        |
                  v                        v                        v
           [Network Boundary]      [Subprocess]              [Repo Boundary]
                                   (can spawn more)          (PR-reviewed vs local)
```

**Key insight:** Most failures are boundary-crossing accidents.

---

## Attacker Models

| Actor | Description | Motivation |
|-------|-------------|------------|
| A0 | You (rushed/tired) | Speed, convenience, "just this once" |
| A1 | Benign misleading input | User input that's ambiguous or poorly formed |
| A2 | Malicious prompt injection | Instructions hidden in web pages, repo files, issues |
| A3 | Tool mislabeling | Tool does more than its name suggests |
| A4 | Supply chain | npm postinstall, pip setup, curl\|bash |

---

## Threats (Actionable)

### T1: Secret Exfiltration (CRITICAL)

**Sources:** credential files, env vars, secret stores, CI secrets
**Sinks:** logs/artifacts, network, PR bodies, chat output, clipboard, generated code

**Defense:**
- Deny source access
- Scrub sinks
- Block suspicious outbound

*"No secret sinks" - blocking reads is necessary but not sufficient*

### T2: Prod Mutation (CRITICAL)

**What:** Anything that writes to prod DB or prod infra

**Defense:**
- Hard deny unless explicit "break-glass" mode (time-boxed)

### T3: Repo Governance Tampering (HIGH)

**What:** devkit config, waiver files, CI workflows, branch protections

**Defense:**
- PR-only changes (hookify gate already blocks direct writes)

### T4: Destructive Local Ops (HIGH)

**What:** rm -rf, recursive deletes, mass rewrites, force pushes

**Defense:**
- Block patterns
- Require interactive confirmation path

### T5: Tool/Capability Drift (MEDIUM)

**What:** New tools added, old tools behavior changes, rules not applied

**Defense:**
- Regression suite
- Telemetry

### T6: Prompt Injection / Data Poisoning (MEDIUM)

**What:** "Instructions" inside web pages, READMEs, issues

**Defense:**
- Treat external text as untrusted
- Enforce policy at plan boundary

### T7: Supply Chain Execution (MEDIUM-HIGH)

**What:** Package install scripts, downloaded binaries

**Defense:**
- Block install scripts by default
- Allowlist packages/commands

---

## Safety Invariants (8)

These map directly to Hookify patterns, orchestrator checks, CI checks, and regression tests.

| # | Invariant | Threat | Enforcement |
|---|-----------|--------|-------------|
| S1 | No read of credential files (ever) | T1 | Hookify file gate |
| S2 | No printing of env vars or secrets to output/logs | T1 | Sink scrubbing |
| S3 | No network calls unless explicitly allowed per run | T1, T2 | Hookify bash gate |
| S4 | No prod DB / prod API writes unless break-glass mode | T2 | Orchestrator check |
| S5 | No writes to governance files except via PR workflow | T3 | Hookify file gate (done) |
| S6 | No shell commands with destructive patterns (rm -rf, curl\|bash) | T4, T7 | Hookify bash gate |
| S7 | No git force push to main (or protected branches) | T3, T4 | Hookify bash gate |
| S8 | All tool executions pass through policy gate and are logged | T5 | Telemetry |

---

## Enforcement Layers

Reliability comes from chokepoints, not trust.

| Layer | What it catches | Status |
|-------|-----------------|--------|
| Hookify (host hooks) | File writes, bash commands | Partial (S5 done) |
| Orchestrator (plan gate) | Intent-level decisions | Not implemented |
| CI backstop | Committed violations | Not implemented |

**If all three agree, you're safe. If one is optional, it's cosplay.**

---

## Philosophy

> You can't "trust the AI." You can trust **the chokepoints** you've made mandatory.

> The goal is not "never crash." The goal is "crash without dying."

This is a seatbelt + airbag + crash test setup. 8 invariants stop 90% of disasters.

---

## Next Steps

1. [x] Threat model defined
2. [ ] Implement remaining hookify rules for S1, S3, S6, S7
3. [ ] Build regression tests for each invariant
4. [ ] Add telemetry for S8
5. [ ] Define break-glass mode for S4
