import sys
import os
from PySide6.QtWidgets import (QSplashScreen, QProgressBar, QLabel, QVBoxLayout, 
                             QWidget, QGraphicsDropShadowEffect, QGraphicsOpacityEffect)
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup, QSequentialAnimationGroup, QPoint
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient, QRadialGradient, QFontDatabase
import time
from PySide6.QtWidgets import QApplication
import math

VERSION = "1.6"
CODENAME = "Arcade Down"

class ModernProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(2)
        self.setTextVisible(False)
        self.setMaximumWidth(300)
        
        # Улучшенный стиль прогресс-бара
        self.setStyleSheet("""
            QProgressBar {
                border: none;
                background: rgba(255, 255, 255, 0.1);
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #FF1493,
                    stop:0.3 #FFD700,
                    stop:0.6 #FF69B4,
                    stop:1 #FFD700
                );
            }
        """)
        
        # Эффект свечения
        glow = QGraphicsDropShadowEffect(self)
        glow.setBlurRadius(10)
        glow.setColor(QColor(255, 20, 147, 150))  # Розовое свечение
        glow.setOffset(0, 0)
        self.setGraphicsEffect(glow)
        
        # Анимация значения
        self.value_animation = QPropertyAnimation(self, b"value")
        self.value_animation.setEasingCurve(QEasingCurve.OutExpo)
        self.value_animation.setDuration(800)
    
    def setValueSmooth(self, value):
        self.value_animation.stop()
        self.value_animation.setStartValue(self.value())
        self.value_animation.setEndValue(value)
        self.value_animation.start()

