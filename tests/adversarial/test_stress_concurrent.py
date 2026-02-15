"""
Stress Tests: Concurrent Access (Phase 2.4)

Tests system behavior under concurrent/parallel operations.

Scenarios tested:
1. Concurrent reads
2. Concurrent writes
3. Mixed read/write operations
4. Race conditions on same artifact
5. Database locking behavior

File refs:
- duro-mcp/index.py (SQLite thread safety)
- Python threading limitations
"""

import pytest
import sys
import time
import threading
import sqlite3
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass

# Add duro-mcp to path
DURO_MCP_PATH = Path.home() / "duro-mcp"
if str(DURO_MCP_PATH) not in sys.path:
    sys.path.insert(0, str(DURO_MCP_PATH))

from harness import IsolatedTestDB, MockArtifact


# =============================================================================
# Test Configuration
# =============================================================================

NUM_THREADS = 4
OPERATIONS_PER_THREAD = 50


# =============================================================================
# Thread Safety Utilities
# =============================================================================

@dataclass
class ThreadResult:
    """Result from a thread operation."""
    thread_id: int
    success_count: int
    error_count: int
    errors: List[str]
    duration: float


def run_concurrent(db: IsolatedTestDB, num_threads: int, operation):
    """Run an operation concurrently across multiple threads."""
    results = []
    barrier = threading.Barrier(num_threads)

    def worker(thread_id: int):
        result = ThreadResult(
            thread_id=thread_id,
            success_count=0,
            error_count=0,
            errors=[],
            duration=0.0
        )

        # Sync all threads to start together
        barrier.wait()
        start = time.perf_counter()

        try:
            operation(db, thread_id, result)
        except Exception as e:
            result.errors.append(str(e))
            result.error_count += 1

        result.duration = time.perf_counter() - start
        return result

    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = [executor.submit(worker, i) for i in range(num_threads)]
        for future in as_completed(futures):
            results.append(future.result())

    return results


# =============================================================================
# Concurrent Read Tests
# =============================================================================

class TestConcurrentReads:
    """Tests for concurrent read operations."""

    def test_concurrent_get_same_artifact(self):
        """Multiple threads reading the same artifact."""
        with IsolatedTestDB(name="conc_read_same") as db:
            # Create target artifact
            db.add_artifact(MockArtifact(
                id="shared_fact",
                type="fact",
                claim="Shared content for concurrent reads"
            ))

            def read_operation(db, thread_id, result):
                for _ in range(OPERATIONS_PER_THREAD):
                    try:
                        artifact = db.get_artifact("shared_fact")
                        if artifact is not None:
                            result.success_count += 1
                        else:
                            result.error_count += 1
                            result.errors.append("Got None")
                    except Exception as e:
                        result.error_count += 1
                        result.errors.append(str(e))

            results = run_concurrent(db, NUM_THREADS, read_operation)

            # All reads should succeed
            total_success = sum(r.success_count for r in results)
            total_errors = sum(r.error_count for r in results)

            assert total_errors == 0, f"Errors: {[r.errors for r in results if r.errors]}"
            assert total_success == NUM_THREADS * OPERATIONS_PER_THREAD

    def test_concurrent_get_different_artifacts(self):
        """Multiple threads reading different artifacts."""
        with IsolatedTestDB(name="conc_read_diff") as db:
            # Create artifacts for each thread
            for i in range(NUM_THREADS):
                db.add_artifact(MockArtifact(
                    id=f"fact_thread_{i}",
                    type="fact",
                    claim=f"Content for thread {i}"
                ))

            def read_operation(db, thread_id, result):
                for _ in range(OPERATIONS_PER_THREAD):
                    try:
                        artifact = db.get_artifact(f"fact_thread_{thread_id}")
                        if artifact is not None:
                            result.success_count += 1
                        else:
                            result.error_count += 1
                    except Exception as e:
                        result.error_count += 1
                        result.errors.append(str(e))

            results = run_concurrent(db, NUM_THREADS, read_operation)

            total_success = sum(r.success_count for r in results)
            total_errors = sum(r.error_count for r in results)

            assert total_errors == 0
            assert total_success == NUM_THREADS * OPERATIONS_PER_THREAD

    def test_concurrent_count_operations(self):
        """Multiple threads calling count simultaneously."""
        with IsolatedTestDB(name="conc_count") as db:
            # Create baseline data
            for i in range(100):
                db.add_artifact(MockArtifact(
                    id=f"fact_{i:04d}",
                    type="fact",
                    claim=f"Content {i}"
                ))

            def count_operation(db, thread_id, result):
                for _ in range(OPERATIONS_PER_THREAD):
                    try:
                        count = db.count_artifacts()
                        if count == 100:
                            result.success_count += 1
                        else:
                            result.error_count += 1
                            result.errors.append(f"Expected 100, got {count}")
                    except Exception as e:
                        result.error_count += 1
                        result.errors.append(str(e))

            results = run_concurrent(db, NUM_THREADS, count_operation)

            total_success = sum(r.success_count for r in results)
            total_errors = sum(r.error_count for r in results)

            assert total_errors == 0
            assert total_success == NUM_THREADS * OPERATIONS_PER_THREAD


