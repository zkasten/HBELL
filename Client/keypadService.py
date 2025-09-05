import sys
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel
from PyQt6.QtCore import Qt
import socket

class KeyPadWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('1920x480 Number Pad Custom')
        self.setFixedSize(1920, 480)
        self.entered_numbers = []
        self.input_buffer = []

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(8)

        left_panel = QVBoxLayout()
        self.grid = QGridLayout()
        self.grid.setSpacing(14)
        self.num_labels = []
        for row in range(2):
            for col in range(4):
                label = QLabel('')
                label.setStyleSheet("font-size:44px; border:2px solid #999; min-width:120px; min-height:60px; background:#fafaff;")
                label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.num_labels.append(label)
                self.grid.addWidget(label, row, col)
        left_panel.addLayout(self.grid)
        main_layout.addLayout(left_panel, 2)

        right_panel = QVBoxLayout()
        right_panel.setSpacing(8)
        self.input_display = QLabel('')
        self.input_display.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.input_display.setStyleSheet("font-size:44px; border:2px solid #bbb; min-height:56px; background:#f8f8f8;")
        right_panel.addWidget(self.input_display)

        num_grid = QGridLayout()
        num_grid.setSpacing(8)
        btn_size = (100, 100)
        sendBtn_size = (100, 135)
        
        button_positions = [
            ('7', 0, 0), ('8', 0, 1), ('9', 0, 2),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2),
            ('1', 2, 0), ('2', 2, 1), ('3', 2, 2),
            ('0', 3, 1), # 0 중앙정렬
        ]
        for text, row, col in button_positions:
            btn = QPushButton(text)
            btn.setFixedSize(*btn_size)
            btn.setStyleSheet("font-size:38px;")
            btn.clicked.connect(lambda _, x=text: self.press_key(x))
            num_grid.addWidget(btn, row, col)
        right_panel.addLayout(num_grid)
        
        # 특수버튼: 세로 박스에 배치
        special_buttons_layout = QVBoxLayout()
        special_buttons_layout.setSpacing(12)
        
        btn_ring = QPushButton('Ring')
        btn_ring.setFixedSize(*btn_size)
        btn_ring.setStyleSheet("font-size:28px; background:#b0c4de;")
        btn_ring.clicked.connect(lambda: self.press_key('c'))
        special_buttons_layout.addWidget(btn_ring)
        
        btn_bksp = QPushButton('<')
        btn_bksp.setFixedSize(*btn_size)
        btn_bksp.setStyleSheet("font-size:38px; background:#ffd966;")
        btn_bksp.clicked.connect(self.backspace)
        special_buttons_layout.addWidget(btn_bksp)
        
        btn_del = QPushButton('DEL')
        btn_del.setFixedSize(*btn_size)
        btn_del.setStyleSheet("font-size:28px; background:#e06666; color:white;")
        btn_del.clicked.connect(self.delete_with_a)
        special_buttons_layout.addWidget(btn_del)
        
        btn_send = QPushButton('SEND')
        btn_send.setFixedSize(*sendBtn_size)
        btn_send.setStyleSheet("font-size:28px; background:#66cdaa;")
        btn_send.clicked.connect(self.enter_number)
        special_buttons_layout.addWidget(btn_send)

        # right_panel에 특수버튼 세로 레이아웃 추가
        #right_panel.addLayout(special_buttons_layout)
        main_layout.addLayout(right_panel, 1)
        main_layout.addLayout(special_buttons_layout)

        # for i, num in enumerate(['7', '8', '9']):
        #     btn = QPushButton(num)
        #     btn.setFixedSize(*btn_size)
        #     btn.setStyleSheet("font-size:38px;")
        #     btn.clicked.connect(lambda _, x=num: self.press_key(x))
        #     grid.addWidget(btn, 0, i)
        # for i, num in enumerate(['4', '5', '6']):
        #     btn = QPushButton(num)
        #     btn.setFixedSize(*btn_size)
        #     btn.setStyleSheet("font-size:38px;")
        #     btn.clicked.connect(lambda _, x=num: self.press_key(x))
        #     grid.addWidget(btn, 1, i)
        # for i, num in enumerate(['1', '2', '3']):
        #     btn = QPushButton(num)
        #     btn.setFixedSize(*btn_size)
        #     btn.setStyleSheet("font-size:38px;")
        #     btn.clicked.connect(lambda _, x=num: self.press_key(x))
        #     grid.addWidget(btn, 2, i)

        # # 4번째줄: ring, 0, <
        # btn_ring = QPushButton('ring')
        # btn_ring.setFixedSize(*btn_size)
        # btn_ring.setStyleSheet("font-size:28px; background:#e06666; color:white;")
        # btn_ring.clicked.connect(lambda: self.press_key('c'))
        # grid.addWidget(btn_ring, 3, 0)

        # btn_zero = QPushButton('0')
        # btn_zero.setFixedSize(*btn_size)
        # btn_zero.setStyleSheet("font-size:38px;")
        # btn_zero.clicked.connect(lambda: self.press_key('0'))
        # grid.addWidget(btn_zero, 3, 1)

        # btn_bksp = QPushButton('<')
        # btn_bksp.setFixedSize(*btn_size)
        # btn_bksp.setStyleSheet("font-size:38px; background:#ffd966;")
        # btn_bksp.clicked.connect(self.backspace)
        # grid.addWidget(btn_bksp, 3, 2)

        # # 하단: SEND(2칸, 188px), DEL(1칸, 90px)
        # btn_send = QPushButton('SEND')
        # btn_send.setFixedSize(188, 80)
        # btn_send.setStyleSheet("font-size:38px; background:#66cdaa;")
        # btn_send.clicked.connect(self.enter_number)
        # grid.addWidget(btn_send, 4, 0, 1, 2)

        # btn_del = QPushButton('DEL')
        # btn_del.setFixedSize(90, 80)
        # btn_del.setStyleSheet("font-size:38px; background:#b0c4de;")
        # btn_del.clicked.connect(self.delete_with_a)
        # grid.addWidget(btn_del, 4, 2)

        # right_panel.addLayout(grid)
        #main_layout.addLayout(right_panel, 1)

        self.refresh_input_display()
        self.refresh_num_labels()

    def press_key(self, value):
        if len(self.input_buffer) < 4:
            self.input_buffer.append(value)
            self.refresh_input_display()
    def backspace(self):
        if self.input_buffer:
            self.input_buffer.pop()
            self.refresh_input_display()
    def enter_number(self):
        if self.input_buffer:
            number = ''.join(self.input_buffer)

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('localhost', 6000))
                s.sendall(str(number).encode())
            self.entered_numbers.insert(0, number)
            if len(self.entered_numbers) > 8:
                self.entered_numbers = self.entered_numbers[:8]
            self.input_buffer.clear()
            self.refresh_input_display()
            self.refresh_num_labels()
    def delete_with_a(self):
        if self.input_buffer:
            number = ''.join(self.input_buffer) + 'a'
            self.entered_numbers.insert(0, number)
            if len(self.entered_numbers) > 8:
                self.entered_numbers = self.entered_numbers[:8]
            self.input_buffer.clear()
            self.refresh_input_display()
            self.refresh_num_labels()
    def refresh_num_labels(self):
        for i in range(8):
            self.num_labels[i].setText(self.entered_numbers[i] if i < len(self.entered_numbers) else '')
    def refresh_input_display(self):
        self.input_display.setText(''.join(self.input_buffer))

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = KeyPadWidget()
    #win.show()
    win.showFullScreen()
    sys.exit(app.exec())

