"""
Skill: session_start
Description: Compound startup skill - loads context, checks orphan episodes, primes recall
Version: 1.0.0
Tier: tested
"""

SKILL_META = {
    "name": "session_start",
    "description": "Compound startup skill - loads context, checks orphan episodes, primes recall",
    "tier": "tested",
    "version": "1.0.0",
    "triggers": ["session start", "start session", "good morning"],
    "keywords": ["session", "startup", "context", "recall", "habit", "compound"],
}

REQUIRES = ["load_context", "list_episodes", "proactive_recall"]

def run(args, tools, context):
    results = {"success": True, "steps": []}
    
    # Step 1: Load context
    load_context = tools.get("load_context")
    if load_context:
        try:
            ctx = load_context(mode="lean")
            results["steps"].append({"step": "load_context", "status": "done"})
        except Exception as e:
            results["steps"].append({"step": "load_context", "error": str(e)})
    
    # Step 2: Check orphan episodes
    list_episodes = tools.get("list_episodes")
    if list_episodes:
        try:
            eps = list_episodes(status="open", limit=10)
            open_count = len(eps) if isinstance(eps, list) else len(eps.get("episodes", []))
            results["steps"].append({"step": "list_episodes", "open": open_count})
        except Exception as e:
            results["steps"].append({"step": "list_episodes", "error": str(e)})
    
    # Step 3: Prime recall
    task = args.get("first_task", "")
    if task:
        recall = tools.get("proactive_recall")
        if recall:
            try:
                recall(context=task, limit=5)
                results["steps"].append({"step": "proactive_recall", "status": "done"})
            except Exception as e:
                results["steps"].append({"step": "proactive_recall", "error": str(e)})
    
    results["report"] = "Session start complete: " + ", ".join(s["step"] for s in results["steps"])
    return results