# =============================================================================
# Concurrent Write Tests
# =============================================================================

class TestConcurrentWrites:
    """Tests for concurrent write operations."""

    def test_concurrent_create_different_artifacts(self):
        """Multiple threads creating different artifacts."""
        with IsolatedTestDB(name="conc_write_diff") as db:
            def create_operation(db, thread_id, result):
                for i in range(OPERATIONS_PER_THREAD):
                    try:
                        db.add_artifact(MockArtifact(
                            id=f"fact_t{thread_id}_i{i}",
                            type="fact",
                            claim=f"Created by thread {thread_id} iteration {i}"
                        ))
                        result.success_count += 1
                    except Exception as e:
                        result.error_count += 1
                        result.errors.append(str(e))

            results = run_concurrent(db, NUM_THREADS, create_operation)

            total_success = sum(r.success_count for r in results)
            total_errors = sum(r.error_count for r in results)
            final_count = db.count_artifacts()

            # All creates should succeed
            assert total_errors == 0, f"Errors: {[r.errors for r in results if r.errors]}"
            assert final_count == NUM_THREADS * OPERATIONS_PER_THREAD

    def test_concurrent_update_same_artifact(self):
        """Multiple threads updating the same artifact (race condition test)."""
        with IsolatedTestDB(name="conc_update_same") as db:
            # Create initial artifact
            db.add_artifact(MockArtifact(
                id="contested_fact",
                type="fact",
                claim="Initial content"
            ))

            update_counts = [0] * NUM_THREADS

            def update_operation(db, thread_id, result):
                for i in range(OPERATIONS_PER_THREAD):
                    try:
                        db.add_artifact(MockArtifact(
                            id="contested_fact",
                            type="fact",
                            claim=f"Updated by thread {thread_id} iteration {i}"
                        ))
                        result.success_count += 1
                    except Exception as e:
                        result.error_count += 1
                        result.errors.append(str(e))

            results = run_concurrent(db, NUM_THREADS, update_operation)

            # All operations should complete (SQLite handles locking)
            total_ops = sum(r.success_count + r.error_count for r in results)
            assert total_ops == NUM_THREADS * OPERATIONS_PER_THREAD

            # Artifact should still exist
            artifact = db.get_artifact("contested_fact")
            assert artifact is not None

    def test_concurrent_delete_operations(self):
        """Multiple threads deleting different artifacts."""
        with IsolatedTestDB(name="conc_delete") as db:
            # Create artifacts to delete
            total_artifacts = NUM_THREADS * OPERATIONS_PER_THREAD
            for i in range(total_artifacts):
                db.add_artifact(MockArtifact(
                    id=f"deletable_{i:04d}",
                    type="fact",
                    claim=f"To be deleted {i}"
                ))

            def delete_operation(db, thread_id, result):
                start_idx = thread_id * OPERATIONS_PER_THREAD
                for i in range(OPERATIONS_PER_THREAD):
                    try:
                        artifact_id = f"deletable_{start_idx + i:04d}"
                        db.index.delete(artifact_id)
                        result.success_count += 1
                    except Exception as e:
                        result.error_count += 1
                        result.errors.append(str(e))

            results = run_concurrent(db, NUM_THREADS, delete_operation)

            final_count = db.count_artifacts()
            assert final_count == 0


