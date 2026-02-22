"""
Provenance Signing Module
=========================

Cryptographic signing and verification of artifact provenance.

This module provides tamper detection for artifacts stored on disk.
If someone edits a JSON file directly, the signature will fail verification.

Environment:
    DURO_PROVENANCE_HMAC_KEYS: Required. Format: "key_id:hex_key" or "v2:hex,v1:hex"
                               First key is active signer, all keys can verify.
                               Keys must be at least 32 bytes (64 hex chars).

Example:
    export DURO_PROVENANCE_HMAC_KEYS="v1:$(openssl rand -hex 32)"

Phase 1 scope:
    - Detect tampering at rest (edited JSON files)
    - Does NOT prevent malicious creation (that's Phase 2)

Usage:
    from provenance_signing import sign_artifact, verify_artifact

    # On creation
    artifact = build_artifact(...)
    artifact = sign_artifact(artifact)
    write_json(artifact)

    # On load
    artifact = read_json(...)
    artifact["signature_status"] = verify_artifact(artifact)
    if artifact["signature_status"] == "invalid":
        log_security_event(...)
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from copy import deepcopy
from enum import Enum
from functools import lru_cache
from typing import Any


class TrustTier(str, Enum):
    """
    Trust tiers for artifact provenance.

    Lower = more trusted. Phase 2 will enforce these based on caller identity.
    For Phase 1, these are just recorded (still caller-provided).
    """
    HUMAN_VERIFIED = "human_verified"    # Explicit user input, human-validated
    SYSTEM_INTERNAL = "system_internal"  # Orchestrator, policy gate, internal code
    AUTO_CAPTURED = "auto_captured"      # Extracted from conversations
    EXTERNAL = "external"                # Web, tool output, unknown


class SignatureStatus(str, Enum):
    """Computed signature verification status."""
    UNSIGNED = "unsigned"      # No signature present
    VALID = "valid"            # Signature verified successfully
    INVALID = "invalid"        # Signature mismatch (tampered!)
    UNKNOWN_KEY = "unknown_key"  # Key ID not in current key set


# =============================================================================
# Key Management
# =============================================================================

@lru_cache(maxsize=1)
def _get_keys() -> tuple[str, dict[str, bytes]]:
    """
    Parse and cache HMAC keys from environment.

    Returns:
        Tuple of (active_key_id, {key_id: key_bytes})

    Raises:
        RuntimeError: If DURO_PROVENANCE_HMAC_KEYS not set
        ValueError: If key format is invalid or key too short
    """
    raw = os.environ.get("DURO_PROVENANCE_HMAC_KEYS", "").strip()
    if not raw:
        raise RuntimeError(
            "DURO_PROVENANCE_HMAC_KEYS not set. "
            "Generate with: export DURO_PROVENANCE_HMAC_KEYS=\"v1:$(openssl rand -hex 32)\""
        )

    key_map: dict[str, bytes] = {}
    active_id: str | None = None

    for part in (p.strip() for p in raw.split(",") if p.strip()):
        if ":" not in part:
            raise ValueError(
                f"Bad DURO_PROVENANCE_HMAC_KEYS entry: '{part}'. "
                "Expected format: key_id:hex_key"
            )
        kid, hexkey = part.split(":", 1)
        kid = kid.strip()
        hexkey = hexkey.strip()

        try:
            key_bytes = bytes.fromhex(hexkey)
        except ValueError as e:
            raise ValueError(f"Key {kid} has invalid hex: {e}") from e

        if len(key_bytes) < 32:
            raise ValueError(
                f"Key {kid} too short ({len(key_bytes)} bytes). "
                "Use at least 32 bytes (64 hex chars)."
            )

        key_map[kid] = key_bytes
        if active_id is None:
            active_id = kid  # First key is the active signer

    if active_id is None:
        raise RuntimeError("No valid keys found in DURO_PROVENANCE_HMAC_KEYS")

    return active_id, key_map


def clear_key_cache() -> None:
    """Clear cached keys. Use after changing DURO_PROVENANCE_HMAC_KEYS in tests."""
    _get_keys.cache_clear()


def is_signing_available() -> bool:
    """Check if signing is available (keys are configured)."""
    try:
        _get_keys()
        return True
    except (RuntimeError, ValueError):
        return False


# =============================================================================
# Canonical Serialization
# =============================================================================

def _canonical_json(obj: dict) -> bytes:
    """
    Serialize dict to canonical JSON bytes for signing.

    Canonical form:
    - Sorted keys (deterministic ordering)
    - No whitespace (compact)
    - UTF-8 encoding
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False
    ).encode("utf-8")


