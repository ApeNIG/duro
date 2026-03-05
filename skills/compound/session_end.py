"""
Skill: session_end
Description: Compound session close - captures episode, saves learnings, graduates logs
Version: 1.0.0
Tier: tested
"""

SKILL_META = {
    "name": "session_end",
    "description": "Compound session close - captures episode, saves learnings, graduates logs",
    "tier": "tested",
    "version": "1.0.0",
    "triggers": ["session end", "end session", "learn and log", "wrapping up", "1"],
    "keywords": ["session", "end", "episode", "learning", "log", "compound"],
}

REQUIRES = ["suggest_episode", "create_episode", "close_episode", "save_learning", "log_task"]

def run(args, tools, context):
    results = {"success": True, "steps": [], "actions": []}
    
    goal = args.get("goal", "Session work")
    learnings = args.get("learnings", [])
    tasks = args.get("tasks", [])
    
    # Step 1: Check if episode-worthy
    suggest = tools.get("suggest_episode")
    if suggest:
        try:
            suggestion = suggest(
                tools_used=args.get("tools_used", True),
                artifacts_produced=args.get("artifacts_produced", False),
                goal_summary=goal
            )
            should_create = suggestion.get("suggested", True)
            results["steps"].append({"step": "suggest_episode", "suggested": should_create})
        except:
            should_create = True
    else:
        should_create = True
    
    # Step 2: Create and close episode
    if should_create and args.get("create_episode", True):
        create_ep = tools.get("create_episode")
        close_ep = tools.get("close_episode")
        if create_ep and close_ep:
            try:
                ep = create_ep(goal=goal, tags=["auto-session"])
                ep_id = ep.get("id", "")
                if ep_id:
                    close_ep(
                        episode_id=ep_id,
                        result=args.get("result", "success"),
                        result_summary=args.get("summary", "Session completed")
                    )
                    results["steps"].append({"step": "episode", "id": ep_id, "status": "closed"})
                    results["episode_id"] = ep_id
            except Exception as e:
                results["steps"].append({"step": "episode", "error": str(e)})
    
    # Step 3: Save learnings
    save_learning = tools.get("save_learning")
    if save_learning and learnings:
        for learning in learnings:
            try:
                save_learning(learning=learning, category="Session")
                results["actions"].append(f"Saved learning: {learning[:40]}...")
            except:
                pass
    
    # Step 4: Log tasks
    log_task = tools.get("log_task")
    if log_task and tasks:
        for t in tasks:
            try:
                log_task(task=t.get("task", ""), outcome=t.get("outcome", ""))
                results["actions"].append(f"Logged task: {t.get('task', '')[:40]}...")
            except:
                pass
    
    results["report"] = f"Session end: {len(results['steps'])} steps, {len(results['actions'])} actions"
    return results
