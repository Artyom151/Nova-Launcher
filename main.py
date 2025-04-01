import os
import sys
import requests
import vk_api
import shutil
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                            QHBoxLayout, QPushButton, QLabel, QFileDialog, 
                            QListWidget, QSlider, QStyle, QLineEdit, QScrollArea,
                            QFrame, QGridLayout, QStackedWidget, QTabWidget, QListWidgetItem,
                            QDialog, QComboBox, QSpinBox, QCheckBox, QMessageBox, QInputDialog,
                            QProgressBar, QGroupBox, QAbstractItemView)
from PySide6.QtCore import Qt, QTimer, QUrl, QSize, QSettings, QThread, Signal, QPointF, QPropertyAnimation, QEasingCurve, Property
from PySide6.QtGui import QIcon, QPixmap, QPalette, QColor, QFont, QFontDatabase, QPainter, QLinearGradient, QBrush, QDesktopServices, QImage, QPen, QRadialGradient
import pygame
from mutagen.mp3 import MP3
from PIL import Image
import io
import json
from pystyle import Colors, Colorate, Center, Box, System
import time
from ytmusicapi import setup_oauth, YTMusic
from pathlib import Path
import minecraft_launcher_lib
import subprocess
import threading
import random
import math

class Snowflake:
    def __init__(self, x, y, size, speed):
        self.x = x
        self.y = y
        self.size = size
        self.speed = speed
        self.angle = random.uniform(0, 360)
        self.swing = random.uniform(-1, 1)

    def update(self, width, height):
        self.y += self.speed
        self.x += math.sin(self.angle) * self.swing
        self.angle += 0.1

        if self.y > height:
            self.y = -self.size
            self.x = random.uniform(0, width)

