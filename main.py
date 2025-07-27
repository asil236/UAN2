import sys
import os
import json
import tempfile
from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton, QFileDialog,
    QVBoxLayout, QTextBrowser, QComboBox, QMessageBox, QLineEdit,
    QHBoxLayout, QSlider, QGroupBox, QGridLayout, 
    QProgressBar, QTableWidget, QTableWidgetItem, 
    QHeaderView, QCheckBox, QDialog, QSpinBox, QColorDialog,
    QDialogButtonBox, QFormLayout, QListWidget, QListWidgetItem,
    QSplitter
)
from PyQt5.QtCore import Qt, QUrl, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor
from pydub import AudioSegment
import pyloudnorm as pyln
import numpy as np
import pygame

# Default LUFS configuration
DEFAULT_LUFS_CONFIG = {
    -12: {"suffix": "_SFX", "name": "SFX", "color": "#FF4444"},
    -14: {"suffix": "_MSC", "name": "Music", "color": "#4444FF"}, 
    -16: {"suffix": "_DLG", "name": "Dialog", "color": "#44FF44"},
    -18: {"suffix": "_UI", "name": "UI", "color": "#FFAA44"},
    -20: {"suffix": "_AMB", "name": "Ambient", "color": "#AA44FF"}
}

# Resource path helper (pre správne cesty pri .exe buildoch)
def resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def get_app_data_path():
    """Get application data directory"""
    if os.name == 'nt':  # Windows
        app_data = os.getenv('APPDATA')
        if app_data:
            app_dir = os.path.join(app_data, 'UnrealAudioNormalizer')
        else:
            app_dir = os.path.join(os.path.expanduser('~'), 'UnrealAudioNormalizer')
    else:  # Linux/Mac
        app_dir = os.path.join(os.path.expanduser('~'), '.unreal_audio_normalizer')
    
    # Create directory if it doesn't exist
    os.makedirs(app_dir, exist_ok=True)
    return app_dir

# Use absolute path for config file
CONFIG_FILE = os.path.join(get_app_data_path(), "lufs_config.json")

# Initialize pygame mixer with more conservative settings
try:
    pygame.mixer.init(frequency=22050, size=-16, channels=2, buffer=1024)
except pygame.error as e:
    print(f"Warning: Could not initialize pygame mixer: {e}")

class LUFSConfigManager:
    def __init__(self):
        self.config = DEFAULT_LUFS_CONFIG.copy()
        self.load_config()
    
    def load_config(self):
        try:
            if os.path.exists(CONFIG_FILE):
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config = {int(k): v for k, v in data.items()}
        except Exception as e:
            print(f"Failed to load config: {e}")
            self.config = DEFAULT_LUFS_CONFIG.copy()
    
    def save_config(self):
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
            data = {str(k): v for k, v in self.config.items()}
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Failed to save config: {e}")
    
    def get_lufs_values(self):
        return sorted(self.config.keys())
    
    def get_suffix(self, lufs_value):
        return self.config.get(lufs_value, {}).get("suffix", "")
    
    def get_name(self, lufs_value):
        return self.config.get(lufs_value, {}).get("name", str(lufs_value))
    
    def get_color(self, lufs_value):
        return self.config.get(lufs_value, {}).get("color", "#888888")
    
    def add_preset(self, lufs_value, suffix, name, color):
        self.config[lufs_value] = {
            "suffix": suffix,
            "name": name,
            "color": color
        }
    
    def remove_preset(self, lufs_value):
        if lufs_value in self.config:
            del self.config[lufs_value]


