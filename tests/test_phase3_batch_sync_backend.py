#!/usr/bin/env python3
"""
tests/test_phase3_batch_sync_backend.py

Phase 3 Backend Unit and Static Verification Tests:
Verifies Chunk-Driven Batch Processing, 30s WaitUntil Safeguards,
R2 Job State Persistence, Distributed Runner Lock, and Dynamic ETA Calculation.
"""

import os
import re
import unittest

WORKER_DIR = os.path.join(os.path.dirname(__file__), "..", "cloudflare_worker")
SRC_INDEX = os.path.join(WORKER_DIR, "src", "index.ts")
SRC_TYPES = os.path.join(WORKER_DIR, "src", "types.ts")

class TestPhase3BackendArchitecture(unittest.TestCase):
    def setUp(self):
        with open(SRC_INDEX, "r", encoding="utf-8") as f:
            self.index_ts = f.read()
        with open(SRC_TYPES, "r", encoding="utf-8") as f:
            self.types_ts = f.read()

    def test_types_ts_contains_extended_batch_job_state(self):
        """Verify BatchJobState has all optional ETA and chunk progress fields."""
        required_fields = [
            "skippedCount?: number;",
            "cleanedCount?: number;",
            "currentProductId?: string;",
            "currentProductTitle?: string;",
            "avgProcessingSec?: number;",
            "estimatedRemainingSec?: number;",
            "updatedAt?: string;",
        ]
        for field in required_fields:
            self.assertIn(field, self.types_ts, f"Missing required field in BatchJobState: {field}")

    def test_r2_job_state_persistence_functions(self):
        """Verify loadShopJobState and saveShopJobState are defined with R2 backing."""
        self.assertIn("async function loadShopJobState(env: Env, shop: string): Promise<BatchJobState>", self.index_ts)
        self.assertIn("async function saveShopJobState(", self.index_ts)
        self.assertIn('`state/${shop}/job.json`', self.index_ts)

    def test_distributed_runner_lock_safeguard(self):
        """Verify 20s TTL lock, heartbeat renewal, and per-product in-flight lock exist to prevent multi-isolate concurrency collision."""
        self.assertIn("BATCH_LOCK_TTL_MS = 20_000", self.index_ts)
        self.assertIn("async function acquireBatchLock(", self.index_ts)
        self.assertIn("async function refreshBatchLock(", self.index_ts)
        self.assertIn("async function releaseBatchLock(", self.index_ts)
        self.assertIn("async function isBatchLockActive(", self.index_ts)
        self.assertIn('`locks/${shop}/batch_runner.json`', self.index_ts)
        chunk_match = re.search(r'async function runBatchChunk\(.*?async function getShopBillingState', self.index_ts, re.DOTALL)
        self.assertIsNotNone(chunk_match)
        chunk_body = chunk_match.group(0)
        self.assertIn("acquireInFlightLock(env, shop, prod.productId)", chunk_body)
        self.assertIn("releaseInFlightLock(env, shop, prod.productId)", chunk_body)
        self.assertIn("refreshBatchLock(env, shop)", chunk_body)
        self.assertIn("cleanedProductIds", chunk_body)

    def test_chunk_budget_limits_prevent_30s_timeout(self):
        """Verify 2 items per chunk or 18s execution budget prevents Cloudflare 30s abort."""
        self.assertIn("MAX_ITEMS_PER_CHUNK = 2", self.index_ts)
        self.assertIn("MAX_CHUNK_DURATION_MS = 18_000", self.index_ts)
        self.assertIn("async function runBatchChunk(", self.index_ts)

    def test_api_status_auto_continuation_trigger(self):
        """Verify GET /api/status triggers runBatchChunk when job is RUNNING and runner lock is free."""
        status_route_match = re.search(r'url\.pathname === "/api/status".*?return Response\.json', self.index_ts, re.DOTALL)
        self.assertIsNotNone(status_route_match, "Could not find /api/status route handler")
        status_code = status_route_match.group(0)
        self.assertIn("isBatchLockActive(env, requestedShop)", status_code)
        self.assertIn("runBatchChunk(env, requestedShop, url.origin, activeToken)", status_code)

    def test_batch_start_calculates_initial_eta_and_pre_skips(self):
        """Verify POST /api/batch/start computes initial ETA and triggers initial chunk."""
        start_route_match = re.search(r'url\.pathname === "/api/batch/start".*?// 5\. API: Emergency Circuit Breaker', self.index_ts, re.DOTALL)
        self.assertIsNotNone(start_route_match, "Could not find /api/batch/start route handler")
        start_code = start_route_match.group(0)
        self.assertIn("isProductAlreadyCleaned", start_code)
        self.assertIn("runBatchChunk(env, requestedShop, url.origin, activeToken, forceReclean)", start_code)
        self.assertIn("saveShopJobState", start_code)

    def test_batch_abort_and_resume_update_job_and_circuit_breaker(self):
        """Verify emergency circuit breaker abort and resume update R2 job state."""
        abort_match = re.search(r'url\.pathname === "/api/batch/abort".*?return Response\.json', self.index_ts, re.DOTALL)
        self.assertIsNotNone(abort_match, "Could not find /api/batch/abort route handler")
        abort_code = abort_match.group(0)
        self.assertIn('currentJob.status = "ABORTED"', abort_code)
        self.assertIn("releaseBatchLock", abort_code)

        resume_match = re.search(r'url\.pathname === "/api/batch/resume".*?return Response\.json', self.index_ts, re.DOTALL)
        self.assertIsNotNone(resume_match, "Could not find /api/batch/resume route handler")
        resume_code = resume_match.group(0)
        self.assertIn('currentJob.status = "RUNNING"', resume_code)

    def test_batch_cancel_updates_job_and_clears_circuit_breaker(self):
        """Verify POST /api/batch/cancel sets job status to CANCELLED and clears circuit breaker."""
        cancel_match = re.search(r'url\.pathname === "/api/batch/cancel".*?return Response\.json', self.index_ts, re.DOTALL)
        self.assertIsNotNone(cancel_match, "Could not find /api/batch/cancel route handler")
        cancel_code = cancel_match.group(0)
        self.assertIn('currentJob.status = "CANCELLED"', cancel_code)
        self.assertIn("billingState.circuitBreakerTripped = false", cancel_code)
        self.assertIn("releaseBatchLock", cancel_code)

if __name__ == "__main__":
    unittest.main()
