"""
Invariant tests for the Autonomy Ladder control plane.

These tests verify that critical safety invariants hold:
1. Approval tokens are one-shot (cannot be consumed twice)
2. Approval log is append-only (no deletions)
3. Pending rewards must mature or cancel (no direct jump to score)
4. Reputation score stays within bounds [0, 1]
5. Token cannot be used after expiry
"""

import sys
import pytest
import tempfile
import os
from pathlib import Path
from datetime import datetime, timedelta

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent / "lib"))

from autonomy_ladder import (
    AutonomyLevel,
    ActionRisk,
    ReputationStore,
    DomainScore,
    ApprovalToken,
    PendingReward,
    AutonomyEnforcer,
    check_action,
    record_outcome,
    handle_reopen_event,
    run_maturation,
    get_autonomy_enforcer,
    get_reputation_store,
    REWARD_MATURATION_DAYS,
)


# === FIXTURES ===

@pytest.fixture
def temp_store_path():
    """Create a temporary path for store persistence."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def fresh_store(temp_store_path):
    """Create a fresh ReputationStore for testing."""
    return ReputationStore(store_path=temp_store_path)


@pytest.fixture
def fresh_enforcer(fresh_store):
    """Create a fresh AutonomyEnforcer for testing."""
    return AutonomyEnforcer(store=fresh_store)


# === INVARIANT 1: Approval tokens are one-shot ===

class TestApprovalTokenOneShot:
    """Verify that approval tokens can only be consumed once."""

    def test_token_consumed_once(self, fresh_enforcer):
        """Token should only be usable once."""
        # Grant approval (doesn't return token)
        fresh_enforcer.grant_approval("test_action_1", reason="test")
        token = fresh_enforcer.approval_tokens.get("test_action_1")
        assert token is not None
        assert token.is_valid

        # First use should succeed
        result = fresh_enforcer.use_approval("test_action_1", used_by="test_run_1")
        assert result is True

        # Second use should fail
        result = fresh_enforcer.use_approval("test_action_1", used_by="test_run_2")
        assert result is False

    def test_token_shows_used_state(self, fresh_enforcer):
        """After use, token should show used state."""
        fresh_enforcer.grant_approval("test_action_2")
        token = fresh_enforcer.approval_tokens.get("test_action_2")
        assert token.used_at is None
        assert token.used_by is None

        fresh_enforcer.use_approval("test_action_2", used_by="test_run")

        # Check token state directly
        assert token.used_at is not None
        assert token.used_by == "test_run"
        assert not token.is_valid

    def test_token_invalid_after_use(self, fresh_enforcer):
        """Token.is_valid should be False after use."""
        fresh_enforcer.grant_approval("test_action_3")
        token = fresh_enforcer.approval_tokens.get("test_action_3")
        assert token.is_valid

        fresh_enforcer.use_approval("test_action_3", used_by="test")

        assert not token.is_valid


# === INVARIANT 2: Approval log is append-only ===

class TestApprovalLogAppendOnly:
    """Verify that the approval log never shrinks."""

    def test_log_grows_monotonically(self, fresh_enforcer):
        """Approval log should only grow, never shrink (grants + uses both append)."""
        initial_count = len(fresh_enforcer.approval_log)

        # Grant several approvals (each grant adds 1 entry)
        for i in range(5):
            fresh_enforcer.grant_approval(f"action_{i}", reason=f"test {i}")

        grant_count = len(fresh_enforcer.approval_log)
        assert grant_count == initial_count + 5

        # Using approvals ALSO adds to log (use events)
        for i in range(5):
            fresh_enforcer.use_approval(f"action_{i}", used_by="test")

        # Log should have grown by 5 more (use events)
        assert len(fresh_enforcer.approval_log) == grant_count + 5

    def test_no_delete_method_on_log(self, fresh_enforcer):
        """Verify there's no public method to delete from approval log."""
        # The enforcer should not have delete exposure
        assert not hasattr(fresh_enforcer, 'delete_approval')
        assert not hasattr(fresh_enforcer, 'remove_approval')
        assert not hasattr(fresh_enforcer, 'clear_approvals')

    def test_log_survives_permission_checks(self, fresh_enforcer):
        """Permission checks should not affect log size."""
        # Grant an approval
        fresh_enforcer.grant_approval("check_test", reason="test")
        count_after_grant = len(fresh_enforcer.approval_log)

        # Do permission checks (should not consume unless requested)
        for _ in range(10):
            fresh_enforcer.check_permission(
                ActionRisk.DESTRUCTIVE,
                "test_domain",
                "check_test",
                consume_token=False
            )

        assert len(fresh_enforcer.approval_log) == count_after_grant


# === INVARIANT 3: Pending rewards must mature or cancel ===

