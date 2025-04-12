# [Предыдущий код nova_launcher.py был слишком длинным для одного сообщения, поэтому я разделю его на части]

import sys
import os
import minecraft_launcher_lib
import subprocess
import json
import uuid
import requests
from datetime import datetime
import threading
import traceback
import hashlib
import urllib.parse
import shutil
import re

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QLineEdit,
                             QProgressBar, QMessageBox, QStackedWidget,
                             QListWidget, QCheckBox, QFileDialog, QDialog,
                             QDialogButtonBox, QListWidgetItem, QSizePolicy,
                             QSpacerItem, QFrame, QGraphicsOpacityEffect, QComboBox,
    QTabWidget, QSplashScreen, QGraphicsDropShadowEffect
)
from PySide6.QtGui import (
    QFont, QFontDatabase, QIcon, QPixmap, QPalette,
    QBrush, QColor, QLinearGradient, QPainter, QCursor,
    QTransform
)
from PySide6.QtCore import (
    Qt, QThread, Signal, QTimer, QPropertyAnimation,
                           QEasingCurve, QPoint, QParallelAnimationGroup, QRect, QSize, Slot, QObject,
    Property, QSequentialAnimationGroup, QPointF
)

try:
    from splash_screen import AnimatedSplashScreen
except ImportError:
    print("Ошибка: Не найден модуль splash_screen")
    class AnimatedSplashScreen:
        def __init__(self): pass
        def setFont(self, font): pass
        def show(self): pass
        def start_animation(self): pass
        def finish(self, window): window.show()

# --- Константы ---
LAUNCHER_VERSION = "2.0.0.1"
SETTINGS_FILE = "settings.json"
PROFILES_FILE = "profiles.json"
MINECRAFT_VERSION = "1.21.4"
RESOURCES_DIR = "Resources"
LOGO_FILE = os.path.join(RESOURCES_DIR, "rounded_logo_nova.png")
FONT_FILE = os.path.join(RESOURCES_DIR, "minecraft-ten-font-cyrillic.ttf")
MINECRAFT_DATA_DIR_NAME = "NovaLauncherMC"
CACHE_DIR = os.path.join(RESOURCES_DIR, "cache")
PROFILE_ICONS_DIR = os.path.join(RESOURCES_DIR, "profile_icons")
DEFAULT_PROFILE_ICON = os.path.join(RESOURCES_DIR, "icon_default.png")

# --- Функция загрузки и кэширования изображений ---
def get_cached_image_path(image_url: str) -> str | None:
    """
    Загружает изображение по URL, кэширует его локально и возвращает путь к файлу.
    Если изображение уже в кэше, возвращает путь к нему.
    Если происходит ошибка, возвращает None.
    """
    if not image_url or not image_url.startswith(('http://', 'https://')):
        print(f"Ошибка: Некорректный URL изображения: {image_url}")
        return None

    try:
        # Создаем папку кэша, если ее нет
        os.makedirs(CACHE_DIR, exist_ok=True)

        # Создаем имя файла на основе хэша URL, сохраняя расширение
        parsed_url = urllib.parse.urlparse(image_url)
        _, ext = os.path.splitext(parsed_url.path)
        if not ext: ext = ".png" # По умолчанию .png, если нет расширения
        filename_hash = hashlib.sha256(image_url.encode()).hexdigest()
        cached_file_path = os.path.join(CACHE_DIR, f"{filename_hash}{ext}")

        # Проверяем наличие файла в кэше
        if os.path.exists(cached_file_path):
            # print(f"Изображение найдено в кэше: {cached_file_path}")
            return cached_file_path

        # Загружаем изображение
        print(f"Загрузка изображения из {image_url}...")
        response = requests.get(image_url, stream=True, timeout=10) # Таймаут 10 сек
        response.raise_for_status() # Вызовет исключение для плохих ответов (4xx или 5xx)

        # Сохраняем в файл
        with open(cached_file_path, 'wb') as f:
            for chunk in response.iter_content(1024):
                f.write(chunk)
        print(f"Изображение сохранено в кэш: {cached_file_path}")
        return cached_file_path

    except requests.exceptions.RequestException as e:
        print(f"Ошибка сети при загрузке {image_url}: {e}")
        return None
    except IOError as e:
        print(f"Ошибка ввода/вывода при сохранении кэша для {image_url}: {e}")
        return None
    except Exception as e:
        print(f"Неизвестная ошибка при обработке {image_url}: {e}")
        return None


# --- Поток для загрузки иконок ---
class IconLoaderThread(QThread):
    """Асинхронно загружает иконки для виджетов."""
    # Сигнал: виджет, путь к загруженной иконке (или None при ошибке)
    icon_loaded = Signal(QObject, str) # Используем QObject для универсальности

    def __init__(self, widgets_with_urls: list[QWidget], parent=None):
        super().__init__(parent)
        # [(widget, url), ...]
        self.widgets_to_load = []
        for widget in widgets_with_urls:
            if hasattr(widget, 'icon_url') and getattr(widget, 'icon_url'):
                 self.widgets_to_load.append((widget, getattr(widget, 'icon_url')))

    def run(self):
        print(f"IconLoaderThread: Загрузка {len(self.widgets_to_load)} иконок...")
        for widget, url in self.widgets_to_load:
            if not isinstance(widget, QObject): # Проверка
                print(f"Предупреждение: Виджет для URL {url} не является QObject.")
                continue

            cached_path = get_cached_image_path(url)
            # Отправляем сигнал даже с None, чтобы обработчик знал о завершении попытки
            self.icon_loaded.emit(widget, cached_path)
            # Небольшая пауза, чтобы не перегружать сеть/диск, если иконок много
            self.msleep(50)
        print("IconLoaderThread: Загрузка завершена.")


# --- Менеджеры данных ---

