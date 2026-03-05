import sys
import os
import datetime
import configparser
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QTextEdit, QFrame)
from PyQt6.QtCore import QTimer, pyqtSignal, QObject, Qt, QFile, QIODevice, QUrl, QTextStream, QByteArray
from PyQt6.QtGui import QFont, QCursor, QPixmap
import pygame
import time
import fcntl

# HBELL Wifi Multicast Receiver
# V1.3.0
#
# 2026-02-17 Extended to support 10 stores - Hyukjoo

CONFIG_PATH = '/home/pi/HBELL-Receiver/hbell.cfg'
LOG_FILE_DIR = "/home/pi/log/"
RING_FILE = "/home/pi/ring.wav"
NUM_LINES_TO_READ = 10
UPDATE_INTERVAL_MS = 1000
MAX_STORES = 5
NUMS_PER_STORE = 7
ALIVE_INTERVAL = 25  # seconds

# Font sizes per MAX_STORES
FONT_TABLE = {
    2: (140, 100),
    3: (120, 85),
    4: (100, 70),
    5: (80, 55),
    6: (65, 45),
    7: (55, 38),
    8: (45, 32),
    9: (40, 28),
    10: (36, 25),
}

def load_config():
    """Load configuration from hbell.cfg"""
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    enable_sound = config.getboolean('DISPLAY', 'ENABLE_SOUND', fallback=True)
    max_stores = config.getint('DISPLAY', 'MAX_STORES', fallback=4)
    store_cnt = config.getint('DISPLAY', 'STORE_CNT', fallback=max_stores)
    return enable_sound, max_stores, store_cnt

ENABLE_SOUND, MAX_STORES, STORE_CNT = load_config()
FONT_SIZE_LARGE, FONT_SIZE_SMALL = FONT_TABLE.get(MAX_STORES, (80, 55))

# --- DataUpdater Class ---
class DataUpdater(QTextEdit):
    data_updated = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(UPDATE_INTERVAL_MS)

        pygame.mixer.init()
        self.sound = pygame.mixer.Sound(RING_FILE)

        self.monitors = [
            {"file": f"/home/pi/log/alive{i}.txt", "is_alive": False, "flag": "DOWN", "name": str(i)}
            for i in range(MAX_STORES)
        ]

    def file_open(self, file_path, mode='r', max_retries=10):
        for _ in range(max_retries):
            try:
                lock_type = fcntl.LOCK_SH if mode == 'r' else fcntl.LOCK_EX
                f = open(file_path, mode)
                fcntl.flock(f, lock_type | fcntl.LOCK_NB)
                return f
            except BlockingIOError:
                f.close()
                time.sleep(0.1)
        raise TimeoutError(f"File Lock failed: {file_path}")
        
    def play_sound(self):
        if ENABLE_SOUND:
            self.sound.play()

    def put_err_log(self, store_nm, flag):
        self.create_empty_err_log_file_if_not_exists()
        err_file = os.path.join(LOG_FILE_DIR, f"err-{datetime.date.today()}.log")
        with open(err_file, "a") as file:
            now = datetime.datetime.now()
            file.write(f"{now} {store_nm} {flag}\r\n")

    def create_empty_err_log_file_if_not_exists(self):
        err_file = os.path.join(LOG_FILE_DIR, f"err-{datetime.date.today()}.log")
        if not os.path.exists(err_file):
            try:
                open(err_file, 'w').close()
            except Exception as e:
                print(f"Error: File '{err_file}' not created: {e}")

    def create_empty_file_if_not_exists(self):
        log_file = os.path.join(LOG_FILE_DIR, f"{datetime.date.today()}.log")
        if not os.path.exists(log_file):
            try:
                open(log_file, 'w').close()
            except Exception as e:
                print(f"Error: File '{log_file}' not created: {e}")

    def clean_log_file(self):
        ring = False
        log_file = os.path.join(LOG_FILE_DIR, f"{datetime.date.today()}.log")
        f = None
        
        try:
            f = self.file_open(log_file, 'r')
            lines = f.readlines()
        except FileNotFoundError:
            return False
        finally:
            if f:
                fcntl.flock(f, fcntl.LOCK_UN)
                f.close()
                
        result = []
        for line in lines:
            parts = line.strip().split(',')
            if len(parts) < 2:
                continue

            if parts[1] == '-':
                for i in range(len(result) -1, -1, -1):
                    r_parts = result[i].strip().split(',')
                    if r_parts[0] == parts[0] and r_parts[2] == parts[2] and r_parts[1] == '+':
                        result.pop(i)
                        break
            else:
                result.append(line)

        try:
            f = self.file_open(log_file, 'w')
            f.writelines(result)
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)
            f.close()

        return ring
        
    def read_last_lines(self, num_lines=NUM_LINES_TO_READ):
        log_file = os.path.join(LOG_FILE_DIR, f"{datetime.date.today()}.log")
        try:
            with open(log_file, 'r') as f:
                lines = f.readlines()
            return lines
        except FileNotFoundError:
            return []

    def update_data(self):
        self.create_empty_file_if_not_exists()
        if self.clean_log_file():
            self.play_sound()

        cur_time = int(time.time())
        for monitor in self.monitors:
            if os.path.exists(monitor["file"]):
                file_time = os.path.getmtime(monitor["file"])
                is_currently_alive = (cur_time - file_time) <= ALIVE_INTERVAL

                if is_currently_alive and not monitor["is_alive"]:
                    monitor["is_alive"] = True
                    monitor["flag"] = "UP"
                    self.put_err_log(monitor["name"], monitor["flag"])
                elif not is_currently_alive and monitor["is_alive"]:
                    monitor["is_alive"] = False
                    monitor["flag"] = "DOWN"
                    self.put_err_log(monitor["name"], monitor["flag"])
        
        log_lines = self.read_last_lines()
        log_content = "".join(log_lines)
        
        if self.toPlainText() != log_content:
             self.play_sound()
             self.setPlainText(log_content)

        self.data_updated.emit({
            "text": log_content,
            "alive_statuses": [m["is_alive"] for m in self.monitors]
        })

