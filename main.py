import sys
import os
import minecraft_launcher_lib
import subprocess
import json
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QComboBox, QLabel, 
                             QLineEdit, QProgressBar, QMessageBox,
                             QStackedWidget, QFileDialog, QScrollArea, QListWidget, QDialog,
                             QFormLayout, QTabWidget, QCheckBox)
from PySide6.QtGui import QFont, QFontDatabase, QIcon, QPixmap, QPalette, QBrush
from PySide6.QtCore import Qt, QThread, Signal

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

class MinecraftLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        # Изменяем пути файлов для использования кастомной директории
        self.nova_directory = os.path.join(os.path.expanduser("~"), ".nova_launcher")
        self.minecraft_directory = os.path.join(os.path.expanduser("~"), ".minecraft")
        
        # Создаем директории, если они не существуют
        if not os.path.exists(self.minecraft_directory):
            os.makedirs(self.minecraft_directory)
        if not os.path.exists(self.nova_directory):
            os.makedirs(self.nova_directory)
            
        self.setWindowTitle("Nova Launcher")
        self.setMinimumSize(1200, 700)
        
        # Set window icon
        self.setWindowIcon(QIcon(os.path.join("Resources", "rounded_logo_nova.png")))
        
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
        self.content_stack = QStackedWidget()
        
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
        version_label = QLabel("Nova Launcher 1.3")
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
        
        # Set background
        self.set_background()
        
        # Set stylesheet
        self.apply_theme()

    def apply_theme(self):
        self.setStyleSheet("""
            QMainWindow {
                background: transparent;
            }
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
        """)

        # Add profileInfo style
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
        
        # Кнопка сохранения настроек памяти
        save_memory_button = QPushButton("Сохранить настройки памяти")
        save_memory_button.setFont(self.minecraft_font)
        save_memory_button.clicked.connect(self.save_memory_settings)
        memory_layout.addWidget(save_memory_button)
        memory_layout.addStretch()
        
        # ================ Таб для настроек версий ================
        versions_tab = QWidget()
        versions_layout = QVBoxLayout(versions_tab)
        
        versions_description = QLabel("Выберите типы версий, которые будут отображаться в списке:")
        versions_description.setFont(self.minecraft_font)
        versions_description.setWordWrap(True)
        versions_layout.addWidget(versions_description)
        
        # Чекбоксы для типов версий
        self.show_release_checkbox = QCheckBox("Релизы (стабильные версии)")
        self.show_release_checkbox.setFont(self.minecraft_font)
        self.show_release_checkbox.setChecked(self.settings.get("show_release", True))
        
        self.show_snapshot_checkbox = QCheckBox("Snapshots (тестовые сборки)")
        self.show_snapshot_checkbox.setFont(self.minecraft_font)
        self.show_snapshot_checkbox.setChecked(self.settings.get("show_snapshot", False))
        
        self.show_beta_checkbox = QCheckBox("Beta (устаревшие бета-версии)")
        self.show_beta_checkbox.setFont(self.minecraft_font)
        self.show_beta_checkbox.setChecked(self.settings.get("show_beta", False))
        
        self.show_alpha_checkbox = QCheckBox("Alpha (устаревшие альфа-версии)")
        self.show_alpha_checkbox.setFont(self.minecraft_font)
        self.show_alpha_checkbox.setChecked(self.settings.get("show_alpha", False))
        
        versions_layout.addWidget(self.show_release_checkbox)
        versions_layout.addWidget(self.show_snapshot_checkbox)
        versions_layout.addWidget(self.show_beta_checkbox)
        versions_layout.addWidget(self.show_alpha_checkbox)
        
        save_versions_button = QPushButton("Сохранить настройки версий")
        save_versions_button.setFont(self.minecraft_font)
        save_versions_button.clicked.connect(self.save_versions_settings)
        versions_layout.addWidget(save_versions_button)
        
        versions_layout.addStretch()
        
        # ================ Таб для настроек директорий ================
        dirs_tab = QWidget()
        dirs_layout = QVBoxLayout(dirs_tab)
        
        dirs_description = QLabel("Управление директориями:")
        dirs_description.setFont(self.minecraft_font)
        dirs_layout.addWidget(dirs_description)
        
        open_minecraft_dir_button = QPushButton("Открыть папку .minecraft")
        open_minecraft_dir_button.setFont(self.minecraft_font)
        open_minecraft_dir_button.clicked.connect(self.open_minecraft_dir)
        
        open_nova_dir_button = QPushButton("Открыть папку лаунчера")
        open_nova_dir_button.setFont(self.minecraft_font)
        open_nova_dir_button.clicked.connect(self.open_nova_dir)
        
        dirs_layout.addWidget(open_minecraft_dir_button)
        dirs_layout.addWidget(open_nova_dir_button)
        dirs_layout.addStretch()
        
        # Добавляем табы
        tabs.addTab(memory_tab, "Память")
        tabs.addTab(versions_tab, "Версии")
        tabs.addTab(dirs_tab, "Директории")
        
        layout.addWidget(tabs)
        
        # Информация о текущих настройках
        self.settings_info = QLabel()
        self.settings_info.setFont(self.minecraft_font)
        self.settings_info.setObjectName("profileInfo")
        self.update_settings_info()
        layout.addWidget(self.settings_info)
        
        return page
        
    def save_memory_settings(self):
        try:
            min_memory = int(self.min_memory_input.text())
            max_memory = int(self.max_memory_input.text())
            
            if min_memory <= 0 or max_memory <= 0:
                raise ValueError("Значения памяти должны быть положительными")
                
            if min_memory > max_memory:
                raise ValueError("Минимальное значение памяти не может быть больше максимального")
            
            self.settings["min_memory"] = min_memory
            self.settings["max_memory"] = max_memory
            self.save_settings()
            self.update_settings_info()
            
            QMessageBox.information(self, "Успешно", "Настройки памяти сохранены")
            
        except ValueError as e:
            QMessageBox.warning(self, "Ошибка", f"Ошибка в значениях памяти: {str(e)}")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить настройки: {str(e)}")
            
    def open_nova_dir(self):
        if os.path.exists(self.nova_directory):
            if sys.platform == 'win32':
                os.startfile(self.nova_directory)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', self.nova_directory])
            else:
                subprocess.Popen(['xdg-open', self.nova_directory])
        else:
            QMessageBox.warning(self, "Ошибка", "Директория лаунчера не найдена")

    def open_settings_dialog(self):
        dialog = SettingsDialog(self, self.settings)
        if dialog.exec():
            settings_data = dialog.get_settings_data()
            if settings_data:
                self.settings = settings_data
                self.save_settings()
                self.update_settings_info()
                
                # Применить изменения
                old_font_size = self.minecraft_font.pointSize()
                new_font_size = self.settings.get("font_size", 10)
                
                if old_font_size != new_font_size:
                    self.minecraft_font.setPointSize(new_font_size)
                    self.update_fonts()
                
                self.apply_theme()
                QMessageBox.information(self, "Успешно", "Настройки сохранены")
                
                # Обновляем значения в полях для памяти
                self.min_memory_input.setText(str(self.settings.get("min_memory", 2048)))
                self.max_memory_input.setText(str(self.settings.get("max_memory", 4096)))

    def update_fonts(self):
        # Обновление шрифтов на всех страницах
        # В реальном приложении здесь можно обновить шрифты для всех элементов
        pass

    def open_minecraft_dir(self):
        if os.path.exists(self.minecraft_directory):
            if sys.platform == 'win32':
                os.startfile(self.minecraft_directory)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', self.minecraft_directory])
            else:
                subprocess.Popen(['xdg-open', self.minecraft_directory])
        else:
            QMessageBox.warning(self, "Ошибка", "Директория .minecraft не найдена")

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
                    "show_alpha": False
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
                "show_alpha": False
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

    def set_background(self):
        background = QPixmap(os.path.join("Resources", "minecraft_launcher.png"))
        palette = QPalette()
        palette.setBrush(QPalette.Window, QBrush(background.scaled(
            self.size(),
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation
        )))
        self.setPalette(palette)

    def change_page(self, index):
        self.content_stack.setCurrentIndex(index)
        for i, button in enumerate(self.sidebar_buttons):
            button.setChecked(i == index)

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

    def create_news_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 40, 40, 40)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("QScrollArea { border: none; }")
        
        news_widget = QWidget()
        news_layout = QVBoxLayout(news_widget)
        
        # Add some sample news
        news_items = [
            ("Nova Launcher 1.3", "Полный редизайн и оптимизация лаунчера"),
            ("Minecraft 1.21.5", """1.21.5, полный выпуск Spring to Life, — это игровой дроп для Java Edition, выпущенный 25 марта 2025 года. 
В этом обновлении были добавлены окрасы для свиней, коров и кур, новые блоки для придания биомам большей атмосферности, 
а также были обновлены иконки яиц призывания и исправлен ряд ошибок."""),
            ("Что ещё?", "Улучшена производительность ")
        ]
        
        for title, desc in news_items:
            news_item = QWidget()
            news_item.setObjectName("newsItem")
            item_layout = QVBoxLayout(news_item)
            
            title_label = QLabel(title)
            title_label.setFont(self.minecraft_font)
            desc_label = QLabel(desc)
            
            item_layout.addWidget(title_label)
            item_layout.addWidget(desc_label)
            
            news_layout.addWidget(news_item)
        
        news_layout.addStretch()
        scroll_area.setWidget(news_widget)
        layout.addWidget(scroll_area)
        
        return page

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
            self.version_combo.clear()
            # Сначала проверяем установленные версии
            installed_versions = minecraft_launcher_lib.utils.get_installed_versions(self.minecraft_directory)
            
            try:
                # Пытаемся получить онлайн-список версий
                version_list = minecraft_launcher_lib.utils.get_version_list()
                
                # Применяем фильтры типов версий
                filtered_versions = []
                for version in version_list:
                    version_type = version["type"]
                    
                    if version_type == "release" and self.settings.get("show_release", True):
                        filtered_versions.append(version)
                    elif version_type == "snapshot" and self.settings.get("show_snapshot", False):
                        filtered_versions.append(version)
                    elif version_type == "old_beta" and self.settings.get("show_beta", False):
                        filtered_versions.append(version)
                    elif version_type == "old_alpha" and self.settings.get("show_alpha", False):
                        filtered_versions.append(version)
                
                # Добавляем отфильтрованные версии в комбобокс
                for version in filtered_versions:
                    self.version_combo.addItem(version["id"])
                    
            except Exception as e:
                # Если не удалось получить онлайн-список, используем только установленные версии
                QMessageBox.warning(
                    self,
                    "Предупреждение",
                    "Не удалось получить список версий с серверов Minecraft.\n"
                    "Будут показаны только установленные версии."
                )
                for version in installed_versions:
                    self.version_combo.addItem(version["id"])
            
            # Если список пуст, добавляем базовые версии
            if self.version_combo.count() == 0:
                default_versions = ["1.20.4", "1.20.2", "1.20.1", "1.19.4", "1.19.3", "1.19.2", "1.18.2"]
                for version in default_versions:
                    self.version_combo.addItem(version)
                
        except Exception as e:
            QMessageBox.critical(
                self,
                "Ошибка",
                f"Не удалось загрузить список версий: {str(e)}\n"
                "Будут использованы базовые версии."
            )
            # Добавляем базовые версии в случае ошибки
            default_versions = ["1.20.4", "1.20.2", "1.20.1", "1.19.4", "1.19.3", "1.19.2", "1.18.2"]
            for version in default_versions:
                self.version_combo.addItem(version)

    def launch_minecraft(self):
        self.progress_bar.setVisible(False)
        self.progress_label.setVisible(False)
        self.play_button.setEnabled(True)

        selected_version = self.version_combo.currentText()
        current_profile = self.profiles[self.profile_combo.currentIndex()]
        username = current_profile["username"]

        min_memory = self.settings.get("min_memory", 2048)
        max_memory = self.settings.get("max_memory", 4096)
        
        options = {
            "username": username,
            "uuid": minecraft_launcher_lib.utils.generate_uuid(username),
            "token": "",
            "jvmArguments": [
                f"-Xms{min_memory}M",
                f"-Xmx{max_memory}M"
            ]
        }

        minecraft_command = minecraft_launcher_lib.command.get_minecraft_command(
            selected_version,
            self.minecraft_directory,
            options
        )

        subprocess.Popen(minecraft_command)
        
        # Закрыть лаунчер, если выбрано в настройках
        if self.settings.get("close_launcher", "Нет") == "Да":
            self.close()

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

    def profile_changed(self, index):
        if index >= 0:
            self.update_profile_info()

    def update_profile_info(self):
        if hasattr(self, 'profile_info_label') and self.profile_combo.currentIndex() >= 0:
            current_profile = self.profiles[self.profile_combo.currentIndex()]
            self.profile_info_label.setText(f"Текущий профиль: {current_profile['name']}\nИгрок: {current_profile['username']}")

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

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.set_background()

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
            
            info_text = f"""
Память:
- Минимальная: {self.settings.get('min_memory', 2048)} МБ
- Максимальная: {self.settings.get('max_memory', 4096)} МБ

Версии:
- Отображаемые типы: {version_types_str}

Внешний вид:
- Размер шрифта: {self.settings.get('font_size', 10)}

Дополнительно:
- Автообновление: {self.settings.get('auto_update', 'Включено')}
- Закрывать лаунчер при запуске: {self.settings.get('close_launcher', 'Нет')}
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
                QMessageBox.warning(self, "Предупреждение", "Должен быть выбран хотя бы один тип версий. Релизы включены автоматически.")
            
            self.save_settings()
            self.update_settings_info()
            self.update_versions()  # Обновляем список версий с новыми настройками
            
            QMessageBox.information(self, "Успешно", "Настройки версий сохранены")
            
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сохранить настройки версий: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    launcher = MinecraftLauncher()
    launcher.show()
    sys.exit(app.exec()) 