class SettingsManager:
    """
    Управляет загрузкой, сохранением и доступом к настройкам лаунчера.
    Настройки хранятся в JSON-файле.
    """
    DEFAULT_SETTINGS = {
        "java_path": "",
        "min_memory_mb": 2048,
        "max_memory_mb": 4096,
        "close_on_launch": False,
        "selected_profile_uuid": None,
        "is_premium": False,  # Флаг премиум-статуса
        # Настройки фильтров версий
        "show_releases": True,
        "show_snapshots": True,
        "show_betas": False,
        "show_alphas": False,
        # Можно добавить и для модов, но пока не будем усложнять
        # "show_fabric": True,
        # "show_forge": True,
    }

    def __init__(self, filename=SETTINGS_FILE):
        self.filename = filename
        self.settings = self._load_settings()

    def _load_settings(self):
        """Загружает настройки из файла, дополняя отсутствующие значения дефолтными."""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Гарантируем наличие всех ключей
                    settings = self.DEFAULT_SETTINGS.copy()
                    settings.update(loaded) # Загруженные значения переопределяют дефолтные
                    return settings
            except (json.JSONDecodeError, IOError, TypeError) as e:
                print(f"Ошибка загрузки файла настроек '{self.filename}': {e}. Используются настройки по умолчанию.")
        return self.DEFAULT_SETTINGS.copy()

    def save_settings(self):
        """Сохраняет текущие настройки в JSON-файл."""
        try:
            os.makedirs(os.path.dirname(self.filename) or '.', exist_ok=True) # Создаем папку, если нужно
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"Ошибка сохранения файла настроек '{self.filename}': {e}.")

    def get(self, key):
        """Возвращает значение настройки по ключу."""
        return self.settings.get(key, self.DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        """Устанавливает значение настройки и сохраняет файл."""
        if key in self.DEFAULT_SETTINGS: # Сохраняем только известные ключи
             self.settings[key] = value
             self.save_settings()
        else:
             print(f"Предупреждение: Попытка установить неизвестный ключ настройки '{key}'.")


class ProfileManager:
    """
    Управляет созданием, редактированием, удалением и хранением профилей пользователей.
    Профили хранятся в JSON-файле.
    """
    def __init__(self, filename=PROFILES_FILE):
        self.filename = filename
        self.profiles = self._load_profiles()

    def _load_profiles(self):
        """Загружает профили из файла."""
        if os.path.exists(self.filename):
            try:
                with open(self.filename, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                    # Простая валидация - ожидаем словарь
                    if isinstance(profiles, dict):
                        return profiles
                    else:
                        print(f"Ошибка формата файла профилей '{self.filename}'. Ожидался словарь.")
                        return {}
            except (json.JSONDecodeError, IOError) as e:
                print(f"Ошибка загрузки файла профилей '{self.filename}': {e}. Список профилей пуст.")
        return {}

    def save_profiles(self):
        """Сохраняет текущий список профилей в JSON-файл."""
        try:
            os.makedirs(os.path.dirname(self.filename) or '.', exist_ok=True)
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, indent=4, ensure_ascii=False)
        except IOError as e:
            print(f"Ошибка сохранения файла профилей '{self.filename}': {e}.")

    def add_profile(self, name, username, version=MINECRAFT_VERSION, min_memory=None, max_memory=None, icon_filename=None):
        """Добавляет новый профиль и возвращает его UUID."""
        if not name or not username:
            print("Ошибка: Имя профиля и имя пользователя не могут быть пустыми.")
            return None
        profile_uuid = str(uuid.uuid4())
        self.profiles[profile_uuid] = {
            "name": name,
            "username": username,
            "version": version,
            "min_memory_override": min_memory,
            "max_memory_override": max_memory,
            "icon_filename": icon_filename, # Сохраняем имя файла иконки
            "last_used": datetime.now().isoformat()
        }
        self.save_profiles()
        return profile_uuid

    def update_profile(self, profile_uuid, name, username, min_memory=None, max_memory=None, icon_filename=None):
        """Обновляет существующий профиль."""
        if profile_uuid in self.profiles:
            if not name or not username:
                print("Ошибка: Имя профиля и имя пользователя не могут быть пустыми.")
                return False
            self.profiles[profile_uuid]["name"] = name
            self.profiles[profile_uuid]["username"] = username
            self.profiles[profile_uuid]["min_memory_override"] = min_memory
            self.profiles[profile_uuid]["max_memory_override"] = max_memory
            self.profiles[profile_uuid]["icon_filename"] = icon_filename # Обновляем имя файла иконки
            self.profiles[profile_uuid]["last_used"] = datetime.now().isoformat()
            self.save_profiles()
            return True
        return False

    def delete_profile(self, profile_uuid):
        """Удаляет профиль по UUID."""
        if profile_uuid in self.profiles:
            del self.profiles[profile_uuid]
            self.save_profiles()
            return True
        return False

    def get_profile(self, profile_uuid):
        """Возвращает данные профиля по UUID."""
        return self.profiles.get(profile_uuid)

    def get_all_profiles(self):
        """Возвращает словарь всех профилей, отсортированных по имени."""
        try:
            # Сортировка с обработкой возможного отсутствия ключа 'name'
            return dict(sorted(self.profiles.items(), key=lambda item: item[1].get('name', '')))
        except Exception as e:
            print(f"Ошибка сортировки профилей: {e}")
            return self.profiles # Возвращаем несортированный словарь в случае ошибки

# --- Диалог редактирования/создания профиля ---

class ProfileDialog(QDialog):
    """Диалоговое окно для создания или редактирования профиля."""
    def __init__(self, profile_uuid=None, profile_data=None, minecraft_font=None, colors=None, parent=None):
        super().__init__(parent)
        self.profile_uuid = profile_uuid # UUID нужен для именования иконки
        self.profile_data = profile_data or {}
        self.minecraft_font = minecraft_font or parent.font() if parent else QFont("Arial", 11)
        self.colors = colors or {}
        self.setWindowTitle("Редактирование профиля" if profile_data else "Новый профиль")
        self.setMinimumWidth(450)

        # Создаем папку для иконок, если ее нет
        os.makedirs(PROFILE_ICONS_DIR, exist_ok=True)

        # Переменная для хранения *нового* имени файла иконки
        self.selected_icon_filename = self.profile_data.get("icon_filename")

        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # --- Поля ввода --- (Name, Username)
        fields = [
            ("Название профиля:", "name", ""),
            ("Имя пользователя:", "username", "")
        ]
        self.inputs = {}
        for label_text, key, default in fields:
            label = QLabel(label_text)
            label.setFont(self.minecraft_font)
            self.inputs[key] = QLineEdit()
            self.inputs[key].setFont(self.minecraft_font)
            if profile_data: self.inputs[key].setText(self.profile_data.get(key, default))
            layout.addWidget(label)
            layout.addWidget(self.inputs[key])

        # --- Выбор иконки --- 
        icon_layout = QHBoxLayout()
        icon_layout.setSpacing(10)

        self.icon_preview_label = QLabel()
        self.icon_preview_label.setFixedSize(48, 48)
        self.icon_preview_label.setObjectName("profileDialogIconPreview")
        self._update_icon_preview() # Загружаем текущую или дефолтную иконку

        icon_button = QPushButton("Выбрать иконку...")
        icon_button.setFont(self.minecraft_font)
        icon_button.setCursor(Qt.PointingHandCursor)
        icon_button.setObjectName("actionButton")
        icon_button.clicked.connect(self._browse_icon)

        icon_layout.addWidget(self.icon_preview_label)
        icon_layout.addWidget(icon_button, 1)
        icon_layout.addStretch(0)
        layout.addLayout(icon_layout)

        # --- Настройки памяти --- (остаются без изменений)
        memory_label = QLabel("Переопределение памяти (МБ, пусто = по умолчанию):")
        memory_label.setFont(self.minecraft_font)
        layout.addWidget(memory_label)
        memory_layout = QHBoxLayout()

        min_mem_label = QLabel("Мин:")
        min_mem_label.setFont(self.minecraft_font)
        # Создаем и добавляем в словарь self.inputs
        self.inputs["min_memory"] = QLineEdit()
        self.inputs["min_memory"].setFont(self.minecraft_font)
        self.inputs["min_memory"].setPlaceholderText(str(SettingsManager.DEFAULT_SETTINGS["min_memory_mb"]))

        max_mem_label = QLabel("Макс:")
        max_mem_label.setFont(self.minecraft_font)
        # Создаем и добавляем в словарь self.inputs
        self.inputs["max_memory"] = QLineEdit()
        self.inputs["max_memory"].setFont(self.minecraft_font)
        self.inputs["max_memory"].setPlaceholderText(str(SettingsManager.DEFAULT_SETTINGS["max_memory_mb"]))

        if profile_data:
             min_override = self.profile_data.get("min_memory_override")
             max_override = self.profile_data.get("max_memory_override")
             if min_override is not None: self.inputs["min_memory"].setText(str(min_override))
             if max_override is not None: self.inputs["max_memory"].setText(str(max_override))

        memory_layout.addWidget(min_mem_label)
        memory_layout.addWidget(self.inputs["min_memory"]) # Используем значение из словаря
        memory_layout.addWidget(max_mem_label)
        memory_layout.addWidget(self.inputs["max_memory"]) # Используем значение из словаря
        layout.addLayout(memory_layout)

        # --- Кнопки OK/Cancel --- (остаются без изменений)
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        ok_button = button_box.button(QDialogButtonBox.Ok)
        cancel_button = button_box.button(QDialogButtonBox.Cancel)
        if ok_button: ok_button.setFont(self.minecraft_font)
        if cancel_button: cancel_button.setFont(self.minecraft_font)
        layout.addWidget(button_box)

        self.apply_styles() # Применяем стили

    def _update_icon_preview(self):
        """Обновляет предпросмотр иконки."""
        icon_path = DEFAULT_PROFILE_ICON
        if self.selected_icon_filename:
            potential_path = os.path.join(PROFILE_ICONS_DIR, self.selected_icon_filename)
            if os.path.exists(potential_path):
                icon_path = potential_path
            else:
                 print(f"Предупреждение: Файл иконки профиля не найден: {potential_path}, используется дефолтная.")
                 self.selected_icon_filename = None # Сбрасываем, если файл пропал

        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_preview_label.setPixmap(pixmap)
        else:
             # Если даже дефолтной нет, ставим фон
             print(f"Ошибка: Не найден файл дефолтной иконки: {DEFAULT_PROFILE_ICON}")
             self.icon_preview_label.setText("?")
             self.icon_preview_label.setAlignment(Qt.AlignCenter)
             self.icon_preview_label.setStyleSheet("background-color: #555; border-radius: 5px;")

    def _browse_icon(self):
        """Открывает диалог выбора файла иконки."""
        filters = "Images (*.png *.jpg *.jpeg *.bmp *.gif)"
        filepath, _ = QFileDialog.getOpenFileName(self, "Выберите иконку профиля", "", filters)

        if filepath:
            try:
                # Генерируем новое имя файла
                _, ext = os.path.splitext(filepath)
                # Используем UUID профиля, если он есть (для редактирования), иначе генерируем новый
                base_name = self.profile_uuid if self.profile_uuid else str(uuid.uuid4())
                new_filename = f"{base_name}{ext}"
                destination_path = os.path.join(PROFILE_ICONS_DIR, new_filename)

                # Копируем файл
                shutil.copy2(filepath, destination_path)
                print(f"Иконка скопирована в {destination_path}")

                # Удаляем старую иконку, если имя файла изменилось (например, из-за расширения)
                old_filename = self.selected_icon_filename
                if old_filename and old_filename != new_filename:
                     old_path = os.path.join(PROFILE_ICONS_DIR, old_filename)
                     if os.path.exists(old_path):
                         try:
                             os.remove(old_path)
                             print(f"Старая иконка удалена: {old_path}")
                         except OSError as e:
                             print(f"Ошибка удаления старой иконки {old_path}: {e}")

                # Сохраняем новое имя файла и обновляем превью
                self.selected_icon_filename = new_filename
                self._update_icon_preview()

            except Exception as e:
                print(f"Ошибка при копировании или обработке иконки: {e}")
                QMessageBox.warning(self, "Ошибка иконки", f"Не удалось обработать выбранный файл иконки.\n{e}")
                self.selected_icon_filename = self.profile_data.get("icon_filename") # Возвращаем старое значение
                self._update_icon_preview() # Обновляем превью на старое/дефолтное

    def get_data(self):
        """Собирает данные из полей ввода, включая имя файла иконки."""
        # ... (сбор min_mem и max_mem остается прежним) ...
        min_mem_str = self.inputs["min_memory"].text().strip()
        max_mem_str = self.inputs["max_memory"].text().strip()
        try:
            min_mem = int(min_mem_str) if min_mem_str.isdigit() else None
            max_mem = int(max_mem_str) if max_mem_str.isdigit() else None
            if min_mem is not None and min_mem < 512: min_mem = 512
            if max_mem is not None and min_mem is not None and max_mem < min_mem: max_mem = min_mem
        except ValueError:
            min_mem = None
            max_mem = None

        return {
            "name": self.inputs["name"].text().strip(),
            "username": self.inputs["username"].text().strip(),
            "min_memory": min_mem,
            "max_memory": max_mem,
            "icon_filename": self.selected_icon_filename # Добавляем имя файла иконки
        }

    def apply_styles(self):
         """Применяет стили к диалоговому окну."""
         # Используем цвета из основного окна, если они переданы
         primary = self.colors.get('primary', '#6C63FF')
         secondary = self.colors.get('secondary', '#8B85FF')
         surface = self.colors.get('surface_solid', '#2D2D2D') # Используем непрозрачный фон
         text_color = self.colors.get('text', '#E0E0E0')
         border_color = self.colors.get('primary', '#6C63FF') # Используем основной цвет для рамки

         self.setStyleSheet(f"""
             QDialog {{
                 background-color: {surface};
                 border: 1px solid {border_color};
                 border-radius: 8px;
             }}
             QLabel {{
                 color: {text_color};
                 padding-top: 5px;
                 background: transparent; /* Явно */
             }}
             QLineEdit {{
                 background: rgba(255, 255, 255, 0.05);
                 border: 1px solid rgba(255, 255, 255, 0.1); /* Слабее граница */
                 border-radius: 5px;
                 padding: 8px 10px;
                 color: {text_color};
                 selection-background-color: {primary};
             }}
             QLineEdit:focus {{
                 border: 1px solid {primary};
                 background: rgba(255, 255, 255, 0.08);
             }}
             /* Стили для кнопок Ok/Cancel */
             QDialogButtonBox QPushButton {{
                 background-color: {primary};
                 color: white;
                 border: none;
                 padding: 8px 20px;
                 border-radius: 5px;
                 min-width: 80px;
             }}
             QDialogButtonBox QPushButton:hover {{
                 background-color: {secondary};
             }}
             QDialogButtonBox QPushButton:pressed {{
                  background-color: {QColor(primary).darker(110).name()};
             }}
             /* Специфичный стиль для Cancel - ищем по стандартной роли */
             QDialogButtonBox QPushButton[role="RejectRole"] {{
                  background-color: rgba(255, 255, 255, 0.1);
                  color: {text_color};
                  border: 1px solid rgba(255, 255, 255, 0.2);
             }}
              QDialogButtonBox QPushButton[role="RejectRole"]:hover {{
                  background-color: rgba(255, 255, 255, 0.15);
                  border: 1px solid rgba(255, 255, 255, 0.3);
             }}
               QDialogButtonBox QPushButton[role="RejectRole"]:pressed {{
                  background-color: rgba(255, 255, 255, 0.05);
             }}
         """)

# --- Виджет кастомной строки заголовка ---

class CustomTitleBar(QWidget):
    """Кастомная строка заголовка для окна без рамок."""
    def __init__(self, parent):
        super().__init__(parent)
        self.parent_window = parent
        self.setAutoFillBackground(True)
        self.setFixedHeight(40)
        self.setObjectName("customTitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(10)

        # Иконка/Лого
        self.icon_label = QLabel()
        if os.path.exists(LOGO_FILE):
            icon_pix = QPixmap(LOGO_FILE).scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_label.setPixmap(icon_pix)
        layout.addWidget(self.icon_label)

        # Заголовок
        self.title_label = QLabel(parent.windowTitle())
        self.title_label.setObjectName("titleBarLabel")
        layout.addWidget(self.title_label)

        layout.addStretch()

        # Кнопки управления окном - передаем текст 'M' и 'C'
        self.minimize_button = self._create_window_button(
            "M", self.parent_window.showMinimized, "_minimizeButton"
        )
        self.close_button = self._create_window_button(
            "C", self.parent_window.close, "_closeButton"
        )

        layout.addWidget(self.minimize_button)
        layout.addWidget(self.close_button)

        self._is_maximized = False
        self._drag_pos = None

    def _create_window_button(self, button_text, slot, object_name):
        """Создает кнопку управления окном с текстом."""
        button = QPushButton(button_text)
        button.setObjectName(object_name)
        # button.setFixedSize(50, 40) # Размер задается в QSS
        button.setFlat(True)
        button.setCursor(QCursor(Qt.PointingHandCursor))
        button.clicked.connect(slot)
        return button

    def _create_sidebar_button(self, icon_path, tooltip, object_name):
        """Создает кнопку для сайдбара."""
        button = QPushButton()
        button.setObjectName(object_name)
        button.setCheckable(True)
        button.setFixedSize(60, 60)
        button.setFlat(True)
        button.setToolTip(tooltip)
        button.setCursor(QCursor(Qt.PointingHandCursor))

        # Устанавливаем иконку напрямую
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            button.setIcon(icon)
            button.setIconSize(QSize(28, 28))
        else:
            print(f"Предупреждение: Файл иконки не найден: {icon_path}")
            button.setText(tooltip[0])

        return button


    def mousePressEvent(self, event):
        """Запоминает позицию для перетаскивания окна."""
        if event.button() == Qt.LeftButton:
            # globalPos() устарело, используем position() и mapToGlobal()
            self._drag_pos = event.position().toPoint()
            event.accept()

    def mouseMoveEvent(self, event):
        """Перетаскивает окно."""
        if event.buttons() == Qt.LeftButton and self._drag_pos:
            # mapToGlobal нужен для получения глобальных координат
            global_pos = self.mapToGlobal(event.position().toPoint())
            self.parent_window.move(global_pos - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        """Сбрасывает позицию перетаскивания."""
        if event.button() == Qt.LeftButton:
            self._drag_pos = None
            event.accept()

    def mouseDoubleClickEvent(self, event):
         """Двойной клик для maximize/restore (если нужно)"""
         # if event.button() == Qt.LeftButton:
         #      self.toggle_maximize()
         #      event.accept()
         pass # Пока не используем

# --- Виджет профиля в топ-баре ---

class ProfileWidget(QWidget):
    """Виджет для отображения информации о профиле в шапке."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("profileWidget")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 10, 5)
        layout.setSpacing(10)

        self.icon_label = QLabel() # Переименовал skin_label в icon_label
        self.icon_label.setObjectName("profileTopIcon") # Новое имя объекта
        self.icon_label.setFixedSize(48, 48)
        self.icon_label.setAlignment(Qt.AlignCenter)
        self.icon_label.setStyleSheet("background-color: #444; border-radius: 5px;") # Начальная заглушка
        layout.addWidget(self.icon_label)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(0)
        info_layout.addStretch()

        self.username_label = QLabel("Профиль не выбран")
        self.username_label.setObjectName("profileUsername")
        self.username_label.setFont(parent.get_font(12, QFont.Bold) if parent else QFont()) # Используем get_font родителя
        info_layout.addWidget(self.username_label)

        info_layout.addStretch()
        layout.addLayout(info_layout)

    def update_profile(self, username, icon_filename=None):
        """Обновляет имя пользователя и иконку."""
        self.username_label.setText(username if username else "Профиль не выбран")

        icon_path_to_load = DEFAULT_PROFILE_ICON
        if icon_filename:
            potential_path = os.path.join(PROFILE_ICONS_DIR, icon_filename)
            if os.path.exists(potential_path):
                icon_path_to_load = potential_path

        if os.path.exists(icon_path_to_load):
            pixmap = QPixmap(icon_path_to_load).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.icon_label.setPixmap(pixmap)
            self.icon_label.setStyleSheet("") # Сбрасываем фон, если иконка загружена
        else:
            self.icon_label.setPixmap(QPixmap()) # Очищаем pixmap
            self.icon_label.setText("?")
            self.icon_label.setStyleSheet("background-color: #444; border-radius: 5px;")
            if icon_path_to_load == DEFAULT_PROFILE_ICON:
                 print(f"Ошибка: Не найден файл дефолтной иконки: {DEFAULT_PROFILE_ICON}")

# --- Главное окно лаунчера ---

class NovaLauncher(QMainWindow): # Переименован класс
    """Основное окно лаунчера Nova с кастомной рамкой.""" # Обновлено описание

    # Сигнал для обновления иконки из другого потока
    request_icon_update = Signal(QWidget, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Nova Launcher v{LAUNCHER_VERSION}") # Обновлен заголовок
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setFixedSize(1280, 720)

        # Удаляем ненужную инициализацию списка иконок
        # self.widgets_requiring_icons = []

        # Менеджеры данных
        self.settings_manager = SettingsManager()
        self.profile_manager = ProfileManager()

        # Новая цветовая палитра (Minecraft/Nova с вашим цветом)
        self.colors = {
            'primary': '#c5b8b3',      # Ваш цвет (бежево-серый)
            'secondary': '#d1c8c4',    # Светлее вашего цвета
            'accent_green': '#c5b8b3', # Заменяем зеленый на ваш цвет
            'accent_green_hover': '#d1c8c4', # Заменяем светло-зеленый на ваш цвет
            'background_main': '#3C3C3C', # Dark Grey (Stone)
            'background_sidebar': '#303030', # Darker Grey
            'surface': 'rgba(68, 68, 68, 0.85)', # Semi-transparent Grey
            'surface_solid': '#444444', # Solid Grey (for dialogs)
            'surface_light': '#555555', # Lighter Grey (for hover?)
            'text': '#E5E5E5',         # Light Grey text
            'text_light': '#B0B0B0',   # Dimmed Grey text
            'border': 'rgba(255, 255, 255, 0.1)', # Keep light border for contrast
            'red': '#FF6060',          # Standard Red
            'red_hover': '#FF8080',
            'yellow': '#FFD700',       # Standard Yellow
            'yellow_hover': '#FFFF00',
        }

        # Загрузка ресурсов
        self._load_font()
        self._check_resources()

        # Иконка окна (для панели задач)
        if os.path.exists(LOGO_FILE):
             self.setWindowIcon(QIcon(LOGO_FILE))

        self._create_minecraft_directory()

        # --- Создание основного макета с кастомным заголовком ---
        self.main_widget = QWidget() # Основной виджет внутри окна
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Список для хранения виджетов, которым нужны иконки
        # self.widgets_requiring_icons = [] # <-- ПЕРЕМЕЩЕНО ВВЕРХ

        # Кастомная строка заголовка
        self.title_bar = CustomTitleBar(self)
        self.main_layout.addWidget(self.title_bar)

        # Основная область (сайдбар + контент)
        self.body_widget = QWidget()
        self.body_layout = QHBoxLayout(self.body_widget)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(0)

        # Сайдбар
        sidebar = self._create_sidebar() # Будет добавлено в следующей части
        self.body_layout.addWidget(sidebar)

        # Контентная область (верхняя панель + стек)
        self.content_area = QWidget()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)

        # Верхняя панель (топ-бар)
        top_bar = self._create_top_bar() # Будет добавлено в следующей части
        self.content_layout.addWidget(top_bar)

        # Стек страниц
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("contentStack")
        # Добавляем страницы
        self.play_page = self._create_play_page() # Будет добавлено в следующей части
        self.profiles_page = self._create_profiles_page() # Будет добавлено в следующей части
        self.settings_page = self._create_settings_page() # Будет добавлено в следующей части
        self.content_stack.addWidget(self.play_page)
        self.content_stack.addWidget(self.profiles_page)
        self.content_stack.addWidget(self.settings_page)
        self.content_layout.addWidget(self.content_stack)

        # Добавляем контентную область в основной layout
        self.body_layout.addWidget(self.content_area)
        self.main_layout.addWidget(self.body_widget)

        # --- Потоки для установки ---
        self.installer_thread = None # Поток для установки версии/Java
        # self.mod_installer_thread = None # Удален, больше не нужен

        # --- Кэш установленных версий ---
        self.installed_version_ids = set() # Для быстрой проверки версий

        # Устанавливаем основной виджет для QMainWindow
        self.setCentralWidget(self.main_widget)

        # --- Анимации для стека ---
        self._active_opacity_effect = None # Храним активный эффект
        self._active_fade_animation = None # Храним активную анимацию

        # --- Инициализация UI --- (Оставшаяся часть будет в следующих блоках)
        # self.apply_styles()
        # self.load_minecraft_versions() # Загружаем версии в комбобокс
        # self.load_profiles_to_ui()
        # self.load_settings_to_ui()
        # self.update_profile_widget() # Обновляем виджет профиля
        # self.on_profile_selected() # Обновляем состояние UI

        # # Подключение сигналов навигации
        # self.home_button.clicked.connect(lambda: self.change_page(0))
        # self.profiles_button.clicked.connect(lambda: self.change_page(1))
        # self.settings_button.clicked.connect(lambda: self.change_page(2))

        # # Анимации переключения страниц
        # self._page_animations = {} # Словарь для хранения анимаций

        # # --- Запуск загрузки иконок ---
        # # if self.widgets_requiring_icons:
        # #     self.icon_loader_thread = IconLoaderThread(self.widgets_requiring_icons)
        # #     self.icon_loader_thread.icon_loaded.connect(self.on_icon_loaded)
        # #     self.icon_loader_thread.start()

        print("Лаунчер Nova инициализирован.") # Обновлено сообщение
        print(f"Папка данных Minecraft: {self.minecraft_directory}")
        self._check_internet()


    def _load_font(self):
        """Загружает кастомный шрифт."""
        self.minecraft_font_base = QFont("Arial") # Запасной
        if not os.path.exists(FONT_FILE):
             print(f"Ошибка: Файл шрифта не найден: {FONT_FILE}.")
             return
        font_id = QFontDatabase.addApplicationFont(FONT_FILE)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families: self.minecraft_font_base = QFont(families[0])
            else: print("Ошибка: Не удалось получить имя семейства шрифтов.")
        else: print("Ошибка: Не удалось добавить шрифт в базу данных.")
        # Устанавливаем базовый шрифт для всего приложения
        QApplication.instance().setFont(self.get_font(10)) # Базовый размер 10pt

    def _check_resources(self):
        """Проверяет наличие ключевых файлов иконок."""
        icons = ["icon_home.png", "icon_profile.png", "icon_settings.png",
                 "icon_minimize.png", "icon_close.png"]
        missing = []
        for icon in icons:
            if not os.path.exists(os.path.join(RESOURCES_DIR, icon)):
                missing.append(icon)
        if missing:
             print(f"Предупреждение: Отсутствуют файлы иконок в папке '{RESOURCES_DIR}': {', '.join(missing)}")
             QMessageBox.warning(self, "Отсутствуют ресурсы", f"Не найдены некоторые файлы иконок в папке '{RESOURCES_DIR}'.\nИнтерфейс может отображаться некорректно.")


    def _create_minecraft_directory(self):
        """Создает папку данных игры."""
        try:
            base_dir = os.path.dirname(minecraft_launcher_lib.utils.get_minecraft_directory())
            self.minecraft_directory = os.path.join(base_dir, MINECRAFT_DATA_DIR_NAME)
            os.makedirs(self.minecraft_directory, exist_ok=True)
        except Exception as e:
            print(f"Критическая ошибка: Не удалось создать папку данных Minecraft '{self.minecraft_directory}': {e}")
            QMessageBox.critical(self, "Ошибка папки данных", f"Не удалось создать папку:\n{self.minecraft_directory}\nОшибка: {e}\nЛаунчер закроется.")
            sys.exit(1)

    def _check_internet(self):
         """Проверка интернет-соединения."""
         # (остается без изменений)
         pass # Убрал вывод в консоль и QMessageBox для чистоты


    def get_font(self, size=10, weight=QFont.Normal, italic=False):
        """Возвращает экземпляр кастомного шрифта."""
        font = QFont(self.minecraft_font_base)
        font.setPointSize(size)
        font.setWeight(weight)
        font.setItalic(italic)
        return font

    # --- Методы построения UI ---

    def _create_sidebar(self):
        """Создает боковую панель с иконками."""
        sidebar = QWidget()
        sidebar.setFixedWidth(70) # Узкий сайдбар
        sidebar.setObjectName("sidebar")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(5, 10, 5, 10) # Уменьшенные отступы
        layout.setSpacing(5)

        # Убираем верхнюю кнопку с логотипом
        # logo_button = self._create_sidebar_button(
        #     os.path.join(RESOURCES_DIR, "icon_home.png"), # Используем icon_home как временный для лого
        #     "Nova", "_sidebarLogoButton" # Пример tooltip -> Заменено на Nova (хотя кнопка убрана)
        # )
        # logo_button.setCheckable(False) # Логотип не должен быть checkable
        # logo_button.setCursor(QCursor(Qt.ArrowCursor)) # Обычный курсор
        # # layout.addWidget(logo_button, 0, Qt.AlignHCenter) # Убрали
        layout.addSpacing(20) # Оставляем отступ сверху

        # Кнопки навигации (иконки)
        self.home_button = self._create_sidebar_button(
            os.path.join(RESOURCES_DIR, "icon_home.png"),
            "Главная", "_sidebarHomeButton"
        )
        self.profiles_button = self._create_sidebar_button(
            os.path.join(RESOURCES_DIR, "icon_profile.png"),
            "Профили", "_sidebarProfilesButton"
        )
        # Добавить другие кнопки по аналогии, если нужно
        # self.mods_button = self._create_sidebar_button("...", "Моды", "_sidebarModsButton")

        self.home_button.setChecked(True) # Первая кнопка (теперь это home) активна
        layout.addWidget(self.home_button)
        layout.addWidget(self.profiles_button)
        # layout.addWidget(self.mods_button)

        layout.addStretch() # Все кнопки вверх, настройки вниз

        # Кнопка настроек внизу
        self.settings_button = self._create_sidebar_button(
            os.path.join(RESOURCES_DIR, "icon_settings.png"),
            "Настройки", "_sidebarSettingsButton"
        )
        layout.addWidget(self.settings_button)

        return sidebar

    def _create_sidebar_button(self, icon_path, tooltip, object_name):
        """Создает кнопку для сайдбара."""
        button = QPushButton()
        button.setObjectName(object_name)
        button.setCheckable(True)
        button.setFixedSize(60, 60)
        button.setFlat(True)
        button.setToolTip(tooltip)
        button.setCursor(QCursor(Qt.PointingHandCursor))

        # Устанавливаем иконку напрямую
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
            button.setIcon(icon)
            button.setIconSize(QSize(28, 28))
        else:
            print(f"Предупреждение: Файл иконки не найден: {icon_path}")
            button.setText(tooltip[0])

        return button


    def _create_top_bar(self):
        """Создает верхнюю панель над контентом."""
        top_bar = QWidget()
        top_bar.setFixedHeight(60) # Фиксированная высота
        top_bar.setObjectName("topBar")
        layout = QHBoxLayout(top_bar)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(15)

        # Левая часть (соц. иконки - плейсхолдеры)
        social_layout = QHBoxLayout()
        social_layout.setSpacing(10)
        # TODO: Заменить QLabel на QPushButton с иконками и ссылками
        social_layout.addWidget(QLabel("TW"))
        social_layout.addWidget(QLabel("DI"))
        social_layout.addWidget(QLabel("IN"))
        social_layout.addWidget(QLabel("YT"))
        layout.addLayout(social_layout)

        layout.addStretch() # Растягиваем до центра

        # Онлайн (плейсхолдер)
        online_layout = QHBoxLayout()
        online_layout.setSpacing(5)
        online_icon = QLabel("\u25CF") # Кружок Unicode
        online_icon.setStyleSheet("color: #90EE90;") # Зеленый
        online_layout.addWidget(online_icon)
        self.online_label = QLabel("Wi-Fi соединение активно") # Плейсхолдер
        self.online_label.setObjectName("onlineLabel")
        online_layout.addWidget(self.online_label)
        layout.addLayout(online_layout)

        layout.addStretch() # Растягиваем до правого края

        # Виджет профиля
        self.profile_widget = ProfileWidget(self) # Передаем self для доступа к get_font
        layout.addWidget(self.profile_widget)

        return top_bar


    def _create_play_page(self):
        """Создает главную страницу (Игра)."""
        page = QWidget()
        page.setObjectName("playPage") # Для QSS фона
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0,0,0,0) # Управляем через QSS

        # Верхняя часть (Описание и кнопка)
        top_section = QWidget()
        top_layout = QHBoxLayout(top_section)
        top_layout.setContentsMargins(40, 40, 40, 20) # Отступы
        top_layout.setSpacing(40)

        # Левая часть (Текст)
        text_layout = QVBoxLayout()
        text_layout.setSpacing(10)
        title_label = QLabel("Minecraft") # Убираем версию из заголовка
        title_label.setObjectName("playPageTitle")
        title_label.setFont(self.get_font(36, QFont.Bold))

        desc_label = QLabel("Добро пожаловать в Nova Launcher!\nВыберите профиль и нажмите 'Играть' для запуска.") # Обновлен текст
        desc_label.setObjectName("playPageDesc")
        desc_label.setFont(self.get_font(11))
        desc_label.setWordWrap(True)

        text_layout.addWidget(title_label)
        text_layout.addWidget(desc_label)
        text_layout.addStretch()
        top_layout.addLayout(text_layout, 2) # Текст занимает 2 части

        # Правая часть (Кнопка и прогресс)
        button_layout = QVBoxLayout()
        button_layout.setSpacing(15)
        button_layout.setAlignment(Qt.AlignCenter) # Центрируем кнопку

        # Добавляем выпадающий список для версий
        self.version_selector = QComboBox()
        self.version_selector.setObjectName("versionSelector")
        self.version_selector.setFont(self.get_font(11))
        self.version_selector.setMinimumWidth(280) # Такая же ширина, как у кнопки
        self.version_selector.setCursor(Qt.PointingHandCursor)
        button_layout.addWidget(self.version_selector) # Добавляем перед кнопкой

        self.launch_button = QPushButton("ЗАПУСТИТЬ") # Убираем версию из текста кнопки
        self.launch_button.setObjectName("playButtonLarge") # Новый ID для стиля
        self.launch_button.setFont(self.get_font(16, QFont.Bold))
        self.launch_button.setMinimumSize(280, 60)
        self.launch_button.setCursor(QCursor(Qt.PointingHandCursor))
        self.launch_button.clicked.connect(self.launch_minecraft) # Будет добавлено позже

        # Подпись под кнопкой
        status_label = QLabel("Готово к запуску")
        status_label.setObjectName("playButtonStatus")
        status_label.setAlignment(Qt.AlignCenter)

        self.progress_bar = CustomProgressBar() # Будет добавлено позже
        self.progress_bar.setVisible(False)
        self.progress_bar.setMaximumWidth(280) # Ограничим ширину

        button_layout.addWidget(self.launch_button)
        button_layout.addWidget(status_label) # Добавили статус
        button_layout.addWidget(self.progress_bar)
        top_layout.addLayout(button_layout, 1) # Кнопка занимает 1 часть

        layout.addWidget(top_section)

        # Нижняя часть (Новости - плейсхолдер)
        news_title = QLabel("Последние новости")
        news_title.setObjectName("newsTitle")
        news_title.setFont(self.get_font(18, QFont.Bold))
        news_title.setContentsMargins(40, 20, 40, 10) # Отступы для заголовка
        layout.addWidget(news_title)

        news_section = self._create_news_section()
        layout.addWidget(news_section)
        layout.addStretch() # Прижимает новости к верху, если мало

        return page

    def _create_news_section(self):
         """Создает секцию с карточками новостей."""
         news_widget = QWidget()
         layout = QHBoxLayout(news_widget)
         layout.setContentsMargins(40, 0, 40, 20) # Отступы секции
         layout.setSpacing(20)

         # Данные для новостей (меняем местами)
         news_data = [
             {
                 "title": "Spring Sale 2025",
                 "description": "Spring is here which means it's also time for our Spring Sale... starting April 8.",
                 "image_path": os.path.join(RESOURCES_DIR, "news2.png")
             },
             {
                 "title": "The Craftmine Update",
                 "description": "Time to finally go bigger and craft it all!",
                 "image_path": os.path.join(RESOURCES_DIR, "news1.png")
             }
         ]

         # Создаем две карточки
         for data in news_data:
              card = self._create_news_card(
                   data["title"],
                   data["description"],
                   data["image_path"]
              )
              layout.addWidget(card)
         layout.addStretch() # Если карточек меньше, они будут слева

         return news_widget

    def _create_news_card(self, title, description, image_path):
         """Создает виджет-карточку новости."""
         card = QWidget()
         card.setObjectName("newsCard")
         card.setFixedSize(220, 280) # Увеличил высоту для описания
         layout = QVBoxLayout(card)
         layout.setContentsMargins(0, 0, 0, 15)
         layout.setSpacing(8)

         image_label = QLabel()
         image_label.setObjectName("newsCardImage")
         image_label.setFixedHeight(120)
         if os.path.exists(image_path):
              pix = QPixmap(image_path).scaled(220, 120, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
              rect = QRect(0, 0, 220, 120)
              pix = pix.copy(rect)
              image_label.setPixmap(pix)
         else:
             image_label.setText("[Изображение]")
             image_label.setAlignment(Qt.AlignCenter)
             image_label.setStyleSheet("background-color: #444;")
         layout.addWidget(image_label)

         title_label = QLabel(title)
         title_label.setObjectName("newsCardTitle")
         title_label.setFont(self.get_font(12, QFont.Bold))
         title_label.setWordWrap(True)
         title_label.setContentsMargins(15, 5, 15, 0) # Отступы для заголовка
         layout.addWidget(title_label)

         description_label = QLabel(description)
         description_label.setObjectName("newsCardDesc")
         description_label.setFont(self.get_font(10)) # Шрифт поменьше для описания
         description_label.setWordWrap(True)
         description_label.setContentsMargins(15, 0, 15, 5) # Отступы для описания
         description_label.setAlignment(Qt.AlignTop) # Выравниваем по верху
         layout.addWidget(description_label, 1) # Добавляем растяжение

         # layout.addStretch() # Убираем лишнее растяжение

         return card


    def _create_profiles_page(self):
        """Создает страницу 'Профили' (обновленный дизайн)."""
        page_wrapper = QWidget()
        page_wrapper.setObjectName("profilesPage") # ID для применения стилей фона
        inner_layout = QVBoxLayout(page_wrapper)
        inner_layout.setContentsMargins(40, 40, 40, 40)
        inner_layout.setSpacing(20)

        title = QLabel("Управление профилями")
        title.setObjectName("pageTitle") # Общий стиль заголовка страницы
        title.setFont(self.get_font(24, QFont.Bold))
        inner_layout.addWidget(title)

        # Убираем #contentBox, применяем стиль к самой странице
        profiles_container = QWidget()
        # profiles_container.setObjectName("contentBox") # Убрали
        container_layout = QHBoxLayout(profiles_container)
        container_layout.setSpacing(25)
        container_layout.setContentsMargins(0, 0, 0, 0) # Без внутренних отступов у контейнера

        list_widget_area = QVBoxLayout()
        list_widget_area.setSpacing(10)
        self.profiles_list = QListWidget()
        self.profiles_list.setFont(self.get_font(12))
        self.profiles_list.setObjectName("profilesList")
        self.profiles_list.itemSelectionChanged.connect(self.on_profile_selected) # Будет добавлено позже
        self.profiles_list.itemDoubleClicked.connect(self.edit_profile) # Будет добавлено позже
        list_widget_area.addWidget(self.profiles_list)

        buttons_area = QVBoxLayout()
        buttons_area.setSpacing(12)
        buttons_area.setAlignment(Qt.AlignTop)

        def create_action_button(text, object_name, slot, icon_char=None):
            btn = QPushButton(f"{icon_char} {text}" if icon_char else text)
            btn.setFont(self.get_font(11, QFont.Medium))
            btn.setCursor(Qt.PointingHandCursor)
            btn.setObjectName(object_name) # Используем общие стили actionButton/deleteButton
            btn.clicked.connect(slot)
            buttons_area.addWidget(btn)
            return btn

        add_profile_btn = create_action_button("Добавить", "actionButton", self.add_profile, "\u2795") # Будет добавлено позже
        self.edit_profile_btn = create_action_button("Редактировать", "actionButton", self.edit_profile, "\u270E") # Будет добавлено позже
        self.delete_profile_btn = create_action_button("Удалить", "deleteButton", self.delete_profile, "\u2716") # Будет добавлено позже

        self.edit_profile_btn.setEnabled(False)
        self.delete_profile_btn.setEnabled(False)

        container_layout.addLayout(list_widget_area, 3)
        container_layout.addLayout(buttons_area, 1)
        # Добавляем контейнер с виджетами прямо в layout страницы
        inner_layout.addWidget(profiles_container)

        return page_wrapper

    def _create_settings_page(self):
        """Создает страницу 'Настройки' с вкладками."""
        page_wrapper = QWidget()
        page_wrapper.setObjectName("settingsPage")
        inner_layout = QVBoxLayout(page_wrapper)
        inner_layout.setContentsMargins(40, 40, 40, 40)
        inner_layout.setSpacing(20)

        title = QLabel("Настройки лаунчера")
        title.setObjectName("pageTitle")
        title.setFont(self.get_font(24, QFont.Bold))
        inner_layout.addWidget(title)

        # Создаем TabWidget
        tab_widget = QTabWidget()
        tab_widget.setObjectName("settingsTabWidget")
        tab_widget.setFont(self.get_font(11)) # Шрифт для табов

        # --- Вкладка 1: Настройки Запуска ---
        launch_settings_widget = QWidget()
        launch_settings_layout = QVBoxLayout(launch_settings_widget)
        launch_settings_layout.setContentsMargins(20, 20, 20, 20) # Внутренние отступы вкладки
        launch_settings_layout.setSpacing(20)

        # Секция Java
        java_title = QLabel("Java") # Добавил текст заголовка секции
        java_title.setObjectName("settingsSectionTitle")
        java_title.setFont(self.get_font(16, QFont.Bold))
        launch_settings_layout.addWidget(java_title)
        java_path_layout = QHBoxLayout()
        java_path_label = QLabel("Путь к Java:")
        java_path_label.setFont(self.get_font(12))
        self.java_path_input = QLineEdit()
        self.java_path_input.setFont(self.get_font(11))
        self.java_path_input.setPlaceholderText("Автоматически (рекомендуется)")
        browse_java_btn = QPushButton("Обзор...")
        browse_java_btn.setFont(self.get_font(11, QFont.Medium))
        browse_java_btn.setCursor(Qt.PointingHandCursor)
        browse_java_btn.setObjectName("actionButton")
        browse_java_btn.clicked.connect(self.browse_java_path) # Будет добавлено позже
        java_path_layout.addWidget(java_path_label)
        java_path_layout.addWidget(self.java_path_input, 1)
        java_path_layout.addWidget(browse_java_btn)
        launch_settings_layout.addLayout(java_path_layout)

        # Секция Память
        memory_title = QLabel("Память") # Добавил текст заголовка секции
        memory_title.setObjectName("settingsSectionTitle")
        memory_title.setFont(self.get_font(16, QFont.Bold))
        launch_settings_layout.addWidget(memory_title)
        memory_layout = QHBoxLayout()
        memory_layout.setSpacing(10)
        def create_memory_input(label_text):
            label = QLabel(label_text)
            label.setFont(self.get_font(12))
            line_edit = QLineEdit()
            line_edit.setFont(self.get_font(11))
            line_edit.setFixedWidth(110)
            line_edit.setAlignment(Qt.AlignCenter)
            memory_layout.addWidget(label)
            memory_layout.addWidget(line_edit)
            return line_edit
        self.min_memory_input = create_memory_input("Мин (МБ):")
        memory_layout.addSpacing(30)
        self.max_memory_input = create_memory_input("Макс (МБ):")
        memory_layout.addStretch()
        launch_settings_layout.addLayout(memory_layout)

        # Секция Дополнительно
        additional_title = QLabel("Дополнительно") # Добавил текст заголовка секции
        additional_title.setObjectName("settingsSectionTitle")
        additional_title.setFont(self.get_font(16, QFont.Bold))
        launch_settings_layout.addWidget(additional_title)
        self.close_on_launch_checkbox = QCheckBox("Закрывать лаунчер после запуска игры")
        self.close_on_launch_checkbox.setFont(self.get_font(12))
        self.close_on_launch_checkbox.setObjectName("styledCheckbox")
        launch_settings_layout.addWidget(self.close_on_launch_checkbox)

        launch_settings_layout.addStretch(1) # Растягиваем вверх
        tab_widget.addTab(launch_settings_widget, "Настройки Запуска")

        # --- Вкладка 2: Фильтры Версий ---
        version_filters_widget = QWidget()
        version_filters_layout = QVBoxLayout(version_filters_widget)
        version_filters_layout.setContentsMargins(20, 20, 20, 20)
        version_filters_layout.setSpacing(15)

        versions_title = QLabel("Отображать в списке версии:")
        versions_title.setObjectName("settingsSectionTitle")
        versions_title.setFont(self.get_font(16, QFont.Bold))
        version_filters_layout.addWidget(versions_title)

        # Функция для создания чекбокса в вертикальный layout
        def create_version_filter_checkbox(text, setting_key):
            checkbox = QCheckBox(text)
            checkbox.setFont(self.get_font(12))
            checkbox.setObjectName("styledCheckbox")
            checkbox.setProperty("setting_key", setting_key)
            version_filters_layout.addWidget(checkbox) # Добавляем вертикально
            return checkbox

        self.show_releases_checkbox = create_version_filter_checkbox("Релизы (например, 1.20.1)", "show_releases")
        self.show_snapshots_checkbox = create_version_filter_checkbox("Снапшоты (например, 23w45a)", "show_snapshots")
        self.show_betas_checkbox = create_version_filter_checkbox("Beta-версии (старые)", "show_betas")
        self.show_alphas_checkbox = create_version_filter_checkbox("Alpha-версии (очень старые)", "show_alphas")

        version_filters_layout.addStretch(1) # Растягиваем вверх
        tab_widget.addTab(version_filters_widget, "Фильтры Версий")

        # Добавляем TabWidget в основной layout страницы
        inner_layout.addWidget(tab_widget)

        # --- Кнопка Сохранить (под табами) ---
        save_settings_btn = QPushButton("Сохранить настройки")
        save_settings_btn.setFont(self.get_font(14, QFont.Bold))
        save_settings_btn.setCursor(Qt.PointingHandCursor)
        save_settings_btn.setMinimumHeight(50)
        save_settings_btn.setObjectName("saveButton")
        save_settings_btn.clicked.connect(self.save_settings_from_ui) # Будет добавлено позже
        inner_layout.addWidget(save_settings_btn, 0, Qt.AlignRight) # Кнопка внизу справа

        return page_wrapper

    # --- Логика UI ---

    @Slot(QObject, str) # Принимаем QObject и путь (или None)
    def on_icon_loaded(self, widget: QObject, icon_path: str | None):
        """Слот для установки загруженной иконки."""
        # Убедимся, что виджет все еще существует и это кнопка
        if not isinstance(widget, QPushButton):
            return

        if icon_path and os.path.exists(icon_path):
            icon = QIcon(icon_path)
            widget.setIcon(icon)
            widget.setText("") # Убираем текст-заглушку
            # Устанавливаем размер иконки в зависимости от типа кнопки
            if widget.objectName().startswith("_sidebar"):
                 widget.setIconSize(QSize(28, 28))
            elif widget.objectName().startswith("_minimize") or widget.objectName().startswith("_close"):
                 widget.setIconSize(QSize(14, 14))
            # print(f"Иконка установлена для {widget.objectName()} из {icon_path}")
        else:
            print(f"Ошибка: Не удалось загрузить/найти иконку для {widget.objectName()} по URL {getattr(widget, 'icon_url', 'N/A')}")
            # Оставляем текст-заглушку или можно установить иконку ошибки
            # widget.setIcon(QIcon(os.path.join(RESOURCES_DIR, "icon_error.png"))) # Пример

    def change_page(self, index):
        """Переключает страницы с анимацией плавного появления/исчезновения."""
        current_index = self.content_stack.currentIndex()
        if index == current_index or not (0 <= index < self.content_stack.count()):
            return

        # --- Очистка предыдущей анимации/эффекта --- 
        active_anim = getattr(self, '_active_fade_animation', None)
        if active_anim:
            try:
                if active_anim.state() == QPropertyAnimation.Running:
                    active_anim.stop()
            except RuntimeError:
                pass # Объект уже мог быть удален
            self._active_fade_animation = None # Всегда сбрасываем ссылку

        active_effect = getattr(self, '_active_opacity_effect', None)
        if active_effect:
             try:
                 # Находим виджет, к которому был применен эффект
                 # parent() может быть None, если эффект не прикреплен
                 widget_with_effect = active_effect.parent()
                 if widget_with_effect and isinstance(widget_with_effect, QWidget):
                      # Проверяем, что эффект на виджете все еще тот самый
                      if widget_with_effect.graphicsEffect() == active_effect:
                          widget_with_effect.setGraphicsEffect(None)
             except RuntimeError:
                 pass # Объект эффекта уже удален
             # Не вызываем deleteLater() явно
             self._active_opacity_effect = None # Всегда сбрасываем ссылку

        # --- Настройка новой страницы --- 
        next_widget = self.content_stack.widget(index)
        next_widget.show()

        next_opacity_effect = QGraphicsOpacityEffect(next_widget)
        # Установка родителя для эффекта не обязательна, он привязывается к виджету
        next_widget.setGraphicsEffect(next_opacity_effect)
        next_opacity_effect.setOpacity(0.0)

        # Указываем self как родителя, чтобы Qt мог управлять памятью
        fade_in = QPropertyAnimation(next_opacity_effect, b"opacity", self)
        fade_in.setDuration(300)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.setEasingCurve(QEasingCurve.InOutQuad)

        # Сохраняем ссылки
        self._active_opacity_effect = next_opacity_effect
        self._active_fade_animation = fade_in

        # Устанавливаем текущий индекс стека
        self.content_stack.setCurrentIndex(index)

        fade_in.finished.connect(self._on_fade_in_finished)
        fade_in.start()

        # Обновляем состояние кнопок сайдбара
        buttons = [self.home_button, self.profiles_button, self.settings_button]
        for i, btn in enumerate(buttons):
            if hasattr(btn, 'setChecked'):
                btn.setChecked(i == index)

    def _on_fade_in_finished(self):
        """Слот, вызываемый по завершении анимации проявления."""
        # Просто сбрасываем ссылку на завершенную анимацию.
        # Очистка эффекта произойдет при следующем вызове change_page.
        # Проверяем, что атрибут существует перед присвоением None
        if hasattr(self, '_active_fade_animation'):
            self._active_fade_animation = None

    def add_profile(self):
        """Обрабатывает добавление нового профиля."""
        dialog = ProfileDialog(minecraft_font=self.get_font(11), colors=self.colors, parent=self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data["name"] or not data["username"]:
                QMessageBox.warning(self, "Ошибка", "Название профиля и имя пользователя не могут быть пустыми.")
                return
            new_uuid = self.profile_manager.add_profile(
                data["name"], data["username"],
                min_memory=data["min_memory"], max_memory=data["max_memory"],
                icon_filename=data.get("icon_filename") # Передаем имя файла иконки
            )
            if new_uuid:
                self.settings_manager.set("selected_profile_uuid", new_uuid)
                self.load_profiles_to_ui() # Будет добавлено позже
            else:
                 QMessageBox.critical(self, "Ошибка", "Не удалось добавить профиль.")

    def edit_profile(self):
        """Обрабатывает редактирование профиля."""
        selected_items = self.profiles_list.selectedItems()
        if not selected_items: return
        selected_uuid = selected_items[0].data(Qt.UserRole)
        profile_data = self.profile_manager.get_profile(selected_uuid)
        if not profile_data: return

        dialog = ProfileDialog(profile_uuid=selected_uuid, profile_data=profile_data, minecraft_font=self.get_font(11), colors=self.colors, parent=self)
        if dialog.exec() == QDialog.Accepted:
            data = dialog.get_data()
            if not data["name"] or not data["username"]:
                QMessageBox.warning(self, "Ошибка", "Название профиля и имя пользователя не могут быть пустыми.")
                return
            if self.profile_manager.update_profile(
                selected_uuid, data["name"], data["username"],
                min_memory=data["min_memory"], max_memory=data["max_memory"],
                icon_filename=data.get("icon_filename") # Передаем имя файла иконки
            ):
                self.load_profiles_to_ui() # Перезагружаем весь список для обновления иконки
                # Если редактировали текущий профиль, update_profile_widget вызовется из load_profiles_to_ui/on_profile_selected
            else:
                 QMessageBox.critical(self, "Ошибка", "Не удалось обновить профиль.")

    def delete_profile(self):
        """Обрабатывает удаление профиля, включая его иконку."""
        selected_items = self.profiles_list.selectedItems()
        if not selected_items: return
        if self.profiles_list.count() <= 1:
             QMessageBox.warning(self, "Нельзя удалить", "Невозможно удалить единственный профиль.")
             return
        selected_uuid = selected_items[0].data(Qt.UserRole)
        profile = self.profile_manager.get_profile(selected_uuid)
        if not profile: return

        reply = QMessageBox.question(self, "Удаление профиля",
                                     f"Вы уверены, что хотите удалить профиль\n'{profile.get('name', 'Без имени')}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            icon_filename_to_delete = profile.get("icon_filename") # Получаем имя файла иконки перед удалением профиля
            if self.profile_manager.delete_profile(selected_uuid):
                # Если удалили текущий, сбрасываем UUID в настройках
                if self.settings_manager.get("selected_profile_uuid") == selected_uuid:
                    self.settings_manager.set("selected_profile_uuid", None)
                self.load_profiles_to_ui() # Перезагружаем список

                # Удаляем файл иконки, если он был
                if icon_filename_to_delete:
                    icon_path_to_delete = os.path.join(PROFILE_ICONS_DIR, icon_filename_to_delete)
                    if os.path.exists(icon_path_to_delete):
                        try:
                            os.remove(icon_path_to_delete)
                            print(f"Иконка удаленного профиля удалена: {icon_path_to_delete}")
                        except OSError as e:
                            print(f"Ошибка удаления файла иконки {icon_path_to_delete}: {e}")
            else:
                 QMessageBox.critical(self, "Ошибка", "Не удалось удалить профиль.")

    def on_profile_selected(self):
        """Обновляет UI при выборе профиля в списке."""
        selected_items = self.profiles_list.selectedItems()
        is_selected = bool(selected_items)
        self.edit_profile_btn.setEnabled(is_selected)
        self.delete_profile_btn.setEnabled(is_selected and self.profiles_list.count() > 1) # Нельзя удалить единственный

        if is_selected:
            selected_uuid = selected_items[0].data(Qt.UserRole)
            # Сохраняем выбранный UUID в настройках, если он изменился
            if self.settings_manager.get("selected_profile_uuid") != selected_uuid:
                 self.settings_manager.set("selected_profile_uuid", selected_uuid)
            self.update_profile_widget() # Обновляем виджет в шапке
            # self._update_mod_install_buttons_state() # Убрано, моды отключены

    def update_profile_widget(self):
        """Обновляет виджет профиля в шапке."""
        if not hasattr(self, 'profile_widget'): return # Проверка, что виджет уже создан

        selected_uuid = self.settings_manager.get("selected_profile_uuid")
        profile = self.profile_manager.get_profile(selected_uuid) if selected_uuid else None

        if profile:
            self.profile_widget.update_profile(
                 profile.get("username"),
                 profile.get("icon_filename")
             )
        else:
             self.profile_widget.update_profile("Профиль не выбран", None)

    def apply_styles(self):
        """Применяет QSS стили к главному окну."""
        primary = self.colors['primary']
        secondary = self.colors['secondary']
        accent_green = self.colors['accent_green']
        accent_green_hover = self.colors['accent_green_hover']
        bg_main = self.colors['background_main']
        bg_sidebar = self.colors['background_sidebar']
        surface = self.colors['surface']
        surface_solid = self.colors['surface_solid']
        surface_light = self.colors['surface_light']
        text_color = self.colors['text']
        text_light = self.colors['text_light']
        border_color = self.colors['border']
        red_color = self.colors['red']
        red_hover = self.colors['red_hover']

        # Convert potential pathlib paths to strings for os.path.join
        checkmark_path = os.path.join(str(RESOURCES_DIR), "icon_checkmark.png").replace("\\", "/")
        dropdown_path = os.path.join(str(RESOURCES_DIR), "icon_dropdown.png").replace("\\", "/")

        self.setStyleSheet(f"""
            /* --- Основное Окно --- */
            QMainWindow {{
                background-color: {bg_main};
            }}
            QWidget#main_widget {{ /* Конкретно к главному виджету */
                background-color: {bg_main};
            }}

            /* --- Кастомная строка заголовка --- */
            CustomTitleBar#customTitleBar {{
                background-color: {bg_sidebar}; /* Темнее */
                border-bottom: 1px solid {border_color};
            }}
            QLabel#titleBarLabel {{
                color: {text_color};
                font-size: 11pt;
                padding-left: 5px;
            }}
            /* Кнопки управления окном */
            QPushButton#_minimizeButton, QPushButton#_closeButton {{
                background-color: transparent;
                border: none;
                color: {text_light}; /* Бледный текст */
                font-family: "Marlett"; /* Шрифт для иконок */
                font-size: 14pt;
                padding: 0px 15px;
                min-height: 30px; /* Убедимся, что высота достаточна */
                max-width: 50px;
            }}
            QPushButton#_minimizeButton {{
                 border-radius: 0px;
            }}
            QPushButton#_closeButton {{
                 border-radius: 0px;
            }}
            QPushButton#_minimizeButton:hover {{
                background-color: {surface_light};
                color: {text_color};
            }}
            QPushButton#_closeButton:hover {{
                background-color: {red_color}; /* Красный фон при наведении */
                color: white;
            }}

             /* --- Сайдбар --- */
            QWidget#sidebar {{
                background-color: {bg_sidebar};
                border-right: 1px solid {border_color};
            }}
            QPushButton[objectName^="_sidebar"] {{ /* Ко всем кнопкам сайдбара */
                background-color: transparent;
                border: none;
                border-radius: 8px; /* Скругление */
                padding: 5px;
                margin: 0 5px; /* Небольшие отступы по бокам */
                icon-size: 28px 28px; /* Явно задаем размер иконки */
            }}
            QPushButton[objectName^="_sidebar"]:hover {{
                background-color: {surface_light};
            }}
            QPushButton[objectName^="_sidebar"]:checked {{
                background-color: {primary}; /* Основной цвет для активной кнопки */
            }}
             /* --- Верхняя панель --- */
            QWidget#topBar {{
                 background-color: {bg_main};
                 border-bottom: 1px solid {border_color};
            }}
            /* Виджет профиля */
            QWidget#profileWidget {{
                background: transparent;
            }}
            QLabel#profileTopIcon {{ /* Новое имя */
                border-radius: 8px; /* Скругление для иконки */
            }}
            QLabel#profileUsername {{
                color: {text_color};
                font-weight: bold;
            }}
             QLabel#onlineLabel {{
                  color: {text_light};
                  font-size: 9pt;
             }}

            /* --- Стек контента --- */
            QStackedWidget#contentStack {{
                 background-color: transparent; /* Сам стек прозрачный */
            }}

             /* --- Страницы контента (Общий фон/стиль) --- */
            QWidget#playPage, QWidget#profilesPage, QWidget#settingsPage {{
                 background-color: {bg_main}; /* Фон для всех страниц */
            }}

            /* --- Элементы на странице Play --- */
            QLabel#playPageTitle {{ color: {text_color}; }}
            QLabel#playPageDesc {{ color: {text_light}; }}
            QLabel#newsTitle {{ color: {text_color}; margin-bottom: 5px; }}
            QLabel#playButtonStatus {{ color: {text_light}; font-size: 9pt; }}

            /* Большая кнопка Играть */
            QPushButton#playButtonLarge {{
                 background-color: {accent_green};
                 color: white; /* Белый текст на зеленом */
                 border: none;
                 border-radius: 8px;
                 padding: 10px 20px;
            }}
            QPushButton#playButtonLarge:hover {{
                 background-color: {accent_green_hover};
            }}
            QPushButton#playButtonLarge:disabled {{
                 background-color: {surface_light};
                 color: {text_light};
            }}

             /* Комбобокс выбора версии */
            QComboBox#versionSelector {{
                background-color: {surface_solid};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 5px;
                padding: 8px 10px;
                min-height: 30px; /* Минимальная высота */
            }}
            QComboBox#versionSelector::drop-down {{
                 border: none;
                 background: transparent;
                 width: 20px;
                 subcontrol-origin: padding;
                 subcontrol-position: top right;
                 padding-right: 5px;
            }}
            QComboBox#versionSelector::down-arrow {{
                image: url({dropdown_path}); /* Путь к иконке */
                width: 12px;
                height: 12px;
            }}
            QComboBox QAbstractItemView {{ /* Выпадающий список */
                 background-color: {surface_solid};
                 border: 1px solid {primary};
                 color: {text_color};
                 selection-background-color: {primary};
                 selection-color: white;
                 outline: 0px; /* Убираем рамку выделения */
                 padding: 5px;
            }}

             /* Карточка новости */
            QWidget#newsCard {{
                 background-color: {surface_solid};
                 border-radius: 8px;
                 border: 1px solid {border_color};
                 /* transition: background-color 0.2s ease; Плавность при наведении */
            }}
            QWidget#newsCard:hover {{
                 background-color: {surface_light};
                 border: 1px solid {secondary};
            }}
            QLabel#newsCardImage {{
                 border-top-left-radius: 8px;
                 border-top-right-radius: 8px;
                 background-color: {bg_main}; /* Фон под картинкой */
            }}
            QLabel#newsCardTitle {{ color: {text_color}; }}
            QLabel#newsCardDesc {{ color: {text_light}; }}

            /* --- Элементы на странице Профили --- */
             QLabel#pageTitle {{ /* Общий стиль для заголовков страниц */
                 color: {text_color};
                 padding-bottom: 10px; /* Отступ снизу */
            }}
             QListWidget#profilesList {{
                 background-color: {surface_solid};
                 border: 1px solid {border_color};
                 border-radius: 5px;
                 color: {text_color};
                 padding: 5px;
                 outline: 0px; /* Убираем рамку выделения */
             }}
             QListWidget#profilesList::item {{
                 padding: 8px 10px;
                 border-radius: 3px; /* Небольшое скругление элемента */
             }}
             QListWidget#profilesList::item:selected {{
                 background-color: {primary};
                 color: white;
             }}
             QListWidget#profilesList::item:hover {{
                 background-color: {surface_light};
             }}

            /* --- Общие кнопки действий (Добавить, Редактировать, Обзор...) --- */
            QPushButton#actionButton {{
                background-color: {primary};
                color: white;
                border: none;
                padding: 10px 15px;
                border-radius: 5px;
                min-height: 30px;
            }}
            QPushButton#actionButton:hover {{
                background-color: {secondary};
            }}
             QPushButton#actionButton:disabled {{
                 background-color: {surface_light};
                 color: {text_light};
             }}

            /* Кнопка Удалить */
            QPushButton#deleteButton {{
                 background-color: {red_color};
                 color: white;
                 border: none;
                 padding: 10px 15px;
                 border-radius: 5px;
                 min-height: 30px;
            }}
            QPushButton#deleteButton:hover {{
                 background-color: {red_hover};
            }}
            QPushButton#deleteButton:disabled {{
                 background-color: {surface_light};
                 color: {text_light};
             }}

            /* --- Элементы на странице Настройки --- */
             QLabel#settingsSectionTitle {{
                  color: {primary};
                  font-size: 14pt; /* Крупнее */
                  border-bottom: 1px solid {border_color};
                  padding-bottom: 5px;
                  margin-bottom: 10px;
             }}
             QTabWidget#settingsTabWidget::pane {{ /* Область вкладки */
                 border: 1px solid {border_color};
                 border-top: none; /* Верхняя граница рисуется табами */
                 border-radius: 0 0 5px 5px;
                 background-color: {surface_solid};
                 padding: 15px;
             }}
             QTabBar::tab {{
                 background: {surface_light};
                 color: {text_light};
                 border: 1px solid {border_color};
                 border-bottom: none;
                 border-top-left-radius: 5px;
                 border-top-right-radius: 5px;
                 padding: 10px 20px;
                 margin-right: 2px;
             }}
             QTabBar::tab:selected {{
                 background: {surface_solid}; /* Цвет фона вкладки */
                 color: {text_color};
                 border: 1px solid {border_color};
                 border-bottom: 1px solid {surface_solid}; /* Соединяем с pane */
             }}
             QTabBar::tab:hover {{
                 background: {surface}; /* Темнее при наведении */
                 color: {text_color};
             }}
             /* Поля ввода и чекбоксы на странице настроек */
             QWidget#settingsPage QLineEdit {{
                 background: rgba(255, 255, 255, 0.05);
                 border: 1px solid rgba(255, 255, 255, 0.1);
                 border-radius: 5px;
                 padding: 8px 10px;
                 color: {text_color};
                 selection-background-color: {primary};
             }}
             QWidget#settingsPage QLineEdit:focus {{
                 border: 1px solid {primary};
                 background: rgba(255, 255, 255, 0.08);
             }}
             QWidget#settingsPage QLabel {{
                 color: {text_light}; /* Светло-серый для подписей */
                 background: transparent; /* Прозрачный фон */
             }}
             QWidget#settingsPage QCheckBox#styledCheckbox {{
                 color: {text_color};
                 spacing: 8px; /* Отступ между галочкой и текстом */
             }}
             QWidget#settingsPage QCheckBox#styledCheckbox::indicator {{
                 width: 16px;
                 height: 16px;
                 border: 1px solid {border_color};
                 border-radius: 3px;
                 background-color: rgba(255, 255, 255, 0.05);
             }}
             QWidget#settingsPage QCheckBox#styledCheckbox::indicator:checked {{
                 background-color: {primary};
                 border: 1px solid {primary};
                 image: url({checkmark_path});
             }}
             QWidget#settingsPage QCheckBox#styledCheckbox::indicator:hover {{
                 border: 1px solid {secondary};
             }}
              /* Кнопка Сохранить */
             QPushButton#saveButton {{
                  background-color: {accent_green};
                  color: white;
                  border: none;
                  border-radius: 5px;
                  padding: 12px 30px;
             }}
             QPushButton#saveButton:hover {{
                  background-color: {accent_green_hover};
             }}

             /* --- Прогресс-бар --- */
             CustomProgressBar {{
                 background-color: {surface_solid};
                 border: 1px solid {border_color};
                 border-radius: 6px;
                 text-align: center;
                 color: {text_color};
                 font-size: 8pt; /* Мельче шрифт */
             }}
             CustomProgressBar::chunk {{
                 background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {primary}, stop:1 {secondary});
                 border-radius: 5px;
                 margin: 1px; /* Отступ для рамки */
             }}
             QToolTip {{
                 background-color: {surface_solid};
                 color: {text_color};
                 border: 1px solid {border_color};
                 padding: 5px;
                 border-radius: 3px;
             }}
        """)
        print("Стили интерфейса применены.")

    # --- Управление настройками (Восстановленные методы) ---

    def browse_java_path(self):
        """Открывает диалог выбора исполняемого файла Java."""
        filters = "Java Executable (java.exe)" if sys.platform == "win32" else "Java Executable (java);;All files (*)"
        current_path = self.java_path_input.text()
        start_dir = os.path.dirname(current_path) if current_path and os.path.exists(current_path) else ""

        filepath, _ = QFileDialog.getOpenFileName(self, "Выберите исполняемый файл Java", start_dir, filters)
        if filepath:
            self.java_path_input.setText(filepath)

    def load_settings_to_ui(self):
        """Загружает сохраненные настройки в элементы UI на странице настроек."""
        try:
            # Проверяем наличие элементов перед доступом
            if hasattr(self, 'java_path_input'):
                self.java_path_input.setText(self.settings_manager.get("java_path"))
            if hasattr(self, 'min_memory_input'):
                self.min_memory_input.setText(str(self.settings_manager.get("min_memory_mb")))
            if hasattr(self, 'max_memory_input'):
                self.max_memory_input.setText(str(self.settings_manager.get("max_memory_mb")))
            if hasattr(self, 'close_on_launch_checkbox'):
                self.close_on_launch_checkbox.setChecked(self.settings_manager.get("close_on_launch"))

            # Загрузка настроек фильтров версий
            if hasattr(self, 'show_releases_checkbox'):
                self.show_releases_checkbox.setChecked(self.settings_manager.get("show_releases"))
            if hasattr(self, 'show_snapshots_checkbox'):
                self.show_snapshots_checkbox.setChecked(self.settings_manager.get("show_snapshots"))
            if hasattr(self, 'show_betas_checkbox'):
                self.show_betas_checkbox.setChecked(self.settings_manager.get("show_betas"))
            if hasattr(self, 'show_alphas_checkbox'):
                self.show_alphas_checkbox.setChecked(self.settings_manager.get("show_alphas"))

        except Exception as e:
            print(f"Ошибка при загрузке настроек в UI: {e}")
            QMessageBox.warning(self, "Ошибка UI", "Не удалось загрузить настройки в интерфейс.")

    def save_settings_from_ui(self):
        """Сохраняет настройки из UI страницы настроек."""
        # Проверяем наличие элементов перед доступом
        if not hasattr(self, 'min_memory_input') or not hasattr(self, 'max_memory_input') \
           or not hasattr(self, 'java_path_input') or not hasattr(self, 'close_on_launch_checkbox') \
           or not hasattr(self, 'show_releases_checkbox') or not hasattr(self, 'show_snapshots_checkbox') \
           or not hasattr(self, 'show_betas_checkbox') or not hasattr(self, 'show_alphas_checkbox'):
            print("Ошибка: Элементы UI настроек не инициализированы.")
            return

        # ... (Валидация и сохранение памяти) ...
        min_mem_str = self.min_memory_input.text().strip()
        max_mem_str = self.max_memory_input.text().strip()
        try:
            min_mem = int(min_mem_str) if min_mem_str else SettingsManager.DEFAULT_SETTINGS["min_memory_mb"]
            max_mem = int(max_mem_str) if max_mem_str else SettingsManager.DEFAULT_SETTINGS["max_memory_mb"]
            if min_mem < 512: min_mem = 512
            if max_mem < min_mem: max_mem = min_mem
        except ValueError:
            QMessageBox.warning(self, "Ошибка ввода", "Неверный формат памяти. Пожалуйста, введите целые числа.")
            return

        # Сохраняем основные настройки
        self.settings_manager.set("java_path", self.java_path_input.text().strip())
        self.settings_manager.set("min_memory_mb", min_mem)
        self.settings_manager.set("max_memory_mb", max_mem)
        self.settings_manager.set("close_on_launch", self.close_on_launch_checkbox.isChecked())

        # Сохраняем настройки фильтров версий
        self.settings_manager.set("show_releases", self.show_releases_checkbox.isChecked())
        self.settings_manager.set("show_snapshots", self.show_snapshots_checkbox.isChecked())
        self.settings_manager.set("show_betas", self.show_betas_checkbox.isChecked())
        self.settings_manager.set("show_alphas", self.show_alphas_checkbox.isChecked())

        # Обновляем поля ввода памяти
        self.min_memory_input.setText(str(min_mem))
        self.max_memory_input.setText(str(max_mem))

        if hasattr(self, 'update_profile_widget'):
            self.update_profile_widget() # Будет добавлено позже

        # Перезагружаем список версий, чтобы применить фильтры
        self.load_minecraft_versions() # Будет добавлено позже

        QMessageBox.information(self, "Сохранено", "Настройки успешно сохранены.\nСписок версий обновлен.")

    # --- Запуск игры ---
    # (Методы launch_minecraft, update_progress, start_game_process, show_launch_error остаются почти без изменений)
    # ...
    def launch_minecraft(self):
        """Основной метод запуска игры, используя выбранную версию."""
        selected_uuid = self.settings_manager.get("selected_profile_uuid")
        profile = self.profile_manager.get_profile(selected_uuid) if selected_uuid else None

        if not profile or not profile.get("username"):
            QMessageBox.warning(self, "Ошибка", "Выберите профиль с именем пользователя.")
            return

        # Получаем выбранную версию из QComboBox
        if not hasattr(self, 'version_selector') or self.version_selector.count() == 0:
            QMessageBox.warning(self, "Ошибка", "Нет доступных версий Minecraft для запуска.")
            return
        version = self.version_selector.currentText()
        if not version:
             QMessageBox.warning(self, "Ошибка", "Пожалуйста, выберите версию Minecraft.")
             return

        min_mem = profile.get("min_memory_override", self.settings_manager.get("min_memory_mb"))
        max_mem = profile.get("max_memory_override", self.settings_manager.get("max_memory_mb"))

        # --- Валидация и установка значений памяти по умолчанию --- 
        if not isinstance(min_mem, int) or min_mem < 512:
            print(f"Предупреждение: Некорректное значение min_mem ({min_mem}), используется значение по умолчанию.")
            min_mem = SettingsManager.DEFAULT_SETTINGS["min_memory_mb"]
        
        if not isinstance(max_mem, int) or max_mem < min_mem:
            print(f"Предупреждение: Некорректное значение max_mem ({max_mem}), используется значение по умолчанию или min_mem.")
            default_max = SettingsManager.DEFAULT_SETTINGS["max_memory_mb"]
            max_mem = max(min_mem, default_max) # Гарантируем, что max_mem не меньше min_mem

        java_path = self.settings_manager.get("java_path") or None

        self.launch_button.setEnabled(False)
        self.launch_button.setText("ЗАГРУЗКА...") # Текст кнопки при загрузке
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("Подготовка...")
        self.progress_bar.setVisible(True)
        QApplication.processEvents()

        self.launch_options = {
            "username": profile["username"], "version": version,
            "min_memory": min_mem, "max_memory": max_mem
            # Убираем java_path отсюда, он будет определен в потоке
        }

        # Запускаем поток (передаем пользовательский путь, если он есть)
        user_java_path = self.settings_manager.get("java_path") or None
        self.installer_thread = MinecraftVersionInstaller(version, self.minecraft_directory, user_java_path) # Будет добавлено позже
        self.installer_thread.progress.connect(self.update_progress)
        # Передаем определенный Java путь в start_game_process при завершении
        self.installer_thread.finished.connect(lambda: self.start_game_process(self.installer_thread.final_java_path))
        self.installer_thread.error.connect(self.show_launch_error)
        self.installer_thread.start()

    def update_progress(self, value: int, status: str):
        """Обновляет прогресс-бар."""
        # (Без изменений)
        if value == -1: # Неопределенный режим или только статус
            self.progress_bar.setRange(0, 0)
            self.progress_bar.setFormat(status if status else "Обработка...")
        else: # Определенный режим (0-100)
            self.progress_bar.setRange(0, 100)
            self.progress_bar.setValue(value)
            self.progress_bar.setFormat(f"{status} ({value}%)" if status else f"{value}%)")
        self.progress_bar.setAlignment(Qt.AlignCenter)

    def start_game_process(self, java_executable_path: str | None):
        """Запускает процесс игры, используя определенный путь к Java."""
        # --- Флаг для предотвращения двойного запуска --- 
        if getattr(self, '_game_process_started', False):
            print("Предупреждение: start_game_process вызван повторно. Игнорирование.")
            return
        self._game_process_started = True
        # --- Конец блока предотвращения --- 

        self.progress_bar.setRange(0, 0)
        self.progress_bar.setFormat("Запуск Minecraft...")
        QApplication.processEvents()

        if not java_executable_path:
             self.show_launch_error("Критическая ошибка: Не удалось определить путь к Java для запуска.")
             self._game_process_started = False # Сброс флага при ошибке

    def show_launch_error(self, error_message: str):
        """Отображает сообщение об ошибке запуска и восстанавливает UI."""
        print(f"Ошибка запуска: {error_message}")
        QMessageBox.critical(self, "Ошибка запуска", f"Не удалось запустить Minecraft:\n\n{error_message}")

        # Сбрасываем флаг, чтобы можно было попробовать запустить снова
        self._game_process_started = False

        # Восстанавливаем состояние кнопки и прогресс-бара
        if hasattr(self, 'launch_button'):
        self.launch_button.setEnabled(True)
            self.launch_button.setText("ЗАПУСТИТЬ") # Возвращаем исходный текст
        if hasattr(self, 'progress_bar'):
        self.progress_bar.setVisible(False)
            self.progress_bar.setFormat("") # Сбрасываем текст
        QApplication.processEvents()

    def load_profiles_to_ui(self):
        """Загружает профили в список на странице профилей."""
        if not hasattr(self, 'profiles_list'):
            print("Ошибка: profiles_list не инициализирован")
            return

        self.profiles_list.clear()
        profiles = self.profile_manager.get_all_profiles()
        selected_uuid = self.settings_manager.get("selected_profile_uuid")

        # Проверяем наличие дефолтной иконки один раз
        default_icon_exists = os.path.exists(DEFAULT_PROFILE_ICON)
        if not default_icon_exists:
            print(f"Предупреждение: Файл дефолтной иконки не найден: {DEFAULT_PROFILE_ICON}")

        for uuid, profile in profiles.items():
            item = QListWidgetItem(profile.get("name", "Без имени"))
            item.setData(Qt.UserRole, uuid)

            # Установка иконки
            icon_to_set = None
            icon_filename = profile.get("icon_filename")
            if icon_filename:
                custom_icon_path = os.path.join(PROFILE_ICONS_DIR, icon_filename)
                if os.path.exists(custom_icon_path):
                    icon_to_set = QIcon(custom_icon_path)

            if not icon_to_set and default_icon_exists:
                icon_to_set = QIcon(DEFAULT_PROFILE_ICON)

            if icon_to_set:
                 item.setIcon(icon_to_set)
            # Можно задать размер иконки в списке, если нужно
            self.profiles_list.setIconSize(QSize(32, 32))

            self.profiles_list.addItem(item)
            if uuid == selected_uuid:
                item.setSelected(True)

        # Если нет выбранного профиля, но есть профили в списке
        if not selected_uuid and self.profiles_list.count() > 0:
             self.profiles_list.item(0).setSelected(True)
             first_uuid = self.profiles_list.item(0).data(Qt.UserRole)
             self.settings_manager.set("selected_profile_uuid", first_uuid)
             # Важно обновить виджет профиля после выбора первого элемента
             self.update_profile_widget()

    def _parse_version_numbers(self, version_id: str) -> tuple:
        """Извлекает числовые компоненты из строки версии."""
        # Для обычных версий (1.2.3)
        match = re.match(r'^(\d+)\.(\d+)(?:\.(\d+))?$', version_id)
        if match:
            parts = [int(p) for p in match.groups() if p is not None]
            return tuple(parts + [0] * (3 - len(parts)))
        
        # Для снапшотов (23w12a)
        match = re.match(r'^(\d{2})w(\d{2})([a-z])$', version_id.lower())
        if match:
            year, week, letter = match.groups()
            # Преобразуем год в полный формат (23 -> 2023)
            full_year = 2000 + int(year)
            # Возвращаем в формате, который обеспечит правильную сортировку
            return (full_year, int(week), ord(letter))
        
        # Для других форматов - просто ищем все числа
        nums = re.findall(r'\d+', version_id)
        if nums:
            return tuple(int(n) for n in nums)
        
        # Если ничего не нашли, возвращаем минимальное значение
        return (-1,)

    def _format_version_name(self, version_id: str, version_type: str, is_installed: bool) -> str:
        """Форматирует имя версии для отображения в списке (только ID)."""
        # Возвращаем только ID версии без префиксов и суффиксов
        return version_id

    def _version_sort_key(self, version_id: str, version_type: str) -> tuple:
        """Создает ключ для сортировки версий."""
        # Приоритеты типов версий (чем больше число, тем выше в списке)
        type_priority_map = {
            "release": 100,  # Релизы всегда вверху
            "snapshot": 90,  # Снапшоты сразу после релизов
            "old_beta": 80,  # Беты ниже
            "old_alpha": 70  # Альфы в самом низу
        }
        type_priority = type_priority_map.get(version_type, 0)
        
        # Получаем числовые компоненты версии
        version_numbers = self._parse_version_numbers(version_id)
        
        return (type_priority, version_numbers)

    def load_minecraft_versions(self):
        """Загружает версии Minecraft в QComboBox с учетом фильтров и сортировкой."""
        if not hasattr(self, 'version_selector'):
            return

        current_selected_data = self.version_selector.currentData()
        self.version_selector.clear()
        self.version_selector.setEnabled(True)
        self.launch_button.setEnabled(True)

        # --- Загрузка настроек фильтров ---
        show_releases = self.settings_manager.get("show_releases")
        show_snapshots = self.settings_manager.get("show_snapshots")
        show_betas = self.settings_manager.get("show_betas")
        show_alphas = self.settings_manager.get("show_alphas")

        all_versions_data_dict = {} # Словарь для хранения всех версий {id: {name, type}}
        self.installed_version_ids = set()

        try:
            # 1. Получаем установленные версии
            installed_versions_info = minecraft_launcher_lib.utils.get_installed_versions(self.minecraft_directory)
            for v_info in installed_versions_info:
                version_id = v_info['id']
                version_type = v_info.get('type', 'release')
                self.installed_version_ids.add(version_id)
                if version_id not in all_versions_data_dict:
                    formatted_name = self._format_version_name(version_id, version_type, True)
                    all_versions_data_dict[version_id] = {
                        "name": formatted_name,
                        "type": version_type,
                        "installed": True # Добавляем флаг, что версия установлена
                    }

            # 2. Получаем список всех доступных версий
            all_versions_list = minecraft_launcher_lib.utils.get_version_list()
            for v_info in all_versions_list:
                     version_id = v_info["id"]
                version_type = v_info.get("type") # Может быть None
                # Добавляем, только если еще не добавили из установленных
                if version_id not in all_versions_data_dict:
                    is_installed = version_id in self.installed_version_ids # Это будет False здесь
                    formatted_name = self._format_version_name(version_id, version_type, is_installed)
                    all_versions_data_dict[version_id] = {
                        "name": formatted_name,
                        "type": version_type,
                        "installed": is_installed
                    }

            # --- 3. Фильтруем версии ---
            filtered_versions = {}
            for version_id, data in all_versions_data_dict.items():
                v_type = data.get("type")
                should_show = False
                if v_type == "release" and show_releases:
                    should_show = True
                elif v_type == "snapshot" and show_snapshots:
                    should_show = True
                elif v_type == "old_beta" and show_betas:
                    should_show = True
                elif v_type == "old_alpha" and show_alphas:
                    should_show = True
                # Всегда показывать установленные версии, если они не подпадают под активные фильтры?
                # Решение: Если версия установлена, но ее тип отключен, все равно показываем,
                # но можно добавить пометку или изменить стиль. Пока просто показываем.
                # if data.get("installed"): # Раскомментируйте, если хотите всегда показывать установленные
                #     should_show = True

                if should_show:
                    filtered_versions[version_id] = data

            # --- 4. Сортируем отфильтрованные версии (от новых к старым) ---
            # Теперь сортируем filtered_versions
            sorted_versions = sorted(
                filtered_versions.items(),
                key=lambda item: self._version_sort_key(item[0], item[1].get("type", "unknown")),
                reverse=True  # От новых к старым
            )

            # --- 5. Добавляем отсортированные и отфильтрованные версии в комбобокс ---
            for version_id, version_data in sorted_versions:
                # Переформатируем имя на случай, если показ установленных версий как-то изменился
                display_name = self._format_version_name(version_id, version_data["type"], version_data["installed"])
                self.version_selector.addItem(display_name, userData=version_id)

            # --- 6. Выбираем версию ---
            if self.version_selector.count() > 0:
                initial_index = -1

                # Пробуем восстановить предыдущий выбор
                if current_selected_data:
                     initial_index = self.version_selector.findData(current_selected_data)

                # Если не удалось, пробуем найти версию по умолчанию
                if initial_index == -1:
                   initial_index = self.version_selector.findData(MINECRAFT_VERSION)

                # Если и это не удалось, берем первую версию (самую новую из отфильтрованного списка)
                if initial_index == -1:
                   initial_index = 0

                     self.version_selector.setCurrentIndex(initial_index)
            else:
                self.version_selector.addItem("Нет версий (проверьте фильтры)")
                 self.version_selector.setEnabled(False)
                 self.launch_button.setEnabled(False)

        except requests.exceptions.RequestException as e:
            print(f"Сетевая ошибка при получении списка версий: {e}")
             self.version_selector.addItem("Ошибка сети (версии)")
             self.version_selector.setEnabled(False)
             self.launch_button.setEnabled(False)
        except Exception as e:
            print(f"Ошибка при получении списка версий: {e}")
            traceback.print_exc()
            self.version_selector.addItem("Ошибка загрузки версий")
            self.version_selector.setEnabled(False)
            self.launch_button.setEnabled(False)

        # Обновляем состояние кнопок установки модов после загрузки версий
        # self._update_mod_install_buttons_state() # Убрано, т.к. установка модов временно отключена

    # --- Установка Модов (временно отключено) ---
    # def _update_mod_install_buttons_state(self):
    #     ...
    # def install_fabric(self):
    #     ...
    # def install_forge(self):
    #     ...
    # def on_mod_install_finished(self, mod_type: str):
    #     ...
    # def show_install_error(self, error: str):
    #     ...
    # def _set_install_ui_state(self, installing: bool, mod_type: str = ""):
    #     ...
    # def _is_vanilla_selected(self) -> bool:
    #     ...


# --- Вспомогательные классы ---
# (MinecraftVersionInstaller, SidebarButton, CustomProgressBar остаются без изменений)
class MinecraftVersionInstaller(QThread):
    """Поток для установки/проверки версии Minecraft и Java Runtime."""
    progress = Signal(int, str) # (value: 0-100 or -1, status: str)
    finished = Signal(str) # Возвращаем путь к Java
    error = Signal(str)

    def __init__(self, version, minecraft_directory, java_path=None):
        super().__init__()
        self.version = version
        self.minecraft_directory = minecraft_directory
        self.user_java_path = java_path if java_path else None
        self.final_java_path = None # Инициализируем здесь
        print(f"Installer Thread: Version={self.version}, Dir={self.minecraft_directory}, Java={self.user_java_path}")

    def run(self):
        callback = {
            "setStatus": lambda status: self.progress.emit(-1, status),
            "setProgress": lambda value: self.progress.emit(value, ""),
            "setMax": lambda value: None
        }
        # Определяем целевую версию JVM (можно сделать настраиваемой позже)
        target_jvm_version = "jre-legacy"

        try:
            effective_java_path = self.user_java_path
            self.final_java_path = None # Сбрасываем перед попыткой

            # 1. Определяем путь к Java
            if not effective_java_path:
                print(f"Явный путь к Java не указан, ищем существующую ({target_jvm_version})...")
                try:
                    # Ищем конкретную версию JVM
                    effective_java_path = minecraft_launcher_lib.runtime.get_executable_path(
                        jvm_version=target_jvm_version, # Указываем версию
                        minecraft_directory=self.minecraft_directory
                    )
                    if effective_java_path:
                        print(f"Найдена управляемая Java ({target_jvm_version}): {effective_java_path}")
                    else:
                        print(f"Управляемая Java ({target_jvm_version}) не найдена.")
                except Exception as e:
                    print(f"Ошибка при поиске Java ({target_jvm_version}): {e}")
                    effective_java_path = None

            # 2. Если Java не найдена или указана пользователем, но не существует,
            #    пытаемся установить целевую версию JVM
            if not effective_java_path or (self.user_java_path and not os.path.exists(self.user_java_path)):
                # Если пользователь указал путь, но он не валиден, игнорируем его
                if self.user_java_path and not os.path.exists(self.user_java_path):
                     print(f"Предупреждение: Указанный пользователем путь Java не найден: {self.user_java_path}. Попытка установки {target_jvm_version}.")
                     effective_java_path = None # Сбрасываем, чтобы точно установить

                print(f"Пытаемся установить Java Runtime ({target_jvm_version})...")
                callback["setStatus"](f"Установка среды Java ({target_jvm_version})...")
                try:
                    # Устанавливаем конкретную версию JVM
                    minecraft_launcher_lib.runtime.install_jvm_runtime(
                        jvm_version=target_jvm_version, # Указываем версию
                        minecraft_directory=self.minecraft_directory,
                        callback=callback
                    )
                    # После установки снова пытаемся получить путь
                    effective_java_path = minecraft_launcher_lib.runtime.get_executable_path(
                        jvm_version=target_jvm_version,
                        minecraft_directory=self.minecraft_directory
                    )
                    if not effective_java_path:
                        raise RuntimeError(f"Не удалось найти {target_jvm_version} даже после попытки установки.")
                    print(f"Java Runtime ({target_jvm_version}) успешно установлен: {effective_java_path}")
                except Exception as java_e:
                    self.error.emit(f"Критическая ошибка: Не удалось установить Java Runtime ({target_jvm_version}): {java_e}")
                    return # Прерываем выполнение потока

            # На этом этапе у нас должен быть рабочий путь к Java в effective_java_path
            if not effective_java_path or not os.path.exists(effective_java_path):
                 self.error.emit(f"Критическая ошибка: Не удалось определить действительный путь к Java.")
                 return

            # Сохраняем действительный путь к Java
            self.final_java_path = effective_java_path
            print(f"Используемый Java: {self.final_java_path}")

            # 3. Установка/Проверка версии Minecraft
            callback["setStatus"](f"Проверка Minecraft {self.version}...")
            minecraft_launcher_lib.install.install_minecraft_version(
                self.version,
                self.minecraft_directory,
                callback=callback
            )

            print(f"Установка Minecraft {self.version} завершена.")
            callback["setStatus"]("Готово к запуску!")
            self.finished.emit(self.final_java_path) # Сигнал об успешном завершении c путем к Java

        except Exception as e:
            print("Ошибка в потоке установщика:")
            traceback.print_exc()
            self.error.emit(f"{e}")

class CustomProgressBar(QProgressBar):
    """Прогресс-бар с кастомным стилем."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(12) # Чуть выше
        self.setTextVisible(True)
        self.setAlignment(Qt.AlignCenter)
        # Стили применяются глобально