class LUFSConfigDialog(QDialog):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.setWindowTitle("LUFS Presets Configuration")
        self.setModal(True)
        self.resize(600, 500)
        self.setup_ui()
        self.refresh_list()
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        
        info_label = QLabel("Configure custom LUFS presets with suffixes, names and colors:")
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)
        
        splitter = QSplitter(Qt.Horizontal)
        
        # Left side - preset list
        list_widget = QWidget()
        list_layout = QVBoxLayout(list_widget)
        
        list_layout.addWidget(QLabel("Current Presets:"))
        
        self.preset_list = QListWidget()
        self.preset_list.currentRowChanged.connect(self.on_preset_selected)
        list_layout.addWidget(self.preset_list)
        
        list_buttons_layout = QHBoxLayout()
        
        btn_add = QPushButton("Add Preset")
        btn_add.clicked.connect(self.add_preset)
        list_buttons_layout.addWidget(btn_add)
        
        btn_remove = QPushButton("Remove Selected")
        btn_remove.clicked.connect(self.remove_preset)
        list_buttons_layout.addWidget(btn_remove)
        
        btn_reset = QPushButton("Reset to Default")
        btn_reset.clicked.connect(self.reset_to_default)
        list_buttons_layout.addWidget(btn_reset)
        
        list_layout.addLayout(list_buttons_layout)
        
        # Right side - edit form
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        
        form_layout.addWidget(QLabel("Edit Selected Preset:"))
        
        self.form_group = QGroupBox("Preset Details")
        self.form_group.setEnabled(False)
        form_form_layout = QFormLayout(self.form_group)
        
        self.lufs_spinbox = QSpinBox()
        self.lufs_spinbox.setRange(-50, 10)
        self.lufs_spinbox.setValue(-16)
        self.lufs_spinbox.valueChanged.connect(self.on_form_changed)
        form_form_layout.addRow("LUFS Value:", self.lufs_spinbox)
        
        self.suffix_input = QLineEdit()
        self.suffix_input.setPlaceholderText("e.g., _DLG")
        self.suffix_input.textChanged.connect(self.on_form_changed)
        form_form_layout.addRow("File Suffix:", self.suffix_input)
        
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("e.g., Dialog")
        self.name_input.textChanged.connect(self.on_form_changed)
        form_form_layout.addRow("Display Name:", self.name_input)
        
        color_layout = QHBoxLayout()
        self.color_button = QPushButton()
        self.color_button.setFixedSize(100, 30)
        self.color_button.clicked.connect(self.choose_color)
        color_layout.addWidget(self.color_button)
        color_layout.addStretch()
        form_form_layout.addRow("Color:", color_layout)
        
        form_layout.addWidget(self.form_group)
        
        self.btn_update = QPushButton("Update Preset")
        self.btn_update.setEnabled(False)
        self.btn_update.clicked.connect(self.update_preset)
        form_layout.addWidget(self.btn_update)
        
        form_layout.addStretch()
        
        splitter.addWidget(list_widget)
        splitter.addWidget(form_widget)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        
        main_layout.addWidget(splitter)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)
        
        self.setLayout(main_layout)
        
        self.current_color = "#888888"
        self.update_color_button()
    
    def refresh_list(self):
        self.preset_list.clear()
        for lufs_value in sorted(self.config_manager.get_lufs_values()):
            name = self.config_manager.get_name(lufs_value)
            suffix = self.config_manager.get_suffix(lufs_value)
            color = self.config_manager.get_color(lufs_value)
            
            item_text = f"{lufs_value} LUFS - {name} ({suffix})"
            item = QListWidgetItem(item_text)
            item.setData(Qt.UserRole, lufs_value)
            
            qcolor = QColor(color)
            qcolor.setAlpha(100)
            item.setBackground(qcolor)
            
            self.preset_list.addItem(item)
    
    def on_preset_selected(self, row):
        if row >= 0:
            item = self.preset_list.item(row)
            lufs_value = item.data(Qt.UserRole)
            
            self.lufs_spinbox.setValue(lufs_value)
            self.suffix_input.setText(self.config_manager.get_suffix(lufs_value))
            self.name_input.setText(self.config_manager.get_name(lufs_value))
            self.current_color = self.config_manager.get_color(lufs_value)
            self.update_color_button()
            
            self.form_group.setEnabled(True)
            self.btn_update.setEnabled(True)
        else:
            self.form_group.setEnabled(False)
            self.btn_update.setEnabled(False)
    
    def on_form_changed(self):
        if self.form_group.isEnabled():
            self.btn_update.setEnabled(True)
    
    def update_color_button(self):
        self.color_button.setStyleSheet(f"""
            QPushButton {{
                background-color: {self.current_color};
                border: 2px solid #333;
                border-radius: 4px;
            }}
        """)
        self.color_button.setText(self.current_color)
    
    def choose_color(self):
        color = QColorDialog.getColor(QColor(self.current_color), self)
        if color.isValid():
            self.current_color = color.name()
            self.update_color_button()
            self.on_form_changed()
    
    def add_preset(self):
        existing_values = set(self.config_manager.get_lufs_values())
        new_lufs = -16
        while new_lufs in existing_values:
            new_lufs -= 1
        
        self.config_manager.add_preset(new_lufs, f"_CUSTOM{abs(new_lufs)}", f"Custom {new_lufs}", "#888888")
        self.refresh_list()
        
        for i in range(self.preset_list.count()):
            item = self.preset_list.item(i)
            if item.data(Qt.UserRole) == new_lufs:
                self.preset_list.setCurrentRow(i)
                break
    
    def remove_preset(self):
        current_row = self.preset_list.currentRow()
        if current_row >= 0:
            item = self.preset_list.item(current_row)
            lufs_value = item.data(Qt.UserRole)
            
            reply = QMessageBox.question(self, "Remove Preset", 
                                       f"Remove preset {lufs_value} LUFS?",
                                       QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.config_manager.remove_preset(lufs_value)
                self.refresh_list()
                self.form_group.setEnabled(False)
                self.btn_update.setEnabled(False)
    
    def update_preset(self):
        current_row = self.preset_list.currentRow()
        if current_row >= 0:
            old_item = self.preset_list.item(current_row)
            old_lufs = old_item.data(Qt.UserRole)
            
            new_lufs = self.lufs_spinbox.value()
            suffix = self.suffix_input.text().strip()
            name = self.name_input.text().strip()
            
            if not suffix:
                QMessageBox.warning(self, "Invalid Input", "Suffix cannot be empty.")
                return
            if not name:
                QMessageBox.warning(self, "Invalid Input", "Name cannot be empty.")
                return
            
            if new_lufs != old_lufs and new_lufs in self.config_manager.config:
                QMessageBox.warning(self, "Conflict", f"LUFS value {new_lufs} already exists.")
                return
            
            if new_lufs != old_lufs:
                self.config_manager.remove_preset(old_lufs)
            
            self.config_manager.add_preset(new_lufs, suffix, name, self.current_color)
            self.refresh_list()
            
            for i in range(self.preset_list.count()):
                item = self.preset_list.item(i)
                if item.data(Qt.UserRole) == new_lufs:
                    self.preset_list.setCurrentRow(i)
                    break
            
            self.btn_update.setEnabled(False)
    
    def reset_to_default(self):
        reply = QMessageBox.question(self, "Reset Configuration", 
                                   "Reset all presets to default values? This will remove all custom presets.",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            self.config_manager.config = DEFAULT_LUFS_CONFIG.copy()
            self.refresh_list()
            self.form_group.setEnabled(False)
            self.btn_update.setEnabled(False)
    
    def accept(self):
        self.config_manager.save_config()
        super().accept()


class SeekableProgressBar(QProgressBar):
    seekRequested = pyqtSignal(float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_dragging = False
    
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = True
            percentage = (event.x() / self.width()) * 100
            percentage = max(0, min(100, percentage))
            self.seekRequested.emit(percentage)
        super().mousePressEvent(event)
    
    def mouseMoveEvent(self, event):
        if self.is_dragging and event.buttons() & Qt.LeftButton:
            percentage = (event.x() / self.width()) * 100
            percentage = max(0, min(100, percentage))
            self.seekRequested.emit(percentage)
        super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.is_dragging = False
        super().mouseReleaseEvent(event)


class AudioPlayerWidget(QWidget):
    def __init__(self, filepath, parent=None):
        super().__init__(parent)
        self.filepath = os.path.abspath(filepath)  # Ensure absolute path
        self.is_playing = False
        self.is_paused = False
        self.position = 0
        self.duration = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_progress)
        self.audio_segment = None
        self.parent_normalizer = None
        self.temp_files = []  # Track temporary files for cleanup
        
        self.setup_ui()
        self.get_duration()
    
    def set_parent_normalizer(self, parent):
        self.parent_normalizer = parent
    
    def setup_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(3)
        
        self.play_button = QPushButton("▶")
        self.play_button.setFixedSize(25, 25)
        self.play_button.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                border: 1px solid #d0d0d0;
                border-radius: 3px;
                font-size: 14px;
                font-weight: bold;
                color: #000000;
                font-family: Arial, sans-serif;
            }
            QPushButton:hover {
                background-color: #f0f0f0;
                border: 1px solid #999999;
            }
            QPushButton:pressed {
                background-color: #e0e0e0;
            }
        """)
        self.play_button.clicked.connect(self.toggle_playback)
        
        self.progress = SeekableProgressBar()
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                border: 1px solid #ddd;
                border-radius: 3px;
                background-color: #f0f0f0;
            }
            QProgressBar::chunk {
                background-color: #4CAF50;
                border-radius: 2px;
            }
        """)
        self.progress.seekRequested.connect(self.seek_to_position)
        
        layout.addWidget(self.play_button)
        layout.addWidget(self.progress, 1)
        
        self.setLayout(layout)
    
    def get_duration(self):
        try:
            # Check if file exists
            if not os.path.exists(self.filepath):
                print(f"Warning: Audio file not found: {self.filepath}")
                self.duration = 0
                self.progress.setMaximum(1000)
                return
                
            self.audio_segment = AudioSegment.from_file(self.filepath)
            self.duration = len(self.audio_segment) / 1000.0
            self.progress.setMaximum(int(self.duration * 10))
        except Exception as e:
            print(f"Error loading audio file {self.filepath}: {e}")
            self.duration = 0
            self.progress.setMaximum(1000)
    
    def seek_to_position(self, percentage):
        if self.duration > 0:
            new_position = (percentage / 100.0) * self.duration
            self.position = new_position
            self.progress.setValue(int(self.position * 10))
            
            if self.is_playing and not self.is_paused:
                try:
                    start_ms = int(self.position * 1000)
                    segment_from_position = self.audio_segment[start_ms:]
                    
                    # Create temporary file in system temp directory
                    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav', 
                                                          dir=tempfile.gettempdir())
                    temp_file_path = temp_file.name
                    temp_file.close()
                    
                    segment_from_position.export(temp_file_path, format="wav")
                    self.temp_files.append(temp_file_path)
                    
                    pygame.mixer.music.stop()
                    pygame.mixer.music.load(temp_file_path)
                    pygame.mixer.music.play()
                    
                    QTimer.singleShot(1000, lambda: self.cleanup_temp_file(temp_file_path))
                except Exception as e:
                    print(f"Error seeking audio: {e}")
    
    def cleanup_temp_file(self, filepath):
        try:
            if os.path.exists(filepath):
                os.unlink(filepath)
                if filepath in self.temp_files:
                    self.temp_files.remove(filepath)
        except Exception as e:
            print(f"Error cleaning up temp file: {e}")
    
    def cleanup_all_temp_files(self):
        for temp_file in self.temp_files[:]:
            self.cleanup_temp_file(temp_file)
    
    def toggle_playback(self):
        if self.parent_normalizer:
            self.parent_normalizer.stop_other_players(self)
        
        if not self.is_playing:
            self.play()
        else:
            if self.is_paused:
                self.resume()
            else:
                self.pause()
    
    def play(self):
        try:
            if not os.path.exists(self.filepath):
                print(f"Cannot play: file not found: {self.filepath}")
                return
                
            if self.position > 0 and self.audio_segment:
                start_ms = int(self.position * 1000)
                segment_from_position = self.audio_segment[start_ms:]
                
                # Create temporary file in system temp directory
                temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.wav',
                                                      dir=tempfile.gettempdir())
                temp_file_path = temp_file.name
                temp_file.close()
                
                segment_from_position.export(temp_file_path, format="wav")
                self.temp_files.append(temp_file_path)
                
                pygame.mixer.music.load(temp_file_path)
                pygame.mixer.music.play()
                
                QTimer.singleShot(1000, lambda: self.cleanup_temp_file(temp_file_path))
            else:
                pygame.mixer.music.load(self.filepath)
                pygame.mixer.music.play()
                self.position = 0
            
            self.is_playing = True
            self.is_paused = False
            self.play_button.setText("||")
            self.timer.start(100)
        except Exception as e:
            print(f"Error playing audio: {e}")
    
    def pause(self):
        pygame.mixer.music.stop()
        self.is_paused = True
        self.play_button.setText("▶")
        self.timer.stop()
    
    def resume(self):
        self.play()
    
    def stop(self):
        pygame.mixer.music.stop()
        self.is_playing = False
        self.is_paused = False
        self.position = 0
        self.play_button.setText("▶")
        self.progress.setValue(0)
        self.timer.stop()
    
    def update_progress(self):
        if self.is_playing and not self.is_paused:
            self.position += 0.1
            if self.position >= self.duration:
                self.stop()
            else:
                self.progress.setValue(int(self.position * 10))
    
    def __del__(self):
        self.cleanup_all_temp_files()


