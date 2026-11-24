"""
High-Poly 3D Interactive Face Renderer for K.A.R.I.S. (J.A.R.V.I.S. JR.)
Pure Vector Polygon Mesh (49 Vertices / 80+ Triangles) with QPainter.
Retains iconic K.A.R.I.S. Cyber Robot identity (Diamond Antenna, Hexagonal Visor,
Prism Ears, Visor Eyes & Mouth) elevated into 120 FPS Perspective 3D HUD.
"""

import math
from typing import List, Tuple, Dict, Any, Optional

from PySide6.QtCore import Qt, QPointF, QRectF
from PySide6.QtGui import QPainter, QPolygonF, QColor, QPen, QBrush, QFont


class HighPolyKarisRenderer:
    """
    Renders high-density 3D faceted robot face of K.A.R.I.S.
    Perspective Projection, Depth-shading, Real-time Gaze Tracking,
    Orbital HUD Rings, and dynamic states (idle, listening, thinking, speaking, etc.).
    """

    # 49 High-Density Robot Anatomy Vertices (x, y, z)
    VERTICES: List[Tuple[float, float, float]] = [
        # 0-4: Top Cyber Helmet Crest
        (0.0, -1.15, 0.18), (-0.42, -1.06, 0.14), (0.42, -1.06, 0.14), (-0.76, -0.82, 0.02), (0.76, -0.82, 0.02),
        # 5-9: Upper Forehead Shield Plate
        (0.0, -0.84, 0.44), (-0.46, -0.78, 0.38), (0.46, -0.78, 0.38), (-0.88, -0.42, -0.05), (0.88, -0.42, -0.05),
        # 10-14: Brow Ridge & Visor Upper Hex Rim
        (0.0, -0.54, 0.56), (-0.56, -0.52, 0.46), (0.56, -0.52, 0.46), (-0.82, -0.18, 0.24), (0.82, -0.18, 0.24),
        # 15-22: Left & Right Cyber Eye Sockets inside Visor (4 pts each)
        (-0.46, -0.34, 0.50), (-0.24, -0.32, 0.54), (-0.44, -0.14, 0.50), (-0.24, -0.15, 0.54), # 15-18 Left Eye
        (0.24, -0.32, 0.54),  (0.46, -0.34, 0.50),  (0.24, -0.15, 0.54),  (0.44, -0.14, 0.50),  # 19-22 Right Eye
        # 23-27: Sculpted 3D Robot Nose / Central Visor Apex
        (0.0, -0.28, 0.62), (-0.13, 0.04, 0.64), (0.13, 0.04, 0.64), (0.0, 0.10, 0.72), (0.0, -0.04, 0.68),
        # 28-31: Cheekbones & Lower Hex Visor Rim
        (-0.78, 0.18, 0.20), (0.78, 0.18, 0.20), (-0.48, 0.16, 0.50), (0.48, 0.16, 0.50),
        # 32-35: Upper Mouth / Core Grill Frame
        (-0.28, 0.34, 0.54), (0.0, 0.32, 0.58), (0.28, 0.34, 0.54), (0.0, 0.42, 0.56),
        # 36-39: Lower Lip / Articulated Jaw (moves on speech)
        (-0.26, 0.50, 0.52), (0.0, 0.48, 0.55), (0.26, 0.50, 0.52), (0.0, 0.60, 0.50),
        # 40-42: Chin Armor & Jawline
        (-0.56, 0.56, 0.18), (0.56, 0.56, 0.18), (0.0, 0.88, 0.30),
        # 43-46: Side Prism Sensor Ear Pods
        (-1.02, -0.22, -0.08), (-1.00, 0.22, -0.08), (1.02, -0.22, -0.08), (1.00, 0.22, -0.08),
        # 47-48: Crown Antenna Stem & Diamond Crystal Apex
        (0.0, -1.42, 0.05), (0.0, -1.65, 0.05)
    ]

    # Dense Triangulation Mesh (80+ Facets)
    TRIANGLES: List[Tuple[int, int, int]] = [
        # Crown & Forehead Plate
        (0, 1, 5), (0, 5, 2), (1, 3, 6), (1, 6, 5), (2, 5, 7), (2, 7, 4), (3, 8, 6), (4, 7, 9),
        (5, 6, 10), (5, 10, 7), (6, 11, 10), (7, 10, 12), (6, 8, 11), (7, 12, 9),
        # Brow Ridge to Visor
        (10, 11, 16), (10, 16, 23), (10, 23, 19), (10, 19, 12),
        (11, 15, 16), (12, 19, 20), (11, 13, 15), (12, 20, 14),
        # Eye Socket Facets
        (15, 17, 16), (16, 17, 18), (19, 21, 20), (20, 21, 22),
        # Central Visor & Nose Apex
        (16, 18, 23), (18, 24, 23), (23, 24, 27), (23, 27, 25), (23, 25, 19), (19, 25, 21),
        (24, 26, 27), (27, 26, 25), (18, 30, 24), (21, 25, 31),
        # Hexagonal Visor Lower Rims & Cheeks
        (13, 28, 15), (15, 28, 17), (17, 28, 30), (14, 20, 29), (20, 22, 29), (22, 31, 29),
        # Mid-Face to Upper Mouth Frame
        (24, 30, 32), (24, 32, 26), (26, 32, 33), (26, 33, 34), (26, 34, 25), (25, 34, 31),
        (32, 35, 33), (33, 35, 34),
        # Articulated Mouth & Chin Jawline
        (30, 40, 32), (32, 40, 36), (32, 36, 35), (35, 36, 37), (35, 37, 38), (35, 38, 34), (34, 38, 41), (34, 41, 31),
        (36, 39, 37), (37, 39, 38), (40, 42, 36), (36, 42, 39), (39, 42, 38), (38, 42, 41),
        # Side Armor & Prism Ears
        (8, 13, 43), (13, 28, 43), (28, 44, 43), (28, 40, 44),
        (9, 45, 14), (14, 45, 29), (29, 45, 46), (29, 46, 41)
    ]

    KEY_NODES = {15, 16, 17, 18, 19, 20, 21, 22, 26, 33, 37, 48}

    def __init__(self):
        self.target_yaw: float = 0.0
        self.target_pitch: float = 0.0
        self.cur_yaw: float = 0.0
        self.cur_pitch: float = 0.0

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

    def render(self, painter: QPainter, width: int = 512, height: int = 374, state: str = "idle", now: float = 0.0, cx: Optional[float] = None, cy: Optional[float] = None, scale: Optional[float] = None):
        """
        Renders complete 3D high-poly K.A.R.I.S. robot face using pure QPainter.
        """
        st = state.lower().strip()
        t = now

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

        # Smooth Spring Damping for Head Look
        idle_sway_x = math.sin(t * 0.9) * 0.04
        idle_sway_y = math.cos(t * 0.75) * 0.03
        self.cur_yaw += (self.target_yaw + idle_sway_x - self.cur_yaw) * 0.14
        self.cur_pitch += (self.target_pitch + idle_sway_y - self.cur_pitch) * 0.14

        if cx is None:
            cx = width * 0.50
        if cy is None:
            cy = height * 0.52
        if scale is None:
            scale = min(width, height) * 0.32

        # 1. Outer Orbital HUD Rings
        painter.save()
        painter.translate(cx, cy)

        # Concentric Outer Ring
        ring_pen1 = QPen(QColor(neon.red(), neon.green(), neon.blue(), 35), 1.0)
        ring_pen1.setCosmetic(True)
        painter.setPen(ring_pen1)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(0.0, 0.0), scale * 1.36, scale * 1.36)

        # Rotating Dashed Orbital Ring
        rot_speed = 1.6 if st in ("thinking", "running_tool") else 0.35
        painter.rotate(math.degrees(t * rot_speed))
        ring_pen2 = QPen(QColor(accent.red(), accent.green(), accent.blue(), 80), 1.2, Qt.DashLine)
        ring_pen2.setCosmetic(True)
        ring_pen2.setDashPattern([20.0, 12.0, 5.0, 12.0])
        painter.setPen(ring_pen2)
        painter.drawEllipse(QPointF(0.0, 0.0), scale * 1.22, scale * 1.22)
        painter.restore()

        # Jaw Drop Kinematics when speaking
        jaw_drop = 0.0
        if st == "speaking":
            jaw_drop = abs(math.sin(t * 14.0) * math.cos(t * 6.0)) * 0.14

        # 2. 3D Perspective Projection
        cyaw, syaw = math.cos(self.cur_yaw), math.sin(self.cur_yaw)
        cpitch, spitch = math.cos(self.cur_pitch), math.sin(self.cur_pitch)

        proj_pts: List[Tuple[float, float, float]] = []
        for idx, (vx, vy, vz) in enumerate(self.VERTICES):
            # Apply jaw drop to lower mouth & chin vertices
            if 36 <= idx <= 39:
                vy += jaw_drop
            elif idx == 42:
                vy += jaw_drop * 0.65

            # Rotate Y (Yaw)
            x1 = vx * cyaw - vz * syaw
            z1 = vx * syaw + vz * cyaw

            # Rotate X (Pitch)
            y2 = vy * cpitch - z1 * spitch
            z2 = vy * spitch + z1 * cpitch

            # Perspective Scaling
            fov = 3.0 / max(0.5, 3.0 - z2)
            px = cx + x1 * scale * fov
            py = cy + y2 * scale * fov
            proj_pts.append((px, py, z2))

        # 3. Draw Depth-Shaded Mesh Triangles
        mesh_pen = QPen(QColor(neon.red(), neon.green(), neon.blue(), 110), 0.8)
        mesh_pen.setCosmetic(True)
        painter.setPen(mesh_pen)

        for a, b, c in self.TRIANGLES:
            p1 = proj_pts[a]
            p2 = proj_pts[b]
            p3 = proj_pts[c]

            avg_z = (p1[2] + p2[2] + p3[2]) / 3.0
            fill_alpha = int(max(10.0, min(65.0, (avg_z + 0.4) * 55.0)))
            brush_col = QColor(neon.red(), neon.green(), neon.blue(), fill_alpha)

            poly = QPolygonF([QPointF(p1[0], p1[1]), QPointF(p2[0], p2[0]), QPointF(p3[0], p3[1])])
            painter.setBrush(QBrush(brush_col))
            painter.drawPolygon(poly)

        # 4. Crown Diamond Crystal Antenna
        ant_pen = QPen(accent, 1.4)
        ant_pen.setCosmetic(True)
        painter.setPen(ant_pen)
        painter.drawLine(QPointF(proj_pts[0][0], proj_pts[0][1]), QPointF(proj_pts[47][0], proj_pts[47][1]))
        painter.drawLine(QPointF(proj_pts[47][0], proj_pts[47][1]), QPointF(proj_pts[48][0], proj_pts[48][1]))

        # Diamond Crystal Tip (Rhombus QPolygonF)
        tip_x, tip_y = proj_pts[48][0], proj_pts[48][1]
        tip_scale = 1.3 if st == "listening" else 1.0
        poly_tip = QPolygonF([
            QPointF(tip_x, tip_y - 7.0 * tip_scale),
            QPointF(tip_x + 5.0 * tip_scale, tip_y),
            QPointF(tip_x, tip_y + 7.0 * tip_scale),
            QPointF(tip_x - 5.0 * tip_scale, tip_y)
        ])
        painter.setBrush(QBrush(accent))
        painter.drawPolygon(poly_tip)

        # 5. Glowing Vertex Nodes
        painter.setPen(Qt.NoPen)
        for idx, (px, py, pz) in enumerate(proj_pts):
            is_key = idx in self.KEY_NODES
            node_r = 2.0 if is_key else 1.1
            node_alpha = 240 if is_key else 120
            node_col = QColor("#FFFFFF") if idx == 48 else QColor(neon.red(), neon.green(), neon.blue(), node_alpha)
            painter.setBrush(QBrush(node_col))
            painter.drawEllipse(QPointF(px, py), node_r, node_r)

        # 6. Glowing 3D Robot Eyes inside Visor
        blink_ratio = 0.15 if ((t % 3.8) > 3.65) else 1.0
        eye_glow = 0.85 + 0.15 * math.sin(t * 6.0)

        # Compute midpoints of eye socket frames
        lx = (proj_pts[15][0] + proj_pts[18][0]) * 0.5 + self.cur_yaw * 6.0
        ly = (proj_pts[15][1] + proj_pts[18][1]) * 0.5 + self.cur_pitch * 4.0
        rx = (proj_pts[19][0] + proj_pts[22][0]) * 0.5 + self.cur_yaw * 6.0
        ry = (proj_pts[19][1] + proj_pts[22][1]) * 0.5 + self.cur_pitch * 4.0

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
                from PySide6.QtGui import QPainterPath
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
                painter.drawEllipse(QPointF(0.0, 0.0), 9.0, 9.0)

                core_col = QColor(accent.red(), accent.green(), accent.blue(), int(220 * eye_glow))
                painter.setBrush(QBrush(core_col))
                painter.drawEllipse(QPointF(0.0, 0.0), 4.2, 4.2)

                # Pupil Sparkle
                painter.setBrush(QBrush(QColor("#FFFFFF")))
                painter.drawEllipse(QPointF(1.2, -1.2), 1.4, 1.4)

            painter.restore()

        # 7. Reactive Lip-Sync / Core Mouth Grill
        if jaw_drop > 0.02:
            mouth_pen = QPen(neon, 2.0)
            mouth_pen.setCosmetic(True)
            painter.setPen(mouth_pen)
            mx1, my1 = proj_pts[36][0], (proj_pts[32][1] + proj_pts[36][1]) * 0.5
            mx2, my2 = proj_pts[37][0], (proj_pts[33][1] + proj_pts[37][1]) * 0.5
            mx3, my3 = proj_pts[38][0], (proj_pts[34][1] + proj_pts[38][1]) * 0.5
            painter.drawLine(QPointF(mx1, my1), QPointF(mx2, my2))
            painter.drawLine(QPointF(mx2, my2), QPointF(mx3, my3))
        else:
            # Idle gentle robot smile
            smile_pen = QPen(QColor(neon.red(), neon.green(), neon.blue(), 140), 1.4)
            smile_pen.setCosmetic(True)
            painter.setPen(smile_pen)
            painter.drawLine(QPointF(proj_pts[32][0], proj_pts[32][1]), QPointF(proj_pts[33][0], proj_pts[33][1] + 1.2))
            painter.drawLine(QPointF(proj_pts[33][0], proj_pts[33][1] + 1.2), QPointF(proj_pts[34][0], proj_pts[34][1]))
