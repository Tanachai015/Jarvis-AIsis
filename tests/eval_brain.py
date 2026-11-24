"""
Evaluation and Sandboxed Test Suite for AI Brain, Identity, Ambiguity Loop, and Owner Approval Gate.
Part of v2.0.0 J.A.R.V.I.S. JR. (aka K.A.R.I.S.) Upgrade.
Runs 100% offline with zero hardware and zero API token burn.
"""

import unittest
import sys
import os
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.event_bus import event_bus


class TestBrainIdentityAndContext(unittest.TestCase):
    """Verifies J.A.R.V.I.S. JR. // K.A.R.I.S. identity, Boss recognition, and tiered instructions."""

    def test_soul_core_karis_identity(self):
        """Verifies soul_core.md contains J.A.R.V.I.S. JR. (K.A.R.I.S.) identity and your Mac."""
        from core.brain import safe_read_soul_core, build_tiered_system_instruction

        soul = safe_read_soul_core()
        self.assertTrue(
            "K.A.R.I.S." in soul or "KARIS" in soul or "J.A.R.V.I.S. JR." in soul,
            "soul_core.md must contain J.A.R.V.I.S. JR. or K.A.R.I.S. identity"
        )
        self.assertIn("ของคุณ", soul, "soul_core.md must mention 'ของคุณ'")
        self.assertIn("บอส", soul, "soul_core.md must mention 'บอส'")

        tiered_instruction = build_tiered_system_instruction()
        self.assertIn("ของคุณ", tiered_instruction, "Tiered system instruction must incorporate 'ของคุณ'")


class TestWorkflowStateAndAmbiguityLoop(unittest.TestCase):
    """Verifies durable workflow_state.json and the 3-step Ambiguity Confirmation Loop."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_memory = Path(self.temp_dir.name)
        self.state_file = self.mock_memory / "workflow_state.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_workflow_state_io(self):
        """Verifies load_workflow_state and save_workflow_state manage state idempotently."""
        import core.brain as brain_mod

        with patch.object(brain_mod, "WORKFLOW_STATE_FILE", self.state_file):
            state = brain_mod.load_workflow_state()
            self.assertIn("pending_confirmation", state)
            self.assertIn("pending_approval", state)
            self.assertFalse(state["pending_confirmation"]["active"])
            self.assertFalse(state["pending_approval"]["active"])

            # Test setting pending confirmation
            brain_mod.set_pending_confirmation("เป็ด แอป เทอร์มีแนล", "เปิดแอป Terminal")
            updated = brain_mod.load_workflow_state()
            self.assertTrue(updated["pending_confirmation"]["active"])
            self.assertEqual(updated["pending_confirmation"]["raw_stt"], "เป็ด แอป เทอร์มีแนล")
            self.assertEqual(updated["pending_confirmation"]["inferred_intent"], "เปิดแอป Terminal")

            # Test clearing
            brain_mod.clear_pending_confirmation()
            cleared = brain_mod.load_workflow_state()
            self.assertFalse(cleared["pending_confirmation"]["active"])

    def test_ambiguity_step1_and_step2_confirmation(self):
        """Verifies Step 1 (ask without repeating garble) and Step 2 (yes -> execute inferred without repeating)."""
        import core.brain as brain_mod

        with patch.object(brain_mod, "WORKFLOW_STATE_FILE", self.state_file):
            brain_mod.set_pending_confirmation("เป็ด แอป เทอร์มีแนล", "เปิดแอป Terminal")

            # When user confirms with "ใช่" or "ถูกต้อง"
            handled, action, reply = brain_mod.handle_workflow_user_turn("ใช่ครับ")
            self.assertTrue(handled, "Ambiguity confirmation turn should be intercepted")
            self.assertEqual(action, "execute_inferred")
            self.assertEqual(reply, "เปิดแอป Terminal")

            # State should be cleared
            state = brain_mod.load_workflow_state()
            self.assertFalse(state["pending_confirmation"]["active"], "State must be cleared after confirmation")

    def test_ambiguity_step3_denial_reveals_raw_stt(self):
        """Verifies Step 3: when user says 'ไม่ใช่' / 'ผิด', system speaks out raw_stt heard."""
        import core.brain as brain_mod

        with patch.object(brain_mod, "WORKFLOW_STATE_FILE", self.state_file):
            brain_mod.set_pending_confirmation("เป็ด แอป เทอร์มีแนล", "เปิดแอป Terminal")

            handled, action, reply = brain_mod.handle_workflow_user_turn("ไม่ใช่ครับ")
            self.assertTrue(handled, "Ambiguity denial turn should be intercepted")
            self.assertEqual(action, "denied_reveal_raw")
            self.assertIn("เป็ด แอป เทอร์มีแนล", reply, "System must reveal raw STT when user denies")
            self.assertIn("บอส", reply, "System must address บอส")

            state = brain_mod.load_workflow_state()
            self.assertFalse(state["pending_confirmation"]["active"], "State must be cleared after denial")


class TestOwnerApprovalGate(unittest.TestCase):
    """Verifies High-Impact Tool detection, pending_approval gating, and approval/rejection signals."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.mock_memory = Path(self.temp_dir.name)
        self.state_file = self.mock_memory / "workflow_state.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_high_impact_tool_detection(self):
        """Verifies is_high_impact_tool correctly classifies dangerous actions."""
        import core.brain as brain_mod

        # Dangerous tools
        self.assertTrue(brain_mod.is_high_impact_tool("git_commit", {"message": "fix"}))
        self.assertTrue(brain_mod.is_high_impact_tool("git_reset", {"hard": True}))
        self.assertTrue(brain_mod.is_high_impact_tool("write_file", {"path": "main.py", "content": "..."}))
        self.assertTrue(brain_mod.is_high_impact_tool("edit_file", {"path": "core/brain.py"}))

        # Safe tools (reading, searching, modifying memory or tests)
        self.assertFalse(brain_mod.is_high_impact_tool("read_file", {"path": "main.py"}))
        self.assertFalse(brain_mod.is_high_impact_tool("write_file", {"path": "memory/chat_history.json"}))
        self.assertFalse(brain_mod.is_high_impact_tool("write_file", {"path": "tests/temp_test.py"}))
        self.assertFalse(brain_mod.is_high_impact_tool("fetch", {"url": "https://example.com"}))

    def test_approval_gate_lifecycle(self):
        """Verifies pending_approval recording and resolution via event_bus."""
        import core.brain as brain_mod

        with patch.object(brain_mod, "WORKFLOW_STATE_FILE", self.state_file):
            # 1. Set pending approval
            brain_mod.set_pending_approval(
                tool_name="git_commit",
                tool_args={"message": "feat: release"},
                description="คอมมิตโค้ด: feat: release"
            )
            state = brain_mod.load_workflow_state()
            self.assertTrue(state["pending_approval"]["active"])
            self.assertEqual(state["pending_approval"]["tool_name"], "git_commit")

            # 2. Test user verbal confirmation "อนุมัติ"
            handled, action, reply = brain_mod.handle_workflow_user_turn("อนุมัติครับ")
            self.assertTrue(handled)
            self.assertEqual(action, "approval_granted")

            # 3. Test user verbal rejection "ยกเลิก"
            brain_mod.set_pending_approval(
                tool_name="git_reset",
                tool_args={"hard": True},
                description="รีเซ็ตโค้ด git_reset"
            )
            handled, action, reply = brain_mod.handle_workflow_user_turn("ยกเลิกครับ")
            self.assertTrue(handled)
            self.assertEqual(action, "approval_rejected")


if __name__ == "__main__":
    unittest.main(verbosity=2)
