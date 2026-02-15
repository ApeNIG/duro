# Eval Definition Schema

Evaluations are defined in YAML files that specify what to test, how to validate, and what metrics to track.

## File Location

Evals live in category directories:
- `evals/skills/` - Individual skill evals
- `evals/workflows/` - Multi-skill workflow evals
- `evals/fashanus/` - Fashanus project-specific evals
- `evals/general/` - General-purpose evals

## Required Fields

```yaml
id: eval_skill_001          # Unique identifier
name: Generate TTS Audio    # Human-readable name
description: Test TTS skill # What this eval tests
skill_path: audio/generate_tts.py  # Skill being tested
```

## Input Definition

```yaml
inputs:
  text:
    type: string
    description: Text to convert to speech
    default: "Hello, this is a test."
    example: "Welcome to the show."
  voice:
    type: string
    description: Voice ID to use
    default: "en-GB-SoniaNeural"
  output_path:
    type: file
    description: Where to save audio
    default: "/tmp/eval_output.mp3"
```

## Expected Outputs

```yaml
expected_outputs:
  - name: file_exists
    type: boolean
    description: Output file was created
  - name: file_size
    type: constraint
    threshold: 1024  # Minimum bytes
    description: File is at least 1KB
  - name: duration_seconds
    type: range
    min: 1
    max: 30
    description: Audio length in reasonable range
```

## Metrics

```yaml
metrics:
  pass_fail:
    type: boolean
    description: Overall pass/fail
  time_seconds:
    type: integer
    description: Execution time
  quality_score:
    type: integer
    range: [1, 5]
    description: Subjective quality rating
```

## Baseline (for regression detection)

```yaml
baseline:
  time_seconds: 5
  file_size: 10000
  quality_score: 4
```

## Flaky Handling

For skills with external dependencies that may fail intermittently:

```yaml
flaky: true               # Mark as potentially flaky
mock_mode: true           # Can run with mocked externals
retry_count: 3            # Retry on transient failures
flaky_reason: "Depends on edge-tts network service"
```

Flaky evals:
- Are skipped in normal runs (use `--mock` to include)
- Don't fail CI on transient errors
- Track flaky trigger rate separately
- Retry automatically before marking as failed

## Categories

```yaml
category: skills          # skills | workflows | fashanus | general
frequency: on_demand      # on_demand | daily | per_commit | per_episode
tags:
  - audio
  - tts
  - network-dependent
```

## History (auto-populated by runner)

```yaml
history:
  - date: "2026-02-15"
    pass: true
    time_seconds: 4.2
    notes: "Clean run"
  - date: "2026-02-14"
    pass: false
    time_seconds: 12.1
    notes: "Network timeout - flaky"
```

## Full Example

```yaml
id: eval_skill_tts_001
name: Generate TTS Audio
description: Test edge-tts speech generation
category: skills
skill_path: audio/generate_tts.py

flaky: true
mock_mode: true
retry_count: 2
flaky_reason: "Network dependency on edge-tts service"

inputs:
  text:
    type: string
    default: "Testing one two three."
  voice:
    type: string
    default: "en-GB-SoniaNeural"
  output_path:
    type: file
    default: "/tmp/eval_tts_test.mp3"

expected_outputs:
  - name: file_exists
    type: boolean
  - name: file_size
    type: constraint
    threshold: 1000

metrics:
  pass_fail:
    type: boolean
  time_seconds:
    type: integer

baseline:
  time_seconds: 5

tags:
  - audio
  - tts
  - network-dependent
```
