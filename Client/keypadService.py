import sys
import time
import socket
import configparser
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QPushButton, QLabel, QSizePolicy
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QPixmap
import pygame

# HBELL KeypadService
# V1.3.0

# --- Constants ---

# Configuration
CONFIG_PATH = '/home/pi/HBELL-Sender/hbell.cfg'

# Window and Layout
WINDOW_TITLE = '1920x480 Number Pad Custom'
WINDOW_SIZE = (1920, 720)
MAIN_MARGINS = (8, 8, 8, 8)
MAIN_SPACING = 8
GRID_SPACING = 14

# Left Panel (History Display)
HISTORY_LABEL_STYLE = f"font-size:70px; min-width:120px; text-align: center;"
FIRST_HISTORY_LABEL_STYLE = f"{HISTORY_LABEL_STYLE} color:red;"
H_LOGO_PATH = "h_logo.png"
LOGO_LABEL_STYLE = "font-size:80px; min-width:120px; min-height:60px; color:red;"

# Right Panel (Input and Numpad)
INPUT_DISPLAY_STYLE = "font-size:44px; border:2px solid #bbb; min-height:56px; background:#f8f8f8;"
NUM_GRID_SPACING = 8
NUM_BTN_SIZE = (150, 150)
NUM_BTN_STYLE = "font-size:38px;"

# Special Buttons Panel
SPECIAL_BTN_SPACING = 12
SEND_BTN_SIZE = (150, 200)
RING_BTN_STYLE = "font-size:28px; background:#b0c4de;"
BKSP_BTN_STYLE = "font-size:38px; background:#ffd966;"
DEL_BTN_STYLE = "font-size:28px; background:#e06666; color:white;"
SEND_BTN_STYLE = "font-size:28px; background:#66cdaa;"

# Network and Logic
PRIMARY_SERVER = ('localhost', 6000)   # bellSender (nRF24)
FALLBACK_SERVER = ('localhost', 7000)  # wifi_M_Sender
SOCKET_TIMEOUT = 2.0
CMD_ADD = ',+'
CMD_DELETE = ',-'
RING_CMD = '99999,-'
MAX_INPUT_LEN = 4
MAX_HISTORY_LEN = 20
RING_FILE = "/home/pi/ring.wav"


def load_config():
    """Load configuration from hbell.cfg"""
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    
    enable_sound = config.getboolean('KEYPAD', 'ENABLE_SOUND', fallback=True)
    sig_prefer = config.get('KEYPAD', 'SIG_PREFER', fallback='RF24')

    return enable_sound, sig_prefer


class NetworkWorker(QThread):
    """Worker thread for network operations."""
    finished = pyqtSignal(str)
    
    def __init__(self, message, sig_prefer):
        super().__init__()
        self.message = message
        self.sig_prefer = sig_prefer
    
    def run(self):
        servers = [FALLBACK_SERVER, PRIMARY_SERVER] if self.sig_prefer == 'WIFI' else [PRIMARY_SERVER, FALLBACK_SERVER]
        
        for server in servers:
            print("--------------------------------")
            print(f"TRYING: {server}")
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(SOCKET_TIMEOUT)
                    s.connect(server)
                    s.sendall(self.message.encode())
                    response = s.recv(1024).decode()
                    print(f"RESPONSE: {response}")
                    if response == 'ok':
                        self.finished.emit('ok')
                        return
            except socket.error as e:
                print(f"Failed on {server}: {e}")
                continue
        
        self.finished.emit('fail')


