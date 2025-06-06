import sys
import os
import datetime
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QTextEdit)
from PyQt6.QtCore import QTimer, pyqtSignal, QObject, Qt, QFile, QIODevice, QUrl, QTextStream, QByteArray
from PyQt6.QtGui import QFont, QCursor, QPixmap
#from PyQt6.QtMultimedia import QSoundEffect
import pygame
import time
import psutil

# 2025-05-27 : add is_file_open - Hyukjoo

FILE_ALIVE1 = "/home/pi/log/alive1.txt"
FILE_ALIVE2 = "/home/pi/log/alive2.txt"
FILE_ALIVE3 = "/home/pi/log/alive3.txt"
FILE_ALIVE4 = "/home/pi/log/alive4.txt"
ISALIVE1 = False
ISALIVE2 = False
ISALIVE3 = False
ISALIVE4 = False
LOG_FILE_DIR = "/home/pi/log/"
RING_FILE = "ring.wav"
NUM_LINES_TO_READ = 8
UPDATE_INTERVAL_MS = 1000
FONT_SIZE_LARGE = 100
FONT_SIZE_SMALL = 70
ALIVE_INTERVAL = 5 # seconds

class DataUpdater(QTextEdit):
    data_updated = pyqtSignal(str)

    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        self.curTxt = ""
        self.counter = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(UPDATE_INTERVAL_MS)

        pygame.mixer.init()
        self.sound = pygame.mixer.Sound(RING_FILE)

    def is_file_open(self, file_path):
        for proc in psutil.process_iter(['pid', 'open_files']):
            try:
                for file in proc.info['open_files'] or []:
                    if file.path == file_path:
                        return True
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
        return False

    def play_sound(self):
#        sound = QSoundEffect(QApplication.instance())
#        sound.setSource(QUrl.fromLocalFile(RING_FILE))
        self.sound.play()

    def create_empty_file_if_not_exists(self):
        log_file = LOG_FILE_DIR + str(datetime.date.today()) + ".log"

        if not os.path.exists(log_file):
            try:
                with open(log_file, 'w'):
                    pass  # touch log file
            except Exception as e:
                print(f"Error: File '{log_file}' not created.")
        return

    def clean_log_file(self):
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

                if lineArr[1] == '-':
                    delItems[lineArr[2]] = lineArr[0]
                    lines.remove(i)
                else:
                    if lineArr[2] in delItems and lineArr[0] == delItems[lineArr[2]]:
                        lines.remove(i)
            num_file.writelines(lines)

    def read_last_lines(self, num_lines=NUM_LINES_TO_READ):
        log_file = LOG_FILE_DIR + str(datetime.date.today()) + ".log"
        file = QFile(log_file)
        lines = []
        stream = QTextStream(file)
        #if file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
        if not file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
            return None
        while not stream.atEnd():
            lines.append(stream.readLine())
        file.close()

        #return lines[-8:]
        return lines

    def update_data(self):
        self.create_empty_file_if_not_exists()
        self.clean_log_file()

        if os.path.exists(FILE_ALIVE1) and os.path.exists(FILE_ALIVE2) and os.path.exists(FILE_ALIVE3) and os.path.exists(FILE_ALIVE4):
            ############# ALIVE CHECK #############
            global ISALIVE1, ISALIVE2, ISALIVE3, ISALIVE4
            cur_time = int(time.time())
            file_time1 = os.path.getmtime(FILE_ALIVE1)
            file_time2 = os.path.getmtime(FILE_ALIVE2)
            file_time3 = os.path.getmtime(FILE_ALIVE3)
            file_time4 = os.path.getmtime(FILE_ALIVE4)

            if cur_time - file_time1 > ALIVE_INTERVAL:
                ISALIVE1 = False
            else:
                ISALIVE1 = True
            if cur_time - file_time2 > ALIVE_INTERVAL:
                ISALIVE2 = False
            else:
                ISALIVE2 = True
            if cur_time - file_time3 > ALIVE_INTERVAL:
                ISALIVE3 = False
            else:
                ISALIVE3 = True
            if cur_time - file_time4 > ALIVE_INTERVAL:
                ISALIVE4 = False
            else:
                ISALIVE4 = True

        file = QFile(self.filename)
        if file.open(QIODevice.OpenModeFlag.ReadOnly | QIODevice.OpenModeFlag.Text):
            text = file.readAll()
        else:
            self.setPlainText("Failed to open file.")
        file.close()

        log = self.read_last_lines()
        log_b_arr = QByteArray()
        for i in log:
            i += "\n"
            encoded_string = i.encode('utf-8')
            log_b_arr.append(QByteArray(encoded_string))

        if text != log_b_arr:
            # print("-------------------DIFF btw LOG & CUR------")
            self.play_sound()

            text = log_b_arr
            self.curTxt = log_b_arr

            file = QFile(self.filename)
            if not file.open(QIODevice.OpenModeFlag.WriteOnly):
                return

            dataStream = QTextStream(file)
            dataStream << log_b_arr
            file.close()
        # else:
            # print("-------------------SAME btw cur & log------")

        self.setPlainText(str(text, 'utf-8'))
        self.data_updated.emit(str(text, 'utf-8'))