class TestPendingRewardLifecycle:
    """Verify that pending rewards follow proper lifecycle."""

    def test_success_creates_pending_not_immediate(self, fresh_store):
        """Recording success should create pending reward, not immediate score change."""
        initial_score = fresh_store.get_domain_score("test_domain").score

        # Record provisional success
        pending = fresh_store.record_provisional_success(
            action_id="test_success_1",
            domain="test_domain",
            confidence=0.8
        )

        assert pending is not None
        assert not pending.matured
        assert not pending.cancelled

        # Score should NOT have changed yet
        current_score = fresh_store.get_domain_score("test_domain").score
        assert current_score == initial_score

    def test_pending_must_mature_to_affect_score(self, fresh_store):
        """Pending rewards only affect score after maturation."""
        # Get a fresh domain score (start at 0.5)
        initial_score = fresh_store.get_domain_score("mature_domain").score

        # Create pending reward
        pending = fresh_store.record_provisional_success(
            action_id="mature_test",
            domain="mature_domain",
            confidence=0.8
        )

        # Score should NOT have changed yet
        mid_score = fresh_store.get_domain_score("mature_domain").score
        assert mid_score == initial_score

        # Manually set mature_at to past to simulate time passing
        fresh_store.pending_rewards[-1].mature_at = (
            datetime.now() - timedelta(days=1)
        ).isoformat()

        # Run maturation
        result = fresh_store.mature_pending_rewards()

        # Now score should have changed
        current_score = fresh_store.get_domain_score("mature_domain").score
        assert current_score > initial_score
        # result["matured"] is a list, check count
        assert result["matured_count"] > 0

    def test_cancelled_rewards_never_apply(self, fresh_store):
        """Cancelled rewards should never affect score."""
        # Get a fresh domain
        initial_score = fresh_store.get_domain_score("cancel_domain").score

        # Create pending reward
        fresh_store.record_provisional_success(
            action_id="cancel_test",
            domain="cancel_domain",
            confidence=0.8
        )

        # Cancel BEFORE maturation
        fresh_store.cancel_pending_reward("cancel_test", apply_penalty=False)

        # Set mature_at to past (after cancellation)
        for pr in fresh_store.pending_rewards:
            if pr.action_id == "cancel_test":
                pr.mature_at = (datetime.now() - timedelta(days=1)).isoformat()

        # Run maturation - cancelled rewards should not mature
        result = fresh_store.mature_pending_rewards()

        # Cancelled rewards don't count as matured
        assert result["matured_count"] == 0

    def test_cancel_with_penalty_decreases_score(self, fresh_store):
        """Cancelling with penalty should decrease score."""
        # Bump the score first
        fresh_store.update_score("test_domain", "successful_closure", 0.8)
        initial_score = fresh_store.get_domain_score("test_domain").score

        # Create and cancel with penalty
        fresh_store.record_provisional_success(
            action_id="penalty_test",
            domain="test_domain",
            confidence=0.8
        )

        fresh_store.cancel_pending_reward("penalty_test", apply_penalty=True)

        current_score = fresh_store.get_domain_score("test_domain").score
        assert current_score < initial_score


# === INVARIANT 4: Reputation score stays bounded ===

class TestScoreBounds:
    """Verify that reputation scores stay within [0, 1]."""

    def test_score_never_exceeds_one(self, fresh_store):
        """Score should never go above 1.0."""
        # Try to inflate score with many successes
        for i in range(100):
            fresh_store.update_score("test_domain", "successful_closure", 0.9)

        score = fresh_store.get_domain_score("test_domain").score
        assert score <= 1.0

    def test_score_never_below_zero(self, fresh_store):
        """Score should never go below 0.0."""
        # Try to deflate score with many failures
        for i in range(100):
            fresh_store.update_score("test_domain", "confident_revert", 0.9)

        score = fresh_store.get_domain_score("test_domain").score
        assert score >= 0.0

    def test_global_score_bounded(self, fresh_store):
        """Global score should stay bounded."""
        # Many updates
        for domain in ["a", "b", "c", "d", "e"]:
            for _ in range(50):
                fresh_store.update_score(domain, "confident_revert", 0.9)

        assert 0.0 <= fresh_store.global_score <= 1.0


# === INVARIANT 5: Token expiry is enforced ===

