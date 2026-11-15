"""
Test Suite: Step 3 Safety Net Retention & Billing Gate Verification
Validates:
1. Snapshot Retention Policy: 1 Permanent Virgin Baseline + Top 3 Rolling Generations.
2. Selectable Time-Machine Restore: Ability to specify and rollback to any available snapshot.
3. Billing Gate Parity: Both Step 2 (Batch Sync) and Step 3 (Rollback) strictly require Trial activation (HTTP 402 for CANARY_TRIAL).
4. UI & I18N Parity: Verify modal elements, dropdown selector, and bilingual dictionary entries.
"""

import unittest
import os
import re
import json

class TestStep3RetentionAndBillingGate(unittest.TestCase):
    def setUp(self):
        self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.worker_dir = os.path.join(self.base_dir, "cloudflare_worker", "src")
        self.types_file = os.path.join(self.worker_dir, "types.ts")
        self.snapshot_file = os.path.join(self.worker_dir, "snapshot.ts")
        self.index_file = os.path.join(self.worker_dir, "index.ts")
        self.ui_file = os.path.join(self.worker_dir, "ui.ts")

    def test_01_types_define_snapshot_summary_and_baseline(self):
        """Verify types.ts defines isBaseline and SnapshotSummary with required fields."""
        with open(self.types_file, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn("isBaseline?: boolean;", content, "StoreSnapshot must support optional isBaseline")
        self.assertIn("export interface SnapshotSummary", content, "SnapshotSummary interface must be exported")
        self.assertIn("snapshotId: string;", content)
        self.assertIn("isBaseline: boolean;", content)
        self.assertIn("isLatest: boolean;", content)
        self.assertIn("label: string;", content)

    def test_02_snapshot_engine_retention_policy_enforcement(self):
        """Verify snapshot.ts implements baseline preservation and top-3 pruning."""
        with open(self.snapshot_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Check baseline preservation
        self.assertIn("getBaselineSnapshotId", content)
        self.assertIn("getBaselineSnapshot", content)
        self.assertIn("pruneOldSnapshots", content)
        self.assertIn("pruneMemorySnapshots", content)

        # Ensure max 3 rolling generations logic
        self.assertIn("maxRollingGenerations = 3", content)

        # Ensure baseline is protected from deletion and always resolves to oldest snapshot
        self.assertIn("itemId !== trueBaselineId", content)
        self.assertIn("const oldestObj = snapshotObjects[0];", content)

        # Ensure listR2Objects excludes latest.json and baseline.json
        self.assertIn('fname !== "latest.json"', content)
        self.assertIn('fname !== "baseline.json"', content)

        # Check listSnapshots method exists and formats labels
        self.assertIn("async listSnapshots()", content)
        self.assertIn("Virgin Baseline", content)

        # Ensure listSnapshots includes customMetadata and falls back cleanly for all snapshots
        self.assertIn('"customMetadata"', content, "listSnapshots must include customMetadata to fetch totalProducts")
        self.assertIn("if (totalProducts === 0)", content, "Fallback must apply to all snapshots when metadata is missing")

        # Check rollback target resolution allows baseline & latest
        self.assertIn('cleanSnapshotId === "baseline"', content)
        self.assertIn('cleanSnapshotId === "latest"', content)

    def test_03_index_billing_gate_on_step2_and_step3(self):
        """Verify index.ts strictly gates /api/rollback and /api/batch/start behind trial activation."""
        with open(self.index_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Step 2 batch sync check
        self.assertIn("SUBSCRIPTION_REQUIRED_FOR_BULK", content)

        # Step 3 rollback check
        self.assertIn("SUBSCRIPTION_REQUIRED_FOR_ROLLBACK", content)
        self.assertIn(
            'if (billingState.planStatus === "CANARY_TRIAL")',
            content,
            "Rollback endpoint must verify planStatus is not CANARY_TRIAL"
        )

        # Status endpoint supplies availableSnapshots
        self.assertIn("availableSnapshots", content)
        self.assertIn("snapshotEngine.listSnapshots()", content)

        # Snapshot list endpoint exists
        self.assertIn('url.pathname === "/api/snapshot/list"', content)

    def test_04_ui_dom_and_selector_contract(self):
        """Verify ui.ts includes snapshot dropdown, trial gate on modal, and bilingual dictionary."""
        with open(self.ui_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Verify dropdown element exists in rollback modal
        self.assertIn('id="rollback-snapshot-select"', content)
        self.assertIn('data-i18n="modal_select_label"', content)
        self.assertIn('data-i18n="modal_select_hint"', content)

        # Verify populateSnapshotSelect function exists
        self.assertIn("function populateSnapshotSelect()", content)

        # Verify openRollbackModal intercepts CANARY_TRIAL
        self.assertIn("planStatus === 'CANARY_TRIAL'", content)
        self.assertIn("openBatchTrialModal('rollback')", content)

        # Verify executeRollback sends selected snapshotId
        self.assertIn("snapshotId: selectedSnapshotId", content)

        # Verify English and Japanese I18N dictionary entries
        self.assertIn("btn_restore_locked:", content)
        self.assertIn("modal_select_label:", content)
        self.assertIn("modal_select_hint:", content)
        self.assertIn("復元するバックアップ時点を選択:", content)
        self.assertIn("初期原本（Baseline）", content)

if __name__ == "__main__":
    unittest.main()
