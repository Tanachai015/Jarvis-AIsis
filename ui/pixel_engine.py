"""
Chill Pixel Life Engine & Renderer for Jarvis Menu Bar Status Item.
Coordinates 14x16 sprite animations, pacing, activities, and pill waveform.
"""
import math
import random
from typing import Dict, Any, Optional

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QImage, QPainter, QColor, QPainterPath, QPen

from ui.pixel_sprites import SPRITES, PALETTE


class ChillPixelLifeEngine:
    """Manages the kinematic walking, pacing, activities and state of the pixel bot."""

    def __init__(self):
        self.bot_x: float = 18.0
        self.dir: float = 1.0
        self.action: str = 'walk'
        self.action_timer: float = 5.5
        self.anim_time: float = 0.0
        self.peek_phase: float = 0.0

    def set_action(self, new_action: str):
        self.action = new_action
        self.action_timer = 5.8 if new_action == 'peek' else 5.5
        self.peek_phase = 0.0

    def trigger_wake(self):
        self.action = 'wake'
        self.action_timer = 1.6
        if self.bot_x < 10.0:
            self.bot_x = 15.0
        if self.bot_x > 30.0:
            self.bot_x = 24.0

    def update(self, dt: float):
        self.anim_time += dt
        if self.action_timer > 0:
            self.action_timer -= dt
            if self.action_timer <= 0:
                self.set_action('walk')

        if self.action in ('walk', 'dash'):
            speed = 15.0 if self.action == 'dash' else 5.5
            self.bot_x += self.dir * speed * dt

            # Walk through left edge (-12) or disappear behind split divider | (38)
            if self.bot_x >= 38.0:
                self.bot_x = 38.0
                self.dir = -1.0
            elif self.bot_x <= -12.0:
                self.bot_x = -12.0
                self.dir = 1.0

            # Low probability natural transition during walking in center
            if self.action == 'walk' and 10.0 < self.bot_x < 28.0 and random.random() < 0.015:
                quirks = [
                    'dash', 'radar', 'jump', 'wave', 'peek', 'read',
                    'eat_rice', 'eat_snack', 'sleep', 'work_typing',
                    'research', 'organize_data'
                ]
                self.set_action(random.choice(quirks))

        elif self.action == 'peek':
            self.peek_phase += dt
            if self.peek_phase < 1.8:
                self.dir = 1.0
                self.bot_x += 10.0 * dt
                if self.bot_x > 49.0:
                    self.bot_x = 49.0
            elif self.peek_phase < 4.2:
                self.dir = -1.0
                self.bot_x += (40.0 - self.bot_x) * 4.0 * dt
            else:
                self.dir = -1.0
                self.bot_x -= 8.0 * dt


