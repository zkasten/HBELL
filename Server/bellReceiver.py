#!/usr/bin/env python3
# 2025-04-22 : change signal strength MAX -> HIGH
#              change channel 75 -> 76
#              
import time
import spidev
#from RF24 import RF24, RF24_PA_HIGH, RF24_1MBPS
from RF24 import RF24, RF24_PA_HIGH, RF24_250KBPS
import datetime
import os
import psutil
import queue

# 2025-05-27 : add is_file_open - Hyukjoo
# 2025-05-30 : move setup_log_file() to while loop - Hyukjoo

FILE_ALIVE1 = "/home/pi/log/alive1.txt"
FILE_ALIVE2 = "/home/pi/log/alive2.txt"
FILE_ALIVE3 = "/home/pi/log/alive3.txt"
FILE_ALIVE4 = "/home/pi/log/alive4.txt"

# SPI Setup
def setup_spi():
    try:
        spi = spidev.SpiDev()
        spi.open(0, 0)
        spi.max_speed_hz = 2000000  # 2MHz
        spi.close()
        print("SPI device access successful: /dev/spidev0.0")
    except IOError as e:
        print(f"Failed to open SPI device: {e}")
        raise SystemExit("Check SPI settings (Enable SPI in raspi-config)")

# RF24 Setup
def setup_rf24():
    nrf = RF24(24, 0)
############################################
#   ADDRESS                                #
    pipe = b"\xe1\xf0\xf0\xf0\xf1"
############################################
    if not nrf.begin():
        print("nRF24L01 initialization failed! Check hardware connection.")
        raise RuntimeError("nRF24L01 hardware initialization failed!")


############################################
#   RF SETTING                             #
    nrf.setPALevel(RF24_PA_HIGH)
    nrf.setDataRate(RF24_250KBPS)
    #nrf.setPALevel(RF24_PA_MAX)
    #nrf.setDataRate(RF24_1MBPS)
############################################

############################################
#   CHANNEL                                #
    nrf.setChannel(110)
############################################

    nrf.enableDynamicPayloads()
    nrf.setAutoAck(True)
    nrf.openReadingPipe(0, pipe)
    nrf.startListening()
    return nrf

def is_file_open(file_path):
    for proc in psutil.process_iter(['pid', 'open_files']):
        try:
            for file in proc.info['open_files'] or []:
                if file.path == file_path:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return False

def touch_file(file_path):
    try:
        with open(file_path, 'a'):
            os.utime(file_path, None)  # Update the timestamp
    except Exception as e:
        print(f"Error: File '{file_path}' not created. {e}")

# Log File Setup
def setup_log_file():
    cur_date = datetime.date.today()
    log_dir = "/home/pi/log"
    os.makedirs(log_dir, exist_ok=True) # Create log directory
    log_file = os.path.join(log_dir, f"{cur_date}.log")
    return log_file

# Data Processing and Logging
def process_data(nrf):
    q = queue.Queue()
    while True:
        log_file = setup_log_file()
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
                    if len(arr) < 3:
                        print(f"Invalid message format: {message}")
                        continue

                    if arr[1] == '-':
                        if arr[2] == '0000':
                            # Alive Signal
                            if arr[0] == '001':
                                touch_file(FILE_ALIVE1)
                            if arr[0] == '002':
                                touch_file(FILE_ALIVE2)
                            if arr[0] == '003':
                                touch_file(FILE_ALIVE3)
                            if arr[0] == '004':
                                touch_file(FILE_ALIVE4)
                            continue
                        message = f"{message}"
                        q.put(message)
                    if arr[1] == '+':
                        message = f"{arr[0]},-,{arr[2]}\n{message}"
                        q.put(message)

                    print("----------------------")
                    if is_file_open(log_file):
                        #time.sleep(0.01)
                        print(f"--WAIT for file to be closed: {log_file}")
                        continue
                    else:
                        print(f"Writing to log file: {log_file}")

                        with open(log_file, "a") as file:
                            #file.write(message + "\n")
                            print("Q size:", str(q.qsize()))
                            while not q.empty():
                                print("write======"+ str(q.qsize()))
                                #msg = q.get()
                                #print("msg:", msg)
                                file.write(q.get() + "\n")
                                #file.write(msg + "\n")
#                            file.flush()
#                            print("1======================")
#                        print("2======================")
#                    print("3======================")

                except UnicodeDecodeError:
                    print(f"Received invalid data: {payload}")

#                print("4======================")
#            print("5======================")
        else:
#            print("No data available from nRF24L01")
            time.sleep(0.1)  # Sleep to avoid busy waiting
            continue

        time.sleep(0.01)
    print("7======================")

if __name__ == "__main__":
    setup_spi()
    nrf = setup_rf24()
    print("Starting to receive data...")
    try:
        process_data(nrf)
    except KeyboardInterrupt:
        print("Stopped by user")
    finally:
        nrf.powerDown()
