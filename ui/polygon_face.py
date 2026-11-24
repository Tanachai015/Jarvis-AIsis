"""
High-Poly 3D Interactive Holographic Face Renderer for K.A.R.I.S. (J.A.R.V.I.S. JR.)
Pure Vector Polygon Mesh (76 Vertices / 114 Triangles) rendered with QPainter.

Inspired by the mathematical structure and holographic behaviors of jarvis-core (head.js):
- 3D Dual-layer Wireframe Volume (faint back-facing facets for transparent holographic depth)
- Front-facing Facets bucketed by surface normal with depth-shaded translucent fills and glowing edges
- Dynamic Holographic Scanline Plane sweeping vertically across the robot
- Reactive Audio Waves: outward expanding ripples while speaking, inward contracting ripples while listening
- Neural Synapse Sparks: random facet flashes during thinking / running_tool
- Natural Kinematics: breathing swell, idle head bob, micro-saccades, spring-damped gaze tracking, and jaw drop
- Iconic K.A.R.I.S. Cyber Robot Anatomy: Diamond Antenna Tip, Hexagonal Visor, Cyber Eyes, Prism Ears, Chest Core
"""

import math
import time
from typing import List, Tuple, Dict, Any, Optional

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
    Renders high-density 3D holographic faceted robot of K.A.R.I.S.
    76 Vertices, 114 Triangles, 120 FPS Perspective Projection,
    Dual-layer volumetric wireframe, scanline sweeps, audio ripples, and gaze tracking.
    """

    # 76 High-Poly K.A.R.I.S. Robot 3D Vertices (x, y, z)
    VERTICES: List[List[float]] = [
        [0.0, 3.8, 0.4],    # 0: Crown apex / Forehead top center
        [-1.8, 3.4, 1.2],   # 1: Forehead top left
        [1.8, 3.4, 1.2],    # 2: Forehead top right
        [0.0, 3.0, 1.8],    # 3: Forehead mid center
        [-1.5, 2.2, 1.8],   # 4: Forehead mid left
        [1.5, 2.2, 1.8],    # 5: Forehead mid right
        [0.0, 1.8, 2.3],    # 6: Visor top center
        [-1.4, 1.8, 2.2],   # 7: Visor top left
        [1.4, 1.8, 2.2],    # 8: Visor top right
        [-2.3, 0.9, 1.9],   # 9: Visor outer left
        [2.3, 0.9, 1.9],    # 10: Visor outer right
        [-1.4, -0.1, 2.0],  # 11: Visor bottom left
        [1.4, -0.1, 2.0],   # 12: Visor bottom right
        [0.0, -0.3, 2.1],   # 13: Visor bottom center
        [0.0, 0.85, 2.1],   # 14: Visor inner center plate
        [-0.9, 0.85, 2.2],  # 15: Left eye center
        [0.9, 0.85, 2.2],   # 16: Right eye center
        [-2.8, 1.8, 0.8],   # 17: Temple left
        [2.8, 1.8, 0.8],    # 18: Temple right
        [-3.1, 0.6, 0.4],   # 19: Cheek upper left
        [3.1, 0.6, 0.4],    # 20: Cheek upper right
        [-2.5, -0.6, 1.2],  # 21: Cheek lower left
        [2.5, -0.6, 1.2],   # 22: Cheek lower right
        [-1.5, -1.5, 1.2],  # 23: Jaw left (moves with jaw_drop)
        [1.5, -1.5, 1.2],   # 24: Jaw right (moves with jaw_drop)
        [0.0, -1.1, 1.7],   # 25: Upper mouth / Philtrum
        [0.0, -1.9, 1.6],   # 26: Lower mouth / Chin top (moves with jaw_drop)
        [0.0, -2.6, 1.4],   # 27: Chin bottom (moves with jaw_drop)
        [-0.8, -2.5, 1.2],  # 28: Chin left (moves with jaw_drop)
        [0.8, -2.5, 1.2],   # 29: Chin right (moves with jaw_drop)
        [-3.0, 1.3, -0.4],  # 30: Ear root top left
        [-3.0, 0.1, -0.4],  # 31: Ear root bottom left
        [-4.4, 0.7, 0.2],   # 32: Ear outer tip front left
        [-4.4, 0.7, -0.9],  # 33: Ear outer tip back left
        [-3.8, 1.9, -0.4],  # 34: Ear fin top left
        [-3.8, -0.5, -0.4], # 35: Ear fin bottom left
        [3.0, 1.3, -0.4],   # 36: Ear root top right
        [3.0, 0.1, -0.4],   # 37: Ear root bottom right
        [4.4, 0.7, 0.2],    # 38: Ear outer tip front right
        [4.4, 0.7, -0.9],   # 39: Ear outer tip back right
        [3.8, 1.9, -0.4],   # 40: Ear fin top right
        [3.8, -0.5, -0.4],  # 41: Ear fin bottom right
        [0.0, 4.6, 0.0],    # 42: Antenna stem mid
        [0.0, 5.4, 0.0],    # 43: Antenna crystal base
        [0.0, 6.0, 0.55],   # 44: Crystal diamond front
        [0.0, 6.0, -0.55],  # 45: Crystal diamond back
        [-0.55, 6.0, 0.0],  # 46: Crystal diamond left
        [0.55, 6.0, 0.0],   # 47: Crystal diamond right
        [0.0, 6.9, 0.0],    # 48: Crystal diamond top apex
        [0.0, 3.4, -2.2],   # 49: Cranium rear crown
        [-2.2, 2.6, -1.8],  # 50: Cranium rear top left
        [2.2, 2.6, -1.8],   # 51: Cranium rear top right
        [-2.8, 1.2, -1.8],  # 52: Cranium rear mid left
        [2.8, 1.2, -1.8],   # 53: Cranium rear mid right
        [0.0, 1.4, -2.4],   # 54: Cranium rear center
        [0.0, -0.6, -2.0],  # 55: Skull base center
        [-1.8, -1.0, -1.6], # 56: Skull base left
        [1.8, -1.0, -1.6],  # 57: Skull base right
        [-0.9, -2.8, 0.0],  # 58: Neck strut left
        [0.9, -2.8, 0.0],   # 59: Neck strut right
        [0.0, -2.8, -0.8],  # 60: Neck rear center
        [0.0, -3.8, 1.4],   # 61: Collar center front
        [-1.8, -3.8, 1.1],  # 62: Collar left front
        [1.8, -3.8, 1.1],   # 63: Collar right front
        [-3.8, -4.1, 0.0],  # 64: Shoulder left
        [3.8, -4.1, 0.0],   # 65: Shoulder right
        [0.0, -4.7, 1.5],   # 66: Chest Core center
        [-1.6, -4.7, 1.3],  # 67: Chest Core left
        [1.6, -4.7, 1.3],   # 68: Chest Core right
        [0.0, -5.6, 1.2],   # 69: Torso bottom center
        [-2.8, -5.4, 0.4],  # 70: Torso bottom left
        [2.8, -5.4, 0.4],   # 71: Torso bottom right
        [0.0, -4.2, -1.6],  # 72: Back torso top
        [-2.6, -4.6, -1.2], # 73: Back torso left
        [2.6, -4.6, -1.2],  # 74: Back torso right
        [0.0, -5.4, -1.4],  # 75: Back torso bottom
    ]

    # 114 Triangular Facets
    TRIANGLES: List[List[int]] = [
        # Forehead Front
        [0, 1, 3], [0, 3, 2], [1, 4, 3], [2, 3, 5],
        [3, 4, 6], [3, 6, 5], [4, 7, 6], [5, 6, 8],
        [1, 17, 4], [2, 5, 18], [17, 19, 4], [18, 5, 20],
        [4, 19, 9], [5, 10, 20], [4, 9, 7], [5, 8, 10],

        # Hexagonal Visor Frame
        [6, 7, 14], [6, 14, 8], [7, 9, 14], [8, 14, 10],
        [9, 11, 14], [10, 14, 12], [11, 13, 14], [12, 14, 13],

        # Cheeks & Mouth & Chin
        [9, 19, 21], [10, 22, 20], [9, 21, 11], [10, 12, 22],
        [11, 21, 23], [12, 24, 22], [11, 23, 25], [12, 25, 24],
        [11, 25, 13], [12, 13, 25],
        [23, 28, 26], [24, 26, 29], [25, 23, 26], [25, 26, 24],
        [26, 28, 27], [26, 27, 29],

        # Ear Pod Left (3D prism)
        [30, 32, 34], [30, 34, 33], [31, 35, 32], [31, 33, 35],
        [32, 35, 33], [32, 33, 34], [19, 30, 31], [19, 31, 21],

        # Ear Pod Right (3D prism)
        [36, 40, 38], [36, 39, 40], [37, 38, 41], [37, 41, 39],
        [38, 39, 41], [38, 40, 39], [20, 37, 36], [20, 22, 37],

        # Diamond Antenna Tip (8 facets around rhombus)
        [43, 44, 46], [43, 47, 44], [43, 46, 45], [43, 45, 47],
        [48, 46, 44], [48, 44, 47], [48, 45, 46], [48, 47, 45],

        # Cranium Rear & Volume (Back-facing facets)
        [0, 50, 49], [0, 49, 51], [0, 1, 50], [0, 51, 2],
        [1, 17, 50], [2, 51, 18], [50, 17, 52], [51, 53, 18],
        [49, 50, 54], [49, 54, 51], [50, 52, 54], [51, 54, 53],
        [52, 30, 56], [53, 57, 36], [54, 52, 55], [54, 55, 53],
        [52, 56, 55], [53, 55, 57],

        # Neck & Collar
        [27, 28, 58], [27, 59, 29], [27, 58, 61], [27, 61, 59],
        [55, 56, 60], [55, 60, 57], [56, 58, 60], [57, 60, 59],
        [58, 62, 61], [59, 61, 63], [58, 64, 62], [59, 63, 65],

        # Torso & Chest Core
        [61, 62, 67], [61, 67, 66], [61, 66, 68], [61, 68, 63],
        [62, 64, 67], [63, 68, 65], [64, 70, 67], [65, 68, 71],
        [66, 67, 69], [66, 69, 68], [67, 70, 69], [68, 69, 71],

        # Back Torso
        [60, 73, 72], [60, 72, 74], [64, 73, 60], [65, 60, 74],
        [72, 73, 75], [72, 75, 74], [73, 70, 75], [74, 75, 71],
    ]

    KEY_NODES = {0, 6, 9, 10, 13, 15, 16, 25, 27, 32, 38, 48, 66}

    def __init__(self):
        self.target_yaw: float = 0.0
        self.target_pitch: float = 0.0
        self.cur_yaw: float = 0.0
        self.cur_pitch: float = 0.0
        self.cur_roll: float = 0.0
        self.start_time: float = time.time()

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
    ):
        """
        Renders complete 3D holographic faceted K.A.R.I.S. robot using pure QPainter.
        """
        st = state.lower().strip()
        t = (time.time() - self.start_time) if now is None else now

        # Color Theme Palette based on state
        if st == "speaking":
            neon = QColor("#00E5FF")       # Neon Cyan
            accent = QColor("#22D3EE")
        elif st == "listening":
            neon = QColor("#00FFD1")       # Mint
            accent = QColor("#34D399")
        elif st in ("thinking", "running_tool"):
            neon = QColor("#38BDF8")       # Sky Blue
            accent = QColor("#60A5FA")
        elif st == "confused":
            neon = QColor("#FBBF24")       # Amber
            accent = QColor("#F59E0B")
        elif st == "wake_ack":
            neon = QColor("#00FFD1")
            accent = QColor("#00E5FF")
        else:  # idle
            neon = QColor("#00E5FF")
            accent = QColor("#00FFD1")

        # Fallback coordinate settings
        if cx is None:
            cx = width * 0.50
        if cy is None:
            cy = height * 0.52
        if scale is None:
            scale = min(width, height) * 0.053
        elif scale < 5.0:
            # Auto-scale if tiny scale was passed
            scale = scale * 7.4

        # -------------------------------------------------------------
        # 1. Soft Radial Backdrop Glow behind Robot (from jarvis-core)
        # -------------------------------------------------------------
        glow_r = scale * 7.8
        glow = QRadialGradient(cx, cy, glow_r)
        glow.setColorAt(0.0, QColor(neon.red(), neon.green(), neon.blue(), 36))
        glow.setColorAt(0.55, QColor(neon.red(), neon.green(), neon.blue(), 12))
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(QRectF(cx - glow_r, cy - glow_r, glow_r * 2.0, glow_r * 2.0), QBrush(glow))

        # -------------------------------------------------------------
        # 2. Concentric Orbital HUD Rings & Audio Ripples
        # -------------------------------------------------------------
        r1 = scale * 6.8
        r2 = scale * 5.8
        painter.save()
        painter.translate(cx, cy)

        # Base Orbital Ring
        p1 = QPen(QColor(neon.red(), neon.green(), neon.blue(), 40), 1.0)
        p1.setCosmetic(True)
        painter.setPen(p1)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(0.0, 0.0), r1, r1)

        # Rotating Dashed Orbital Ring
        rot_speed = 1.6 if st in ("thinking", "running_tool") else 0.4
        painter.rotate(math.degrees(t * rot_speed))
        p2 = QPen(QColor(accent.red(), accent.green(), accent.blue(), 75), 1.2, Qt.DashLine)
        p2.setCosmetic(True)
        p2.setDashPattern([16.0, 10.0, 4.0, 10.0])
        painter.setPen(p2)
        painter.drawEllipse(QPointF(0.0, 0.0), r2, r2)
        painter.restore()

        # Reactive Audio Ripples (from jarvis-core audio wave mechanics)
        if st == "speaking":
            # Outward expanding ripples
            painter.save()
            painter.translate(cx, cy)
            for i in range(3):
                wave_t = (t * 1.8 + i * 0.33) % 1.0
                wave_r = scale * 3.5 + wave_t * scale * 4.5
                wave_alpha = int(90 * (1.0 - wave_t))
                w_pen = QPen(QColor(neon.red(), neon.green(), neon.blue(), wave_alpha), 1.2)
                w_pen.setCosmetic(True)
                painter.setPen(w_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(0.0, 0.0), wave_r, wave_r * 0.95)
            painter.restore()
        elif st == "listening":
            # Inward contracting ripples
            painter.save()
            painter.translate(cx, cy)
            for i in range(2):
                wave_t = (1.0 - (t * 1.5 + i * 0.5) % 1.0)
                wave_r = scale * 3.2 + wave_t * scale * 4.0
                wave_alpha = int(80 * wave_t)
                w_pen = QPen(QColor(accent.red(), accent.green(), accent.blue(), wave_alpha), 1.0, Qt.DotLine)
                w_pen.setCosmetic(True)
                painter.setPen(w_pen)
                painter.setBrush(Qt.NoBrush)
                painter.drawEllipse(QPointF(0.0, 0.0), wave_r, wave_r)
            painter.restore()

        # -------------------------------------------------------------
        # 3. Kinematics & 3D Projection Setup
        # -------------------------------------------------------------
        # Idle micro-saccades / sway
        idle_sway_x = math.sin(t * 0.75) * 0.035
        idle_sway_y = math.cos(t * 0.60) * 0.025
        yaw = self.cur_yaw + idle_sway_x
        pitch = self.cur_pitch + idle_sway_y
        roll = math.sin(t * 0.35) * 0.025

        # Breathing swell & head bob
        breath = 1.0 + math.sin(t * 1.5) * 0.018
        bob = math.sin(t * 1.5) * 2.2

        # Reactive Lip-Sync / Jaw Drop
        jaw_drop = 0.0
        if st == "speaking":
            jaw_drop = abs(math.sin(t * 14.0) * math.cos(t * 6.5)) * 0.42

        # 3D Euler Rotation Matrix
        cyaw, syaw = math.cos(yaw), math.sin(yaw)
        cpitch, spitch = math.cos(pitch), math.sin(pitch)
        croll, sroll = math.cos(roll), math.sin(roll)

        proj_pts: List[Tuple[float, float, float]] = []
        for idx, (vx, vy, vz) in enumerate(self.VERTICES):
            # Apply jaw drop to lower mouth & chin
            if idx in (23, 24, 26, 27, 28, 29):
                vy -= jaw_drop

            # Scale breathing
            vx *= breath
            vy *= breath
            vz *= breath

            # Yaw (around Y axis)
            x1 = vx * cyaw + vz * syaw
            z1 = -vx * syaw + vz * cyaw

            # Pitch (around X axis)
            y2 = vy * cpitch - z1 * spitch
            z2 = vy * spitch + z1 * cpitch

            # Roll (around Z axis)
            x3 = x1 * croll - y2 * sroll
            y3 = x1 * sroll + y2 * croll

            # Perspective Scaling (Z-depth perspective division)
            fov = 18.0 / max(4.0, 18.0 - z2)
            px = cx + x3 * scale * fov
            py = cy - y3 * scale * fov + bob
            proj_pts.append((px, py, z2))

        # -------------------------------------------------------------
        # 4. Triangles Normal Calculation & Bucketing (jarvis-core)
        # -------------------------------------------------------------
        backs: List[int] = []
        fronts: List[Tuple[int, float, float]] = []

        # Holographic Scanline Sweep Plane (jarvis-core)
        # Sweeps vertically from model Y = -5.5 to +6.8
        scan_t = (t * 0.35) % 1.0
        scan_y = -5.5 + scan_t * 12.3
        scans: List[int] = []

        for idx, (a, b, c) in enumerate(self.TRIANGLES):
            p0 = proj_pts[a]
            p1 = proj_pts[b]
            p2 = proj_pts[c]

            # Screen 2D cross product for front-facing check (y is inverted down)
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

                # Check if triangle intersects scanline plane
                orig_avg_y = (self.VERTICES[a][1] + self.VERTICES[b][1] + self.VERTICES[c][1]) / 3.0
                if abs(orig_avg_y - scan_y) < 0.75:
                    scans.append(idx)

        # -------------------------------------------------------------
        # 5. Draw Back-facing Wireframe (Faint Holographic Volume Depth)
        # -------------------------------------------------------------
        back_pen = QPen(QColor(neon.red(), neon.green(), neon.blue(), 28), 0.8)
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
        # 6. Draw Front-facing Shaded Triangles (Depth & Normal Shaded)
        # -------------------------------------------------------------
        # Sort back-to-front by average Z
        fronts.sort(key=lambda item: item[2])

        # Neural Synapse Sparks when thinking or running_tool
        spark_indices = set()
        if st in ("thinking", "running_tool"):
            seed = int(t * 18.0)
            spark_indices = {((seed * 37 + i * 59) % len(self.TRIANGLES)) for i in range(5)}

        for f_idx, cpz, avg_z in fronts:
            a, b, c = self.TRIANGLES[f_idx]
            poly = QPolygonF([
                QPointF(proj_pts[a][0], proj_pts[a][1]),
                QPointF(proj_pts[b][0], proj_pts[b][1]),
                QPointF(proj_pts[c][0], proj_pts[c][1]),
            ])

            if f_idx in spark_indices:
                # Flashing synapse spark
                painter.setBrush(QBrush(QColor(255, 255, 255, 180)))
                s_pen = QPen(QColor("#FFFFFF"), 1.4)
                s_pen.setCosmetic(True)
                painter.setPen(s_pen)
                painter.drawPolygon(poly)
                continue

            # Normal lighting factor based on depth and orientation
            norm_factor = min(1.0, max(0.1, (avg_z + 2.0) / 4.5))
            fill_alpha = int(16 + 55 * norm_factor * norm_factor)
            stroke_alpha = int(60 + 150 * norm_factor)

            fill_col = QColor(neon.red(), neon.green(), neon.blue(), fill_alpha)
            stroke_col = QColor(neon.red(), neon.green(), neon.blue(), stroke_alpha)

            painter.setBrush(QBrush(fill_col))
            pen = QPen(stroke_col, 1.0)
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
            QPointF(proj_pts[42][0], proj_pts[42][1]),
        )
        painter.drawLine(
            QPointF(proj_pts[42][0], proj_pts[42][1]),
            QPointF(proj_pts[43][0], proj_pts[43][1]),
        )

        # Glowing Crystal Diamond Apex Dot
        apex = proj_pts[48]
        apex_pulse = 1.0 + math.sin(t * 8.0) * 0.25 if st == "listening" else 1.0
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(accent.red(), accent.green(), accent.blue(), 230)))
        painter.drawEllipse(QPointF(apex[0], apex[1]), 3.2 * apex_pulse, 3.2 * apex_pulse)
        painter.setBrush(QBrush(QColor("#FFFFFF")))
        painter.drawEllipse(QPointF(apex[0], apex[1]), 1.4, 1.4)

        # -------------------------------------------------------------
        # 9. Hexagonal Dark Visor Rim & Glowing Cyber Eyes
        # -------------------------------------------------------------
        visor_pen = QPen(QColor(accent.red(), accent.green(), accent.blue(), 220), 1.8)
        visor_pen.setCosmetic(True)
        painter.setPen(visor_pen)
        painter.setBrush(Qt.NoBrush)
        v_poly = QPolygonF([
            QPointF(proj_pts[6][0], proj_pts[6][1]),
            QPointF(proj_pts[8][0], proj_pts[8][1]),
            QPointF(proj_pts[10][0], proj_pts[10][1]),
            QPointF(proj_pts[12][0], proj_pts[12][1]),
            QPointF(proj_pts[13][0], proj_pts[13][1]),
            QPointF(proj_pts[11][0], proj_pts[11][1]),
            QPointF(proj_pts[9][0], proj_pts[9][1]),
            QPointF(proj_pts[7][0], proj_pts[7][1]),
        ])
        painter.drawPolygon(v_poly)

        # Animated Cyber Eyes inside Visor (indices 15 & 16)
        blink_ratio = 0.15 if ((t % 3.8) > 3.65) else 1.0
        eye_glow = 0.85 + 0.15 * math.sin(t * 6.0)

        lx, ly = proj_pts[15][0] + self.cur_yaw * 4.0, proj_pts[15][1] + self.cur_pitch * 3.0
        rx, ry = proj_pts[16][0] + self.cur_yaw * 4.0, proj_pts[16][1] + self.cur_pitch * 3.0

        for ex, ey in [(lx, ly), (rx, ry)]:
            painter.save()
            painter.translate(ex, ey)
            painter.scale(1.0, blink_ratio)

            if blink_ratio < 0.3:
                # Blink slit
                slit_pen = QPen(neon, 1.6)
                slit_pen.setCosmetic(True)
                painter.setPen(slit_pen)
                painter.drawLine(QPointF(-6.0, 0.0), QPointF(6.0, 0.0))
            elif st in ("speaking", "wake_ack"):
                # Happy Arched Eye (^ ^)
                arch_pen = QPen(neon, 1.8)
                arch_pen.setCosmetic(True)
                painter.setPen(arch_pen)
                painter.setBrush(Qt.NoBrush)
                p_arch = QPainterPath()
                p_arch.moveTo(-6.0, 2.0)
                p_arch.quadTo(0.0, -5.0, 6.0, 2.0)
                painter.drawPath(p_arch)
            elif st in ("thinking", "running_tool"):
                # Scanning Bar
                bar_pen = QPen(accent, 2.2)
                bar_pen.setCosmetic(True)
                painter.setPen(bar_pen)
                painter.drawLine(QPointF(-7.0, 0.0), QPointF(7.0, 0.0))
            elif st == "confused":
                # Left eye circle, right eye slit
                if ex == lx:
                    painter.setPen(QPen(neon, 1.6))
                    painter.setBrush(Qt.NoBrush)
                    painter.drawEllipse(QPointF(0.0, 0.0), 4.5, 4.5)
                else:
                    painter.setPen(QPen(neon, 1.6))
                    painter.drawLine(QPointF(-6.0, -1.0), QPointF(6.0, 1.0))
            else:
                # Attentive round eyes with halo and bright center
                halo_col = QColor(neon.red(), neon.green(), neon.blue(), int(60 * eye_glow))
                painter.setBrush(QBrush(halo_col))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(0.0, 0.0), 8.5, 8.5)

                core_col = QColor(accent.red(), accent.green(), accent.blue(), int(220 * eye_glow))
                painter.setBrush(QBrush(core_col))
                painter.drawEllipse(QPointF(0.0, 0.0), 4.0, 4.0)

                # Pupil Sparkle
                painter.setBrush(QBrush(QColor("#FFFFFF")))
                painter.drawEllipse(QPointF(1.2, -1.2), 1.4, 1.4)

            painter.restore()

        # -------------------------------------------------------------
        # 10. Chest Core / Equalizer (vertices 66-68)
        # -------------------------------------------------------------
        core_pt = proj_pts[66]
        c_pulse = 1.0 + math.sin(t * 10.0) * 0.3 if st == "speaking" else 1.0
        painter.setBrush(QBrush(QColor(neon.red(), neon.green(), neon.blue(), 180)))
        painter.setPen(QPen(accent, 1.2))
        painter.drawRoundedRect(
            QRectF(core_pt[0] - 8.0 * c_pulse, core_pt[1] - 4.0 * c_pulse, 16.0 * c_pulse, 8.0 * c_pulse),
            2.0, 2.0
        )

        # -------------------------------------------------------------
        # 11. Key Vertex Glowing Points
        # -------------------------------------------------------------
        painter.setPen(Qt.NoPen)
        for idx in self.KEY_NODES:
            pt = proj_pts[idx]
            painter.setBrush(QBrush(QColor(255, 255, 255, 200)))
            painter.drawEllipse(QPointF(pt[0], pt[1]), 1.8, 1.8)
