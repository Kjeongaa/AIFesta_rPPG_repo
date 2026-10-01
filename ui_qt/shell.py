#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Fullscreen PySide6 shell with three empty monitor cards."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCursor, QFontDatabase, QKeyEvent
from PySide6.QtWidgets import QApplication, QFrame, QWidget


PALETTE = {
    "background": "#05080A",
    "card": "#0A1114",
    "card_border": "#16262B",
    "neon_green": "#B6FF2E",
    "red": "#FF4D5E",
    "text_muted": "#6F8A8F",
    "text_dark": "#4D666B",
    "text_hint": "#D9F5E8",
    "wave_bg": "#000000",
    "grid_minor": "#0B1A0A",
    "grid_major": "#13300F",
}


def load_app_fonts() -> list[str]:
    repo_root = Path(__file__).resolve().parents[1]
    font_dir = repo_root / "assets" / "fonts"
    font_files = sorted(font_dir.glob("*.ttf"))

    if not font_files:
        print(f"[QT UI] No .ttf fonts found in {font_dir}. Falling back to sans-serif.")
        return []

    loaded_families: list[str] = []
    for font_file in font_files:
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        if font_id < 0:
            print(f"[QT UI] Failed to load font: {font_file}")
            continue
        families = QFontDatabase.applicationFontFamilies(font_id)
        loaded_families.extend(families)
        print(f"[QT UI] Loaded font {font_file.name}: {', '.join(families)}")

    if not loaded_families:
        print("[QT UI] Font files were found, but no font families were loaded. Falling back to sans-serif.")
    return loaded_families


class MonitorShell(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("rPPG Monitor")
        self.setCursor(QCursor(Qt.BlankCursor))
        self.setStyleSheet(f"background: {PALETTE['background']};")

        self.camera_card = QFrame(self)
        self.bpm_card = QFrame(self)
        self.ekg_card = QFrame(self)

        for card in (self.camera_card, self.bpm_card, self.ekg_card):
            card.setFrameShape(QFrame.NoFrame)

        self._apply_card_styles()

    def update_data(self, frame_bgr, last_bpm, wave_samples, face_detected) -> None:
        self._latest_frame = None if frame_bgr is None else frame_bgr.copy()
        self._last_bpm = last_bpm
        self._wave_samples = wave_samples
        self._face_detected = face_detected
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Escape:
            self.close()
            return
        super().keyPressEvent(event)

    def resizeEvent(self, event) -> None:
        self._layout_cards()
        self._apply_card_styles()
        super().resizeEvent(event)

    def _layout_cards(self) -> None:
        width = self.width()
        height = self.height()
        margin = round(height * 0.025)
        gap = round(height * 0.02)

        usable_width = max(0, width - (margin * 2) - gap)
        column_width = usable_width // 2
        content_height = max(0, height - (margin * 2))

        left_x = margin
        right_x = margin + column_width + gap
        top_y = margin

        bpm_height = round(height * 0.38)
        ekg_height = max(0, content_height - bpm_height - gap)

        self.camera_card.setGeometry(left_x, top_y, column_width, content_height)
        self.bpm_card.setGeometry(right_x, top_y, column_width, bpm_height)
        self.ekg_card.setGeometry(right_x, top_y + bpm_height + gap, column_width, ekg_height)

    def _apply_card_styles(self) -> None:
        radius = max(1, round(self.height() * (18 / 870)))
        border = PALETTE["card_border"]

        self.camera_card.setStyleSheet(
            f"""
            QFrame {{
                background: qradialgradient(
                    cx: 0.5, cy: 0.5, radius: 0.85,
                    fx: 0.5, fy: 0.5,
                    stop: 0 {PALETTE['card']},
                    stop: 0.48 #0C171B,
                    stop: 1 {PALETTE['background']}
                );
                border: 1px solid {border};
                border-radius: {radius}px;
            }}
            """
        )
        self.bpm_card.setStyleSheet(
            f"""
            QFrame {{
                background: {PALETTE['card']};
                border: 1px solid {border};
                border-radius: {radius}px;
            }}
            """
        )
        self.ekg_card.setStyleSheet(
            f"""
            QFrame {{
                background: {PALETTE['wave_bg']};
                border: 1px solid {border};
                border-radius: {radius}px;
            }}
            """
        )


def main() -> int:
    app = QApplication(sys.argv)
    load_app_fonts()

    window = MonitorShell()
    window.showFullScreen()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
