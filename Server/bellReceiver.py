import time
import spidev
from pyrf24 import RF24, RF24_PA_HIGH, RF24_250KBPS
import datetime
import os
import fcntl
import queue
import sys
import configparser
import threading
import logging

# HBELL nRF24 bellReceiver
# V1.3.0

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

config = configparser.ConfigParser()

try:
    BASE_DIR = "/home/pi"
    LOG_DIR = os.path.join(BASE_DIR, "log")
    config.read('/home/pi/HBELL-Receiver/hbell.cfg')
    STORE_NUMBER = config['STORE']['ADDRESS']
    
    ALIVE_INTERVAL = int(config['NRF24']['ALIVE_INTERVAL'])

    IS_MULTI = config['STORE'].get('IS_MULTI', 'N').upper()
except Exception as e:
    print(f"Config error: {e}")
    sys.exit(1)

ALIVE_FILES = {
    '0': os.path.join(LOG_DIR, "alive0.txt"),
    '1': os.path.join(LOG_DIR, "alive1.txt"),
    '2': os.path.join(LOG_DIR, "alive2.txt"),
    '3': os.path.join(LOG_DIR, "alive3.txt"),
    '4': os.path.join(LOG_DIR, "alive4.txt"),
    '5': os.path.join(LOG_DIR, "alive5.txt"),
    '6': os.path.join(LOG_DIR, "alive6.txt"),
    '7': os.path.join(LOG_DIR, "alive7.txt"),
    '8': os.path.join(LOG_DIR, "alive8.txt"),
    '9': os.path.join(LOG_DIR, "alive9.txt"),
}

def setup_spi():
    try:
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = int(config['NRF24']['SPI_SPEED'])
        spi.close()
        print("SPI device access successful: /dev/spidev0.0")
    except IOError as e:
        print(f"Failed to open SPI device: {e}")
        raise SystemExit("Check SPI settings (Enable SPI in raspi-config)")

def setup_rf24():
    nrf = RF24(24, 0)
    if not nrf.begin():
        print("nRF24L01 initialization failed! Check hardware connection.")
        raise RuntimeError("nRF24L01 hardware initialization failed!")

    pipe_idx = int(config['NRF24']['PIPE_IDX'])
    if 0 <= pipe_idx < len(PIPE):
        pipe = PIPE[pipe_idx]
    else:
        raise ValueError(f"Invalid PIPE_IDX: {pipe_idx}. Must be 0-{len(PIPE)-1}")

    nrf.setPALevel(RF24_PA_HIGH)
    nrf.setDataRate(RF24_250KBPS)
    nrf.setChannel(int(config['NRF24']['CHANNEL']))
    nrf.enableDynamicPayloads()
    nrf.setAutoAck(True)
    nrf.enableAckPayload()
    nrf.openReadingPipe(1, PIPE[pipe_idx])
    nrf.startListening()
    return nrf, pipe_idx

def touch_file(file_path):
    try:
        with open(file_path, 'a'):
            os.utime(file_path, None)
    except Exception as e:
        print(f"Error: File '{file_path}' not created. {e}")

class LogWriter(threading.Thread):
    """Thread that writes log messages from queue to file with file locking."""
    def __init__(self, log_queue):
        super().__init__(daemon=True)
        self.log_queue = log_queue
        self.logger = logging.getLogger('LogWriter')
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        messages = []
        while not self._stop_event.is_set():
            try:
                timeout = 0.1 if messages else 0.5
                message = self.log_queue.get(timeout=timeout)
                messages.append(message)
                self.log_queue.task_done()
                
                if self.log_queue.empty():
                    raise queue.Empty

            except queue.Empty:
                if not messages:
                    continue

                log_file_path = os.path.join(LOG_DIR, f"{datetime.date.today()}.log")
                os.makedirs(LOG_DIR, exist_ok=True)
                
                while True:
                    try:
                        with open(log_file_path, 'a') as f:
                            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
                            for msg in messages:
                                self.logger.info(f"-write log: {msg}")
                                f.write(msg + '\n')
                            f.flush()
                            fcntl.flock(f, fcntl.LOCK_UN)
                            messages.clear()
                            break
                    except (IOError, BlockingIOError):
                        self.logger.warning(f"Log file '{log_file_path}' is locked. Retrying...")
                        time.sleep(0.1)
                        continue

            except Exception as e:
                self.logger.error(f"An unexpected error occurred in LogWriter thread: {e}", exc_info=True)
                if messages:
                    for msg in reversed(messages):
                        self.log_queue.put(msg)
                time.sleep(0.5)

def process_data(nrf, log_queue, pipe_idx):
    # 첫 수신 전 ACK 준비
    ack_msg = f"{STORE_NUMBER},{pipe_idx}".encode('utf-8')
    nrf.writeAckPayload(1, ack_msg)
    
    while True:
        if nrf.available():
            print("Data available from nRF24L01")
            payload_size = nrf.getDynamicPayloadSize()
            print(f"Payload size: {payload_size}")
            if payload_size > 0:
                payload = nrf.read(payload_size)
                try:
                    message = payload.decode('utf-8').strip()
                    print(f"Received: {message}")
                    arr = message.split(',')
                    
                    if len(arr) < 3 or not arr[0].isdigit() or not arr[2].replace('\n','').isdigit():
                        print(f"Invalid message format: {message}")
                        nrf.writeAckPayload(1, ack_msg)
                        continue
                    
                    if IS_MULTI == 'N' and arr[0] != STORE_NUMBER:
                        print("Store number mismatch:"+ str(arr[0]))
                        nrf.writeAckPayload(1, ack_msg)
                        continue

                    if arr[1] == '-':
                        if arr[0][0] != STORE_NUMBER[0]:
                            nrf.writeAckPayload(1, ack_msg)
                            continue
                        if arr[2] == ALIVE_SIGNAL:
                            print("Alive Signal received")
                            server_id = arr[0][2]
                            if server_id in ALIVE_FILES:
                                touch_file(ALIVE_FILES[server_id])
                            continue
                        else:
                            log_queue.put(message)
                        
                    if arr[1] == '+':
                        log_queue.put(f"{arr[0]},-,{arr[2]}")
                        log_queue.put(message)
                    
                    # 다음 수신을 위한 ACK 준비
                    nrf.writeAckPayload(1, ack_msg)

                except UnicodeDecodeError:
                    print(f"Received invalid data: {payload}")

        else:
            time.sleep(0.1)
            continue

        time.sleep(0.01)

def setup_logging():
    """Global logging setup for console output."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

if __name__ == "__main__":
    setup_logging()
    setup_spi()
    nrf, pipe_idx = setup_rf24()
    
    log_queue = queue.Queue()
    log_writer = LogWriter(log_queue)
    log_writer.start()
    
    print("Starting to receive data...")
    try:
        process_data(nrf, log_queue, pipe_idx)
    except KeyboardInterrupt:
        print("Stopped by user")
        log_queue.join()
        log_writer.stop()
    finally:
        nrf.powerDown()
