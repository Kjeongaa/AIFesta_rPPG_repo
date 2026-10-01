#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Fullscreen PySide6 shell with three empty monitor cards."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, QRectF, Qt, QTimer
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
    QPixmap,
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


class BpmCard(QWidget):
    HEART_PERIOD = 0.83

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._bpm_text = "--"
        self._has_bpm = False
        self._font_cache = {}
        self._number_cache_key = None
        self._number_cache = None
        self._heart_rect = QRectF()
        self._beat_start = time.monotonic()
        self._beat_timer = QTimer(self)
        self._beat_timer.setInterval(33)
        self._beat_timer.timeout.connect(self._update_heart)

    def set_bpm(self, last_bpm) -> None:
        has_bpm = last_bpm is not None and last_bpm != 0
        bpm_text = "--" if not has_bpm else f"{int(last_bpm)}"
        changed = bpm_text != self._bpm_text or has_bpm != self._has_bpm
        self._bpm_text = bpm_text
        self._has_bpm = has_bpm

        if self._has_bpm and not self._beat_timer.isActive():
            self._beat_start = time.monotonic()
            self._beat_timer.start()
        elif not self._has_bpm and self._beat_timer.isActive():
            self._beat_timer.stop()
            self.update(self._heart_rect.toAlignedRect())

        if changed:
            self._number_cache_key = None
            self.update()

    def preferred_height(self, window_height: int) -> int:
        number_px = max(64, round(window_height * 0.26))
        vertical_pad = round(window_height * 0.02) * 2
        return number_px + vertical_pad

    def paintEvent(self, event) -> None:
        update_rect = QRectF(event.rect())
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
        painter.setClipRect(event.rect())

        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = scaled_radius(self.window().height(), 18)
        painter.setPen(QPen(QColor(PALETTE["card_border"]), 1))
        painter.setBrush(QColor(PALETTE["card"]))
        painter.drawRoundedRect(rect, radius, radius)

        layout = self._layout(rect)
        if update_rect.intersects(layout["heart"].adjusted(-8, -8, 8, 8)):
            self._draw_heart(painter, layout["heart"])
        if update_rect.intersects(layout["number"]):
            self._draw_number(painter, layout["number"], layout["number_font"])
        if update_rect.intersects(layout["unit"]):
            self._draw_units(painter, layout["unit"], layout["unit_font"], layout["label_font"])

    def resizeEvent(self, event) -> None:
        self._number_cache_key = None
        super().resizeEvent(event)

    def _update_heart(self) -> None:
        if self._has_bpm:
            self.update(self._heart_rect.toAlignedRect().adjusted(-8, -8, 8, 8))

    def _font(self, family: str, fallback: str, pixel_size: int, weight: int, spacing_pct: float = 100.0) -> QFont:
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

    def _layout(self, rect: QRectF) -> dict:
        win_h = max(1, self.window().height())
        win_w = max(1, self.window().width())
        gap = win_w * 0.03
        pad_y = win_h * 0.02
        pad_x = win_h * 0.02

        scale = 1.0
        available_width = max(1.0, rect.width() - pad_x * 2.0)
        while True:
            number_px = max(48, round(win_h * 0.26 * scale))
            unit_px = max(14, round(win_h * 0.034 * scale))
            label_px = max(8, round(win_h * 0.018 * scale))
            heart_size = max(30.0, win_h * 0.09 * scale)
            scaled_gap = gap * scale

            number_font = self._font("Orbitron", "Sans Serif", number_px, QFont.ExtraBold)
            unit_font = self._font("Orbitron", "Sans Serif", unit_px, QFont.Medium, 120.0)
            label_font = self._font("Rajdhani", "Sans Serif", label_px, QFont.DemiBold, 112.0)

            number_width = self._number_width(number_font)
            unit_width = max(
                self._text_width(unit_font, "BPM"),
                self._text_width(label_font, "HEART RATE"),
            )
            content_width = heart_size + scaled_gap + number_width + scaled_gap + unit_width
            if content_width <= available_width or scale <= 0.62:
                break
            scale *= available_width / content_width

        left = rect.center().x() - content_width / 2.0

        number_height = self._text_height(number_font)
        center_y = rect.top() + pad_y + max(heart_size, number_height) / 2.0
        center_y = max(center_y, rect.center().y())

        heart_rect = QRectF(left, center_y - heart_size / 2.0, heart_size, heart_size)
        number_rect = QRectF(
            heart_rect.right() + scaled_gap,
            center_y - number_height / 2.0,
            number_width,
            number_height,
        )
        unit_height = self._text_height(unit_font) + self._text_height(label_font) * 0.95
        unit_rect = QRectF(
            number_rect.right() + scaled_gap,
            center_y - unit_height / 2.0,
            unit_width,
            unit_height,
        )
        self._heart_rect = heart_rect
        return {
            "heart": heart_rect,
            "number": number_rect,
            "unit": unit_rect,
            "number_font": number_font,
            "unit_font": unit_font,
            "label_font": label_font,
        }

    def _number_width(self, font: QFont) -> int:
        return max(self._text_width(font, "888"), self._text_width(font, "--"))

    def _text_width(self, font: QFont, text: str) -> int:
        metrics = self.fontMetrics()
        old_font = self.font()
        self.setFont(font)
        metrics = self.fontMetrics()
        width = metrics.horizontalAdvance(text)
        self.setFont(old_font)
        return width

    def _text_height(self, font: QFont) -> int:
        old_font = self.font()
        self.setFont(font)
        height = self.fontMetrics().height()
        self.setFont(old_font)
        return height

    def _draw_heart(self, painter: QPainter, rect: QRectF) -> None:
        phase = 0.0 if not self._has_bpm else ((time.monotonic() - self._beat_start) % self.HEART_PERIOD) / self.HEART_PERIOD
        if not self._has_bpm:
            scale = 1.0
        elif phase <= 0.12:
            scale = 1.0 + 0.22 * (phase / 0.12)
        elif phase <= 0.28:
            scale = 1.22 - 0.22 * ((phase - 0.12) / 0.16)
        else:
            scale = 1.0

        draw_rect = QRectF(rect)
        center = draw_rect.center()
        draw_rect.setWidth(rect.width() * scale)
        draw_rect.setHeight(rect.height() * scale)
        draw_rect.moveCenter(center)

        path = self._heart_path(draw_rect)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(PALETTE["red"]))
        painter.drawPath(path)

    def _heart_path(self, rect: QRectF) -> QPainterPath:
        x = rect.x()
        y = rect.y()
        w = rect.width()
        h = rect.height()
        path = QPainterPath()
        path.moveTo(x + 0.50 * w, y + 0.88 * h)
        path.cubicTo(x + 0.08 * w, y + 0.62 * h, x + 0.00 * w, y + 0.34 * h, x + 0.18 * w, y + 0.18 * h)
        path.cubicTo(x + 0.34 * w, y + 0.04 * h, x + 0.48 * w, y + 0.17 * h, x + 0.50 * w, y + 0.28 * h)
        path.cubicTo(x + 0.52 * w, y + 0.17 * h, x + 0.66 * w, y + 0.04 * h, x + 0.82 * w, y + 0.18 * h)
        path.cubicTo(x + 1.00 * w, y + 0.34 * h, x + 0.92 * w, y + 0.62 * h, x + 0.50 * w, y + 0.88 * h)
        path.closeSubpath()
        return path

    def _draw_number(self, painter: QPainter, rect: QRectF, font: QFont) -> None:
        pixmap = self._number_pixmap(font, rect.size().toSize())
        painter.drawPixmap(rect.topLeft(), pixmap)

    def _number_pixmap(self, font: QFont, size) -> QPixmap:
        key = (self._bpm_text, font.pixelSize(), size.width(), size.height())
        if self._number_cache_key == key and self._number_cache is not None:
            return self._number_cache

        glow_margin = max(8, round(font.pixelSize() * 0.05))
        pixmap = QPixmap(size.width() + glow_margin * 2, size.height() + glow_margin * 2)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setFont(font)
        text_rect = QRectF(glow_margin, glow_margin, size.width(), size.height())

        glow = QColor(PALETTE["neon_green"])
        glow.setAlphaF(0.45)
        painter.setPen(glow)
        for offset in (-4, -2, 2, 4):
            painter.drawText(text_rect.translated(offset, 0), Qt.AlignCenter, self._bpm_text)
            painter.drawText(text_rect.translated(0, offset), Qt.AlignCenter, self._bpm_text)
        painter.setPen(QColor(PALETTE["neon_green"]))
        painter.drawText(text_rect, Qt.AlignCenter, self._bpm_text)
        painter.end()

        final = QPixmap(size)
        final.fill(Qt.transparent)
        final_painter = QPainter(final)
        final_painter.drawPixmap(-glow_margin, -glow_margin, pixmap)
        final_painter.end()

        self._number_cache_key = key
        self._number_cache = final
        return final

    def _draw_units(self, painter: QPainter, rect: QRectF, unit_font: QFont, label_font: QFont) -> None:
        painter.setFont(unit_font)
        unit_metrics = painter.fontMetrics()
        bpm_y = rect.top() + unit_metrics.ascent()
        painter.setPen(QColor(PALETTE["text_muted"]))
        painter.drawText(QPointF(rect.left(), bpm_y), "BPM")

        painter.setFont(label_font)
        label_metrics = painter.fontMetrics()
        label_y = bpm_y + unit_metrics.descent() + label_metrics.height() * 0.95
        painter.setPen(QColor(PALETTE["text_dark"]))
        painter.drawText(QPointF(rect.left(), label_y), "HEART RATE")


class MonitorShell(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("rPPG Monitor")
        self.setCursor(QCursor(Qt.BlankCursor))
        self.setStyleSheet(f"background: {PALETTE['background']};")

        self.camera_card = CameraCard(self)
        self.bpm_card = BpmCard(self)
        self.ekg_card = QFrame(self)

        for card in (self.ekg_card,):
            card.setFrameShape(QFrame.NoFrame)

        self._apply_card_styles()

    def update_data(self, frame_bgr, last_bpm, wave_samples, face_detected) -> None:
        self.camera_card.set_frame(frame_bgr)
        self.bpm_card.set_bpm(last_bpm)
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

        bpm_height = min(content_height, self.bpm_card.preferred_height(height))
        ekg_height = max(0, content_height - bpm_height - gap)

        self.camera_card.setGeometry(left_x, top_y, column_width, content_height)
        self.bpm_card.setGeometry(right_x, top_y, column_width, bpm_height)
        self.ekg_card.setGeometry(right_x, top_y + bpm_height + gap, column_width, ekg_height)

    def _apply_card_styles(self) -> None:
        radius = scaled_radius(self.height(), 18)
        border = PALETTE["card_border"]

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
