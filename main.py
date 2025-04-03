import sys
import os
import minecraft_launcher_lib
import subprocess
import json
import uuid
import requests
from datetime import datetime
import threading
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QComboBox, QLabel, 
                             QLineEdit, QProgressBar, QMessageBox,
                             QStackedWidget, QFileDialog, QScrollArea, QListWidget, QDialog,
                             QFormLayout, QTabWidget, QCheckBox, QSystemTrayIcon, QMenu,
                             QListWidgetItem, QGroupBox, QSpinBox)
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPixmap, QPalette, QBrush, QAction
from PySide6.QtCore import (Qt, QThread, Signal, QTimer, QPoint, QPropertyAnimation, 
                           QEasingCurve, QParallelAnimationGroup, QAbstractAnimation)
from splash_screen import LoadingSplash
import time

class SidebarButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setMinimumHeight(50)
        self.setFont(parent.minecraft_font)
        self.setCursor(Qt.PointingHandCursor)

class MinecraftVersionInstaller(QThread):
    progress = Signal(int, str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, version, minecraft_directory):
        super().__init__()
        self.version = version
        self.minecraft_directory = minecraft_directory

    def run(self):
        try:
            def set_status(status: str):
                self.progress.emit(-1, status)

            def set_progress(value: int):
                self.progress.emit(value, "")

            minecraft_launcher_lib.install.install_minecraft_version(
                self.version, self.minecraft_directory,
                callback={"setStatus": set_status, "setProgress": set_progress}
            )
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class ProfileDialog(QDialog):
    def __init__(self, parent=None, profile_data=None):
        super().__init__(parent)
        self.setWindowTitle("Профиль")
        self.setMinimumWidth(400)
        
        layout = QFormLayout(self)
        
        self.name_input = QLineEdit(self)
        self.name_input.setFont(parent.minecraft_font)
        if profile_data:
            self.name_input.setText(profile_data.get("name", ""))
        
        self.username_input = QLineEdit(self)
        self.username_input.setFont(parent.minecraft_font)
        if profile_data:
            self.username_input.setText(profile_data.get("username", ""))
        
        layout.addRow("Имя профиля:", self.name_input)
        layout.addRow("Никнейм:", self.username_input)
        
        buttons = QHBoxLayout()
        save_button = QPushButton("Сохранить")
        save_button.setFont(parent.minecraft_font)
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Отмена")
        cancel_button.setFont(parent.minecraft_font)
        cancel_button.clicked.connect(self.reject)
        
        buttons.addWidget(save_button)
        buttons.addWidget(cancel_button)
        layout.addRow("", buttons)

    def get_profile_data(self):
        return {
            "name": self.name_input.text(),
            "username": self.username_input.text()
        }

class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки лаунчера")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Memory settings
        memory_group = QWidget()
        memory_layout = QFormLayout(memory_group)
        
        self.min_memory = QLineEdit(self)
        self.min_memory.setFont(parent.minecraft_font)
        self.min_memory.setText(str(settings.get("min_memory", 2048)))
        
        self.max_memory = QLineEdit(self)
        self.max_memory.setFont(parent.minecraft_font)
        self.max_memory.setText(str(settings.get("max_memory", 4096)))
        
        memory_layout.addRow("Минимальная память (МБ):", self.min_memory)
        memory_layout.addRow("Максимальная память (МБ):", self.max_memory)
        
        # Appearance settings
        appearance_group = QWidget()
        appearance_layout = QFormLayout(appearance_group)
        
        self.font_size = QLineEdit(self)
        self.font_size.setFont(parent.minecraft_font)
        self.font_size.setText(str(settings.get("font_size", 10)))
        
        appearance_layout.addRow("Размер шрифта:", self.font_size)
        
        # Advanced settings
        advanced_group = QWidget()
        advanced_layout = QFormLayout(advanced_group)
        
        self.auto_update = QComboBox(self)
        self.auto_update.setFont(parent.minecraft_font)
        self.auto_update.addItems(["Включено", "Выключено"])
        auto_update = settings.get("auto_update", "Включено")
        self.auto_update.setCurrentText(auto_update)
        
        self.close_launcher = QComboBox(self)
        self.close_launcher.setFont(parent.minecraft_font)
        self.close_launcher.addItems(["Да", "Нет"])
        close_launcher = settings.get("close_launcher", "Нет")
        self.close_launcher.setCurrentText(close_launcher)
        
        advanced_layout.addRow("Автообновление:", self.auto_update)
        advanced_layout.addRow("Закрывать лаунчер при запуске игры:", self.close_launcher)
        
        # Add groups to layout
        layout.addWidget(QLabel("Память"))
        layout.addWidget(memory_group)
        layout.addWidget(QLabel("Внешний вид"))
        layout.addWidget(appearance_group)
        layout.addWidget(QLabel("Дополнительно"))
        layout.addWidget(advanced_group)
        
        # Buttons
        buttons = QHBoxLayout()
        save_button = QPushButton("Сохранить")
        save_button.setFont(parent.minecraft_font)
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Отмена")
        cancel_button.setFont(parent.minecraft_font)
        cancel_button.clicked.connect(self.reject)
        
        buttons.addWidget(save_button)
        buttons.addWidget(cancel_button)
        layout.addLayout(buttons)

    def get_settings_data(self):
        try:
            min_memory = int(self.min_memory.text())
            max_memory = int(self.max_memory.text())
            font_size = int(self.font_size.text())
        except ValueError:
            QMessageBox.warning(self, "Ошибка", "Пожалуйста, введите корректные числовые значения")
            return None
        
        return {
            "min_memory": min_memory,
            "max_memory": max_memory,
            "font_size": font_size,
            "auto_update": self.auto_update.currentText(),
            "close_launcher": self.close_launcher.currentText()
        }

class UpdateChecker(QThread):
    update_available = Signal(str, str)
    
    def __init__(self, current_version):
        super().__init__()
        self.current_version = current_version
        
    def run(self):
        try:
            # Проверяем обновления с GitHub
            response = requests.get('https://api.github.com/repos/Artyom151/Nova-Launcher/releases/latest')
            if response.status_code == 200:
                latest_release = response.json()
                latest_version = latest_release['tag_name']
                
                # Сравниваем версии (простое строковое сравнение)
                if latest_version > self.current_version:
                    release_notes = latest_release['body']
                    download_url = latest_release['html_url']
                    self.update_available.emit(latest_version, download_url)
        except Exception:
            # Игнорируем ошибки при проверке обновлений
            pass

class MinecraftLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        # Устанавливаем версию лаунчера
        self.launcher_version = "1.4"
        
        # Изменяем пути файлов для использования кастомной директории
        self.nova_directory = os.path.join(os.path.expanduser("~"), ".nova_launcher")
        self.minecraft_directory = os.path.join(os.path.expanduser("~"), ".minecraft")
        
        # Создаем директории, если они не существуют
        if not os.path.exists(self.minecraft_directory):
            os.makedirs(self.minecraft_directory)
        if not os.path.exists(self.nova_directory):
            os.makedirs(self.nova_directory)
            
        # Настройка окна и базового стиля
        self.setWindowTitle("Nova Launcher")
        self.setMinimumSize(1200, 700)
        
        # Set window icon
        self.icon = QIcon(os.path.join("Resources", "rounded_logo_nova.png"))
        self.setWindowIcon(self.icon)
        
        # Установка фона в самом начале
        self.background_path = os.path.join("Resources", "minecraft_launcher.png")
        self.setup_permanent_background()
        
        # Load settings
        self.load_settings()
        
        # Load Minecraft font
        font_path = os.path.join("Resources", "minecraft-ten-font-cyrillic.ttf")
        font_id = QFontDatabase.addApplicationFont(font_path)
        if font_id != -1:
            font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
            self.minecraft_font = QFont(font_family, self.settings.get("font_size", 10))
        else:
            self.minecraft_font = QFont("Arial", self.settings.get("font_size", 10))

        # Load profiles first
        self.load_profiles()

        # Create profile combo
        self.profile_combo = QComboBox()
        self.profile_combo.setFont(self.minecraft_font)
        self.profile_combo.currentIndexChanged.connect(self.profile_changed)
        self.update_profile_combo()

        # Create main widget and layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QHBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Create and setup sidebar
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(200)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Create stacked widget for content
        self.content_stack = SmoothStackedWidget()
        self.content_stack.setSpeed(300)
        self.content_stack.setAnimation(QEasingCurve.OutCubic)
        self.content_stack.setWrap(False)
        
        # Create pages first
        self.play_page = self.create_play_page()
        self.versions_page = self.create_versions_page()
        self.skins_page = self.create_skins_page()
        self.news_page = self.create_news_page()
        self.settings_page = self.create_settings_page()
        self.social_page = self.create_social_page()

        # Add profile selector to sidebar
        profile_layout = QHBoxLayout()
        add_profile_button = QPushButton("+")
        add_profile_button.setFont(self.minecraft_font)
        add_profile_button.setFixedSize(30, 30)
        add_profile_button.clicked.connect(self.add_profile)
        profile_layout.addWidget(self.profile_combo)
        profile_layout.addWidget(add_profile_button)
        sidebar_layout.addLayout(profile_layout)

        # Add logo to sidebar
        logo_label = QLabel()
        logo_pixmap = QPixmap(os.path.join("Resources", "rounded_logo_nova.png"))
        logo_label.setPixmap(logo_pixmap.scaled(120, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(logo_label)
        sidebar_layout.addSpacing(20)
        
        # Create sidebar buttons
        self.sidebar_buttons = []
        pages = [
            ("ИГРАТЬ", self.play_page),
            ("УСТАНОВКИ", self.versions_page),
            ("СКИНЫ", self.skins_page),
            ("НОВОСТИ", self.news_page),
            ("НАСТРОЙКИ", self.settings_page),
            ("СООБЩЕСТВО", self.social_page)
        ]

        for i, (text, page) in enumerate(pages):
            button = SidebarButton(text, self)
            button.setObjectName("sidebarButton")
            button.clicked.connect(lambda checked, index=i: self.change_page(index))
            sidebar_layout.addWidget(button)
            self.sidebar_buttons.append(button)
            self.content_stack.addWidget(page)

        sidebar_layout.addStretch()
        
        # Add version info at bottom of sidebar
        version_label = QLabel("Nova Launcher 1.4")
        version_label.setFont(self.minecraft_font)
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setObjectName("versionLabel")
        sidebar_layout.addWidget(version_label)
        
        # Add widgets to main layout
        main_layout.addWidget(sidebar)
        main_layout.addWidget(self.content_stack)
        
        # Select first page by default
        self.sidebar_buttons[0].setChecked(True)
        self.content_stack.setCurrentIndex(0)
        
        # Set stylesheet
        self.apply_theme()
        
        # Создаем системный трей
        self.setup_system_tray()
        
        # Запускаем проверку обновлений
        self.check_for_updates()

    def setup_permanent_background(self):
        """Устанавливает постоянный фон, который не исчезнет при обновлении интерфейса"""
        if not os.path.exists(self.background_path):
            return
            
        # Устанавливаем фон через styleSheet для центрального виджета
        self.setStyleSheet(f"""
            QMainWindow {{
                background-image: url("{self.background_path.replace('\\', '/')}");
                background-position: center;
                background-repeat: no-repeat;
                background-attachment: fixed;
                background-color: #2C2C2C;
            }}
        """)
        
        # Добавляем атрибут для полупрозрачности
        self.setAttribute(Qt.WA_TranslucentBackground, False)
        
    def apply_theme(self):
        # Сохраняем базовые стили для фона
        background_style = f"""
            QMainWindow {{
                background-image: url("{self.background_path.replace('\\', '/')}");
                background-position: center;
                background-repeat: no-repeat;
                background-attachment: fixed;
                background-color: #2C2C2C;
            }}
        """
        
        # Добавляем остальные стили
        additional_styles = """
            #sidebar {
                background-color: rgba(21, 21, 21, 200);
                border-right: 1px solid rgba(255, 255, 255, 30);
            }
            #sidebarButton {
                background-color: transparent;
                border: none;
                color: white;
                text-align: left;
                padding: 10px 20px;
                font-size: 14px;
            }
            #sidebarButton:hover {
                background-color: rgba(255, 255, 255, 20);
            }
            #sidebarButton:checked {
                background-color: rgba(255, 255, 255, 30);
                border-left: 4px solid #43A047;
            }
            #versionLabel {
                color: rgba(255, 255, 255, 100);
                padding: 10px;
            }
            QWidget {
                color: white;
            }
            QLineEdit {
                background-color: rgba(45, 45, 45, 180);
                color: white;
                border: 1px solid rgba(61, 61, 61, 180);
                padding: 8px;
                border-radius: 4px;
            }
            QComboBox {
                background-color: rgba(45, 45, 45, 180);
                color: white;
                border: 1px solid rgba(61, 61, 61, 180);
                padding: 8px;
                border-radius: 4px;
                min-width: 200px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border: none;
            }
            QPushButton#playButton {
                background-color: #43A047;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 10px 20px;
                font-size: 16px;
            }
            QPushButton#playButton:hover {
                background-color: #2E7D32;
            }
            QProgressBar {
                border: 1px solid rgba(61, 61, 61, 180);
                border-radius: 4px;
                text-align: center;
                background-color: rgba(45, 45, 45, 180);
            }
            QProgressBar::chunk {
                background-color: #43A047;
            }
            QLabel {
                color: white;
            }
        """
        
        # Объединяем стили и устанавливаем
        self.setStyleSheet(background_style + additional_styles)

        # Добавляем profileInfo style
        self.setStyleSheet(self.styleSheet() + """
            QLabel#profileInfo {
                background-color: rgba(45, 45, 45, 180);
                padding: 15px;
                border-radius: 4px;
                font-size: 14px;
            }
        """)

    def create_settings_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Заголовок
        title_label = QLabel("Настройки лаунчера")
        title_label.setFont(self.minecraft_font)
        title_label.setStyleSheet("font-size: 18px;")
        layout.addWidget(title_label)
        
        # Создаем табы для разных типов настроек
        tabs = QTabWidget()
        tabs.setFont(self.minecraft_font)
        
        # ================ Таб для основных настроек ================
        basic_tab = QWidget()
        basic_layout = QVBoxLayout(basic_tab)
        
        # Группа для основных настроек
        basic_group = QWidget()
        basic_form = QFormLayout(basic_group)
        
        basic_layout.addWidget(basic_group)
        basic_layout.addStretch()
        
        # ================ Таб для настроек памяти ================
        memory_tab = QWidget()
        memory_layout = QVBoxLayout(memory_tab)
        
        memory_group = QWidget()
        memory_form_layout = QFormLayout(memory_group)
        
        self.min_memory_input = QLineEdit()
        self.min_memory_input.setFont(self.minecraft_font)
        self.min_memory_input.setText(str(self.settings.get("min_memory", 2048)))
        
        self.max_memory_input = QLineEdit()
        self.max_memory_input.setFont(self.minecraft_font)
        self.max_memory_input.setText(str(self.settings.get("max_memory", 4096)))
        
        memory_form_layout.addRow("Минимальная память (МБ):", self.min_memory_input)
        memory_form_layout.addRow("Максимальная память (МБ):", self.max_memory_input)
        
        memory_layout.addWidget(memory_group)
        memory_layout.addStretch()
        
        # ================ Таб для настроек версий ================
        versions_tab = QWidget()
        versions_layout = QVBoxLayout(versions_tab)
        
        versions_description = QLabel("Выбор версий временно недоступен из-за технических проблем.\nПриносим извинения за неудобства.")
        versions_description.setFont(self.minecraft_font)
        versions_description.setWordWrap(True)
        versions_description.setStyleSheet("color: #ff6b6b;")  # Красный цвет для уведомления
        versions_layout.addWidget(versions_description)
        
        # Чекбоксы для типов версий (отключенные)
        self.show_release_checkbox = QCheckBox("Релизы (стабильные версии)")
        self.show_release_checkbox.setFont(self.minecraft_font)
        self.show_release_checkbox.setChecked(self.settings.get("show_release", True))
        self.show_release_checkbox.setEnabled(False)
        
        self.show_snapshot_checkbox = QCheckBox("Snapshots (тестовые сборки)")
        self.show_snapshot_checkbox.setFont(self.minecraft_font)
        self.show_snapshot_checkbox.setChecked(self.settings.get("show_snapshot", False))
        self.show_snapshot_checkbox.setEnabled(False)
        
        self.show_beta_checkbox = QCheckBox("Beta (устаревшие бета-версии)")
        self.show_beta_checkbox.setFont(self.minecraft_font)
        self.show_beta_checkbox.setChecked(self.settings.get("show_beta", False))
        self.show_beta_checkbox.setEnabled(False)
        
        self.show_alpha_checkbox = QCheckBox("Alpha (устаревшие альфа-версии)")
        self.show_alpha_checkbox.setFont(self.minecraft_font)
        self.show_alpha_checkbox.setChecked(self.settings.get("show_alpha", False))
        self.show_alpha_checkbox.setEnabled(False)
        
        versions_layout.addWidget(self.show_release_checkbox)
        versions_layout.addWidget(self.show_snapshot_checkbox)
        versions_layout.addWidget(self.show_beta_checkbox)
        versions_layout.addWidget(self.show_alpha_checkbox)
        versions_layout.addStretch()
        
        # ================ Таб для настроек директорий ================
        dirs_tab = QWidget()
        dirs_layout = QVBoxLayout(dirs_tab)
        
        dirs_description = QLabel("Управление директориями:")
        dirs_description.setFont(self.minecraft_font)
        dirs_layout.addWidget(dirs_description)
        
        # Поле для выбора директории загрузки
        download_layout = QHBoxLayout()
        download_label = QLabel("Директория загрузок:")
        download_label.setFont(self.minecraft_font)
        
        self.download_location_input = QLineEdit()
        self.download_location_input.setFont(self.minecraft_font)
        self.download_location_input.setText(self.settings.get("download_location", self.minecraft_directory))
        
        browse_download_button = QPushButton("Обзор")
        browse_download_button.setFont(self.minecraft_font)
        browse_download_button.clicked.connect(self.browse_download_location)
        
        download_layout.addWidget(download_label)
        download_layout.addWidget(self.download_location_input)
        download_layout.addWidget(browse_download_button)
        
        # Поле для выбора пути к Java
        java_layout = QHBoxLayout()
        java_label = QLabel("Путь к Java:")
        java_label.setFont(self.minecraft_font)
        
        self.java_path_input = QLineEdit()
        self.java_path_input.setFont(self.minecraft_font)
        self.java_path_input.setText(self.settings.get("java_path", ""))
        self.java_path_input.setPlaceholderText("Оставьте пустым для автоматического выбора")
        
        browse_java_button = QPushButton("Обзор")
        browse_java_button.setFont(self.minecraft_font)
        browse_java_button.clicked.connect(self.browse_java_path)
        
        java_layout.addWidget(java_label)
        java_layout.addWidget(self.java_path_input)
        java_layout.addWidget(browse_java_button)
        
        dirs_layout.addLayout(download_layout)
        dirs_layout.addLayout(java_layout)
        dirs_layout.addStretch()
        
        # ================ Таб для дополнительных настроек ================
        advanced_tab = QWidget()
        advanced_layout = QVBoxLayout(advanced_tab)
        
        # Группа управления лаунчером
        launcher_group = QWidget()
        launcher_form = QFormLayout(launcher_group)
        
        # Чекбоксы для настроек трея и обновлений
        self.show_tray_checkbox = QCheckBox("Показывать значок в трее")
        self.show_tray_checkbox.setFont(self.minecraft_font)
        self.show_tray_checkbox.setChecked(self.settings.get("show_tray_icon", True))
        
        self.minimize_to_tray_checkbox = QCheckBox("Сворачивать в трей при закрытии")
        self.minimize_to_tray_checkbox.setFont(self.minecraft_font)
        self.minimize_to_tray_checkbox.setChecked(self.settings.get("minimize_to_tray", True))
        
        self.auto_check_updates_checkbox = QCheckBox("Автоматически проверять обновления")
        self.auto_check_updates_checkbox.setFont(self.minecraft_font)
        self.auto_check_updates_checkbox.setChecked(self.settings.get("auto_check_updates", True))
        
        # Комбобоксы для дополнительных настроек
        self.auto_update_combo = QComboBox()
        self.auto_update_combo.setFont(self.minecraft_font)
        self.auto_update_combo.addItems(["Включено", "Выключено"])
        self.auto_update_combo.setCurrentText(self.settings.get("auto_update", "Включено"))
        
        self.close_launcher_combo = QComboBox()
        self.close_launcher_combo.setFont(self.minecraft_font)
        self.close_launcher_combo.addItems(["Да", "Нет"])
        self.close_launcher_combo.setCurrentText(self.settings.get("close_launcher", "Нет"))
        
        # Поле для дополнительных аргументов Java
        self.additional_args_input = QLineEdit()
        self.additional_args_input.setFont(self.minecraft_font)
        self.additional_args_input.setText(self.settings.get("additional_arguments", ""))
        self.additional_args_input.setPlaceholderText("Например: -XX:+UseConcMarkSweepGC")
        
        # Добавляем элементы в форму
        launcher_form.addRow("Обновление Minecraft:", self.auto_update_combo)
        launcher_form.addRow("Закрывать лаунчер при запуске игры:", self.close_launcher_combo)
        advanced_layout.addWidget(launcher_group)
        advanced_layout.addWidget(self.show_tray_checkbox)
        advanced_layout.addWidget(self.minimize_to_tray_checkbox)
        advanced_layout.addWidget(self.auto_check_updates_checkbox)
        
        advanced_layout.addWidget(QLabel("Дополнительные аргументы Java:"))
        advanced_layout.addWidget(self.additional_args_input)
        advanced_layout.addStretch()
        
        # ================ Таб для управления данными ================
        data_tab = QWidget()
        data_layout = QVBoxLayout(data_tab)
        
        data_description = QLabel("Управление данными лаунчера:")
        data_description.setFont(self.minecraft_font)
        data_description.setWordWrap(True)
        data_layout.addWidget(data_description)
        
        # Кнопки для управления данными
        backup_button = QPushButton("Создать резервную копию")
        backup_button.setFont(self.minecraft_font)
        backup_button.clicked.connect(self.create_backup)
        
        restore_button = QPushButton("Восстановить из резервной копии")
        restore_button.setFont(self.minecraft_font)
        restore_button.clicked.connect(self.restore_from_backup)
        
        reset_button = QPushButton("Сбросить настройки лаунчера")
        reset_button.setFont(self.minecraft_font)
        reset_button.clicked.connect(self.reset_launcher_settings)
        
        data_layout.addWidget(backup_button)
        data_layout.addWidget(restore_button)
        data_layout.addWidget(reset_button)
        data_layout.addStretch()
        
        # Добавляем все табы
        tabs.addTab(basic_tab, "Основные")
        tabs.addTab(memory_tab, "Память")
        tabs.addTab(versions_tab, "Версии")
        tabs.addTab(dirs_tab, "Директории")
        tabs.addTab(advanced_tab, "Дополнительно")
        tabs.addTab(data_tab, "Данные")
        
        layout.addWidget(tabs)
        
        # Информация о текущих настройках
        self.settings_info = QLabel()
        self.settings_info.setFont(self.minecraft_font)
        self.settings_info.setObjectName("profileInfo")
        self.update_settings_info()
        layout.addWidget(self.settings_info)
        
        return page

    def animate_tab_change(self, tab_widget, new_index):
        current_widget = tab_widget.currentWidget()
        if not current_widget:
            return
            
        # Создаем анимацию прозрачности
        fade_out = QPropertyAnimation(current_widget, b"windowOpacity")
        fade_out.setDuration(150)
        fade_out.setStartValue(1.0)
        fade_out.setEndValue(0.0)
        fade_out.finished.connect(lambda: self.complete_tab_change(tab_widget, new_index))
        fade_out.start()
        
    def complete_tab_change(self, tab_widget, new_index):
        # Переключаем таб
        tab_widget.setCurrentIndex(new_index)
        current_widget = tab_widget.currentWidget()
        
        # Создаем анимацию появления
        fade_in = QPropertyAnimation(current_widget, b"windowOpacity")
        fade_in.setDuration(150)
        fade_in.setStartValue(0.0)
        fade_in.setEndValue(1.0)
        fade_in.start()

    def change_page(self, index):
        # Используем плавную анимацию
        self.content_stack.slideInIdx(index)
        
        # Обновляем состояние кнопок
        for i, button in enumerate(self.sidebar_buttons):
            button.setChecked(i == index)

    def open_profile_manager(self):
        dialog = ProfileManagerDialog(self)
        if dialog.exec():
            self.update_profile_combo()
            self.update_profile_info()

    def create_play_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Add current profile display
        profile_info = QLabel()
        profile_info.setFont(self.minecraft_font)
        profile_info.setObjectName("profileInfo")
        self.profile_info_label = profile_info  # Store reference for updates
        layout.addWidget(profile_info)
        
        # Add profile management button
        profile_buttons_layout = QHBoxLayout()
        manage_profiles_button = QPushButton("Управление профилями")
        manage_profiles_button.setFont(self.minecraft_font)
        manage_profiles_button.clicked.connect(self.open_profile_manager)
        profile_buttons_layout.addWidget(manage_profiles_button)
        profile_buttons_layout.addStretch()
        layout.addLayout(profile_buttons_layout)
        
        # Add spacer
        layout.addStretch()
        
        # Version selection
        version_layout = QHBoxLayout()
        version_label = QLabel("Версия:")
        version_label.setFont(self.minecraft_font)
        self.version_combo = QComboBox()
        self.version_combo.setFont(self.minecraft_font)
        self.update_versions()
        version_layout.addWidget(version_label)
        version_layout.addWidget(self.version_combo)
        version_layout.addStretch()
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_label = QLabel("")
        self.progress_label.setFont(self.minecraft_font)
        self.progress_label.setVisible(False)
        
        # Container for version selection and play button
        bottom_container = QWidget()
        bottom_layout = QVBoxLayout(bottom_container)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.setSpacing(20)
        
        # Add version selection to bottom
        bottom_layout.addLayout(version_layout)
        
        # Play button
        self.play_button = QPushButton("ИГРАТЬ")
        self.play_button.setObjectName("playButton")
        self.play_button.setFont(self.minecraft_font)
        self.play_button.setMinimumHeight(50)
        self.play_button.clicked.connect(self.launch_minecraft)
        bottom_layout.addWidget(self.play_button)
        
        # Add progress indicators
        bottom_layout.addWidget(self.progress_bar)
        bottom_layout.addWidget(self.progress_label)
        
        # Add bottom container to main layout
        layout.addWidget(bottom_container, alignment=Qt.AlignBottom)
        
        # Update profile info
        self.update_profile_info()
        
        return page
        
    def open_screenshots(self):
        """Открывает окно для просмотра скриншотов"""
        screenshots_dialog = ScreenshotsDialog(self)
        screenshots_dialog.exec()
        
    def create_versions_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Installed versions list
        versions_label = QLabel("Установленные версии")
        versions_label.setFont(self.minecraft_font)
        layout.addWidget(versions_label)
        
        self.versions_list = QListWidget()
        self.versions_list.setFont(self.minecraft_font)
        self.update_installed_versions()
        layout.addWidget(self.versions_list)
        
        # Version management buttons
        buttons_layout = QHBoxLayout()
        
        delete_button = QPushButton("Удалить")
        delete_button.setFont(self.minecraft_font)
        delete_button.clicked.connect(self.delete_version)
        
        refresh_button = QPushButton("Обновить")
        refresh_button.setFont(self.minecraft_font)
        refresh_button.clicked.connect(self.update_installed_versions)
        
        buttons_layout.addWidget(delete_button)
        buttons_layout.addWidget(refresh_button)
        buttons_layout.addStretch()
        
        layout.addLayout(buttons_layout)
        
        return page

    def create_skins_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Skin preview
        preview_label = QLabel("Текущий скин")
        preview_label.setFont(self.minecraft_font)
        layout.addWidget(preview_label)
        
        self.skin_preview = QLabel()
        self.skin_preview.setFixedSize(128, 256)
        self.skin_preview.setStyleSheet("background-color: rgba(45, 45, 45, 180); border-radius: 4px;")
        layout.addWidget(self.skin_preview)
        
        # Skin upload
        upload_button = QPushButton("Загрузить скин")
        upload_button.setFont(self.minecraft_font)
        upload_button.clicked.connect(self.upload_skin)
        upload_button.setObjectName("playButton")
        layout.addWidget(upload_button)
        
        layout.addStretch()
        return page

    def create_screenshots_page(self):
        """Creates the screenshots page"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)

        # Title
        title_label = QLabel("Скриншоты")
        title_label.setFont(self.minecraft_font)
        title_label.setStyleSheet("font-size: 18px;")
        layout.addWidget(title_label)
        
        # Screenshots list and preview
        content_layout = QHBoxLayout()
        
        # Left panel with file list
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        self.screenshots_list = QListWidget()
        self.screenshots_list.setFont(self.minecraft_font)
        self.screenshots_list.currentItemChanged.connect(self.screenshot_selected)
        
        refresh_button = QPushButton("Обновить")
        refresh_button.setFont(self.minecraft_font)
        refresh_button.clicked.connect(self.load_screenshots)
        
        open_folder_button = QPushButton("Открыть папку")
        open_folder_button.setFont(self.minecraft_font)
        open_folder_button.clicked.connect(self.open_screenshots_folder)
        
        left_layout.addWidget(QLabel("Доступные скриншоты:"))
        left_layout.addWidget(self.screenshots_list)
        left_layout.addWidget(refresh_button)
        left_layout.addWidget(open_folder_button)
        
        # Right panel with preview
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.screenshot_preview = QLabel("Выберите скриншот для предпросмотра")
        self.screenshot_preview.setAlignment(Qt.AlignCenter)
        self.screenshot_preview.setStyleSheet("background-color: rgba(45, 45, 45, 180); border-radius: 4px;")
        
        delete_button = QPushButton("Удалить")
        delete_button.setFont(self.minecraft_font)
        delete_button.clicked.connect(self.delete_screenshot)
        
        share_button = QPushButton("Сохранить копию")
        share_button.setFont(self.minecraft_font)
        share_button.clicked.connect(self.save_screenshot_copy)
        
        right_layout.addWidget(QLabel("Предпросмотр:"))
        right_layout.addWidget(self.screenshot_preview)
        
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(delete_button)
        buttons_layout.addWidget(share_button)
        right_layout.addLayout(buttons_layout)
        
        # Add panels to main layout
        content_layout.addWidget(left_panel, 1)  # 1/3 width
        content_layout.addWidget(right_panel, 2)  # 2/3 width
        
        layout.addLayout(content_layout)
        
        # Load screenshots
        self.load_screenshots()
        
        return page

    def screenshot_selected(self, current, previous):
        """Обрабатывает выбор скриншота"""
        if current is None:
            self.screenshot_preview.setText("Выберите скриншот для предпросмотра")
            return
            
        screenshot_path = os.path.join(self.minecraft_directory, "screenshots", current.text())
        
        if os.path.exists(screenshot_path):
            pixmap = QPixmap(screenshot_path)
            
            # Масштабируем изображение, чтобы оно поместилось в область предпросмотра
            preview_size = self.screenshot_preview.size()
            scaled_pixmap = pixmap.scaled(
                preview_size, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            
            self.screenshot_preview.setPixmap(scaled_pixmap)
        else:
            self.screenshot_preview.setText("Ошибка загрузки изображения")

    def load_screenshots(self):
        """Загружает список скриншотов"""
        self.screenshots_list.clear()
        
        screenshots_dir = os.path.join(self.minecraft_directory, "screenshots")
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)
            return
            
        # Получаем список файлов изображений
        image_extensions = ['.png', '.jpg', '.jpeg']
        screenshots = []
        
        for file in os.listdir(screenshots_dir):
            for ext in image_extensions:
                if file.lower().endswith(ext):
                    screenshots.append(file)
                    break
        
        # Сортируем по дате модификации (новые сверху)
        screenshots.sort(key=lambda x: os.path.getmtime(os.path.join(screenshots_dir, x)), reverse=True)
        
        # Добавляем в список
        for screenshot in screenshots:
            self.screenshots_list.addItem(screenshot)
            
        # Выбираем первый элемент, если он есть
        if self.screenshots_list.count() > 0:
            self.screenshots_list.setCurrentRow(0)
        else:
            self.screenshot_preview.setText("Нет доступных скриншотов")

    def open_screenshots_folder(self):
        """Открывает папку со скриншотами"""
        screenshots_dir = os.path.join(self.minecraft_directory, "screenshots")
        if not os.path.exists(screenshots_dir):
            os.makedirs(screenshots_dir)
            
        if os.path.exists(screenshots_dir):
            if sys.platform == 'win32':
                os.startfile(screenshots_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', screenshots_dir])
            else:
                subprocess.Popen(['xdg-open', screenshots_dir])
        else:
            QMessageBox.warning(self, "Ошибка", "Директория скриншотов не найдена")

    def delete_screenshot(self):
        """Удаляет выбранный скриншот"""
        current_item = self.screenshots_list.currentItem()
        if current_item is None:
            return
            
        screenshot_path = os.path.join(self.minecraft_directory, "screenshots", current_item.text())
        
        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить скриншот {current_item.text()}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                os.remove(screenshot_path)
                self.load_screenshots()  # Обновляем список
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить файл: {str(e)}")

    def save_screenshot_copy(self):
        """Сохраняет копию выбранного скриншота"""
        current_item = self.screenshots_list.currentItem()
        if current_item is None:
            return
            
        screenshot_path = os.path.join(self.minecraft_directory, "screenshots", current_item.text())
        
        if not os.path.exists(screenshot_path):
            QMessageBox.warning(self, "Ошибка", "Файл скриншота не найден")
            return
            
        # Запрашиваем место для сохранения копии
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить копию скриншота",
            current_item.text(),
            "PNG изображения (*.png);;JPEG изображения (*.jpg *.jpeg);;Все файлы (*.*)"
        )
        
        if not save_path:
            return
            
        try:
            import shutil
            shutil.copy2(screenshot_path, save_path)
            QMessageBox.information(self, "Успешно", f"Копия скриншота сохранена:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить копию: {str(e)}")

    def create_news_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Заголовок
        title_label = QLabel("Новости и обновления")
        title_label.setFont(self.minecraft_font)
        title_label.setStyleSheet("font-size: 18px;")
        layout.addWidget(title_label)
        
        # Добавляем прогресс-бар и метку для загрузки
        news_loading_label = QLabel("Загрузка новостей...")
        news_loading_label.setFont(self.minecraft_font)
        
        news_progress = QProgressBar()
        news_progress.setRange(0, 0)  # Бесконечный прогресс
        
        layout.addWidget(news_loading_label)
        layout.addWidget(news_progress)
        
        # Создаем контейнер для новостей
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        self.news_widget = QWidget()
        self.news_layout = QVBoxLayout(self.news_widget)
        
        # Добавляем пустой виджет для растяжения в конце списка новостей
        self.news_layout.addStretch()
        
        scroll_area.setWidget(self.news_widget)
        layout.addWidget(scroll_area)
        
        # Скрываем скролл-область до загрузки новостей
        scroll_area.setVisible(False)
        
        # Кнопка обновления
        refresh_button = QPushButton("Обновить новости")
        refresh_button.setFont(self.minecraft_font)
        refresh_button.clicked.connect(self.refresh_news)
        layout.addWidget(refresh_button)
        
        # Сохраняем ссылки на элементы для обновления
        self.news_scroll_area = scroll_area
        self.news_loading_label = news_loading_label
        self.news_progress = news_progress
        
        # Загружаем новости
        self.refresh_news()
        
        return page
        
    def refresh_news(self):
        """Обновляет новости"""
        # Показываем индикатор загрузки
        self.news_scroll_area.setVisible(False)
        self.news_loading_label.setVisible(True)
        self.news_progress.setVisible(True)
        
        # Очищаем старые новости
        for i in reversed(range(self.news_layout.count())):
            item = self.news_layout.itemAt(i)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
        
        # Добавляем растяжку обратно
        self.news_layout.addStretch()
        
        # Запускаем загрузку новостей в отдельном потоке
        self.news_thread = MinecraftNewsThread()
        self.news_thread.news_loaded.connect(self.display_news)
        self.news_thread.error.connect(self.show_news_error)
        self.news_thread.start()
        
    def display_news(self, news_items):
        """Отображает загруженные новости"""
        # Убираем индикатор загрузки
        self.news_loading_label.setVisible(False)
        self.news_progress.setVisible(False)
        
        # Очищаем старые новости и растяжку
        for i in reversed(range(self.news_layout.count())):
            item = self.news_layout.itemAt(i)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    # Удаляем растяжку
                    self.news_layout.removeItem(item)
        
        # Добавляем новые новости
        for title, desc in news_items:
            news_item = QWidget()
            news_item.setObjectName("newsItem")
            item_layout = QVBoxLayout(news_item)
            
            title_label = QLabel(title)
            title_label.setFont(self.minecraft_font)
            title_label.setStyleSheet("font-weight: bold;")
            
            desc_label = QLabel(desc)
            desc_label.setWordWrap(True)
            desc_label.setStyleSheet("color: rgba(255, 255, 255, 200);")
            
            item_layout.addWidget(title_label)
            item_layout.addWidget(desc_label)
            
            # Добавляем стили для новостных элементов
            news_item.setStyleSheet("""
                #newsItem {
                    background-color: rgba(45, 45, 45, 180);
                    border-radius: 4px;
                    margin-bottom: 10px;
                    padding: 10px;
                }
            """)
            
            self.news_layout.addWidget(news_item)
        
        # Добавляем растяжку в конце
        self.news_layout.addStretch()
        
        # Показываем новости
        self.news_scroll_area.setVisible(True)
        
    def show_news_error(self, error_message):
        """Обрабатывает ошибки при загрузке новостей"""
        # Показываем скрытое сообщение для отладки в консоли
        print(f"Ошибка загрузки новостей: {error_message}")
        
        # Продолжаем показывать интерфейс
        self.news_loading_label.setVisible(False)
        self.news_progress.setVisible(False)
        self.news_scroll_area.setVisible(True)

    def create_social_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        
        # Заголовок
        title_label = QLabel("Сообщество")
        title_label.setFont(self.minecraft_font)
        title_label.setStyleSheet("font-size: 18px;")
        layout.addWidget(title_label)
        
        # Описание
        description = QLabel("Присоединяйтесь к нашему сообществу и следите за обновлениями:")
        description.setFont(self.minecraft_font)
        description.setWordWrap(True)
        layout.addWidget(description)
        
        layout.addSpacing(20)
        
        # Telegram
        telegram_container = QWidget()
        telegram_container.setObjectName("socialContainer")
        telegram_layout = QHBoxLayout(telegram_container)
        
        telegram_icon = QLabel()
        telegram_icon_path = os.path.join("Resources", "telegram_icon.png")
        
        telegram_pixmap = QPixmap(telegram_icon_path)
        telegram_icon.setPixmap(telegram_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            
        telegram_link = QLabel("<a href='https://t.me/novadev_hub' style='color: white; text-decoration: none;'>Telegram канал: @novadev_hub</a>")
        telegram_link.setFont(self.minecraft_font)
        telegram_link.setOpenExternalLinks(True)
        
        telegram_layout.addWidget(telegram_icon)
        telegram_layout.addWidget(telegram_link)
        telegram_layout.addStretch()
        
        # Discord
        discord_container = QWidget()
        discord_container.setObjectName("socialContainer")
        discord_layout = QHBoxLayout(discord_container)
        
        discord_icon = QLabel()
        discord_icon_path = os.path.join("Resources", "discord_icon.png")
        
        discord_pixmap = QPixmap(discord_icon_path)
        discord_icon.setPixmap(discord_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            
        discord_link = QLabel("<a href='https://discord.gg/ts3uN93cu9' style='color: white; text-decoration: none;'>Discord сервер: Nova Hub</a>")
        discord_link.setFont(self.minecraft_font)
        discord_link.setOpenExternalLinks(True)
        
        discord_layout.addWidget(discord_icon)
        discord_layout.addWidget(discord_link)
        discord_layout.addStretch()
        
        # GitHub
        github_container = QWidget()
        github_container.setObjectName("socialContainer")
        github_layout = QHBoxLayout(github_container)
        
        github_icon = QLabel()
        github_icon_path = os.path.join("Resources", "github_icon.png")
        
        github_pixmap = QPixmap(github_icon_path)
        github_icon.setPixmap(github_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            
        github_link = QLabel("<a href='https://github.com/Artyom151' style='color: white; text-decoration: none;'>GitHub: Artyom151</a>")
        github_link.setFont(self.minecraft_font)
        github_link.setOpenExternalLinks(True)
        
        github_layout.addWidget(github_icon)
        github_layout.addWidget(github_link)
        github_layout.addStretch()
        
        # Добавляем контейнеры на страницу
        layout.addWidget(telegram_container)
        layout.addSpacing(10)
        layout.addWidget(discord_container)
        layout.addSpacing(10)
        layout.addWidget(github_container)
        
        # Стили для контейнеров социальных сетей
        social_container_style = """
            #socialContainer {
                background-color: rgba(45, 45, 45, 180);
                border-radius: 4px;
                padding: 10px;
            }
        """
        
        telegram_container.setStyleSheet(social_container_style)
        discord_container.setStyleSheet(social_container_style)
        github_container.setStyleSheet(social_container_style)
        
        layout.addStretch()
        return page

    def update_versions(self):
        try:
            # Safely disconnect the signal if it exists
            try:
                if self.version_combo.receivers(self.version_combo.currentTextChanged) > 0:
                    self.version_combo.currentTextChanged.disconnect()
            except:
                pass

            self.version_combo.clear()
            versions_to_show = []
            
            try:
                # Получаем полный список версий
                version_list = minecraft_launcher_lib.utils.get_version_list()
                
                # Фильтруем версии согласно настройкам
                for version in version_list:
                    version_type = version.get("type", "")
                    
                    if version_type == "release" and self.settings.get("show_release", True):
                        versions_to_show.append(version)
                    elif version_type == "snapshot" and self.settings.get("show_snapshot", False):
                        versions_to_show.append(version)
                    elif version_type == "old_beta" and self.settings.get("show_beta", False):
                        versions_to_show.append(version)
                    elif version_type == "old_alpha" and self.settings.get("show_alpha", False):
                        versions_to_show.append(version)
                
                # Сортируем версии по дате выхода (новые сверху)
                versions_to_show.sort(key=lambda x: x.get("releaseTime", ""), reverse=True)
                
                # Если после фильтрации список пуст, показываем хотя бы релизы
                if not versions_to_show and not self.settings.get("show_release", True):
                    self.settings["show_release"] = True
                    self.save_settings()
                    for version in version_list:
                        if version.get("type", "") == "release":
                            versions_to_show.append(version)
                    versions_to_show.sort(key=lambda x: x.get("releaseTime", ""), reverse=True)
                
                # Добавляем версии в комбобокс
                for version in versions_to_show:
                    self.version_combo.addItem(version["id"])
                    
            except Exception as e:
                print(f"Ошибка при получении онлайн-списка версий: {str(e)}")
                # В случае ошибки получения онлайн-списка, используем установленные версии
                installed_versions = minecraft_launcher_lib.utils.get_installed_versions(self.minecraft_directory)
                for version in installed_versions:
                    self.version_combo.addItem(version["id"])
            
            # Если список все еще пуст, добавляем базовые версии
            if self.version_combo.count() == 0:
                default_versions = ["1.20.4", "1.20.2", "1.20.1", "1.19.4", "1.19.3", "1.19.2", "1.18.2"]
                for version in default_versions:
                    self.version_combo.addItem(version)
            
            # Восстанавливаем последнюю использованную версию
            last_version = self.settings.get("last_version", "")
            if last_version:
                index = self.version_combo.findText(last_version)
                if index >= 0:
                    self.version_combo.setCurrentIndex(index)
                    
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось обновить список версий: {str(e)}\n"
                "Будут использованы базовые версии."
            )
            # В случае критической ошибки добавляем базовые версии
            default_versions = ["1.20.4", "1.20.2", "1.20.1", "1.19.4", "1.19.3", "1.19.2", "1.18.2"]
            for version in default_versions:
                self.version_combo.addItem(version)
                
        # Подключаем сигнал изменения версии
        try:
            self.version_combo.currentTextChanged.disconnect()
        except:
            pass
        self.version_combo.currentTextChanged.connect(self.version_changed)

    def version_changed(self, version_text):
        """Сохраняет выбранную версию Minecraft"""
        if version_text:
            self.settings["last_version"] = version_text
            self.save_settings()

    def launch_minecraft(self):
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.play_button.setEnabled(True)

        selected_version = self.version_combo.currentText()
        current_profile = self.profiles[self.profile_combo.currentIndex()]
        username = current_profile["username"]

        # Проверка наличия версии
        try:
            # Получаем список установленных версий
            installed_versions = minecraft_launcher_lib.utils.get_installed_versions(self.minecraft_directory)
            installed_version_ids = [version["id"] for version in installed_versions]
            
            # Если версия не установлена, сначала устанавливаем её
            if selected_version not in installed_version_ids:
                reply = QMessageBox.question(
                    self,
                    "Версия не установлена",
                    f"Версия {selected_version} не установлена. Установить её сейчас?",
                    QMessageBox.Yes | QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    self.progress_bar.setVisible(True)
                    self.progress_label.setVisible(True)
                    self.play_button.setEnabled(False)
                    
                    # Install version
                    self.installer = MinecraftVersionInstaller(selected_version, self.minecraft_directory)
                    self.installer.progress.connect(self.update_progress)
                    self.installer.finished.connect(lambda: self.finish_minecraft_launch(selected_version, username))
                    self.installer.error.connect(self.show_error)
                    self.installer.start()
                    return
                else:
                    return
            
            # Если версия установлена, продолжаем запуск
            self.finish_minecraft_launch(selected_version, username)
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось проверить версию: {str(e)}"
            )
            
    def finish_minecraft_launch(self, selected_version, username):
        min_memory = self.settings.get("min_memory", 2048)
        max_memory = self.settings.get("max_memory", 4096)
        
        # Генерация UUID на основе имени пользователя
        player_uuid = str(uuid.uuid3(uuid.NAMESPACE_OID, username))
        
        # Базовые JVM аргументы
        jvm_arguments = [
            f"-Xms{min_memory}M",
            f"-Xmx{max_memory}M"
        ]
        
        # Добавляем дополнительные аргументы, если они указаны
        additional_args = self.settings.get("additional_arguments", "")
        if additional_args:
            jvm_arguments.extend(additional_args.split())
        
        options = {
            "username": username,
            "uuid": player_uuid,
            "token": "",
            "jvmArguments": jvm_arguments,
            "customResolution": False
        }
        
        # Если указан пользовательский путь к Java, добавляем его в опции
        java_path = self.settings.get("java_path", "")
        if java_path and os.path.exists(java_path):
            options["javaPath"] = java_path

        try:
            # Используем директорию для игры из настроек
            minecraft_directory = self.settings.get("download_location", self.minecraft_directory)
            
            # Получаем команду для запуска
            minecraft_command = minecraft_launcher_lib.command.get_minecraft_command(
                selected_version,
                minecraft_directory,
                options
            )

            # Запускаем Minecraft в отдельном процессе
            process = subprocess.Popen(minecraft_command)
            
            # Сохраняем PID процесса для возможного отслеживания
            self.minecraft_process_pid = process.pid
            
            # Показываем уведомление в трее, если включен
            if hasattr(self, "tray_icon") and self.tray_icon.isVisible():
                self.tray_icon.showMessage(
                    "Minecraft запущен",
                    f"Minecraft {selected_version} запущен успешно",
                    QSystemTrayIcon.Information,
                    2000
                )
            
            # Закрыть лаунчер, если выбрано в настройках
            if self.settings.get("close_launcher", "Нет") == "Да":
                self.close()
        except minecraft_launcher_lib.exceptions.VersionNotFound:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Версия {selected_version} не найдена в директории Minecraft."
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось запустить Minecraft: {str(e)}"
            )
            
    def update_progress(self, value: int, status: str):
        if value >= 0:
            self.progress_bar.setValue(value)
        if status:
            self.progress_label.setText(status)
    
    def show_error(self, error: str):
        QMessageBox.critical(self, "Ошибка", f"Ошибка при установке: {error}")
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.play_button.setEnabled(True)

    def load_profiles(self):
        try:
            self.profiles = []
            profiles_file = os.path.join(self.nova_directory, "profiles.json")
            if os.path.exists(profiles_file):
                with open(profiles_file, "r", encoding='utf-8') as f:
                    self.profiles = json.load(f)
            if not self.profiles:
                self.profiles = [{"name": "Default", "username": "Player"}]
                self.save_profiles()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить профили: {str(e)}")
            self.profiles = [{"name": "Default", "username": "Player"}]

    def save_profiles(self):
        try:
            # Убедимся, что директория существует
            if not os.path.exists(self.nova_directory):
                os.makedirs(self.nova_directory)
                
            profiles_file = os.path.join(self.nova_directory, "profiles.json")
            with open(profiles_file, "w", encoding='utf-8') as f:
                json.dump(self.profiles, f, ensure_ascii=False, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить профили: {str(e)}")

    def update_profile_combo(self):
        self.profile_combo.clear()
        for profile in self.profiles:
            self.profile_combo.addItem(profile["name"])
            if "icon" in profile and profile["icon"]:
                icon_path = os.path.join(self.nova_directory, "profile_icons", profile["icon"])
                if os.path.exists(icon_path):
                    icon = QIcon(icon_path)
                    self.profile_combo.setItemIcon(self.profile_combo.count() - 1, icon)
            
        # Устанавливаем последний использованный профиль, если он сохранен
        last_profile_index = self.settings.get("last_profile_index", 0)
        if 0 <= last_profile_index < len(self.profiles):
            self.profile_combo.setCurrentIndex(last_profile_index)

    def profile_changed(self, index):
        if index >= 0:
            self.update_profile_info()
            # Сохраняем текущий индекс профиля
            self.settings["last_profile_index"] = index
            self.save_settings()

    def update_profile_info(self):
        if hasattr(self, 'profile_info_label') and self.profile_combo.currentIndex() >= 0:
            current_profile = self.profiles[self.profile_combo.currentIndex()]
            info_text = f"Текущий профиль: {current_profile['name']}\nИгрок: {current_profile['username']}"
            
            # Добавляем иконку профиля, если она есть
            if "icon" in current_profile and current_profile["icon"]:
                icon_path = os.path.join(self.nova_directory, "profile_icons", current_profile["icon"])
                if os.path.exists(icon_path):
                    pixmap = QPixmap(icon_path)
                    self.profile_info_label.setPixmap(pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                    self.profile_info_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                    info_text = f"  {info_text}"  # Добавляем отступ для иконки
            
            self.profile_info_label.setText(info_text)

    def add_profile(self):
        dialog = ProfileDialog(self)
        if dialog.exec():
            try:
                profile_data = dialog.get_profile_data()
                self.profiles.append(profile_data)
                self.save_profiles()
                self.update_profile_combo()
                self.profile_combo.setCurrentIndex(len(self.profiles) - 1)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось добавить профиль: {str(e)}")

    def update_installed_versions(self):
        self.versions_list.clear()
        versions_dir = os.path.join(self.minecraft_directory, "versions")
        if os.path.exists(versions_dir):
            for version in os.listdir(versions_dir):
                if os.path.isdir(os.path.join(versions_dir, version)):
                    self.versions_list.addItem(version)

    def delete_version(self):
        current_item = self.versions_list.currentItem()
        if current_item:
            version = current_item.text()
            reply = QMessageBox.question(
                self,
                "Подтверждение",
                f"Вы уверены, что хотите удалить версию {version}?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.Yes:
                version_dir = os.path.join(self.minecraft_directory, "versions", version)
                try:
                    import shutil
                    shutil.rmtree(version_dir)
                    self.update_installed_versions()
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось удалить версию: {str(e)}")

    def upload_skin(self):
        file_dialog = QFileDialog()
        skin_path, _ = file_dialog.getOpenFileName(
            self,
            "Выберите скин",
            "",
            "PNG Files (*.png)"
        )
        if skin_path:
            # Load and display skin preview
            skin_pixmap = QPixmap(skin_path)
            if skin_pixmap.width() == 64 and skin_pixmap.height() == 64:
                self.skin_preview.setPixmap(skin_pixmap.scaled(
                    self.skin_preview.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                ))
            else:
                QMessageBox.warning(self, "Ошибка", "Неверный размер скина. Требуется 64x64 пикселей.")

    def update_settings_info(self):
        if hasattr(self, 'settings_info'):
            # Определяем отображаемые типы версий
            version_types = []
            if self.settings.get('show_release', True):
                version_types.append("Релизы")
            if self.settings.get('show_snapshot', False):
                version_types.append("Snapshots")
            if self.settings.get('show_beta', False):
                version_types.append("Beta")
            if self.settings.get('show_alpha', False):
                version_types.append("Alpha")
            
            version_types_str = ", ".join(version_types)
            
            # Форматируем информацию о последней проверке обновлений
            last_check = self.settings.get('last_update_check', "")
            last_check_info = "Никогда" if not last_check else last_check
            
            info_text = f"""
