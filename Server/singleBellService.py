import sys
import os
import datetime
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QTextEdit)
from PyQt6.QtCore import QTimer, pyqtSignal, QObject, Qt, QFile, QIODevice, QUrl, QTextStream, QByteArray
from PyQt6.QtGui import QFont, QCursor, QPixmap
from PyQt6.QtWidgets import QFrame
import pygame
import time
import configparser
import psutil

config = configparser.ConfigParser()
config.read('/home/pi/hbell.cfg')
            
STORE_NUMBER = config['STORE']['ADDRESS']

FILE_ALIVE = "/home/pi/log/alive1.txt"
if STORE_NUMBER == "001":
    FILE_ALIVE = "/home/pi/log/alive1.txt"
elif STORE_NUMBER == "002":
    FILE_ALIVE = "/home/pi/log/alive2.txt"
elif STORE_NUMBER == "003":
    FILE_ALIVE = "/home/pi/log/alive3.txt"
elif STORE_NUMBER == "004":
    FILE_ALIVE = "/home/pi/log/alive4.txt"

ISALIVE = True
LOG_FILE_DIR = "/home/pi/log/"
RING_FILE = "ring.wav"
UPDATE_INTERVAL_MS = 1000
ALIVE_INTERVAL = 7 # seconds

class DataUpdater(QTextEdit):
    data_updated = pyqtSignal(str)

    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        self.curTxt = ""
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(UPDATE_INTERVAL_MS)

        pygame.mixer.init()
        self.sound = pygame.mixer.Sound(RING_FILE)

    def play_sound(self):
        self.sound.play()

    def is_file_open(self, file_path):
        for proc in psutil.process_iter(['pid', 'open_files']):
            try:
                for file in proc.info['open_files'] or []:
                    if file.path == file_path:
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False
    def create_empty_file_if_not_exists(self):
        log_file = LOG_FILE_DIR + str(datetime.date.today()) + ".log"

        if not os.path.exists(log_file):
            try:
                with open(log_file, 'w'):
                    pass
            except Exception as e:
                print(f"Error: File '{log_file}' not created.")

    def clean_log_file(self):
        ring = False
        log_file = LOG_FILE_DIR + str(datetime.date.today()) + ".log"
        try:
            with open(log_file, "r") as num_file:
                lines = num_file.readlines()
        except FileNotFoundError:
            return f"Error: File '{log_file}' not found."

        while self.is_file_open(log_file):
            time.sleep(0.01)  # Wait until the file is not open by another process
            
        with open(log_file, "w") as num_file:
            delItems = {}
            for i in reversed(lines):
                lineArr = i.split(",")
                if len(lineArr) < 3:
                    lines.remove(i)
                    continue
                if not lineArr[0].isdigit():
                    lines.remove(i)
                    continue
                if not lineArr[2].replace('\n','').isdigit():
                    lines.remove(i)
                    continue
                if lineArr[2].replace('\n','') == '99999':
                    ring = True
                if lineArr[1] == '-':
                    delItems[lineArr[2].strip('\n')] = lineArr[0]
                    lines.remove(i)
                else:
                    if lineArr[2].strip('\n') in delItems and lineArr[0] == delItems[lineArr[2].strip('\n')]:
                        lines.remove(i)
            num_file.writelines(lines)
        return ring
                                
    def read_last_lines(self):
        log_file = LOG_FILE_DIR + str(datetime.date.today()) + ".log"
        file = QFile(log_file)
        lines = []
        stream = QTextStream(file)
        if not file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
            return None
        while not stream.atEnd():
            lines.append(stream.readLine())
        file.close()

        return lines

    def update_data(self):
        self.create_empty_file_if_not_exists()
        ring = self.clean_log_file()
        if ring:
            self.play_sound()

        if os.path.exists(FILE_ALIVE):
            global ISALIVE
            cur_time = int(time.time())
            file_time = os.path.getmtime(FILE_ALIVE)
            if cur_time - file_time > ALIVE_INTERVAL:
                ISALIVE = False
            else:
                ISALIVE = True
        else:
            ISALIVE = False

        file = QFile(self.filename)
        if file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
            text = file.readAll()
        else:
            self.setPlainText("Failed to open file.")
        file.close()

        log = self.read_last_lines()
        log_b_arr = QByteArray()
        for i in log:
            if i.split(',')[0] == STORE_NUMBER:
                i += "\n"
                encoded_string = i.encode('utf-8')
                log_b_arr.append(QByteArray(encoded_string))

        if text != log_b_arr:
            self.play_sound()

            text = log_b_arr
            self.curTxt = log_b_arr

            file = QFile(self.filename)
            if not file.open(QIODevice.OpenModeFlag.WriteOnly):
                return

            dataStream = QTextStream(file)
            dataStream << log_b_arr
            file.close()

        self.setPlainText(str(text, 'utf-8'))
        self.data_updated.emit(str(text, 'utf-8'))