class SliderWithLabels(QWidget):
    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.scale_labels = []
        self.name_labels = []
        self.setup_ui()
        self.create_labels()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        self.names_widget = QWidget()
        self.names_widget.setFixedHeight(15)
        layout.addWidget(self.names_widget)
        
        self.labels_widget = QWidget()
        self.labels_widget.setFixedHeight(20)
        layout.addWidget(self.labels_widget)
        
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setMinimum(-30)
        self.slider.setMaximum(0)
        self.slider.setValue(-16)
        self.slider.setTickPosition(QSlider.NoTicks)
        self.slider.setStyleSheet("""
            QSlider {
                background: transparent;
                border: none;
            }
            QSlider::groove:horizontal {
                border: 1px solid #999999;
                height: 4px;
                background: #E0E0E0;
                margin: 2px 0;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #4CAF50;
                border: 1px solid #45a049;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
            QSlider::sub-page:horizontal {
                background: #4CAF50;
                border-radius: 2px;
            }
            QSlider::add-page:horizontal {
                background: #E0E0E0;
                border-radius: 2px;
            }
        """)
        layout.addWidget(self.slider)
    
    def create_labels(self):
        base_values = [-30, -25, -20, -18, -16, -15, -14, -12, -10, -5, 0]
        config_values = set(self.config_manager.get_lufs_values())
        all_values = sorted(set(base_values).union(config_values))
        
        for val in all_values:
            label = QLabel(str(val), self.labels_widget)
            label.setAlignment(Qt.AlignCenter)
            
            if val in config_values:
                color = self.config_manager.get_color(val)
                label.setStyleSheet(f"font-size: 10px; color: {color}; font-weight: bold;")
            else:
                label.setStyleSheet("font-size: 10px; color: #666; font-weight: normal;")
            
            label.show()
            self.scale_labels.append((val, label))
        
        for val in config_values:
            name = self.config_manager.get_name(val)
            color = self.config_manager.get_color(val)
            
            name_label = QLabel(name, self.names_widget)
            name_label.setAlignment(Qt.AlignCenter)
            name_label.setStyleSheet(f"font-size: 8px; color: {color}; font-weight: bold;")
            name_label.show()
            self.name_labels.append((val, name_label))
    
    def refresh_labels(self):
        for _, label in self.scale_labels:
            label.hide()
            label.deleteLater()
        
        for _, label in self.name_labels:
            label.hide()
            label.deleteLater()
        
        self.scale_labels.clear()
        self.name_labels.clear()
        
        self.create_labels()
        QTimer.singleShot(50, self.position_labels)
    
    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(10, self.position_labels)
    
    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(100, self.position_labels)
    
    def position_labels(self):
        if not self.labels_widget.isVisible() or not self.scale_labels:
            return
            
        slider_margin = 10
        effective_width = self.slider.width() - (2 * slider_margin)
        effective_x = slider_margin
        
        for val, label in self.scale_labels:
            if label and not label.isHidden():
                position_ratio = (val + 30) / 30
                x_pos = effective_x + (position_ratio * effective_width) - (label.width() // 2)
                label.move(max(0, int(x_pos)), 0)
        
        for val, label in self.name_labels:
            if label and not label.isHidden():
                position_ratio = (val + 30) / 30
                x_pos = effective_x + (position_ratio * effective_width) - (label.width() // 2)
                label.move(max(0, int(x_pos)), 0)


class OutputPathWidget(QWidget):
    def __init__(self, filepath, suffix, suffix_color="#FF0000", parent=None):
        super().__init__(parent)
        self.setup_ui(filepath, suffix, suffix_color)
    
    def setup_ui(self, filepath, suffix, suffix_color):
        layout = QHBoxLayout()
        layout.setContentsMargins(5, 2, 5, 2)
        
        if filepath == "No override folder selected":
            label = QLabel("No override folder selected")
            label.setStyleSheet("color: red; font-weight: bold;")
            layout.addWidget(label)
        elif not filepath:
            label = QLabel("No path")
            label.setStyleSheet("color: red; font-weight: bold;")
            layout.addWidget(label)
        else:
            # Ensure we're working with absolute path
            filepath = os.path.abspath(filepath)
            dir_path = os.path.dirname(filepath)
            filename = os.path.basename(filepath)
            
            if suffix and suffix in filename:
                suffix_pos = filename.rfind(suffix)
                name_part = filename[:suffix_pos]
                suffix_part = filename[suffix_pos:suffix_pos + len(suffix)]
                extension_part = filename[suffix_pos + len(suffix):]
                
                full_path = os.path.join(dir_path, name_part)
                html_text = f'{full_path}<span style="color: {suffix_color};">{suffix_part}</span>{extension_part}'
            else:
                html_text = filepath
            
            label = QLabel(html_text)
            label.setTextFormat(Qt.RichText)
            layout.addWidget(label)
        
        layout.addStretch()
        self.setLayout(layout)


class AudioNormalizer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Unreal Audio Normalizer")
        self.output_folder = ""
        self.lufs_values = {}
        self.master_checked = True
        self.current_filter = "all"
        self.tolerance = 1.0
        self.use_override_folder = False
        
        self.config_manager = LUFSConfigManager()
        
        self.setup_ui()
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            audio_extensions = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac']
            valid_files = []
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if any(file_path.lower().endswith(ext) for ext in audio_extensions):
                    valid_files.append(file_path)
            
            if valid_files:
                event.acceptProposedAction()
            else:
                event.ignore()
        else:
            event.ignore()

    def dropEvent(self, event):
        audio_extensions = ['.wav', '.mp3', '.flac', '.ogg', '.m4a', '.aac']
        dropped_files = []
        
        for url in event.mimeData().urls():
            file_path = os.path.abspath(url.toLocalFile())  # Ensure absolute path
            if any(file_path.lower().endswith(ext) for ext in audio_extensions):
                dropped_files.append(file_path)
        
        if dropped_files:
            if len(dropped_files) > 1:
                self.progress_bar.setVisible(True)
                self.progress_bar.setMaximum(len(dropped_files))
                self.progress_bar.setValue(0)
                self.status_label.setText("Analyzing dropped audio files...")
                
                for i, file_path in enumerate(dropped_files):
                    self.progress_bar.setValue(i)
                    QApplication.processEvents()
                    self.add_list_item(file_path)
                
                self.progress_bar.setVisible(False)
                self.status_label.setText("")
            else:
                self.add_list_item(dropped_files[0])
            
            self.update_info_label()
            event.acceptProposedAction()
        else:
            event.ignore()

    def update_tolerance(self):
        self.tolerance = self.tolerance_spinbox.value() / 10.0
        self.tolerance_display.setText(f"({self.tolerance} LUFS)")
        self.refresh_color_coding()

    def toggle_override_folder(self):
        self.use_override_folder = self.use_override_checkbox.isChecked()
        self.btn_select_override.setEnabled(self.use_override_folder)
        
        if self.use_override_folder:
            if not self.output_folder:
                self.override_label.setText("No override folder selected.")
                self.override_label.setStyleSheet("color: red; font-weight: bold;")
            else:
                self.override_label.setText(f"Override folder: {self.output_folder}")
                self.override_label.setStyleSheet("color: black; font-weight: normal;")
        else:
            self.override_label.setText("Using input file locations.")
            self.override_label.setStyleSheet("color: #666; font-style: italic;")
        
        self.update_all_displays()

    def select_override_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Override Output Folder")
        if folder:
            self.output_folder = os.path.abspath(folder)  # Ensure absolute path
            self.override_label.setText(f"Override folder: {folder}")
            self.override_label.setStyleSheet("color: black; font-weight: normal;")
            self.update_all_displays()

    def get_target_lufs(self):
        return self.slider.value()

    def get_output_filename(self, filepath):
        new_suffix = self.suffix_input.text().strip()
        base = os.path.splitext(os.path.basename(filepath))[0]
        
        all_suffixes = [self.config_manager.get_suffix(lufs) for lufs in self.config_manager.get_lufs_values()]
        all_suffixes = [s for s in all_suffixes if s]
        
        for existing_suffix in all_suffixes:
            if base.endswith(existing_suffix):
                base = base[:-len(existing_suffix)]
                break
        
        final_name = base + new_suffix + ".wav"
        
        if self.use_override_folder:
            if not self.output_folder:
                return "No override folder selected"
            else:
                return os.path.abspath(os.path.join(self.output_folder, final_name))
        else:
            input_dir = os.path.dirname(os.path.abspath(filepath))
            return os.path.abspath(os.path.join(input_dir, final_name))

    def update_slider_value(self):
        lufs_value = self.slider.value()
        
        if lufs_value in self.config_manager.get_lufs_values():
            preset_name = self.config_manager.get_name(lufs_value)
            preset_color = self.config_manager.get_color(lufs_value)
            
            self.target_display_label.setText(f"Target LUFS: {lufs_value} ({preset_name})")
            self.target_display_label.setStyleSheet(f"""
                QLabel {{
                    font-size: 24px;
                    font-weight: bold;
                    color: {preset_color};
                    margin: 5px;
                }}
            """)
            
            suffix = self.config_manager.get_suffix(lufs_value)
            self.suffix_input.setText(suffix)
        else:
            self.target_display_label.setText(f"Target LUFS: {lufs_value}")
            self.target_display_label.setStyleSheet("""
                QLabel {
                    font-size: 24px;
                    font-weight: bold;
                    color: #333333;
                    margin: 5px;
                }
            """)
            
            current_suffix = self.suffix_input.text().strip()
            configured_suffixes = [self.config_manager.get_suffix(v) for v in self.config_manager.get_lufs_values()]
            if not current_suffix or current_suffix in configured_suffixes:
                self.suffix_input.setText("")
        
        self.refresh_color_coding()
        self.update_all_displays()

    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Normalization Settings
        settings_group = QGroupBox("Normalization Settings")
        settings_layout = QVBoxLayout()
        settings_layout.setSpacing(6)
        
        # Target LUFS display
        target_display_layout = QHBoxLayout()
        target_display_layout.addStretch()
        
        self.target_display_label = QLabel("Target LUFS: -16")
        self.target_display_label.setStyleSheet("""
            QLabel {
                font-size: 24px;
                font-weight: bold;
                color: #333333;
                margin: 5px;
            }
        """)
        self.target_display_label.setAlignment(Qt.AlignCenter)
        target_display_layout.addWidget(self.target_display_label)
        target_display_layout.addStretch()
        
        settings_layout.addLayout(target_display_layout)
        
        # Slider
        self.slider_widget = SliderWithLabels(self.config_manager)
        self.slider = self.slider_widget.slider
        self.slider.valueChanged.connect(self.update_slider_value)
        settings_layout.addWidget(self.slider_widget)
        
        # Suffix, tolerance and config
        suffix_tolerance_layout = QHBoxLayout()
        
        suffix_tolerance_layout.addWidget(QLabel("Output File Suffix:"))
        self.suffix_input = QLineEdit()
        self.suffix_input.setPlaceholderText("Output file suffix")
        self.suffix_input.textChanged.connect(self.update_all_displays)
        suffix_tolerance_layout.addWidget(self.suffix_input)
        
        suffix_tolerance_layout.addWidget(QLabel("   LUFS Tolerance:"))
        self.tolerance_spinbox = QSpinBox()
        self.tolerance_spinbox.setRange(1, 50)
        self.tolerance_spinbox.setValue(int(self.tolerance * 10))
        self.tolerance_spinbox.setSuffix(" tenths")
        self.tolerance_spinbox.setToolTip("Tolerance in tenths of LUFS (e.g., 10 = 1.0 LUFS)")
        self.tolerance_spinbox.valueChanged.connect(self.update_tolerance)
        suffix_tolerance_layout.addWidget(self.tolerance_spinbox)
        
        tolerance_display = QLabel(f"({self.tolerance} LUFS)")
        tolerance_display.setStyleSheet("color: #666; font-style: italic;")
        self.tolerance_display = tolerance_display
        suffix_tolerance_layout.addWidget(tolerance_display)
        
        btn_help = QPushButton("❓ Help/Documentation")
        btn_help.setToolTip("Open the user guide")
        btn_help.clicked.connect(self.open_help_documentation)
        suffix_tolerance_layout.addWidget(btn_help)
        
        suffix_tolerance_layout.addStretch()
        btn_config = QPushButton("⚙ Configure LUFS Presets")
        btn_config.clicked.connect(self.open_config_dialog)
        btn_config.setStyleSheet("""
            QPushButton {
                background-color: #f0f0f0;
                border: 2px solid #4CAF50;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
                color: #2E7D32;
            }
            QPushButton:hover {
                background-color: #e8f5e8;
            }
        """)
        suffix_tolerance_layout.addWidget(btn_config)
        
        settings_layout.addLayout(suffix_tolerance_layout)
        
        settings_group.setLayout(settings_layout)
        main_layout.addWidget(settings_group)
        
        # Audio File Management
        files_group = QGroupBox("Audio File Management")
        files_layout = QVBoxLayout()
        files_layout.setSpacing(6)
        
        file_buttons_layout = QHBoxLayout()
        file_buttons_layout.setSpacing(4)
        
        btn_add_files = QPushButton("Add Audio Files")
        btn_add_files.clicked.connect(self.add_files)
        file_buttons_layout.addWidget(btn_add_files)
        
        btn_clear_files = QPushButton("Clear All")
        btn_clear_files.clicked.connect(self.clear_files)
        file_buttons_layout.addWidget(btn_clear_files)
        
        btn_remove_selected = QPushButton("Remove Checked (✓)")
        btn_remove_selected.clicked.connect(self.remove_selected_files)
        file_buttons_layout.addWidget(btn_remove_selected)
        
        btn_analyze_lufs = QPushButton("Re-analyze All LUFS")
        btn_analyze_lufs.clicked.connect(self.analyze_lufs)
        file_buttons_layout.addWidget(btn_analyze_lufs)
        
        files_layout.addLayout(file_buttons_layout)
        
        # Search and filter
        search_filter_layout = QHBoxLayout()
        
        search_filter_layout.addWidget(QLabel("Search:"))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Filter files by name...")
        self.search_input.setMaximumWidth(200)
        self.search_input.textChanged.connect(self.filter_files)
        search_filter_layout.addWidget(self.search_input)
        
        search_filter_layout.addWidget(QLabel("    Show:"))
        
        btn_show_all = QPushButton("All")
        btn_show_all.clicked.connect(lambda: self.apply_filter("all"))
        search_filter_layout.addWidget(btn_show_all)
        
        btn_show_out_tolerance = QPushButton("Out of Tolerance")
        btn_show_out_tolerance.clicked.connect(lambda: self.apply_filter("out_tolerance"))
        search_filter_layout.addWidget(btn_show_out_tolerance)
        
        btn_show_mono = QPushButton("Mono files")
        btn_show_mono.clicked.connect(lambda: self.apply_filter("mono"))
        search_filter_layout.addWidget(btn_show_mono)
        
        btn_show_stereo = QPushButton("Stereo files")
        btn_show_stereo.clicked.connect(lambda: self.apply_filter("stereo"))
        search_filter_layout.addWidget(btn_show_stereo)
        
        btn_show_mp3 = QPushButton("MP3 files")
        btn_show_mp3.clicked.connect(lambda: self.apply_filter("mp3"))
        search_filter_layout.addWidget(btn_show_mp3)
        
        btn_show_wav = QPushButton("WAV files")
        btn_show_wav.clicked.connect(lambda: self.apply_filter("wav"))
        search_filter_layout.addWidget(btn_show_wav)
        
        self.info_label = QLabel("0 files loaded")
        self.info_label.setStyleSheet("font-weight: bold; color: #666; margin-left: 20px;")
        search_filter_layout.addWidget(self.info_label)
        search_filter_layout.addStretch()
        
        files_layout.addLayout(search_filter_layout)
        
        # Progress
        progress_layout = QHBoxLayout()
        progress_layout.setContentsMargins(0, 2, 0, 2)
        self.status_label = QLabel("")
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        progress_layout.addWidget(self.status_label)
        progress_layout.addWidget(self.progress_bar)
        progress_layout.addStretch()
        files_layout.addLayout(progress_layout)
        
        # File table
        self.file_table = QTableWidget()
        self.file_table.setColumnCount(10)
        
        headers = ["✓", "Audio Preview", "Filename", "LUFS Value", "Predicted Gain", "Length", "Audio Stats", "Convert to Mono", "Input Path", "Output Path"]
        self.file_table.setHorizontalHeaderLabels(headers)
        
        for col in range(10):
            item = self.file_table.horizontalHeaderItem(col)
            if item:
                item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)
        
        self.file_table.horizontalHeader().setStyleSheet("""
            QHeaderView::section {
                background-color: #e0e0e0;
                padding: 5px;
                border: 1px solid #c0c0c0;
                font-weight: bold;
                text-align: center;
            }
        """)
        
        self.file_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.file_table.setAlternatingRowColors(True)
        self.file_table.horizontalHeader().setStretchLastSection(True)
        self.file_table.setColumnWidth(0, 40)
        self.file_table.setColumnWidth(1, 150)
        self.file_table.setColumnWidth(2, 250)
        self.file_table.setColumnWidth(3, 100)
        self.file_table.setColumnWidth(4, 100)
        self.file_table.setColumnWidth(5, 70)
        self.file_table.setColumnWidth(6, 120)
        self.file_table.setColumnWidth(7, 120)
        self.file_table.setColumnWidth(8, 200)
        
        self.file_table.setAcceptDrops(True)
        self.file_table.setDragDropMode(QTableWidget.DropOnly)
        
        self.master_checkbox = QCheckBox()
        self.master_checkbox.setChecked(True)
        self.master_checkbox.stateChanged.connect(self.toggle_all_checkboxes)
        
        files_layout.addWidget(self.file_table)
        QTimer.singleShot(100, self.setup_master_checkbox_in_header)
        
        files_group.setLayout(files_layout)
        main_layout.addWidget(files_group)
        
        # Output & Processing
        output_group = QGroupBox("Output & Processing")
        output_layout = QVBoxLayout()
        output_layout.setSpacing(6)
        
        override_section_layout = QVBoxLayout()
        override_section_layout.setSpacing(4)
        
        self.use_override_checkbox = QCheckBox("Use Override Output Folder")
        self.use_override_checkbox.setChecked(False)
        self.use_override_checkbox.stateChanged.connect(self.toggle_override_folder)
        override_section_layout.addWidget(self.use_override_checkbox)
        
        override_folder_layout = QHBoxLayout()
        self.btn_select_override = QPushButton("Override Output Folder")
        self.btn_select_override.clicked.connect(self.select_override_folder)
        self.btn_select_override.setEnabled(False)
        override_folder_layout.addWidget(self.btn_select_override)
        
        self.override_label = QLabel("No override folder selected.")
        self.override_label.setWordWrap(True)
        self.override_label.setStyleSheet("color: #666; font-style: italic;")
        override_folder_layout.addWidget(self.override_label)
        
        override_section_layout.addLayout(override_folder_layout)
        output_layout.addLayout(override_section_layout)
        
        info_layout = QHBoxLayout()
        info_icon = QLabel("ℹ️")
        info_text = QLabel("By default, output files are saved in the same folder as input files.")
        info_text.setStyleSheet("color: #666; font-style: italic; font-size: 11px;")
        info_layout.addWidget(info_icon)
        info_layout.addWidget(info_text)
        info_layout.addStretch()
        output_layout.addLayout(info_layout)
        
        normalize_layout = QHBoxLayout()
        
        btn_normalize_selected = QPushButton("Normalize Checked")
        btn_normalize_selected.clicked.connect(self.normalize_selected)
        normalize_layout.addWidget(btn_normalize_selected)
        
        btn_normalize_all = QPushButton("Normalize All")
        btn_normalize_all.clicked.connect(self.normalize_all)
        normalize_layout.addWidget(btn_normalize_all)
        
        output_layout.addLayout(normalize_layout)
        
        output_group.setLayout(output_layout)
        main_layout.addWidget(output_group)
        
        self.setLayout(main_layout)
        self.resize(1200, 650)
        
        self.update_slider_value()
        self.update_info_label()

    def open_config_dialog(self):
        dialog = LUFSConfigDialog(self.config_manager, self)
        if dialog.exec_() == QDialog.Accepted:
            self.slider_widget.refresh_labels()
            self.update_slider_value()
            self.refresh_color_coding()

    def setup_master_checkbox_in_header(self):
        header = self.file_table.horizontalHeader()
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.addWidget(self.master_checkbox)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        
        x = header.sectionViewportPosition(0)
        width = header.sectionSize(0)
        height = header.height()
        
        container.setParent(header)
        container.setGeometry(x, 0, width, height)
        container.show()
        
        header.sectionResized.connect(self.reposition_master_checkbox)

    def reposition_master_checkbox(self, logical_index, old_size, new_size):
        if logical_index == 0:
            header = self.file_table.horizontalHeader()
            x = header.sectionViewportPosition(0)
            width = header.sectionSize(0)
            height = header.height()
            
            for child in header.children():
                if isinstance(child, QWidget) and child.findChild(QCheckBox):
                    child.setGeometry(x, 0, width, height)
                    break

    def stop_other_players(self, current_player):
        for row in range(self.file_table.rowCount()):
            player_widget = self.file_table.cellWidget(row, 1)
            if isinstance(player_widget, AudioPlayerWidget) and player_widget != current_player:
                player_widget.stop()

    def stop_all_audio(self):
        pygame.mixer.music.stop()
        for row in range(self.file_table.rowCount()):
            player_widget = self.file_table.cellWidget(row, 1)
            if isinstance(player_widget, AudioPlayerWidget):
                player_widget.stop()

    def closeEvent(self, event):
        try:
            self.stop_all_audio()
            # Clean up all temporary files
            for row in range(self.file_table.rowCount()):
                player_widget = self.file_table.cellWidget(row, 1)
                if isinstance(player_widget, AudioPlayerWidget):
                    player_widget.cleanup_all_temp_files()
            pygame.mixer.quit()
        except:
            pass
        event.accept()

    def toggle_all_checkboxes(self):
        self.master_checked = self.master_checkbox.isChecked()
        
        for row in range(self.file_table.rowCount()):
            item = self.file_table.item(row, 0)
            if item:
                if self.file_table.isRowHidden(row):
                    item.setCheckState(Qt.Unchecked)
                else:
                    item.setCheckState(Qt.Checked if self.master_checked else Qt.Unchecked)
        
        self.update_info_label()

    def get_audio_info(self, filepath):
        try:
            if not os.path.exists(filepath):
                return "File not found"
            sound = AudioSegment.from_file(filepath)
            channels = sound.channels
            sample_rate = sound.frame_rate
            channel_str = "Mono" if channels == 1 else "Stereo" if channels == 2 else f"{channels}ch"
            return f"{sample_rate/1000:.1f}kHz {channel_str}"
        except Exception as e:
            print(f"Error getting audio info for {filepath}: {e}")
            return "Unknown format"

    def get_audio_length(self, filepath):
        try:
            if not os.path.exists(filepath):
                return "0:00"
            sound = AudioSegment.from_file(filepath)
            duration_seconds = len(sound) / 1000.0
            minutes = int(duration_seconds // 60)
            seconds = int(duration_seconds % 60)
            return f"{minutes}:{seconds:02d}"
        except Exception as e:
            print(f"Error getting audio length for {filepath}: {e}")
            return "0:00"

    def get_suffix_color_for_lufs(self, lufs_value):
        return self.config_manager.get_color(lufs_value)

    def add_files(self):
        files, _ = QFileDialog.getOpenFileNames(self, "Add Audio Files", "", 
                                              "Audio files (*.wav *.mp3 *.flac *.ogg *.m4a *.aac)")
        if not files:
            return
            
        # Convert to absolute paths
        files = [os.path.abspath(f) for f in files]
            
        if len(files) > 1:
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(len(files))
            self.progress_bar.setValue(0)
            self.status_label.setText("Analyzing audio files...")
            
            for i, file in enumerate(files):
                self.progress_bar.setValue(i)
                QApplication.processEvents()
                self.add_list_item(file)
            
            self.progress_bar.setVisible(False)
            self.status_label.setText("")
        else:
            self.add_list_item(files[0])

    def add_list_item(self, filepath):
        # Ensure absolute path
        filepath = os.path.abspath(filepath)
        
        # Check if file exists
        if not os.path.exists(filepath):
            print(f"Warning: File not found: {filepath}")
            return
            
        filename = os.path.basename(filepath)
        self.status_label.setText(f"Analyzing: {filename}")
        
        row = self.file_table.rowCount()
        self.file_table.insertRow(row)
        
        # Checkbox
        checkbox_item = QTableWidgetItem()
        checkbox_item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
        checkbox_item.setCheckState(Qt.Checked if self.master_checked else Qt.Unchecked)
        self.file_table.setItem(row, 0, checkbox_item)
        
        # Audio player
        player_widget = AudioPlayerWidget(filepath)
        player_widget.set_parent_normalizer(self)
        self.file_table.setCellWidget(row, 1, player_widget)
        
        # Other columns
        self.file_table.setItem(row, 2, QTableWidgetItem(filename))
        self.file_table.setItem(row, 3, QTableWidgetItem("Analyzing..."))
        
        audio_length = self.get_audio_length(filepath)
        self.file_table.setItem(row, 5, QTableWidgetItem(audio_length))
        
        audio_info = self.get_audio_info(filepath)
        self.file_table.setItem(row, 6, QTableWidgetItem(audio_info))
        
        # Convert to Mono checkbox - only for stereo files
        if "Stereo" in audio_info:
            mono_checkbox = QCheckBox()
            mono_checkbox.setChecked(False)
            mono_checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    width: 18px;
                    height: 18px;
                }
            """)
            mono_checkbox_widget = QWidget()
            mono_checkbox_layout = QHBoxLayout(mono_checkbox_widget)
            mono_checkbox_layout.addWidget(mono_checkbox)
            mono_checkbox_layout.setAlignment(Qt.AlignCenter)
            mono_checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.file_table.setCellWidget(row, 7, mono_checkbox_widget)
        else:
            empty_widget = QWidget()
            self.file_table.setCellWidget(row, 7, empty_widget)
        
        self.file_table.setItem(row, 8, QTableWidgetItem(filepath))
        
        # Output path
        output_path = self.get_output_filename(filepath)
        suffix = self.suffix_input.text().strip()
        target_lufs = self.get_target_lufs()
        suffix_color = self.get_suffix_color_for_lufs(target_lufs)
        output_widget = OutputPathWidget(output_path, suffix, suffix_color)
        self.file_table.setCellWidget(row, 9, output_widget)
        
        # Store filepath
        self.file_table.item(row, 2).setData(Qt.UserRole, filepath)
        
        # Auto-analyze LUFS
        self.analyze_single_file(filepath, row)
        
        if not self.progress_bar.isVisible():
            self.status_label.setText("")
            
        self.update_info_label()

    def analyze_single_file(self, filepath, row):
        try:
            if not os.path.exists(filepath):
                raise FileNotFoundError(f"File not found: {filepath}")
                
            sound = AudioSegment.from_file(filepath)
            samples = np.array(sound.get_array_of_samples()).astype(np.float32)
            samples /= np.iinfo(sound.array_type).max

            meter = pyln.Meter(sound.frame_rate)
            loudness = meter.integrated_loudness(samples)
            
            self.lufs_values[filepath] = loudness
            
            lufs_value = f"{loudness:.2f} LUFS"
            self.file_table.setItem(row, 3, QTableWidgetItem(lufs_value))
            
            # Calculate predicted gain
            target_lufs = self.get_target_lufs()
            predicted_gain = target_lufs - loudness
            gain_text = f"{predicted_gain:+.1f} dB"
            gain_item = QTableWidgetItem(gain_text)
            
            # Color code the gain
            if abs(predicted_gain) <= 1.0:
                gain_item.setForeground(Qt.green)
            elif abs(predicted_gain) <= 3.0:
                gain_item.setForeground(QColor("#FF8C00"))
            else:
                gain_item.setForeground(Qt.red)
            
            self.file_table.setItem(row, 4, gain_item)
            
            # Color code LUFS based on tolerance
            diff = abs(loudness - target_lufs)
            color = Qt.green if diff <= self.tolerance else Qt.red
            
            lufs_item = self.file_table.item(row, 3)
            lufs_item.setForeground(color)
            
        except Exception as e:
            print(f"Error analyzing {filepath}: {e}")
            self.file_table.setItem(row, 3, QTableWidgetItem("Error"))
            self.file_table.setItem(row, 4, QTableWidgetItem("N/A"))
            lufs_item = self.file_table.item(row, 3)
            lufs_item.setForeground(Qt.darkRed)
        
        if not self.progress_bar.isVisible():
            self.update_info_label()

    def update_all_displays(self):
        suffix = self.suffix_input.text().strip()
        target_lufs = self.get_target_lufs()
        suffix_color = self.get_suffix_color_for_lufs(target_lufs)
        
        for row in range(self.file_table.rowCount()):
            filename_item = self.file_table.item(row, 2)
            if filename_item:
                filepath = filename_item.data(Qt.UserRole)
                if filepath:
                    output_path = self.get_output_filename(filepath)
                    output_widget = OutputPathWidget(output_path, suffix, suffix_color)
                    self.file_table.setCellWidget(row, 9, output_widget)
        
        self.update_info_label()

    def update_info_label(self):
        total_files = self.file_table.rowCount()
        selected_files = 0
        mono_conversions = 0
        out_of_tolerance = 0
        stereo_files = 0
        mono_files = 0
        mp3_files = 0
        wav_files = 0
        
        target_lufs = self.get_target_lufs()
        
        for row in range(total_files):
            filepath = self.get_filepath_for_row(row)
            
            checkbox_item = self.file_table.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                selected_files += 1
            
            if self.is_mono_conversion_enabled(row):
                mono_conversions += 1
            
            if filepath and filepath in self.lufs_values:
                loudness = self.lufs_values[filepath]
                diff = abs(loudness - target_lufs)
                if diff > self.tolerance:
                    out_of_tolerance += 1
            
            audio_stats_item = self.file_table.item(row, 6)
            if audio_stats_item:
                audio_stats = audio_stats_item.text()
                if "Stereo" in audio_stats:
                    stereo_files += 1
                elif "Mono" in audio_stats:
                    mono_files += 1
            
            if filepath:
                if filepath.lower().endswith('.mp3'):
                    mp3_files += 1
                elif filepath.lower().endswith('.wav'):
                    wav_files += 1
        
        info_text = f"{total_files} files loaded, {selected_files} selected, {out_of_tolerance} out of tolerance, {stereo_files} stereo files, {mono_files} mono files, {mp3_files} MP3 files, {wav_files} WAV files"
        
        if mono_conversions > 0:
            info_text = f"{total_files} files loaded, {selected_files} selected, {mono_conversions} will convert to mono, {out_of_tolerance} out of tolerance, {stereo_files} stereo files, {mono_files} mono files, {mp3_files} MP3 files, {wav_files} WAV files"
        
        self.info_label.setText(info_text)

    def filter_files(self):
        search_text = self.search_input.text().lower()
        for row in range(self.file_table.rowCount()):
            filename_item = self.file_table.item(row, 2)
            if filename_item:
                filename = filename_item.text().lower()
                show_row = search_text in filename
                self.file_table.setRowHidden(row, not show_row)

    def apply_filter(self, filter_type):
        self.current_filter = filter_type
        target_lufs = self.get_target_lufs()
        
        for row in range(self.file_table.rowCount()):
            show_row = True
            
            if filter_type == "out_tolerance":
                filepath = self.get_filepath_for_row(row)
                if filepath and filepath in self.lufs_values:
                    loudness = self.lufs_values[filepath]
                    diff = abs(loudness - target_lufs)
                    show_row = diff > self.tolerance
                else:
                    show_row = False
            elif filter_type == "mono":
                audio_stats_item = self.file_table.item(row, 6)
                if audio_stats_item:
                    show_row = "Mono" in audio_stats_item.text()
                else:
                    show_row = False
            elif filter_type == "stereo":
                audio_stats_item = self.file_table.item(row, 6)
                if audio_stats_item:
                    show_row = "Stereo" in audio_stats_item.text()
                else:
                    show_row = False
            elif filter_type == "mp3":
                filepath = self.get_filepath_for_row(row)
                if filepath:
                    show_row = filepath.lower().endswith('.mp3')
                else:
                    show_row = False
            elif filter_type == "wav":
                filepath = self.get_filepath_for_row(row)
                if filepath:
                    show_row = filepath.lower().endswith('.wav')
                else:
                    show_row = False
            
            self.file_table.setRowHidden(row, not show_row)

    def refresh_color_coding(self):
        if not self.lufs_values:
            return
            
        target_lufs = self.get_target_lufs()
        
        for row in range(self.file_table.rowCount()):
            filename_item = self.file_table.item(row, 2)
            if filename_item:
                filepath = filename_item.data(Qt.UserRole)
                if filepath in self.lufs_values:
                    loudness = self.lufs_values[filepath]
                    diff = abs(loudness - target_lufs)
                    
                    color = Qt.green if diff <= self.tolerance else Qt.red
                    lufs_item = self.file_table.item(row, 3)
                    if lufs_item:
                        lufs_item.setForeground(color)
                    
                    predicted_gain = target_lufs - loudness
                    gain_text = f"{predicted_gain:+.1f} dB"
                    gain_item = self.file_table.item(row, 4)
                    if not gain_item:
                        gain_item = QTableWidgetItem(gain_text)
                        self.file_table.setItem(row, 4, gain_item)
                    else:
                        gain_item.setText(gain_text)
                    
                    if abs(predicted_gain) <= 1.0:
                        gain_item.setForeground(Qt.green)
                    elif abs(predicted_gain) <= 3.0:
                        gain_item.setForeground(QColor("#FF8C00"))
                    else:
                        gain_item.setForeground(Qt.red)
        
        self.update_info_label()

    def clear_files(self):
        self.stop_all_audio()
        self.file_table.setRowCount(0)
        self.lufs_values.clear()
        self.update_info_label()

    def remove_selected_files(self):
        self.stop_all_audio()
        
        rows_to_remove = []
        for row in range(self.file_table.rowCount()):
            checkbox_item = self.file_table.item(row, 0)
            if checkbox_item and checkbox_item.checkState() == Qt.Checked:
                rows_to_remove.append(row)
        
        for row in reversed(rows_to_remove):
            filename_item = self.file_table.item(row, 2)
            if filename_item:
                filepath = filename_item.data(Qt.UserRole)
                if filepath in self.lufs_values:
                    del self.lufs_values[filepath]
            self.file_table.removeRow(row)
        
        self.update_info_label()

    def analyze_lufs(self):
        self.stop_all_audio()
        self.lufs_values.clear()
        
        file_count = self.file_table.rowCount()
        if file_count > 0:
            self.progress_bar.setVisible(True)
            self.progress_bar.setMaximum(file_count)
            self.progress_bar.setValue(0)
            self.status_label.setText("Re-analyzing audio files...")

        for row in range(self.file_table.rowCount()):
            filename_item = self.file_table.item(row, 2)
            if not filename_item:
                continue
                
            filepath = filename_item.data(Qt.UserRole)
            if not filepath:
                continue
            
            self.progress_bar.setValue(row)
            filename = os.path.basename(filepath)
            self.status_label.setText(f"Re-analyzing: {filename}")
            QApplication.processEvents()
            
            self.file_table.setItem(row, 3, QTableWidgetItem("Analyzing..."))
            self.analyze_single_file(filepath, row)

        self.progress_bar.setVisible(False)
        self.status_label.setText("")
        self.update_info_label()

    def get_selected_filepaths(self, only_checked=False):
        filepaths = []
        for row in range(self.file_table.rowCount()):
            filename_item = self.file_table.item(row, 2)
            if not filename_item:
                continue
                
            if only_checked:
                checkbox_item = self.file_table.item(row, 0)
                if not checkbox_item or checkbox_item.checkState() != Qt.Checked:
                    continue
            
            filepath = filename_item.data(Qt.UserRole)
            if filepath:
                filepaths.append(filepath)
        return filepaths

    def is_mono_conversion_enabled(self, row):
        mono_widget = self.file_table.cellWidget(row, 7)
        if mono_widget:
            checkbox = mono_widget.findChild(QCheckBox)
            if checkbox:
                return checkbox.isChecked()
        return False

    def get_filepath_for_row(self, row):
        filename_item = self.file_table.item(row, 2)
        if filename_item:
            return filename_item.data(Qt.UserRole)
        return None

    def normalize_files(self, filepaths):
        if not filepaths:
            QMessageBox.warning(self, "No Files", "No files selected for normalization.")
            return

        if self.use_override_folder and not self.output_folder:
            QMessageBox.warning(
                self,
                "Missing Override Folder",
                "Override output folder is enabled but no folder is selected. "
                "Please select an override folder or disable the override option."
            )
            return

        target_lufs = self.get_target_lufs()
        suffix = self.suffix_input.text().strip()

        files_to_process = []
        for row in range(self.file_table.rowCount()):
            filepath = self.get_filepath_for_row(row)
            if filepath and filepath in filepaths:
                convert_to_mono = self.is_mono_conversion_enabled(row)
                files_to_process.append((filepath, convert_to_mono))

        # Check for existing outputs
        existing = []
        for fp, _ in files_to_process:
            out = self.get_output_filename(fp)
            if out and out not in ["No override folder selected"] and os.path.exists(out):
                existing.append(os.path.basename(out))

        if existing:
            msg = "\n".join(existing[:5])
            if len(existing) > 5:
                msg += f"\n... and {len(existing) - 5} more files"
            reply = QMessageBox.question(
                self,
                "Overwrite Files?",
                f"The following files already exist:\n\n{msg}\n\nOverwrite?",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return

        # UI setup
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(files_to_process))
        self.progress_bar.setValue(0)
        self.status_label.setText("Normalizing audio files...")

        # normalization parameters
        tol = 0.01    # ±0.01 LUFS tolerance
        max_iter = 50
        
        successful_count = 0
        failed_files = []

        for i, (fp, to_mono) in enumerate(files_to_process):
            try:
                self.progress_bar.setValue(i)
                name = os.path.basename(fp)
                mono_text = " (mono)" if to_mono else ""
                self.status_label.setText(f"Normalizing: {name}{mono_text}")
                QApplication.processEvents()

                # Check if input file exists
                if not os.path.exists(fp):
                    raise FileNotFoundError(f"Input file not found: {fp}")

                # --- load & preprocess ---
                sound = AudioSegment.from_file(fp)
                if to_mono:
                    sound = sound.set_channels(1)
                sound = sound.set_frame_rate(48000)

                # build sample array in float32 [-1..+1]
                raw = np.array(sound.get_array_of_samples(), dtype=np.float32)
                divisor = float(2 ** (8 * sound.sample_width - 1))
                samples = raw / divisor

                # for stereo, reshape to (n,2)
                if sound.channels > 1:
                    samples = samples.reshape(-1, sound.channels)

                # meter
                meter = pyln.Meter(sound.frame_rate)
                cur = meter.integrated_loudness(samples)

                # --- initial normalization ---
                norm = pyln.normalize.loudness(samples, cur, target_lufs)
                cur = meter.integrated_loudness(norm)

                # --- iterative refine ---
                it = 0
                while abs(cur - target_lufs) > tol and it < max_iter:
                    it += 1
                    correction = target_lufs - cur
                    norm = pyln.normalize.loudness(norm, cur, cur + correction)
                    cur = meter.integrated_loudness(norm)

                # --- back to AudioSegment ---
                scaled = (norm * divisor).astype({2: np.int16, 3: np.int32, 4: np.int32}.get(sound.sample_width, np.int16))
                if sound.channels > 1:
                    scaled = scaled.flatten()
                seg = AudioSegment(
                    scaled.tobytes(),
                    frame_rate=sound.frame_rate,
                    sample_width=sound.sample_width,
                    channels=sound.channels
                )

                # --- export ---
                out_path = self.get_output_filename(fp)
                if not out_path or out_path in ["No override folder selected"]:
                    raise RuntimeError("Invalid output path")

                # Ensure output directory exists
                out_dir = os.path.dirname(out_path)
                if not os.path.exists(out_dir):
                    os.makedirs(out_dir, exist_ok=True)
                
                # export as 24-bit WAV for good quality
                seg.export(out_path, format="wav", parameters=["-acodec", "pcm_s24le"])
                
                # Verify the output file was created
                if not os.path.exists(out_path):
                    raise RuntimeError(f"Output file was not created: {out_path}")
                
                successful_count += 1

            except Exception as e:
                failed_files.append((os.path.basename(fp), str(e)))
                print(f"Failed on {os.path.basename(fp)}: {e}")

        self.progress_bar.setVisible(False)
        self.status_label.setText("")
        
        # Show results
        if failed_files:
            failed_msg = "\n".join([f"• {name}: {error}" for name, error in failed_files[:5]])
            if len(failed_files) > 5:
                failed_msg += f"\n... and {len(failed_files) - 5} more files"
            
            QMessageBox.warning(self, "Processing Complete", 
                              f"Normalization complete!\n\n"
                              f"✓ {successful_count} files processed successfully\n"
                              f"✗ {len(failed_files)} files failed\n\n"
                              f"Failed files:\n{failed_msg}")
        else:
            QMessageBox.information(self, "Success",
                                  f"Normalization complete! {successful_count} files processed successfully.")

    def normalize_all(self):
        filepaths = self.get_selected_filepaths(only_checked=False)
        self.normalize_files(filepaths)

    def normalize_selected(self):
        filepaths = self.get_selected_filepaths(only_checked=True)
        self.normalize_files(filepaths)

    def open_help_documentation(self):
        dlg = QDialog(self)
        dlg.setWindowTitle("Help / Documentation")
        dlg.resize(600, 800)

        browser = QTextBrowser(dlg)
        
        # Try to find help documentation - check multiple locations
        help_found = False
        
        # First try README.md in root
        readme_path = resource_path("README.md")
        if os.path.exists(readme_path):
            browser.setSource(QUrl.fromLocalFile(readme_path))
            help_found = True
        else:
            # Try docs folder
            docs_path = resource_path("docs/help_documentation.md")
            if os.path.exists(docs_path):
                browser.setSource(QUrl.fromLocalFile(docs_path))
                help_found = True
        
        if not help_found:
            # Fallback text if help file not found
            browser.setHtml("""
            <h1>Unreal Audio Normalizer - Help</h1>
            <h2>Basic Usage:</h2>
            <ol>
                <li><strong>Add Files:</strong> Click "Add Audio Files" or drag & drop audio files into the application</li>
                <li><strong>Set Target LUFS:</strong> Use the slider to select your desired LUFS level</li>
                <li><strong>Configure Output:</strong> Set file suffix and optionally choose override output folder</li>
                <li><strong>Process:</strong> Click "Normalize Checked" or "Normalize All"</li>
            </ol>
            
            <h2>LUFS Presets:</h2>
            <ul>
                <li><strong>-12 LUFS:</strong> SFX (Sound Effects)</li>
                <li><strong>-14 LUFS:</strong> Music</li>
                <li><strong>-16 LUFS:</strong> Dialog</li>
                <li><strong>-18 LUFS:</strong> UI (User Interface)</li>
                <li><strong>-20 LUFS:</strong> Ambient</li>
            </ul>
            
            <h2>Supported Formats:</h2>
            <p><strong>Input:</strong> WAV, MP3, FLAC, OGG, M4A, AAC</p>
            <p><strong>Output:</strong> 24-bit WAV files</p>
            
            <h2>Features:</h2>
            <ul>
                <li>Batch processing of multiple files</li>
                <li>Audio preview with built-in player</li>
                <li>Mono conversion option for stereo files</li>
                <li>Custom output directory</li>
                <li>Configurable LUFS tolerance</li>
                <li>File filtering and search</li>
            </ul>
            
            <h2>Troubleshooting:</h2>
            <p><strong>"Cannot find specified file" Error:</strong></p>
            <ul>
                <li>Ensure all input files exist and are accessible</li>
                <li>Check write permissions to output directory</li>
                <li>Try running as administrator if needed</li>
            </ul>
            
            <p><strong>MP3 Files Not Loading:</strong></p>
            <ul>
                <li>The application includes FFmpeg for MP3 support</li>
                <li>If issues persist, try converting to WAV first</li>
            </ul>
            """)

        layout = QVBoxLayout(dlg)
        layout.addWidget(browser)
        dlg.exec_()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = AudioNormalizer()
    win.show()
    sys.exit(app.exec_())