Память:
- Минимальная: {self.settings.get('min_memory', 2048)} МБ
- Максимальная: {self.settings.get('max_memory', 4096)} МБ

Версии:
- Отображаемые типы: {version_types_str}

Директории:
- Загрузка: {os.path.basename(self.settings.get('download_location', self.minecraft_directory))}
- Java: {"По умолчанию" if not self.settings.get('java_path', "") else "Пользовательская"}

Дополнительно:
- Автообновление: {self.settings.get('auto_update', 'Включено')}
- Закрывать лаунчер при запуске: {self.settings.get('close_launcher', 'Нет')}
- Значок в трее: {"Включен" if self.settings.get('show_tray_icon', True) else "Выключен"}
- Последняя проверка обновлений: {last_check_info}
            """
            self.settings_info.setText(info_text.strip())

    def save_versions_settings(self):
        try:
            self.settings["show_release"] = self.show_release_checkbox.isChecked()
            self.settings["show_snapshot"] = self.show_snapshot_checkbox.isChecked()
            self.settings["show_beta"] = self.show_beta_checkbox.isChecked()
            self.settings["show_alpha"] = self.show_alpha_checkbox.isChecked()
            
            # Если ничего не выбрано, включаем хотя бы релизы
            if not any([self.settings["show_release"], 
                       self.settings["show_snapshot"], 
                       self.settings["show_beta"], 
                       self.settings["show_alpha"]]):
                self.settings["show_release"] = True
                self.show_release_checkbox.setChecked(True)
                QMessageBox.warning(self, "Предупреждение", 
                                  "Должен быть выбран хотя бы один тип версий. Релизы включены автоматически.")
            
            # Сохраняем настройки
            self.save_settings()
            self.update_settings_info()
            
            # Запоминаем текущую версию
            current_version = self.version_combo.currentText()
            
            # Обновляем список версий с новыми настройками
            self.update_versions()
            
            # Пытаемся восстановить выбранную версию
            if current_version:
                index = self.version_combo.findText(current_version)
                if index >= 0:
                    self.version_combo.setCurrentIndex(index)
            
            QMessageBox.information(self, "Успешно", "Настройки версий сохранены")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить настройки версий: {str(e)}")

    def setup_system_tray(self):
        """Настройка значка в системном трее"""
        self.tray_icon = QSystemTrayIcon(self.icon, self)
        
        # Создаем контекстное меню
        tray_menu = QMenu()
        
        open_action = QAction("Открыть лаунчер", self)
        open_action.triggered.connect(self.show)
        
        exit_action = QAction("Выход", self)
        exit_action.triggered.connect(self.close)
        
        tray_menu.addAction(open_action)
        tray_menu.addSeparator()
        tray_menu.addAction(exit_action)
        
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.tray_icon_activated)
        
        # Показываем иконку, если включено в настройках
        if self.settings.get("show_tray_icon", True):
            self.tray_icon.show()
    
    def tray_icon_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isHidden():
                self.show()
            else:
                self.hide()
                
    def check_for_updates(self):
        """Проверяет наличие обновлений лаунчера"""
        if self.settings.get("auto_update", "Включено") == "Включено":
            # Запускаем проверку в отдельном потоке
            self.update_checker = UpdateChecker(self.launcher_version)
            self.update_checker.update_available.connect(self.show_update_notification)
            self.update_checker.start()
            
    def show_update_notification(self, new_version, download_url):
        """Показывает уведомление о доступном обновлении"""
        reply = QMessageBox.question(
            self,
            "Доступно обновление",
            f"Доступна новая версия лаунчера: {new_version}\n\nХотите перейти на страницу загрузки?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # Открываем браузер со страницей загрузки
            import webbrowser
            webbrowser.open(download_url)
            
    def closeEvent(self, event):
        """Обрабатывает закрытие окна"""
        if self.settings.get("minimize_to_tray", True) and self.settings.get("show_tray_icon", True):
            event.ignore()
            self.hide()
            
            # Показываем уведомление
            self.tray_icon.showMessage(
                "Nova Launcher",
                "Лаунчер продолжает работать в фоновом режиме",
                QSystemTrayIcon.Information,
                2000
            )
        else:
            event.accept()

    def browse_download_location(self):
        """Выбор директории для загрузки Minecraft"""
        dir_path = QFileDialog.getExistingDirectory(
            self, 
            "Выберите директорию для загрузки Minecraft",
            self.download_location_input.text()
        )
        if dir_path:
            self.download_location_input.setText(dir_path)
            
    def browse_java_path(self):
        """Выбор пути к Java"""
        file_filter = ""
        if sys.platform == "win32":
            file_filter = "Java Executable (javaw.exe)"
        else:
            file_filter = "Java Executable (java)"
            
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите исполняемый файл Java",
            "",
            file_filter
        )
        if file_path:
            self.java_path_input.setText(file_path)
            
    def save_dirs_settings(self):
        """Сохранение настроек директорий"""
        try:
            download_location = self.download_location_input.text()
            if not os.path.exists(download_location):
                reply = QMessageBox.question(
                    self,
                    "Директория не существует",
                    "Указанная директория не существует. Создать её?",
                    QMessageBox.Yes | QMessageBox.No
                )
                if reply == QMessageBox.Yes:
                    os.makedirs(download_location)
                else:
                    return
                    
            # Сохраняем настройки
            self.settings["download_location"] = download_location
            self.settings["java_path"] = self.java_path_input.text()
            
            self.save_settings()
            self.update_settings_info()
            
            QMessageBox.information(self, "Успешно", "Настройки директорий сохранены")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить настройки: {str(e)}")
            
    def save_advanced_settings(self):
        """Сохранение дополнительных настроек"""
        try:
            self.settings["show_tray_icon"] = self.show_tray_checkbox.isChecked()
            self.settings["minimize_to_tray"] = self.minimize_to_tray_checkbox.isChecked()
            self.settings["auto_check_updates"] = self.auto_check_updates_checkbox.isChecked()
            self.settings["auto_update"] = self.auto_update_combo.currentText()
            self.settings["close_launcher"] = self.close_launcher_combo.currentText()
            self.settings["additional_arguments"] = self.additional_args_input.text()
            
            self.save_settings()
            self.update_settings_info()
            
            # Обновляем состояние трея
            if hasattr(self, "tray_icon"):
                if self.settings["show_tray_icon"]:
                    self.tray_icon.show()
                else:
                    self.tray_icon.hide()
            
            QMessageBox.information(self, "Успешно", "Дополнительные настройки сохранены")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить настройки: {str(e)}")
            
    def manual_check_updates(self):
        """Ручная проверка обновлений"""
        self.progress_bar.setVisible(True)
        self.progress_label.setVisible(True)
        self.progress_label.setText("Проверка обновлений...")
        self.progress_bar.setRange(0, 0)  # Индикатор без процентов
        
        # Запускаем проверку в отдельном потоке
        self.update_checker = UpdateChecker(self.launcher_version)
        self.update_checker.update_available.connect(self.handle_manual_update_check)
        self.update_checker.finished.connect(self.finish_update_check)
        self.update_checker.start()
    
    def handle_manual_update_check(self, new_version, download_url):
        """Обработка результатов ручной проверки обновлений"""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        
        # Обновляем время последней проверки
        self.settings["last_update_check"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_settings()
        
        # Показываем сообщение о результате
        self.show_update_notification(new_version, download_url)
        
    def finish_update_check(self):
        """Завершение проверки обновлений"""
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        
        # Обновляем время последней проверки
        self.settings["last_update_check"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.save_settings()
        self.update_settings_info()
        
        # Если не было сигнала о наличии обновлений, значит обновлений нет
        if not hasattr(self, "_update_found") or not self._update_found:
            QMessageBox.information(self, "Проверка обновлений", "У вас установлена последняя версия лаунчера.")

    def create_backup(self):
        """Создает резервную копию настроек и профилей лаунчера"""
        try:
            import zipfile
            import datetime
            
            # Создаем имя для архива с текущей датой и временем
            now = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            backup_filename = f"nova_launcher_backup_{now}.zip"
            
            # Спрашиваем пользователя, куда сохранить бэкап
            backup_path, _ = QFileDialog.getSaveFileName(
                self,
                "Сохранить резервную копию",
                backup_filename,
                "ZIP архивы (*.zip)"
            )
            
            if not backup_path:
                return
                
            # Создаем ZIP архив
            with zipfile.ZipFile(backup_path, 'w') as backup_zip:
                # Добавляем файлы настроек и профилей
                settings_file = os.path.join(self.nova_directory, "launcher_settings.json")
                profiles_file = os.path.join(self.nova_directory, "profiles.json")
                
                if os.path.exists(settings_file):
                    backup_zip.write(settings_file, os.path.basename(settings_file))
                
                if os.path.exists(profiles_file):
                    backup_zip.write(profiles_file, os.path.basename(profiles_file))
            
            QMessageBox.information(
                self,
                "Резервное копирование",
                f"Резервная копия успешно создана:\n{backup_path}"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось создать резервную копию: {str(e)}"
            )
    
    def restore_from_backup(self):
        """Восстанавливает настройки и профили из резервной копии"""
        try:
            import zipfile
            
            # Спрашиваем пользователя, откуда восстановить бэкап
            backup_path, _ = QFileDialog.getOpenFileName(
                self,
                "Открыть резервную копию",
                "",
                "ZIP архивы (*.zip)"
            )
            
            if not backup_path or not os.path.exists(backup_path):
                return
                
            # Проверяем архив на корректность
            try:
                with zipfile.ZipFile(backup_path, 'r') as backup_zip:
                    file_list = backup_zip.namelist()
                    
                    # Проверяем наличие необходимых файлов
                    if "launcher_settings.json" not in file_list and "profiles.json" not in file_list:
                        QMessageBox.warning(
                            self,
                            "Ошибка",
                            "Выбранный архив не содержит данных лаунчера"
                        )
                        return
                        
                    # Спрашиваем подтверждение
                    reply = QMessageBox.question(
                        self,
                        "Подтверждение восстановления",
                        "Текущие настройки и профили будут заменены данными из резервной копии. Продолжить?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    
                    if reply == QMessageBox.No:
                        return
                        
                    # Распаковываем файлы
                    backup_zip.extractall(self.nova_directory)
            
            except zipfile.BadZipFile:
                QMessageBox.critical(
                    self,
                    "Ошибка",
                    "Выбранный файл не является корректным ZIP архивом"
                )
                return
                
            # Перезагружаем настройки и профили
            self.load_settings()
            self.load_profiles()
            self.update_profile_combo()
            self.update_profile_info()
            self.update_settings_info()
            
            QMessageBox.information(
                self,
                "Восстановление",
                "Данные лаунчера успешно восстановлены из резервной копии"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось восстановить данные: {str(e)}"
            )
    
    def reset_launcher_settings(self):
        """Сбрасывает настройки лаунчера на значения по умолчанию"""
        reply = QMessageBox.question(
            self,
            "Подтверждение сброса",
            "Вы уверены, что хотите сбросить все настройки лаунчера на значения по умолчанию?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.No:
            return
            
        try:
            # Сохраняем текущие профили
            current_profiles = self.profiles.copy()
            
            # Создаем настройки по умолчанию
            self.settings = {
                "min_memory": 2048,
                "max_memory": 4096,
                "font_size": 10,
                "auto_update": "Включено",
                "close_launcher": "Нет",
                "show_release": True,
                "show_snapshot": False,
                "show_beta": False,
                "show_alpha": False,
                "show_tray_icon": True,
                "minimize_to_tray": True,
                "auto_check_updates": True,
                "download_location": self.minecraft_directory,
                "java_path": "",
                "additional_arguments": "",
                "last_update_check": "",
                "last_profile_index": 0,
                "last_version": ""
            }
            
            # Сохраняем настройки по умолчанию
            self.save_settings()
            
            # Восстанавливаем профили
            self.profiles = current_profiles
            self.save_profiles()
            
            # Обновляем интерфейс
            self.update_settings_info()
            self.update_profile_combo()
            self.update_profile_info()
            
            # Обновляем элементы настроек
            self.min_memory_input.setText(str(self.settings.get("min_memory", 2048)))
            self.max_memory_input.setText(str(self.settings.get("max_memory", 4096)))
            self.show_release_checkbox.setChecked(self.settings.get("show_release", True))
            self.show_snapshot_checkbox.setChecked(self.settings.get("show_snapshot", False))
            self.show_beta_checkbox.setChecked(self.settings.get("show_beta", False))
            self.show_alpha_checkbox.setChecked(self.settings.get("show_alpha", False))
            self.download_location_input.setText(self.settings.get("download_location", self.minecraft_directory))
            self.java_path_input.setText(self.settings.get("java_path", ""))
            self.show_tray_checkbox.setChecked(self.settings.get("show_tray_icon", True))
            self.minimize_to_tray_checkbox.setChecked(self.settings.get("minimize_to_tray", True))
            self.auto_check_updates_checkbox.setChecked(self.settings.get("auto_check_updates", True))
            self.auto_update_combo.setCurrentText(self.settings.get("auto_update", "Включено"))
            self.close_launcher_combo.setCurrentText(self.settings.get("close_launcher", "Нет"))
            self.additional_args_input.setText(self.settings.get("additional_arguments", ""))
            
            QMessageBox.information(
                self,
                "Сброс настроек",
                "Настройки лаунчера успешно сброшены на значения по умолчанию"
            )
            
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось сбросить настройки: {str(e)}"
            )

    def load_settings(self):
        try:
            self.settings = {}
            settings_file = os.path.join(self.nova_directory, "launcher_settings.json")
            if os.path.exists(settings_file):
                with open(settings_file, "r", encoding='utf-8') as f:
                    self.settings = json.load(f)
            if not self.settings:
                self.settings = {
                    "min_memory": 2048,
                    "max_memory": 4096,
                    "font_size": 10,
                    "auto_update": "Включено",
                    "close_launcher": "Нет",
                    "show_release": True,
                    "show_snapshot": False,
                    "show_beta": False,
                    "show_alpha": False,
                    "show_tray_icon": True,
                    "minimize_to_tray": True,
                    "auto_check_updates": True,
                    "download_location": self.minecraft_directory,
                    "java_path": "",
                    "additional_arguments": "",
                    "last_update_check": "",
                    "last_profile_index": 0,
                    "last_version": ""
                }
                self.save_settings()
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить настройки: {str(e)}")
            self.settings = {
                "min_memory": 2048,
                "max_memory": 4096,
                "font_size": 10,
                "auto_update": "Включено",
                "close_launcher": "Нет",
                "show_release": True,
                "show_snapshot": False,
                "show_beta": False,
                "show_alpha": False,
                "show_tray_icon": True,
                "minimize_to_tray": True,
                "auto_check_updates": True,
                "download_location": self.minecraft_directory,
                "java_path": "",
                "additional_arguments": "",
                "last_update_check": "",
                "last_profile_index": 0,
                "last_version": ""
            }

    def save_settings(self):
        try:
            # Убедимся, что директория существует
            if not os.path.exists(self.nova_directory):
                os.makedirs(self.nova_directory)
                
            settings_file = os.path.join(self.nova_directory, "launcher_settings.json")
            with open(settings_file, "w", encoding='utf-8') as f:
                json.dump(self.settings, f, ensure_ascii=False, indent=4)
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить настройки: {str(e)}")

    def create_profiles_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)

        # Заголовок страницы
        title_label = QLabel("Профили")
        title_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #43A047,
                    stop:0.5 #4CAF50,
                    stop:1 #43A047);
                border-radius: 10px;
            }
        """)
        layout.addWidget(title_label)

        # Контейнер для списка и кнопок
        container = QWidget()
        container_layout = QHBoxLayout(container)
        container_layout.setSpacing(20)

        # Левая панель со списком профилей
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(10)

        # Список профилей
        self.profiles_list = QListWidget()
        self.profiles_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(255, 255, 255, 10);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 10px;
                padding: 5px;
                color: white;
            }
            QListWidget::item {
                background-color: rgba(255, 255, 255, 5);
                border: 1px solid rgba(255, 255, 255, 20);
                border-radius: 5px;
                padding: 8px;
                margin: 2px;
            }
            QListWidget::item:selected {
                background-color: rgba(67, 160, 71, 0.5);
                border: 1px solid #4CAF50;
            }
            QListWidget::item:hover {
                background-color: rgba(255, 255, 255, 15);
            }
        """)
        left_layout.addWidget(self.profiles_list)

        # Кнопки управления профилями
        buttons_widget = QWidget()
        buttons_layout = QHBoxLayout(buttons_widget)
        buttons_layout.setSpacing(10)

        add_button = QPushButton("Добавить")
        remove_button = QPushButton("Удалить")
        edit_button = QPushButton("Редактировать")

        for button in [add_button, remove_button, edit_button]:
            button.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255, 255, 255, 10);
                    border: 1px solid rgba(255, 255, 255, 30);
                    border-radius: 5px;
                    color: white;
                    padding: 8px 15px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: rgba(67, 160, 71, 0.5);
                    border: 1px solid #4CAF50;
                }
                QPushButton:pressed {
                    background-color: rgba(67, 160, 71, 0.7);
                }
            """)
            buttons_layout.addWidget(button)

        left_layout.addWidget(buttons_widget)
        container_layout.addWidget(left_panel)

        # Правая панель с настройками профиля
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(15)

        # Группа основных настроек
        settings_group = QGroupBox("Настройки профиля")
        settings_group.setStyleSheet("""
            QGroupBox {
                background-color: rgba(255, 255, 255, 5);
                border: 1px solid rgba(255, 255, 255, 30);
                border-radius: 10px;
                color: white;
                font-weight: bold;
                padding: 15px;
                margin-top: 15px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        settings_layout = QFormLayout(settings_group)
        settings_layout.setSpacing(10)

        # Поля настроек
        name_edit = QLineEdit()
        version_combo = QComboBox()
        memory_spin = QSpinBox()
        java_path_edit = QLineEdit()
        game_dir_edit = QLineEdit()

        for widget in [name_edit, version_combo, memory_spin, java_path_edit, game_dir_edit]:
            widget.setStyleSheet("""
                QLineEdit, QComboBox, QSpinBox {
                    background-color: rgba(255, 255, 255, 10);
                    border: 1px solid rgba(255, 255, 255, 30);
                    border-radius: 5px;
                    color: white;
                    padding: 5px;
                }
                QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
                    border: 1px solid #4CAF50;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox::down-arrow {
                    image: url(Resources/down_arrow.png);
                    width: 12px;
                    height: 12px;
                }
            """)

        settings_layout.addRow("Имя профиля:", name_edit)
        settings_layout.addRow("Версия:", version_combo)
        settings_layout.addRow("Память (MB):", memory_spin)
        settings_layout.addRow("Путь к Java:", java_path_edit)
        settings_layout.addRow("Папка игры:", game_dir_edit)

        right_layout.addWidget(settings_group)

        # Группа дополнительных настроек
        advanced_group = QGroupBox("Дополнительные настройки")
        advanced_group.setStyleSheet(settings_group.styleSheet())
        advanced_layout = QVBoxLayout(advanced_group)

        # Чекбоксы для дополнительных настроек
        checkboxes = [
            QCheckBox("Открывать лаунчер после закрытия игры"),
            QCheckBox("Использовать собственные библиотеки"),
            QCheckBox("Включить экспериментальные функции")
        ]

        for checkbox in checkboxes:
            checkbox.setStyleSheet("""
                QCheckBox {
                    color: white;
                    spacing: 5px;
                }
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                    background-color: rgba(255, 255, 255, 10);
                    border: 1px solid rgba(255, 255, 255, 30);
                    border-radius: 3px;
                }
                QCheckBox::indicator:checked {
                    background-color: #4CAF50;
                    border: 1px solid #43A047;
                }
                QCheckBox::indicator:hover {
                    border: 1px solid #4CAF50;
                }
            """)
            advanced_layout.addWidget(checkbox)

        right_layout.addWidget(advanced_group)

        # Кнопки сохранения
        save_buttons = QWidget()
        save_layout = QHBoxLayout(save_buttons)
        save_layout.setSpacing(10)

        save_button = QPushButton("Сохранить")
        cancel_button = QPushButton("Отмена")

        for button in [save_button, cancel_button]:
            button.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    border: none;
                    border-radius: 5px;
                    color: white;
                    padding: 10px 20px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #43A047;
                }
                QPushButton:pressed {
                    background-color: #388E3C;
                }
            """)
            save_layout.addWidget(button)

        right_layout.addWidget(save_buttons)
        container_layout.addWidget(right_panel)

        layout.addWidget(container)
        return page