class KeyPadWidget(QWidget):
    """A custom keypad widget for a specific display and function."""
    def __init__(self):
        super().__init__()
        self.entered_numbers = []
        self.input_buffer = []
        self.history_buttons = []
        self._init_ui()
        self._refresh_ui()
        
        enable_sound, self.sig_prefer = load_config()
        if enable_sound:
            pygame.mixer.init()
            self.sound = pygame.mixer.Sound(RING_FILE)
        else:
            self.sound = None

    def play_sound(self):
        if self.sound:
            self.sound.play()
        
    def _init_ui(self):
        """Initializes the main user interface, layout, and widgets."""
        self.setWindowTitle(WINDOW_TITLE)
        self.setFixedSize(*WINDOW_SIZE)

        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(*MAIN_MARGINS)
        main_layout.setSpacing(MAIN_SPACING)

        left_panel = self._create_left_panel()
        right_panel = self._create_right_panel()
        special_buttons_panel = self._create_special_buttons_panel()

        main_layout.addLayout(left_panel, 2)
        main_layout.addLayout(right_panel, 1)
        main_layout.addLayout(special_buttons_panel)

    def _create_left_panel(self):
        """Creates the left panel with the 3x3 grid for history display."""
        panel_layout = QVBoxLayout()
        grid_layout = QGridLayout()
        grid_layout.setSpacing(GRID_SPACING)

        # Create 8 clickable history buttons and 1 logo placeholder
        for i in range(9):
            row, col = divmod(i, 3)
            # The last cell (bottom-right) is for the H Mart logo
            if i == 8:
                widget = QLabel('H Mart')
                pixmap = QPixmap(H_LOGO_PATH)
                widget.setPixmap(pixmap)
                widget.setStyleSheet(LOGO_LABEL_STYLE)
                widget.setAlignment(Qt.AlignmentFlag.AlignCenter) # Keep for QLabel
            else:
                # History entries are buttons styled to look like labels
                button = QPushButton('')
                # Removed button.setFlat(True)
                button.setStyleSheet(FIRST_HISTORY_LABEL_STYLE if i == 0 else HISTORY_LABEL_STYLE)
                button.clicked.connect(lambda checked, index=i: self._on_history_clicked(index))
                button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                self.history_buttons.append(button)
                widget = button

            grid_layout.addWidget(widget, row, col)

        # Set stretch factors for the rows to make them expand vertically
        grid_layout.setRowStretch(0, 1)
        grid_layout.setRowStretch(1, 1)
        grid_layout.setRowStretch(2, 1)

        panel_layout.addLayout(grid_layout)
        return panel_layout

    def _create_right_panel(self):
        """Creates the right panel with the input display and number buttons."""
        panel_layout = QVBoxLayout()
        panel_layout.setSpacing(MAIN_SPACING)

        # Input display
        self.input_display = QLabel('')
        self.input_display.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.input_display.setStyleSheet(INPUT_DISPLAY_STYLE)
        panel_layout.addWidget(self.input_display)

        # Number pad grid
        num_grid = QGridLayout()
        num_grid.setSpacing(NUM_GRID_SPACING)
        button_positions = [
            ('7', 0, 0), ('8', 0, 1), ('9', 0, 2),
            ('4', 1, 0), ('5', 1, 1), ('6', 1, 2),
            ('1', 2, 0), ('2', 2, 1), ('3', 2, 2),
            ('0', 3, 1),
        ]
        for text, row, col in button_positions:
            btn = QPushButton(text)
            btn.setFixedSize(*NUM_BTN_SIZE)
            btn.setStyleSheet(NUM_BTN_STYLE)
            btn.clicked.connect(lambda _, x=text: self._press_key(x))
            num_grid.addWidget(btn, row, col)
        
        panel_layout.addLayout(num_grid)
        return panel_layout

    def _create_special_buttons_panel(self):
        """Creates the vertical panel with special action buttons."""
        panel_layout = QVBoxLayout()
        panel_layout.setSpacing(SPECIAL_BTN_SPACING)

        buttons = [
            ('Ring', RING_BTN_STYLE, self._ring, NUM_BTN_SIZE),
            ('<', BKSP_BTN_STYLE, self._backspace, NUM_BTN_SIZE),
            ('DEL', DEL_BTN_STYLE, self._delete_entry, NUM_BTN_SIZE),
            ('SEND', SEND_BTN_STYLE, self._send_entry, SEND_BTN_SIZE),
        ]

        for text, style, callback, size in buttons:
            btn = QPushButton(text)
            btn.setFixedSize(*size)
            btn.setStyleSheet(style)
            btn.clicked.connect(callback)
            panel_layout.addWidget(btn)

        return panel_layout

    def _send_msg(self, message, callback):
        """Sends a message asynchronously with failover support."""
        worker = NetworkWorker(message, self.sig_prefer)
        worker.finished.connect(callback)
        worker.start()
        self._workers = getattr(self, '_workers', [])
        self._workers.append(worker)
    
    def _show_error(self):
        """Visual feedback for transmission failure."""
        original_style = self.input_display.styleSheet()
        self.input_display.setStyleSheet(INPUT_DISPLAY_STYLE + "background:#ffcccc;")
        QApplication.processEvents()
        time.sleep(0.3)
        self.input_display.setStyleSheet(original_style)

    def _execute_command(self, command_suffix):
        """Executes a command based on the current input buffer."""
        if not self.input_buffer:
            return

        number = ''.join(self.input_buffer)
        message = number + command_suffix
        
        def on_result(result):
            if result == 'ok':
                self.play_sound()
                if command_suffix == CMD_ADD:
                    self._move_or_insert_history(number)
                elif command_suffix == CMD_DELETE:
                    if number in self.entered_numbers:
                        self.entered_numbers.remove(number)
                self._refresh_ui()
            else:
                self._show_error()
        
        self.input_buffer.clear()
        self._refresh_ui()
        self._send_msg(message, on_result)

    def _move_or_insert_history(self, number):
        """Moves a number to the top of the history or inserts it."""
        if number in self.entered_numbers:
            self.entered_numbers.remove(number)
        self.entered_numbers.insert(0, number)
        
        if len(self.entered_numbers) > MAX_HISTORY_LEN:
            self.entered_numbers = self.entered_numbers[:MAX_HISTORY_LEN]

    def _refresh_ui(self):
        """Refreshes the entire UI display."""
        self._refresh_input_display()
        self._refresh_history_buttons()

    def _refresh_input_display(self):
        """Updates the input display label."""
        self.input_display.setText(''.join(self.input_buffer))

    def _refresh_history_buttons(self):
        """Updates the history buttons with entered numbers."""
        for i, button in enumerate(self.history_buttons):
            text = self.entered_numbers[i] if i < len(self.entered_numbers) else ''
            button.setText(text)

    # --- Slots for Button Clicks ---

    def _on_history_clicked(self, index):
        """Handles a click on a history entry."""
        if index < len(self.entered_numbers):
            selected_number = self.entered_numbers[index]
            self.input_buffer = list(selected_number)
            self._refresh_input_display()

    def _press_key(self, value):
        """Handles a number key press."""
        if len(self.input_buffer) < MAX_INPUT_LEN:
            self.input_buffer.append(value)
            self._refresh_input_display()

    def _backspace(self):
        """Handles the backspace button press."""
        if self.input_buffer:
            self.input_buffer.pop()
            self._refresh_input_display()

    def _send_entry(self):
        """Handles the SEND button press."""
        self._execute_command(CMD_ADD)

    def _delete_entry(self):
        """Handles the DEL button press."""
        self._execute_command(CMD_DELETE)

    def _ring(self):
        """Handles the Ring button press."""
        def on_result(result):
            if result == 'ok':
                self.play_sound()
        
        self._send_msg(RING_CMD, on_result)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = KeyPadWidget()
    win.setCursor(Qt.CursorShape.BlankCursor)
    win.showFullScreen()
    sys.exit(app.exec())