class TestTokenExpiry:
    """Verify that expired tokens cannot be used."""

    def test_expired_token_is_invalid(self, fresh_enforcer):
        """Expired token should not be valid."""
        # Create token with immediate expiry (0 seconds)
        fresh_enforcer.grant_approval(
            "expire_test",
            duration_seconds=0  # Immediate expiry
        )
        token = fresh_enforcer.approval_tokens.get("expire_test")

        # Token should be expired (is_valid checks expiry)
        assert not token.is_valid

    def test_expired_token_cannot_be_used(self, fresh_enforcer):
        """Attempting to use expired token should fail."""
        # Create a token that's already expired
        token = ApprovalToken(
            action_id="expired_action",
            granted_at=datetime.now().isoformat(),
            expires_at=datetime.now() - timedelta(hours=1)  # Already expired
        )
        # Put it in the tokens dict (not approval_log which is a list)
        fresh_enforcer.approval_tokens["expired_action"] = token

        # Use should fail because token is expired
        result = fresh_enforcer.use_approval("expired_action", used_by="test")
        assert result is False


# === INVARIANT 6: Action classification is deterministic ===

class TestActionClassificationDeterminism:
    """Verify that action classification is deterministic."""

    def test_same_action_same_risk(self):
        """Same action should always get same risk level."""
        action = "delete_file"
        risks = [ActionRisk.from_action(action) for _ in range(100)]
        assert all(r == risks[0] for r in risks)

    def test_destructive_patterns_are_destructive(self):
        """Destructive action patterns should be classified as DESTRUCTIVE."""
        destructive_actions = [
            "delete_file",
            "remove_artifact",
            "drop_table",
            "destroy_resource",
            "force_push",
            "bash_command",
            "deploy_prod",
        ]

        for action in destructive_actions:
            risk = ActionRisk.from_action(action)
            assert risk == ActionRisk.DESTRUCTIVE, f"{action} should be DESTRUCTIVE"

    def test_read_patterns_are_read(self):
        """Read action patterns should be classified as READ."""
        read_actions = [
            "read_file",
            "get_artifact",
            "fetch_data",
            "query_database",
            "list_items",
            "search_code",
        ]

        for action in read_actions:
            risk = ActionRisk.from_action(action)
            assert risk == ActionRisk.READ, f"{action} should be READ"


# === INVARIANT 7: Persistence round-trip integrity ===

class TestPersistenceIntegrity:
    """Verify that save/load preserves all data."""

    def test_pending_rewards_persist(self, temp_store_path):
        """Pending rewards should survive save/load cycle."""
        store1 = ReputationStore(store_path=temp_store_path)

        # Add pending rewards
        store1.record_provisional_success("persist_1", "domain_a", 0.8)
        store1.record_provisional_success("persist_2", "domain_b", 0.7)

        # Save
        store1.save()

        # Load in new store
        store2 = ReputationStore.load(temp_store_path)

        assert len(store2.pending_rewards) == 2
        assert store2.pending_rewards[0].action_id == "persist_1"
        assert store2.pending_rewards[1].action_id == "persist_2"

    def test_domain_scores_persist(self, temp_store_path):
        """Domain scores should survive save/load cycle."""
        store1 = ReputationStore(store_path=temp_store_path)

        # Update some scores
        store1.update_score("code_changes", "successful_closure", 0.8)
        store1.update_score("decisions", "successful_closure", 0.7)

        # Save
        store1.save()

        # Load in new store
        store2 = ReputationStore.load(temp_store_path)

        assert store2.get_domain_score("code_changes").score > 0.5
        assert store2.get_domain_score("decisions").score > 0.5


# === INVARIANT 8: Reopen events cancel pending rewards ===

class TestReopenCancellation:
    """Verify that reopen events properly cancel pending rewards."""

    def test_reopen_cancels_linked_reward(self, fresh_store):
        """Reopen event should cancel the linked pending reward."""
        # Create pending reward
        fresh_store.record_provisional_success(
            action_id="close_decision_123",
            domain="decisions",
            confidence=0.8
        )

        assert len([p for p in fresh_store.pending_rewards if not p.cancelled]) == 1

        # Handle reopen
        result = handle_reopen_event(
            artifact_type="decision",
            artifact_id="decision_123",
            linked_action_id="close_decision_123",
            store=fresh_store
        )

        assert result["cancelled"] is True

        # Reward should be cancelled
        pending = [p for p in fresh_store.pending_rewards if not p.cancelled]
        assert len(pending) == 0


# === INVARIANT 9: Maturation heartbeat processes pending rewards ===