class MyWidget(QWidget):
    def __init__(self, filename):
        super().__init__()

        self.label = QLabel(self)
        self.pixmap = QPixmap("backgroundS_err.png")
        self.label.setPixmap(self.pixmap)

        self.layout = QVBoxLayout(self)
        self.layout_base = QHBoxLayout()
        self.layout_base.setContentsMargins(0, 0, 0, 0)
        self.layout_base.setSpacing(0)
        self.layout1 = QVBoxLayout()
        self.layout1.setSpacing(0)
        self.layout2 = QVBoxLayout()
        self.layout2.setSpacing(0)

        self.filename = filename
        self.data_updater = DataUpdater(filename)

        self.labels = [QLabel("") for _ in range(8)]
        
        font_small = QFont('Arial', 120)
        font_large = QFont('Arial', 210)

        colors = ['#F5F5DC', '#FFE4E1']

        for i in range(3):
            self.labels[i].setFont(font_large)
            self.labels[i].setAlignment(Qt.AlignmentFlag.AlignCenter)
            if i == 2:
                self.labels[i].setStyleSheet(f"color: red; font-weight: bold; background-color: {colors[i % 2]}")
            else:
                self.labels[i].setStyleSheet(f"font-weight: bold; background-color: {colors[i % 2]}")
            self.layout1.addWidget(self.labels[i])

        for i in range(3, 8):
            self.labels[i].setFont(font_small)
            self.labels[i].setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.labels[i].setStyleSheet(f"font-weight: bold; background-color: {colors[i % 2]}")
            self.layout2.addWidget(self.labels[i])
        
#        self.labels[7].setStyleSheet(f"color: red; font-weight: bold; background-color: {colors[7 % 2]}")

        # 가운데 세로줄 추가
        self.separator = QFrame()
        self.separator.setFrameShape(QFrame.Shape.VLine)
        self.separator.setFrameShadow(QFrame.Shadow.Plain)
        self.separator.setLineWidth(30)  # 세로줄 두께
        # 초기 색 (ISALIVE True = 진한 회색)
        self.separator.setStyleSheet("color: black; background-color: #404040;")

        
        self.layout_base.addLayout(self.layout1, 6)
        self.layout_base.addWidget(self.separator)  # 가운데 세로줄
        self.layout_base.addLayout(self.layout2, 4)

        self.layout.addLayout(self.layout_base)
        
        self.data_updater.data_updated.connect(self.update_text)

    def update_text(self, new_text):
        arr = new_text.split('\n')
        while len(arr) < 9:
            arr.insert(0, "000,+, ")
        
        self.labels[2].setText(arr[len(arr)-2].split(',')[2])
        self.labels[1].setText(arr[len(arr)-3].split(',')[2])
        self.labels[0].setText(arr[len(arr)-4].split(',')[2])
        self.labels[7].setText(arr[len(arr)-5].split(',')[2])
        self.labels[6].setText(arr[len(arr)-6].split(',')[2])
        self.labels[5].setText(arr[len(arr)-7].split(',')[2])
        self.labels[4].setText(arr[len(arr)-8].split(',')[2])
        self.labels[3].setText(arr[len(arr)-9].split(',')[2])

        if ISALIVE:
            self.separator.setStyleSheet("color: black; background-color: #FF0000;")
        else:
            self.separator.setStyleSheet("color: red; background-color: #FF0000;")
        self.label.setPixmap(self.pixmap)

if __name__ == '__main__':
    app = QApplication(sys.argv)

    widget = MyWidget("cur_num.csv")
    widget.setCursor(QCursor(Qt.CursorShape.BlankCursor))

    widget.showFullScreen()

    sys.exit(app.exec())

