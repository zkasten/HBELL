import sys
import os
import datetime
from PyQt6.QtWidgets import (QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QTextEdit)
from PyQt6.QtCore import QTimer, pyqtSignal, QObject, Qt, QFile, QIODevice, QUrl, QTextStream, QByteArray
from PyQt6.QtGui import QFont, QCursor, QPixmap
#from PyQt6.QtMultimedia import QSoundEffect
import pygame
import time
import configparser
import psutil

# 2025-06-25 : Add number validation check, Add is_file_open() - Hyukjoo
# 2025-06-06 : Add configparser - Hyukjoo

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
NUM_LINES_TO_READ = 8
UPDATE_INTERVAL_MS = 1000
FONT_SIZE_LARGE = 180
FONT_SIZE_SMALL = 120
ALIVE_INTERVAL = 7 # seconds

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

    def play_sound(self):
#        sound = QSoundEffect(QApplication.instance())
#        sound.setSource(QUrl.fromLocalFile(RING_FILE))
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
                print(lineArr)
                if len(lineArr) < 3:
                    print("remove1")
                    lines.remove(i)
                    continue
                if not lineArr[0].isdigit():
                    print("remove2")
                    lines.remove(i)
                    continue
                if not lineArr[2].replace('\n','').isdigit():
                    print("remove3")
                    lines.remove(i)
                    continue
                if lineArr[1] == '-':
                    print("remove-")
                    delItems[lineArr[2]] = lineArr[0]
                    lines.remove(i)
                else:
                    if lineArr[2] in delItems and lineArr[0] == delItems[lineArr[2]]:
                        print("remove-else")
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
            print(i.split(',')[0]+ " :: " + STORE_NUMBER)

            if i.split(',')[0] == STORE_NUMBER:
                i += "\n"
                encoded_string = i.encode('utf-8')
                print("encoded_string:"+ str(encoded_string))
                log_b_arr.append(QByteArray(encoded_string))

        # print("LOG:"+ str(log_b_arr))
        # print("TXT:"+ str(text))
        # print("MEM:"+ str(self.curTxt))

        if text != log_b_arr:
            # print("-------------------DIFF btw LOG & CUR------")
            self.play_sound()

            text = log_b_arr
            self.curTxt = log_b_arr
            # print("text type:"+ str(type(text)))
            # print("log_b_arr type:"+ str(type(log_b_arr)))
            # print(str(log_b_arr))

            file = QFile(self.filename)
            if not file.open(QIODevice.OpenModeFlag.WriteOnly):
                return

#            for i in range(len(log_b_arr)):
#                if log_b_arr[i] == b'':
#                    print("---BLANK---!!!")
#                elif log_b_arr[i] == '':
#                    print("---NEWLINE---!!!")
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
        self.pixmap = QPixmap("backgroundS_err.png")
        self.label.setPixmap(self.pixmap)
        #self.showFullScreen()
        self.setGeometry(0, 0, 1920, 1080)
        self.label.resize(self.pixmap.width(), self.pixmap.height())

        self.layout = QVBoxLayout()
        self.layout_base = QHBoxLayout()
        self.layout_base.setContentsMargins(100, 0, 0, 0)
        self.layout1 = QVBoxLayout()
        self.layout2 = QVBoxLayout()

        self.filename = filename
        self.data_updater = DataUpdater(filename)

        self.label1 = QLabel("")
        self.label2 = QLabel("")
        self.label3 = QLabel("")
        self.label4 = QLabel("")
        self.label5 = QLabel("")
        self.label6 = QLabel("")
        self.label7 = QLabel("")
        self.label8 = QLabel("")

        self.label1.setFont(QFont('Arial', 120))
        self.label2.setFont(QFont('Arial', 120))
        self.label3.setFont(QFont('Arial', 120))
        self.label4.setFont(QFont('Arial', 120))
        self.label5.setFont(QFont('Arial', 120))
        self.label6.setFont(QFont('Arial', 210))
        self.label7.setFont(QFont('Arial', 210))
        self.label8.setFont(QFont('Arial', 210))

