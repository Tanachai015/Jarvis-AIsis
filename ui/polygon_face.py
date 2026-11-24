"""
High-Poly 3D Interactive Holographic Face Renderer for K.A.R.I.S. (J.A.R.V.I.S. JR.)
Pure Vector Polygon Mesh (98 Vertices / 160+ Triangles) rendered with QPainter.

Features:
- Rounded-Rectangle Cyber Robot Helmet with dense multi-ring beveled triangulation
- 3D Dual-layer Wireframe Volume (faint back-facing facets for transparent holographic depth)
- Front-facing Facets bucketed by surface normal with depth-shaded translucent fills and glowing edges
- Digital Hologram World: 3D orbiting bokeh energy nodes, HUD arcs, and Floating Live Telemetry Callouts
- Bottom Holographic Telemetry Status Bar showing real-time K.A.R.I.S. thought/action stream
- Dynamic Holographic Scanline Plane sweeping vertically across the robot
- Reactive Audio Waves & Neural Synapse Sparks
- Natural Kinematics: breathing swell, idle head bob, micro-saccades, spring-damped gaze tracking, and jaw drop
"""

import math
import time
from typing import List, Tuple, Optional

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import (
    QPainter,
    QPolygonF,
    QColor,
    QPen,
    QBrush,
    QFont,
    QRadialGradient,
    QPainterPath,
)


