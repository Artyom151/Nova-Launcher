import sys
import os
from PySide6.QtWidgets import QSplashScreen, QProgressBar, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QSize, QRect, QParallelAnimationGroup
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient, QPainterPath, QRegion, QRadialGradient
import time
from PySide6.QtWidgets import QApplication

VERSION = "1.5"
CODENAME = "Angel Falling"

class SimpleProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(4)
        self.setTextVisible(False)
        self.setValue(0)
        
        # Улучшенный стиль прогресс-бара с более плавным градиентом
        self.setStyleSheet("""
            QProgressBar {
                border: none;
                background: rgba(255, 255, 255, 0.08);
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                    stop:0 #FFD700, 
                    stop:0.3 #FFC0CB,
                    stop:0.6 #FF69B4,
                    stop:0.8 #FF1493,
                    stop:1 #FF00FF);
                border-radius: 2px;
            }
        """)
        
        # Создаем анимацию для плавного увеличения значения
        self.animation = QPropertyAnimation(self, b"value")
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # Создаем эффект размытия для движения
        self.trail_widgets = []
        for i in range(3):
            trail = QProgressBar(self)
            trail.setFixedHeight(4)
            trail.setTextVisible(False)
            trail.setStyleSheet(f"""
                QProgressBar {{
                    border: none;
                    background: transparent;
                    border-radius: 2px;
                }}
                QProgressBar::chunk {{
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, 
                        stop:0 rgba(255, 215, 0, {40 - i*10}),
                        stop:0.3 rgba(255, 192, 203, {40 - i*10}),
                        stop:0.6 rgba(255, 105, 180, {40 - i*10}),
                        stop:0.8 rgba(255, 20, 147, {40 - i*10}),
                        stop:1 rgba(255, 0, 255, {40 - i*10}));
                    border-radius: 2px;
                }}
            """)
            trail.hide()
            self.trail_widgets.append(trail)
            
        # Анимации для следов
        self.trail_animations = []
        for trail in self.trail_widgets:
            anim = QPropertyAnimation(trail, b"value")
            anim.setEasingCurve(QEasingCurve.OutCubic)
            self.trail_animations.append(anim)
        
    def setValueSmooth(self, value, duration=500):
        """Плавно устанавливает значение прогресс-бара с эффектом размытия движения"""
        current = self.value()
        
        # Показываем следы
        for trail in self.trail_widgets:
            trail.show()
            trail.setValue(current)
            trail.raise_()
        
        # Настраиваем анимацию основного прогресс-бара
        self.animation.stop()
        self.animation.setStartValue(current)
        self.animation.setEndValue(value)
        self.animation.setDuration(duration)
        
        # Настраиваем анимации следов с разными задержками
        for i, (trail, trail_anim) in enumerate(zip(self.trail_widgets, self.trail_animations)):
            delay_factor = 0.2 * (i + 1)  # Каждый след начинает двигаться с задержкой
            trail_anim.stop()
            trail_anim.setStartValue(current)
            trail_anim.setEndValue(value)
            trail_anim.setDuration(int(duration * (1 + delay_factor)))
            
            # Запускаем анимации
            trail_anim.start()
        
        # Запускаем основную анимацию
        self.animation.start()
        
        # Скрываем следы после завершения анимации
        QTimer.singleShot(duration + 100, lambda: [trail.hide() for trail in self.trail_widgets])