class MyWidget(QWidget):
    def __init__(self, filename):
        super().__init__()

        self.label = QLabel(self)
        self.pixmap = QPixmap("background.png")
        self.label.setPixmap(self.pixmap)
        #self.showFullScreen()
        self.setGeometry(0, 0, 1920, 1080)
        self.label.resize(self.pixmap.width(), self.pixmap.height())

        self.filename = filename
        self.data_updater = DataUpdater(filename)

        self.layout_base = QHBoxLayout()
        self.layout_store_names = QVBoxLayout()
        self.layout_numbers_b = QVBoxLayout()
        self.layout_numbers_s = QVBoxLayout()

        self.layout_numline1_1 = QHBoxLayout()
        self.layout_numline1_1.setSpacing(50)
        self.layout_numline1_2 = QVBoxLayout()
        self.layout_numline1_2_1 = QHBoxLayout()
        self.layout_numline1_2_2 = QHBoxLayout()

        self.layout_numline2_1 = QHBoxLayout()
        self.layout_numline2_1.setSpacing(50)
        self.layout_numline2_2 = QVBoxLayout()
        self.layout_numline2_2_1 = QHBoxLayout()
        self.layout_numline2_2_2 = QHBoxLayout()

        self.layout_numline3_1 = QHBoxLayout()
        self.layout_numline3_1.setSpacing(50)
        self.layout_numline3_2 = QVBoxLayout()
        self.layout_numline3_2_1 = QHBoxLayout()
        self.layout_numline3_2_2 = QHBoxLayout()

        self.layout_numline4_1 = QHBoxLayout()
        self.layout_numline4_1.setSpacing(50)
        self.layout_numline4_2 = QVBoxLayout()
        self.layout_numline4_2_1 = QHBoxLayout()
        self.layout_numline4_2_2 = QHBoxLayout()

        pixmap1 = QPixmap("store1.png")
        pixmap2 = QPixmap("store2.png")
        pixmap3 = QPixmap("store3.png")
        pixmap4 = QPixmap("store4.png")
        self.store_name1 = QLabel()
        self.store_name1.setPixmap(pixmap1)
        self.store_name2 = QLabel()
        self.store_name2.setPixmap(pixmap2)
        self.store_name3 = QLabel()
        self.store_name3.setPixmap(pixmap3)
        self.store_name4 = QLabel()
        self.store_name4.setPixmap(pixmap4)

        self.layout_store_names.addWidget(self.store_name1)
        self.layout_store_names.addWidget(self.store_name2)
        self.layout_store_names.addWidget(self.store_name3)
        self.layout_store_names.addWidget(self.store_name4)
        self.layout_base.addLayout(self.layout_store_names)

        self.numLabel1_1 = QLabel("101")
        self.numLabel1_2 = QLabel("102")
        self.numLabel1_3 = QLabel("103")
        self.numLabel1_4 = QLabel("104")
        self.numLabel1_5 = QLabel("105")
        self.numLabel1_6 = QLabel("106")
        self.numLabel1_7 = QLabel("*")

        self.numLabel2_1 = QLabel("11")
        self.numLabel2_2 = QLabel("12")
        self.numLabel2_3 = QLabel("13")
        self.numLabel2_4 = QLabel("14")
        self.numLabel2_5 = QLabel("15")
        self.numLabel2_6 = QLabel("16")
        self.numLabel2_7 = QLabel("*")

        self.numLabel3_1 = QLabel("21")
        self.numLabel3_2 = QLabel("22")
        self.numLabel3_3 = QLabel("23")
        self.numLabel3_4 = QLabel("24")
        self.numLabel3_5 = QLabel("25")
        self.numLabel3_6 = QLabel("26")
        self.numLabel3_7 = QLabel("*")

        self.numLabel4_1 = QLabel("1")
        self.numLabel4_2 = QLabel("2")
        self.numLabel4_3 = QLabel("3")
        self.numLabel4_4 = QLabel("4")
        self.numLabel4_5 = QLabel("5")
        self.numLabel4_6 = QLabel("6")
        self.numLabel4_7 = QLabel("*")

        self.numLabel1_1.setFont(QFont('Arial', FONT_SIZE_LARGE))
        self.numLabel1_2.setFont(QFont('Arial', FONT_SIZE_LARGE))
        self.numLabel1_3.setFont(QFont('Arial', FONT_SIZE_LARGE))
        self.numLabel1_4.setFont(QFont('Arial', FONT_SIZE_SMALL))
        self.numLabel1_5.setFont(QFont('Arial', FONT_SIZE_SMALL))
        self.numLabel1_6.setFont(QFont('Arial', FONT_SIZE_SMALL))
        self.numLabel1_7.setFont(QFont('Arial', FONT_SIZE_SMALL))

        self.numLabel2_1.setFont(QFont('Arial', FONT_SIZE_LARGE))
        self.numLabel2_2.setFont(QFont('Arial', FONT_SIZE_LARGE))
        self.numLabel2_3.setFont(QFont('Arial', FONT_SIZE_LARGE))
        self.numLabel2_4.setFont(QFont('Arial', FONT_SIZE_SMALL))
        self.numLabel2_5.setFont(QFont('Arial', FONT_SIZE_SMALL))
        self.numLabel2_6.setFont(QFont('Arial', FONT_SIZE_SMALL))
        self.numLabel2_7.setFont(QFont('Arial', FONT_SIZE_SMALL))

        self.numLabel3_1.setFont(QFont('Arial', FONT_SIZE_LARGE))
        self.numLabel3_2.setFont(QFont('Arial', FONT_SIZE_LARGE))
        self.numLabel3_3.setFont(QFont('Arial', FONT_SIZE_LARGE))
        self.numLabel3_4.setFont(QFont('Arial', FONT_SIZE_SMALL))
        self.numLabel3_5.setFont(QFont('Arial', FONT_SIZE_SMALL))
        self.numLabel3_6.setFont(QFont('Arial', FONT_SIZE_SMALL))
        self.numLabel3_7.setFont(QFont('Arial', FONT_SIZE_SMALL))

        self.numLabel4_1.setFont(QFont('Arial', FONT_SIZE_LARGE))
        self.numLabel4_2.setFont(QFont('Arial', FONT_SIZE_LARGE))
        self.numLabel4_3.setFont(QFont('Arial', FONT_SIZE_LARGE))
        self.numLabel4_4.setFont(QFont('Arial', FONT_SIZE_SMALL))
        self.numLabel4_5.setFont(QFont('Arial', FONT_SIZE_SMALL))
        self.numLabel4_6.setFont(QFont('Arial', FONT_SIZE_SMALL))
        self.numLabel4_7.setFont(QFont('Arial', FONT_SIZE_SMALL))

        self.numLabel1_1.setStyleSheet("color: red; font-weight: bold")
        self.numLabel1_2.setStyleSheet("font-weight: bold")
        self.numLabel1_3.setStyleSheet("font-weight: bold")
        self.numLabel1_7.setStyleSheet("color: red")
        self.numLabel2_1.setStyleSheet("color: red; font-weight: bold")
        self.numLabel2_2.setStyleSheet("font-weight: bold")
        self.numLabel2_3.setStyleSheet("font-weight: bold")
        self.numLabel2_7.setStyleSheet("color: red")
        self.numLabel3_1.setStyleSheet("color: red; font-weight: bold")
        self.numLabel3_2.setStyleSheet("font-weight: bold")
        self.numLabel3_3.setStyleSheet("font-weight: bold")
        self.numLabel3_7.setStyleSheet("color: red")
        self.numLabel4_1.setStyleSheet("color: red; font-weight: bold")
        self.numLabel4_2.setStyleSheet("font-weight: bold")
        self.numLabel4_3.setStyleSheet("font-weight: bold")
        self.numLabel4_7.setStyleSheet("color: red")

        self.layout_numline1_2_1.addWidget(self.numLabel1_4, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline1_2_1.addWidget(self.numLabel1_5, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline1_2_2.addWidget(self.numLabel1_6, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline1_2_2.addWidget(self.numLabel1_7, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.layout_numline2_2_1.addWidget(self.numLabel2_4, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline2_2_1.addWidget(self.numLabel2_5, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline2_2_2.addWidget(self.numLabel2_6, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline2_2_2.addWidget(self.numLabel2_7, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.layout_numline3_2_1.addWidget(self.numLabel3_4, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline3_2_1.addWidget(self.numLabel3_5, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline3_2_2.addWidget(self.numLabel3_6, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline3_2_2.addWidget(self.numLabel3_7, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.layout_numline4_2_1.addWidget(self.numLabel4_4, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline4_2_1.addWidget(self.numLabel4_5, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline4_2_2.addWidget(self.numLabel4_6, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline4_2_2.addWidget(self.numLabel4_7, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.layout_numline1_2.addLayout(self.layout_numline1_2_1)
        self.layout_numline1_2.addLayout(self.layout_numline1_2_2)

        self.layout_numline2_2.addLayout(self.layout_numline2_2_1)
        self.layout_numline2_2.addLayout(self.layout_numline2_2_2)

        self.layout_numline3_2.addLayout(self.layout_numline3_2_1)
        self.layout_numline3_2.addLayout(self.layout_numline3_2_2)

        self.layout_numline4_2.addLayout(self.layout_numline4_2_1)
        self.layout_numline4_2.addLayout(self.layout_numline4_2_2)

        self.layout_numline1_1.addWidget(self.numLabel1_1, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline1_1.addWidget(self.numLabel1_2, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline1_1.addWidget(self.numLabel1_3, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.layout_numline2_1.addWidget(self.numLabel2_1, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline2_1.addWidget(self.numLabel2_2, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline2_1.addWidget(self.numLabel2_3, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.layout_numline3_1.addWidget(self.numLabel3_1, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline3_1.addWidget(self.numLabel3_2, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline3_1.addWidget(self.numLabel3_3, alignment=Qt.AlignmentFlag.AlignHCenter)
        
        self.layout_numline4_1.addWidget(self.numLabel4_1, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline4_1.addWidget(self.numLabel4_2, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout_numline4_1.addWidget(self.numLabel4_3, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.layout_numbers_b.addLayout(self.layout_numline1_1)
        self.layout_numbers_b.addLayout(self.layout_numline2_1)
        self.layout_numbers_b.addLayout(self.layout_numline3_1)
        self.layout_numbers_b.addLayout(self.layout_numline4_1)

        self.layout_numbers_s.addLayout(self.layout_numline1_2)
        self.layout_numbers_s.addLayout(self.layout_numline2_2)
        self.layout_numbers_s.addLayout(self.layout_numline3_2)
        self.layout_numbers_s.addLayout(self.layout_numline4_2)

        self.layout_base.addLayout(self.layout_numbers_b)
        self.layout_base.addLayout(self.layout_numbers_s)

        self.setLayout(self.layout_base)

        self.data_updater.data_updated.connect(self.update_text)

    def getNumber(self, fullStr):
        print("fullStr:"+ fullStr)
#        if fullStr != '':
#            arr = fullStr.split(',')
#            return arr[1]
        return fullStr
    
    def update_text(self, new_text):
        arr = new_text.split('\n')
        store1 = []
        store2 = []
        store3 = []
        store4 = []
        for i in reversed(arr):
            if i.split(',')[0] == '001' and len(store1) < 8:
                store1.append(i.split(',')[2])
            elif i.split(',')[0] == '002' and len(store2) < 8:
                store2.append(i.split(',')[2])
            elif i.split(',')[0] == '003' and len(store3) < 8:
                store3.append(i.split(',')[2])
            elif i.split(',')[0] == '004' and len(store4) < 8:
                store4.append(i.split(',')[2])

        while len(store1) < 8:
            store1.append(" ")
        while len(store2) < 8:
            store2.append(" ")
        while len(store3) < 8:
            store3.append(" ")
        while len(store4) < 8:
            store4.append(" ")

        # self.showFullScreen()

        self.numLabel1_1.setText(store1[0])
        self.numLabel1_2.setText(store1[1])
        self.numLabel1_3.setText(store1[2])
        self.numLabel1_4.setText(store1[3])
        self.numLabel1_5.setText(store1[4])
        self.numLabel1_6.setText(store1[5])

        if ISALIVE1:
            self.numLabel1_7.setText(store1[6])
            self.numLabel1_7.setStyleSheet("color: black")
        else:
            self.numLabel1_7.setText("*")
            self.numLabel1_7.setStyleSheet("color: red")

        self.numLabel2_1.setText(store2[0])
        self.numLabel2_2.setText(store2[1])
        self.numLabel2_3.setText(store2[2])
        self.numLabel2_4.setText(store2[3])
        self.numLabel2_5.setText(store2[4])
        self.numLabel2_6.setText(store2[5])

        if ISALIVE2:
            self.numLabel2_7.setText(store2[6])
            self.numLabel2_7.setStyleSheet("color: black")
        else:
            self.numLabel2_7.setText("*")
            self.numLabel2_7.setStyleSheet("color: red")

        self.numLabel3_1.setText(store3[0])
        self.numLabel3_2.setText(store3[1])
        self.numLabel3_3.setText(store3[2])
        self.numLabel3_4.setText(store3[3])
        self.numLabel3_5.setText(store3[4])
        self.numLabel3_6.setText(store3[5])
        if ISALIVE3:
            self.numLabel3_7.setText(store3[6])
            self.numLabel3_7.setStyleSheet("color: black")
        else:
            self.numLabel3_7.setText("*")
            self.numLabel3_7.setStyleSheet("color: red")

        self.numLabel4_1.setText(store4[0])
        self.numLabel4_2.setText(store4[1])
        self.numLabel4_3.setText(store4[2])
        self.numLabel4_4.setText(store4[3])
        self.numLabel4_5.setText(store4[4])
        self.numLabel4_6.setText(store4[5])
        if ISALIVE4:
            self.numLabel4_7.setText(store4[6])
            self.numLabel4_7.setStyleSheet("color: black")
        else:
            self.numLabel4_7.setText("*")
            self.numLabel4_7.setStyleSheet("color: red")

        self.showFullScreen()
        self.setGeometry(0, 0, 1920, 1080)
        self.label.resize(self.pixmap.width(), self.pixmap.height())

if __name__ == '__main__':
    app = QApplication(sys.argv)

    widget = MyWidget("cur_num.csv")
    widget.setCursor(QCursor(Qt.CursorShape.BlankCursor))
    # widget.setStyleSheet("background-color: red;")

    widget.showFullScreen()

#    widget.show()
    sys.exit(app.exec())