def render_standby_frame(
    engine: ChillPixelLifeEngine,
    scale: float = 2.0,
    is_wake_on: bool = True,
    is_light_bg: bool = False,
    audio_level: float = 0.0,
    is_wake_listening: bool = False
) -> QImage:
    """Renders pixel-perfect 88x22 iPhone-pill status bar frame with Chat, Voice, and Wake zones."""
    W, H = 88, 22
    splitX = 38
    pill_radius = (H - 1.0) / 2.0

    img = QImage(int(W * scale), int(H * scale), QImage.Format_ARGB32_Premultiplied)
    img.fill(0)
    p = QPainter(img)
    p.scale(scale, scale)

    # 1. Pill Background & Outline
    pill_rect = QRectF(0.5, 0.5, W - 1.0, H - 1.0)
    pill_path = QPainterPath()
    pill_path.addRoundedRect(pill_rect, pill_radius, pill_radius)

    if engine.action == 'wake':
        p.fillPath(pill_path, QColor(6, 21, 32, 245))
        p.setPen(QPen(QColor('#00FFD1'), 1.0))
        p.drawPath(pill_path)
    else:
        bg_col = QColor(10, 16, 29, 238) if not is_light_bg else QColor(15, 23, 42, 240)
        p.fillPath(pill_path, bg_col)
        p.setPen(QPen(QColor(0, 229, 255, 110), 0.75))
        p.drawPath(pill_path)

    # 2. Left Zone Clip (Robot: x 1 to splitX - 1)
    p.save()
    clip_path = QPainterPath()
    clip_path.addRoundedRect(QRectF(1.0, 1.0, splitX - 1.0, H - 2.0), pill_radius, pill_radius)
    p.setClipPath(clip_path)

    # Ground line
    p.fillRect(QRectF(7, 19, splitX - 9, 1), QColor(0, 229, 255, 35))

    # Determine sprite
    t = engine.anim_time
    act = engine.action
    draw_x = int(round(engine.bot_x))
    draw_y = 3
    sprite_name = 'walk1'

    if act == 'wake':
        sprite_name = 'wake'
        draw_y = 3 - int(round(abs(math.sin(t * 10.0)) * 2))
    elif act == 'jump':
        sprite_name = 'jump'
        draw_y = 3 - int(round(abs(math.sin(t * 4.5)) * 3))
    elif act == 'radar':
        sprite_name = 'walk2'
        pulse = int(math.floor(t * 2.2)) % 3
        if pulse >= 1:
            p.fillRect(draw_x + 2, 2, 1, 3, QColor('#00FFD1'))
            p.fillRect(draw_x + 11, 2, 1, 3, QColor('#00FFD1'))
        if pulse == 2:
            p.fillRect(draw_x, 1, 1, 5, QColor('#00FFD1'))
            p.fillRect(draw_x + 13, 1, 1, 5, QColor('#00FFD1'))
    elif act == 'read':
        sprite_name = 'read1' if (int(math.floor(t * 1.4)) % 2 == 0) else 'read2'
    elif act == 'eat_rice':
        sprite_name = 'eat_rice1' if (int(math.floor(t * 2.2)) % 2 == 0) else 'eat_rice2'
    elif act == 'eat_snack':
        sprite_name = 'eat_snack1' if (int(math.floor(t * 2.0)) % 2 == 0) else 'eat_snack2'
    elif act == 'wave':
        sprite_name = 'wave1' if (int(math.floor(t * 3.2)) % 2 == 0) else 'wave2'
    elif act == 'work_typing':
        sprite_name = 'work_typing1' if (int(math.floor(t * 3.0)) % 2 == 0) else 'work_typing2'
    elif act == 'research':
        sprite_name = 'research'
    elif act == 'organize_data':
        sprite_name = 'organize_data'
    elif act == 'sleep':
        sprite_name = 'sleep'
        z_step = int(math.floor(t * 1.2)) % 3
        if z_step >= 0:
            p.fillRect(draw_x + 12, 6, 3, 1, QColor('#38BDF8'))
            p.fillRect(draw_x + 13, 7, 1, 1, QColor('#38BDF8'))
            p.fillRect(draw_x + 12, 8, 3, 1, QColor('#38BDF8'))
        if z_step >= 1:
            p.fillRect(draw_x + 15, 2, 4, 1, QColor('#38BDF8'))
            p.fillRect(draw_x + 17, 3, 1, 1, QColor('#38BDF8'))
            p.fillRect(draw_x + 16, 4, 1, 1, QColor('#38BDF8'))
            p.fillRect(draw_x + 15, 5, 4, 1, QColor('#38BDF8'))
    else:  # walk or dash
        step_rate = 8.0 if act == 'dash' else 3.5
        step = int(math.floor(t * step_rate)) % 2
        sprite_name = 'walk1' if step == 0 else 'walk2'
        draw_y = 3 - step
        if act == 'dash':
            dust_x = (draw_x - 3 - step * 2) if engine.dir == 1.0 else (draw_x + 15 + step * 2)
            p.fillRect(int(dust_x), 16, 2, 2, QColor(224, 242, 254, 180))

    sp = SPRITES.get(sprite_name, SPRITES['walk1'])
    flip = (act in ('walk', 'dash', 'peek')) and (engine.dir == -1.0)
    for r in range(16):
        for c in range(14):
            src_c = (13 - c) if flip else c
            code = sp[r][src_c]
            if code != '0':
                p.fillRect(draw_x + c, draw_y + r, 1, 1, PALETTE[code])
    p.restore()

    # 3. Divider 1 (between Robot and Chat at x = 38)
    p.fillRect(QRectF(splitX, 3.5, 1.0, H - 7.0), QColor(0, 229, 255, 75))

    # 4. Chat Bubble Icon (x: 39..53, center 46.0)
    bubble_path = QPainterPath()
    bubble_path.addRoundedRect(QRectF(41.5, 7.0, 9.0, 6.5), 2.0, 2.0)
    tail = QPainterPath()
    tail.moveTo(43.0, 12.5)
    tail.lineTo(41.5, 15.0)
    tail.lineTo(45.0, 12.5)
    tail.closeSubpath()
    bubble_path = bubble_path.united(tail)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor('#38BDF8'))
    p.drawPath(bubble_path)
    # Mini chat dots
    p.fillRect(44, 9, 1, 1, QColor(255, 255, 255, 230))
    p.fillRect(47, 9, 1, 1, QColor(255, 255, 255, 230))

    # 5. Divider 2 (between Chat and Voice at x = 54)
    p.fillRect(QRectF(54.0, 5.0, 1.0, H - 10.0), QColor(255, 255, 255, 25))

    # 6. Voice Wave Bars (x: 55..69, center 62.0)
    wave_x = [57, 60, 63, 66]
    for i in range(4):
        if act == 'wake':
            bh = 4.0 + abs(math.sin(t * 14.0 + i * 1.1)) * 8.0
            p.fillRect(QRectF(wave_x[i], round(11.0 - bh / 2.0), 1.5, bh), QColor('#00FFD1'))
        else:
            bh = 2.0 + abs(math.sin(t * 1.6 + i * 0.9)) * 2.8
            p.fillRect(QRectF(wave_x[i], round(11.0 - bh / 2.0), 1.5, bh), QColor(0, 229, 255, 140))

    # 7. Divider 3 (between Voice and Wake at x = 70)
    p.fillRect(QRectF(70.0, 5.0, 1.0, H - 10.0), QColor(255, 255, 255, 25))

    # 8. Wake Standby Dot (x: 71..87, center 78.5) - Clickable Wake Trigger
    dot_cx = 78.5
    dot_cy = 11.0
    dot_pulse = 0.65 + 0.35 * math.sin(t * 2.2)
    p.setPen(Qt.NoPen)
    if act == 'wake':
        p.setBrush(QColor('#00FFD1'))
        p.drawEllipse(QPointF(dot_cx, dot_cy), 3.2, 3.2)
    elif is_wake_on:
        # Outer glow ring
        p.setBrush(QColor(0, 255, 209, int(55 * dot_pulse)))
        p.drawEllipse(QPointF(dot_cx, dot_cy), 5.5, 5.5)
        # Core mint LED dot
        p.setBrush(QColor('#00FFD1'))
        p.drawEllipse(QPointF(dot_cx, dot_cy), 2.8, 2.8)
    else:
        # Calm dim slate dot
        p.setBrush(QColor(100, 116, 139, 120))
        p.drawEllipse(QPointF(dot_cx, dot_cy), 2.5, 2.5)

    p.end()
    return img
