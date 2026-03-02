"""
Skill: decision_accountability
Description: Surface and review stale decisions - closes the feedback loop on past choices
Version: 1.0.0
Tier: tested
"""

SKILL_META = {
    "name": "decision_accountability",
    "description": "Surface and review stale decisions - closes feedback loop on past choices",
    "tier": "tested",
    "version": "1.0.0",
    "triggers": ["review decisions", "decision review", "stale decisions", "accountability"],
    "keywords": ["decision", "review", "stale", "accountability", "feedback", "compound"],
}

REQUIRES = ["list_unreviewed_decisions", "review_decision", "validate_decision"]

def run(args, tools, context):
    results = {"success": True, "steps": [], "reviewed": []}
    
    days = args.get("older_than_days", 14)
    limit = args.get("limit", 5)
    
    # Step 1: Surface stale decisions
    list_unreviewed = tools.get("list_unreviewed_decisions")
    if list_unreviewed:
        try:
            decisions = list_unreviewed(older_than_days=days, limit=limit)
            dec_list = decisions if isinstance(decisions, list) else decisions.get("decisions", [])
            results["steps"].append({"step": "list_unreviewed", "found": len(dec_list)})
            results["decisions"] = dec_list
        except Exception as e:
            results["steps"].append({"step": "list_unreviewed", "error": str(e)})
            return results
    
    # Step 2: Get review context for each
    review = tools.get("review_decision")
    if review and results.get("decisions"):
        for dec in results["decisions"][:limit]:
            dec_id = dec.get("id", "")
            if not dec_id:
                continue
            try:
                ctx = review(decision_id=dec_id, dry_run=True)
                results["reviewed"].append({
                    "id": dec_id,
                    "decision": dec.get("decision", "")[:80],
                    "age_days": dec.get("age_days", 0),
                    "status": dec.get("status", "unknown"),
                })
            except:
                pass
    
    # Generate report
    lines = ["## Decision Accountability Report", ""]
    lines.append(f"**Found:** {len(results.get('decisions', []))} decisions older than {days} days")
    lines.append("")
    for r in results["reviewed"]:
        lines.append(f"- [{r['status']}] ({r['age_days']:.1f}d) {r['decision']}...")
    
    results["report"] = "\n".join(lines)
    return results