class BaseEffect(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.settings = QSettings('RadeonLauncher', 'Settings')
        self.effect_glow = self.settings.value('effect_glow', True, bool)
        self.effect_trails = self.settings.value('effect_trails', True, bool)
        self.effect_rotation = self.settings.value('effect_rotation', True, bool)
        self.effect_interaction = self.settings.value('effect_interaction', True, bool)
        self.particle_size_scale = self.settings.value('particle_size', 100, int) / 100
        self.effect_opacity = self.settings.value('effect_opacity', 70, int) / 100
        
        if self.effect_interaction:
            self.setMouseTracking(True)
            self.mouse_pos = QPointF(0, 0)
            
    def mouseMoveEvent(self, event):
        if self.effect_interaction:
            self.mouse_pos = event.position()
            
    def get_particle_color(self, base_color, opacity=1.0):
        color = QColor(base_color)
        color.setAlpha(int(255 * opacity * self.effect_opacity))
        return color
        
    def apply_glow(self, painter, pos, size, color):
        if self.effect_glow:
            glow_gradient = QRadialGradient(pos, size * 2)
            glow_color = self.get_particle_color(color, 0.5)
            glow_gradient.setColorAt(0, glow_color)
            glow_gradient.setColorAt(1, QColor(0, 0, 0, 0))
            painter.setBrush(glow_gradient)
            painter.drawEllipse(pos, size * 2, size * 2)

class SnowfallEffect(BaseEffect):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.snowflakes = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(50)
        
        particle_count = self.settings.value('particle_count', 100, int)
        for _ in range(particle_count):
            self.create_snowflake()
            
    def create_snowflake(self):
        x = random.uniform(0, self.width())
        y = random.uniform(-50, 0)
        base_size = random.uniform(2, 6)
        size = base_size * self.particle_size_scale
        speed = random.uniform(1, 3)
        rotation = random.uniform(0, 360) if self.effect_rotation else 0
        self.snowflakes.append({
            'x': x, 'y': y,
            'size': size,
            'speed': speed,
            'rotation': rotation,
            'trail': [] if self.effect_trails else None
        })

    def update_animation(self):
        for flake in self.snowflakes:
            if self.effect_interaction:
                dx = flake['x'] - self.mouse_pos.x()
                dy = flake['y'] - self.mouse_pos.y()
                distance = math.sqrt(dx * dx + dy * dy)
                if distance < 100:
                    flake['x'] += dx * 0.02
                    flake['y'] += dy * 0.02
            
            flake['y'] += flake['speed']
            flake['x'] += math.sin(flake['rotation']) * 0.5
            
            if self.effect_rotation:
                flake['rotation'] += 0.1
                
            if self.effect_trails:
                flake['trail'].append((flake['x'], flake['y']))
                if len(flake['trail']) > 5:
                    flake['trail'].pop(0)
            
            if flake['y'] > self.height():
                flake['y'] = -flake['size']
                flake['x'] = random.uniform(0, self.width())
                if self.effect_trails:
                    flake['trail'].clear()
                    
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for flake in self.snowflakes:
            pos = QPointF(flake['x'], flake['y'])
            
            # Рисуем след
            if self.effect_trails and flake['trail']:
                trail_pen = QPen(self.get_particle_color(Qt.white, 0.3))
                trail_pen.setWidth(1)
                painter.setPen(trail_pen)
                for i in range(len(flake['trail']) - 1):
                    painter.drawLine(
                        QPointF(flake['trail'][i][0], flake['trail'][i][1]),
                        QPointF(flake['trail'][i + 1][0], flake['trail'][i + 1][1])
                    )
            
            # Рисуем свечение
            if self.effect_glow:
                self.apply_glow(painter, pos, flake['size'], Qt.white)
            
            # Рисуем снежинку
            painter.setPen(Qt.NoPen)
            gradient = QRadialGradient(pos, flake['size'])
            gradient.setColorAt(0, self.get_particle_color(Qt.white))
            gradient.setColorAt(1, self.get_particle_color(Qt.white, 0))
            painter.setBrush(gradient)
            
            if self.effect_rotation:
                painter.save()
                painter.translate(pos)
                painter.rotate(flake['rotation'])
                painter.translate(-pos)
            
            painter.drawEllipse(pos, flake['size'], flake['size'])
            
            if self.effect_rotation:
                painter.restore()

class MatrixRainEffect(BaseEffect):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.drops = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(50)
        
        particle_count = self.settings.value('particle_count', 100, int)
        for _ in range(particle_count):
            self.create_drop()
            
    def create_drop(self):
        self.drops.append({
            'x': random.uniform(0, self.width()),
            'y': random.uniform(-100, 0),
            'speed': random.uniform(5, 15),
            'chars': [],
            'colors': [],
            'font_size': random.uniform(10, 20) * self.particle_size_scale,
            'update_interval': random.randint(2, 5),
            'counter': 0,
            'trail': [] if self.effect_trails else None,
            'rotation': random.uniform(0, 360) if self.effect_rotation else 0
        })

    def update_animation(self):
        for drop in self.drops:
            if self.effect_interaction:
                dx = drop['x'] - self.mouse_pos.x()
                dy = drop['y'] - self.mouse_pos.y()
                distance = math.sqrt(dx * dx + dy * dy)
                if distance < 100:
                    drop['x'] += dx * 0.02
                    drop['y'] += dy * 0.02
            
            drop['y'] += drop['speed']
            drop['counter'] += 1
            
            if self.effect_rotation:
                drop['rotation'] += 0.5
            
            if drop['counter'] >= drop['update_interval']:
                drop['counter'] = 0
                if len(drop['chars']) < 20:
                    drop['chars'].append(chr(random.randint(0x30A0, 0x30FF)))
                    drop['colors'].append(255)
            
            for i in range(len(drop['colors'])):
                drop['colors'][i] = max(0, drop['colors'][i] - 5)
            
            if self.effect_trails:
                drop['trail'].append((drop['x'], drop['y']))
                if len(drop['trail']) > 10:
                    drop['trail'].pop(0)
            
            if drop['y'] > self.height():
                drop['y'] = random.uniform(-100, 0)
                drop['x'] = random.uniform(0, self.width())
                drop['chars'] = []
                drop['colors'] = []
                if self.effect_trails:
                    drop['trail'].clear()
        
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for drop in self.drops:
            # Рисуем след
            if self.effect_trails and drop['trail']:
                trail_pen = QPen(self.get_particle_color(QColor(0, 255, 0), 0.3))
                trail_pen.setWidth(1)
                painter.setPen(trail_pen)
                for i in range(len(drop['trail']) - 1):
                    painter.drawLine(
                        QPointF(drop['trail'][i][0], drop['trail'][i][1]),
                        QPointF(drop['trail'][i + 1][0], drop['trail'][i + 1][1])
                    )
            
            y = drop['y']
            for char, alpha in zip(drop['chars'], drop['colors']):
                pos = QPointF(drop['x'], y)
                
                # Рисуем свечение
                if self.effect_glow:
                    self.apply_glow(painter, pos, drop['font_size'] / 2, QColor(0, 255, 0))
                
                # Рисуем символ
                color = self.get_particle_color(QColor(0, 255, 0), alpha / 255)
                painter.setPen(color)
                painter.setFont(QFont("Courier", drop['font_size']))
                
                if self.effect_rotation:
                    painter.save()
                    painter.translate(pos)
                    painter.rotate(drop['rotation'])
                    painter.translate(-pos)
                
                painter.drawText(pos, char)
                
                if self.effect_rotation:
                    painter.restore()
                
                y -= drop['font_size']

class ParticleEffect(BaseEffect):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.particles = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(30)
        
        particle_count = self.settings.value('particle_count', 100, int)
        self.colors = [
            QColor("#1db954"),  # Зеленый
            QColor("#ff3333"),  # Красный
            QColor("#3333ff"),  # Синий
            QColor("#ff9933"),  # Оранжевый
            QColor("#9933ff")   # Фиолетовый
        ]
        
        for _ in range(particle_count):
            self.create_particle()

    def create_particle(self):
        x = random.uniform(0, self.width())
        y = random.uniform(0, self.height())
        size = random.uniform(2, 6)
        speed_x = random.uniform(-2, 2)
        speed_y = random.uniform(-2, 2)
        color = random.choice(self.colors)
        life = 255
        
        self.particles.append({
            'x': x, 'y': y,
            'size': size,
            'speed_x': speed_x,
            'speed_y': speed_y,
            'color': color,
            'life': life
        })

    def update_animation(self):
        for particle in self.particles:
            particle['x'] += particle['speed_x']
            particle['y'] += particle['speed_y']
            particle['life'] -= 2
            
            # Отражение от границ
            if particle['x'] < 0 or particle['x'] > self.width():
                particle['speed_x'] *= -1
            if particle['y'] < 0 or particle['y'] > self.height():
                particle['speed_y'] *= -1
        
        # Удаляем угасшие частицы и создаем новые
        self.particles = [p for p in self.particles if p['life'] > 0]
        while len(self.particles) < 50:
            self.create_particle()
            
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for particle in self.particles:
            color = particle['color']
            color.setAlpha(particle['life'])
            painter.setPen(Qt.NoPen)
            
            gradient = QRadialGradient(
                QPointF(particle['x'], particle['y']),
                particle['size'] * 2
            )
            gradient.setColorAt(0, color)
            gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
            painter.setBrush(QBrush(gradient))
            
            painter.drawEllipse(
                QPointF(particle['x'], particle['y']),
                particle['size'],
                particle['size']
            )

class GlowingButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self._glow_radius = 0
        self.glow_animation = QPropertyAnimation(self, b"glow_radius")
        self.glow_animation.setDuration(1500)
        self.glow_animation.setLoopCount(-1)
        self.glow_animation.setStartValue(0)
        self.glow_animation.setEndValue(20)
        self.glow_animation.setEasingCurve(QEasingCurve.InOutQuad)
        self.glow_animation.start()

    @Property(float)
    def glow_radius(self):
        return self._glow_radius

    @glow_radius.setter
    def glow_radius(self, radius):
        self._glow_radius = radius
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Рисуем свечение
        if self._glow_radius > 0:
            gradient = QRadialGradient(self.rect().center(), self._glow_radius)
            gradient.setColorAt(0, QColor(29, 185, 84, 100))
            gradient.setColorAt(1, QColor(29, 185, 84, 0))
            painter.setPen(Qt.NoPen)
            painter.setBrush(gradient)
            painter.drawRect(self.rect())

        # Рисуем кнопку
        super().paintEvent(event)

class ProfileManager:
    def __init__(self):
        self.profiles_file = "profiles.json"
        self.profiles = self.load_profiles()

    def load_profiles(self):
        try:
            if os.path.exists(self.profiles_file):
                with open(self.profiles_file, 'r') as f:
                    return json.load(f)
            return {"profiles": []}
        except:
            return {"profiles": []}

    def save_profiles(self):
        with open(self.profiles_file, 'w') as f:
            json.dump(self.profiles, f)

    def add_profile(self, name, username):
        self.profiles["profiles"].append({
            "name": name,
            "username": username
        })
        self.save_profiles()

    def remove_profile(self, name):
        self.profiles["profiles"] = [p for p in self.profiles["profiles"] if p["name"] != name]
        self.save_profiles()

class ServerManager:
    def __init__(self):
        self.servers_file = "servers.json"
        self.servers = self.load_servers()
        
    def load_servers(self):
        try:
            if os.path.exists(self.servers_file):
                with open(self.servers_file, 'r') as f:
                    return json.load(f)
            return {"servers": []}
        except:
            return {"servers": []}
            
    def save_servers(self):
        with open(self.servers_file, 'w') as f:
            json.dump(self.servers, f)
            
    def add_server(self, name, address, port=25565):
        self.servers["servers"].append({
            "name": name,
            "address": address,
            "port": port
        })
        self.save_servers()
        
    def remove_server(self, name):
        self.servers["servers"] = [s for s in self.servers["servers"] if s["name"] != name]
        self.save_servers()

class ServerListWidget(QWidget):
    def __init__(self, server_manager):
        super().__init__()
        self.server_manager = server_manager
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Список серверов
        self.server_list = QListWidget()
        layout.addWidget(self.server_list)
        
        # Кнопки управления
        buttons_layout = QHBoxLayout()
        self.add_server_btn = QPushButton("Добавить сервер")
        self.remove_server_btn = QPushButton("Удалить сервер")
        
        buttons_layout.addWidget(self.add_server_btn)
        buttons_layout.addWidget(self.remove_server_btn)
        
        self.add_server_btn.clicked.connect(self.add_server)
        self.remove_server_btn.clicked.connect(self.remove_server)
        
        layout.addLayout(buttons_layout)
        self.refresh_servers()
        
    def refresh_servers(self):
        self.server_list.clear()
        for server in self.server_manager.servers["servers"]:
            self.server_list.addItem(f"{server['name']} - {server['address']}:{server['port']}")
            
    def add_server(self):
        name, ok = QInputDialog.getText(self, "Добавить сервер", "Название сервера:")
        if ok and name:
            address, ok = QInputDialog.getText(self, "Добавить сервер", "IP адрес:")
            if ok and address:
                port, ok = QInputDialog.getInt(self, "Добавить сервер", "Порт:", 25565, 1, 65535)
                if ok:
                    self.server_manager.add_server(name, address, port)
                    self.refresh_servers()
                    
    def remove_server(self):
        current = self.server_list.currentItem()
        if current:
            name = current.text().split(" - ")[0]
            self.server_manager.remove_server(name)
            self.refresh_servers()

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройки")
        self.setMinimumWidth(800)
        self.settings = QSettings('RadeonLauncher', 'Settings')
        
        layout = QVBoxLayout(self)
        
        # Создаем вкладки для разных категорий настроек
        tabs = QTabWidget()
        
        # Добавляем вкладки
        tabs.addTab(self.create_general_tab(), "Общие")
        tabs.addTab(self.create_graphics_tab(), "Графика")
        tabs.addTab(self.create_sound_tab(), "Звук")
        tabs.addTab(self.create_controls_tab(), "Управление")
        tabs.addTab(self.create_network_tab(), "Сеть")
        tabs.addTab(self.create_java_tab(), "Java")
        
        layout.addWidget(tabs)
        
        # Кнопки
        buttons = QHBoxLayout()
        save_btn = QPushButton("Сохранить")
        cancel_btn = QPushButton("Отмена")
        
        save_btn.clicked.connect(self.save_settings)
        cancel_btn.clicked.connect(self.reject)
        
        buttons.addWidget(save_btn)
        buttons.addWidget(cancel_btn)
        layout.addLayout(buttons)

    def create_general_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Настройки отображения версий
        versions_group = QGroupBox("Отображение версий")
        versions_layout = QVBoxLayout(versions_group)
        
        self.show_release = QCheckBox("Release версии")
        self.show_snapshot = QCheckBox("Snapshot версии")
        self.show_beta = QCheckBox("Beta версии")
        self.show_alpha = QCheckBox("Alpha версии")
        
        self.show_release.setChecked(self.settings.value('show_release', True, bool))
        self.show_snapshot.setChecked(self.settings.value('show_snapshot', False, bool))
        self.show_beta.setChecked(self.settings.value('show_beta', False, bool))
        self.show_alpha.setChecked(self.settings.value('show_alpha', False, bool))
        
        versions_layout.addWidget(self.show_release)
        versions_layout.addWidget(self.show_snapshot)
        versions_layout.addWidget(self.show_beta)
        versions_layout.addWidget(self.show_alpha)
        
        layout.addWidget(versions_group)
        
        # Настройки эффектов
        effects_group = QGroupBox("Настройки эффектов")
        effects_layout = QVBoxLayout(effects_group)
        
        # Выбор эффекта
        effect_layout = QHBoxLayout()
        effect_layout.addWidget(QLabel("Эффект:"))
        self.effect_combo = QComboBox()
        self.effect_combo.addItems([
            "Снежинки", "Матрица", "Частицы", "Звёздное небо", 
            "Дождь", "Пузыри", "Огонь", "Случайный", "Отключено"
        ])
        self.effect_combo.setCurrentText(self.settings.value('selected_effect', "Случайный"))
        effect_layout.addWidget(self.effect_combo)
        effects_layout.addLayout(effect_layout)
        
        # Настройки снежинок
        snowflake_layout = QHBoxLayout()
        snowflake_layout.addWidget(QLabel("Количество частиц:"))
        self.particle_count = QSpinBox()
        self.particle_count.setRange(50, 500)
        self.particle_count.setValue(self.settings.value('particle_count', 100, int))
        snowflake_layout.addWidget(self.particle_count)
        effects_layout.addLayout(snowflake_layout)
        
        # Скорость эффектов
        effect_speed_layout = QHBoxLayout()
        effect_speed_layout.addWidget(QLabel("Скорость эффектов:"))
        self.effect_speed = QSlider(Qt.Horizontal)
        self.effect_speed.setRange(1, 200)
        self.effect_speed.setValue(self.settings.value('effect_speed', 100, int))
        effect_speed_layout.addWidget(self.effect_speed)
        self.effect_speed_label = QLabel(f"{self.effect_speed.value()}%")
        self.effect_speed.valueChanged.connect(lambda v: self.effect_speed_label.setText(f"{v}%"))
        effect_speed_layout.addWidget(self.effect_speed_label)
        effects_layout.addLayout(effect_speed_layout)
        
        # Размер частиц
        particle_size_layout = QHBoxLayout()
        particle_size_layout.addWidget(QLabel("Размер частиц:"))
        self.particle_size = QSlider(Qt.Horizontal)
        self.particle_size.setRange(1, 200)
        self.particle_size.setValue(self.settings.value('particle_size', 100, int))
        particle_size_layout.addWidget(self.particle_size)
        self.particle_size_label = QLabel(f"{self.particle_size.value()}%")
        self.particle_size.valueChanged.connect(lambda v: self.particle_size_label.setText(f"{v}%"))
        particle_size_layout.addWidget(self.particle_size_label)
        effects_layout.addLayout(particle_size_layout)
        
        # Прозрачность эффектов
        effect_opacity_layout = QHBoxLayout()
        effect_opacity_layout.addWidget(QLabel("Прозрачность:"))
        self.effect_opacity = QSlider(Qt.Horizontal)
        self.effect_opacity.setRange(1, 100)
        self.effect_opacity.setValue(self.settings.value('effect_opacity', 70, int))
        effect_opacity_layout.addWidget(self.effect_opacity)
        self.effect_opacity_label = QLabel(f"{self.effect_opacity.value()}%")
        self.effect_opacity.valueChanged.connect(lambda v: self.effect_opacity_label.setText(f"{v}%"))
        effect_opacity_layout.addWidget(self.effect_opacity_label)
        effects_layout.addLayout(effect_opacity_layout)
        
        # Дополнительные настройки эффектов
        self.effect_glow = QCheckBox("Свечение частиц")
        self.effect_glow.setChecked(self.settings.value('effect_glow', True, bool))
        effects_layout.addWidget(self.effect_glow)
        
        self.effect_trails = QCheckBox("Следы за частицами")
        self.effect_trails.setChecked(self.settings.value('effect_trails', True, bool))
        effects_layout.addWidget(self.effect_trails)
        
        self.effect_rotation = QCheckBox("Вращение частиц")
        self.effect_rotation.setChecked(self.settings.value('effect_rotation', True, bool))
        effects_layout.addWidget(self.effect_rotation)
        
        self.effect_interaction = QCheckBox("Взаимодействие с курсором")
        self.effect_interaction.setChecked(self.settings.value('effect_interaction', True, bool))
        effects_layout.addWidget(self.effect_interaction)
        
        layout.addWidget(effects_group)

        # Настройки цвета
        color_group = QGroupBox("Цветовая схема")
        color_layout = QVBoxLayout(color_group)
        
        self.color_combo = QComboBox()
        self.colors = {
            "Красный": "#ff3333",
            "Синий": "#3333ff",
            "Зеленый": "#33ff33",
            "Фиолетовый": "#9933ff",
            "Оранжевый": "#ff9933",
            "Бирюзовый": "#33ffff",
            "Лавандовый": "#E6E6FA",
            "Сиреневый": "#C8A2C8",
            "Розовый": "#FFC0CB",
            "Малиновый": "#DC143C",
            "Индиго": "#4B0082",
            "Аквамарин": "#7FFFD4",
            "Коралловый": "#FF7F50",
            "Лаймовый": "#32CD32",
            "Персиковый": "#FFDAB9",
            "Золотой": "#FFD700",
            "Сапфировый": "#082567",
            "Изумрудный": "#50C878",
            "Рубиновый": "#E0115F",
            "Аметистовый": "#9966CC",
            "Топазовый": "#FFC87C",
            "Янтарный": "#FFBF00",
            "Нефритовый": "#00A86B",
            "Опаловый": "#A8C3BC",
            "Гранатовый": "#A42A04",
            "Бирюзовый океан": "#48D1CC",
            "Лунный камень": "#E6E6FA",
            "Жемчужный": "#FDEEF4",
            "Небесный": "#87CEEB",
            "Закатный": "#FAD6A5",
            "Рассветный": "#FF7F50",
            "Полночный": "#191970",
            "Лесной": "#228B22",
            "Пустынный": "#DEB887",
            "Вулканический": "#B22222",
            "Ледяной": "#E0FFFF",
            "Космический": "#483D8B",
            "Радужный": "#FF1493",
            "Неоновый": "#00FF7F"
        }
        self.color_combo.addItems(self.colors.keys())
        current_color = self.settings.value('accent_color', "Красный")
        self.color_combo.setCurrentText(current_color)
        color_layout.addWidget(QLabel("Основной цвет:"))
        color_layout.addWidget(self.color_combo)

        self.use_gradient = QCheckBox("Использовать градиент")
        self.use_gradient.setChecked(self.settings.value('use_gradient', False, bool))
        color_layout.addWidget(self.use_gradient)

        self.gradient_color_combo = QComboBox()
        self.gradient_color_combo.addItems(self.colors.keys())
        gradient_color = self.settings.value('gradient_color', "Синий")
        self.gradient_color_combo.setCurrentText(gradient_color)
        color_layout.addWidget(QLabel("Второй цвет градиента:"))
        color_layout.addWidget(self.gradient_color_combo)
        
        # Дополнительные настройки градиента
        gradient_settings_layout = QVBoxLayout()
        
        # Направление градиента
        gradient_direction_layout = QHBoxLayout()
        gradient_direction_layout.addWidget(QLabel("Направление градиента:"))
        self.gradient_direction = QComboBox()
        self.gradient_direction.addItems([
            "Горизонтальное", "Вертикальное", "Диагональное ↘", 
            "Диагональное ↙", "Радиальное", "Случайное"
        ])
        self.gradient_direction.setCurrentText(self.settings.value('gradient_direction', "Горизонтальное"))
        gradient_direction_layout.addWidget(self.gradient_direction)
        gradient_settings_layout.addLayout(gradient_direction_layout)
        
        # Интенсивность градиента
        gradient_intensity_layout = QHBoxLayout()
        gradient_intensity_layout.addWidget(QLabel("Интенсивность градиента:"))
        self.gradient_intensity = QSlider(Qt.Horizontal)
        self.gradient_intensity.setRange(1, 100)
        self.gradient_intensity.setValue(self.settings.value('gradient_intensity', 50, int))
        gradient_intensity_layout.addWidget(self.gradient_intensity)
        self.gradient_intensity_label = QLabel(f"{self.gradient_intensity.value()}%")
        self.gradient_intensity.valueChanged.connect(
            lambda v: self.gradient_intensity_label.setText(f"{v}%")
        )
        gradient_intensity_layout.addWidget(self.gradient_intensity_label)
        gradient_settings_layout.addLayout(gradient_intensity_layout)
        
        color_layout.addLayout(gradient_settings_layout)
        
        layout.addWidget(color_group)
        
        return tab

    def create_graphics_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Настройки окна
        window_group = QGroupBox("Окно")
        window_layout = QVBoxLayout(window_group)
        
        self.fullscreen = QCheckBox("Полноэкранный режим")
        self.fullscreen.setChecked(self.settings.value('fullscreen', False, bool))
        window_layout.addWidget(self.fullscreen)
        
        resolution_layout = QHBoxLayout()
        resolution_layout.addWidget(QLabel("Разрешение:"))
        self.resolution_combo = QComboBox()
        resolutions = ["1920x1080", "1600x900", "1366x768", "1280x720"]
        self.resolution_combo.addItems(resolutions)
        self.resolution_combo.setCurrentText(self.settings.value('resolution', "1280x720"))
        resolution_layout.addWidget(self.resolution_combo)
        window_layout.addLayout(resolution_layout)
        
        layout.addWidget(window_group)
        
        # Настройки графики
        graphics_settings_group = QGroupBox("Настройки графики")
        graphics_settings_layout = QVBoxLayout(graphics_settings_group)
        
        # Качество графики
        graphics_quality_layout = QHBoxLayout()
        graphics_quality_layout.addWidget(QLabel("Качество графики:"))
        self.graphics_quality = QComboBox()
        qualities = ["Минимальное", "Низкое", "Среднее", "Высокое", "Ультра"]
        self.graphics_quality.addItems(qualities)
        self.graphics_quality.setCurrentText(self.settings.value('graphics_quality', "Среднее"))
        graphics_quality_layout.addWidget(self.graphics_quality)
        graphics_settings_layout.addLayout(graphics_quality_layout)
        
        # Дистанция прорисовки
        render_distance_layout = QHBoxLayout()
        render_distance_layout.addWidget(QLabel("Дистанция прорисовки:"))
        self.render_distance = QSpinBox()
        self.render_distance.setRange(2, 32)
        self.render_distance.setValue(self.settings.value('render_distance', 8, int))
        render_distance_layout.addWidget(self.render_distance)
        graphics_settings_layout.addLayout(render_distance_layout)
        
        # Частота кадров
        fps_layout = QHBoxLayout()
        fps_layout.addWidget(QLabel("Ограничение FPS:"))
        self.fps_limit = QSpinBox()
        self.fps_limit.setRange(30, 1000)
        self.fps_limit.setValue(self.settings.value('fps_limit', 60, int))
        fps_layout.addWidget(self.fps_limit)
        graphics_settings_layout.addLayout(fps_layout)
        
        # Дополнительные настройки графики
        self.vsync = QCheckBox("Вертикальная синхронизация")
        self.vsync.setChecked(self.settings.value('vsync', True, bool))
        graphics_settings_layout.addWidget(self.vsync)
        
        self.particles = QCheckBox("Частицы")
        self.particles.setChecked(self.settings.value('particles', True, bool))
        graphics_settings_layout.addWidget(self.particles)
        
        self.smooth_lighting = QCheckBox("Плавное освещение")
        self.smooth_lighting.setChecked(self.settings.value('smooth_lighting', True, bool))
        graphics_settings_layout.addWidget(self.smooth_lighting)
        
        self.clouds = QCheckBox("Облака")
        self.clouds.setChecked(self.settings.value('clouds', True, bool))
        graphics_settings_layout.addWidget(self.clouds)
        
        layout.addWidget(graphics_settings_group)
        
        return tab

    def create_sound_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Общие настройки звука
        sound_group = QGroupBox("Общие настройки звука")
        sound_group_layout = QVBoxLayout(sound_group)
        
        # Общая громкость
        master_volume_layout = QHBoxLayout()
        master_volume_layout.addWidget(QLabel("Общая громкость:"))
        self.master_volume = QSlider(Qt.Horizontal)
        self.master_volume.setRange(0, 100)
        self.master_volume.setValue(self.settings.value('master_volume', 100, int))
        master_volume_layout.addWidget(self.master_volume)
        self.master_volume_label = QLabel(f"{self.master_volume.value()}%")
        master_volume_layout.addWidget(self.master_volume_label)
        sound_group_layout.addLayout(master_volume_layout)
        
        # Музыка
        music_volume_layout = QHBoxLayout()
        music_volume_layout.addWidget(QLabel("Громкость музыки:"))
        self.music_volume = QSlider(Qt.Horizontal)
        self.music_volume.setRange(0, 100)
        self.music_volume.setValue(self.settings.value('music_volume', 70, int))
        music_volume_layout.addWidget(self.music_volume)
        self.music_volume_label = QLabel(f"{self.music_volume.value()}%")
        music_volume_layout.addWidget(self.music_volume_label)
        sound_group_layout.addLayout(music_volume_layout)
        
        layout.addWidget(sound_group)
        
        # Дополнительные настройки звука
        sound_advanced_group = QGroupBox("Дополнительные настройки")
        sound_advanced_layout = QVBoxLayout(sound_advanced_group)
        
        self.sound_subtitles = QCheckBox("Показывать субтитры звуков")
        self.sound_subtitles.setChecked(self.settings.value('sound_subtitles', False, bool))
        sound_advanced_layout.addWidget(self.sound_subtitles)
        
        self.sound_device_layout = QHBoxLayout()
        self.sound_device_layout.addWidget(QLabel("Устройство вывода:"))
        self.sound_device = QComboBox()
        self.sound_device.addItems(["Системное по умолчанию", "Наушники", "Динамики"])
        self.sound_device.setCurrentText(self.settings.value('sound_device', "Системное по умолчанию"))
        self.sound_device_layout.addWidget(self.sound_device)
        sound_advanced_layout.addLayout(self.sound_device_layout)
        
        layout.addWidget(sound_advanced_group)
        
        return tab

    def create_controls_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Основные настройки управления
        controls_group = QGroupBox("Основные настройки")
        controls_group_layout = QVBoxLayout(controls_group)
        
        self.mouse_sensitivity = QHBoxLayout()
        self.mouse_sensitivity.addWidget(QLabel("Чувствительность мыши:"))
        self.sensitivity_slider = QSlider(Qt.Horizontal)
        self.sensitivity_slider.setRange(1, 200)
        self.sensitivity_slider.setValue(self.settings.value('mouse_sensitivity', 100, int))
        self.mouse_sensitivity.addWidget(self.sensitivity_slider)
        self.sensitivity_label = QLabel(f"{self.sensitivity_slider.value()}%")
        self.mouse_sensitivity.addWidget(self.sensitivity_label)
        controls_group_layout.addLayout(self.mouse_sensitivity)
        
        self.invert_mouse = QCheckBox("Инвертировать мышь")
        self.invert_mouse.setChecked(self.settings.value('invert_mouse', False, bool))
        controls_group_layout.addWidget(self.invert_mouse)
        
        layout.addWidget(controls_group)
        
        return tab

    def create_network_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Настройки прокси
        proxy_group = QGroupBox("Настройки прокси")
        proxy_layout = QVBoxLayout(proxy_group)
        
        self.use_proxy = QCheckBox("Использовать прокси")
        self.use_proxy.setChecked(self.settings.value('use_proxy', False, bool))
        proxy_layout.addWidget(self.use_proxy)
        
        proxy_host_layout = QHBoxLayout()
        proxy_host_layout.addWidget(QLabel("Хост:"))
        self.proxy_host = QLineEdit()
        self.proxy_host.setText(self.settings.value('proxy_host', ""))
        proxy_host_layout.addWidget(self.proxy_host)
        proxy_layout.addLayout(proxy_host_layout)
        
        proxy_port_layout = QHBoxLayout()
        proxy_port_layout.addWidget(QLabel("Порт:"))
        self.proxy_port = QSpinBox()
        self.proxy_port.setRange(0, 65535)
        self.proxy_port.setValue(self.settings.value('proxy_port', 8080, int))
        proxy_port_layout.addWidget(self.proxy_port)
        proxy_layout.addLayout(proxy_port_layout)
        
        layout.addWidget(proxy_group)
        
        # Настройки подключения
        connection_group = QGroupBox("Настройки подключения")
        connection_layout = QVBoxLayout(connection_group)
        
        self.max_players_layout = QHBoxLayout()
        self.max_players_layout.addWidget(QLabel("Максимум игроков в сети:"))
        self.max_players = QSpinBox()
        self.max_players.setRange(2, 100)
        self.max_players.setValue(self.settings.value('max_players', 8, int))
        self.max_players_layout.addWidget(self.max_players)
        connection_layout.addLayout(self.max_players_layout)
        
        self.server_port_layout = QHBoxLayout()
        self.server_port_layout.addWidget(QLabel("Порт сервера:"))
        self.server_port = QSpinBox()
        self.server_port.setRange(1024, 65535)
        self.server_port.setValue(self.settings.value('server_port', 25565, int))
        self.server_port_layout.addWidget(self.server_port)
        connection_layout.addLayout(self.server_port_layout)
        
        layout.addWidget(connection_group)
        
        return tab

    def create_java_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Настройки Java
        java_group = QGroupBox("Настройки Java")
        java_layout_group = QVBoxLayout(java_group)
        
        # Путь к Java
        java_path_layout = QHBoxLayout()
        java_path_layout.addWidget(QLabel("Путь к Java:"))
        self.java_path = QLineEdit()
        self.java_path.setText(self.settings.value('java_path', ""))
        java_path_layout.addWidget(self.java_path)
        browse_btn = QPushButton("Обзор")
        browse_btn.clicked.connect(self.browse_java)
        java_path_layout.addWidget(browse_btn)
        java_layout_group.addLayout(java_path_layout)
        
        # Дополнительные аргументы JVM
        java_args_layout = QHBoxLayout()
        java_args_layout.addWidget(QLabel("Аргументы JVM:"))
        self.java_args = QLineEdit()
        self.java_args.setText(self.settings.value('java_args', "-XX:+UseG1GC -XX:+ParallelRefProcEnabled"))
        java_args_layout.addWidget(self.java_args)
        java_layout_group.addLayout(java_args_layout)
        
        # Версия Java
        java_version_layout = QHBoxLayout()
        java_version_layout.addWidget(QLabel("Версия Java:"))
        self.java_version = QComboBox()
        self.java_version.addItems(["Java 8", "Java 11", "Java 16", "Java 17", "Java 18+"])
        self.java_version.setCurrentText(self.settings.value('java_version', "Java 17"))
        java_version_layout.addWidget(self.java_version)
        java_layout_group.addLayout(java_version_layout)
        
        layout.addWidget(java_group)
        
        return tab

    def browse_java(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Выберите исполняемый файл Java")
        if file_name:
            self.java_path.setText(file_name)

    def save_settings(self):
        # Сохранение общих настроек
        self.settings.setValue('show_release', self.show_release.isChecked())
        self.settings.setValue('show_snapshot', self.show_snapshot.isChecked())
        self.settings.setValue('show_beta', self.show_beta.isChecked())
        self.settings.setValue('show_alpha', self.show_alpha.isChecked())
        
        # Сохранение настроек эффектов
        self.settings.setValue('selected_effect', self.effect_combo.currentText())
        self.settings.setValue('particle_count', self.particle_count.value())
        self.settings.setValue('effect_speed', self.effect_speed.value())
        self.settings.setValue('particle_size', self.particle_size.value())
        self.settings.setValue('effect_opacity', self.effect_opacity.value())
        self.settings.setValue('effect_glow', self.effect_glow.isChecked())
        self.settings.setValue('effect_trails', self.effect_trails.isChecked())
        self.settings.setValue('effect_rotation', self.effect_rotation.isChecked())
        self.settings.setValue('effect_interaction', self.effect_interaction.isChecked())
        
        # Сохранение настроек цветов
        self.settings.setValue('accent_color', self.color_combo.currentText())
        self.settings.setValue('use_gradient', self.use_gradient.isChecked())
        self.settings.setValue('gradient_color', self.gradient_color_combo.currentText())
        self.settings.setValue('gradient_direction', self.gradient_direction.currentText())
        self.settings.setValue('gradient_intensity', self.gradient_intensity.value())
        
        # Сохранение настроек графики
        self.settings.setValue('fullscreen', self.fullscreen.isChecked())
        self.settings.setValue('resolution', self.resolution_combo.currentText())
        self.settings.setValue('graphics_quality', self.graphics_quality.currentText())
        self.settings.setValue('render_distance', self.render_distance.value())
        self.settings.setValue('fps_limit', self.fps_limit.value())
        self.settings.setValue('vsync', self.vsync.isChecked())
        self.settings.setValue('particles', self.particles.isChecked())
        self.settings.setValue('smooth_lighting', self.smooth_lighting.isChecked())
        self.settings.setValue('clouds', self.clouds.isChecked())
        
        # Сохранение настроек звука
        self.settings.setValue('master_volume', self.master_volume.value())
        self.settings.setValue('music_volume', self.music_volume.value())
        self.settings.setValue('sound_subtitles', self.sound_subtitles.isChecked())
        self.settings.setValue('sound_device', self.sound_device.currentText())
        
        # Сохранение настроек управления
        self.settings.setValue('mouse_sensitivity', self.sensitivity_slider.value())
        self.settings.setValue('invert_mouse', self.invert_mouse.isChecked())
        
        # Сохранение сетевых настроек
        self.settings.setValue('use_proxy', self.use_proxy.isChecked())
        self.settings.setValue('proxy_host', self.proxy_host.text())
        self.settings.setValue('proxy_port', self.proxy_port.value())
        self.settings.setValue('max_players', self.max_players.value())
        self.settings.setValue('server_port', self.server_port.value())
        
        # Сохранение настроек Java
        self.settings.setValue('java_path', self.java_path.text())
        self.settings.setValue('java_args', self.java_args.text())
        self.settings.setValue('java_version', self.java_version.currentText())
        
        # Применяем эффекты сразу после сохранения
        if isinstance(self.parent(), MinecraftLauncher):
            self.parent().show_selected_effect(self.effect_combo.currentText())
            self.parent().apply_color_scheme()
        
        self.accept()

class AnimatedProgressBar(QProgressBar):
    def __init__(self):
        super().__init__()
        self.setStyleSheet("""
            QProgressBar {
                background-color: #2d2d2d;
                border: 2px solid #1db954;
                border-radius: 10px;
                height: 20px;
                text-align: center;
                color: white;
            }
            QProgressBar::chunk {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 #1db954,
                    stop:0.5 #3dd975,
                    stop:1 #1db954);
                border-radius: 8px;
            }
        """)
        
        # Анимация прогресса
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.update_animation)
        self.animation_offset = 0
        
    def update_animation(self):
        self.animation_offset = (self.animation_offset + 1) % 100
        self.update()

class ModManager(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Менеджер модов")
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Заголовок
        title = QLabel("Mod Manager")
        title.setStyleSheet("font-size: 24px; color: #1db954;")
        layout.addWidget(title)
        
        # Список модов
        self.mod_list = QListWidget()
        self.mod_list.setStyleSheet("""
            QListWidget {
                background-color: #2d2d2d;
                border: 2px solid #1db954;
                border-radius: 10px;
            }
            QListWidget::item {
                color: white;
                padding: 10px;
                border-bottom: 1px solid #3d3d3d;
            }
            QListWidget::item:selected {
                background-color: #1db954;
            }
        """)
        layout.addWidget(self.mod_list)
        
        # Кнопки управления модами
        buttons_layout = QHBoxLayout()
        
        self.add_mod_btn = QPushButton("Добавить мод")
        self.remove_mod_btn = QPushButton("Удалить мод")
        self.enable_mod_btn = QPushButton("Включить")
        self.disable_mod_btn = QPushButton("Отключить")
        
        for btn in [self.add_mod_btn, self.remove_mod_btn, self.enable_mod_btn, self.disable_mod_btn]:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #1db954;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 5px;
                }
                QPushButton:hover {
                    background-color: #3dd975;
                }
            """)
            buttons_layout.addWidget(btn)
            
        layout.addLayout(buttons_layout)

    def refresh_mods(self):
        self.mod_list.clear()
        if os.path.exists(self.mods_dir):
            for mod in os.listdir(self.mods_dir):
                if mod.endswith('.jar'):
                    self.mod_list.addItem(mod)
                    
    def add_mod(self):
        file, _ = QFileDialog.getOpenFileName(self, "Выберите мод", "", "JAR files (*.jar)")
        if file:
            shutil.copy2(file, os.path.join(self.mods_dir, os.path.basename(file)))
            self.refresh_mods()
            
    def remove_mod(self):
        current = self.mod_list.currentItem()
        if current:
            os.remove(os.path.join(self.mods_dir, current.text()))
            self.refresh_mods()
            
    def enable_mod(self):
        current = self.mod_list.currentItem()
        if current:
            name = current.text()
            if name.endswith('.jar.disabled'):
                new_name = name[:-9]
                os.rename(os.path.join(self.mods_dir, name), os.path.join(self.mods_dir, new_name))
                self.refresh_mods()
                
    def disable_mod(self):
        current = self.mod_list.currentItem()
        if current:
            name = current.text()
            if name.endswith('.jar'):
                new_name = name + '.disabled'
                os.rename(os.path.join(self.mods_dir, name), os.path.join(self.mods_dir, new_name))
                self.refresh_mods()

class ModLoaderManager:
    def __init__(self, minecraft_dir):
        self.minecraft_dir = minecraft_dir
        self.loaders_dir = os.path.join(minecraft_dir, "loaders")
        os.makedirs(self.loaders_dir, exist_ok=True)
        
        # Создаем директории для загрузчиков
        self.fabric_dir = os.path.join(self.loaders_dir, "fabric")
        self.forge_dir = os.path.join(self.loaders_dir, "forge")
        
        for directory in [self.fabric_dir, self.forge_dir]:
            os.makedirs(directory, exist_ok=True)

    def get_forge_versions(self, minecraft_version):
        try:
            forge_version = minecraft_launcher_lib.forge.find_forge_version(minecraft_version)
            if forge_version is None:
                print(f"Версия Minecraft {minecraft_version} не поддерживается Forge")
                return []
            return [forge_version]
        except Exception as e:
            print(f"Ошибка получения версий Forge: {e}")
            return []

    def get_fabric_versions(self, minecraft_version):
        try:
            fabric_versions = minecraft_launcher_lib.fabric.get_all_loader_versions()
            compatible_versions = []
            for version in fabric_versions:
                if version.get("stable", False):  # Берем только стабильные версии
                    compatible_versions.append(version["version"])
            return compatible_versions
        except Exception as e:
            print(f"Ошибка получения версий Fabric: {e}")
            return []

    def install_forge(self, minecraft_version, forge_version, callback=None):
        try:
            # Очищаем кэш версии
            version_path = os.path.join(self.minecraft_dir, "versions", minecraft_version)
            forge_path = os.path.join(self.minecraft_dir, "versions", f"{minecraft_version}-forge-{forge_version}")
            
            # Удаляем старые файлы Forge, если они существуют
            if os.path.exists(forge_path):
                shutil.rmtree(forge_path)
            
            # Создаем директории
            os.makedirs(version_path, exist_ok=True)
            os.makedirs(forge_path, exist_ok=True)
            
            # Устанавливаем базовую версию Minecraft
            if callback:
                callback["setStatus"]("Установка базовой версии Minecraft...")
                callback["setProgress"](0.1)  # 10% прогресса
                
            minecraft_launcher_lib.install.install_minecraft_version(
                minecraft_version,
                self.minecraft_dir,
                callback=callback
            )
            
            # Проверяем установку базовой версии
            jar_path = os.path.join(version_path, f"{minecraft_version}.jar")
            json_path = os.path.join(version_path, f"{minecraft_version}.json")
            if not os.path.exists(jar_path) or not os.path.exists(json_path):
                raise Exception("Не удалось установить базовую версию Minecraft")
            
            # Устанавливаем Forge
            if callback:
                callback["setStatus"]("Установка Forge...")
                callback["setProgress"](0.5)  # 50% прогресса
            
            try:
                # Устанавливаем Forge используя правильный метод
                minecraft_launcher_lib.forge.install_forge_version(
                    forge_version,
                    self.minecraft_dir,
                    callback=callback
                )
                
                # Проверяем наличие файлов Forge после установки
                forge_json = os.path.join(forge_path, f"{minecraft_version}-forge-{forge_version}.json")
                forge_jar = os.path.join(forge_path, f"{minecraft_version}-forge-{forge_version}.jar")
                
                # Если файлы не найдены в первом пути, проверяем альтернативный путь
                if not os.path.exists(forge_json) or not os.path.exists(forge_jar):
                    alt_forge_path = os.path.join(self.minecraft_dir, "versions", f"forge-{minecraft_version}")
                    alt_forge_json = os.path.join(alt_forge_path, f"forge-{minecraft_version}.json")
                    alt_forge_jar = os.path.join(alt_forge_path, f"forge-{minecraft_version}.jar")
                    
                    if os.path.exists(alt_forge_json) and os.path.exists(alt_forge_jar):
                        # Копируем файлы в правильное место
                        os.makedirs(forge_path, exist_ok=True)
                        shutil.copy2(alt_forge_json, forge_json)
                        shutil.copy2(alt_forge_jar, forge_jar)
                    else:
                        # Проверяем еще один возможный путь
                        legacy_forge_path = os.path.join(self.minecraft_dir, "versions", f"{minecraft_version}-forge-{forge_version}")
                        legacy_forge_json = os.path.join(legacy_forge_path, f"{minecraft_version}-forge-{forge_version}.json")
                        legacy_forge_jar = os.path.join(legacy_forge_path, f"{minecraft_version}-forge-{forge_version}.jar")
                        
                        if os.path.exists(legacy_forge_json) and os.path.exists(legacy_forge_jar):
                            # Копируем файлы в правильное место
                            os.makedirs(forge_path, exist_ok=True)
                            shutil.copy2(legacy_forge_json, forge_json)
                            shutil.copy2(legacy_forge_jar, forge_jar)
                        else:
                            raise Exception("Не удалось найти установленные файлы Forge")
                
                if callback:
                    callback["setStatus"]("Forge успешно установлен!")
                    callback["setProgress"](1.0)  # 100% прогресса
                    
                return True
                
            except Exception as forge_error:
                print(f"Ошибка при установке Forge: {forge_error}")
                raise Exception(f"Не удалось установить Forge: {forge_error}")
                
        except Exception as e:
            print(f"Ошибка установки Forge: {e}")
            if callback:
                callback["setStatus"](f"Ошибка: {str(e)}")
                callback["setProgress"](0.0)  # Сбрасываем прогресс при ошибке
            return False

    def install_fabric(self, minecraft_version, fabric_version, callback=None):
        try:
            minecraft_launcher_lib.fabric.install_fabric(
                minecraft_version,
                self.minecraft_dir,
                callback=callback
            )
            return True
        except Exception as e:
            print(f"Ошибка установки Fabric: {e}")
            return False

    def is_forge_installed(self, version):
        forge_json = os.path.join(self.minecraft_dir, "versions", f"forge-{version}", f"forge-{version}.json")
        return os.path.exists(forge_json)

    def is_fabric_installed(self, version):
        fabric_json = os.path.join(self.minecraft_dir, "versions", f"fabric-loader-{version}", f"fabric-loader-{version}.json")
        return os.path.exists(fabric_json)

    def is_optifine_installed(self, version):
        optifine_json = os.path.join(self.minecraft_dir, "versions", f"OptiFine_{version}", f"OptiFine_{version}.json")
        return os.path.exists(optifine_json)

class LoaderInstallThread(QThread):
    progress = Signal(int)
    status = Signal(str)
    finished = Signal()
    error = Signal(str)
    version_list = Signal(list)

    def __init__(self, loader_type, version, mod_loader_manager):
        super().__init__()
        self.loader_type = loader_type
        self.version = version
        self.mod_loader_manager = mod_loader_manager
        self.action = "install"
        self.loader_version = None
        self._is_running = False

    def set_action(self, action):
        self.action = action

    def set_loader_version(self, version):
        self.loader_version = version

    def run(self):
        try:
            self._is_running = True
            success = False
            
            if self.action == "get_versions":
                if self.loader_type == "Fabric":
                    versions = self.mod_loader_manager.get_fabric_versions(self.version)
                    if versions:
                        self.version_list.emit(versions)
                    else:
                        self.error.emit("Не удалось получить версии Fabric")
                elif self.loader_type == "Forge":
                    versions = self.mod_loader_manager.get_forge_versions(self.version)
                    if versions:
                        self.version_list.emit(versions)
                    else:
                        self.error.emit("Эта версия Minecraft не поддерживается Forge")
            else:  # install
                callback = {
                    "setProgress": lambda x: self.progress.emit(int(x * 100)),
                    "setStatus": lambda x: self.status.emit(x)
                }
                
                if self.loader_type == "Fabric":
                    self.status.emit("Установка Fabric...")
                    self.progress.emit(0)  # Начальный прогресс
                    success = self.mod_loader_manager.install_fabric(
                        self.version,
                        self.loader_version,
                        callback=callback
                    )
                elif self.loader_type == "Forge":
                    self.status.emit("Установка Forge...")
                    self.progress.emit(0)  # Начальный прогресс
                    success = self.mod_loader_manager.install_forge(
                        self.version,
                        self.loader_version,
                        callback=callback
                    )
                
                if success:
                    self.progress.emit(100)  # Убеждаемся, что прогресс достиг 100%
                    self.finished.emit()
                else:
                    self.progress.emit(0)  # Сбрасываем прогресс при ошибке
                    self.error.emit(f"Не удалось установить {self.loader_type}")
                    
        except Exception as e:
            self.progress.emit(0)  # Сбрасываем прогресс при ошибке
            self.error.emit(str(e))
        finally:
            self._is_running = False
            
    def stop(self):
        self._is_running = False
        self.wait()
        
    def __del__(self):
        self.stop()

class MinecraftLauncher(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nova Launcher")
        self.setMinimumSize(1200, 800)
        
        # Установка иконки окна
        icon = QIcon("resources/icon.ico")
        self.setWindowIcon(icon)
        
        # Инициализация менеджеров
        self.profile_manager = ProfileManager()
        self.server_manager = ServerManager()
        self.mod_loader_manager = ModLoaderManager(os.path.join(os.path.dirname(os.path.abspath(__file__)), "minecraft"))
        
        self.settings = QSettings('RadeonLauncher', 'Settings')
        self.mods_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minecraft", "mods")
        os.makedirs(self.mods_directory, exist_ok=True)
        self.resourcepacks_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minecraft", "resourcepacks")
        os.makedirs(self.resourcepacks_directory, exist_ok=True)
        
        # Добавляем эффекты
        self.setup_effects()
        
        self.loader_install_thread = None
        self.setup_ui()
        self.setup_loader_connections()
        self.apply_color_scheme()
        self.display_minecraft_news()

    def setup_loader_connections(self):
        # Подключаем сигналы для загрузчика модов
        self.version_combo.currentTextChanged.connect(self.on_version_changed)
        self.loader_version_combo.currentTextChanged.connect(self.on_loader_version_changed)

    def on_version_changed(self, version):
        if not version:
            return

        # Обновляем список доступных загрузчиков
        self.loader_version_combo.clear()
        self.loader_version_combo.addItem("Vanilla")
        
        # Получаем версии Forge
        forge_versions = self.mod_loader_manager.get_forge_versions(version)
        for forge_version in forge_versions:
            self.loader_version_combo.addItem(f"Forge {forge_version}")
            
        # Получаем версии Fabric
        fabric_versions = self.mod_loader_manager.get_fabric_versions(version)
        for fabric_version in fabric_versions:
            self.loader_version_combo.addItem(f"Fabric {fabric_version}")

    def on_loader_version_changed(self, loader_version):
        if not loader_version or loader_version == "Vanilla":
                return
                
        # Проверяем, установлен ли уже этот загрузчик
        minecraft_version = self.version_combo.currentText()
        loader_type = loader_version.split()[0]  # Получаем Fabric или Forge
        loader_ver = " ".join(loader_version.split()[1:])  # Получаем версию загрузчика
        
        is_installed = False
        if loader_type == "Forge":
            is_installed = self.mod_loader_manager.is_forge_installed(minecraft_version)
        elif loader_type == "Fabric":
            is_installed = self.mod_loader_manager.is_fabric_installed(minecraft_version)

    def on_loader_error(self, error_message):
        self.progress_group.hide()
        QMessageBox.critical(self, "Ошибка", f"Ошибка установки загрузчика: {error_message}")

    def display_minecraft_news(self):
        news_items = [
            {
                "title": "Minecraft 1.20.5 - Обновление!",
                "description": "Новое обновление включает улучшения производительности, исправления багов и новые биомы.",
                "date": "2024"
            },
            {
                "title": "Новые мобы в Minecraft",
                "description": "Встречайте новых обитателей мира Minecraft! Добавлены новые виды существ и их поведение.",
                "date": "2024"
            },
            {
                "title": "Улучшения редстоуна",
                "description": "Механизмы стали еще интереснее! Новые компоненты и возможности для создания сложных устройств.",
                "date": "2024"
            },
            {
                "title": "Обновление пещер и гор",
                "description": "Исследуйте обновленные пещерные системы и величественные горные массивы.",
                "date": "2024"
            }
        ]

        # Очищаем существующие новости
        for i in reversed(range(self.news_layout.count())): 
            self.news_layout.itemAt(i).widget().setParent(None)

        # Добавляем новости
        for news in news_items:
            news_widget = QWidget()
            news_widget_layout = QVBoxLayout(news_widget)
            
            title = QLabel(news["title"])
            title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1db954;")
            
            description = QLabel(news["description"])
            description.setWordWrap(True)
            
            date = QLabel(news["date"])
            date.setStyleSheet("color: gray;")
            
            news_widget_layout.addWidget(title)
            news_widget_layout.addWidget(description)
            news_widget_layout.addWidget(date)
            
            self.news_layout.addWidget(news_widget)

    def setup_effects(self):
        # Создаем все эффекты
        self.snowfall = SnowfallEffect(self)
        self.matrix = MatrixRainEffect(self)
        self.particles = ParticleEffect(self)
        self.starfield = StarEffect(self)
        self.rain = RainEffect(self)
        self.bubbles = BubbleEffect(self)
        self.fire = FireEffect(self)
        
        # Устанавливаем размеры для всех эффектов
        for effect in [self.snowfall, self.matrix, self.particles, 
                      self.starfield, self.rain, self.bubbles, self.fire]:
            effect.resize(self.size())
            effect.hide()  # Скрываем все эффекты по умолчанию
        
        # Получаем настройки эффектов
        selected_effect = self.settings.value('selected_effect', "Случайный")
        effect_speed = self.settings.value('effect_speed', 100, int)
        particle_count = self.settings.value('particle_count', 100, int)
        particle_size = self.settings.value('particle_size', 100, int)
        effect_opacity = self.settings.value('effect_opacity', 70, int)
        
        # Настройки поведения
        effect_glow = self.settings.value('effect_glow', True, bool)
        effect_trails = self.settings.value('effect_trails', True, bool)
        effect_rotation = self.settings.value('effect_rotation', True, bool)
        effect_interaction = self.settings.value('effect_interaction', True, bool)
        
        # Применяем настройки к таймерам эффектов
        timer_interval = int(50 * (100 / effect_speed))
        for effect in [self.snowfall, self.matrix, self.particles, 
                      self.starfield, self.rain, self.bubbles, self.fire]:
            if hasattr(effect, 'timer'):
                effect.timer.setInterval(timer_interval)
        
        # Устанавливаем выбранный эффект
        if selected_effect == "Случайный":
            self.effect_timer = QTimer(self)
            self.effect_timer.timeout.connect(self.toggle_effects)
            self.effect_timer.start(10000)  # Переключение каждые 10 секунд
            self.current_effect = 0
            self.toggle_effects()
        else:
            self.show_selected_effect(selected_effect)

    def show_selected_effect(self, effect_name):
        # Скрываем все эффекты
        for effect in [self.snowfall, self.matrix, self.particles, 
                      self.starfield, self.rain, self.bubbles, self.fire]:
            effect.hide()
        
        # Показываем выбранный эффект
        if effect_name == "Снежинки":
            self.snowfall.show()
        elif effect_name == "Матрица":
            self.matrix.show()
        elif effect_name == "Частицы":
            self.particles.show()
        elif effect_name == "Звёздное небо":
            self.starfield.show()
        elif effect_name == "Дождь":
            self.rain.show()
        elif effect_name == "Пузыри":
            self.bubbles.show()
        elif effect_name == "Огонь":
            self.fire.show()

    def toggle_effects(self):
        if self.settings.value('selected_effect', "Случайный") == "Случайный":
            # Скрываем все эффекты
            for effect in [self.snowfall, self.matrix, self.particles, 
                          self.starfield, self.rain, self.bubbles, self.fire]:
                effect.hide()
            
            # Показываем следующий эффект
            self.current_effect = (self.current_effect + 1) % 7
            effects = [self.snowfall, self.matrix, self.particles, 
                      self.starfield, self.rain, self.bubbles, self.fire]
            effects[self.current_effect].show()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Обновляем размеры всех эффектов
        for effect in [self.snowfall, self.matrix, self.particles, 
                      self.starfield, self.rain, self.bubbles, self.fire]:
            if hasattr(self, effect.__class__.__name__.lower()):
                effect.resize(self.size())

    def setup_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QHBoxLayout(main_widget)
        layout.setSpacing(0)
        layout.setContentsMargins(0, 0, 0, 0)

        # Сайдбар
        self.sidebar = QWidget()
        self.sidebar.setFixedWidth(450)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setSpacing(15)
        sidebar_layout.setContentsMargins(10, 10, 10, 10)

        # Лого
        logo = QLabel("MINECRAFT")
        logo.setStyleSheet("font-size: 24px; font-weight: bold; padding: 20px 0;")
        logo.setAlignment(Qt.AlignCenter)
        sidebar_layout.addWidget(logo)

        # Профили
        profile_group = QGroupBox("Профили")
        profile_layout = QVBoxLayout(profile_group)
        self.profile_combo = QComboBox()
        
        add_profile_btn = QPushButton("+ Добавить профиль")
        add_profile_btn.clicked.connect(self.add_profile)
        remove_profile_btn = QPushButton("- Удалить")
        remove_profile_btn.clicked.connect(self.remove_profile)
        
        profile_layout.addWidget(self.profile_combo)
        profile_layout.addWidget(add_profile_btn)
        profile_layout.addWidget(remove_profile_btn)
        sidebar_layout.addWidget(profile_group)

        # Версия и загрузчик
        version_group = QGroupBox("Версия")
        version_layout = QVBoxLayout(version_group)
        
        self.version_combo = QComboBox()
        version_layout.addWidget(self.version_combo)
        
        # Добавляем выпадающий список версий загрузчика
        self.loader_version_layout = QHBoxLayout()
        self.loader_version_layout.addWidget(QLabel("Загрузчик:"))
        self.loader_version_combo = QComboBox()
        self.loader_version_combo.addItems(["Vanilla"])  # По умолчанию только Vanilla
        self.loader_version_layout.addWidget(self.loader_version_combo)
        version_layout.addLayout(self.loader_version_layout)
        
        sidebar_layout.addWidget(version_group)
        
        # Кнопка менеджера модов
        mods_btn = QPushButton("🧩 Менеджер модов")
        mods_btn.clicked.connect(self.show_mod_manager)
        sidebar_layout.addWidget(mods_btn)
        
        # Прогресс установки
        self.progress_group = QGroupBox("Прогресс установки")
        self.progress_group.hide()
        progress_layout = QVBoxLayout()
        
        self.status_label = QLabel("Подготовка к установке...")
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)
        self.progress_group.setLayout(progress_layout)
        
        sidebar_layout.addWidget(self.progress_group)

        # Кнопки внизу сайдбара
        sidebar_layout.addStretch()
        
        settings_btn = GlowingButton("⚙ Настройки")
        settings_btn.clicked.connect(self.show_settings)
        sidebar_layout.addWidget(settings_btn)
        
        play_btn = GlowingButton("ИГРАТЬ")
        play_btn.setObjectName("play_btn")
        play_btn.clicked.connect(self.launch_game)
        sidebar_layout.addWidget(play_btn)

        layout.addWidget(self.sidebar)

        # Правая панель с вкладками
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Создаем вкладки
        self.right_tabs = QTabWidget()
        self.right_tabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #404040;
                background: rgba(30, 30, 30, 180);
                border-radius: 8px;
            }
            QTabBar::tab {
                background: rgba(40, 40, 40, 180);
                color: white;
                padding: 8px 20px;
                border: 1px solid #404040;
                border-bottom: none;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: rgba(60, 60, 60, 180);
            }
        """)
        right_layout.addWidget(self.right_tabs)
        layout.addWidget(right_panel)

        # Вкладка новостей
        news_tab = QWidget()
        news_layout = QVBoxLayout(news_tab)
        
        news_group = QGroupBox("Новости Minecraft")
        self.news_layout = QVBoxLayout(news_group)
        self.news_layout.setSpacing(10)
        self.news_layout.setContentsMargins(10, 10, 10, 10)
        
        news_scroll = QScrollArea()
        news_scroll.setWidget(news_group)
        news_scroll.setWidgetResizable(True)
        news_layout.addWidget(news_scroll)
        
        self.right_tabs.addTab(news_tab, "Новости")

        # Вкладка серверов
        self.server_manager = ServerManager()
        servers_tab = ServerListWidget(self.server_manager)
        self.right_tabs.addTab(servers_tab, "Сервера")

        # Вкладка модификаций
        mods_tab = QWidget()
        mods_layout = QVBoxLayout()
        
        # Добавляем группу для управления модами
        mods_group = QGroupBox("Установленные моды")
        mods_group_layout = QVBoxLayout()
        
        # Список модов
        self.mods_list = QListWidget()
        self.mods_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        # Кнопки управления модами
        mods_buttons_layout = QHBoxLayout()
        
        self.add_mod_btn = QPushButton("Добавить мод")
        self.remove_mod_btn = QPushButton("Удалить мод")
        self.enable_mod_btn = QPushButton("Включить")
        self.disable_mod_btn = QPushButton("Отключить")
        
        for btn in [self.add_mod_btn, self.remove_mod_btn, self.enable_mod_btn, self.disable_mod_btn]:
            mods_buttons_layout.addWidget(btn)
        
        # Подключаем сигналы кнопок
        self.add_mod_btn.clicked.connect(self.add_mod)
        self.remove_mod_btn.clicked.connect(self.remove_mod)
        self.enable_mod_btn.clicked.connect(self.enable_mod)
        self.disable_mod_btn.clicked.connect(self.disable_mod)
        
        # Добавляем все элементы в layout
        mods_group_layout.addWidget(self.mods_list)
        mods_group_layout.addLayout(mods_buttons_layout)
        mods_group.setLayout(mods_group_layout)
        
        # Добавляем группу модов в layout вкладки модификаций
        mods_layout.addWidget(mods_group)
        
        # Добавляем вкладку в правую панель
        self.right_tabs.addTab(mods_tab, "Модификации")
        
        # Добавляем вкладку ресурспаков
        resourcepacks_tab = QWidget()
        resourcepacks_layout = QVBoxLayout()
        
        # Группа для управления ресурспаками
        resourcepacks_group = QGroupBox("Ресурспаки")
        resourcepacks_group_layout = QVBoxLayout()
        
        # Список ресурспаков
        self.resourcepacks_list = QListWidget()
        self.resourcepacks_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        
        # Кнопки управления ресурспаками
        resourcepack_buttons_layout = QHBoxLayout()
        
        self.add_resourcepack_btn = QPushButton("Добавить ресурспак")
        self.remove_resourcepack_btn = QPushButton("Удалить")
        self.enable_resourcepack_btn = QPushButton("Включить")
        self.disable_resourcepack_btn = QPushButton("Отключить")
        
        for btn in [self.add_resourcepack_btn, self.remove_resourcepack_btn, 
                    self.enable_resourcepack_btn, self.disable_resourcepack_btn]:
            resourcepack_buttons_layout.addWidget(btn)
        
        # Подключаем сигналы кнопок
        self.add_resourcepack_btn.clicked.connect(self.add_resourcepack)
        self.remove_resourcepack_btn.clicked.connect(self.remove_resourcepack)
        self.enable_resourcepack_btn.clicked.connect(self.enable_resourcepack)
        self.disable_resourcepack_btn.clicked.connect(self.disable_resourcepack)
        
        # Добавляем все элементы в layout
        resourcepacks_group_layout.addWidget(self.resourcepacks_list)
        resourcepacks_group_layout.addLayout(resourcepack_buttons_layout)
        resourcepacks_group.setLayout(resourcepacks_group_layout)
        
        resourcepacks_layout.addWidget(resourcepacks_group)
        resourcepacks_tab.setLayout(resourcepacks_layout)
        
        # Добавляем вкладку в правую панель
        self.right_tabs.addTab(resourcepacks_tab, "Ресурспаки")
        
        # Добавляем вкладку скинов
        skins_tab = QWidget()
        skins_layout = QVBoxLayout()
        
        # Группа для текущего скина
        current_skin_group = QGroupBox("Текущий скин")
        current_skin_layout = QHBoxLayout()
        
        # Превью текущего скина
        self.skin_preview = QLabel()
        self.skin_preview.setFixedSize(128, 256)
        self.skin_preview.setStyleSheet("""
            QLabel {
                background: rgba(40, 40, 40, 180);
                border: 2px solid #404040;
                border-radius: 8px;
            }
        """)
        current_skin_layout.addWidget(self.skin_preview)
        
        # Информация о скине и кнопки управления
        skin_info_layout = QVBoxLayout()
        
        self.skin_name_label = QLabel("Текущий скин: Не выбран")
        skin_info_layout.addWidget(self.skin_name_label)
        
        skin_buttons_layout = QHBoxLayout()
        
        self.change_skin_btn = QPushButton("Изменить скин")
        self.reset_skin_btn = QPushButton("Сбросить")
        self.download_skin_btn = QPushButton("Скачать")
        
        self.change_skin_btn.clicked.connect(self.change_skin)
        self.reset_skin_btn.clicked.connect(self.reset_skin)
        self.download_skin_btn.clicked.connect(self.download_skin)
        
        for btn in [self.change_skin_btn, self.reset_skin_btn, self.download_skin_btn]:
            skin_buttons_layout.addWidget(btn)
        
        skin_info_layout.addLayout(skin_buttons_layout)
        skin_info_layout.addStretch()
        
        current_skin_layout.addLayout(skin_info_layout)
        current_skin_group.setLayout(current_skin_layout)
        
        # Группа для библиотеки скинов
        skins_library_group = QGroupBox("Библиотека скинов")
        skins_library_layout = QVBoxLayout()
        
        # Поиск скинов
        search_layout = QHBoxLayout()
        self.skin_search = QLineEdit()
        self.skin_search.setPlaceholderText("Поиск скинов...")
        search_layout.addWidget(self.skin_search)
        
        self.search_btn = QPushButton("Найти")
        self.search_btn.clicked.connect(self.search_skins)
        search_layout.addWidget(self.search_btn)
        
        skins_library_layout.addLayout(search_layout)
        
        # Сетка для превью скинов
        self.skins_grid = QGridLayout()
        self.skins_grid.setSpacing(10)
        
        # Создаем виджет для прокрутки
        scroll_content = QWidget()
        scroll_content.setLayout(self.skins_grid)
        
        scroll_area = QScrollArea()
        scroll_area.setWidget(scroll_content)
        scroll_area.setWidgetResizable(True)
        
        skins_library_layout.addWidget(scroll_area)
        skins_library_group.setLayout(skins_library_layout)
        
        # Добавляем группы в layout вкладки
        skins_layout.addWidget(current_skin_group)
        skins_layout.addWidget(skins_library_group)
        
        skins_tab.setLayout(skins_layout)
        
        # Добавляем вкладку в правую панель
        self.right_tabs.addTab(skins_tab, "Скины")
        
        # Загружаем профили и версии
        self.load_profiles()
        self.load_versions()
        
        # Применяем цветовую схему
        self.apply_color_scheme()

    def show_mod_manager(self):
        dialog = ModManager()
        dialog.exec()

    def add_profile(self):
        name, ok = QInputDialog.getText(self, "Новый профиль", "Введите имя профиля:")
        if ok and name:
            username, ok = QInputDialog.getText(self, "Имя пользователя", "Введите имя пользователя:")
            if ok and username:
                self.profile_manager.add_profile(name, username)
                self.load_profiles()

    def remove_profile(self):
        current = self.profile_combo.currentText()
        if current:
            self.profile_manager.remove_profile(current)
            self.load_profiles()

    def load_profiles(self):
        self.profile_combo.clear()
        for profile in self.profile_manager.profiles["profiles"]:
            self.profile_combo.addItem(profile["name"])

    def show_settings(self):
        dialog = SettingsDialog(self)
        if dialog.exec():
            self.load_versions()
            self.apply_color_scheme()

    def apply_color_scheme(self):
        colors = {
            "Красный": "#ff3333",
            "Синий": "#3333ff",
            "Зеленый": "#33ff33",
            "Фиолетовый": "#9933ff",
            "Оранжевый": "#ff9933",
            "Бирюзовый": "#33ffff",
            "Лавандовый": "#E6E6FA",
            "Сиреневый": "#C8A2C8",
            "Розовый": "#FFC0CB",
            "Малиновый": "#DC143C",
            "Индиго": "#4B0082",
            "Аквамарин": "#7FFFD4",
            "Коралловый": "#FF7F50",
            "Лаймовый": "#32CD32",
            "Персиковый": "#FFDAB9",
            "Золотой": "#FFD700",
            "Сапфировый": "#082567",
            "Изумрудный": "#50C878",
            "Рубиновый": "#E0115F",
            "Аметистовый": "#9966CC",
            "Топазовый": "#FFC87C",
            "Янтарный": "#FFBF00",
            "Нефритовый": "#00A86B",
            "Опаловый": "#A8C3BC",
            "Гранатовый": "#A42A04",
            "Бирюзовый океан": "#48D1CC",
            "Лунный камень": "#E6E6FA",
            "Жемчужный": "#FDEEF4",
            "Небесный": "#87CEEB",
            "Закатный": "#FAD6A5",
            "Рассветный": "#FF7F50",
            "Полночный": "#191970",
            "Лесной": "#228B22",
            "Пустынный": "#DEB887",
            "Вулканический": "#B22222",
            "Ледяной": "#E0FFFF",
            "Космический": "#483D8B",
            "Радужный": "#FF1493",
            "Неоновый": "#00FF7F"
        }
        
        accent_color = colors[self.settings.value('accent_color', "Красный")]
        use_gradient = self.settings.value('use_gradient', False, bool)
        gradient_color = colors[self.settings.value('gradient_color', "Синий")]
        
        if use_gradient:
            gradient_style = f"""
                qlineargradient(
                    x1:0, y1:0.5, 
                    x2:1, y2:0.5, 
                    stop:0 {accent_color}, 
                    stop:0.5 {gradient_color}, 
                    stop:1 {accent_color}
                )
            """
            gradient_sidebar = f"""
                qlineargradient(
                    x1:0, y1:0, 
                    x2:1, y2:1, 
                    stop:0 rgba({int(accent_color[1:3], 16)}, {int(accent_color[3:5], 16)}, {int(accent_color[5:7], 16)}, 150), 
                    stop:1 rgba({int(gradient_color[1:3], 16)}, {int(gradient_color[3:5], 16)}, {int(gradient_color[5:7], 16)}, 100)
                )
            """
        else:
            gradient_style = accent_color
            gradient_sidebar = f"rgba({int(accent_color[1:3], 16)}, {int(accent_color[3:5], 16)}, {int(accent_color[5:7], 16)}, 100)"
        
        self.setStyleSheet(f"""
            QMainWindow {{
                background: #1a1a1a;
            }}
            
            QWidget {{
                    color: white;
                }}
                
                QPushButton {{
                background-color: rgba(40, 40, 40, 200);
                border: 2px solid {accent_color};
                border-radius: 8px;
                padding: 10px;
                    color: white;
                    font-weight: bold;
                }}
                
                QPushButton:hover {{
                    background: {gradient_style};
                border-color: white;
            }}
            
            QPushButton:pressed {{
                background-color: rgba(30, 30, 30, 200);
            }}
            
            QProgressBar {{
                background-color: rgba(30, 30, 30, 180);
                border: 2px solid {accent_color};
                border-radius: 10px;
                height: 20px;
                text-align: center;
                color: white;
            }}
            
            QProgressBar::chunk {{
                background: {gradient_style};
                border-radius: 8px;
            }}
            
            QGroupBox {{
                background-color: rgba(40, 40, 40, 180);
                border: 2px solid {accent_color};
                border-radius: 10px;
                margin-top: 2ex;
                padding: 15px;
            }}
            
            QGroupBox::title {{
                color: {accent_color};
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 0 10px;
                background-color: #1a1a1a;
            }}
            
            QComboBox {{
                background-color: rgba(40, 40, 40, 200);
                border: 2px solid {accent_color};
                border-radius: 8px;
                padding: 8px;
                color: white;
            }}
            
            QComboBox:hover {{
                border-color: white;
            }}
            
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            
            QComboBox::down-arrow {{
                width: 12px;
                height: 12px;
                border-left: 2px solid {accent_color};
                border-bottom: 2px solid {accent_color};
                margin-right: 8px;
            }}
            
            QScrollBar:vertical {{
                background: rgba(40, 40, 40, 100);
                width: 14px;
                border-radius: 7px;
                margin: 0;
            }}
            
            QScrollBar::handle:vertical {{
                background: {gradient_style};
                min-height: 30px;
                border-radius: 7px;
            }}
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0;
            }}
            
            QListWidget {{
                background-color: rgba(30, 30, 30, 180);
                border: 2px solid {accent_color};
                border-radius: 10px;
                padding: 5px;
            }}
            
            QListWidget::item {{
                background-color: rgba(40, 40, 40, 180);
                border-radius: 5px;
                margin: 2px;
                padding: 5px;
            }}
            
            QListWidget::item:selected {{
                background: {gradient_style};
            }}
            
            QLineEdit {{
                background-color: rgba(40, 40, 40, 200);
                border: 2px solid {accent_color};
                border-radius: 8px;
                padding: 8px;
                color: white;
            }}
            
            QLineEdit:focus {{
                border-color: white;
            }}
            
            #play_btn {{
                font-size: 24px;
                padding: 15px;
                background: {gradient_style};
                border: 3px solid white;
            }}
            
            #play_btn:hover {{
                background-color: {gradient_color};
            }}
        """)
        
        # Принудительное обновление
        self.update()
        QApplication.processEvents()

    def load_versions(self):
        try:
            versions = minecraft_launcher_lib.utils.get_version_list()
            self.version_combo.clear()
            
            for version in versions:
                should_add = False
                if version['type'] == 'release' and self.settings.value('show_release', True, bool):
                    should_add = True
                elif version['type'] == 'snapshot' and self.settings.value('show_snapshot', False, bool):
                    should_add = True
                elif version['type'] == 'old_beta' and self.settings.value('show_beta', False, bool):
                    should_add = True
                elif version['type'] == 'old_alpha' and self.settings.value('show_alpha', False, bool):
                    should_add = True
                
                if should_add:
                    self.version_combo.addItem(version['id'])
                    
        except Exception as e:
            QMessageBox.warning(self, "Ошибка", f"Не удалось загрузить версии: {str(e)}")

    def launch_game(self):
        version = self.version_combo.currentText()
        if not version:
            QMessageBox.warning(self, "Ошибка", "Выберите версию игры")
            return

        self.progress_group.show()
        self.progress_bar.setValue(0)
        self.status_label.setText("Подготовка к запуску...")

        try:
            minecraft_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minecraft")
            os.makedirs(minecraft_directory, exist_ok=True)
            
            # Получаем выбранный загрузчик
            loader_version = self.loader_version_combo.currentText()
            launch_version = version
            
            # Определяем финальную версию для запуска
            if loader_version != "Vanilla":
                loader_type = loader_version.split()[0]  # Получаем Fabric или Forge
                loader_ver = " ".join(loader_version.split()[1:])  # Получаем версию загрузчика
                
                if loader_type == "Forge":
                    launch_version = f"{version}-forge-{loader_ver}"
                elif loader_type == "Fabric":
                    launch_version = f"fabric-loader-{loader_ver}-{version}"

            # Проверяем наличие версии
            version_dir = os.path.join(minecraft_directory, "versions", launch_version)
            version_json = os.path.join(version_dir, f"{launch_version}.json")
            version_jar = os.path.join(version_dir, f"{launch_version}.jar")
            
            needs_install = False
            
            # Проверяем наличие файлов версии
            if not os.path.exists(version_dir) or not os.path.exists(version_json) or not os.path.exists(version_jar):
                needs_install = True
            
            if needs_install:
                # Сначала устанавливаем базовую версию
                self.status_label.setText(f"Установка версии {version}...")
                minecraft_launcher_lib.install.install_minecraft_version(
                    version,
                    minecraft_directory,
                    callback={
                        "setProgress": lambda x: self.progress_bar.setValue(int(x * 50)),  # 50% на установку базовой версии
                        "setStatus": lambda x: self.status_label.setText(x)
                    }
                )
                
                # Если выбран загрузчик, устанавливаем его
                if loader_version != "Vanilla":
                    self.status_label.setText(f"Установка {loader_type}...")
                    self.install_thread = LoaderInstallThread(loader_type, version, self.mod_loader_manager)
                    self.install_thread.set_loader_version(loader_ver)
                    self.install_thread.progress.connect(lambda x: self.progress_bar.setValue(50 + int(x * 0.5)))  # Оставшиеся 50%
                    self.install_thread.status.connect(self.status_label.setText)
                    self.install_thread.finished.connect(lambda: self.complete_launch(launch_version))
                    self.install_thread.error.connect(self.on_loader_error)
                    self.install_thread.start()
                    return
            
            # Если установка не требуется или это Vanilla версия, запускаем сразу
            self.complete_launch(launch_version)

        except Exception as e:
            self.progress_group.hide()
            QMessageBox.critical(self, "Ошибка", f"Ошибка запуска игры: {str(e)}")

    def complete_launch(self, version):
        try:
            minecraft_directory = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minecraft")
            
            # Проверяем наличие необходимых файлов
            version_dir = os.path.join(minecraft_directory, "versions", version)
            version_json = os.path.join(version_dir, f"{version}.json")
            version_jar = os.path.join(version_dir, f"{version}.jar")
            
            if not os.path.exists(version_dir):
                raise Exception(f"Директория версии {version} не найдена")
            if not os.path.exists(version_json):
                raise Exception(f"Файл {version}.json не найден")
            if not os.path.exists(version_jar):
                raise Exception(f"Файл {version}.jar не найден")
            
            # Настройки запуска
            ram = self.settings.value('ram', 2, int)
            username = self.profile_combo.currentText() or "Player"
            
            options = {
                "username": username,
                "uuid": "",
                "token": "",
                "jvmArguments": [
                    f"-Xmx{ram}G",
                    "-XX:+UnlockExperimentalVMOptions",
                    "-XX:+UseG1GC",
                    "-XX:G1NewSizePercent=20",
                    "-XX:G1ReservePercent=20",
                    "-XX:MaxGCPauseMillis=50",
                    "-XX:G1HeapRegionSize=32M"
                ],
                "launcherName": "RadeonLauncher",
                "launcherVersion": "0.2"
            }
            
            # Получаем команду запуска
            command = minecraft_launcher_lib.command.get_minecraft_command(
                version,
                minecraft_directory,
                options
            )
            
            # Запускаем процесс
            subprocess.Popen(command)
            
            self.progress_group.hide()
            QMessageBox.information(self, "Успех", "Игра запущена!")
            
        except Exception as e:
            self.progress_group.hide()
            QMessageBox.critical(self, "Ошибка", f"Ошибка запуска игры: {str(e)}")

    def add_mod(self):
        file_dialog = QFileDialog()
        file_dialog.setNameFilter("Minecraft Mods (*.jar)")
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        
        if file_dialog.exec_():
            files = file_dialog.selectedFiles()
            for file_path in files:
                try:
                    # Копируем мод в папку mods
                    shutil.copy2(file_path, self.mods_directory)
                    self.refresh_mods_list()
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось добавить мод: {str(e)}")

    def remove_mod(self):
        selected_items = self.mods_list.selectedItems()
        if not selected_items:
            return
        
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Вы уверены, что хотите удалить выбранные моды ({len(selected_items)} шт.)?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for item in selected_items:
                try:
                    mod_path = os.path.join(self.mods_directory, item.text())
                    os.remove(mod_path)
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось удалить мод {item.text()}: {str(e)}")
            
            self.refresh_mods_list()

    def enable_mod(self):
        selected_items = self.mods_list.selectedItems()
        if not selected_items:
            return
        
        for item in selected_items:
            try:
                mod_path = os.path.join(self.mods_directory, item.text())
                if mod_path.endswith(".disabled"):
                    new_path = mod_path[:-9]  # Убираем .disabled
                    os.rename(mod_path, new_path)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось включить мод {item.text()}: {str(e)}")
        
        self.refresh_mods_list()

    def disable_mod(self):
        selected_items = self.mods_list.selectedItems()
        if not selected_items:
            return
        
        for item in selected_items:
            try:
                mod_path = os.path.join(self.mods_directory, item.text())
                if not mod_path.endswith(".disabled"):
                    new_path = mod_path + ".disabled"
                    os.rename(mod_path, new_path)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось отключить мод {item.text()}: {str(e)}")
        
        self.refresh_mods_list()

    def refresh_mods_list(self):
        self.mods_list.clear()
        
        if not os.path.exists(self.mods_directory):
            os.makedirs(self.mods_directory)
        
        for file_name in os.listdir(self.mods_directory):
            if file_name.endswith(".jar") or file_name.endswith(".jar.disabled"):
                item = QListWidgetItem(file_name)
                if file_name.endswith(".disabled"):
                    item.setForeground(QColor(128, 128, 128))  # Серый цвет для отключенных модов
                self.mods_list.addItem(item)

    def add_resourcepack(self):
        file_dialog = QFileDialog()
        file_dialog.setNameFilter("Resource Packs (*.zip)")
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        
        if file_dialog.exec_():
            files = file_dialog.selectedFiles()
            for file_path in files:
                try:
                    # Копируем ресурспак в папку resourcepacks
                    shutil.copy2(file_path, self.resourcepacks_directory)
                    self.refresh_resourcepacks_list()
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось добавить ресурспак: {str(e)}")

    def remove_resourcepack(self):
        selected_items = self.resourcepacks_list.selectedItems()
        if not selected_items:
            return
        
        reply = QMessageBox.question(
            self,
            "Подтверждение",
            f"Вы уверены, что хотите удалить выбранные ресурспаки ({len(selected_items)} шт.)?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            for item in selected_items:
                try:
                    resourcepack_path = os.path.join(self.resourcepacks_directory, item.text())
                    os.remove(resourcepack_path)
                except Exception as e:
                    QMessageBox.critical(self, "Ошибка", f"Не удалось удалить ресурспак {item.text()}: {str(e)}")
            
            self.refresh_resourcepacks_list()

    def enable_resourcepack(self):
        selected_items = self.resourcepacks_list.selectedItems()
        if not selected_items:
            return
        
        for item in selected_items:
            try:
                resourcepack_path = os.path.join(self.resourcepacks_directory, item.text())
                if resourcepack_path.endswith(".disabled"):
                    new_path = resourcepack_path[:-9]  # Убираем .disabled
                    os.rename(resourcepack_path, new_path)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось включить ресурспак {item.text()}: {str(e)}")
        
        self.refresh_resourcepacks_list()

    def disable_resourcepack(self):
        selected_items = self.resourcepacks_list.selectedItems()
        if not selected_items:
            return
        
        for item in selected_items:
            try:
                resourcepack_path = os.path.join(self.resourcepacks_directory, item.text())
                if not resourcepack_path.endswith(".disabled"):
                    new_path = resourcepack_path + ".disabled"
                    os.rename(resourcepack_path, new_path)
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось отключить ресурспак {item.text()}: {str(e)}")
        
        self.refresh_resourcepacks_list()

    def refresh_resourcepacks_list(self):
        self.resourcepacks_list.clear()
        
        if not os.path.exists(self.resourcepacks_directory):
            os.makedirs(self.resourcepacks_directory)
        
        for file_name in os.listdir(self.resourcepacks_directory):
            if file_name.endswith(".zip") or file_name.endswith(".zip.disabled"):
                item = QListWidgetItem(file_name)
                if file_name.endswith(".disabled"):
                    item.setForeground(QColor(128, 128, 128))  # Серый цвет для отключенных ресурспаков
                self.resourcepacks_list.addItem(item)

    def change_skin(self):
        file_dialog = QFileDialog()
        file_dialog.setNameFilter("Minecraft Skins (*.png)")
        file_dialog.setFileMode(QFileDialog.ExistingFile)
        
        if file_dialog.exec_():
            try:
                skin_path = file_dialog.selectedFiles()[0]
                # Проверяем размер скина
                with Image.open(skin_path) as img:
                    if img.size not in [(64, 32), (64, 64)]:
                        raise ValueError("Неверный размер скина. Должен быть 64x32 или 64x64")
                    
                    # Копируем скин в папку skins
                    skin_name = os.path.basename(skin_path)
                    skins_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minecraft", "skins")
                    os.makedirs(skins_dir, exist_ok=True)
                    
                    new_skin_path = os.path.join(skins_dir, skin_name)
                    shutil.copy2(skin_path, new_skin_path)
                    
                    # Обновляем превью
                    self.update_skin_preview(new_skin_path)
                    self.skin_name_label.setText(f"Текущий скин: {skin_name}")
                    
                    QMessageBox.information(self, "Успех", "Скин успешно изменен!")
                    
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось изменить скин: {str(e)}")

    def reset_skin(self):
        try:
            # Возвращаем стандартный скин
            self.skin_preview.clear()
            self.skin_name_label.setText("Текущий скин: Стандартный")
            QMessageBox.information(self, "Успех", "Скин сброшен на стандартный!")
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось сбросить скин: {str(e)}")

    def download_skin(self):
        try:
            # Получаем путь текущего скина
            skins_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minecraft", "skins")
            current_skin = self.skin_name_label.text().replace("Текущий скин: ", "")
            
            if current_skin == "Не выбран" or current_skin == "Стандартный":
                QMessageBox.warning(self, "Внимание", "Нет скина для скачивания")
                return
            
            # Открываем диалог сохранения
            file_dialog = QFileDialog()
            file_dialog.setAcceptMode(QFileDialog.AcceptSave)
            file_dialog.setNameFilter("Minecraft Skins (*.png)")
            file_dialog.setDefaultSuffix("png")
            file_dialog.selectFile(current_skin)
            
            if file_dialog.exec_():
                save_path = file_dialog.selectedFiles()[0]
                current_skin_path = os.path.join(skins_dir, current_skin)
                shutil.copy2(current_skin_path, save_path)
                QMessageBox.information(self, "Успех", "Скин успешно сохранен!")
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось скачать скин: {str(e)}")

    def search_skins(self):
        search_query = self.skin_search.text().lower()
        
        # Очищаем сетку
        while self.skins_grid.count():
            item = self.skins_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        try:
            # Получаем список скинов
            skins_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "minecraft", "skins")
            os.makedirs(skins_dir, exist_ok=True)
            
            skins = [f for f in os.listdir(skins_dir) if f.endswith('.png') and search_query in f.lower()]
            
            # Добавляем превью скинов в сетку
            for i, skin in enumerate(skins):
                skin_widget = QWidget()
                skin_layout = QVBoxLayout(skin_widget)
                
                preview = QLabel()
                preview.setFixedSize(64, 128)
                
                # Загружаем превью скина
                skin_path = os.path.join(skins_dir, skin)
                self.update_skin_preview(skin_path, preview)
                
                name_label = QLabel(skin)
                name_label.setAlignment(Qt.AlignCenter)
                name_label.setWordWrap(True)
                
                skin_layout.addWidget(preview)
                skin_layout.addWidget(name_label)
                
                self.skins_grid.addWidget(skin_widget, i // 4, i % 4)
                
        except Exception as e:
            QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить скины: {str(e)}")

    def update_skin_preview(self, skin_path, label=None):
        try:
            if label is None:
                label = self.skin_preview
            
            # Загружаем скин
            with Image.open(skin_path) as img:
                # Преобразуем в формат QPixmap
                data = img.tobytes("raw", "RGBA")
                qimg = QImage(data, img.width, img.height, QImage.Format_RGBA8888)
                pixmap = QPixmap.fromImage(qimg)
                
                # Масштабируем с сохранением пропорций
                scaled_pixmap = pixmap.scaled(
                    label.size(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                
                label.setPixmap(scaled_pixmap)
                
        except Exception as e:
            print(f"Ошибка обновления превью скина: {e}")

class InstallThread(QThread):
    progress = Signal(int)
    status = Signal(str)
    finished = Signal()
    error = Signal(str)

    def __init__(self, version, minecraft_directory):
        super().__init__()
        self.version = version
        self.minecraft_directory = minecraft_directory

    def run(self):
        try:
            minecraft_launcher_lib.install.install_minecraft_version(
                self.version,
                self.minecraft_directory,
                callback={"setProgress": lambda x: self.progress.emit(int(x * 100)),
                         "setStatus": lambda x: self.status.emit(x)}
            )
            self.finished.emit()
        except Exception as e:
            self.error.emit(str(e))

class StarEffect(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.stars = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(50)
        
        # Создаем звезды
        for _ in range(100):
            self.stars.append({
                'x': random.uniform(0, self.width()),
                'y': random.uniform(0, self.height()),
                'size': random.uniform(1, 4),
                'brightness': random.uniform(0.3, 1.0),
                'twinkle_speed': random.uniform(0.02, 0.1)
            })

    def update_animation(self):
        for star in self.stars:
            star['brightness'] += math.sin(time.time() * star['twinkle_speed']) * 0.1
            star['brightness'] = max(0.3, min(1.0, star['brightness']))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for star in self.stars:
            color = QColor(255, 255, 255, int(255 * star['brightness']))
            painter.setPen(Qt.NoPen)
            
            gradient = QRadialGradient(
                QPointF(star['x'], star['y']),
                star['size'] * 2
            )
            gradient.setColorAt(0, color)
            gradient.setColorAt(1, QColor(255, 255, 255, 0))
            painter.setBrush(QBrush(gradient))
            
            painter.drawEllipse(
                QPointF(star['x'], star['y']),
                star['size'],
                star['size']
            )

class RainEffect(BaseEffect):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.drops = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(30)
        
        particle_count = self.settings.value('particle_count', 100, int)
        for _ in range(particle_count):
            self.create_drop()

    def create_drop(self):
        base_length = random.uniform(10, 30)
        length = base_length * self.particle_size_scale
        base_thickness = random.uniform(1, 3)
        thickness = base_thickness * self.particle_size_scale
        
        self.drops.append({
            'x': random.uniform(0, self.width()),
            'y': random.uniform(-100, 0),
            'speed': random.uniform(5, 15),
            'length': length,
            'thickness': thickness,
            'opacity': random.uniform(0.5, 1.0),
            'rotation': random.uniform(-20, 20) if self.effect_rotation else 0,
            'trail': [] if self.effect_trails else None
        })

    def update_animation(self):
        for drop in self.drops:
            if self.effect_interaction:
                dx = drop['x'] - self.mouse_pos.x()
                dy = drop['y'] - self.mouse_pos.y()
                distance = math.sqrt(dx * dx + dy * dy)
                if distance < 100:
                    drop['x'] += dx * 0.02
                    drop['y'] += dy * 0.02
            
            drop['y'] += drop['speed']
            
            if self.effect_rotation:
                drop['rotation'] += random.uniform(-1, 1)
                drop['rotation'] = max(-30, min(30, drop['rotation']))
            
            if self.effect_trails:
                drop['trail'].append((drop['x'], drop['y']))
                if len(drop['trail']) > 5:
                    drop['trail'].pop(0)
            
            if drop['y'] > self.height():
                drop['y'] = random.uniform(-100, 0)
                drop['x'] = random.uniform(0, self.width())
                if self.effect_trails:
                    drop['trail'].clear()
        
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for drop in self.drops:
            # Рисуем след
            if self.effect_trails and drop['trail']:
                trail_pen = QPen(self.get_particle_color(QColor(150, 150, 255), 0.3))
                trail_pen.setWidth(drop['thickness'] / 2)
                painter.setPen(trail_pen)
                for i in range(len(drop['trail']) - 1):
                    painter.drawLine(
                        QPointF(drop['trail'][i][0], drop['trail'][i][1]),
                        QPointF(drop['trail'][i + 1][0], drop['trail'][i + 1][1])
                    )
            
            start_pos = QPointF(drop['x'], drop['y'])
            end_pos = QPointF(drop['x'], drop['y'] + drop['length'])
            
            # Рисуем свечение
            if self.effect_glow:
                self.apply_glow(painter, start_pos, drop['thickness'] * 2, QColor(150, 150, 255))
            
            # Рисуем каплю
            gradient = QLinearGradient(start_pos, end_pos)
            gradient.setColorAt(0, self.get_particle_color(QColor(150, 150, 255), drop['opacity']))
            gradient.setColorAt(1, self.get_particle_color(QColor(150, 150, 255), 0))
            
            painter.setPen(QPen(QBrush(gradient), drop['thickness']))
            
            if self.effect_rotation:
                painter.save()
                painter.translate(start_pos)
                painter.rotate(drop['rotation'])
                painter.translate(-start_pos)
            
            painter.drawLine(start_pos, end_pos)
            
            if self.effect_rotation:
                painter.restore()

class BubbleEffect(BaseEffect):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.bubbles = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(50)
        
        particle_count = self.settings.value('particle_count', 100, int)
        for _ in range(particle_count):
            self.create_bubble()

    def create_bubble(self):
        base_size = random.uniform(5, 20)
        size = base_size * self.particle_size_scale
        
        self.bubbles.append({
            'x': random.uniform(0, self.width()),
            'y': random.uniform(0, self.height()),
            'size': size,
            'speed': random.uniform(1, 3),
            'wobble': random.uniform(-1, 1),
            'wobble_speed': random.uniform(0.05, 0.2),
            'opacity': random.uniform(0.3, 0.8),
            'rotation': random.uniform(0, 360) if self.effect_rotation else 0,
            'trail': [] if self.effect_trails else None
        })

    def update_animation(self):
        for bubble in self.bubbles:
            if self.effect_interaction:
                dx = bubble['x'] - self.mouse_pos.x()
                dy = bubble['y'] - self.mouse_pos.y()
                distance = math.sqrt(dx * dx + dy * dy)
                if distance < 100:
                    bubble['x'] += dx * 0.02
                    bubble['y'] += dy * 0.02
            
            bubble['y'] -= bubble['speed']
            bubble['x'] += math.sin(time.time() * bubble['wobble_speed']) * bubble['wobble']
            
            if self.effect_rotation:
                bubble['rotation'] += bubble['wobble_speed'] * 10
            
            if self.effect_trails:
                bubble['trail'].append((bubble['x'], bubble['y']))
                if len(bubble['trail']) > 5:
                    bubble['trail'].pop(0)
            
            if bubble['y'] < -bubble['size']:
                bubble['y'] = self.height() + bubble['size']
                bubble['x'] = random.uniform(0, self.width())
                if self.effect_trails:
                    bubble['trail'].clear()
        
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for bubble in self.bubbles:
            pos = QPointF(bubble['x'], bubble['y'])
            
            # Рисуем след
            if self.effect_trails and bubble['trail']:
                trail_pen = QPen(self.get_particle_color(Qt.white, 0.3 * bubble['opacity']))
                trail_pen.setWidth(1)
                painter.setPen(trail_pen)
                for i in range(len(bubble['trail']) - 1):
                    painter.drawLine(
                        QPointF(bubble['trail'][i][0], bubble['trail'][i][1]),
                        QPointF(bubble['trail'][i + 1][0], bubble['trail'][i + 1][1])
                    )
            
            # Рисуем свечение
            if self.effect_glow:
                self.apply_glow(painter, pos, bubble['size'], Qt.white)
            
            # Рисуем пузырь
            gradient = QRadialGradient(pos, bubble['size'])
            base_color = self.get_particle_color(Qt.white, bubble['opacity'])
            gradient.setColorAt(0, self.get_particle_color(Qt.white, 0.2 * bubble['opacity']))
            gradient.setColorAt(0.8, base_color)
            gradient.setColorAt(1, self.get_particle_color(Qt.white, 0))
            
            painter.setPen(QPen(base_color, 1))
            painter.setBrush(QBrush(gradient))
            
            if self.effect_rotation:
                painter.save()
                painter.translate(pos)
                painter.rotate(bubble['rotation'])
                painter.translate(-pos)
            
            painter.drawEllipse(pos, bubble['size'], bubble['size'])
            
            # Рисуем блик на пузыре
            highlight_pos = QPointF(
                pos.x() + bubble['size'] * 0.3,
                pos.y() - bubble['size'] * 0.3
            )
            highlight_gradient = QRadialGradient(highlight_pos, bubble['size'] * 0.2)
            highlight_gradient.setColorAt(0, self.get_particle_color(Qt.white, 0.8 * bubble['opacity']))
            highlight_gradient.setColorAt(1, self.get_particle_color(Qt.white, 0))
            painter.setBrush(QBrush(highlight_gradient))
            painter.drawEllipse(highlight_pos, bubble['size'] * 0.2, bubble['size'] * 0.2)
            
            if self.effect_rotation:
                painter.restore()

class FireEffect(BaseEffect):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.particles = []
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(30)
        
        particle_count = self.settings.value('particle_count', 100, int)
        for _ in range(particle_count):
            self.create_particle()

    def create_particle(self):
        base_size = random.uniform(5, 15)
        self.particles.append({
            'x': random.uniform(0, self.width()),
            'y': self.height() + 10,
            'size': random.uniform(5, 15),
            'speed_x': random.uniform(-1, 1),
            'speed_y': random.uniform(-3, -1),
            'life': 255,
            'color': random.choice([
                QColor(255, 100, 0),  # Оранжевый
                QColor(255, 50, 0),   # Красно-оранжевый
                QColor(255, 150, 0),  # Светло-оранжевый
                QColor(255, 200, 0)   # Желтый
            ])
        })

    def update_animation(self):
        for particle in self.particles:
            particle['x'] += particle['speed_x']
            particle['y'] += particle['speed_y']
            particle['life'] -= 5
            particle['size'] *= 0.99
            
            # Добавляем случайное колебание
            particle['x'] += random.uniform(-0.5, 0.5)
            
        # Удаляем угасшие частицы и создаем новые
        self.particles = [p for p in self.particles if p['life'] > 0]
        while len(self.particles) < 100:
            self.create_particle()
            
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        for particle in self.particles:
            color = particle['color']
            color.setAlpha(particle['life'])
            
            gradient = QRadialGradient(
                QPointF(particle['x'], particle['y']),
                particle['size']
            )
            gradient.setColorAt(0, color)
            gradient.setColorAt(1, QColor(color.red(), color.green(), color.blue(), 0))
            
            painter.setPen(Qt.NoPen)
            painter.setBrush(QBrush(gradient))
            painter.drawEllipse(
                QPointF(particle['x'], particle['y']),
                particle['size'],
                particle['size']
            )

if __name__ == '__main__':
    app = QApplication(sys.argv)
    
    # Загрузка шрифта Minecraft
    font_id = QFontDatabase.addApplicationFont("resources/minecraft-ten-font-cyrillic.ttf")
    if font_id != -1:
        font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        app.setFont(QFont(font_family, 10))
    
    launcher = MinecraftLauncher()
    launcher.show()
    sys.exit(app.exec()) 