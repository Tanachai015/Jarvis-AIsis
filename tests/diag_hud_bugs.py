"""
Automated Diagnostic Test Suite for K.A.R.I.S. HUD (v2.1.3 -> v2.1.4 Audit)
Hunts for multi-screen duplicate popups, click-outside failures across all states,
click-inside stability, animation tick resurrections, and child widget sync bugs.
"""

import sys
import os
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint, QPointF, QEvent
from PySide6.QtGui import QMouseEvent, QGuiApplication

from core.event_bus import event_bus
from ui.dynamic_island import DynamicIsland, DynamicIslandManager


class TestHUDDiagnostics(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication(sys.argv)

    def _make_two_screen_manager(self):
        """Creates a DynamicIslandManager with 2 independent screen islands for testing."""
        manager = DynamicIslandManager()
        for isl in manager.islands:
            isl.close()
        manager.islands.clear()

        scr1 = MagicMock()
        scr1.geometry.return_value = MagicMock(x=lambda: 0, y=lambda: 0, width=lambda: 1440, height=lambda: 900)
        scr1.availableGeometry.return_value = MagicMock(x=lambda: 0, y=lambda: 25, width=lambda: 1440, height=lambda: 875)
        scr2 = MagicMock()
        scr2.geometry.return_value = MagicMock(x=lambda: 1440, y=lambda: 0, width=lambda: 1920, height=lambda: 1080)
        scr2.availableGeometry.return_value = MagicMock(x=lambda: 1440, y=lambda: 25, width=lambda: 1920, height=lambda: 1055)

        isl1 = DynamicIsland(screen=scr1)
        isl2 = DynamicIsland(screen=scr2)
        manager.islands = [isl1, isl2]
        return manager, scr1, scr2, isl1, isl2

    def test_diag_01_multiscreen_state_change_no_duplicate_popup(self):
        """[Bug Hunt 1] Switching states (thinking/listening/speaking) must NOT pop up HUD on 2nd screen."""
        manager, scr1, scr2, isl1, isl2 = self._make_two_screen_manager()
        try:
            with patch.object(QGuiApplication, "screenAt", return_value=scr1):
                manager.expand_active()
                self.assertTrue(isl1.isVisible(), "Active screen 1 must be visible")
                self.assertFalse(isl2.isVisible(), "Inactive screen 2 must remain hidden")

                # Simulate Brain thinking -> speaking -> listening while cursor moves or screenAt returns None
                for st in ["thinking", "speaking", "listening"]:
                    event_bus.state_changed.emit(st)
                    isl1._on_animation_tick()
                    isl2._on_animation_tick()

                visible_count = sum(1 for isl in manager.islands if isl.isVisible())
                self.assertEqual(
                    visible_count, 1,
                    f"Duplicate HUD detected! {visible_count} screens visible simultaneously during active states."
                )
        finally:
            for isl in manager.islands:
                isl.close()

    def test_diag_02_screenAt_none_edge_case_no_all_screen_popup(self):
        """[Bug Hunt 2] If QGuiApplication.screenAt(cursor) returns None (menubar/edge), must NOT open all screens."""
        manager, scr1, scr2, isl1, isl2 = self._make_two_screen_manager()
        try:
            with patch.object(QGuiApplication, "screenAt", return_value=None):
                event_bus.state_changed.emit("listening")
                isl1._on_animation_tick()
                isl2._on_animation_tick()
                visible_count = sum(1 for isl in manager.islands if isl.isVisible())
                self.assertLessEqual(
                    visible_count, 1,
                    f"screenAt()==None caused {visible_count} HUD windows to open at once!"
                )
        finally:
            for isl in manager.islands:
                isl.close()

    def test_diag_03_click_outside_closes_in_ALL_modes(self):
        """[Bug Hunt 3] Clicking outside HUD must close it in EVERY mode (idle, listening, thinking, running_tool, speaking, confused)."""
        states = ["idle", "listening", "thinking", "running_tool", "speaking", "wake_ack", "confused"]
        failures = []
        for st in states:
            island = DynamicIsland()
            try:
                island.expand_manually()
                island.on_state_changed(st)
                island._last_expand_time = time.time() - 1.0  # bypass open grace period
                self.assertTrue(island.isVisible(), f"Setup failed: island not visible in state '{st}'")

                # Simulate global click outside HUD bounds
                outside_pt = QPointF(-500.0, -500.0)
                ev = QMouseEvent(QEvent.MouseButtonPress, outside_pt, outside_pt, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
                with patch("ui.dynamic_island.QCursor.pos", return_value=QPoint(-500, -500)):
                    island.eventFilter(island, ev)

                # Simulate animation ticks running after click-outside
                for _ in range(3):
                    island._on_animation_tick()

                if island.isVisible():
                    failures.append(st)
            finally:
                island.close()

        self.assertEqual(
            failures, [],
            f"Click-outside FAILED to close HUD (or it resurrected on tick) in states: {failures}"
        )

    def test_diag_04_app_deactivate_closes_in_ALL_modes(self):
        """[Bug Hunt 4] Switching to another macOS app (ApplicationDeactivate) must close HUD in EVERY mode."""
        states = ["idle", "listening", "thinking", "running_tool", "speaking"]
        failures = []
        for st in states:
            island = DynamicIsland()
            try:
                island.expand_manually()
                island.on_state_changed(st)
                island._last_expand_time = time.time() - 1.0
                ev = QEvent(QEvent.ApplicationDeactivate)
                island.eventFilter(island, ev)
                for _ in range(3):
                    island._on_animation_tick()
                if island.isVisible():
                    failures.append(st)
            finally:
                island.close()

        self.assertEqual(
            failures, [],
            f"ApplicationDeactivate FAILED to close HUD in states: {failures}"
        )

    def test_diag_05_click_inside_empty_area_never_closes(self):
        """[Bug Hunt 5] Clicking non-button areas inside HUD must NEVER close it in any mode."""
        island = DynamicIsland()
        try:
            for st in ["idle", "listening", "thinking", "speaking"]:
                island.expand_manually()
                island.on_state_changed(st)
                island._last_expand_time = time.time() - 1.0

                # Click right-side 3D stage background (x=550, y=218)
                inside_pos = QPointF(550.0, 218.0)
                ev = QMouseEvent(QEvent.MouseButtonPress, inside_pos, inside_pos, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
                island.mousePressEvent(ev)
                self.assertTrue(island.isVisible(), f"Inside click closed HUD in state '{st}'")
        finally:
            island.close()

    def test_diag_06_child_widgets_hidden_when_dismissed(self):
        """[Bug Hunt 6] Embedded QLineEdits (chat_input, todo_input) must hide when HUD is dismissed."""
        island = DynamicIsland()
        try:
            island.expand_manually()
            island._active_console_view = "chat"
            island._sync_child_widgets()
            self.assertTrue(island.chat_input.isVisible())

            island.fold_manually()
            self.assertFalse(island.chat_input.isVisible(), "chat_input remained visible after fold_manually()")
            self.assertFalse(island.todo_input.isVisible(), "todo_input remained visible after fold_manually()")
        finally:
            island.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