class HighPolyKarisRenderer:
    """
    Renders high-density 3D holographic faceted Rounded-Rectangle K.A.R.I.S. robot
    with Digital Hologram World atmosphere and Live Telemetry Callouts.
    """

    # 98 High-Poly Rounded-Rectangle K.A.R.I.S. Robot 3D Vertices (x, y, z)
    VERTICES: List[List[float]] = [
        # --- Crown & Rounded-Rectangle Forehead (0..12) ---
        [0.0, 3.7, 0.5],     # 0: Crown top center
        [-1.3, 3.65, 0.8],   # 1: Crown top left
        [1.3, 3.65, 0.8],    # 2: Crown top right
        [-2.5, 3.35, 0.9],   # 3: Top-left rounded corner upper
        [2.5, 3.35, 0.9],    # 4: Top-right rounded corner upper
        [-3.15, 2.65, 0.7],  # 5: Top-left rounded corner side
        [3.15, 2.65, 0.7],   # 6: Top-right rounded corner side
        [0.0, 3.05, 1.75],   # 7: Forehead upper center
        [-1.4, 2.95, 1.7],   # 8: Forehead upper left
        [1.4, 2.95, 1.7],    # 9: Forehead upper right
        [-2.4, 2.35, 1.55],  # 10: Forehead mid left
        [2.4, 2.35, 1.55],   # 11: Forehead mid right
        [0.0, 2.25, 2.15],   # 12: Forehead lower / Brow center

        # --- Rounded-Rectangle Visor Frame & Eyes (13..24) ---
        [-1.45, 2.05, 2.2],  # 13: Visor top left
        [1.45, 2.05, 2.2],   # 14: Visor top right
        [-2.45, 1.45, 1.9],  # 15: Visor corner top-left
        [2.45, 1.45, 1.9],   # 16: Visor corner top-right
        [-2.55, 0.45, 1.95], # 17: Visor corner bot-left
        [2.55, 0.45, 1.95],  # 18: Visor corner bot-right
        [-1.5, -0.15, 2.1],  # 19: Visor bot left
        [1.5, -0.15, 2.1],   # 20: Visor bot right
        [0.0, -0.25, 2.2],   # 21: Visor bot center
        [0.0, 0.9, 2.15],    # 22: Visor inner bridge
        [-1.1, 0.9, 2.3],    # 23: Left eye center
        [1.1, 0.9, 2.3],     # 24: Right eye center

        # --- Rounded-Rectangle Cheeks, Jaw & Chin (25..39) ---
        [-3.35, 1.75, 0.55], # 25: Side wall upper left
        [3.35, 1.75, 0.55],  # 26: Side wall upper right
        [-3.35, 0.55, 0.55], # 27: Side wall mid left
        [3.35, 0.55, 0.55],  # 28: Side wall mid right
        [-3.15, -0.75, 0.7], # 29: Side wall lower left
        [3.15, -0.75, 0.7],  # 30: Side wall lower right
        [-2.55, -1.75, 1.0], # 31: Bot-left rounded corner (moves with jaw)
        [2.55, -1.75, 1.0],  # 32: Bot-right rounded corner (moves with jaw)
        [-1.45, -2.35, 1.25],# 33: Jaw bot left (moves with jaw)
        [1.45, -2.35, 1.25], # 34: Jaw bot right (moves with jaw)
        [0.0, -2.5, 1.45],   # 35: Chin bottom center (moves with jaw)
        [-1.45, -1.25, 1.75],# 36: Cheek inner left
        [1.45, -1.25, 1.75], # 37: Cheek inner right
        [0.0, -1.05, 1.9],   # 38: Upper mouth / Philtrum
        [0.0, -1.8, 1.75],   # 39: Lower mouth / Chin top (moves with jaw)

        # --- Ear Sensor Pods Left & Right (40..51) ---
        [-3.35, 1.25, -0.3], # 40: Ear root top left
        [-3.35, 0.05, -0.3], # 41: Ear root bot left
        [-4.55, 0.65, 0.2],  # 42: Ear outer tip front left
        [-4.55, 0.65, -0.8], # 43: Ear outer tip back left
        [-3.95, 1.85, -0.3], # 44: Ear fin top left
        [-3.95, -0.55, -0.3],# 45: Ear fin bot left
        [3.35, 1.25, -0.3],  # 46: Ear root top right
        [3.35, 0.05, -0.3],  # 47: Ear root bot right
        [4.55, 0.65, 0.2],   # 48: Ear outer tip front right
        [4.55, 0.65, -0.8],  # 49: Ear outer tip back right
        [3.95, 1.85, -0.3],  # 50: Ear fin top right
        [3.95, -0.55, -0.3], # 51: Ear fin bot right

        # --- Antenna Stem & Diamond Crystal Apex (52..58) ---
        [0.0, 4.45, 0.0],    # 52: Antenna stem mid
        [0.0, 5.2, 0.0],     # 53: Antenna crystal base
        [0.0, 5.75, 0.55],   # 54: Crystal diamond front
        [0.0, 5.75, -0.55],  # 55: Crystal diamond back
        [-0.55, 5.75, 0.0],  # 56: Crystal diamond left
        [0.55, 5.75, 0.0],   # 57: Crystal diamond right
        [0.0, 6.65, 0.0],    # 58: Crystal diamond top apex

        # --- Rear Rounded-Rectangle Cranium Shell (59..70) ---
        [0.0, 3.45, -1.9],   # 59: Rear crown center
        [-2.3, 3.1, -1.6],   # 60: Rear crown left
        [2.3, 3.1, -1.6],    # 61: Rear crown right
        [-3.1, 1.8, -1.6],   # 62: Rear side upper left
        [3.1, 1.8, -1.6],    # 63: Rear side upper right
        [-3.0, -0.4, -1.5],  # 64: Rear side lower left
        [3.0, -0.4, -1.5],   # 65: Rear side lower right
        [0.0, 1.35, -2.35],  # 66: Rear cranium center
        [-1.8, 1.35, -2.0],  # 67: Rear mid left
        [1.8, 1.35, -2.0],   # 68: Rear mid right
        [0.0, -1.1, -2.0],   # 69: Skull base center
        [-2.0, -1.4, -1.4],  # 70: Skull base left
        [2.0, -1.4, -1.4],   # 71: Skull base right

        # --- Neck, Collar & Torso Chest Core (72..89) ---
        [-0.95, -2.8, 0.0],  # 72: Neck strut left
        [0.95, -2.8, 0.0],   # 73: Neck strut right
        [0.0, -2.8, -0.85],  # 74: Neck rear center
        [0.0, -3.7, 1.4],    # 75: Collar center front
        [-1.8, -3.7, 1.15],  # 76: Collar left front
        [1.8, -3.7, 1.15],   # 77: Collar right front
        [-3.7, -4.0, 0.0],   # 78: Shoulder left
        [3.7, -4.0, 0.0],    # 79: Shoulder right
        [0.0, -4.6, 1.55],   # 80: Chest Core center
        [-1.6, -4.6, 1.35],  # 81: Chest Core left
        [1.6, -4.6, 1.35],   # 82: Chest Core right
        [0.0, -5.5, 1.2],    # 83: Torso bottom center
        [-2.7, -5.3, 0.4],   # 84: Torso bottom left
        [2.7, -5.3, 0.4],    # 85: Torso bottom right
        [0.0, -4.1, -1.6],   # 86: Back torso top
        [-2.5, -4.5, -1.2],  # 87: Back torso left
        [2.5, -4.5, -1.2],   # 88: Back torso right
        [0.0, -5.3, -1.4],   # 89: Back torso bottom

        # --- Extra Bevel & Cheek Sub-facets for High-Poly Density (90..97) ---
        [-2.95, 1.2, 1.25],  # 90: Cheek bevel upper left
        [2.95, 1.2, 1.25],   # 91: Cheek bevel upper right
        [-2.9, -0.1, 1.3],   # 92: Cheek bevel mid left
        [2.9, -0.1, 1.3],    # 93: Cheek bevel mid right
        [-2.15, -1.15, 1.45],# 94: Cheek bevel lower left
        [2.15, -1.15, 1.45], # 95: Cheek bevel lower right
        [-0.75, -1.9, 1.65], # 96: Mouth bevel left (moves with jaw)
        [0.75, -1.9, 1.65],  # 97: Mouth bevel right (moves with jaw)
    ]

    # 160+ Triangular Facets for High-Poly Rounded-Rectangle Mesh
    TRIANGLES: List[List[int]] = [
        # Forehead Top & Rounded Crown Corners
        [0, 1, 7], [0, 7, 2], [1, 8, 7], [2, 7, 9],
        [1, 3, 8], [2, 9, 4], [3, 5, 10], [4, 11, 6],
        [3, 10, 8], [4, 9, 11], [7, 8, 12], [7, 12, 9],
        [8, 13, 12], [9, 12, 14], [8, 10, 13], [9, 14, 11],
        [10, 15, 13], [11, 14, 16], [5, 25, 10], [6, 11, 26],
        [10, 25, 90], [11, 91, 26], [10, 90, 15], [11, 16, 91],

        # Rounded-Rectangle Visor Frame (Upper & Side Bevels)
        [12, 13, 22], [12, 22, 14], [13, 15, 22], [14, 22, 16],
        [15, 17, 22], [16, 22, 18], [17, 19, 22], [18, 22, 20],
        [19, 21, 22], [20, 22, 21],

        # High-Poly Cheek Bevel Rings (Left & Right)
        [25, 27, 90], [26, 91, 28], [90, 27, 92], [91, 28, 93],
        [15, 90, 17], [16, 18, 91], [90, 92, 17], [91, 18, 93],
        [27, 29, 92], [28, 93, 30], [17, 92, 94], [18, 95, 93],
        [17, 94, 19], [18, 20, 95], [92, 29, 94], [93, 95, 30],
        [29, 31, 94], [30, 95, 32],

        # Mouth, Jaw & Rounded Chin
        [19, 36, 21], [20, 21, 37], [19, 94, 36], [20, 37, 95],
        [21, 36, 38], [21, 38, 37], [94, 31, 33], [95, 34, 32],
        [94, 33, 36], [95, 37, 34], [36, 33, 96], [37, 97, 34],
        [36, 96, 38], [37, 38, 97], [38, 96, 39], [38, 39, 97],
        [33, 35, 96], [34, 97, 35], [96, 35, 39], [97, 39, 35],

        # Ear Pod Left (3D Prism)
        [40, 42, 44], [40, 44, 43], [41, 45, 42], [41, 43, 45],
        [42, 45, 43], [42, 43, 44], [25, 40, 41], [25, 41, 27],
        [27, 41, 29], [5, 40, 25],

        # Ear Pod Right (3D Prism)
        [46, 50, 48], [46, 49, 50], [47, 48, 51], [47, 51, 49],
        [48, 49, 51], [48, 50, 49], [26, 47, 46], [26, 28, 47],
        [28, 47, 30], [6, 26, 46],

        # Diamond Antenna Crystal (8 facets)
        [53, 54, 56], [53, 57, 54], [53, 56, 55], [53, 55, 57],
        [58, 56, 54], [58, 54, 57], [58, 55, 56], [58, 57, 55],

        # Rear Rounded-Rectangle Cranium Volume (Back-facing facets)
        [0, 60, 59], [0, 59, 61], [0, 1, 60], [0, 61, 2],
        [1, 3, 60], [2, 61, 4], [3, 5, 60], [4, 61, 6],
        [5, 62, 60], [6, 61, 63], [5, 25, 62], [6, 63, 26],
        [59, 60, 67], [59, 67, 66], [59, 66, 68], [59, 68, 61],
        [60, 62, 67], [61, 68, 63], [62, 64, 67], [63, 68, 65],
        [66, 67, 69], [66, 69, 68], [67, 64, 70], [68, 71, 65],
        [67, 70, 69], [68, 69, 71], [64, 29, 70], [65, 71, 30],
        [29, 31, 70], [30, 71, 32],

        # Neck & Collar
        [35, 33, 72], [35, 73, 34], [35, 72, 75], [35, 75, 73],
        [69, 70, 74], [69, 74, 71], [70, 72, 74], [71, 74, 73],
        [72, 76, 75], [73, 75, 77], [72, 78, 76], [73, 77, 79],

        # Torso & Chest Core
        [75, 76, 81], [75, 81, 80], [75, 80, 82], [75, 82, 77],
        [76, 78, 81], [77, 82, 79], [78, 84, 81], [79, 82, 85],
        [80, 81, 83], [80, 83, 82], [81, 84, 83], [82, 83, 85],

        # Back Torso
        [74, 87, 86], [74, 86, 88], [78, 87, 74], [79, 74, 88],
        [86, 87, 89], [86, 89, 88], [87, 84, 89], [88, 89, 85],
    ]

    KEY_NODES = {0, 3, 4, 12, 15, 16, 17, 18, 21, 23, 24, 31, 32, 35, 42, 48, 58, 80}

    # 3D Digital Bokeh / Hologram Orbs (angle_offset, radius_mult, y_offset, speed, size, color_type)
    HOLO_ORBS = [
        (0.4, 5.4, -2.5, 0.28, 3.2, "amber"),
        (1.6, 6.2, 1.8, -0.22, 4.0, "cyan"),
        (2.7, 4.8, -1.2, 0.35, 2.8, "violet"),
        (3.8, 6.5, 2.6, -0.18, 3.6, "amber"),
        (4.9, 5.1, 0.4, 0.25, 2.5, "mint"),
        (5.8, 6.0, -3.1, -0.30, 3.4, "cyan"),
        (0.9, 7.1, 0.8, 0.14, 2.2, "amber"),
        (3.1, 6.9, -1.9, -0.16, 2.6, "violet"),
    ]

    def __init__(self):
        self.target_yaw: float = 0.0
        self.target_pitch: float = 0.0
        self.cur_yaw: float = 0.0
        self.cur_pitch: float = 0.0
        self.cur_roll: float = 0.0
        self.start_time: float = time.time()

        # Cached fonts to avoid macOS font-alias lookup latency
        self._font_tele = QFont("Menlo", 7, QFont.Bold)
        self._font_tele_sub = QFont("Menlo", 6, QFont.Normal)
        self._font_bar = QFont("Menlo", 8, QFont.Bold)

    def set_gaze_target(self, yaw: float, pitch: float):
        """Sets gaze target in radians for 3D spring look tracking."""
        self.target_yaw = max(-0.65, min(0.65, yaw))
        self.target_pitch = max(-0.45, min(0.45, pitch))

    def reset_gaze(self):
        """Resets gaze back to center."""
        self.target_yaw = 0.0
        self.target_pitch = 0.0

    def update(self, dt: float = 0.016):
        """Advances spring damping, kinematics and timer ticks."""
        rate = max(0.05, min(1.0, dt * 9.0))
        self.cur_yaw += (self.target_yaw - self.cur_yaw) * rate
        self.cur_pitch += (self.target_pitch - self.cur_pitch) * rate

    def _get_telemetry_labels(self, state: str, live_telemetry: Optional[str]) -> Tuple[str, str, str, str]:
        """Returns (left_callout, top_right_callout, right_callout, bottom_bar_text) for current state."""
        st = state.lower().strip()
        clean_live = (live_telemetry or "").strip()
        if len(clean_live) > 26:
            clean_live = clean_live[:24] + ".."

        if st == "listening":
            return (
                "AUDIO • SILERO VAD ACTIVE",
                "MIC • 16KHZ STREAM",
                clean_live.upper() if clean_live else "INPUT • LISTENING VOICE",
                "LISTENING • AWAITING BOSS COMMAND",
            )
        elif st in ("thinking", "running_tool"):
            task_txt = clean_live.upper() if clean_live else "ANALYZING CONTEXT"
            return (
                "NEURAL • GEMINI COGNITION",
                "AGENT • ACTIVE THREAD",
                f"TOOL • {task_txt}",
                f"RUNNING • {task_txt}",
            )
        elif st == "speaking":
            return (
                "SYNTH • VOICE PIPELINE",
                "OUTPUT • DUAL STREAM",
                clean_live.upper() if clean_live else "SPEECH • ACTIVE REPLY",
                "SPEAKING • DELIVERING RESPONSE",
            )
        elif st == "confused":
            return (
                "GATE • AMBIGUITY CHECK",
                "STATUS • CLARIFYING",
                clean_live.upper() if clean_live else "CONFIRM • AWAITING BOSS",
                "PAUSED • AWAITING CONFIRMATION",
            )
        elif st == "wake_ack":
            return (
                "WAKE • HEY JARVIS ACK",
                "SENSOR • TRIGGERED",
                "READY • STANDBY ENGAGED",
                "WAKE ACK • READY TO LISTEN",
            )
        else:
            return (
                "CORE • K.A.R.I.S. MESH",
                "MODE • STANDBY GUARD",
                clean_live.upper() if clean_live else "SYSTEM • ALL NOMINAL",
                "STANDBY • READY FOR COMMAND",
            )

    def render(
        self,
        painter: QPainter,
        width: int = 512,
        height: int = 374,
        state: str = "idle",
        now: Optional[float] = None,
        cx: Optional[float] = None,
        cy: Optional[float] = None,
        scale: Optional[float] = None,
        live_telemetry: Optional[str] = None,
    ):
        """
        Renders complete 3D holographic Rounded-Rectangle K.A.R.I.S. robot
        with Digital Hologram World atmosphere and Live Telemetry Callouts.
        """
        st = state.lower().strip()
        t = (time.time() - self.start_time) if now is None else now

        # Color Theme Palette based on state
        if st == "speaking":
            neon = QColor("#00E5FF")
            accent = QColor("#22D3EE")
        elif st == "listening":
            neon = QColor("#00FFD1")
            accent = QColor("#34D399")
        elif st in ("thinking", "running_tool"):
            neon = QColor("#38BDF8")
            accent = QColor("#60A5FA")
        elif st == "confused":
            neon = QColor("#FBBF24")
            accent = QColor("#F59E0B")
        elif st == "wake_ack":
            neon = QColor("#00FFD1")
            accent = QColor("#00E5FF")
        else:
            neon = QColor("#00E5FF")
            accent = QColor("#00FFD1")

        # Fallback coordinate settings
        if cx is None:
            cx = width * 0.50
        if cy is None:
            cy = height * 0.50
        if scale is None:
            scale = min(width, height) * 0.050
        elif scale < 5.0:
            scale = scale * 7.2

        # -------------------------------------------------------------
        # 1. Digital Hologram World Atmosphere (Depth Glow + Bokeh Orbs)
        # -------------------------------------------------------------
        glow_r = scale * 8.8
        glow = QRadialGradient(cx, cy, glow_r)
        glow.setColorAt(0.0, QColor(neon.red(), neon.green(), neon.blue(), 46))
        glow.setColorAt(0.45, QColor(neon.red(), neon.green(), neon.blue(), 18))
        glow.setColorAt(0.80, QColor(10, 30, 50, 8))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(QRectF(cx - glow_r, cy - glow_r, glow_r * 2.0, glow_r * 2.0), QBrush(glow))

        # Orbiting 3D Bokeh Data Particles (inspired by digital world background)
        for idx, (ang0, r_mult, y_off, spd, orb_sz, col_kind) in enumerate(self.HOLO_ORBS):
            ang = ang0 + t * spd
            ox = cx + math.cos(ang) * (scale * r_mult)
            oz = math.sin(ang)
            oy = cy + y_off * scale * 0.75 + math.sin(t * 0.9 + idx) * 4.0
            depth_alpha = 0.45 + 0.55 * ((oz + 1.0) * 0.5)

            if col_kind == "amber":
                o_col = QColor(251, 191, 36, int(170 * depth_alpha))
            elif col_kind == "violet":
                o_col = QColor(192, 132, 252, int(170 * depth_alpha))
            elif col_kind == "mint":
                o_col = QColor(0, 255, 209, int(175 * depth_alpha))
            else:
                o_col = QColor(neon.red(), neon.green(), neon.blue(), int(175 * depth_alpha))

            # Soft bokeh halo
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(QColor(o_col.red(), o_col.green(), o_col.blue(), int(45 * depth_alpha))))
            painter.drawEllipse(QPointF(ox, oy), orb_sz * 2.4, orb_sz * 2.4)
            # Core dot
            painter.setBrush(QBrush(o_col))
            painter.drawEllipse(QPointF(ox, oy), orb_sz * 0.7, orb_sz * 0.7)

        # -------------------------------------------------------------
        # 2. Concentric Orbital HUD Rings, Arcs & Audio Ripples
        # -------------------------------------------------------------
        r1 = scale * 7.1
        r2 = scale * 6.0
        r3 = scale * 4.9
        painter.save()
        painter.translate(cx, cy)

        # Base Outer Orbital Ring
        p1 = QPen(QColor(neon.red(), neon.green(), neon.blue(), 38), 1.0)
        p1.setCosmetic(True)
        painter.setPen(p1)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(0.0, 0.0), r1, r1)

        # Rotating Dashed Orbital Ring
        rot_speed = 1.6 if st in ("thinking", "running_tool") else 0.4
        painter.save()
        painter.rotate(math.degrees(t * rot_speed))
        p2 = QPen(QColor(accent.red(), accent.green(), accent.blue(), 80), 1.2, Qt.DashLine)
        p2.setCosmetic(True)
        p2.setDashPattern([18.0, 10.0, 4.0, 10.0])
        painter.setPen(p2)
        painter.drawEllipse(QPointF(0.0, 0.0), r2, r2)
        painter.restore()

        # Counter-rotating Segmented Inner HUD Arc
        painter.save()
        painter.rotate(-math.degrees(t * 0.25))
        p3 = QPen(QColor(neon.red(), neon.green(), neon.blue(), 55), 1.5)
        p3.setCosmetic(True)
        painter.setPen(p3)
        painter.drawArc(QRectF(-r3, -r3, r3 * 2, r3 * 2), 20 * 16, 70 * 16)
        painter.drawArc(QRectF(-r3, -r3, r3 * 2, r3 * 2), 200 * 16, 70 * 16)
        painter.restore()
        painter.restore()

        # Reactive Audio Ripples
        if st == "speaking":
            painter.save()
            painter.translate(cx, cy)
            for i in range(3):
                wave_t = (t * 1.8 + i * 0.33) % 1.0
                wave_r = scale * 3.8 + wave_t * scale * 4.5
                wave_alpha = int(95 * (1.0 - wave_t))
                w_pen = QPen(QColor(neon.red(), neon.green(), neon.blue(), wave_alpha), 1.3)
                w_pen.setCosmetic(True)
                painter.setPen(w_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(0.0, 0.0), wave_r, wave_r * 0.94)
            painter.restore()
        elif st == "listening":
            painter.save()
            painter.translate(cx, cy)
            for i in range(2):
                wave_t = (1.0 - (t * 1.5 + i * 0.5) % 1.0)
                wave_r = scale * 3.4 + wave_t * scale * 4.2
                wave_alpha = int(85 * wave_t)
                w_pen = QPen(QColor(accent.red(), accent.green(), accent.blue(), wave_alpha), 1.1, Qt.DotLine)
                w_pen.setCosmetic(True)
                painter.setPen(w_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(0.0, 0.0), wave_r, wave_r)
            painter.restore()

        # -------------------------------------------------------------
        # 3. Kinematics & 3D Projection Setup
        # -------------------------------------------------------------
        idle_sway_x = math.sin(t * 0.75) * 0.038
        idle_sway_y = math.cos(t * 0.60) * 0.025
        yaw = self.cur_yaw + idle_sway_x
        pitch = self.cur_pitch + idle_sway_y
        roll = math.sin(t * 0.35) * 0.025

        breath = 1.0 + math.sin(t * 1.5) * 0.018
        bob = math.sin(t * 1.5) * 2.0

        jaw_drop = 0.0
        if st == "speaking":
            jaw_drop = abs(math.sin(t * 14.0) * math.cos(t * 6.5)) * 0.42

        cyaw, syaw = math.cos(yaw), math.sin(yaw)
        cpitch, spitch = math.cos(pitch), math.sin(pitch)
        croll, sroll = math.cos(roll), math.sin(roll)

        jaw_indices = {31, 32, 33, 34, 35, 39, 96, 97}
        proj_pts: List[Tuple[float, float, float]] = []
        for idx, (vx, vy, vz) in enumerate(self.VERTICES):
            if idx in jaw_indices:
                vy -= jaw_drop

            vx *= breath
            vy *= breath
            vz *= breath

            # Yaw (Y axis)
            x1 = vx * cyaw + vz * syaw
            z1 = -vx * syaw + vz * cyaw
            # Pitch (X axis)
            y2 = vy * cpitch - z1 * spitch
            z2 = vy * spitch + z1 * cpitch
            # Roll (Z axis)
            x3 = x1 * croll - y2 * sroll
            y3 = x1 * sroll + y2 * croll

            fov = 18.0 / max(4.0, 18.0 - z2)
            px = cx + x3 * scale * fov
            py = cy - y3 * scale * fov + bob
            proj_pts.append((px, py, z2))

        # -------------------------------------------------------------
        # 4. Triangles Normal Calculation & Bucketing
        # -------------------------------------------------------------
        backs: List[int] = []
        fronts: List[Tuple[int, float, float]] = []

        scan_t = (t * 0.38) % 1.0
        scan_y = -5.4 + scan_t * 12.1
        scans: List[int] = []

        for idx, (a, b, c) in enumerate(self.TRIANGLES):
            p0 = proj_pts[a]
            p1 = proj_pts[b]
            p2 = proj_pts[c]

            ux = p1[0] - p0[0]
            uy = p1[1] - p0[1]
            vx = p2[0] - p0[0]
            vy = p2[1] - p0[1]

            cpz = ux * vy - uy * vx
            if cpz <= 0:
                backs.append(idx)
            else:
                avg_z = (p0[2] + p1[2] + p2[2]) / 3.0
                fronts.append((idx, cpz, avg_z))

                orig_avg_y = (self.VERTICES[a][1] + self.VERTICES[b][1] + self.VERTICES[c][1]) / 3.0
                if abs(orig_avg_y - scan_y) < 0.72:
                    scans.append(idx)

        # -------------------------------------------------------------
        # 5. Draw Back-facing Wireframe (Holographic Depth)
        # -------------------------------------------------------------
        back_pen = QPen(QColor(neon.red(), neon.green(), neon.blue(), 30), 0.75)
        back_pen.setCosmetic(True)
        painter.setPen(back_pen)
        painter.setBrush(Qt.NoBrush)
        for b_idx in backs:
            a, b, c = self.TRIANGLES[b_idx]
            poly = QPolygonF([
                QPointF(proj_pts[a][0], proj_pts[a][1]),
                QPointF(proj_pts[b][0], proj_pts[b][1]),
                QPointF(proj_pts[c][0], proj_pts[c][1]),
            ])
            painter.drawPolygon(poly)

        # -------------------------------------------------------------
        # 6. Draw Front-facing Shaded Triangles
        # -------------------------------------------------------------
        fronts.sort(key=lambda item: item[2])

        spark_indices = set()
        if st in ("thinking", "running_tool"):
            seed = int(t * 18.0)
            spark_indices = {((seed * 37 + i * 59) % len(self.TRIANGLES)) for i in range(6)}

        for f_idx, cpz, avg_z in fronts:
            a, b, c = self.TRIANGLES[f_idx]
            poly = QPolygonF([
                QPointF(proj_pts[a][0], proj_pts[a][1]),
                QPointF(proj_pts[b][0], proj_pts[b][1]),
                QPointF(proj_pts[c][0], proj_pts[c][1]),
            ])

            if f_idx in spark_indices:
                painter.setBrush(QBrush(QColor(255, 255, 255, 185)))
                s_pen = QPen(QColor("#FFFFFF"), 1.3)
                s_pen.setCosmetic(True)
                painter.setPen(s_pen)
                painter.drawPolygon(poly)
                continue

            norm_factor = min(1.0, max(0.12, (avg_z + 2.0) / 4.5))
            fill_alpha = int(16 + 58 * norm_factor * norm_factor)
            stroke_alpha = int(70 + 155 * norm_factor)

            painter.setBrush(QBrush(QColor(neon.red(), neon.green(), neon.blue(), fill_alpha)))
            pen = QPen(QColor(neon.red(), neon.green(), neon.blue(), stroke_alpha), 1.0)
            pen.setCosmetic(True)
            painter.setPen(pen)
            painter.drawPolygon(poly)

        # -------------------------------------------------------------
        # 7. Draw Scanline Sweep Plane Highlight
        # -------------------------------------------------------------
        if scans:
            scan_pen = QPen(QColor(255, 255, 255, 210), 1.3)
            scan_pen.setCosmetic(True)
            painter.setPen(scan_pen)
            painter.setBrush(QBrush(QColor(accent.red(), accent.green(), accent.blue(), 75)))
            for s_idx in scans:
                a, b, c = self.TRIANGLES[s_idx]
                poly = QPolygonF([
                    QPointF(proj_pts[a][0], proj_pts[a][1]),
                    QPointF(proj_pts[b][0], proj_pts[b][1]),
                    QPointF(proj_pts[c][0], proj_pts[c][1]),
                ])
                painter.drawPolygon(poly)

        # -------------------------------------------------------------
        # 8. Antenna Stem & Diamond Crystal Apex
        # -------------------------------------------------------------
        ant_pen = QPen(accent, 1.4)
        ant_pen.setCosmetic(True)
        painter.setPen(ant_pen)
        painter.drawLine(
            QPointF(proj_pts[0][0], proj_pts[0][1]),
            QPointF(proj_pts[52][0], proj_pts[52][1]),
        )
        painter.drawLine(
            QPointF(proj_pts[52][0], proj_pts[52][1]),
            QPointF(proj_pts[53][0], proj_pts[53][1]),
        )

        apex = proj_pts[58]
        apex_pulse = 1.0 + math.sin(t * 8.0) * 0.25 if st == "listening" else 1.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(accent.red(), accent.green(), accent.blue(), 230)))
        painter.drawEllipse(QPointF(apex[0], apex[1]), 3.2 * apex_pulse, 3.2 * apex_pulse)
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawEllipse(QPointF(apex[0], apex[1]), 1.4, 1.4)

        # -------------------------------------------------------------
        # 9. Rounded-Rectangle Visor Rim & Glowing 3-Layer Cyber Eyes
        # -------------------------------------------------------------
        visor_pen = QPen(QColor(accent.red(), accent.green(), accent.blue(), 230), 1.9)
        visor_pen.setCosmetic(True)
        painter.setPen(visor_pen)
        painter.setBrush(QBrush(QColor(4, 12, 22, 115)))
        v_poly = QPolygonF([
            QPointF(proj_pts[12][0], proj_pts[12][1]),
            QPointF(proj_pts[14][0], proj_pts[14][1]),
            QPointF(proj_pts[16][0], proj_pts[16][1]),
            QPointF(proj_pts[18][0], proj_pts[18][1]),
            QPointF(proj_pts[20][0], proj_pts[20][1]),
            QPointF(proj_pts[21][0], proj_pts[21][1]),
            QPointF(proj_pts[19][0], proj_pts[19][1]),
            QPointF(proj_pts[17][0], proj_pts[17][1]),
            QPointF(proj_pts[15][0], proj_pts[15][1]),
            QPointF(proj_pts[13][0], proj_pts[13][1]),
        ])
        painter.drawPolygon(v_poly)

        # Animated Cyber Eyes (indices 23 & 24)
        blink_ratio = 0.15 if ((t % 3.8) > 3.65) else 1.0
        eye_glow = 0.85 + 0.15 * math.sin(t * 6.0)

        lx, ly = proj_pts[23][0] + self.cur_yaw * 4.0, proj_pts[23][1] + self.cur_pitch * 3.0
        rx, ry = proj_pts[24][0] + self.cur_yaw * 4.0, proj_pts[24][1] + self.cur_pitch * 3.0

        for ex, ey in [(lx, ly), (rx, ry)]:
            painter.save()
            painter.translate(ex, ey)
            painter.scale(1.0, blink_ratio)

            if blink_ratio < 0.3:
                slit_pen = QPen(neon, 1.8)
                slit_pen.setCosmetic(True)
                painter.setPen(slit_pen)
                painter.drawLine(QPointF(-6.5, 0.0), QPointF(6.5, 0.0))
            elif st in ("speaking", "wake_ack"):
                arch_pen = QPen(neon, 2.0)
                arch_pen.setCosmetic(True)
                painter.setPen(arch_pen)
                painter.setBrush(Qt.NoBrush)
                p_arch = QPainterPath()
                p_arch.moveTo(-6.5, 2.0)
                p_arch.quadTo(0.0, -5.5, 6.5, 2.0)
                painter.drawPath(p_arch)
            elif st in ("thinking", "running_tool"):
                bar_pen = QPen(accent, 2.4)
                bar_pen.setCosmetic(True)
                painter.setPen(bar_pen)
                painter.drawLine(QPointF(-7.5, 0.0), QPointF(7.5, 0.0))
            elif st == "confused":
                if ex == lx:
                    painter.setPen(QPen(neon, 1.8))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(QPointF(0.0, 0.0), 4.8, 4.8)
                else:
                    painter.setPen(QPen(neon, 1.8))
                    painter.drawLine(QPointF(-6.0, -1.0), QPointF(6.0, 1.0))
            else:
                # 3-layer glowing cyber eyes
                halo_col = QColor(neon.red(), neon.green(), neon.blue(), int(75 * eye_glow))
                painter.setBrush(QBrush(halo_col))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(0.0, 0.0), 10.5, 10.5)

                ring_pen = QPen(QColor(accent.red(), accent.green(), accent.blue(), 190), 1.2)
                ring_pen.setCosmetic(True)
                painter.setPen(ring_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(0.0, 0.0), 6.2, 6.2)

                core_col = QColor(220, 255, 255, int(235 * eye_glow))
                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(core_col))
                painter.drawEllipse(QPointF(0.0, 0.0), 3.8, 3.8)

                painter.setBrush(QBrush(QColor("#FFFFFF")))
                painter.drawEllipse(QPointF(1.2, -1.2), 1.5, 1.5)

            painter.restore()

        # -------------------------------------------------------------
        # 10. Chest Core / Equalizer (index 80)
        # -------------------------------------------------------------
        core_pt = proj_pts[80]
        c_pulse = 1.0 + math.sin(t * 10.0) * 0.3 if st == "speaking" else 1.0
        painter.setBrush(QBrush(QColor(neon.red(), neon.green(), neon.blue(), 190)))
        painter.setPen(QPen(accent, 1.2))
        painter.drawRoundedRect(
            QRectF(core_pt[0] - 8.5 * c_pulse, core_pt[1] - 4.0 * c_pulse, 17.0 * c_pulse, 8.0 * c_pulse),
            2.5, 2.5
        )

        # -------------------------------------------------------------
        # 11. Key Vertex Glowing Points
        # -------------------------------------------------------------
        painter.setPen(Qt.NoPen)
        for idx in self.KEY_NODES:
            pt = proj_pts[idx]
            painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
            painter.drawEllipse(QPointF(pt[0], pt[1]), 1.7, 1.7)

        # -------------------------------------------------------------
        # 12. Floating Live Telemetry Callout Nodes & Bottom Status Bar
        # -------------------------------------------------------------
        left_lbl, top_r_lbl, right_lbl, bar_lbl = self._get_telemetry_labels(st, live_telemetry)

        # Anchor 1: Left Temple Callout (Vertex 15)
        ax1, ay1 = proj_pts[15][0], proj_pts[15][1]
        self._draw_callout_node(
            painter, ax1, ay1, cx - scale * 5.2, ay1 - 14.0,
            left_lbl, QColor("#C084FC"), align_left=True, pulse=t
        )

        # Anchor 2: Top-Right Crown Callout (Vertex 4)
        ax2, ay2 = proj_pts[4][0], proj_pts[4][1]
        self._draw_callout_node(
            painter, ax2, ay2, cx + scale * 4.4, ay2 - 16.0,
            top_r_lbl, QColor("#FBBF24"), align_left=False, pulse=t + 1.2
        )

        # Anchor 3: Mid-Right Cheek Callout (Vertex 18)
        ax3, ay3 = proj_pts[18][0], proj_pts[18][1]
        self._draw_callout_node(
            painter, ax3, ay3, cx + scale * 4.8, ay3 + 12.0,
            right_lbl, QColor("#38BDF8"), align_left=False, pulse=t + 2.4
        )

        # Bottom Holographic Telemetry Bar
        bar_w = 270.0
        bar_h = 22.0
        bar_x = cx - bar_w * 0.5
        bar_y = cy + scale * 6.9
        bar_rect = QRectF(bar_x, bar_y, bar_w, bar_h)

        painter.save()
        painter.setBrush(QBrush(QColor(8, 18, 30, 185)))
        b_pen = QPen(QColor(neon.red(), neon.green(), neon.blue(), 110), 1.0)
        b_pen.setCosmetic(True)
        painter.setPen(b_pen)
        painter.drawRoundedRect(bar_rect, 4.0, 4.0)

        # Animated pulse dot on left of bar
        dot_a = int(150 + 105 * math.sin(t * 5.0))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(accent.red(), accent.green(), accent.blue(), dot_a)))
        painter.drawEllipse(QPointF(bar_x + 12.0, bar_y + bar_h * 0.5), 2.5, 2.5)

        painter.setFont(self._font_bar)
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 230), 1))
        painter.drawText(
            QRectF(bar_x + 20.0, bar_y, bar_w - 26.0, bar_h),
            Qt.AlignCenter,
            bar_lbl
        )
        painter.restore()

    def _draw_callout_node(
        self,
        painter: QPainter,
        ax: float,
        ay: float,
        tx: float,
        ty: float,
        label: str,
        node_color: QColor,
        align_left: bool,
        pulse: float,
    ):
        """Draws a glowing floating telemetry node with leader line and status text."""
        painter.save()
        p_alpha = int(170 + 80 * math.sin(pulse * 3.5))

        # Glowing orb at anchor point
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(node_color.red(), node_color.green(), node_color.blue(), 65)))
        painter.drawEllipse(QPointF(ax, ay), 7.5, 7.5)
        painter.setBrush(QBrush(QColor(255, 255, 255, p_alpha)))
        painter.drawEllipse(QPointF(ax, ay), 2.6, 2.6)

        # Leader line to telemetry label
        l_pen = QPen(QColor(node_color.red(), node_color.green(), node_color.blue(), 140), 0.9)
        l_pen.setCosmetic(True)
        painter.setPen(l_pen)
        elbow_x = tx + (18.0 if align_left else -18.0)
        painter.drawLine(QPointF(ax, ay), QPointF(elbow_x, ty))
        painter.drawLine(QPointF(elbow_x, ty), QPointF(tx, ty))

        # Telemetry text
        painter.setFont(self._font_tele)
        painter.setPen(QPen(QColor(node_color.red(), node_color.green(), node_color.blue(), 235), 1))
        if align_left:
            painter.drawText(QRectF(tx - 155.0, ty - 8.0, 150.0, 16.0), Qt.AlignRight | Qt.AlignVCenter, label)
        else:
            painter.drawText(QRectF(tx + 5.0, ty - 8.0, 165.0, 16.0), Qt.AlignLeft | Qt.AlignVCenter, label)

        painter.restore()
