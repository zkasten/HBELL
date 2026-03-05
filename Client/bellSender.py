import configparser
import datetime
import os
import socket
import spidev
import sys
import threading
import time
from pyrf24 import RF24, RF24_PA_HIGH, RF24_250KBPS
#from RF24 import RF24, RF24_PA_HIGH, RF24_250KBPS

# HBELL nRF24 bellSender
# V1.3.0

LOG_DIR = '/home/pi/log'


class DailyLogWriter:
    """Redirects writes to a daily rotating log file."""
    def __init__(self, log_dir):
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)
        self._file = None
        self._current_date = None

    def _get_file(self):
        today = datetime.date.today().isoformat()
        if today != self._current_date:
            if self._file:
                self._file.close()
            self._current_date = today
            path = os.path.join(self.log_dir, f"{today}-nrf24.log")
            self._file = open(path, 'a')
        return self._file

    def write(self, msg):
        if msg.strip():
            ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self._get_file().write(f"[{ts}] {msg}\n")
            self._get_file().flush()
        return len(msg)

    def flush(self):
        if self._file:
            self._file.flush()

PIPE = (b'\xe0\xf0\xf0\xf0\xf0',
        b'\xe1\xf1\xf1\xf1\xf1',
        b'\xe2\xf2\xf2\xf2\xf2',
        b'\xe3\xf3\xf3\xf3\xf3',
        b'\xe4\xf4\xf4\xf4\xf4',
        b'\xe5\xf5\xf5\xf5\xf5',
        b'\xe6\xf6\xf6\xf6\xf6',
        b'\xe7\xf7\xf7\xf7\xf7',
        b'\xe8\xf8\xf8\xf8\xf8')

ALIVE_SIGNAL = '0000'

# --- Global Constants ---
CONFIG_PATH = '/home/pi/HBELL-Sender/hbell.cfg'

nrf_lock = threading.Lock()

