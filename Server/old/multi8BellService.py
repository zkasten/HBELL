import sys
import os
import datetime
import time
import psutil
import pygame
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout)
from PyQt6.QtCore import QObject, QTimer, pyqtSignal, Qt, QFile, QIODevice, QTextStream, QByteArray
from PyQt6.QtGui import QFont, QCursor, QPixmap

# --- 설정값 (Configuration) ---
NUM_STORES = 8  # 매장 수
LOG_FILE_DIR = "/home/pi/log/"
RING_FILE = "ring.wav"
UPDATE_INTERVAL_MS = 1000
FONT_SIZE_LARGE = 70
FONT_SIZE_SMALL = 30
ALIVE_INTERVAL = 5  # seconds
FILENAME = "cur_num.csv"

# 파일 경로를 리스트로 관리 (os.path.join을 사용하여 경로 결합)
FILE_ALIVE_PATHS = [os.path.join(LOG_FILE_DIR, f"alive{i}.txt") for i in range(1, NUM_STORES + 1)]


class DataUpdater(QObject):
    # 시그널에 상태 리스트도 함께 전달
    data_updated = pyqtSignal(str, list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.curTxt = ""
        # is_alive 상태를 클래스 멤버 변수로 관리
        self.is_alive_status = [False] * NUM_STORES

        pygame.mixer.init()
        try:
            self.sound = pygame.mixer.Sound(RING_FILE)
        except pygame.error as e:
            print(f"Error loading sound file '{RING_FILE}': {e}")
            self.sound = None

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_data)
        self.timer.start(UPDATE_INTERVAL_MS)

    def is_file_open(self, file_path):
        for proc in psutil.process_iter(['pid', 'open_files']):
            try:
                for file in proc.info.get('open_files') or []:
                    if file.path == file_path:
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False

    def play_sound(self):
        if self.sound:
            self.sound.play()

    def get_todays_log_path(self):
        return os.path.join(LOG_FILE_DIR, f"{datetime.date.today()}.log")

    def create_empty_file_if_not_exists(self):
        log_file = self.get_todays_log_path()
        if not os.path.exists(log_file):
            try:
                open(log_file, 'w').close()
            except IOError as e:
                print(f"Error creating file '{log_file}': {e}")

    def clean_log_file(self):
        log_file = self.get_todays_log_path()
        print(log_file)
        try:
            with open(log_file, "r") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return

        if self.is_file_open(log_file):
            time.sleep(0.01)

        cleaned_lines = []
        del_items = {}
        for line in reversed(lines):
            parts = line.strip().split(",")
            if len(parts) < 3:
                continue

            log_time, status, call_num = parts[0], parts[1], parts[2]

            if status == '-':
                del_items[call_num] = log_time
            elif not (call_num in del_items and log_time == del_items[call_num]):
                cleaned_lines.append(line)

        with open(log_file, "w") as f:
            f.writelines(reversed(cleaned_lines))

    def read_log_lines(self):
        log_file = self.get_todays_log_path()
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                return f.readlines()
        except FileNotFoundError:
            return []

    def check_alive_status(self):
        cur_time = time.time()
        for i in range(NUM_STORES):
            try:
                file_time = os.path.getmtime(FILE_ALIVE_PATHS[i])
                self.is_alive_status[i] = (cur_time - file_time) <= ALIVE_INTERVAL
            except FileNotFoundError:
                self.is_alive_status[i] = False

    def update_data(self):
        self.create_empty_file_if_not_exists()
        self.clean_log_file()
        self.check_alive_status()
        
        try:
            with open(FILENAME, 'r', encoding='utf-8') as f:
                self.curTxt = f.readlines()
        except FileNotFoundError:
            return[]

        log_lines = self.read_log_lines()
        print(log_lines)
        log_text = "".join(log_lines)
        print(log_text)
        

        if self.curTxt != log_text:
            self.play_sound()
            self.curTxt = log_text
            
            with open(FILENAME, "w") as f:
                f.writelines(self.curTxt)
        
        # 업데이트된 텍스트와 alive 상태를 함께 시그널로 보냄
        self.data_updated.emit(self.curTxt, self.is_alive_status)


class MyWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Waiting Line Display")
        self.setup_ui()

        self.data_updater = DataUpdater(self)
        self.data_updater.data_updated.connect(self.update_display)

    def setup_ui(self):
        # 1080x1920 해상도 설정
        self.setGeometry(0, 0, 1080, 1920)

        # 배경 이미지 설정
        self.background_label = QLabel(self)
        self.background_pixmap = QPixmap("background8.png")
        self.background_label.setPixmap(self.background_pixmap.scaled(
            self.size(), 
            Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
            Qt.TransformationMode.SmoothTransformation
        ))
        self.background_label.setGeometry(0, 0, self.width(), self.height())
        
        # 메인 레이아웃을 QVBoxLayout으로 변경하여 세로로 배치
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(1, 1, 1, 1)
        self.main_layout.setSpacing(1)

        self.store_labels = [] # 라벨들을 저장할 2차원 리스트

        # 반복문으로 8개 매장 UI 생성
        for i in range(NUM_STORES):
            # 한 줄(row)을 위한 레이아웃
            row_layout = QHBoxLayout()
            row_layout.setSpacing(20)

            # 1. 매장 이름 이미지
            store_name_label = QLabel()
            pixmap = QPixmap(f"store{i+1}.png")
            store_name_label.setPixmap(pixmap.scaledToHeight(150, Qt.TransformationMode.SmoothTransformation))
            row_layout.addWidget(store_name_label, 2) # 비율 2

            # 2. 큰 번호 3개
            large_num_layout = QHBoxLayout()
            large_num_layout.setSpacing(40)
            row_labels = []

            for j in range(3):
                label = QLabel("-")
                label.setFont(QFont('Arial', FONT_SIZE_LARGE, QFont.Weight.Bold))
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                large_num_layout.addWidget(label)
                row_labels.append(label)

            row_layout.addLayout(large_num_layout, 5) # 비율 5

            # # 3. 작은 번호 4개
            # small_num_layout = QVBoxLayout()
            # small_num_row1 = QHBoxLayout()
            # small_num_row2 = QHBoxLayout()
            
            # for j in range(4):
            #     label = QLabel("-")
            #     label.setFont(QFont('Arial', FONT_SIZE_SMALL))
            #     label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            #     if j < 2:
            #         small_num_row1.addWidget(label)
            #     else:
            #         small_num_row2.addWidget(label)
            #     row_labels.append(label)
            
            # small_num_layout.addLayout(small_num_row1)
            # small_num_layout.addLayout(small_num_row2)
            
            # row_layout.addLayout(small_num_layout, 3) # 비율 3
            
            self.main_layout.addLayout(row_layout)
            self.store_labels.append(row_labels) # 생성된 라벨 리스트를 전체 리스트에 추가

    def update_display(self, new_text, is_alive_status):
        print("----update_display")
        print(new_text)
        # 8개 매장 데이터를 저장할 리스트 초기화
        stores_data = [[] for _ in range(NUM_STORES)]

        lines = new_text.strip().split('\n')
        for line in reversed(lines):
            print (f"update display: {line}")
            if not line:
                continue
            
            try:
                log_id, _, call_num = line.split(',')
                print(f"{log_id} --- {_} --- {call_num}")
                # log_id (예: KIOSK_1)에서 매장 인덱스(0-7) 추출
                #store_index = int(log_id.split('_')[1]) - 1
                store_index = int(log_id[2])
                print('+++++')
                print(store_index)

                if 0 <= store_index < NUM_STORES and len(stores_data[store_index]) < 7:
                    stores_data[store_index].append(call_num)
            except (ValueError, IndexError):
                continue

        # 각 매장별로 UI 업데이트
        for i in range(NUM_STORES):
            # 데이터가 부족할 경우 공백으로 채우기
            #while len(stores_data[i]) < 7:
            while len(stores_data[i]) < 3:
                stores_data[i].append(" ")

            # 7개 라벨에 데이터 설정
            #for j in range(6):
            for j in range(3):
                self.store_labels[i][j].setText(stores_data[i][j])
            
            # 첫 번째 큰 숫자는 항상 빨간색
            self.store_labels[i][0].setStyleSheet("color: red; font-weight: bold;")
            self.store_labels[i][1].setStyleSheet("color: black; font-weight: bold;")
            self.store_labels[i][2].setStyleSheet("color: black; font-weight: bold;")

            # 7번째 라벨(alive 상태 표시) 업데이트
            #alive_label = self.store_labels[i][6]
            alive_label = self.store_labels[i][2]
            if is_alive_status[i]:
                #alive_label.setText(stores_data[i][6])
                alive_label.setText(stores_data[i][2])
                alive_label.setStyleSheet("color: black;")
            else:
                alive_label.setText("*")
                alive_label.setStyleSheet("color: red;")
    
    def resizeEvent(self, event):
        # 창 크기가 변경될 때 배경 이미지 크기도 조절
        self.background_label.setPixmap(self.background_pixmap.scaled(
            self.size(), 
            Qt.AspectRatioMode.KeepAspectRatioByExpanding, 
            Qt.TransformationMode.SmoothTransformation
        ))
        self.background_label.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    widget = MyWidget()
    widget.setCursor(QCursor(Qt.CursorShape.BlankCursor))
    widget.showFullScreen()
    sys.exit(app.exec())
