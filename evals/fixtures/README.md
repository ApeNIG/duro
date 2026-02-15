# Eval Fixtures

Test fixtures for Duro eval suite.

## Files

| Fixture | Used By | Description |
|---------|---------|-------------|
| `sample_design.json` | design_to_code_verifier | Design spec for UserCard component |
| `sample_component.tsx` | design_to_code_verifier, accessibility_verifier | React component matching design |
| `sample_code.py` | code_review_verifier, test_coverage_verifier | Python service class |
| `git_repo/` | git_commit | Test git repository with staged changes |

## Usage

Fixtures use relative paths from `.agent/` root:
```yaml
inputs:
  file_path:
    default: "evals/fixtures/sample_code.py"
```

## Adding New Fixtures

1. Add file to this directory
2. Update relevant eval YAML to reference it
3. Document in this README
