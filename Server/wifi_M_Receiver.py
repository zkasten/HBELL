#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import datetime
import os
import queue
import configparser
import struct
import logging
import threading
import fcntl
import time

# HBELL Wifi Multicast Receiver
# V1.3.0
#
# 2026-02-05 Refectored legacy code, Added ACK handling from multiple servers - Hyukjoo

BASE_DIR = "/home/pi"
LOG_DIR = os.path.join(BASE_DIR, "log")
CONFIG_FILE = os.path.join(BASE_DIR, "HBELL-Receiver/hbell.cfg")
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
ALIVE_SIGNAL = '0000'

# 3rd digit of [STORE][ADDRESS]
UNIT_INDEX = 2

class Config:
    """Manages the configuration file (.cfg)."""
    def __init__(self, path):
        self._config = configparser.ConfigParser()
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found: {path}")
        self._config.read(path)

    @property
    def store_number(self):
        return self._config.get('STORE', 'ADDRESS')

    @property
    def is_multi(self):
        return self._config.get('STORE', 'IS_MULTI', fallback='N').upper()
    
    @property
    def mcast_grp(self):
        return self._config.get('WIFI-M', 'MCAST_GRP')
    
    @property
    def mcast_port(self):
        try:
            return int(self._config.get('WIFI-M', "MCAST_PORT"))
        except (ValueError, configparser.NoOptionError) as e:
            raise ValueError(f"Invalid MCAST_PORT config: {e}")
    
    @property
    def mcast_buffer(self):
        try:
            return int(self._config.get('WIFI-M', 'MCAST_BUF_SIZE'))
        except (ValueError, configparser.NoOptionError) as e:
            raise ValueError(f"Invalid MCAST_BUF_SIZE config: {e}")

class Data:
    """Data class for structuring received messages."""
    def __init__(self, store, type, number):
        self.store = store
        self.type = type
        self.number = number

    def __str__(self):
        return f"Data(store={self.store}, type={self.type}, number={self.number})"

class LogWriter(threading.Thread):
    """
    Thread that gets log messages from a queue and writes them to a file,
    using a file-locking mechanism to safely handle concurrent access.
    """
    def __init__(self, log_queue):
        super().__init__(daemon=True)
        self.log_queue = log_queue
        self.logger = logging.getLogger('LogWriter')
        self.setup_logger()
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def setup_logger(self):
        """Sets up a console logger for internal thread status and errors."""
        self.logger.setLevel(logging.WARNING)
        console_handler = logging.StreamHandler()
        console_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_handler.setFormatter(console_formatter)
        self.logger.addHandler(console_handler)

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
                        self.logger.warning(f"Log file '{log_file_path}' is locked. Retrying in 1 second...")
                        time.sleep(0.1)
                        continue

            except Exception as e:
                self.logger.error(f"An unexpected error occurred in LogWriter thread: {e}", exc_info=True)
                if messages:
                    for msg in reversed(messages):
                        self.log_queue.put(msg)
                time.sleep(0.5)

def setup_logging():
    """Global logging setup for console output."""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def setup_multicast_socket(config):
    """Sets up and returns a UDP socket configured for multicast."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('', config.mcast_port))
    mreq = struct.pack('4sl', socket.inet_aton(config.mcast_grp), socket.INADDR_ANY)
    server_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
    logging.info(f"UDP Multicast Server listening on {config.mcast_grp}:{config.mcast_port}")
    return server_socket

def touch_file(file_path):
    """Updates the file's timestamp to the current time."""
    try:
        with open(file_path, 'a'):
            os.utime(file_path, None)
    except Exception as e:
        logging.warning(f"Failed to create or update file '{file_path}': {e}")

def parse_message(message_str):
    """Parses the received string into a Data object."""
    # Sanitize message, removing extra whitespace and newlines
    message_str = message_str.strip()
    parts = message_str.split(',')
    if len(parts) < 3:
        logging.warning(f"Invalid message format: {message_str}")
        return None
    
    store, msg_type, number = parts[0], parts[1], parts[2]
    
    if not store.isdigit() or not number.isdigit():
        logging.warning(f"Message contains non-numeric values: {message_str}")
        return None
        
    return Data(store, msg_type, number)

def handle_message(data, config, log_queue):
    """Processes the parsed message data."""
    # Check for store group match (first digit)
    if data.store[0] != config.store_number[0]:
        logging.debug(f"Store group mismatch for message: {data}")
        return False

    # If not in multi-store mode, check for exact store number match
    if config.is_multi == 'N' and data.store[2] != config.store_number[2]:
        logging.warning(f"Store number mismatch in single-store mode: {data.store} - {config.store_number}")
        return False

    if data.type == '-':
        if data.number == ALIVE_SIGNAL:  # Alive Signal
            logging.info(f"Alive signal received for unit {data.store[UNIT_INDEX]}")
            if data.store[UNIT_INDEX] in ALIVE_FILES:
                touch_file(ALIVE_FILES[data.store[UNIT_INDEX]])
        else:  # Number Deletion
            logging.info(f"Put DELETE log_queue: {data.store},-,{data.number}")
            log_queue.put(f"{data.store},-,{data.number}")

    elif data.type == '+': # Number Addition
        # Put both deletion and addition messages in the queue
        logging.info(f"Put ADD log_queue: {data.store},-,{data.number}")
        logging.info(f"Put ADD log_queue: {data.store},+,{data.number}")
        log_queue.put(f"{data.store},-,{data.number}")
        log_queue.put(f"{data.store},+,{data.number}")

    return True

def main():
    """Main execution function."""
    setup_logging()
    try:
        config = Config(CONFIG_FILE)
    except (FileNotFoundError, ValueError) as e:
        logging.critical(e)
        return

    log_queue = queue.Queue()
    log_writer = LogWriter(log_queue)
    log_writer.start()

    server_socket = setup_multicast_socket(config)
    server_socket.settimeout(5)

    try:
        logging.info("Starting to receive data...")
        while True:
            try:
                data, addr = server_socket.recvfrom(config.mcast_buffer)
            except socket.timeout:
                continue
    
            try:
                message_str = data.decode('utf-8')
                logging.debug(f"Received raw message: '{message_str.strip()}' from {addr}")
                
                parsed_data = parse_message(message_str)
                if parsed_data:
                    # parsed_data(store, msg_type, number)
                    if handle_message(parsed_data, config, log_queue) and parsed_data.number != ALIVE_SIGNAL:
                        logging.info(f"parsed data: {config.store_number},{parsed_data.number}")
                        try:
                            msg = f"{config.store_number[0]}{config.store_number[1]}{parsed_data.store[2]},{message_str.strip()}"
                            #server_socket.sendto(f"{config.store_number},{data}", addr)
                            server_socket.sendto(msg.encode('utf-8'), addr)
                        except socket.error as e:
                            logging.warning(f"Failed to send response to {addr}: {e}")

            except UnicodeDecodeError:
                logging.warning(f"Received invalid (non-UTF-8) data from {addr}: {data}")
            except Exception as e:
                logging.error(f"Error processing message from {addr}: {e}", exc_info=True)

    except KeyboardInterrupt:
        logging.info("Server stopped by user.")
    except Exception as e:
        logging.critical(f"A critical error occurred: {e}", exc_info=True)
    finally:
        logging.info("Closing socket and exiting program.")
        server_socket.close()
        log_writer.stop()
        log_queue.join()

if __name__ == '__main__':
    main()