class LoadingSplash(QSplashScreen):
    def __init__(self):
        # Создаем пустой QPixmap
        super().__init__(QPixmap(700, 475))
        
        # Настройка окна
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Центрируем окно
        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2
        )
        
        # Основной контейнер
        self.content = QWidget(self)
        self.content.setGeometry(0, 0, self.width(), self.height())
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(20)
        
        # Логотип
        self.logo_label = QLabel()
        logo_pixmap = QPixmap(os.path.join("Resources", "rounded_logo_nova.png"))
        self.logo_label.setPixmap(logo_pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.logo_label.setAlignment(Qt.AlignCenter)
        
        # Загружаем красивый шрифт
        font_id = QFontDatabase.addApplicationFont(os.path.join("Resources", "minecraft-ten-font-cyrillic.ttf"))
        if font_id != -1:
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            title_font = QFont(font_family, 36)
            version_font = QFont(font_family, 16)
            status_font = QFont(font_family, 14)
        else:
            title_font = QFont("Segoe UI", 36, QFont.Bold)
            version_font = QFont("Segoe UI", 16)
            status_font = QFont("Segoe UI", 14)
        
        # Заголовок с улучшенным стилем
        self.title = QLabel("NOVA LAUNCHER")
        self.title.setFont(title_font)
        self.title.setStyleSheet("""
            color: white;
            font-weight: bold;
            letter-spacing: 4px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #FF1493,
                stop:0.5 #FFD700,
                stop:1 #FF1493
            );
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            padding: 10px;
        """)
        self.title.setAlignment(Qt.AlignCenter)
        
        # Версия с улучшенным стилем
        self.version = QLabel(f"v{VERSION} '{CODENAME}'")
        self.version.setFont(version_font)
        self.version.setStyleSheet("""
            color: #FFD700;
            letter-spacing: 2px;
            text-shadow: 0 0 10px rgba(255, 215, 0, 0.5);
        """)
        self.version.setAlignment(Qt.AlignCenter)
        
        # Статус с улучшенным стилем
        self.status = QLabel("Инициализация...")
        self.status.setFont(status_font)
        self.status.setStyleSheet("""
            color: rgba(255, 255, 255, 0.9);
            letter-spacing: 1px;
            background: rgba(0, 0, 0, 0.3);
            padding: 10px 20px;
            border-radius: 15px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        """)
        self.status.setAlignment(Qt.AlignCenter)
        
        # Прогресс-бар
        self.progress = ModernProgressBar()
        
        # Добавляем виджеты
        layout.addStretch(1)
        layout.addWidget(self.logo_label, 0, Qt.AlignCenter)
        layout.addWidget(self.title, 0, Qt.AlignCenter)
        layout.addWidget(self.version, 0, Qt.AlignCenter)
        layout.addSpacing(30)
        layout.addWidget(self.status, 0, Qt.AlignCenter)
        layout.addWidget(self.progress, 0, Qt.AlignCenter)
        layout.addStretch(1)
        
        # Эффекты для виджетов
        for widget in [self.logo_label, self.title, self.version, self.status]:
            glow = QGraphicsDropShadowEffect(widget)
            glow.setBlurRadius(20)
            glow.setColor(QColor(0, 0, 0, 180))
            glow.setOffset(0, 0)
            widget.setGraphicsEffect(glow)
        
        # Анимация появления
        self.fade_in_animation = QSequentialAnimationGroup(self)
        
        # Анимация для каждого виджета
        widgets = [self.logo_label, self.title, self.version, self.status, self.progress]
        for i, widget in enumerate(widgets):
            opacity_effect = QGraphicsOpacityEffect(widget)
            widget.setGraphicsEffect(opacity_effect)
            opacity_effect.setOpacity(0.0)
            
            pause = QTimer()
            pause.setInterval(i * 100)
            pause.setSingleShot(True)
            
            anim = QPropertyAnimation(opacity_effect, b"opacity")
            anim.setDuration(1000)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.OutCubic)
            
            self.fade_in_animation.addAnimation(anim)
            pause.timeout.connect(anim.start)
            pause.start()
        
        self.loading_finished = False
        
    def drawBackground(self, painter):
        """Рисует улучшенный фон с градиентом"""
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Основной градиент
        gradient = QLinearGradient(0, 0, self.width(), self.height())
        gradient.setColorAt(0, QColor(20, 20, 30))
        gradient.setColorAt(1, QColor(30, 30, 45))
        painter.fillRect(self.rect(), gradient)
        
        # Верхнее свечение
        glow = QRadialGradient(
            self.width() / 2, -50,
            self.width() / 1.5
        )
        glow.setColorAt(0, QColor(255, 20, 147, 30))  # Розовое свечение
        glow.setColorAt(0.5, QColor(255, 215, 0, 20))  # Желтое свечение
        glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), glow)
        
        # Дополнительное боковое свечение
        side_glow = QRadialGradient(
            self.width(), self.height() / 2,
            self.width() / 2
        )
        side_glow.setColorAt(0, QColor(255, 215, 0, 20))
        side_glow.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), side_glow)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        self.drawBackground(painter)
        
    def start_progress(self):
        """Запускает анимацию загрузки"""
        self.show()
        self.fade_in_animation.start()
        QTimer.singleShot(500, self.animate_phase1)
    
    def animate_phase1(self):
        self.status.setText("Инициализация лаунчера...")
        self.progress.setValueSmooth(20)
        QTimer.singleShot(1000, self.animate_phase2)
    
    def animate_phase2(self):
        self.status.setText("Проверка обновлений...")
        self.progress.setValueSmooth(40)
        QTimer.singleShot(1000, self.animate_phase3)
    
    def animate_phase3(self):
        self.status.setText("Загрузка настроек...")
        self.progress.setValueSmooth(60)
        QTimer.singleShot(1000, self.animate_phase4)
    
    def animate_phase4(self):
        self.status.setText("Подготовка интерфейса...")
        self.progress.setValueSmooth(80)
        QTimer.singleShot(1000, self.animate_phase5)
    
    def animate_phase5(self):
        self.status.setText("Завершение загрузки...")
        self.progress.setValueSmooth(100)
        QTimer.singleShot(1000, self.complete_loading)
    
    def complete_loading(self):
        self.loading_finished = True
        self.status.setText("Загрузка завершена!")
    
    def finish(self, window):
        if not self.loading_finished:
            self.complete_loading()
        
        # Анимация исчезновения
        fade_out = QParallelAnimationGroup(self)
        
        for widget in [self.logo_label, self.title, self.version, self.status, self.progress]:
            if widget.graphicsEffect():
                anim = QPropertyAnimation(widget.graphicsEffect(), b"opacity")
                anim.setDuration(500)
                anim.setStartValue(1.0)
                anim.setEndValue(0.0)
                anim.setEasingCurve(QEasingCurve.InCubic)
                fade_out.addAnimation(anim)
        
        def show_main_window():
            window.show()
            window.raise_()
            window.activateWindow()
            self.hide()
        
        fade_out.finished.connect(show_main_window)
        fade_out.start() 