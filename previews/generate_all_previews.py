"""
J.A.R.V.I.S. Desktop Assistant - Animated Preview GIF Generator
Generates 4 high-quality demonstration GIFs:
1. 01_menubar_standby.gif: Chill Pixel Robot on Menu Bar (Standby & Quick Actions)
2. 02_dynamic_island_popout.gif: Dynamic Island Spring Pop-out & State Transitions
3. 03_overlay_chat.gif: Overlay Chat & Spotlight Experience (Active Monitor)
4. 04_jarvis_showcase.gif: Full All-in-One End-to-End Showcase
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import shutil
import subprocess
import math
from PIL import Image

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt, QPoint, QRect, QRectF, QPointF
from PySide6.QtGui import (
    QImage, QPainter, QColor, QFont, QPen, QBrush, QLinearGradient,
    QPainterPath, QCursor
)

from ui.pixel_engine import ChillPixelLifeEngine, render_standby_frame
from ui.dynamic_island import DynamicIsland
from ui.overlay_chat import OverlayChat

TMP_DIR = "/tmp/jarvis_gif_build"
OUTPUT_DIR = os.path.abspath("previews")


def run_ffmpeg_gif(frames_pattern: str, output_path: str, fps: int = 15, max_colors: int = 128):
    """Uses ffmpeg palettegen/paletteuse for crisp, compact animated GIFs."""
    cmd = (
        f'ffmpeg -y -i "{frames_pattern}" -vf '
        f'"fps={fps},split[s0][s1];[s0]palettegen=max_colors={max_colors}:reserve_transparent=0[p];[s1][p]paletteuse=dither=bayer:bayer_scale=3" '
        f'"{output_path}"'
    )
    subprocess.run(cmd, shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def draw_mac_menubar_strip(p: QPainter, width: int, y: int = 0, title: str = "J.A.R.V.I.S."):
    """Draws a sleek macOS menu bar background strip."""
    bar_rect = QRectF(0, y, width, 28)
    p.fillRect(bar_rect, QColor(15, 20, 32, 240))
    p.setPen(QColor(255, 255, 255, 25))
    p.drawLine(0, y + 28, width, y + 28)

    # Apple logo + Menu items
    p.setFont(QFont("Arial", 11, QFont.Bold))
    p.setPen(QColor(220, 225, 235, 220))
    p.drawText(14, y + 18, "")

    p.setFont(QFont("Arial", 10, QFont.Medium))
    p.setPen(QColor(200, 210, 225, 200))
    items = [title, "File", "Edit", "View", "Window", "Help"]
    curr_x = 36
    for it in items:
        p.drawText(curr_x, y + 18, it)
        curr_x += int(len(it) * 7.5 + 16)

    # Right side: WiFi, Battery, Clock
    p.setFont(QFont("Arial", 10, QFont.Normal))
    p.setPen(QColor(180, 190, 210, 180))
    p.drawText(width - 70, y + 18, "9:41 AM")
    p.drawText(width - 105, y + 18, "🔋100%")
    p.drawText(width - 130, y + 18, "􀙇")


# ============================================================================
# GIF 1: Menubar Standby Mode & Quick Actions
# ============================================================================
def generate_gif1_menubar_standby():
    print("[GIF 1/4] Generating 01_menubar_standby.gif...")
    work_dir = os.path.join(TMP_DIR, "gif1")
    shutil.rmtree(work_dir, ignore_errors=True)
    os.makedirs(work_dir, exist_ok=True)

    engine = ChillPixelLifeEngine()
    width, height = 700, 200
    total_frames = 60

    # Simulate mouse cursor path
    # Frame 0-18: idle walk
    # Frame 19-32: cursor moves to Wake dot (x=670, y=14) and clicks
    # Frame 33-46: cursor moves to Voice icon and clicks
    # Frame 47-60: cursor moves to Robot icon and clicks
    wake_on = True

    for f in range(total_frames):
        img = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        img.fill(QColor(11, 15, 25))
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)

        # Draw desktop background gradient
        grad = QLinearGradient(0, 0, width, height)
        grad.setColorAt(0.0, QColor(14, 20, 36))
        grad.setColorAt(1.0, QColor(8, 11, 18))
        p.fillRect(QRectF(0, 0, width, height), grad)

        # Draw Menu bar
        draw_mac_menubar_strip(p, width, y=0)

        # Update engine
        engine.update(0.06)

        # Toggle wake state around click
        if f == 26:
            wake_on = False
        elif f == 32:
            wake_on = True

        audio_level = 0.6 if 36 <= f <= 46 else (0.15 + 0.1 * math.sin(f * 0.4))
        standby_qimg = render_standby_frame(
            engine, scale=2.0, is_wake_on=wake_on,
            is_light_bg=False, audio_level=audio_level,
            is_wake_listening=(36 <= f <= 46)
        )

        # Place the 88x22 capsule on the menu bar (right side, before status icons)
        capsule_x = width - 230
        capsule_y = 3
        p.drawImage(capsule_x, capsule_y, standby_qimg.scaled(88, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # Bottom Inspector Card (Enlarged 3.5x Preview)
        card_rect = QRectF(25, 45, width - 50, 140)
        p.setBrush(QColor(16, 24, 42, 235))
        p.setPen(QColor(0, 229, 255, 60))
        p.drawRoundedRect(card_rect, 14, 14)

        # Header in card
        p.setFont(QFont("Arial", 11, QFont.Bold))
        p.setPen(QColor(0, 229, 255, 230))
        p.drawText(42, 68, "J.A.R.V.I.S. Menu Bar Dynamic Island (Native NSStatusItem 88pt)")

        p.setFont(QFont("Arial", 9, QFont.Normal))
        p.setPen(QColor(140, 160, 190, 200))
        p.drawText(width - 240, 68, "Standard Mode • Silent Standby")

        # Draw enlarged 88x22 capsule at 3.5x scale (308 x 77 px)
        enlarged = standby_qimg.scaled(308, 77, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        p.drawImage(45, 88, enlarged)

        # Legend and Action Labels
        p.setFont(QFont("Arial", 9, QFont.Bold))
        labels = [
            ("🤖 1. Robot Zone (x < 38pt)", "คลิก: กาง/พับหน้าต่าง Pop-out (Expand/Fold)", QColor(0, 229, 255)),
            ("💬 2. Chat Zone (38 ≤ x < 54pt)", "คลิก: เปิดหน้าต่างแชท (Alt+Space)", QColor(56, 189, 248)),
            ("🎙️ 3. Voice Zone (54 ≤ x < 70pt)", "คลิก: สั่งบันทึกเสียงทันที (Cmd+Shift+J)", QColor(52, 211, 153)),
            ("⚡ 4. Wake Zone (x ≥ 70pt)", f"คลิก: สลับคำปลุก ON/OFF ({'ON' if wake_on else 'OFF'})", QColor(250, 204, 21) if wake_on else QColor(148, 163, 184)),
        ]
        curr_ly = 96
        for title_lbl, desc, col in labels:
            p.setPen(col)
            p.drawText(370, curr_ly, title_lbl)
            p.setFont(QFont("Arial", 8, QFont.Normal))
            p.setPen(QColor(160, 175, 200, 190))
            p.drawText(370, curr_ly + 13, desc)
            p.setFont(QFont("Arial", 9, QFont.Bold))
            curr_ly += 25

        # Draw animated simulated mouse cursor
        if 20 <= f <= 32:
            # Wake click
            cursor_pos = QPoint(capsule_x + 78, 14)
            is_click = (f in (25, 26, 31, 32))
        elif 34 <= f <= 46:
            # Voice click
            cursor_pos = QPoint(capsule_x + 62, 14)
            is_click = (f in (37, 38))
        elif 48 <= f <= 58:
            # Chat click
            cursor_pos = QPoint(capsule_x + 46, 14)
            is_click = (f in (50, 51))
        else:
            cursor_pos = QPoint(capsule_x + 20, 14)
            is_click = False

        # Draw mouse pointer
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 240))
        pts = [
            QPoint(cursor_pos.x(), cursor_pos.y()),
            QPoint(cursor_pos.x() + 9, cursor_pos.y() + 9),
            QPoint(cursor_pos.x() + 4, cursor_pos.y() + 10),
            QPoint(cursor_pos.x() + 2, cursor_pos.y() + 14),
        ]
        p.drawPolygon(pts)
        if is_click:
            p.setPen(QColor(0, 229, 255, 180))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(cursor_pos.x() - 4, cursor_pos.y() - 4, 18, 18)

        p.end()
        img.save(os.path.join(work_dir, f"frame_{f:03d}.png"))

    out_gif = os.path.join(OUTPUT_DIR, "01_menubar_standby.gif")
    run_ffmpeg_gif(os.path.join(work_dir, "frame_%03d.png"), out_gif, fps=15)
    print(f"✅ Created {out_gif} ({os.path.getsize(out_gif):,} bytes)")


# ============================================================================
# GIF 2: Dynamic Island Pop-out & State Transitions
# ============================================================================
def generate_gif2_dynamic_island_popout():
    print("[GIF 2/4] Generating 02_dynamic_island_popout.gif...")
    work_dir = os.path.join(TMP_DIR, "gif2")
    shutil.rmtree(work_dir, ignore_errors=True)
    os.makedirs(work_dir, exist_ok=True)

    island = DynamicIsland()
    island.resize(360, 70)

    width, height = 760, 260
    total_frames = 65

    # Sequence:
    # 0-10: Spring bounce expansion
    # 11-24: ready (wake_ack)
    # 25-38: listening
    # 39-50: thinking
    # 51-64: speaking
    for f in range(total_frames):
        canvas = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        canvas.fill(QColor(10, 14, 24))
        p = QPainter(canvas)
        p.setRenderHint(QPainter.Antialiasing)

        # Background gradient
        grad = QLinearGradient(0, 0, width, height)
        grad.setColorAt(0.0, QColor(13, 19, 34))
        grad.setColorAt(1.0, QColor(7, 10, 18))
        p.fillRect(QRectF(0, 0, width, height), grad)

        # macOS Menu bar strip
        draw_mac_menubar_strip(p, width, y=0)

        # Set Island state
        if f <= 10:
            # Expansion bounce
            island.on_state_changed("wake_ack")
            progress = min(1.0, f / 9.0)
            # easeOutBack
            c1, c3 = 1.70158, 2.70158
            bounce = 1 + c3 * math.pow(progress - 1, 3) + c1 * math.pow(progress - 1, 2)
            cur_h = int(24 + (70 - 24) * max(0.1, bounce))
            island.resize(360, cur_h)
            island._show_robot_bubble("พร้อมครับบอส!", "ตรวจพบคำปลุก 'Hey Jarvis'", duration=2.0)
        elif 11 <= f <= 24:
            island.resize(360, 70)
            island.on_state_changed("wake_ack")
            island._show_robot_bubble("พร้อมครับบอส!", "พูดคำสั่งที่ต้องการได้เลยครับ", duration=2.0)
        elif 25 <= f <= 38:
            island.on_state_changed("listening")
            island._show_robot_bubble("กำลังฟังเสียงคำสั่ง...", "“ช่วยสรุปรายงานการทำงานวันนี้”", duration=2.0)
        elif 39 <= f <= 50:
            island.on_state_changed("thinking")
            island._show_robot_bubble("กำลังวิเคราะห์คำสั่ง...", "Gemini 3.5 Flash Lite + Tiered Context", duration=2.0)
        else:
            island.on_state_changed("speaking")
            island._show_robot_bubble("กำลังพูดตอบกลับ...", "“สรุปผลการทำงานและจัดเก็บเรียบร้อยครับ”", duration=2.0)

        # Grab island widget
        island_img = island.grab().toImage()

        # Place Island centered right beneath menu bar (x = width//2 - 180, y = 34)
        isl_x = (width - 360) // 2
        isl_y = 34
        p.drawImage(isl_x, isl_y, island_img)

        # Annotation badge at bottom
        badge_rect = QRectF((width - 460) // 2, 190, 460, 45)
        p.setBrush(QColor(15, 23, 42, 220))
        p.setPen(QColor(0, 229, 255, 45))
        p.drawRoundedRect(badge_rect, 10, 10)

        # Text in badge
        p.setFont(QFont("Arial", 9, QFont.Bold))
        state_titles = {
            "wake_ack": ("⚡ WAKE ACK", "พร้อมตอบรับทันที เมื่อพูด 'Hey Jarvis' หรือคลิกปุ่ม Voice", QColor(0, 229, 255)),
            "listening": ("🎙️ LISTENING", "Silero VAD เปิดไมค์อัตโนมัติ • ตัดส่งทันทีเมื่อหยุดพูด", QColor(52, 211, 153)),
            "thinking": ("🧠 THINKING", "ประมวลผลผ่านสมอง AI Gemini พร้อมเครื่องมือ macOS / MCP", QColor(56, 189, 248)),
            "speaking": ("🔊 SPEAKING", "อ่านออกเสียงไทย-อังกฤษสมจริง • กด Esc หรือพูดแทรกเพื่อเบรกได้ทันที", QColor(147, 197, 253)),
        }
        curr_state = island.current_state if hasattr(island, "current_state") else "speaking"
        if f <= 24:
            st_key = "wake_ack"
        elif f <= 38:
            st_key = "listening"
        elif f <= 50:
            st_key = "thinking"
        else:
            st_key = "speaking"

        st_title, st_desc, st_col = state_titles[st_key]
        p.setPen(st_col)
        p.drawText(int(badge_rect.x() + 18), int(badge_rect.y() + 20), st_title)
        p.setFont(QFont("Arial", 8, QFont.Normal))
        p.setPen(QColor(180, 195, 220, 210))
        p.drawText(int(badge_rect.x() + 18), int(badge_rect.y() + 35), st_desc)

        p.end()
        canvas.save(os.path.join(work_dir, f"frame_{f:03d}.png"))

    out_gif = os.path.join(OUTPUT_DIR, "02_dynamic_island_popout.gif")
    run_ffmpeg_gif(os.path.join(work_dir, "frame_%03d.png"), out_gif, fps=15)
    print(f"✅ Created {out_gif} ({os.path.getsize(out_gif):,} bytes)")


# ============================================================================
# GIF 3: Overlay Chat & Spotlight Experience
# ============================================================================
def generate_gif3_overlay_chat():
    print("[GIF 3/4] Generating 03_overlay_chat.gif...")
    work_dir = os.path.join(TMP_DIR, "gif3")
    shutil.rmtree(work_dir, ignore_errors=True)
    os.makedirs(work_dir, exist_ok=True)

    chat = OverlayChat()
    chat.resize(680, 440)

    width, height = 760, 520
    total_frames = 65

    # Prepare chat contents
    chat.on_user_message("สวัสดีครับ จาร์วิส ช่วยตรวจเช็คสถานะระบบและเครื่องมือ MCP ให้หน่อยครับ")
    chat.on_assistant_reply(
        "<b>รับทราบครับบอส! ตรวจสอบสถานะระบบเรียบร้อย 🚀</b><br><br>"
        "• <b>AI Brain:</b> Gemini 3.5 Flash Lite (Active & Fallback Chain พร้อม)<br>"
        "• <b>Official MCP:</b> Filesystem, Web Fetch, Git เชื่อมต่อสมบูรณ์ (31 เครื่องมือ)<br>"
        "• <b>Voice Pipeline:</b> Standard Mode ไมโครโฟนปิดเงียบ 100% ในช่วงสแตนบาย<br>"
        "• <b>Menu Bar:</b> NSStatusItem แสดงผลบนหน้าจอ Active พร้อมรับคำสั่งครับ"
    )
    chat.on_task_log("MCP Connection", "[MCP] Filesystem server connected: 16 tools registered.")
    chat.on_task_log("Fetch Server", "[MCP] Fetch server connected: 1 tools registered.")
    chat.on_task_log("TaskManager Sync", "[TaskManager] Background tasks synced with memory/background_tasks.json")

    for f in range(total_frames):
        canvas = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        canvas.fill(QColor(10, 14, 24))
        p = QPainter(canvas)
        p.setRenderHint(QPainter.Antialiasing)

        # Wallpaper
        grad = QLinearGradient(0, 0, width, height)
        grad.setColorAt(0.0, QColor(14, 21, 38))
        grad.setColorAt(1.0, QColor(7, 9, 16))
        p.fillRect(QRectF(0, 0, width, height), grad)

        # Menu bar
        draw_mac_menubar_strip(p, width, y=0)

        # Tab selection:
        # Frame 0-42: Conversation tab
        # Frame 43-56: Process & Raw Data tab
        # Frame 57-64: Back to Conversation
        if 43 <= f <= 56:
            chat.tab_widget.setCurrentIndex(1)
        else:
            chat.tab_widget.setCurrentIndex(0)

        # Slide-down entry animation
        entry_offset = 0
        if f <= 8:
            entry_offset = int((8 - f) * 6)

        chat_img = chat.grab().toImage()

        # Draw centered
        chat_x = (width - 680) // 2
        chat_y = 48 + entry_offset
        p.drawImage(chat_x, chat_y, chat_img)

        # Shortcut pill at top right
        pill_rect = QRectF(width - 240, 34, 210, 24)
        p.setBrush(QColor(0, 229, 255, 25))
        p.setPen(QColor(0, 229, 255, 80))
        p.drawRoundedRect(pill_rect, 6, 6)
        p.setFont(QFont("Arial", 8, QFont.Bold))
        p.setPen(QColor(0, 229, 255, 230))
        p.drawText(int(pill_rect.x() + 10), int(pill_rect.y() + 16), "⌨️ Alt + Space (Active Screen)")

        p.end()
        canvas.save(os.path.join(work_dir, f"frame_{f:03d}.png"))

    out_gif = os.path.join(OUTPUT_DIR, "03_overlay_chat.gif")
    run_ffmpeg_gif(os.path.join(work_dir, "frame_%03d.png"), out_gif, fps=15)
    print(f"✅ Created {out_gif} ({os.path.getsize(out_gif):,} bytes)")


# ============================================================================
# GIF 4: All-in-One Showcase (Complete User Journey)
# ============================================================================
def generate_gif4_all_in_one_showcase():
    print("[GIF 4/4] Generating 04_jarvis_showcase.gif...")
    work_dir = os.path.join(TMP_DIR, "gif4")
    shutil.rmtree(work_dir, ignore_errors=True)
    os.makedirs(work_dir, exist_ok=True)

    engine = ChillPixelLifeEngine()
    island = DynamicIsland()
    island.resize(360, 70)

    chat = OverlayChat()
    chat.resize(680, 380)
    chat.on_user_message("สวัสดีครับ จาร์วิส วันนี้มีอัปเดตอะไรใหม่บ้าง?")
    chat.on_assistant_reply(
        "<b>ยินดีต้อนรับครับบอส! อัปเดตล่าสุด v1.9.4 เรียบร้อยแล้ว 🚀</b><br>"
        "• <b>Esc Cancel:</b> กดปุ่ม Esc เพื่อยกเลิกคำสั่งเสียงทันทีโดยไม่ส่งข้อมูล<br>"
        "• <b>Active Screen:</b> หน้าต่างแชทเด้งตามจอ Active ของเมาส์เคอร์เซอร์เสมอ"
    )

    width, height = 800, 560
    total_frames = 90

    # Phases:
    # 0-18: Standby on Menu Bar (Pixel Robot chilling)
    # 19-45: Trigger Voice / Wake Word -> Island pops out -> Listening -> Thinking -> Speaking
    # 46-75: Alt+Space -> Overlay Chat opens & displays interaction
    # 76-90: Esc pressed -> Cancels listening / closes chat -> Returns to Menu Bar Silent Standby
    for f in range(total_frames):
        canvas = QImage(width, height, QImage.Format_ARGB32_Premultiplied)
        canvas.fill(QColor(10, 14, 24))
        p = QPainter(canvas)
        p.setRenderHint(QPainter.Antialiasing)

        # Background
        grad = QLinearGradient(0, 0, width, height)
        grad.setColorAt(0.0, QColor(14, 21, 38))
        grad.setColorAt(1.0, QColor(7, 9, 16))
        p.fillRect(QRectF(0, 0, width, height), grad)

        # Menu bar
        draw_mac_menubar_strip(p, width, y=0)

        # Standby frame
        engine.update(0.06)
        standby_qimg = render_standby_frame(
            engine, scale=2.0, is_wake_on=True,
            is_light_bg=False, audio_level=0.4 if 25 <= f <= 40 else 0.1,
            is_wake_listening=(25 <= f <= 40)
        )
        capsule_x = width - 240
        p.drawImage(capsule_x, 3, standby_qimg.scaled(88, 22, Qt.KeepAspectRatio, Qt.SmoothTransformation))

        # Bottom Phase Banner
        banner_rect = QRectF(25, height - 42, width - 50, 32)
        p.setBrush(QColor(15, 23, 42, 230))
        p.setPen(QColor(0, 229, 255, 45))
        p.drawRoundedRect(banner_rect, 8, 8)

        # Phase logic
        if f <= 18:
            # Standby phase
            p.setFont(QFont("Arial", 9, QFont.Bold))
            p.setPen(QColor(0, 229, 255))
            p.drawText(40, height - 22, "PHASE 1: STANDBY MODE")
            p.setFont(QFont("Arial", 8, QFont.Normal))
            p.setPen(QColor(160, 180, 210))
            p.drawText(210, height - 22, "Native NSStatusItem บนแถบเมนูบาร์ • ไมค์เงียบ 100% ไม่มีไอคอนส้มรบกวน")

            # Center hint
            hint_rect = QRectF((width - 340) // 2, 220, 340, 60)
            p.setBrush(QColor(16, 24, 42, 200))
            p.setPen(QColor(0, 229, 255, 50))
            p.drawRoundedRect(hint_rect, 10, 10)
            p.setFont(QFont("Arial", 11, QFont.Bold))
            p.setPen(QColor(0, 229, 255, 230))
            p.drawText(hint_rect, Qt.AlignCenter, "🤖 J.A.R.V.I.S. Standing By\n(พูด 'Hey Jarvis' หรือกด Alt+Space)")

        elif 19 <= f <= 45:
            # Island popout phase
            p.setFont(QFont("Arial", 9, QFont.Bold))
            p.setPen(QColor(52, 211, 153))
            p.drawText(40, height - 22, "PHASE 2: DYNAMIC ISLAND EXPANSION")
            p.setFont(QFont("Arial", 8, QFont.Normal))
            p.setPen(QColor(160, 180, 210))
            p.drawText(280, height - 22, "สปริง Pop-out เด้งใต้เมนูบาร์ • หุ่นยนต์ 60 FPS ตอบรับตามสถานะ")

            if f <= 28:
                island.on_state_changed("listening")
                island._show_robot_bubble("กำลังฟังเสียงคำสั่ง...", "Silero VAD กรองเสียงชัดเจน", duration=2.0)
            elif f <= 36:
                island.on_state_changed("thinking")
                island._show_robot_bubble("กำลังวิเคราะห์คำสั่ง...", "Gemini 3.5 Flash Lite", duration=2.0)
            else:
                island.on_state_changed("speaking")
                island._show_robot_bubble("กำลังพูดตอบกลับ...", "อ่านออกเสียงไทย-อังกฤษสมจริง", duration=2.0)

            isl_img = island.grab().toImage()
            p.drawImage((width - 360) // 2, 38, isl_img)

        elif 46 <= f <= 75:
            # Overlay Chat phase
            p.setFont(QFont("Arial", 9, QFont.Bold))
            p.setPen(QColor(56, 189, 248))
            p.drawText(40, height - 22, "PHASE 3: OVERLAY CHAT (Alt + Space)")
            p.setFont(QFont("Arial", 8, QFont.Normal))
            p.setPen(QColor(160, 180, 210))
            p.drawText(295, height - 22, "Cyber Glass Overlay • เด้งกึ่งกลางจอ Active ตามตำแหน่งเมาส์เสมอ")

            chat_img = chat.grab().toImage()
            p.drawImage((width - 680) // 2, 50, chat_img)

        else:
            # Esc cancel & fold back phase
            p.setFont(QFont("Arial", 9, QFont.Bold))
            p.setPen(QColor(250, 204, 21))
            p.drawText(40, height - 22, "PHASE 4: INSTANT ESC CANCEL & FOLD")
            p.setFont(QFont("Arial", 8, QFont.Normal))
            p.setPen(QColor(160, 180, 210))
            p.drawText(305, height - 22, "กด Esc ตัดเสียงทันที ทิ้งข้อมูลเสียง 100% คืนสู่โหมดเงียบบน Menu Bar")

            # Center notification card
            esc_card = QRectF((width - 440) // 2, 210, 440, 75)
            p.setBrush(QColor(16, 24, 42, 235))
            p.setPen(QColor(250, 204, 21, 80))
            p.drawRoundedRect(esc_card, 12, 12)
            p.setFont(QFont("Arial", 11, QFont.Bold))
            p.setPen(QColor(250, 204, 21, 240))
            p.drawText(esc_card, Qt.AlignCenter, "🛑 ESC PRESSED: VOICE CANCELLED\nข้อมูลเสียงถูกทิ้ง 100% ไม่ส่งข้อมูลออกไป\nคืนสถานะ Silent Standby บน Menu Bar")

        p.end()
        canvas.save(os.path.join(work_dir, f"frame_{f:03d}.png"))

    out_gif = os.path.join(OUTPUT_DIR, "04_jarvis_showcase.gif")
    run_ffmpeg_gif(os.path.join(work_dir, "frame_%03d.png"), out_gif, fps=15)
    print(f"✅ Created {out_gif} ({os.path.getsize(out_gif):,} bytes)")


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    print("=" * 60)
    print("🎥 GENERATING ALL 4 J.A.R.V.I.S. PREVIEW GIFS")
    print("=" * 60)

    generate_gif1_menubar_standby()
    generate_gif2_dynamic_island_popout()
    generate_gif3_overlay_chat()
    generate_gif4_all_in_one_showcase()

    print("=" * 60)
    print("🎉 ALL 4 PREVIEW GIFS GENERATED SUCCESSFULLY!")
    print(f"Directory: {OUTPUT_DIR}")
    for fname in sorted(os.listdir(OUTPUT_DIR)):
        if fname.endswith(".gif"):
            fpath = os.path.join(OUTPUT_DIR, fname)
            print(f"  • {fname} ({os.path.getsize(fpath):,} bytes)")
    print("=" * 60)


if __name__ == "__main__":
    main()