# --- MyWidget Class ---
class MyWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.data_updater = DataUpdater()
        self.data_updater.data_updated.connect(self.update_text)
        self.init_ui()
        
    def init_ui(self):
        self.setGeometry(0, 0, 1920, 1080)
        
        # --- Main Layout ---
        self.layout_base = QHBoxLayout()
        self.setLayout(self.layout_base)

        # --- Store Names Column ---
        store_names_widget = QWidget()
        store_names_widget.setFixedWidth(450)
        store_names_widget.setStyleSheet("background-color: white;")
        layout_store_names = QVBoxLayout(store_names_widget)
        layout_store_names.setContentsMargins(0, 0, 0, 0)
        layout_store_names.setSpacing(0)

        # 1080 / 5 = 216 per store
        store_row_height = 1080 // MAX_STORES

        store_pixmaps = [f"store{i+1}.png" for i in range(MAX_STORES)]
        self.store_name_labels = []
        for i, pixmap_file in enumerate(store_pixmaps):
            label = QLabel()
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            if i < STORE_CNT and os.path.exists(pixmap_file):
                pixmap = QPixmap(pixmap_file)
                label.setPixmap(pixmap.scaled(450, store_row_height, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
            else:
                label.setFixedSize(450, store_row_height)

            self.store_name_labels.append(label)
            layout_store_names.addWidget(label)
            if i < STORE_CNT - 1:
                h_line = QFrame()
                h_line.setFrameShape(QFrame.Shape.HLine)
                h_line.setFrameShadow(QFrame.Shadow.Sunken)
                h_line.setStyleSheet("border-width: 5px; border-style: solid; border-color: black;")
                layout_store_names.addWidget(h_line)

        # Clear pixmaps for hidden stores
        for i in range(STORE_CNT, MAX_STORES):
            self.store_name_labels[i].setPixmap(QPixmap())

        self.layout_base.addWidget(store_names_widget)

        # --- Vertical Separator ---
        v_line1_container = QWidget()
        v_line1_container.setFixedWidth(6)
        v_line1_layout = QVBoxLayout(v_line1_container)
        v_line1_layout.setContentsMargins(0, 0, 0, 0)
        v_line1_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        v_line1 = QFrame()
        v_line1.setFrameShape(QFrame.Shape.VLine)
        v_line1.setFrameShadow(QFrame.Shadow.Sunken)
        v_line1.setStyleSheet("border-width: 2px; border-style: solid; border-color: black;")
        v_line1.setFixedHeight(store_row_height * STORE_CNT + (STORE_CNT - 1) * 10)
        
        v_line1_layout.addWidget(v_line1)
        self.layout_base.addWidget(v_line1_container)
        
        # --- Number Columns ---
        self.num_labels = []
        
        # Big numbers column
        big_numbers_widget = QWidget()
        big_numbers_widget.setFixedWidth(950)
        big_numbers_widget.setStyleSheet("background-color: white;")
        layout_numbers_b = QVBoxLayout(big_numbers_widget)
        layout_numbers_b.setContentsMargins(0, 0, 0, 0)
        layout_numbers_b.setSpacing(0)

        # Small numbers column
        small_numbers_widget = QWidget()
        small_numbers_widget.setStyleSheet("background-color: white;")
        layout_numbers_s = QVBoxLayout(small_numbers_widget)
        layout_numbers_s.setContentsMargins(0, 0, 0, 0)
        layout_numbers_s.setSpacing(0)

        font_large = QFont('Arial', FONT_SIZE_LARGE)
        font_small = QFont('Arial', FONT_SIZE_SMALL)

        for i in range(MAX_STORES):
            row_labels = []
            
            layout_numline_b = QHBoxLayout()
            layout_numline_b.setSpacing(50)
            
            layout_numline_s_container = QVBoxLayout()
            layout_numline_s1 = QHBoxLayout()
            layout_numline_s2 = QHBoxLayout()
            layout_numline_s_container.addLayout(layout_numline_s1)
            layout_numline_s_container.addLayout(layout_numline_s2)

            for j in range(NUMS_PER_STORE):
                label = QLabel("")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                
                if j < 3: # Big numbers
                    label.setFont(font_large)
                    label.setStyleSheet("font-weight: bold")
                    if j == 0:
                        label.setStyleSheet("color: red; font-weight: bold")
                    layout_numline_b.addWidget(label)
                else: # Small numbers
                    label.setFont(font_small)
                    if j == 6: # Status indicator
                         label.setStyleSheet("color: red")
                    
                    if j < 5:
                        layout_numline_s1.addWidget(label)
                    else:
                        layout_numline_s2.addWidget(label)

                row_labels.append(label)
            
            self.num_labels.append(row_labels)
            layout_numbers_b.addLayout(layout_numline_b)
            
            if i < STORE_CNT - 1:
                h_line_b = QFrame()
                h_line_b.setFrameShape(QFrame.Shape.HLine)
                h_line_b.setFrameShadow(QFrame.Shadow.Sunken)
                h_line_b.setStyleSheet("border-width: 5px; border-style: solid; border-color: black;")
                layout_numbers_b.addWidget(h_line_b)
                
            layout_numbers_s.addLayout(layout_numline_s_container)
            if i < STORE_CNT - 1:
                h_line_s = QFrame()
                h_line_s.setFrameShape(QFrame.Shape.HLine)
                h_line_s.setFrameShadow(QFrame.Shadow.Sunken)
                h_line_s.setStyleSheet("border-width: 5px; border-style: solid; border-color: black;")
                layout_numbers_s.addWidget(h_line_s)
            
        # Cover unused store rows
        if STORE_CNT < MAX_STORES:
            self.cover_label = QLabel(self)
            self.cover_label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
            cover_y = store_row_height * STORE_CNT + (STORE_CNT - 1) * 10
            cover_h = 1080 - cover_y
            cover_file = f"cover_{MAX_STORES - STORE_CNT}.png"
            cover_pixmap = QPixmap(cover_file)
            self.cover_label.setGeometry(0, cover_y, 1920, cover_h)
            for i in range(STORE_CNT, MAX_STORES):
                self.num_labels[i][6].hide()
            self.cover_label.setPixmap(cover_pixmap)
            QTimer.singleShot(0, self.cover_label.raise_)
            self.cover_label.raise_()

        self.layout_base.addWidget(big_numbers_widget)
        self.layout_base.addWidget(small_numbers_widget)
        
    def update_text(self, data):
        new_text = data["text"]
        alive_statuses = data["alive_statuses"]
        
        stores_data = [[] for _ in range(MAX_STORES)]
        
        for line in reversed(new_text.strip().split('\n')):
            if not line:
                continue
            try:
                parts = line.split(',')
                store_idx = int(parts[0][2])
                if 0 <= store_idx < MAX_STORES and len(stores_data[store_idx]) < NUMS_PER_STORE:
                    stores_data[store_idx].append(parts[2])
            except (IndexError, ValueError) as e:
                print(f"Skipping malformed line: {line} - Error: {e}")
                continue

        for i, store_data in enumerate(stores_data):
            while len(store_data) < NUMS_PER_STORE:
                store_data.append(" ")
            
            for j in range(6):
                self.num_labels[i][j].setText(store_data[j])

            status_label = self.num_labels[i][6]
            if alive_statuses[i]:
                status_label.setText(store_data[6])
                status_label.setStyleSheet("color: black")
            else:
                status_label.setText("*")
                status_label.setStyleSheet("color: red")

        self.showFullScreen()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = MyWidget()
    widget.setCursor(QCursor(Qt.CursorShape.BlankCursor))
    widget.showFullScreen()
    sys.exit(app.exec())