class TestMaturationHeartbeat:
    """Verify that maturation is called and processes rewards."""

    def test_run_maturation_processes_ready_rewards(self, fresh_store):
        """run_maturation should process rewards past their maturation date."""
        # Create a pending reward
        fresh_store.record_provisional_success(
            action_id="heartbeat_test",
            domain="heartbeat_domain",
            confidence=0.8
        )

        # Manually set mature_at to past
        fresh_store.pending_rewards[-1].mature_at = (
            datetime.now() - timedelta(days=1)
        ).isoformat()

        initial_score = fresh_store.get_domain_score("heartbeat_domain").score

        # Run maturation (the heartbeat)
        result = run_maturation(fresh_store)

        # Should have processed the reward
        assert result["matured_count"] == 1

        # Score should have increased
        final_score = fresh_store.get_domain_score("heartbeat_domain").score
        assert final_score > initial_score

    def test_run_maturation_idempotent(self, fresh_store):
        """Calling run_maturation multiple times should be safe."""
        # Create a pending reward
        fresh_store.record_provisional_success(
            action_id="idempotent_test",
            domain="idempotent_domain",
            confidence=0.8
        )

        # Set to past maturation
        fresh_store.pending_rewards[-1].mature_at = (
            datetime.now() - timedelta(days=1)
        ).isoformat()

        # Run maturation twice
        result1 = run_maturation(fresh_store)
        result2 = run_maturation(fresh_store)

        # First run should mature, second should find nothing
        assert result1["matured_count"] == 1
        assert result2["matured_count"] == 0

    def test_run_maturation_skips_future_rewards(self, fresh_store):
        """Pending rewards not yet mature should be skipped."""
        # Create a pending reward (future maturation)
        fresh_store.record_provisional_success(
            action_id="future_test",
            domain="future_domain",
            confidence=0.8
        )
        # Default maturation is 7 days in future - no change needed

        # Run maturation
        result = run_maturation(fresh_store)

        # Should not have processed anything
        assert result["matured_count"] == 0
        assert result["still_pending"] == 1


# === INVARIANT 10: Artifact linkage enables deterministic matching ===

class TestArtifactLinkage:
    """Verify that artifact linkage enables deterministic reopen matching."""

    def test_pending_reward_stores_artifact_linkage(self, fresh_store):
        """Pending rewards should store artifact_type and artifact_id."""
        reward = fresh_store.record_provisional_success(
            action_id="close_decision_456",
            domain="decisions",
            confidence=0.8,
            artifact_type="decision",
            artifact_id="decision_456"
        )

        assert reward.artifact_type == "decision"
        assert reward.artifact_id == "decision_456"

    def test_reopen_matches_by_artifact_linkage(self, fresh_store):
        """Reopen should match by artifact_type + artifact_id (deterministic)."""
        # Create reward WITH artifact linkage
        fresh_store.record_provisional_success(
            action_id="close_decision_789",
            domain="decisions",
            confidence=0.8,
            artifact_type="decision",
            artifact_id="decision_789"
        )

        # Reopen using artifact linkage (no linked_action_id needed)
        result = handle_reopen_event(
            artifact_type="decision",
            artifact_id="decision_789",
            store=fresh_store
        )

        assert result["cancelled"] is True
        assert result["match_method"] == "artifact_linkage"

    def test_artifact_linkage_preferred_over_action_id(self, fresh_store):
        """Artifact linkage should be preferred over action_id matching."""
        # Create reward with both linkage AND action_id
        fresh_store.record_provisional_success(
            action_id="action_abc",
            domain="decisions",
            confidence=0.8,
            artifact_type="decision",
            artifact_id="decision_abc"
        )

        # Create another reward with same action_id but different artifact
        fresh_store.record_provisional_success(
            action_id="action_abc",  # Same action_id!
            domain="decisions",
            confidence=0.7,
            artifact_type="decision",
            artifact_id="decision_xyz"  # Different artifact
        )

        # Reopen using artifact linkage - should match exact artifact
        result = handle_reopen_event(
            artifact_type="decision",
            artifact_id="decision_abc",
            linked_action_id="action_abc",  # Provided but should not be used
            store=fresh_store
        )

        assert result["cancelled"] is True
        assert result["match_method"] == "artifact_linkage"

        # Only one should be cancelled (the one with matching artifact_id)
        cancelled_count = sum(1 for r in fresh_store.pending_rewards if r.cancelled)
        assert cancelled_count == 1

        # The correct one (decision_abc) should be cancelled
        for r in fresh_store.pending_rewards:
            if r.artifact_id == "decision_abc":
                assert r.cancelled is True
            elif r.artifact_id == "decision_xyz":
                assert r.cancelled is False

    def test_artifact_linkage_persists(self, temp_store_path):
        """Artifact linkage should survive save/load cycle."""
        store1 = ReputationStore(store_path=temp_store_path)

        store1.record_provisional_success(
            action_id="persist_linkage",
            domain="decisions",
            confidence=0.8,
            artifact_type="incident",
            artifact_id="incident_999"
        )

        store1.save()

        # Load in new store
        store2 = ReputationStore.load(temp_store_path)

        assert len(store2.pending_rewards) == 1
        assert store2.pending_rewards[0].artifact_type == "incident"
        assert store2.pending_rewards[0].artifact_id == "incident_999"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
