from PySide6.QtWidgets import QSplashScreen, QProgressBar, QLabel, QVBoxLayout, QWidget
from PySide6.QtCore import Qt, QTimer, QPropertyAnimation, QEasingCurve, QPoint, QSize, QRect
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QLinearGradient, QPainterPath

VERSION = "1.4"
CODENAME = "Phoenix Rising"

class ModernProgressBar(QProgressBar):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(3)  # Делаем прогресс-бар тоньше
        self.setTextVisible(False)
        self.animation = QPropertyAnimation(self, b"value", self)
        self.animation.setEasingCurve(QEasingCurve.InOutQuart)
        self.animation.setDuration(100)
        
    def setValueAnimated(self, value):
        self.animation.setStartValue(self.value())
        self.animation.setEndValue(value)
        self.animation.start()

class LoadingSplash(QSplashScreen):
    def __init__(self):
        # Загружаем фоновое изображение для определения размеров
        self.background = QPixmap("Resources/minecraft_launcher.png")
        if self.background.isNull():
            self.background = QPixmap(800, 450)
            self.background.fill(Qt.transparent)
        
        # Создаем пустой QPixmap нужного размера
        super().__init__(QPixmap(self.background.size()))
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # Основной контейнер
        self.content = QWidget(self)
        self.content.setGeometry(0, 0, self.background.width(), self.background.height())
        layout = QVBoxLayout(self.content)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(15)
        
        # Заголовок
        self.title = QLabel("NOVA LAUNCHER")
        self.title.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 32px;
                font-weight: bold;
                font-family: 'Segoe UI';
                letter-spacing: 2px;
                text-shadow: 0 2px 4px rgba(0, 0, 0, 0.5);
            }
        """)
        self.title.setAlignment(Qt.AlignCenter)
        
        # Версия и кодовое имя
        self.version = QLabel(f"v{VERSION} '{CODENAME}'")
        self.version.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.7);
                font-size: 14px;
                font-family: 'Segoe UI';
                font-weight: 500;
                letter-spacing: 1px;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 10px;
                padding: 4px 12px;
            }
        """)
        self.version.setAlignment(Qt.AlignCenter)
        
        # Статус
        self.status = QLabel("Инициализация...")
        self.status.setStyleSheet("""
            QLabel {
                color: rgba(255, 255, 255, 0.9);
                font-size: 16px;
                font-family: 'Segoe UI';
                font-weight: 500;
                letter-spacing: 0.5px;
            }
        """)
        self.status.setAlignment(Qt.AlignCenter)
        
        # Прогресс-бар
        self.progress = ModernProgressBar()
        self.progress.setMaximumWidth(400)  # Ограничиваем ширину
        self.progress.setStyleSheet("""
            QProgressBar {
                border: none;
                background: rgba(255, 255, 255, 0.1);
                border-radius: 1.5px;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #ffffff,
                    stop:1 rgba(255, 255, 255, 0.7));
                border-radius: 1.5px;
            }
        """)
        
        # Добавляем виджеты
        layout.addStretch(2)
        layout.addWidget(self.title)
        layout.addWidget(self.version, 0, Qt.AlignCenter)
        layout.addSpacing(10)
        layout.addWidget(self.status)
        layout.addWidget(self.progress, 0, Qt.AlignCenter)
        layout.addStretch(3)
        
        # Таймеры
        self.loading_finished = False
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress_internal)
        self.ensure_completion_timer = QTimer()
        self.ensure_completion_timer.timeout.connect(self.ensure_completion)
        self.ensure_completion_timer.setSingleShot(True)
        
        # Начальная анимация
        self.setWindowOpacity(0)
        self.fadeIn()
    
    def drawContents(self, painter: QPainter):
        # Включаем сглаживание
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # Рисуем фоновое изображение
        if not self.background.isNull():
            painter.drawPixmap(0, 0, self.background)
        
        # Создаем градиентный оверлей
        overlay = QLinearGradient(0, 0, 0, self.height())
        overlay.setColorAt(0, QColor(0, 0, 0, 200))
        overlay.setColorAt(0.5, QColor(0, 0, 0, 170))
        overlay.setColorAt(1, QColor(0, 0, 0, 200))
        painter.fillRect(self.rect(), overlay)
        
        # Добавляем легкое свечение сверху
        glow = QLinearGradient(0, 0, 0, 100)
        glow.setColorAt(0, QColor(255, 255, 255, 30))
        glow.setColorAt(1, QColor(255, 255, 255, 0))
        painter.fillRect(QRect(0, 0, self.width(), 100), glow)
    
    def start_progress(self):
        self.progress.setValue(0)
        self.timer.start(25)
        self.ensure_completion_timer.start(3000)
    
    def ensure_completion(self):
        if self.progress.value() < 100:
            remaining_steps = (100 - self.progress.value()) // 5
            if remaining_steps > 0:
                self.timer.setInterval(50 // remaining_steps)
            else:
                self.updateProgress(100)
                self.loading_finished = True
                self.timer.stop()
    
    def update_progress_internal(self):
        current_value = self.progress.value()
        if current_value < 100:
            self.updateProgress(current_value + 1)
        else:
            self.timer.stop()
            self.loading_finished = True
    
    def updateProgress(self, value, status=""):
        if status:
            self.status.setText(status)
        self.progress.setValueAnimated(value)
        
        if value <= 20:
            self.status.setText("Инициализация лаунчера...")
        elif value <= 40:
            self.status.setText("Проверка обновлений...")
        elif value <= 60:
            self.status.setText("Загрузка настроек...")
        elif value <= 80:
            self.status.setText("Подготовка интерфейса...")
        elif value < 100:
            self.status.setText("Завершение загрузки...")
        else:
            self.status.setText("Загрузка завершена!")
    
    def fadeIn(self):
        self.show()
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setStartValue(0)
        anim.setEndValue(1)
        anim.setDuration(1000)
        anim.setEasingCurve(QEasingCurve.OutCubic)
        anim.start()
    
    def fadeOut(self):
        anim = QPropertyAnimation(self, b"windowOpacity", self)
        anim.setStartValue(1)
        anim.setEndValue(0)
        anim.setDuration(800)
        anim.setEasingCurve(QEasingCurve.InCubic)
        anim.start()
        return anim
    
    def finish(self, window):
        if not self.loading_finished:
            return
        anim = self.fadeOut()
        anim.finished.connect(lambda: QSplashScreen.finish(self, window)) 