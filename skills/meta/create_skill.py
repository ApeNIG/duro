"""
Meta-Skill: create_skill
Description: Generate a new skill from a successful workflow
Purpose: Scale skill library without handcrafting each one

Usage:
    python create_skill.py --name "my_skill" --category "audio" --description "Does X"

    Or import:
    from create_skill import create_skill_scaffold
    create_skill_scaffold("my_skill", "audio", "Does X", inputs, outputs)
"""

import os
import sys
import json
import argparse
from datetime import datetime
from textwrap import dedent

SKILLS_ROOT = os.path.join(os.path.dirname(__file__), "..")


def create_skill_scaffold(
    name: str,
    category: str,
    description: str,
    inputs: list = None,
    outputs: list = None,
    dependencies: list = None,
    example_code: str = None
) -> dict:
    """
    Create a new skill with all required files.

    Args:
        name: Skill name (snake_case)
        category: Category folder (audio, image, production, etc.)
        description: What the skill does
        inputs: List of input parameters
        outputs: List of outputs
        dependencies: Python packages required
        example_code: Optional example implementation

    Returns:
        dict with created files and status
    """
    inputs = inputs or []
    outputs = outputs or []
    dependencies = dependencies or []

    result = {
        "success": True,
        "skill_name": name,
        "files_created": [],
        "errors": []
    }

    # Create category directory if needed
    category_dir = os.path.join(SKILLS_ROOT, category)
    os.makedirs(category_dir, exist_ok=True)

    # Generate skill file
    skill_path = os.path.join(category_dir, f"{name}.py")
    skill_content = generate_skill_template(name, description, inputs, outputs, dependencies, example_code)

    try:
        with open(skill_path, 'w', encoding='utf-8') as f:
            f.write(skill_content)
        result["files_created"].append(skill_path)
    except Exception as e:
        result["errors"].append(f"Failed to create skill file: {e}")
        result["success"] = False

    # Generate test file
    test_path = os.path.join(category_dir, f"test_{name}.py")
    test_content = generate_test_template(name, category, inputs)

    try:
        with open(test_path, 'w', encoding='utf-8') as f:
            f.write(test_content)
        result["files_created"].append(test_path)
    except Exception as e:
        result["errors"].append(f"Failed to create test file: {e}")

    # Generate or update meta.json
    meta_path = os.path.join(category_dir, "meta.json")
    meta_content = generate_meta(name, description, inputs, outputs, dependencies, category)

    try:
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta_content, f, indent=2)
        result["files_created"].append(meta_path)
    except Exception as e:
        result["errors"].append(f"Failed to create meta file: {e}")

    # Update skills index
    try:
        update_skills_index(name, category, description)
        result["files_created"].append(os.path.join(SKILLS_ROOT, "index.json"))
    except Exception as e:
        result["errors"].append(f"Failed to update index: {e}")

    return result


def generate_skill_template(name, description, inputs, outputs, dependencies, example_code):
    """Generate the Python skill file."""

    # Build imports
    imports = ["import os", "import sys", "import argparse"]

    # Build input params
    input_params = ", ".join([f"{i['name']}: {i.get('type', 'str')}" for i in inputs]) if inputs else ""
    input_docs = "\n".join([f"        {i['name']}: {i.get('description', 'Input parameter')}" for i in inputs]) if inputs else "        None"

    # Build output docs
    output_docs = "\n".join([f"        {o['name']}: {o.get('description', 'Output')}" for o in outputs]) if outputs else "        dict with result"

    template = f'''"""
Skill: {name}
Description: {description}
Dependencies: {", ".join(dependencies) if dependencies else "None"}

Usage:
    python {name}.py [args]

    Or import:
    from {name} import {name}
"""

{chr(10).join(imports)}


def {name}({input_params}) -> dict:
    """
    {description}

    Args:
{input_docs}

    Returns:
{output_docs}
    """
    result = {{
        "success": False,
        "error": None
    }}

    try:
        # TODO: Implement skill logic
        {example_code if example_code else "pass  # Your implementation here"}

        result["success"] = True
    except Exception as e:
        result["error"] = str(e)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="{description}")
    # TODO: Add argument parsing based on inputs
    args = parser.parse_args()

    result = {name}()
    if result["success"]:
        print("Success")
    else:
        print(f"Error: {{result['error']}}")
        sys.exit(1)
'''
    return template