class MinecraftNewsThread(QThread):
    news_loaded = Signal(list)
    error = Signal(str)
    
    def run(self):
        try:
            # Попытка загрузить новости с API или сайта Minecraft
            news_items = []
            
            # Пробуем загрузить официальные новости
            try:
                response = requests.get('https://launchercontent.mojang.com/news.json', timeout=5)
                if response.status_code == 200:
                    news_data = response.json()
                    
                    # Обрабатываем полученные новости
                    for entry in news_data.get('entries', [])[:5]:  # Берем только первые 5 новостей
                        title = entry.get('title', 'Без заголовка')
                        text = entry.get('text', 'Нет описания')
                        news_items.append((title, text))
            except:
                # Если не удалось загрузить, используем запасной вариант
                pass
                
            # Если не удалось получить новости с официального API, добавляем собственные
            if not news_items:
                news_items = [
                    ("Nova Launcher 1.4", "Полный редизайн и оптимизация лаунчера с автоматическими обновлениями"),
                    ("Minecraft 1.20.4", """1.20.4 - стабильное обновление для Java Edition, вышедшее на релиз 1 декабря 2023 года. 
В этом обновлении были добавлены улучшения производительности, исправления багов 
и внесены важные изменения в игровую механику."""),
                    ("Готовность к обновлениям", "Nova Launcher теперь поддерживает все типы версий Minecraft: релизы, снапшоты, бета и альфа версии."),
                    ("Системный трей", "Лаунчер может работать в фоновом режиме через системный трей."),
                    ("Расширенные настройки", "Добавлены новые возможности настройки Java, памяти и профилей.")
                ]
                
            self.news_loaded.emit(news_items)
        except Exception as e:
            self.error.emit(str(e))
            
            # В случае ошибки используем стандартные новости
            default_news = [
                ("Nova Launcher 1.4", "Полный редизайн и оптимизация лаунчера"),
                ("Minecraft 1.20.4", "Стабильная версия с исправлениями ошибок"),
                ("Функции лаунчера", "Поддержка всех типов версий Minecraft")
            ]
            self.news_loaded.emit(default_news)

class ScreenshotsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Скриншоты")
        self.setMinimumSize(800, 600)
        
        # Указываем директорию со скриншотами
        self.screenshots_dir = os.path.join(parent.minecraft_directory, "screenshots")
        
        # Создаем директорию, если она не существует
        if not os.path.exists(self.screenshots_dir):
            os.makedirs(self.screenshots_dir)
            
        # Создаем основной layout
        layout = QVBoxLayout(self)
        
        # Заголовок
        title_label = QLabel("Скриншоты Minecraft")
        title_label.setFont(parent.minecraft_font)
        title_label.setStyleSheet("font-size: 18px;")
        layout.addWidget(title_label)
        
        # Список скриншотов и предпросмотр
        content_layout = QHBoxLayout()
        
        # Левая панель со списком файлов
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        
        self.files_list = QListWidget()
        self.files_list.setFont(parent.minecraft_font)
        self.files_list.currentItemChanged.connect(self.screenshot_selected)
        
        refresh_button = QPushButton("Обновить")
        refresh_button.setFont(parent.minecraft_font)
        refresh_button.clicked.connect(self.load_screenshots)
        
        open_folder_button = QPushButton("Открыть папку")
        open_folder_button.setFont(parent.minecraft_font)
        open_folder_button.clicked.connect(self.open_screenshots_folder)
        
        left_layout.addWidget(QLabel("Доступные скриншоты:"))
        left_layout.addWidget(self.files_list)
        left_layout.addWidget(refresh_button)
        left_layout.addWidget(open_folder_button)
        
        # Правая панель с предпросмотром
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        self.image_preview = QLabel("Выберите скриншот для предпросмотра")
        self.image_preview.setAlignment(Qt.AlignCenter)
        self.image_preview.setStyleSheet("background-color: rgba(45, 45, 45, 180); border-radius: 4px;")
        
        delete_button = QPushButton("Удалить")
        delete_button.setFont(parent.minecraft_font)
        delete_button.clicked.connect(self.delete_screenshot)
        
        share_button = QPushButton("Сохранить копию")
        share_button.setFont(parent.minecraft_font)
        share_button.clicked.connect(self.save_screenshot_copy)
        
        right_layout.addWidget(QLabel("Предпросмотр:"))
        right_layout.addWidget(self.image_preview)
        
        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(delete_button)
        buttons_layout.addWidget(share_button)
        right_layout.addLayout(buttons_layout)
        
        # Добавляем панели в основной layout
        content_layout.addWidget(left_panel, 1)  # 1/3 ширины
        content_layout.addWidget(right_panel, 2)  # 2/3 ширины
        
        layout.addLayout(content_layout)
        
        # Загружаем скриншоты
        self.load_screenshots()
        
    def load_screenshots(self):
        """Загружает список скриншотов"""
        self.files_list.clear()
        
        if not os.path.exists(self.screenshots_dir):
            return
            
        # Получаем список файлов изображений
        image_extensions = ['.png', '.jpg', '.jpeg']
        screenshots = []
        
        for file in os.listdir(self.screenshots_dir):
            for ext in image_extensions:
                if file.lower().endswith(ext):
                    screenshots.append(file)
                    break
        
        # Сортируем по дате модификации (новые сверху)
        screenshots.sort(key=lambda x: os.path.getmtime(os.path.join(self.screenshots_dir, x)), reverse=True)
        
        # Добавляем в список
        for screenshot in screenshots:
            self.files_list.addItem(screenshot)
            
        # Выбираем первый элемент, если он есть
        if self.files_list.count() > 0:
            self.files_list.setCurrentRow(0)
        else:
            self.image_preview.setText("Нет доступных скриншотов")
            
    def screenshot_selected(self, current, previous):
        """Обрабатывает выбор скриншота"""
        if current is None:
            self.image_preview.setText("Выберите скриншот для предпросмотра")
            return
            
        screenshot_path = os.path.join(self.screenshots_dir, current.text())
        
        if os.path.exists(screenshot_path):
            pixmap = QPixmap(screenshot_path)
            
            # Масштабируем изображение, чтобы оно поместилось в область предпросмотра
            preview_size = self.image_preview.size()
            scaled_pixmap = pixmap.scaled(
                preview_size, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            
            self.image_preview.setPixmap(scaled_pixmap)
        else:
            self.image_preview.setText("Ошибка загрузки изображения")
            
    def open_screenshots_folder(self):
        """Открывает папку со скриншотами"""
        if os.path.exists(self.screenshots_dir):
            if sys.platform == 'win32':
                os.startfile(self.screenshots_dir)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', self.screenshots_dir])
            else:
                subprocess.Popen(['xdg-open', self.screenshots_dir])
        else:
            QMessageBox.warning(self, "Ошибка", "Директория скриншотов не найдена")
            
    def delete_screenshot(self):
        """Удаляет выбранный скриншот"""
        current_item = self.files_list.currentItem()
        if current_item is None:
            return
            
        screenshot_path = os.path.join(self.screenshots_dir, current_item.text())
        
        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить скриншот {current_item.text()}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                os.remove(screenshot_path)
                self.load_screenshots()  # Обновляем список
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось удалить файл: {str(e)}")
                
    def save_screenshot_copy(self):
        """Сохраняет копию выбранного скриншота"""
        current_item = self.files_list.currentItem()
        if current_item is None:
            return
            
        screenshot_path = os.path.join(self.screenshots_dir, current_item.text())
        
        if not os.path.exists(screenshot_path):
            QMessageBox.warning(self, "Ошибка", "Файл скриншота не найден")
            return
            
        # Запрашиваем место для сохранения копии
        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Сохранить копию скриншота",
            current_item.text(),
            "PNG изображения (*.png);;JPEG изображения (*.jpg *.jpeg);;Все файлы (*.*)"
        )
        
        if not save_path:
            return
            
        try:
            import shutil
            shutil.copy2(screenshot_path, save_path)
            QMessageBox.information(self, "Успешно", f"Копия скриншота сохранена:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить копию: {str(e)}")

class ProfileManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.parent = parent
        self.setWindowTitle("Управление профилями")
        self.setMinimumSize(600, 400)
        
        layout = QVBoxLayout(self)
        
        # Список профилей
        self.profiles_list = QListWidget()
        self.profiles_list.setFont(parent.minecraft_font)
        self.profiles_list.currentItemChanged.connect(self.profile_selected)
        layout.addWidget(self.profiles_list)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        
        add_button = QPushButton("Добавить")
        add_button.setFont(parent.minecraft_font)
        add_button.clicked.connect(self.add_profile)
        
        edit_button = QPushButton("Редактировать")
        edit_button.setFont(parent.minecraft_font)
        edit_button.clicked.connect(self.edit_profile)
        
        delete_button = QPushButton("Удалить")
        delete_button.setFont(parent.minecraft_font)
        delete_button.clicked.connect(self.delete_profile)
        
        buttons_layout.addWidget(add_button)
        buttons_layout.addWidget(edit_button)
        buttons_layout.addWidget(delete_button)
        layout.addLayout(buttons_layout)
        
        # Информация о профиле
        info_group = QWidget()
        info_layout = QFormLayout(info_group)
        
        self.name_label = QLabel()
        self.name_label.setFont(parent.minecraft_font)
        self.username_label = QLabel()
        self.username_label.setFont(parent.minecraft_font)
        
        info_layout.addRow("Имя профиля:", self.name_label)
        info_layout.addRow("Никнейм:", self.username_label)
        
        layout.addWidget(info_group)
        
        # Кнопка выбора иконки
        self.icon_button = QPushButton("Выбрать иконку")
        self.icon_button.setFont(parent.minecraft_font)
        self.icon_button.clicked.connect(self.choose_icon)
        layout.addWidget(self.icon_button)
        
        # Предпросмотр иконки
        self.icon_preview = QLabel()
        self.icon_preview.setFixedSize(64, 64)
        self.icon_preview.setAlignment(Qt.AlignCenter)
        self.icon_preview.setStyleSheet("background-color: rgba(45, 45, 45, 180); border-radius: 4px;")
        layout.addWidget(self.icon_preview)
        
        # Кнопки закрытия
        close_buttons = QHBoxLayout()
        save_button = QPushButton("Сохранить")
        save_button.setFont(parent.minecraft_font)
        save_button.clicked.connect(self.accept)
        cancel_button = QPushButton("Отмена")
        cancel_button.setFont(parent.minecraft_font)
        cancel_button.clicked.connect(self.reject)
        
        close_buttons.addWidget(save_button)
        close_buttons.addWidget(cancel_button)
        layout.addLayout(close_buttons)
        
        # Загружаем профили
        self.load_profiles()
        
    def load_profiles(self):
        self.profiles_list.clear()
        for profile in self.parent.profiles:
            item = QListWidgetItem(profile["name"])
            item.setData(Qt.UserRole, profile)
            self.profiles_list.addItem(item)
            
    def profile_selected(self, current, previous):
        if current is None:
            self.name_label.setText("")
            self.username_label.setText("")
            self.icon_preview.clear()
            return
            
        profile = current.data(Qt.UserRole)
        self.name_label.setText(profile["name"])
        self.username_label.setText(profile["username"])
        
        # Отображаем иконку профиля
        if "icon" in profile and profile["icon"]:
            icon_path = os.path.join(self.parent.nova_directory, "profile_icons", profile["icon"])
            if os.path.exists(icon_path):
                pixmap = QPixmap(icon_path)
                self.icon_preview.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            else:
                self.icon_preview.clear()
        else:
            self.icon_preview.clear()
            
    def add_profile(self):
        dialog = ProfileDialog(self.parent)
        if dialog.exec():
            profile_data = dialog.get_profile_data()
            self.parent.profiles.append(profile_data)
            self.parent.save_profiles()
            self.load_profiles()
            
    def edit_profile(self):
        current_item = self.profiles_list.currentItem()
        if current_item is None:
            return
            
        profile = current_item.data(Qt.UserRole)
        dialog = ProfileDialog(self.parent, profile)
        if dialog.exec():
            profile_data = dialog.get_profile_data()
            index = self.profiles_list.currentRow()
            self.parent.profiles[index] = profile_data
            self.parent.save_profiles()
            self.load_profiles()
            
    def delete_profile(self):
        current_item = self.profiles_list.currentItem()
        if current_item is None:
            return
            
        reply = QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить профиль {current_item.text()}?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            index = self.profiles_list.currentRow()
            # Удаляем иконку профиля, если она есть
            profile = self.parent.profiles[index]
            if "icon" in profile and profile["icon"]:
                icon_path = os.path.join(self.parent.nova_directory, "profile_icons", profile["icon"])
                if os.path.exists(icon_path):
                    os.remove(icon_path)
            
            del self.parent.profiles[index]
            self.parent.save_profiles()
            self.load_profiles()
            
    def choose_icon(self):
        current_item = self.profiles_list.currentItem()
        if current_item is None:
            return
            
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Выберите иконку профиля",
            "",
            "Изображения (*.png *.jpg *.jpeg)"
        )
        
        if file_path:
            try:
                # Создаем директорию для иконок, если её нет
                icons_dir = os.path.join(self.parent.nova_directory, "profile_icons")
                if not os.path.exists(icons_dir):
                    os.makedirs(icons_dir)
                
                # Генерируем уникальное имя файла
                file_ext = os.path.splitext(file_path)[1]
                new_filename = f"icon_{uuid.uuid4()}{file_ext}"
                new_path = os.path.join(icons_dir, new_filename)
                
                # Копируем файл
                import shutil
                shutil.copy2(file_path, new_path)
                
                # Обновляем профиль
                index = self.profiles_list.currentRow()
                self.parent.profiles[index]["icon"] = new_filename
                self.parent.save_profiles()
                
                # Обновляем предпросмотр
                pixmap = QPixmap(new_path)
                self.icon_preview.setPixmap(pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось установить иконку: {str(e)}")

class SmoothStackedWidget(QStackedWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.m_direction = Qt.Horizontal
        self.m_speed = 300
        self.m_animationtype = QEasingCurve.OutCubic
        self.m_now = 0
        self.m_next = 0
        self.m_wrap = False
        self.m_pnow = QPoint(0, 0)
        self.m_active = False

    def setDirection(self, direction):
        self.m_direction = direction

    def setSpeed(self, speed):
        self.m_speed = speed

    def setAnimation(self, animationtype):
        self.m_animationtype = animationtype

    def setWrap(self, wrap):
        self.m_wrap = wrap

    def slideInNext(self):
        now = self.currentIndex()
        if self.m_wrap or now < self.count() - 1:
            self.slideInIdx(now + 1)

    def slideInPrev(self):
        now = self.currentIndex()
        if self.m_wrap or now > 0:
            self.slideInIdx(now - 1)

    def slideInIdx(self, idx):
        if idx > self.count() - 1:
            idx = idx % self.count()
        elif idx < 0:
            idx = (idx + self.count()) % self.count()
        self.slideInWgt(self.widget(idx))

    def slideInWgt(self, newwidget):
        if self.m_active:
            return

        self.m_active = True

        _now = self.currentIndex()
        _next = self.indexOf(newwidget)

        if _now == _next:
            self.m_active = False
            return

        offsetx = self.frameRect().width()
        offsety = self.frameRect().height()
        self.widget(_next).setGeometry(self.frameRect())

        if not self.m_direction == Qt.Horizontal:
            if _now < _next:
                offsetx = 0
                offsety = -offsety
            else:
                offsetx = 0
                offsety = offsety
        else:
            if _now < _next:
                offsetx = -offsetx
                offsety = 0
            else:
                offsetx = offsetx
                offsety = 0

        pnext = self.widget(_next).pos()
        pnow = self.widget(_now).pos()
        self.m_pnow = pnow

        offset = QPoint(offsetx, offsety)
        self.widget(_next).move(pnext - offset)
        self.widget(_next).show()
        self.widget(_next).raise_()

        anim_group = QParallelAnimationGroup(self)

        for index, start, end in zip((_now, _next), (pnow, pnext - offset), (pnow + offset, pnext)):
            animation = QPropertyAnimation(self.widget(index), b"pos", self)
            animation.setDuration(self.m_speed)
            animation.setEasingCurve(self.m_animationtype)
            animation.setStartValue(start)
            animation.setEndValue(end)
            anim_group.addAnimation(animation)

        anim_group.finished.connect(self.animationDoneSlot)
        self.m_next = _next
        self.m_now = _now
        self.m_active = True
        anim_group.start(QAbstractAnimation.DeleteWhenStopped)

    def animationDoneSlot(self):
        self.setCurrentIndex(self.m_next)
        self.widget(self.m_now).hide()
        self.m_active = False

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Создаем и показываем сплэш скрин
    splash = LoadingSplash()
    splash.show()
    
    # Создаем главное окно, но пока не показываем его
    window = MinecraftLauncher()
    
    # Запускаем прогресс загрузки
    splash.start_progress()
    
    # Создаем таймер для проверки завершения загрузки
    check_timer = QTimer()
    
    def check_loading():
        if splash.loading_finished:
            check_timer.stop()
            # Запускаем анимацию скрытия сплэш скрина
            splash.finish(window)
            # Показываем главное окно после небольшой задержки
            QTimer.singleShot(800, window.show)
    
    check_timer.timeout.connect(check_loading)
    check_timer.start(100)
    
    sys.exit(app.exec()) 