def load_config(path):
    """Loads configuration from the specified path."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Configuration file not found at {path}")
    config = configparser.ConfigParser()
    config.read(path)
    return config


def setup_nrf(config):
    """Initializes and configures the nRF24L01 module."""
    try:
        spi_speed = config.getint('NRF24', 'SPI_SPEED')
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = spi_speed
        spi.close()
        print("SPI device access check successful: /dev/spidev0.0")
    except (IOError, configparser.Error) as e:
        print(f"SPI device initialization failed: {e}")
        raise SystemExit("Please check SPI configuration.")

    # nRF24L01 CE and CSN pins (24, 0 means CE=GPIO24, CSN=SPI_CE0)
    nrf = RF24(24, 0)
    print("Initializing nRF24L01 module...")
    if not nrf.begin():
        raise RuntimeError("nRF24L01 hardware initialization failed. Module not responding.")

    try:
        pa_level = RF24_PA_HIGH
        data_rate = RF24_250KBPS
        channel = config.getint('NRF24', 'CHANNEL')
        pipe_indices = [int(x.strip()) for x in config.get('NRF24', 'PIPE_IDX').split(',')]
        retry_count = config.getint('NRF24', 'RETRY_CNT')
        retry_interval = config.getint('NRF24', 'RETRY_INTERVAL')

        nrf.setPALevel(pa_level)
        nrf.setDataRate(data_rate)
        nrf.setChannel(channel)
        nrf.enableDynamicPayloads()
        nrf.setAutoAck(True)
        nrf.enableAckPayload()
        nrf.setRetries(retry_count, retry_interval)
        
        for idx in pipe_indices:
            if 0 <= idx < len(PIPE):
                nrf.openWritingPipe(PIPE[idx])

        nrf.stopListening()
        print(f"nRF24L01 module configured successfully. Pipe indices: {pipe_indices}")
        nrf.printDetails()
        return nrf, pipe_indices

    except configparser.Error as e:
        print(f"Failed to read nRF24 configuration: {e}")
        raise SystemExit("Please check nRF24 settings in the config file.")


def send_message(nrf, store_number, number, is_negative, pipe_indices, config):
    """Sends message to multiple pipes with ACK counting."""
    command = "-" if is_negative else "+"
    flag_alive = (number == ALIVE_SIGNAL)
    data_to_send = f"{store_number},{command},{number}"
    data = data_to_send.encode('utf-8')

    max_retries = 3 if number != ALIVE_SIGNAL else 1
    retry_delays = [0.5, 1, 2]
    max_svr_no = config.getint('STORE', 'MAX_SVR_NO')
    ack_receivers = set()
    ack_pipes = set()

    for attempt in range(max_retries):
        pending_pipes = [idx for idx in pipe_indices if idx not in ack_pipes]
        
        for idx in pending_pipes:
            with nrf_lock:
                nrf.openWritingPipe(PIPE[idx])
                success = nrf.write(data)
                if success and nrf.available() and not flag_alive:
                    ack_size = nrf.getDynamicPayloadSize()
                    ack = nrf.read(ack_size).decode('utf-8', errors='ignore').strip('\x00').strip()
                    if ack:
                        parts = ack.split(',')
                        if len(parts) == 2:
                            store_addr, pipe_id = parts
                            if store_addr not in ack_receivers:
                                ack_receivers.add(store_addr)
                                ack_pipes.add(int(pipe_id))
                                print(f"ACK received from: {store_addr} (pipe {pipe_id})")
            
            if success:
                print(f"Transmission successful to pipe {idx}: {data_to_send}")
            else:
                print(f"Transmission failed on pipe {idx}, attempt {attempt + 1}/{max_retries}")
        
        if len(ack_receivers) >= max_svr_no:
            print(f"All {max_svr_no} receivers acknowledged: {ack_receivers}")
            return "ok"
        
        if attempt < max_retries - 1:
            print(f"Retrying... ({len(ack_receivers)}/{max_svr_no} ACKs received)")
            time.sleep(retry_delays[attempt])
    
    print(f"Transmission completed with {len(ack_receivers)}/{max_svr_no} ACKs")
    return "ok" if len(ack_receivers) >= max_svr_no else "fail"


def server(nrf, config, pipe_indices):
    """
    Listens on a TCP socket for commands and triggers nRF transmissions.
    """
    host = 'localhost'
    port = 6000
    store_number = config.get('STORE', 'ADDRESS')

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.bind((host, port))
            s.listen()
            print(f"Listening for commands on {host}:{port}")

            while True:
                conn, addr = s.accept()
                with conn:
                    print(f"Accepted connection from {addr}")
                    try:
                        data = conn.recv(1024)
                        if not data:
                            continue

                        msg = data.decode().strip()
                        print(f"Received command: {msg}")
                        
                        parts = msg.split(',')
                        if len(parts) != 2:
                            print(f"Invalid command format: {msg}")
                            conn.sendall(b'fail')
                            continue

                        number_str, command_char = parts
                        if command_char not in ('+', '-'):
                            print(f"Invalid command operator: {command_char}")
                            conn.sendall(b'fail')
                            continue
                        
                        is_negative = (command_char == '-')
                        result = send_message(nrf, store_number, number_str, is_negative, pipe_indices, config)
                        conn.sendall(result.encode())

                    except Exception as e:
                        print(f"Error during connection with {addr}: {e}")
                    finally:
                        print(f"Connection from {addr} closed.")
    except Exception as e:
        print(f"Server thread failed: {e}")


def alive_check(nrf, config, pipe_indices):
    """Periodically sends an 'alive' signal."""
    alive_interval = config.getint('NRF24', 'ALIVE_INTERVAL', fallback=30)
    store_number = config.get('STORE', 'ADDRESS')
    
    while True:
        try:
            send_message(nrf, store_number, ALIVE_SIGNAL, is_negative=True, pipe_indices=pipe_indices, config=config)
            time.sleep(alive_interval)
        except Exception as e:
            print(f"Error in alive_check thread: {e}")
            time.sleep(alive_interval)


def main():
    """Main function to set up and run the application."""
    log_writer = DailyLogWriter(LOG_DIR)
    sys.stdout = log_writer
    sys.stderr = log_writer

    global nrf_lock
    nrf_lock = threading.Lock()
    nrf = None
    pipe_indices = None
    try:
        config = load_config(CONFIG_PATH)
        nrf, pipe_indices = setup_nrf(config)

        # Start background threads
        server_thread = threading.Thread(target=server, args=(nrf, config, pipe_indices), daemon=True)
        alive_thread = threading.Thread(target=alive_check, args=(nrf, config, pipe_indices), daemon=True)
        
        server_thread.start()
        alive_thread.start()

        # Keep the main thread alive to handle shutdown
        print("Application running. Press Ctrl+C to exit.")
        while True:
            time.sleep(1)

    except (FileNotFoundError, RuntimeError, SystemExit) as e:
        print(f"Startup failed: {e}")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nShutting down application.")
    finally:
        if nrf:
            nrf.powerDown()
            print("nRF24L01 powered down.")
        print("Exiting.")


if __name__ == "__main__":
    main()