def _signing_payload(artifact: dict) -> dict:
    """
    Extract the payload to be signed from an artifact.

    CRITICAL: Must exclude:
    - provenance.signature (can't sign a value that includes itself)
    - signature_status (computed on load, not stored)
    """
    payload = deepcopy(artifact)

    # Remove signature from provenance block
    if "provenance" in payload and isinstance(payload["provenance"], dict):
        payload["provenance"].pop("signature", None)

    # Remove computed status
    payload.pop("signature_status", None)

    return payload


# =============================================================================
# Signing
# =============================================================================

def sign_artifact(artifact: dict) -> dict:
    """
    Sign an artifact dict with HMAC-SHA256.

    Modifies artifact in place, adding:
    - provenance.signature.key_id
    - provenance.signature.alg
    - provenance.signature.mac_hex
    - signature_status = "valid"

    Args:
        artifact: The artifact dict to sign

    Returns:
        The same artifact dict with signature added

    Raises:
        RuntimeError: If signing keys not configured
    """
    active_id, keys = _get_keys()
    key = keys[active_id]

    # Build signing payload (excludes signature fields)
    payload = _signing_payload(artifact)

    # Compute HMAC
    mac = hmac.new(key, _canonical_json(payload), hashlib.sha256).hexdigest()

    # Add signature to artifact
    artifact.setdefault("provenance", {})
    artifact["provenance"]["signature"] = {
        "key_id": active_id,
        "alg": "hmac-sha256",
        "mac_hex": mac,
    }
    artifact["signature_status"] = SignatureStatus.VALID.value

    return artifact


# =============================================================================
# Verification
# =============================================================================

def verify_artifact(artifact: dict) -> str:
    """
    Verify an artifact's signature.

    Args:
        artifact: The artifact dict to verify

    Returns:
        SignatureStatus value:
        - "unsigned": No signature present
        - "valid": Signature matches
        - "invalid": Signature mismatch (TAMPERED!)
        - "unknown_key": Key ID not in current key set
    """
    # Check for signature
    provenance = artifact.get("provenance")
    if not provenance or not isinstance(provenance, dict):
        return SignatureStatus.UNSIGNED.value

    sig = provenance.get("signature")
    if not sig or not isinstance(sig, dict):
        return SignatureStatus.UNSIGNED.value

    # Extract signature components
    key_id = sig.get("key_id")
    mac_hex = sig.get("mac_hex")

    if not key_id or not mac_hex:
        return SignatureStatus.INVALID.value

    # Get key
    try:
        _, keys = _get_keys()
    except (RuntimeError, ValueError):
        # Keys not configured - can't verify
        return SignatureStatus.UNKNOWN_KEY.value

    key = keys.get(key_id)
    if not key:
        return SignatureStatus.UNKNOWN_KEY.value

    # Compute expected MAC
    payload = _signing_payload(artifact)
    expected = hmac.new(key, _canonical_json(payload), hashlib.sha256).hexdigest()

    # Constant-time comparison
    if hmac.compare_digest(expected, mac_hex):
        return SignatureStatus.VALID.value
    else:
        return SignatureStatus.INVALID.value


# =============================================================================
# Provenance Block Helpers
# =============================================================================

def create_provenance_block(
    workflow: str = "unknown",
    created_by: str = "mcp",
    created_via: str = "unknown",
    trust_tier: TrustTier = TrustTier.EXTERNAL,
) -> dict:
    """
    Create a new provenance block for an artifact.

    Phase 1: These are still caller-provided.
    Phase 2: Server will enforce based on caller identity.

    Args:
        workflow: Source workflow name
        created_by: Actor identity (Phase 1: just "mcp")
        created_via: Tool/channel name
        trust_tier: Trust tier (Phase 1: caller-provided)

    Returns:
        Provenance block dict (without signature - call sign_artifact after)
    """
    return {
        "trust_tier": trust_tier.value if isinstance(trust_tier, TrustTier) else trust_tier,
        "workflow": workflow,
        "created_by": created_by,
        "created_via": created_via,
        "validators": [],  # Phase 4: list of validation event IDs
        # signature will be added by sign_artifact()
    }


def stamp_provenance(
    artifact: dict,
    workflow: str,
    created_via: str,
    trust_tier: TrustTier = TrustTier.EXTERNAL,
) -> dict:
    """
    Stamp provenance on an artifact and sign it.

    Convenience function combining create_provenance_block + sign_artifact.

    Args:
        artifact: Artifact dict to stamp
        workflow: Source workflow name
        created_via: Tool/channel name
        trust_tier: Trust tier

    Returns:
        Artifact with provenance block and signature
    """
    artifact["provenance"] = create_provenance_block(
        workflow=workflow,
        created_by="mcp",  # Phase 2 will make this real
        created_via=created_via,
        trust_tier=trust_tier,
    )
    return sign_artifact(artifact)
