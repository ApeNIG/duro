"""
Skill: verify_and_store_fact
Compound skill that verifies claims via web search before storing as facts.

Interface:
- SKILL_META: metadata about this skill
- REQUIRES: list of required capabilities
- run(args, tools, context) -> dict: main execution function

This skill enforces truth hygiene by:
1. Searching the web for sources
2. Reading top pages for evidence
3. Determining evidence quality
4. Storing with proper attribution

Timeout handling:
- Default timeout: 30 seconds
- Graceful degradation: stores with reduced confidence if verification times out
"""

import time
from typing import Dict, List, Optional, Any


# Skill metadata
SKILL_META = {
    "name": "verify_and_store_fact",
    "description": "Verifies claims via web search before storing as facts",
    "tier": "core",
    "version": "2.1.0",
    "author": "duro",
}

# Default timeout in seconds
DEFAULT_TIMEOUT = 30

# Required capabilities - orchestrator checks these before execution
REQUIRES = ["search", "read", "store_fact"]


# Confidence calculation based on evidence quality
CONFIDENCE_FACTORS = {
    "source_count": {0: 0.0, 1: 0.6, 2: 0.75, 3: 0.85},
    "evidence_type_modifier": {
        "quote": 0.15,
        "paraphrase": 0.10,
        "inference": 0.0,
        "none": -0.2
    },
    "source_quality": {
        "official_docs": 0.10,
        "reputable_news": 0.05,
        "forum_wiki": 0.0,
        "unknown": -0.05
    }
}


def calculate_confidence(
    sources_found: int,
    evidence_type: str,
    source_quality: str = "unknown"
) -> float:
    """Calculate confidence score based on evidence quality."""
    if sources_found >= 3:
        base = 0.85
    else:
        base = CONFIDENCE_FACTORS["source_count"].get(sources_found, 0.0)

    evidence_mod = CONFIDENCE_FACTORS["evidence_type_modifier"].get(evidence_type, 0.0)
    quality_mod = CONFIDENCE_FACTORS["source_quality"].get(source_quality, 0.0)

    confidence = min(0.95, max(0.0, base + evidence_mod + quality_mod))
    return round(confidence, 2)


def determine_evidence_type(snippet: Optional[str], claim: str) -> str:
    """Determine evidence type based on snippet relationship to claim."""
    if not snippet:
        return "none"

    snippet_lower = snippet.lower()
    claim_lower = claim.lower()

    # Check for direct quote indicators
    if any(phrase in snippet_lower for phrase in ['"', 'said', 'stated', 'announced']):
        return "quote"

    # Check for word overlap (rough paraphrase detection)
    claim_words = set(claim_lower.split())
    snippet_words = set(snippet_lower.split())
    overlap = len(claim_words & snippet_words) / max(len(claim_words), 1)

    if overlap > 0.5:
        return "paraphrase"
    elif overlap > 0.2:
        return "inference"
    else:
        return "inference"


def classify_source_quality(url: str) -> str:
    """Classify source quality based on domain."""
    url_lower = url.lower()

    official_indicators = [
        'docs.', 'documentation', 'developer.', 'api.',
        'github.com', 'anthropic.com', 'openai.com',
        '.gov', '.edu'
    ]
    reputable_indicators = [
        'techcrunch', 'wired', 'theverge', 'arstechnica',
        'bbc.', 'nytimes', 'reuters', 'bloomberg'
    ]
    low_quality_indicators = [
        'reddit.com', 'quora.com', 'medium.com',
        'stackoverflow.com', 'wikipedia.org'
    ]

    if any(ind in url_lower for ind in official_indicators):
        return "official_docs"
    elif any(ind in url_lower for ind in reputable_indicators):
        return "reputable_news"
    elif any(ind in url_lower for ind in low_quality_indicators):
        return "forum_wiki"
    return "unknown"


def extract_best_snippet(content: str, claim: str, max_length: int = 500) -> Optional[str]:
    """Extract the most relevant snippet from page content."""
    if not content:
        return None

    # Simple approach: find sentences with most claim word overlap
    claim_words = set(claim.lower().split())

    # Split into sentences (rough)
    sentences = content.replace('\n', ' ').split('.')

    best_sentence = None
    best_overlap = 0

    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 20 or len(sentence) > max_length:
            continue

        sentence_words = set(sentence.lower().split())
        overlap = len(claim_words & sentence_words)

        if overlap > best_overlap:
            best_overlap = overlap
            best_sentence = sentence

    return best_sentence + "." if best_sentence else None