def generate_test_template(name, category, inputs):
    """Generate the test file."""

    template = f'''"""
Test: {name} skill
Run: python test_{name}.py
"""

import os
import sys
import tempfile

# Add parent to path for import
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from {name} import {name}


def test_basic():
    """Test basic functionality."""
    # TODO: Implement test
    # result = {name}(...)
    # assert result["success"], f"Failed: {{result['error']}}"
    print("PASS: test_basic (TODO: implement)")


def test_error_handling():
    """Test error cases."""
    # TODO: Implement error case test
    print("PASS: test_error_handling (TODO: implement)")


if __name__ == "__main__":
    print("Testing {name} skill...")
    print("-" * 40)

    try:
        test_basic()
        test_error_handling()
        print("-" * 40)
        print("ALL TESTS PASSED (some need implementation)")
    except AssertionError as e:
        print(f"FAIL: {{e}}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: {{e}}")
        sys.exit(1)
'''
    return template


def generate_meta(name, description, inputs, outputs, dependencies, category):
    """Generate the meta.json content."""

    return {
        "skill_id": f"skill_{category}_{name}",
        "name": name,
        "description": description,
        "version": "1.0.0",
        "created": datetime.now().strftime("%Y-%m-%d"),
        "last_updated": datetime.now().strftime("%Y-%m-%d"),
        "inputs": [
            {"name": i["name"], "type": i.get("type", "string"), "required": i.get("required", True), "description": i.get("description", "")}
            for i in inputs
        ] if inputs else [],
        "outputs": [
            {"name": o["name"], "type": o.get("type", "any"), "description": o.get("description", "")}
            for o in outputs
        ] if outputs else [],
        "dependencies": dependencies,
        "usage_count": 0,
        "success_count": 0,
        "failure_count": 0,
        "success_rate": 0.0,
        "last_used": None,
        "known_issues": [],
        "tested": False,
        "test_file": f"test_{name}.py"
    }


def update_skills_index(name, category, description):
    """Add the new skill to the index."""

    index_path = os.path.join(SKILLS_ROOT, "index.json")

    # Load existing index
    if os.path.exists(index_path):
        with open(index_path, 'r', encoding='utf-8') as f:
            index = json.load(f)
    else:
        index = {"version": "1.0", "description": "Duro Skills Index", "skills": []}

    # Check if skill already exists
    existing = [s for s in index["skills"] if s["name"] == name]
    if existing:
        return  # Already in index

    # Add new skill
    index["skills"].append({
        "id": f"skill_{category}_{name}",
        "name": name,
        "path": f"{category}/{name}.py",
        "description": description,
        "keywords": name.replace("_", " ").split()
    })

    index["last_updated"] = datetime.now().strftime("%Y-%m-%d")

    # Save updated index
    with open(index_path, 'w', encoding='utf-8') as f:
        json.dump(index, f, indent=2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create a new skill scaffold")
    parser.add_argument("--name", required=True, help="Skill name (snake_case)")
    parser.add_argument("--category", required=True, help="Category (audio, image, production, etc.)")
    parser.add_argument("--description", required=True, help="What the skill does")
    parser.add_argument("--deps", nargs="*", default=[], help="Dependencies")

    args = parser.parse_args()

    result = create_skill_scaffold(
        name=args.name,
        category=args.category,
        description=args.description,
        dependencies=args.deps
    )

    if result["success"]:
        print(f"Skill '{args.name}' created successfully!")
        print("Files created:")
        for f in result["files_created"]:
            print(f"  - {f}")
        print("\nNext steps:")
        print(f"  1. Implement the skill logic in {args.category}/{args.name}.py")
        print(f"  2. Write tests in {args.category}/test_{args.name}.py")
        print("  3. Run tests to verify")
    else:
        print("Failed to create skill:")
        for e in result["errors"]:
            print(f"  - {e}")
        sys.exit(1)