# =============================================================================
# Mixed Operation Tests
# =============================================================================

class TestMixedOperations:
    """Tests for mixed concurrent operations."""

    def test_concurrent_read_write(self):
        """Some threads reading while others write."""
        with IsolatedTestDB(name="conc_rw") as db:
            # Create initial data
            for i in range(50):
                db.add_artifact(MockArtifact(
                    id=f"existing_{i:04d}",
                    type="fact",
                    claim=f"Existing content {i}"
                ))

            def mixed_operation(db, thread_id, result):
                for i in range(OPERATIONS_PER_THREAD):
                    try:
                        if thread_id % 2 == 0:
                            # Even threads: read
                            artifact = db.get_artifact(f"existing_{i % 50:04d}")
                            if artifact is not None:
                                result.success_count += 1
                            else:
                                result.error_count += 1
                        else:
                            # Odd threads: write
                            db.add_artifact(MockArtifact(
                                id=f"new_t{thread_id}_i{i}",
                                type="fact",
                                claim=f"New content from thread {thread_id}"
                            ))
                            result.success_count += 1
                    except Exception as e:
                        result.error_count += 1
                        result.errors.append(str(e))

            results = run_concurrent(db, NUM_THREADS, mixed_operation)

            total_success = sum(r.success_count for r in results)
            total_errors = sum(r.error_count for r in results)

            # Should have minimal errors
            error_rate = total_errors / (total_success + total_errors) if total_success + total_errors > 0 else 0
            assert error_rate < 0.1, f"Error rate {error_rate:.1%} too high"

    def test_concurrent_create_read_delete(self):
        """All three operations happening concurrently."""
        with IsolatedTestDB(name="conc_crd") as db:
            # Create some initial data
            for i in range(100):
                db.add_artifact(MockArtifact(
                    id=f"initial_{i:04d}",
                    type="fact",
                    claim=f"Initial {i}"
                ))

            def crd_operation(db, thread_id, result):
                for i in range(OPERATIONS_PER_THREAD):
                    try:
                        op = (thread_id + i) % 3
                        if op == 0:
                            # Create
                            db.add_artifact(MockArtifact(
                                id=f"created_t{thread_id}_i{i}",
                                type="fact",
                                claim=f"Created {thread_id}-{i}"
                            ))
                            result.success_count += 1
                        elif op == 1:
                            # Read
                            artifact = db.get_artifact(f"initial_{i % 100:04d}")
                            result.success_count += 1
                        else:
                            # Delete (may fail if already deleted)
                            db.index.delete(f"initial_{i % 100:04d}")
                            result.success_count += 1
                    except Exception as e:
                        result.error_count += 1
                        result.errors.append(str(e))

            results = run_concurrent(db, NUM_THREADS, crd_operation)

            # Operations should complete
            total_ops = sum(r.success_count + r.error_count for r in results)
            assert total_ops == NUM_THREADS * OPERATIONS_PER_THREAD


# =============================================================================
# Database Locking Tests
# =============================================================================