#        self.label3.setStyleSheet("background-color: red")
#        self.label3.setStyleSheet("color: darkred; border: 2px solid black; padding: 20px")
        #self.label6.setStyleSheet("color: orange; font-weight: bold")
        #self.label7.setStyleSheet("color: red; font-weight: bold")
        self.label1.setStyleSheet("font-weight: bold")
        self.label2.setStyleSheet("font-weight: bold")
        self.label3.setStyleSheet("font-weight: bold")
        self.label4.setStyleSheet("font-weight: bold")
        self.label5.setStyleSheet("font-weight: bold")
        self.label6.setStyleSheet("font-weight: bold")
        self.label7.setStyleSheet("font-weight: bold")
        self.label8.setStyleSheet("color: red; font-weight: bold")

        self.label1.move(100, 100)
        self.label2.move(100, 200)
        self.label3.move(100, 300)
        self.label4.move(100, 400)
        self.label5.move(100, 500)
        self.label6.move(100, 100)
        self.label7.move(100, 300)
        self.label8.move(100, 500)

        self.layout1.addWidget(self.label6, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout1.addWidget(self.label7, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout1.addWidget(self.label8, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.layout2.addWidget(self.label1, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout2.addWidget(self.label2, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout2.addWidget(self.label3, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout2.addWidget(self.label4, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.layout2.addWidget(self.label5, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.layout_base.addLayout(self.layout1)
        self.layout_base.addLayout(self.layout2)

        self.layout.addLayout(self.layout_base)
        self.setLayout(self.layout)

        self.data_updater.data_updated.connect(self.update_text)

    def getNumber(self, fullStr):
        print("fullStr:"+ fullStr)
#        if fullStr != '':
#            arr = fullStr.split(',')
#            return arr[1]
        return fullStr
    
    def update_text(self, new_text):
        arr = new_text.split('\n')
        while len(arr) < 9:
            arr.insert(0, "000,+, ")
        
        self.label1.setText(arr[len(arr)-9].split(',')[2])
        self.label2.setText(arr[len(arr)-8].split(',')[2])
        self.label3.setText(arr[len(arr)-7].split(',')[2])
        self.label4.setText(arr[len(arr)-6].split(',')[2])
        self.label5.setText(arr[len(arr)-5].split(',')[2])
        self.label6.setText(arr[len(arr)-4].split(',')[2])
        self.label7.setText(arr[len(arr)-3].split(',')[2])
        self.label8.setText(arr[len(arr)-2].split(',')[2])

#        self.label1.setText(self.getNumber(arr[len(arr)-1].split(',')[2]))
#        self.label2.setText(self.getNumber(arr[1].split(',')[2]))
#        self.label3.setText(self.getNumber(arr[2].split(',')[2]))
#        self.label4.setText(self.getNumber(arr[3].split(',')[2]))
#        self.label5.setText(self.getNumber(arr[4].split(',')[2]))
#        self.label6.setText(self.getNumber(arr[5].split(',')[2]))
#        self.label7.setText(self.getNumber(arr[6].split(',')[2]))
#        self.label8.setText(self.getNumber(arr[7].split(',')[2]))
#        self.setStyleSheet("background-color: grey;")

        if ISALIVE:
            self.pixmap = QPixmap("backgroundS.png")
        else:
            self.pixmap = QPixmap("backgroundS_err.png")
        self.label.setPixmap(self.pixmap)
        self.showFullScreen()

#        self.setGeometry(0, 0, 1920, 1080)
#        self.label.resize(self.pixmap.width(), self.pixmap.height())

if __name__ == '__main__':
    app = QApplication(sys.argv)

    widget = MyWidget("cur_num.csv")
    widget.setCursor(QCursor(Qt.CursorShape.BlankCursor))

    #widget.setStyleSheet("background-color: lightblue;")
    widget.showFullScreen()

#    widget.show()
    sys.exit(app.exec())

