#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Fullscreen PySide6 shell with three empty monitor cards."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QCursor,
    QFont,
    QFontDatabase,
    QImage,
    QKeyEvent,
    QPainter,
    QPainterPath,
    QPen,
    QRadialGradient,
)
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


def scaled_radius(height: int, base_px: float) -> int:
    return max(1, round(height * (base_px / 870)))


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


class CameraCard(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._frame_bgr = None
        self._image = None
        self._frame_size = (640, 480)
        self._font_cache = {}
        self._text_cache = {}

    def set_frame(self, frame_bgr) -> None:
        if frame_bgr is not None:
            frame = np.array(frame_bgr, copy=True, order="C")
            height, width = frame.shape[:2]
            bytes_per_line = int(frame.strides[0])
            self._frame_bgr = frame
            self._frame_size = (width, height)
            self._image = QImage(
                self._frame_bgr.data,
                width,
                height,
                bytes_per_line,
                QImage.Format_BGR888,
            )
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)

        card_rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        card_radius = scaled_radius(self.window().height(), 18)
        image_radius = scaled_radius(self.window().height(), 10)
        self._draw_card_background(painter, card_rect, card_radius)

        video_rect = self._video_rect(card_rect)
        if self._image is not None and not self._image.isNull():
            clip = QPainterPath()
            clip.addRoundedRect(video_rect, image_radius, image_radius)
            painter.save()
            painter.setClipPath(clip)
            painter.drawImage(video_rect, self._image)
            painter.restore()

        self._draw_overlay(painter, video_rect)

    def _draw_card_background(self, painter: QPainter, rect: QRectF, radius: int) -> None:
        gradient = QRadialGradient(rect.center(), max(rect.width(), rect.height()) * 0.72)
        gradient.setColorAt(0.0, QColor(PALETTE["card"]))
        gradient.setColorAt(0.48, QColor("#0C171B"))
        gradient.setColorAt(1.0, QColor(PALETTE["background"]))
        painter.setPen(QPen(QColor(PALETTE["card_border"]), 1))
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(rect, radius, radius)

    def _video_rect(self, card_rect: QRectF) -> QRectF:
        available = card_rect.adjusted(1.0, 1.0, -1.0, -1.0)
        aspect = 4.0 / 3.0
        width = available.width()
        height = width / aspect
        if height > available.height():
            height = available.height()
            width = height * aspect
        left = available.left() + (available.width() - width) / 2.0
        top = available.top() + (available.height() - height) / 2.0
        return QRectF(left, top, width, height)

    def _font(self, family: str, fallback: str, pixel_size: int, weight: int, spacing_pct: float) -> QFont:
        key = (family, fallback, pixel_size, weight, spacing_pct)
        if key not in self._font_cache:
            font = QFont(family)
            if not font.exactMatch():
                font = QFont(fallback)
            font.setPixelSize(pixel_size)
            font.setWeight(weight)
            font.setLetterSpacing(QFont.PercentageSpacing, spacing_pct)
            self._font_cache[key] = font
        return self._font_cache[key]

    def _text_width(self, painter: QPainter, cache_key: str, font: QFont, text: str) -> int:
        key = (cache_key, font.pixelSize(), text)
        if key not in self._text_cache:
            painter.setFont(font)
            self._text_cache[key] = painter.fontMetrics().horizontalAdvance(text)
        return self._text_cache[key]

    def _draw_overlay(self, painter: QPainter, video_rect: QRectF) -> None:
        win_h = max(1, self.window().height())
        small_px = max(8, round(win_h * 0.016))
        hint_px = max(10, round(win_h * 0.024))
        inset = video_rect.height() * 0.03

        orbitron = self._font("Orbitron", "Sans Serif", small_px, QFont.Medium, 115.0)
        rajdhani = self._font("Rajdhani", "Sans Serif", hint_px, QFont.DemiBold, 108.0)

        painter.setFont(orbitron)
        metrics = painter.fontMetrics()
        live_y = video_rect.top() + inset + metrics.ascent()
        dot_r = max(3.0, small_px * 0.28)
        alpha = 0.35 + 0.65 * ((time.monotonic() % 1.2) / 1.2)
        if alpha > 0.675:
            alpha = 1.35 - alpha
        alpha = max(0.35, min(1.0, alpha / 0.675))
        dot_color = QColor(PALETTE["red"])
        dot_color.setAlphaF(alpha)
        dot_center = QPointF(video_rect.left() + inset + dot_r, live_y - metrics.ascent() * 0.35)
        painter.setPen(Qt.NoPen)
        painter.setBrush(dot_color)
        painter.drawEllipse(dot_center, dot_r, dot_r)

        painter.setPen(QColor(PALETTE["neon_green"]))
        live_x = dot_center.x() + dot_r + max(5, round(small_px * 0.45))
        painter.drawText(QPointF(live_x, live_y), "LIVE")

        frame_text = f"{self._frame_size[0]} × {self._frame_size[1]}"
        frame_w = self._text_width(painter, "frame_size", orbitron, frame_text)
        painter.setPen(QColor(PALETTE["text_muted"]))
        painter.drawText(QPointF(video_rect.right() - inset - frame_w, live_y), frame_text)

        hint_text = "가만히 화면을 바라봐 주세요"
        painter.setFont(rajdhani)
        hint_metrics = painter.fontMetrics()
        hint_w = self._text_width(painter, "hint", rajdhani, hint_text)
        hint_x = video_rect.center().x() - hint_w / 2.0
        hint_y = video_rect.bottom() - video_rect.height() * 0.04
        shadow = QColor("#000000")
        shadow.setAlpha(150)
        painter.setPen(shadow)
        painter.drawText(QPointF(hint_x + 2, hint_y + 2), hint_text)
        painter.setPen(QColor(PALETTE["text_hint"]))
        painter.drawText(QPointF(hint_x, hint_y), hint_text)


class MonitorShell(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("rPPG Monitor")
        self.setCursor(QCursor(Qt.BlankCursor))
        self.setStyleSheet(f"background: {PALETTE['background']};")

        self.camera_card = CameraCard(self)
        self.bpm_card = QFrame(self)
        self.ekg_card = QFrame(self)

        for card in (self.bpm_card, self.ekg_card):
            card.setFrameShape(QFrame.NoFrame)

        self._apply_card_styles()

    def update_data(self, frame_bgr, last_bpm, wave_samples, face_detected) -> None:
        self.camera_card.set_frame(frame_bgr)
        self._last_bpm = last_bpm
        self._wave_samples = wave_samples
        self._face_detected = face_detected

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
        radius = scaled_radius(self.height(), 18)
        border = PALETTE["card_border"]

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