def run(args: Dict[str, Any], tools: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main skill execution function.

    Args:
        args: {claim, confidence (optional), tags, sensitivity}
        tools: {search, read, store_fact, log}
        context: {run_id, constraints, max_sources, max_pages, timeout}

    Returns:
        {success, artifact_id, sources_found, confidence, evidence_type, error}
    """
    start_time = time.time()
    timeout = context.get("timeout", DEFAULT_TIMEOUT)

    def check_timeout(phase: str) -> bool:
        """Check if we've exceeded timeout. Returns True if timed out."""
        elapsed = time.time() - start_time
        return elapsed >= timeout

    def time_remaining() -> float:
        """Return seconds remaining before timeout."""
        return max(0, timeout - (time.time() - start_time))

    claim = args.get("claim", "")
    if not claim or len(claim.strip()) < 10:
        return {"success": False, "error": "Claim must be at least 10 characters"}

    requested_confidence = args.get("confidence", 0.9)
    tags = args.get("tags") or []
    sensitivity = args.get("sensitivity", "public")

    # Limits from context
    max_sources = context.get("max_sources", 3)
    max_pages = context.get("max_pages", 2)
    run_id = context.get("run_id", "unknown")

    # Track state for graceful degradation
    source_urls = []
    snippets = []
    best_quality = "unknown"
    search_completed = False
    timed_out = False

    # Step 1: Search for sources
    if not check_timeout("search"):
        try:
            search_result = tools["search"](claim, max_results=max_sources)
            search_completed = True

            if search_result.get("error"):
                # Search failed - store with low confidence
                return _store_unverified(
                    tools, claim, requested_confidence, tags, sensitivity, run_id,
                    reason=f"Search failed: {search_result['error']}"
                )

            results = search_result.get("results", [])
        except Exception as e:
            return _store_unverified(
                tools, claim, requested_confidence, tags, sensitivity, run_id,
                reason=f"Search exception: {str(e)}"
            )
    else:
        timed_out = True
        results = []

    # Step 2: Read top pages and extract evidence (with timeout checks)
    if not timed_out and results:
        for i, result in enumerate(results[:max_pages]):
            if check_timeout("read"):
                timed_out = True
                break

            url = result.get("url") or result.get("link", "")
            if not url:
                continue

            try:
                page_result = tools["read"](url)

                if page_result.get("error"):
                    continue

                content = page_result.get("content", "")
                if not content:
                    continue

                # Extract snippet
                snippet = extract_best_snippet(content, claim)
                if snippet:
                    snippets.append(snippet)
                    source_urls.append(url)

                    # Track best quality source
                    quality = classify_source_quality(url)
                    if quality in ["official_docs", "reputable_news"]:
                        best_quality = quality
            except Exception:
                # Skip this URL on error, continue with others
                continue

    sources_found = len(source_urls)

    # Step 3: Determine evidence type and confidence
    best_snippet = snippets[0] if snippets else None
    evidence_type = determine_evidence_type(best_snippet, claim)

    calculated_confidence = calculate_confidence(
        sources_found=sources_found,
        evidence_type=evidence_type,
        source_quality=best_quality
    )

    # Use the lower of requested and calculated confidence
    final_confidence = min(requested_confidence, calculated_confidence)

    # If timed out during verification, cap confidence
    if timed_out:
        final_confidence = min(final_confidence, 0.4)
        if not source_urls:
            evidence_type = "none"
    # If no sources but search worked, cap at 0.5
    elif sources_found == 0:
        final_confidence = min(final_confidence, 0.5)
        evidence_type = "none"

    # Step 4: Store the fact
    if check_timeout("store"):
        return {
            "success": False,
            "error": "Timeout before storing fact",
            "sources_found": sources_found,
            "timed_out": True
        }

    store_result = tools["store_fact"](
        claim=claim,
        source_urls=source_urls if source_urls else None,
        snippet=best_snippet,
        confidence=final_confidence,
        evidence_type=evidence_type,
        provenance="web" if source_urls else "user",
        tags=tags + (["partial_verification"] if timed_out else []),
        sensitivity=sensitivity,
        workflow=f"verify_and_store_fact:{run_id}"
    )

    if not store_result.get("success"):
        return {
            "success": False,
            "error": f"Failed to store fact: {store_result.get('path', 'unknown error')}",
            "sources_found": sources_found
        }

    # Success!
    elapsed = time.time() - start_time
    return {
        "success": True,
        "artifact_id": store_result.get("artifact_id"),
        "sources_found": sources_found,
        "source_urls": source_urls,
        "confidence": final_confidence,
        "evidence_type": evidence_type,
        "snippet": best_snippet[:200] if best_snippet else None,
        "timed_out": timed_out,
        "elapsed_seconds": round(elapsed, 2)
    }


def _store_unverified(
    tools: Dict[str, Any],
    claim: str,
    requested_confidence: float,
    tags: list,
    sensitivity: str,
    run_id: str,
    reason: str
) -> Dict[str, Any]:
    """Store fact with low confidence when verification fails."""
    final_confidence = min(requested_confidence, 0.3)

    store_result = tools["store_fact"](
        claim=claim,
        confidence=final_confidence,
        evidence_type="none",
        provenance="user",
        tags=tags + ["unverified"],
        sensitivity=sensitivity,
        workflow=f"verify_and_store_fact:{run_id}"
    )

    if store_result.get("success"):
        return {
            "success": True,
            "artifact_id": store_result.get("artifact_id"),
            "sources_found": 0,
            "confidence": final_confidence,
            "evidence_type": "none",
            "verification_failed": reason
        }
    else:
        return {
            "success": False,
            "error": f"Verification failed ({reason}) and storage failed",
            "sources_found": 0
        }


if __name__ == "__main__":
    # Test/documentation mode
    print("verify_and_store_fact Skill v2.1")
    print("=" * 40)
    print(f"Requires: {REQUIRES}")
    print(f"Default timeout: {DEFAULT_TIMEOUT}s")
    print("\nConfidence calculation examples:")
    print(f"  0 sources, no evidence: {calculate_confidence(0, 'none')}")
    print(f"  1 source, paraphrase: {calculate_confidence(1, 'paraphrase')}")
    print(f"  2 sources, quote: {calculate_confidence(2, 'quote')}")
    print(f"  3 sources, quote, official: {calculate_confidence(3, 'quote', 'official_docs')}")
    print("\nTimeout behavior:")
    print("  - Checks timeout before each network operation")
    print("  - Graceful degradation: stores with reduced confidence if timed out")
    print("  - Tags fact with 'partial_verification' if timed out mid-verification")