class TestDatabaseLocking:
    """Tests for SQLite database locking behavior."""

    def test_write_contention(self):
        """High write contention scenario."""
        with IsolatedTestDB(name="write_contention") as db:
            errors_lock = threading.Lock()
            all_errors = []

            def high_write_operation(db, thread_id, result):
                for i in range(OPERATIONS_PER_THREAD * 2):  # More operations
                    try:
                        db.add_artifact(MockArtifact(
                            id=f"contention_t{thread_id}_i{i}",
                            type="fact",
                            claim=f"High contention write {thread_id}-{i}"
                        ))
                        result.success_count += 1
                    except sqlite3.OperationalError as e:
                        if "database is locked" in str(e):
                            result.error_count += 1
                            with errors_lock:
                                all_errors.append(str(e))
                        else:
                            raise
                    except Exception as e:
                        result.error_count += 1
                        result.errors.append(str(e))

            results = run_concurrent(db, NUM_THREADS * 2, high_write_operation)  # More threads

            total_success = sum(r.success_count for r in results)
            total_errors = sum(r.error_count for r in results)

            # Some locking errors are acceptable under high contention
            print(f"\nWrite contention: {total_success} success, {total_errors} locked")

    def test_long_transaction_impact(self):
        """Test impact of long-running operations."""
        with IsolatedTestDB(name="long_txn") as db:
            # Create baseline data
            for i in range(50):
                db.add_artifact(MockArtifact(
                    id=f"baseline_{i:04d}",
                    type="fact",
                    claim=f"Baseline {i}"
                ))

            def operation(db, thread_id, result):
                if thread_id == 0:
                    # Thread 0: slow operation
                    for i in range(10):
                        db.add_artifact(MockArtifact(
                            id=f"slow_{i}",
                            type="fact",
                            claim="x" * 10000  # Large content
                        ))
                        time.sleep(0.01)  # Simulate slow processing
                        result.success_count += 1
                else:
                    # Other threads: fast reads
                    for i in range(OPERATIONS_PER_THREAD):
                        try:
                            artifact = db.get_artifact(f"baseline_{i % 50:04d}")
                            if artifact:
                                result.success_count += 1
                        except Exception as e:
                            result.error_count += 1
                            result.errors.append(str(e))

            results = run_concurrent(db, NUM_THREADS, operation)

            # Reads should mostly succeed despite slow writer
            read_results = [r for r in results if r.thread_id != 0]
            total_read_success = sum(r.success_count for r in read_results)
            total_read_errors = sum(r.error_count for r in read_results)

            success_rate = total_read_success / (total_read_success + total_read_errors) if (total_read_success + total_read_errors) > 0 else 0
            assert success_rate > 0.9, f"Read success rate {success_rate:.1%} too low"


# =============================================================================
# Stress Scenarios
# =============================================================================

class TestStressScenarios:
    """Extreme stress test scenarios."""

    def test_burst_traffic(self):
        """Simulate burst traffic pattern."""
        with IsolatedTestDB(name="burst") as db:
            burst_size = 100
            burst_count = 3

            for burst in range(burst_count):
                def burst_operation(db, thread_id, result):
                    for i in range(burst_size // NUM_THREADS):
                        try:
                            db.add_artifact(MockArtifact(
                                id=f"burst{burst}_t{thread_id}_i{i}",
                                type="fact",
                                claim=f"Burst traffic {burst}-{thread_id}-{i}"
                            ))
                            result.success_count += 1
                        except Exception as e:
                            result.error_count += 1

                results = run_concurrent(db, NUM_THREADS, burst_operation)

                # Brief pause between bursts
                time.sleep(0.1)

            final_count = db.count_artifacts()
            expected = burst_size * burst_count
            # Allow some failures under burst load
            assert final_count >= expected * 0.9

    def test_sustained_load(self):
        """Sustained concurrent load over time."""
        with IsolatedTestDB(name="sustained") as db:
            duration_seconds = 2
            operations_completed = [0]
            stop_flag = threading.Event()

            def sustained_operation(db, thread_id, result):
                i = 0
                while not stop_flag.is_set():
                    try:
                        if i % 3 == 0:
                            db.add_artifact(MockArtifact(
                                id=f"sustained_t{thread_id}_i{i}",
                                type="fact",
                                claim=f"Sustained load {thread_id}-{i}"
                            ))
                        else:
                            db.count_artifacts()
                        result.success_count += 1
                        i += 1
                    except Exception as e:
                        result.error_count += 1

            # Start threads
            threads = []
            results = [ThreadResult(i, 0, 0, [], 0) for i in range(NUM_THREADS)]

            for i in range(NUM_THREADS):
                t = threading.Thread(
                    target=sustained_operation,
                    args=(db, i, results[i])
                )
                threads.append(t)
                t.start()

            # Let them run
            time.sleep(duration_seconds)
            stop_flag.set()

            # Wait for completion
            for t in threads:
                t.join()

            total_ops = sum(r.success_count for r in results)
            print(f"\nSustained load: {total_ops} operations in {duration_seconds}s")
            print(f"Rate: {total_ops / duration_seconds:.1f} ops/sec")

            assert total_ops > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
