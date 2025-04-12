import sys
import os
from PySide6.QtWidgets import (
    QSplashScreen, QLabel, QWidget, QApplication,
    QGraphicsDropShadowEffect, QVBoxLayout
)
from PySide6.QtCore import (
    Qt, QTimer, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
    QPointF, Property, QRect, QObject, Signal, Slot
)
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QFont, QFontDatabase, QTransform
)

# --- Виджет логотипа ---
class RotatingLogo(QLabel):
    """Виджет QLabel с вращением и тенью (для эффекта прозрачности)."""
    def __init__(self, pixmap, parent=None):
        super().__init__(parent)
        self.base_pixmap = pixmap
        self._rotation_angle = 0.0
        self.setPixmap(self.base_pixmap)
        self.setAlignment(Qt.AlignCenter)

        self._shadow_effect = QGraphicsDropShadowEffect(self)
        self._shadow_effect.setBlurRadius(20)
        self._shadow_effect.setColor(QColor(0, 0, 0, 0)) # Начинаем прозрачной
        self._shadow_effect.setOffset(5, 5)
        self.setGraphicsEffect(self._shadow_effect)

    @Property(float)
    def rotationAngle(self): return self._rotation_angle
    @rotationAngle.setter
    def rotationAngle(self, angle): self._rotation_angle = angle % 360; self.update()

    @Property(QColor)
    def shadowColor(self): return self._shadow_effect.color() if self._shadow_effect else QColor(0,0,0,0)
    @shadowColor.setter
    def shadowColor(self, color):
        if self._shadow_effect: self._shadow_effect.setColor(color)

    @Property(float)
    def shadowBlurRadius(self): return self._shadow_effect.blurRadius() if self._shadow_effect else 0.0
    @shadowBlurRadius.setter
    def shadowBlurRadius(self, radius):
        if self._shadow_effect: self._shadow_effect.setBlurRadius(max(0, radius))

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing); painter.setRenderHint(QPainter.SmoothPixmapTransform)
        cx = self.width() / 2; cy = self.height() / 2
        painter.translate(cx, cy); painter.rotate(self._rotation_angle); painter.translate(-cx, -cy)
        pix = self.pixmap()
        if pix and not pix.isNull():
            margin = 2 # Небольшой отступ
            target_rect = self.rect().adjusted(margin, margin, -margin, -margin)
            painter.drawPixmap(target_rect, pix)


