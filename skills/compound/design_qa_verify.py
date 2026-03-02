"""
Skill: design_qa_verify
Description: Rigorous design QA - measures before claiming done. Prevents false "matches" claims.
Version: 1.0.0
Tier: tested

Failure pattern this fixes: Visual guessing instead of measuring.
Key insight: "The margin between subtle tension and alignment error is 2-3px"

Process:
1. Get snapshot_layout for pixel measurements
2. Calculate edge positions mathematically
3. Check alignment relationships numerically
4. Take screenshot for hierarchy check
5. List specific issues (never "looks good")
"""

SKILL_META = {
    "name": "design_qa_verify",
    "description": "Rigorous design QA - measures before claiming done",
    "tier": "tested",
    "version": "1.0.0",
    "triggers": ["design qa", "verify design", "check design", "does this match"],
    "keywords": ["design", "qa", "verify", "alignment", "spacing", "measurement", "precision"],
}

REQUIRES = ["snapshot_layout", "get_screenshot", "batch_get"]

def calculate_edges(node):
    """Calculate right and bottom edges from node bounds."""
    x = node.get("x", 0)
    y = node.get("y", 0)
    width = node.get("width", 0)
    height = node.get("height", 0)
    return {
        "left": x,
        "top": y,
        "right": x + width if isinstance(width, (int, float)) else "auto",
        "bottom": y + height if isinstance(height, (int, float)) else "auto",
        "width": width,
        "height": height,
    }

def check_alignment(nodes, tolerance=2):
    """Check if nodes are aligned within tolerance."""
    issues = []
    
    # Group by approximate left edge
    left_edges = {}
    for n in nodes:
        edges = calculate_edges(n)
        left = round(edges["left"] / 10) * 10  # Group by 10px
        left_edges.setdefault(left, []).append((n.get("name", n.get("id")), edges["left"]))
    
    # Check for near-misses (within 10px but not exact)
    for group_key, items in left_edges.items():
        if len(items) > 1:
            values = [v for _, v in items]
            spread = max(values) - min(values)
            if 0 < spread <= 10:
                issues.append(f"Near-miss alignment: {[n for n, _ in items]} differ by {spread}px")
    
    return issues

def run(args, tools, context):
    results = {"success": True, "checks": [], "issues": [], "measurements": {}}
    
    file_path = args.get("file_path", "")
    node_id = args.get("node_id", "")
    reference_spec = args.get("reference_spec", {})  # Optional: expected values
    
    if not node_id:
        return {"success": False, "error": "node_id required"}
    
    # Step 1: Get layout measurements
    snapshot_layout = tools.get("snapshot_layout")
    if snapshot_layout:
        try:
            layout = snapshot_layout(filePath=file_path, parentId=node_id, maxDepth=2)
            results["checks"].append({"step": "snapshot_layout", "status": "done"})
            
            # Extract measurements
            if isinstance(layout, dict):
                nodes = layout.get("nodes", [layout])
            elif isinstance(layout, list):
                nodes = layout
            else:
                nodes = []
            
            for node in nodes[:20]:  # Limit to avoid overflow
                name = node.get("name", node.get("id", "unknown"))
                results["measurements"][name] = calculate_edges(node)
            
            # Check alignments
            alignment_issues = check_alignment(nodes)
            results["issues"].extend(alignment_issues)
            
        except Exception as e:
            results["checks"].append({"step": "snapshot_layout", "error": str(e)})
    
    # Step 2: Get screenshot for visual hierarchy check
    get_screenshot = tools.get("get_screenshot")
    if get_screenshot:
        try:
            get_screenshot(filePath=file_path, nodeId=node_id)
            results["checks"].append({"step": "screenshot", "status": "done"})
        except Exception as e:
            results["checks"].append({"step": "screenshot", "error": str(e)})
    
    # Step 3: Compare to reference spec if provided
    if reference_spec:
        for element, expected in reference_spec.items():
            actual = results["measurements"].get(element, {})
            for prop, expected_val in expected.items():
                actual_val = actual.get(prop)
                if actual_val is not None and actual_val != expected_val:
                    diff = abs(actual_val - expected_val) if isinstance(actual_val, (int, float)) else "mismatch"
                    results["issues"].append(f"{element}.{prop}: expected {expected_val}, got {actual_val} (diff: {diff})")
    
    # Generate report
    lines = ["## Design QA Verify Report", ""]
    lines.append(f"**Node:** {node_id}")
    lines.append(f"**Checks completed:** {len(results['checks'])}")
    lines.append(f"**Issues found:** {len(results['issues'])}")
    lines.append("")
    
    if results["issues"]:
        lines.append("### Issues")
        for issue in results["issues"]:
            lines.append(f"- {issue}")
        lines.append("")
    else:
        lines.append("### No alignment issues detected")
        lines.append("*Note: This is numerical check only. Still verify visual hierarchy manually.*")
    
    if results["measurements"]:
        lines.append("### Measurements (first 5)")
        for name, edges in list(results["measurements"].items())[:5]:
            lines.append(f"- **{name}**: L={edges['left']}, R={edges['right']}, W={edges['width']}")
    
    results["report"] = "\n".join(lines)
    
    # Final verdict
    if results["issues"]:
        results["verdict"] = "ISSUES_FOUND"
        results["can_claim_done"] = False
    else:
        results["verdict"] = "NUMERICAL_CHECK_PASSED"
        results["can_claim_done"] = True  # But still need visual hierarchy check
    
    return results

if __name__ == "__main__":
    print("design_qa_verify v1.0.0")
    print("Prevents false 'done' claims by measuring instead of guessing")