class LoadingSplash(QSplashScreen):
    def __init__(self):
        # Загружаем фоновое изображение для определения размеров
        self.background = QPixmap("Resources/minecraft_launcher.png")
        if self.background.isNull():
            self.background = QPixmap(800, 450)
            self.background.fill(Qt.transparent)
        
        # Создаем пустой QPixmap нужного размера
        super().__init__(QPixmap(self.background.size()))
        
        # Устанавливаем флаги окна
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_NoSystemBackground)
        
        # Центрируем окно на экране
        screen = QApplication.primaryScreen().geometry()
        self.move(
            screen.center().x() - self.width() // 2,
            screen.center().y() - self.height() // 2
        )
        
        # Основной контейнер
        self.content = QWidget(self)
        self.content.setGeometry(0, 0, self.background.width(), self.background.height())
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(15)
        
        # Заголовок с улучшенным стилем
        self.title = QLabel("NOVA LAUNCHER")
        self.title.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 32px;
                font-weight: bold;
                font-family: 'Segoe UI';
                letter-spacing: 2px;
                background-color: rgba(0, 0, 0, 0.3);
                border-radius: 10px;
                padding: 10px 20px;
            }
        """)
        self.title.setAlignment(Qt.AlignCenter)
        
        # Версия и кодовое имя с улучшенным стилем
        self.version = QLabel(f"v{VERSION} '{CODENAME}'")
        self.version.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                font-family: 'Segoe UI';
                font-weight: 500;
                letter-spacing: 1px;
                background-color: rgba(67, 160, 71, 0.2);
                border: 1px solid rgba(67, 160, 71, 0.3);
                border-radius: 10px;
                padding: 4px 12px;
            }
        """)
        self.version.setAlignment(Qt.AlignCenter)
        
        # Статус с улучшенным стилем
        self.status = QLabel("Инициализация...")
        self.status.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 16px;
                font-family: 'Segoe UI';
                font-weight: 500;
                letter-spacing: 0.5px;
                background-color: rgba(0, 0, 0, 0.3);
                border-radius: 8px;
                padding: 8px 16px;
            }
        """)
        self.status.setAlignment(Qt.AlignCenter)
        
        # Прогресс-бар (используем простую версию)
        self.progress = SimpleProgressBar()
        self.progress.setMaximumWidth(400)
        
        # Добавляем виджеты
        layout.addStretch(2)
        layout.addWidget(self.title)
        layout.addWidget(self.version, 0, Qt.AlignCenter)
        layout.addSpacing(10)
        layout.addWidget(self.status)
        layout.addWidget(self.progress, 0, Qt.AlignCenter)
        layout.addStretch(3)
        
        # Переменные для отслеживания прогресса
        self.loading_finished = False
        self.current_progress = 0
        
        # Показываем окно сразу с полной прозрачностью
        self.setWindowOpacity(1.0)
        self.show()
    
    def drawContents(self, painter: QPainter):
        # Включаем сглаживание
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Рисуем фоновое изображение
        if not self.background.isNull():
            painter.drawPixmap(0, 0, self.background)
        
        # Создаем темную виньетку
        # Внешний градиент (темная рамка)
        outer_gradient = QLinearGradient(0, 0, 0, self.height())
        outer_gradient.setColorAt(0, QColor(0, 0, 0, 180))  # Темный верх
        outer_gradient.setColorAt(0.4, QColor(0, 0, 0, 120))  # Более светлый центр
        outer_gradient.setColorAt(0.6, QColor(0, 0, 0, 120))  # Более светлый центр
        outer_gradient.setColorAt(1, QColor(0, 0, 0, 180))  # Темный низ
        painter.fillRect(self.rect(), outer_gradient)
        
        # Боковая виньетка
        left_gradient = QLinearGradient(0, 0, self.width() * 0.3, 0)
        left_gradient.setColorAt(0, QColor(0, 0, 0, 180))
        left_gradient.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), left_gradient)
        
        right_gradient = QLinearGradient(self.width(), 0, self.width() * 0.7, 0)
        right_gradient.setColorAt(0, QColor(0, 0, 0, 180))
        right_gradient.setColorAt(1, QColor(0, 0, 0, 0))
        painter.fillRect(self.rect(), right_gradient)
        
        # Добавляем легкое свечение в центре
        center_glow = QRadialGradient(
            self.width() / 2, self.height() / 2,  # центр
            min(self.width(), self.height()) / 2   # радиус
        )
        center_glow.setColorAt(0, QColor(255, 255, 255, 10))  # Очень легкое свечение в центре
        center_glow.setColorAt(0.5, QColor(255, 255, 255, 0))  # Постепенно исчезает
        center_glow.setColorAt(1, QColor(0, 0, 0, 0))  # Полностью прозрачный край
        painter.fillRect(self.rect(), center_glow)
    
    def start_progress(self):
        """Начинает процесс отображения прогресса загрузки"""
        # Окно уже должно быть видимым, просто делаем его прозрачным
        self.fadeIn()
        
        # Сбрасываем прогресс
        self.current_progress = 0
        self.progress.setValue(0)
        
        # Запускаем плавную анимацию загрузки
        QTimer.singleShot(500, self.animate_phase1)
    
    def animate_phase1(self):
        """Плавная анимация первой фазы (0-20%)"""
        self.status.setText("Инициализация лаунчера...")
        self.progress.setValueSmooth(20, 1000)
        QTimer.singleShot(1100, self.animate_phase2)
    
    def animate_phase2(self):
        """Плавная анимация второй фазы (20-40%)"""
        self.status.setText("Проверка обновлений...")
        self.progress.setValueSmooth(40, 1000)
        QTimer.singleShot(1100, self.animate_phase3)
    
    def animate_phase3(self):
        """Плавная анимация третьей фазы (40-60%)"""
        self.status.setText("Загрузка настроек...")
        self.progress.setValueSmooth(60, 1000)
        QTimer.singleShot(1100, self.animate_phase4)
    
    def animate_phase4(self):
        """Плавная анимация четвертой фазы (60-80%)"""
        self.status.setText("Подготовка интерфейса...")
        self.progress.setValueSmooth(80, 1000)
        QTimer.singleShot(1100, self.animate_phase5)
    
    def animate_phase5(self):
        """Плавная анимация финальной фазы (80-100%)"""
        self.status.setText("Завершение загрузки...")
        self.progress.setValueSmooth(100, 1200)
        QTimer.singleShot(1300, self.complete_loading)
    
    def complete_loading(self):
        """Завершает загрузку"""
        self.status.setText("Загрузка завершена!")
        self.progress.setValue(100)
        self.loading_finished = True
        print("Загрузка завершена, готов к закрытию!")
    
    def fadeIn(self):
        """Улучшенная анимация появления splash screen"""
        print("Начинаю анимацию появления splash screen...")
        
        # Принудительно поднимаем окно наверх
        self.raise_()
        self.activateWindow()
        
        # Создаем анимацию появления
        fade_in = QPropertyAnimation(self, b"windowOpacity")
        fade_in.setDuration(1000)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.OutCubic)
        
        # Создаем анимацию масштабирования
        scale_in = QPropertyAnimation(self, b"geometry")
        scale_in.setDuration(1000)
        initial_rect = self.geometry()
        scaled_rect = initial_rect
        scaled_rect.setSize(scaled_rect.size() * 0.95)
        scale_in.setStartValue(scaled_rect)
        scale_in.setEndValue(initial_rect)
        scale_in.setEasingCurve(QEasingCurve.OutCubic)
        
        # Запускаем анимации параллельно
        self.anim_group = QParallelAnimationGroup(self)
        self.anim_group.addAnimation(fade_in)
        self.anim_group.addAnimation(scale_in)
        
        # Показываем окно перед началом анимации
        self.show()
        self.raise_()
        
        # Запускаем анимацию
        self.anim_group.start(QParallelAnimationGroup.DeleteWhenStopped)
        
        # Обрабатываем события
        QApplication.processEvents()
    
    def fadeOut(self):
        """Улучшенная анимация исчезновения splash screen"""
        print("Начинаю анимацию исчезновения splash screen...")
        
        # Принудительно поднимаем окно наверх перед исчезновением
        self.raise_()
        
        # Создаем анимацию исчезновения
        fade_out = QPropertyAnimation(self, b"windowOpacity")
        fade_out.setDuration(800)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.setEasingCurve(QEasingCurve.InCubic)
        
        # Создаем анимацию масштабирования
        scale_out = QPropertyAnimation(self, b"geometry")
        scale_out.setDuration(800)
        initial_rect = self.geometry()
        scaled_rect = initial_rect
        scaled_rect.setSize(scaled_rect.size() * 1.05)
        scale_out.setStartValue(initial_rect)
        scale_out.setEndValue(scaled_rect)
        scale_out.setEasingCurve(QEasingCurve.InCubic)
        
        # Запускаем анимации параллельно
        self.anim_group = QParallelAnimationGroup(self)
        self.anim_group.addAnimation(fade_out)
        self.anim_group.addAnimation(scale_out)
        self.anim_group.start(QParallelAnimationGroup.DeleteWhenStopped)
        
        return self.anim_group
    
    def finish(self, window):
        """Завершает отображение splash screen и показывает основное окно"""
        if not self.loading_finished:
            self.complete_loading()
            
        print("Начинаю процесс закрытия splash screen...")
        
        # Создаем и запускаем анимацию исчезновения
        fade_anim = self.fadeOut()
        
        def show_main_window():
            print("Показываю главное окно...")
            
            # Устанавливаем флаги окна для отображения поверх других
            window.setWindowState(window.windowState() & ~Qt.WindowMinimized | Qt.WindowActive)
            window.setWindowFlags(window.windowFlags() | Qt.WindowStaysOnTopHint)
            
            # Показываем окно
            window.show()
            
            # Центрируем окно на экране
            screen = QApplication.primaryScreen().geometry()
            window.move(
                screen.center().x() - window.width() // 2,
                screen.center().y() - window.height() // 2
            )
            
            # Активируем окно и поднимаем его поверх других
            window.raise_()
            window.activateWindow()
            
            # Возвращаем обычные флаги окна после небольшой задержки
            QTimer.singleShot(1000, lambda: window.setWindowFlags(window.windowFlags() & ~Qt.WindowStaysOnTopHint))
            QTimer.singleShot(1100, window.show)  # Показываем окно снова после изменения флагов
            
            # Скрываем splash screen после того как главное окно стало видимым
            QTimer.singleShot(100, self.hide)
            QTimer.singleShot(200, self.deleteLater)
            print("Главное окно отображено.")
        
        # Подключаем функцию к сигналу завершения анимации
        fade_anim.finished.connect(show_main_window)
        
        # Страховка с меньшей задержкой
        QTimer.singleShot(800, lambda: show_main_window() if not window.isVisible() else None) 