# --- Поток для установки Fabric/Forge (временно отключен) ---
# class ModInstallerThread(QThread):
#     ...


# --- Точка входа ---

if __name__ == "__main__":
    # Настройка High DPI
    if hasattr(Qt, 'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    # Загрузка шрифта
    main_font = QFont("Arial", 10) # Запасной
    if os.path.exists(FONT_FILE):
        font_id = QFontDatabase.addApplicationFont(FONT_FILE)
        if font_id != -1:
            families = QFontDatabase.applicationFontFamilies(font_id)
            if families: main_font = QFont(families[0], 10)
    app.setFont(main_font) # Устанавливаем шрифт для всего приложения

    # Сплеш-скрин
    splash = AnimatedSplashScreen()
    splash_font = QFont(main_font); splash_font.setPointSize(36); splash_font.setWeight(QFont.Bold)
    # splash.setFont(splash_font) # Убираем установку шрифта, так как текст убран
    splash.show()
    splash.start_animation()

    # Отложенное создание главного окна
    main_window = None
    def create_main_window_and_finish_splash():
        global main_window
        if main_window is None: # Создаем только один раз
             try: # <<< Добавляем обработку ошибок
                 print("[Launcher] Создание NovaLauncher...") # <<< Лог
             main_window = NovaLauncher()
                 # --- Добавляем сюда инициализацию UI после создания окна ---
                 main_window.apply_styles()
                 main_window.load_minecraft_versions() # Загружаем версии в комбобокс
                 main_window.load_profiles_to_ui()
                 main_window.load_settings_to_ui()
                 main_window.update_profile_widget() # Обновляем виджет профиля
                 main_window.on_profile_selected() # Обновляем состояние UI

                 # Подключение сигналов навигации
                 main_window.home_button.clicked.connect(lambda: main_window.change_page(0))
                 main_window.profiles_button.clicked.connect(lambda: main_window.change_page(1))
                 main_window.settings_button.clicked.connect(lambda: main_window.change_page(2))
                 # -----------------------------------------------------------

                 print("[Launcher] NovaLauncher создан. Вызов splash.finish()...") # <<< Лог
             splash.finish(main_window) # Запускаем исчезновение и показ главного окна
                 print("[Launcher] splash.finish() вызван.") # <<< Лог
             except Exception as e:
                 print(f"[Launcher] КРИТИЧЕСКАЯ ОШИБКА при создании NovaLauncher: {e}")
                 import traceback
                 traceback.print_exc() # Выводим полный traceback
                 # Можно показать QMessageBox, но пока просто закроем
                 print("[Launcher] Закрытие приложения из-за ошибки...")
                 if splash: splash.close() # Закрываем сплеш, если он есть
                 app.quit()

    QTimer.singleShot(2000, create_main_window_and_finish_splash) # Показываем сплеш 2 сек

    sys.exit(app.exec()) 