# --- Красивый и Простой Сплеш-скрин ---
class AnimatedSplashScreen(QSplashScreen):
    """Простой сплеш-скрин с красивыми и плавными анимациями."""

    # --- Константы Анимации ---
    WINDOW_SIZE = 600
    LOGO_BASE_SIZE = 280
    APPEAR_DURATION = 1600 # мс
    DISAPPEAR_DURATION = 800 # мс
    ROTATION_APPEAR_START = -90.0
    ROTATION_DISAPPEAR_OFFSET = 90.0
    SHADOW_BASE_COLOR = QColor(15, 15, 25, 110) # Темно-синяя, полупрозрачная
    SHADOW_BASE_BLUR = 25.0
    SCALE_APPEAR_OVERSHOOT = 1.1 # Насколько масштаб "выпрыгивает" (для OutBack)

    def __init__(self):
        print("[Splash] Init Start (Simple & Beautiful)")
        pixmap = QPixmap(self.WINDOW_SIZE, self.WINDOW_SIZE); pixmap.fill(Qt.transparent)
        super().__init__(pixmap)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.SplashScreen)
        self.setAttribute(Qt.WA_TranslucentBackground); self.setAttribute(Qt.WA_DeleteOnClose)
        self._main_window = None
        self._current_logo_scale = 0.0

        logo_path = os.path.join("Resources", "rounded_logo_nova.png")
        self.logo_pixmap = QPixmap(logo_path).scaled(self.LOGO_BASE_SIZE, self.LOGO_BASE_SIZE, Qt.KeepAspectRatio, Qt.SmoothTransformation) \
                           if os.path.exists(logo_path) else self._create_placeholder_logo(self.LOGO_BASE_SIZE)

        self.logo_label = RotatingLogo(self.logo_pixmap, self)
        self.logo_label.setGeometry(self._calculate_logo_rect(0))

        self._appear_group = self._create_appear_animation()
        self._disappear_group = self._create_disappear_animation()
        self.center_window()
        print("[Splash] Init Complete (Simple & Beautiful)")

    # --- Вспомогательные методы ---
    def _create_placeholder_logo(self, size):
        pix = QPixmap(size, size); pix.fill(QColor(45, 45, 55))
        p = QPainter(pix); p.setPen(QColor(200, 200, 220)); p.setFont(QFont("Arial", size // 4, QFont.Bold))
        p.drawText(pix.rect(), Qt.AlignCenter, "N"); p.end(); return pix

    def _calculate_logo_rect(self, current_visual_size):
        size = max(0, int(current_visual_size)); x = (self.WINDOW_SIZE - size) // 2; y = (self.WINDOW_SIZE - size) // 2
         return QRect(x, y, size, size)

    # --- Свойство Масштаба ---
    @Property(float)
    def logoScale(self): return self._current_logo_scale
    @logoScale.setter
    def logoScale(self, scale):
        self._current_logo_scale = max(0.0, scale)
        if hasattr(self, 'logo_label') and self.logo_label:
            vs = self.LOGO_BASE_SIZE * self._current_logo_scale; self.logo_label.setGeometry(self._calculate_logo_rect(vs))
            if self.logo_pixmap and not self.logo_pixmap.isNull(): self.logo_label.setPixmap(self.logo_pixmap.scaled(int(vs), int(vs), Qt.KeepAspectRatio, Qt.SmoothTransformation) if vs > 1 else QPixmap())

    # --- Создание Анимаций ---
    def _create_appear_animation(self):
        print("[Splash] Creating Appear Animation (Simple & Beautiful)")
        group = QParallelAnimationGroup(self)

        # Масштаб (с легким отскоком)
        scale = QPropertyAnimation(self, b"logoScale", group)
        scale.setDuration(self.APPEAR_DURATION); scale.setStartValue(0.0); scale.setEndValue(1.0)
        curve_scale = QEasingCurve(QEasingCurve.OutBack) # Красивый отскок
        curve_scale.setOvershoot(self.SCALE_APPEAR_OVERSHOOT)
        scale.setEasingCurve(curve_scale); group.addAnimation(scale)

        # Вращение (плавное)
        rotate = QPropertyAnimation(self.logo_label, b"rotationAngle", group)
        rotate.setDuration(int(self.APPEAR_DURATION * 1.1)); # Чуть дольше масштаба
        rotate.setStartValue(self.ROTATION_APPEAR_START); rotate.setEndValue(0.0)
        rotate.setEasingCurve(QEasingCurve.OutCubic); group.addAnimation(rotate) # Плавный выход

        # Цвет/Прозрачность Тени
        shadow_c = QPropertyAnimation(self.logo_label, b"shadowColor", group)
        shadow_c.setDuration(int(self.APPEAR_DURATION * 0.8)) # Появляется быстрее
        shadow_c.setStartValue(QColor(0,0,0,0)); shadow_c.setEndValue(self.SHADOW_BASE_COLOR)
        shadow_c.setEasingCurve(QEasingCurve.OutCubic); group.addAnimation(shadow_c)

        # Размытие Тени
        shadow_b = QPropertyAnimation(self.logo_label, b"shadowBlurRadius", group)
        shadow_b.setDuration(int(self.APPEAR_DURATION * 0.8))
        shadow_b.setStartValue(self.SHADOW_BASE_BLUR - 15); shadow_b.setEndValue(self.SHADOW_BASE_BLUR)
        shadow_b.setEasingCurve(QEasingCurve.OutCubic); group.addAnimation(shadow_b)

        return group

    def _create_disappear_animation(self):
        print("[Splash] Creating Disappear Animation (Simple & Beautiful)")
        group = QParallelAnimationGroup(self)
        curve = QEasingCurve.InOutQuad # Плавное замедление

        # Масштаб
        scale = QPropertyAnimation(self, b"logoScale", group)
        scale.setDuration(self.DISAPPEAR_DURATION); scale.setStartValue(1.0); scale.setEndValue(0.0)
        scale.setEasingCurve(curve); group.addAnimation(scale)

        # Вращение
        rotate = QPropertyAnimation(self.logo_label, b"rotationAngle", group)
        rotate.setDuration(self.DISAPPEAR_DURATION); rotate.setEasingCurve(curve)
        group.addAnimation(rotate) # Start/End в finish

        # Цвет/Прозрачность Тени
        shadow_c = QPropertyAnimation(self.logo_label, b"shadowColor", group)
        shadow_c.setDuration(int(self.DISAPPEAR_DURATION * 0.9)) # Исчезает чуть быстрее
        shadow_c.setStartValue(self.SHADOW_BASE_COLOR); shadow_c.setEndValue(QColor(0,0,0,0))
        shadow_c.setEasingCurve(curve); group.addAnimation(shadow_c)

        # Размытие Тени
        shadow_b = QPropertyAnimation(self.logo_label, b"shadowBlurRadius", group)
        shadow_b.setDuration(int(self.DISAPPEAR_DURATION * 0.9))
        shadow_b.setStartValue(self.SHADOW_BASE_BLUR); shadow_b.setEndValue(self.SHADOW_BASE_BLUR - 10)
        shadow_b.setEasingCurve(curve); group.addAnimation(shadow_b)

        group.finished.connect(self._on_disappear_finished)
        return group

    # --- Управление анимацией ---
    def start_animation(self):
        print("[Splash] Start Appear (Simple & Beautiful)")
        self.logoScale = 0.0
        self.logo_label.rotationAngle = self.ROTATION_APPEAR_START
        self.logo_label.shadowColor = QColor(0,0,0,0)
        self.logo_label.shadowBlurRadius = self.SHADOW_BASE_BLUR - 15
        self.show(); self._appear_group.start()
        print("[Splash] Appear Started (Simple & Beautiful)")
    
    def finish(self, window):
        print("[Splash] Start Disappear (Simple & Beautiful)")
        if self._appear_group and self._appear_group.state() == QPropertyAnimation.Running:
            print("[Splash] Stopping Appear Anim (Simple & Beautiful)")
            self._appear_group.stop()
        self._main_window = window

        current_scale = self.logoScale
        current_angle = self.logo_label.rotationAngle
        current_shadow_color = self.logo_label.shadowColor
        current_shadow_blur = self.logo_label.shadowBlurRadius

        try:
            scale_anim = self._disappear_group.animationAt(0)
            rotate_anim = self._disappear_group.animationAt(1)
            color_anim = self._disappear_group.animationAt(2)
            blur_anim = self._disappear_group.animationAt(3)

            if isinstance(scale_anim, QPropertyAnimation): scale_anim.setStartValue(current_scale)
            if isinstance(rotate_anim, QPropertyAnimation):
                rotate_anim.setStartValue(current_angle)
                rotate_anim.setEndValue(current_angle + self.ROTATION_DISAPPEAR_OFFSET)
            if isinstance(color_anim, QPropertyAnimation): color_anim.setStartValue(current_shadow_color)
            if isinstance(blur_anim, QPropertyAnimation): blur_anim.setStartValue(current_shadow_blur)

        except IndexError as ie: print(f"[Splash] IndexError setting disappear start values: {ie}")
        except Exception as e: print(f"[Splash] Error setting disappear start values: {e}")
        finally:
             self._disappear_group.start()
             print("[Splash] Disappear Started (Simple & Beautiful)")

    @Slot()
    def _on_disappear_finished(self):
        print("[Splash] Disappear Finished (Simple & Beautiful)")
        self._show_main_window()

    def _show_main_window(self):
        print("[Splash] Show Main Window (Simple & Beautiful)")
        if self._main_window:
            try:
                screen = QApplication.primaryScreen().geometry(); mw_size = self._main_window.size()
                self._main_window.move(screen.center().x()-mw_size.width()//2, screen.center().y()-mw_size.height()//2)
                self._main_window.show(); self._main_window.raise_(); self._main_window.activateWindow()
                print("[Splash] Main Window Shown (Simple & Beautiful)")
            except Exception as e: print(f"[Splash] Error Showing Main: {e}")
        else: print("[Splash] Warning: Main Window is None (Simple & Beautiful)")
        print("[Splash] Closing Splash (Simple & Beautiful)")
        self.close()

    def center_window(self):
        try: screen = QApplication.primaryScreen().geometry(); self.move(screen.center().x()-self.width()//2, screen.center().y()-self.height()//2)
        except Exception as e: print(f"[Splash] Error Centering Splash: {e}")

    def paintEvent(self, event): super().paintEvent(event)

# --- Тестовый запуск ---
if __name__ == '__main__':
    if hasattr(Qt, 'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv)

    splash = AnimatedSplashScreen()
    splash.start_animation()

    class MockMainWindow(QWidget):
        def __init__(self):
            super().__init__(); self.setWindowTitle("Mock Main"); self.resize(800, 600)
            label = QLabel("Main Window", self); label.setFont(QFont("Arial", 20)); label.setAlignment(Qt.AlignCenter)
            layout = QVBoxLayout(self); layout.addWidget(label)

    mock_window = MockMainWindow()
    QTimer.singleShot(4000, lambda: splash.finish(mock_window)) # Показываем 4 сек
    sys.exit(app.exec()) 