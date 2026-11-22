"""
Dynamic Island UI for Jarvis Desktop Assistant.
Adaptive Edge-Aware Menu Bar Docked Dynamic Island (Folded ↔ Expanded)
with 60 FPS Pure Vector Cyber Mini-Robot Avatar (QPainter & Kinematics).
"""

import sys
import time
import math
import random
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, QTimer, QRectF, QPointF, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QPainter, QPainterPath, QColor, QFont, QPen, QBrush, QGuiApplication
from PySide6.QtWidgets import QWidget, QApplication

import config
from core.event_bus import event_bus


class DynamicIsland(QWidget):
    """
    Menu Bar Docked Dynamic Island with Cyber Mini-Robot Avatar.
    - Folded Mode (idle): Compact pill (68x24 px) embedded seamlessly in macOS Menu Bar.
    - Expanded Mode (active): 340x56 px 2-stage spring popup displaying the animated robot and status.
    - Pure QPainter vector graphics: Zero raster assets, 100% Retina crisp, 60 FPS / 30 FPS adaptive.
    """

    STATES = {
        "speaking": {
            "id": "speaking",
            "tag": "speaking",
            "status": "กำลังพูดตอบกลับ...",
            "subtext": "Jarvis Speaker กำลังอ่านข้อความสรุป",
            "color": QColor("#00E5FF"),       # Primary Neon Cyan
            "bg_tint": QColor("#05141F"),
            "visor_tint": QColor("#082030"),
        },
        "listening": {
            "id": "listening",
            "tag": "listening",
            "status": "กำลังฟังคำสั่ง...",
            "subtext": "Silero VAD เปิดรับเสียง • พูดคำสั่งได้เลยครับบอส",
            "color": QColor("#00FFD1"),       # Listening Mint
            "bg_tint": QColor("#041816"),
            "visor_tint": QColor("#072622"),
        },
        "thinking": {
            "id": "thinking",
            "tag": "thinking",
            "status": "กำลังวิเคราะห์คำสั่ง...",
            "subtext": "Gemini 3.5 Flash Lite กำลังประมวลผลบริบท",
            "color": QColor("#38BDF8"),       # Sky Glow
            "bg_tint": QColor("#061224"),
            "visor_tint": QColor("#0A1E3A"),
        },
        "running_tool": {
            "id": "running_tool",
            "tag": "running_tool",
            "status": "กำลังรันเครื่องมือ MCP...",
            "subtext": "Executing macOS Control / Filesystem / Web Fetch",
            "color": QColor("#60A5FA"),       # Tool Blue
            "bg_tint": QColor("#071126"),
            "visor_tint": QColor("#0C1C3D"),
        },
        "wake_ack": {
            "id": "wake_ack",
            "tag": "ready",
            "status": "พร้อมครับบอส!",
            "subtext": "ตรวจพบคำปลุก 'Hey Jarvis' พร้อมรับคำสั่ง",
            "color": QColor("#22D3EE"),       # Joy Cyan
            "bg_tint": QColor("#051822"),
            "visor_tint": QColor("#092838"),
        },
        "confused": {
            "id": "confused",
            "tag": "confused",
            "status": "ขออภัยครับ ฟังไม่ถนัด...",
            "subtext": "กรุณาพูดคำสั่งใหม่อีกครั้งครับบอส",
            "color": QColor("#FBBF24"),       # Warning Amber
            "bg_tint": QColor("#1A1305"),
            "visor_tint": QColor("#291E08"),
        },
        "idle": {
            "id": "idle",
            "tag": "standby",
            "status": "Standby Wake (รอคำปลุก)",
            "subtext": "พูด 'Hey Jarvis' หรือกด Cmd+Shift+J",
            "color": QColor("#0EA5E9"),       # Calm Sky
            "bg_tint": QColor("#06101D"),
            "visor_tint": QColor("#09182B"),
        },
    }

    QUIRK_NAMES = ["look_around", "double_blink", "hum_hop", "mini_yawn", "curious_nod"]

    def __init__(self, parent=None):
        super().__init__(parent)

        # macOS Frameless Overlay Window Flags
        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowDoesNotAcceptFocus
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        self.current_state = "idle"
        self._custom_subtext = ""

        # Geometry & Dimension Settings
        self.edge = "top"
        self.bar_thickness = 24
        self.folded_w = 68
        self.folded_h = 24
        self.expanded_w = 340
        self.expanded_h = 56
        self.menubar_offset_x = 0

        # Load menubar_offset_x from voice_settings.json if present
        self._load_settings()

        # Cache for system tray edge position
        self._cached_tray_min_x: Optional[float] = None
        self._last_tray_scan_time: float = 0.0

        # Kinematics & Animation State
        self.start_time = time.time()
        self.active_quirk: Optional[str] = None
        self.quirk_start_time: float = 0.0
        self.quirk_duration: float = 1.6
        self.next_auto_quirk_time: float = 3.0

        # Geometry Animation (Spring Pop-out)
        self.anim = QPropertyAnimation(self, b"geometry", self)
        self.anim.setDuration(320)
        self.anim.setEasingCurve(QEasingCurve.Type.OutBack)

        # 60 FPS / 30 FPS Adaptive Render Timer
        self.render_timer = QTimer(self)
        self.render_timer.timeout.connect(self._on_animation_tick)
        self.render_timer.start(33)  # Start at 30 FPS for idle

        # Setup macOS AppKit Window Level & Space behaviors
        self._setup_macos_window_level()

        # Calculate initial edge and position
        self._detect_system_edge_and_bar()
        self._apply_geometry_for_state(animated=False)

        # Connect screen geometry change events
        app = QGuiApplication.instance()
        if app:
            primary_screen = QGuiApplication.primaryScreen()
            if primary_screen:
                primary_screen.geometryChanged.connect(self._on_screen_geometry_changed)
                primary_screen.availableGeometryChanged.connect(self._on_screen_geometry_changed)

        # Connect event bus signals
        event_bus.state_changed.connect(self.on_state_changed)
        event_bus.task_log_updated.connect(self._on_task_log_updated)

        self.show()

    def _load_settings(self):
        """Loads optional menubar_offset_x from voice_settings.json."""
        try:
            import json
            settings_path = config.PROJECT_ROOT / "voice_settings.json"
            if settings_path.exists():
                with open(settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.menubar_offset_x = int(data.get("menubar_offset_x", 0))
        except Exception:
            self.menubar_offset_x = 0

    def _setup_macos_window_level(self):
        """Sets macOS Window level to NSMainMenuWindowLevel + 1 and enables multi-space persistence."""
        if sys.platform != "darwin":
            return
        try:
            import AppKit
            import objc
            view_ptr = int(self.winId())
            nsview = objc.objc_object(c_void_p=view_ptr)
            nswindow = nsview.window()
            if nswindow:
                nswindow.setLevel_(AppKit.NSMainMenuWindowLevel + 1)
                nswindow.setCollectionBehavior_(
                    AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces |
                    AppKit.NSWindowCollectionBehaviorStationary
                )
        except Exception as e:
            # Safe fallback for headless or non-PyObjC environments
            pass

    def _detect_system_edge_and_bar(self):
        """
        Detects macOS Menu Bar / System Taskbar edge ('top', 'bottom', 'left', 'right')
        and bar thickness by comparing full screen geometry with availableGeometry.
        Prioritizes 'top' for macOS Menu Bar.
        """
        screen = QGuiApplication.primaryScreen()
        if not screen:
            self.edge = "top"
            self.bar_thickness = 24
            return

        full = screen.geometry()
        avail = screen.availableGeometry()

        # On macOS, Menu Bar is always at the top
        if avail.y() > full.y():
            self.edge = "top"
            self.bar_thickness = avail.y() - full.y()
        elif full.bottom() > avail.bottom():
            self.edge = "bottom"
            self.bar_thickness = full.bottom() - avail.bottom()
        elif avail.x() > full.x():
            self.edge = "left"
            self.bar_thickness = avail.x() - full.x()
        elif full.right() > avail.right():
            self.edge = "right"
            self.bar_thickness = full.right() - avail.right()
        else:
            # Auto-hide or full-screen fallback: check AppKit NSStatusBar thickness
            self.edge = "top"
            self.bar_thickness = 24
            if sys.platform == "darwin":
                try:
                    import AppKit
                    self.bar_thickness = int(AppKit.NSStatusBar.systemStatusBar().thickness())
                except Exception:
                    self.bar_thickness = 24

        # Enforce realistic menu bar height limits
        self.bar_thickness = max(22, min(40, self.bar_thickness))
        self.folded_h = self.bar_thickness - 2
        self.folded_w = int(self.folded_h * 2.8)

    def _get_leftmost_tray_x(self) -> float:
        """
        Detects leftmost bounds of macOS Menu Bar Status/Tray items (Quartz Layer 25).
        Caches result for 5 seconds to avoid CPU overhead in animation loop.
        """
        now = time.time()
        if self._cached_tray_min_x is not None and (now - self._last_tray_scan_time < 5.0):
            return self._cached_tray_min_x

        screen = QGuiApplication.primaryScreen()
        sw = float(screen.geometry().width()) if screen else 1650.0

        # Safe default if Quartz is unavailable
        default_x = sw - 340.0 - 100.0 - self.menubar_offset_x

        if sys.platform != "darwin":
            self._cached_tray_min_x = default_x
            self._last_tray_scan_time = now
            return default_x

        try:
            import Quartz
            opts = Quartz.kCGWindowListOptionOnScreenOnly
            wins = Quartz.CGWindowListCopyWindowInfo(opts, Quartz.kCGNullWindowID)
            tray_xs = []
            for w in wins:
                if w.get('kCGWindowLayer', 0) == 25:
                    b = w.get('kCGWindowBounds', {})
                    bx = float(b.get('X', 0.0))
                    by = float(b.get('Y', 0.0))
                    if 0.0 <= by <= 40.0 and (sw * 0.35) <= bx < sw:
                        tray_xs.append(bx)

            if tray_xs:
                min_x = min(tray_xs)
                # Verify Notch right boundary if available
                min_safe_x = self._get_notch_min_safe_x()
                if min_safe_x > 0 and min_x < min_safe_x:
                    min_x = min_safe_x + 16.0
                self._cached_tray_min_x = min_x
                self._last_tray_scan_time = now
                return min_x
        except Exception:
            pass

        self._cached_tray_min_x = default_x
        self._last_tray_scan_time = now
        return default_x

    def _get_notch_min_safe_x(self) -> float:
        """Returns right edge of macOS camera notch via NSScreen.auxiliaryTopRightArea."""
        if sys.platform != "darwin":
            return 0.0
        try:
            import AppKit
            screen = AppKit.NSScreen.mainScreen()
            if hasattr(screen, "auxiliaryTopRightArea"):
                area = screen.auxiliaryTopRightArea()
                if area and area.size.width > 0:
                    return float(area.origin.x)
        except Exception:
            pass
        return 0.0

    def _calculate_target_geometry(self, is_expanded: bool) -> tuple:
        """Calculates (x, y, w, h) for Folded or Expanded pill avoiding Notch and Tray."""
        screen = QGuiApplication.primaryScreen()
        screen_geo = screen.geometry() if screen else QRectF(0, 0, 1650, 1050)
        sw = screen_geo.width()

        tray_min_x = self._get_leftmost_tray_x()
        min_safe_x = self._get_notch_min_safe_x()

        if is_expanded:
            w = self.expanded_w
            h = self.expanded_h
            # Right edge docks 12px before tray icons
            right_x = tray_min_x - 12.0 - self.menubar_offset_x
            x = right_x - w
            if min_safe_x > 0 and x < min_safe_x + 10:
                x = min_safe_x + 10
            y = screen_geo.y() + 2
        else:
            w = self.folded_w
            h = self.folded_h
            right_x = tray_min_x - 12.0 - self.menubar_offset_x
            x = right_x - w
            if min_safe_x > 0 and x < min_safe_x + 10:
                x = min_safe_x + 10
            y = screen_geo.y() + 1

        return int(x), int(y), int(w), int(h)

    def compute_dock_geometry(self, is_expanded: bool) -> tuple:
        """Public method to compute dock geometry (x, y, w, h) for testing or layout queries."""
        return self._calculate_target_geometry(is_expanded)

    def trigger_quirk(self, quirk_name: str):
        """Manually triggers a specific autonomous quirk animation."""
        if quirk_name in self.QUIRK_NAMES:
            self.active_quirk = quirk_name
            self.quirk_start_time = time.time() - self.start_time
            self.quirk_duration = 1.9 if quirk_name == "mini_yawn" else 1.5

    def _apply_geometry_for_state(self, animated: bool = True):
        """Morphs geometry between Folded and Expanded pill using spring easing."""
        is_expanded = (self.current_state != "idle")
        target_x, target_y, target_w, target_h = self._calculate_target_geometry(is_expanded)

        if animated:
            self.anim.stop()
            self.anim.setStartValue(self.geometry())
            self.anim.setEndValue(QRectF(target_x, target_y, target_w, target_h).toRect())
            self.anim.start()
        else:
            self.setGeometry(target_x, target_y, target_w, target_h)

    def _on_screen_geometry_changed(self):
        """Handles display resolution or dock location changes."""
        self._cached_tray_min_x = None
        self._detect_system_edge_and_bar()
        self._apply_geometry_for_state(animated=False)

    def on_state_changed(self, new_state: str):
        """Slot for state_changed signal from event_bus."""
        clean_state = new_state.lower().strip()
        if clean_state not in self.STATES:
            if "listen" in clean_state:
                clean_state = "listening"
            elif "think" in clean_state:
                clean_state = "thinking"
            elif "speak" in clean_state:
                clean_state = "speaking"
            elif "tool" in clean_state:
                clean_state = "running_tool"
            else:
                clean_state = "idle"

        prev_state = self.current_state
        self.current_state = clean_state

        # Adaptive FPS: 60 FPS for active states, 30 FPS for folded idle
        if self.current_state == "idle":
            self.render_timer.setInterval(33)  # 30 FPS
            self._custom_subtext = ""
        else:
            self.render_timer.setInterval(16)  # 60 FPS

        # Refresh tray bounds and trigger morph animation if state foldedness changed
        was_expanded = (prev_state != "idle")
        is_expanded = (self.current_state != "idle")
        if was_expanded != is_expanded or prev_state != clean_state:
            self._apply_geometry_for_state(animated=True)

        self.update()

    def _on_task_log_updated(self, title: str, content: str):
        """Displays user-friendly task updates in subtext if active."""
        if self.current_state != "idle" and content:
            clean = content.strip().split("\n")[0]
            if len(clean) > 55:
                clean = clean[:52] + "..."
            self._custom_subtext = clean
            self.update()

    def mousePressEvent(self, event):
        """Clicking Dynamic Island toggles OverlayChat immediately."""
        if event.button() == Qt.LeftButton:
            event_bus.toggle_overlay_signal.emit()

    def _on_animation_tick(self):
        """60 FPS / 30 FPS tick updating kinematics and quirks."""
        now = time.time()
        t = now - self.start_time

        # Autonomous Quirks engine during idle or listening
        if (self.current_state in ("idle", "listening")) and (self.active_quirk is None) and (t >= self.next_auto_quirk_time):
            self.active_quirk = random.choice(self.QUIRK_NAMES)
            self.quirk_start_time = t
            self.quirk_duration = 1.9 if self.active_quirk == "mini_yawn" else 1.5
            self.next_auto_quirk_time = t + random.uniform(3.0, 5.5)

        self.update()

    # =========================================================================
    # Pure Vector Graphics (QPainter Cyber Mini-Robot Avatar)
    # =========================================================================

    def paintEvent(self, event):
        """Renders 60 FPS cyber capsule and animated vector robot avatar."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)

        w = self.width()
        h = self.height()
        is_folded = (w < 120)

        cfg = self.STATES.get(self.current_state, self.STATES["idle"])
        neon_color = cfg["color"]

        # 1. Capsule Background with Frosting & Cyber Border
        rect = QRectF(0.5, 0.5, w - 1.0, h - 1.0)
        radius = h / 2.0

        bg_color = QColor(7, 11, 19, 235)
        border_pen = QPen(QColor(neon_color.red(), neon_color.green(), neon_color.blue(), 100), 1.2)
        border_pen.setCosmetic(True)

        painter.setBrush(QBrush(bg_color))
        painter.setPen(border_pen)
        painter.drawRoundedRect(rect, radius, radius)

        t = time.time() - self.start_time

        # 2. Render Avatar
        if is_folded:
            # Folded Mode in Menu Bar (Peek-a-boo mini avatar centered on left)
            painter.save()
            # Mini avatar box 20x20
            scale_s = (h - 4.0) / 48.0
            painter.translate(6.0, 2.0)
            painter.scale(scale_s, scale_s)
            self._draw_cyber_robot(painter, t, cfg, is_mini=True)
            painter.restore()

            # Status dot on right
            dot_r = 3.0
            dot_cx = w - 14.0
            dot_cy = h / 2.0
            pulse = 0.5 + 0.5 * math.sin(t * 3.0)
            dot_alpha = int(140 + 115 * pulse)
            painter.setBrush(QBrush(QColor(neon_color.red(), neon_color.green(), neon_color.blue(), dot_alpha)))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(dot_cx, dot_cy), dot_r, dot_r)
        else:
            # Expanded Mode: Full 48x48 animated avatar on the left
            painter.save()
            painter.translate(6.0, 4.0)
            self._draw_cyber_robot(painter, t, cfg, is_mini=False)
            painter.restore()

            # Status Texts (Center)
            text_x = 60.0
            text_w = w - text_x - 36.0

            # Title & Tag
            painter.setPen(QPen(neon_color, 1))
            font_title = painter.font()
            font_title.setStyleHint(QFont.Monospace)
            font_title.setFamily("Menlo")
            font_title.setPointSize(9)
            font_title.setWeight(QFont.Bold)
            painter.setFont(font_title)
            painter.drawText(QRectF(text_x, 10.0, 80.0, 16.0), Qt.AlignLeft | Qt.AlignVCenter, "J.A.R.V.I.S.")

            # Status Text
            painter.setPen(QPen(QColor("#F1F5F9"), 1))
            font_status = painter.font()
            font_status.setStyleHint(QFont.SansSerif)
            font_status.setFamily("-apple-system")
            font_status.setPointSize(10)
            font_status.setWeight(QFont.Medium)
            painter.setFont(font_status)
            painter.drawText(QRectF(text_x + 65.0, 10.0, text_w - 65.0, 16.0), Qt.AlignLeft | Qt.AlignVCenter, f"• {cfg['status']}")

            # Subtext
            subtext_str = self._custom_subtext if self._custom_subtext else cfg["subtext"]
            painter.setPen(QPen(QColor("#94A3B8"), 1))
            font_sub = painter.font()
            font_sub.setStyleHint(QFont.SansSerif)
            font_sub.setFamily("-apple-system")
            font_sub.setPointSize(9)
            font_sub.setWeight(QFont.Normal)
            painter.setFont(font_sub)
            painter.drawText(QRectF(text_x, 28.0, text_w, 18.0), Qt.AlignLeft | Qt.AlignVCenter, subtext_str)

            # Mini Live Wave Indicator (Right edge)
            wave_x = w - 24.0
            wave_y = h / 2.0
            painter.setPen(Qt.NoPen)
            for i in range(3):
                bar_mult = 1.0 if self.current_state == "speaking" else (0.65 if self.current_state == "listening" else 0.25)
                bar_h = 3.0 + abs(math.sin(t * (8.0 + i * 2.5) + i)) * 14.0 * bar_mult
                bx = wave_x + i * 4.0
                by = wave_y - bar_h / 2.0
                painter.setBrush(QBrush(neon_color))
                painter.drawRoundedRect(QRectF(bx, by, 2.0, bar_h), 1.0, 1.0)

    def _draw_cyber_robot(self, painter: QPainter, t: float, cfg: Dict[str, Any], is_mini: bool = False):
        """
        Pure QPainter Vector Renderer of the Cyber Mini-Robot Avatar.
        Normalized to a 48x48 coordinate box matching the visual mockup.
        """
        neon = cfg["color"]
        bg_tint = cfg["bg_tint"]
        visor_tint = cfg["visor_tint"]

        # Evaluate Quirk Envelope (0 -> 1 -> 0 smooth bell curve)
        q_env = 0.0
        q_prog = 0.0
        if self.active_quirk:
            q_prog = (t - self.quirk_start_time) / self.quirk_duration
            if q_prog >= 1.0:
                self.active_quirk = None
            else:
                q_env = math.sin(q_prog * math.pi)

        # Kinematics Computation
        body_y = 0.0
        head_tilt = 0.0
        head_bob_y = 0.0
        look_x = 0.0
        look_y = 0.0
        antenna_angle = math.sin(t * 3.2) * 0.08
        left_paw_y = 0.0
        right_paw_y = 0.0
        left_paw_x = 0.0
        right_paw_x = 0.0

        st = self.current_state
        if st == "speaking":
            body_y = -abs(math.sin(t * 7.5)) * 1.6
            head_tilt = math.sin(t * 5.2) * 0.09
            head_bob_y = -abs(math.cos(t * 7.5)) * 0.7
            antenna_angle = math.sin(t * 11.0) * 0.22
            left_paw_y = -2.2 + math.sin(t * 8.0) * 1.8
            right_paw_y = -2.2 + math.sin(t * 8.0 + math.pi) * 1.8
        elif st == "listening":
            body_y = math.sin(t * 2.6) * 0.6
            head_tilt = -0.11 + math.sin(t * 2.0) * 0.03
            antenna_angle = math.sin(t * 9.0) * 0.25
            left_paw_y = math.sin(t * 2.6) * 0.7
            right_paw_y = math.cos(t * 2.6) * 0.7
        elif st == "thinking":
            body_y = math.sin(t * 2.2) * 0.9
            look_x = math.sin(t * 3.4) * 2.3
            look_y = -0.5
            right_paw_y = -5.5 + math.sin(t * 3.0) * 0.5
            right_paw_x = -2.5
            left_paw_y = math.sin(t * 2.2) * 0.6
        elif st == "running_tool":
            body_y = math.sin(t * 6.0) * 0.45
            look_x = math.sin(t * 9.5) * 2.6
            left_paw_y = -3.8 + math.sin(t * 22.0) * 1.6
            right_paw_y = -3.8 + math.sin(t * 22.0 + math.pi) * 1.6
            left_paw_x = 1.4
            right_paw_x = -1.4
        elif st == "wake_ack":
            body_y = -abs(math.sin(t * 6.8)) * 2.8
            head_tilt = math.sin(t * 6.8) * 0.11
            antenna_angle = math.sin(t * 14.0) * 0.3
            left_paw_y = -6.2 + math.sin(t * 10.0) * 1.2
            right_paw_y = -6.2 + math.cos(t * 10.0) * 1.2
        elif st == "confused":
            body_y = math.sin(t * 2.4) * 0.5
            head_tilt = 0.24 + math.sin(t * 3.5) * 0.04
            left_paw_y = -3.2
            right_paw_y = 0.4
        else:
            # idle gentle breathing
            body_y = math.sin(t * 2.1) * 0.85
            left_paw_y = math.sin(t * 2.1 + 0.5) * 0.9
            right_paw_y = math.sin(t * 2.1 + 0.5) * 0.9

        # Apply Autonomous Quirk Modifiers
        if self.active_quirk == "look_around":
            look_x += math.sin(q_prog * math.pi * 2.0) * 3.0
            head_tilt += math.sin(q_prog * math.pi * 2.0) * 0.12
        elif self.active_quirk == "double_blink":
            antenna_angle += math.sin(q_prog * math.pi * 6.0) * 0.35 * q_env
        elif self.active_quirk == "hum_hop":
            body_y -= abs(math.sin(q_prog * math.pi * 3.0)) * 2.2
            head_tilt += math.sin(q_prog * math.pi * 4.0) * 0.12
            left_paw_y -= q_env * 2.5
            right_paw_y -= q_env * 2.5
        elif self.active_quirk == "mini_yawn":
            head_tilt -= q_env * 0.14
            head_bob_y -= q_env * 0.9
            left_paw_y -= q_env * 5.2
            right_paw_y -= q_env * 5.2
            left_paw_x -= q_env * 1.2
            right_paw_x += q_env * 1.2
        elif self.active_quirk == "curious_nod":
            head_tilt += q_env * 0.18
            head_bob_y += abs(math.sin(q_prog * math.pi * 2.0)) * 1.4

        # Configure cosmetic pens for Retina crispness
        main_pen = QPen(neon, 1.6)
        main_pen.setCosmetic(True)
        thin_pen = QPen(neon, 1.1)
        thin_pen.setCosmetic(True)

        painter.translate(0.0, body_y + 1.2)

        # 1. Torso & Shoulders (Skip or simplify in mini mode)
        if not is_mini:
            torso_path = QPainterPath()
            torso_path.moveTo(12.5, 42.5)
            torso_path.lineTo(12.5, 34.8)
            torso_path.quadTo(12.5, 29.2, 18.2, 29.2)
            torso_path.lineTo(29.8, 29.2)
            torso_path.quadTo(35.5, 29.2, 35.5, 34.8)
            torso_path.lineTo(35.5, 42.5)

            painter.setBrush(QBrush(bg_tint))
            painter.setPen(main_pen)
            painter.drawPath(torso_path)

            # Shoulder Trim
            painter.setPen(thin_pen)
            painter.drawLine(QPointF(12.5, 35.5), QPointF(15.5, 35.5))
            painter.drawLine(QPointF(32.5, 35.5), QPointF(35.5, 35.5))

            # Chest Core / Equalizer
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(QRectF(18.2, 32.5, 11.6, 7.6), 2.0, 2.0)

            if st == "speaking" or self.active_quirk == "hum_hop":
                b1 = 2.0 + abs(math.sin(t * 14.0)) * 3.4
                b2 = 2.2 + abs(math.sin(t * 11.0 + 1.2)) * 3.8
                b3 = 2.0 + abs(math.cos(t * 13.0)) * 3.4
                painter.setBrush(QBrush(neon))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(QRectF(20.0, 38.6 - b1, 1.6, b1), 0.7, 0.7)
                painter.drawRoundedRect(QRectF(23.2, 38.6 - b2, 1.6, b2), 0.7, 0.7)
                painter.drawRoundedRect(QRectF(26.4, 38.6 - b3, 1.6, b3), 0.7, 0.7)
            elif st in ("running_tool", "thinking"):
                active_dot = int(t * (10 if st == "running_tool" else 4)) % 3
                painter.setPen(Qt.NoPen)
                for idx, cx in enumerate([20.5, 24.0, 27.5]):
                    alpha = 255 if idx == active_dot else 70
                    painter.setBrush(QBrush(QColor(neon.red(), neon.green(), neon.blue(), alpha)))
                    painter.drawEllipse(QPointF(cx, 36.3), 1.25, 1.25)
            else:
                pulse_w = 5.0 + math.sin(t * 3.0) * 1.4
                painter.setBrush(QBrush(neon))
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(QRectF(24.0 - pulse_w / 2.0, 35.5, pulse_w, 1.6), 0.8, 0.8)

            # Neck Connectors
            painter.setPen(main_pen)
            painter.drawLine(QPointF(21.0, 26.2), QPointF(21.0, 29.2))
            painter.drawLine(QPointF(27.0, 26.2), QPointF(27.0, 29.2))

        # 2. Head Group (Rotates around neck 24, 25)
        painter.save()
        painter.translate(24.0, 25.0 + head_bob_y)
        painter.rotate(math.degrees(head_tilt))
        painter.translate(-24.0, -25.0)

        # Antenna
        painter.save()
        painter.translate(24.0, 8.2)
        painter.rotate(math.degrees(antenna_angle))
        painter.setPen(main_pen)
        painter.drawLine(QPointF(0.0, 0.0), QPointF(0.0, -4.6))
        painter.setBrush(QBrush(neon))
        painter.setPen(Qt.NoPen)
        tip_r = 1.85 if st == "listening" else 1.5
        painter.drawEllipse(QPointF(0.0, -5.3), tip_r, tip_r)
        painter.restore()

        # Ear Pods
        painter.setBrush(Qt.NoBrush)
        painter.setPen(thin_pen)
        painter.drawRoundedRect(QRectF(8.6, 13.8, 2.4, 7.2), 1.1, 1.1)
        painter.drawRoundedRect(QRectF(37.0, 13.8, 2.4, 7.2), 1.1, 1.1)

        # Head Shell
        painter.setBrush(QBrush(bg_tint))
        painter.setPen(main_pen)
        painter.drawRoundedRect(QRectF(11.4, 8.2, 25.2, 18.0), 6.8, 6.8)

        # Inner Dark Visor
        painter.setBrush(QBrush(visor_tint))
        painter.setPen(thin_pen)
        painter.drawRoundedRect(QRectF(13.8, 10.6, 20.4, 13.2), 4.6, 4.6)

        # 3. Eyes & Mouth Inside Visor
        painter.save()
        painter.translate(look_x, look_y)

        # Blink calculation
        periodic_blink = (t % 3.6) > 3.46
        quirk_blink = (self.active_quirk == "double_blink") and (
            (0.15 < q_prog < 0.32) or (0.52 < q_prog < 0.70)
        )
        is_blinking = periodic_blink or quirk_blink or (self.active_quirk == "mini_yawn")

        # --- EYES ---
        eye_pen = QPen(neon, 1.65)
        eye_pen.setCosmetic(True)
        painter.setPen(eye_pen)

        if is_blinking:
            # Closed blink lines
            painter.drawLine(QPointF(16.6, 16.0), QPointF(20.6, 16.0))
            painter.drawLine(QPointF(27.4, 16.0), QPointF(31.4, 16.0))
        elif st in ("speaking", "wake_ack") or self.active_quirk == "hum_hop":
            # Happy Arched Eyes (^ ^)
            p1 = QPainterPath()
            p1.moveTo(16.6, 16.6)
            p1.quadTo(18.6, 13.6, 20.6, 16.6)
            p2 = QPainterPath()
            p2.moveTo(27.4, 16.6)
            p2.quadTo(29.4, 13.6, 31.4, 16.6)
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(p1)
            painter.drawPath(p2)
        elif st in ("thinking", "running_tool"):
            # Visor Scanning Bars
            bar_w = 4.8 if st == "running_tool" else 5.4
            painter.setBrush(QBrush(neon))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(QRectF(16.4, 14.6, bar_w, 2.6), 1.2, 1.2)
            painter.drawRoundedRect(QRectF(26.8, 14.6, bar_w, 2.6), 1.2, 1.2)
        elif st == "confused":
            # Left eye circle O, right eye slit -
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(18.6, 15.6), 2.2, 2.2)
            painter.drawLine(QPointF(27.2, 16.0), QPointF(31.4, 15.4))
        elif st == "listening":
            # Sparkly attentive round eyes
            painter.setBrush(Qt.NoBrush)
            painter.drawEllipse(QPointF(18.6, 15.6), 2.25, 2.25)
            painter.drawEllipse(QPointF(29.4, 15.6), 2.25, 2.25)
            painter.setBrush(QBrush(QColor("#FFFFFF")))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(19.3, 14.9), 0.7, 0.7)
            painter.drawEllipse(QPointF(30.1, 14.9), 0.7, 0.7)
        else:
            # Soft friendly dots
            painter.setBrush(QBrush(neon))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(QPointF(18.6, 15.8), 1.75, 1.75)
            painter.drawEllipse(QPointF(29.4, 15.8), 1.75, 1.75)

        # --- MOUTH ---
        mouth_pen = QPen(neon, 1.45)
        mouth_pen.setCosmetic(True)
        painter.setPen(mouth_pen)
        painter.setBrush(Qt.NoBrush)

        mouth_cx = 24.0
        mouth_cy = 20.4

        if self.active_quirk == "mini_yawn":
            yawn_r = 1.0 + q_env * 2.1
            painter.drawEllipse(QPointF(mouth_cx, mouth_cy - 0.2), yawn_r * 0.85, yawn_r)
        elif self.active_quirk == "hum_hop":
            hum_r = 1.1 + abs(math.sin(t * 14.0)) * 0.9
            painter.drawEllipse(QPointF(mouth_cx, mouth_cy), hum_r, hum_r)
        elif st == "speaking":
            syllable = abs(math.sin(t * 14.5) * math.cos(t * 6.2))
            mouth_w = 3.4 + math.sin(t * 10.0) * 1.4
            mouth_h = 0.8 + syllable * 3.1
            if syllable > 0.55:
                # Open D-Shape mouth
                d_path = QPainterPath()
                d_path.moveTo(mouth_cx - mouth_w / 2.0, mouth_cy - 0.7)
                d_path.lineTo(mouth_cx + mouth_w / 2.0, mouth_cy - 0.7)
                d_path.quadTo(mouth_cx, mouth_cy + mouth_h + 0.8, mouth_cx - mouth_w / 2.0, mouth_cy - 0.7)
                painter.setBrush(QBrush(QColor(neon.red(), neon.green(), neon.blue(), 90)))
                painter.drawPath(d_path)
            else:
                painter.drawRoundedRect(QRectF(mouth_cx - mouth_w / 2.0, mouth_cy - mouth_h / 2.0, mouth_w, max(1.2, mouth_h)), 1.4, 1.4)
        elif st == "listening":
            pulse_o = 1.35 + math.sin(t * 5.0) * 0.2
            painter.drawEllipse(QPointF(mouth_cx, mouth_cy), pulse_o, pulse_o)
        elif st == "thinking":
            # Wavy ponder ~
            shift = math.sin(t * 5.0) * 0.5
            w_path = QPainterPath()
            w_path.moveTo(21.2, mouth_cy + shift)
            w_path.quadTo(22.6, mouth_cy - 1.2 - shift, 24.0, mouth_cy)
            w_path.quadTo(25.4, mouth_cy + 1.2 + shift, 26.8, mouth_cy - shift)
            painter.drawPath(w_path)
        elif st == "running_tool":
            painter.drawLine(QPointF(21.4, mouth_cy), QPointF(26.6, mouth_cy - 0.3))
        elif st == "wake_ack":
            d_path = QPainterPath()
            d_path.moveTo(20.6, mouth_cy - 0.8)
            d_path.lineTo(27.4, mouth_cy - 0.8)
            d_path.quadTo(24.0, mouth_cy + 3.2, 20.6, mouth_cy - 0.8)
            painter.setBrush(QBrush(QColor(neon.red(), neon.green(), neon.blue(), 80)))
            painter.drawPath(d_path)
        elif st == "confused":
            c_path = QPainterPath()
            c_path.moveTo(21.4, mouth_cy + 0.6)
            c_path.quadTo(24.0, mouth_cy - 1.0, 26.6, mouth_cy + 0.5)
            painter.drawPath(c_path)
        else:
            # Idle gentle smile
            s_path = QPainterPath()
            s_path.moveTo(21.6, mouth_cy - 0.3)
            s_path.quadTo(24.0, mouth_cy + 1.3, 26.4, mouth_cy - 0.3)
            painter.drawPath(s_path)

        painter.restore()  # End gaze offset
        painter.restore()  # End head rotation

        # Confused floating '?' mark
        if st == "confused":
            q_float = math.sin(t * 4.5) * 1.2
            painter.setPen(QPen(neon, 1))
            font_confused = QFont("Menlo", 7, QFont.Bold)
            font_confused.setStyleHint(QFont.Monospace)
            painter.setFont(font_confused)
            painter.drawText(QPointF(39.0, 11.5 + q_float), "?")

        # 4. Floating Paws (Hands)
        if not is_mini:
            painter.setBrush(QBrush(bg_tint))
            painter.setPen(main_pen)
            # Left Paw
            painter.drawRoundedRect(QRectF(7.2 + left_paw_x, 34.5 + left_paw_y, 3.6, 4.6), 1.8, 1.8)
            # Right Paw
            painter.drawRoundedRect(QRectF(37.2 + right_paw_x, 34.5 + right_paw_y, 3.6, 4.6), 1.8, 1.8)
