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
def process_data(nrf, log_file):
    while True:
        if nrf.available():
            payload_size = nrf.getDynamicPayloadSize()
            if payload_size > 0:
                payload = nrf.read(payload_size)
                try:
                    message = payload.decode('utf-8').strip()
                    print(f"Received: {message}")
                    arr = message.split(',')
                    if arr[1] == '-' and arr[2] == '0000':
                        # Alive Signal
                        if arr[0] == '001':
                            touch_file(FILE_ALIVE1)
                        if arr[0] == '002':
                            touch_file(FILE_ALIVE2)
                        if arr[0] == '003':
                            touch_file(FILE_ALIVE3)
                        if arr[0] == '004':
                            touch_file(FILE_ALIVE4)
                    if arr[1] == '+':
                        message = f"{arr[0]},-,{arr[2]}\n{message}"
                    with open(log_file, "a") as file:
                        file.write(message + "\n")
                except UnicodeDecodeError:
                    print(f"Received invalid data: {payload}")
        time.sleep(0.01)

if __name__ == "__main__":
    setup_spi()
    nrf = setup_rf24()
    log_file = setup_log_file()
    print("Starting to receive data...")
    try:
        process_data(nrf, log_file)
    except KeyboardInterrupt:
        print("Stopped by user")
    finally:
        nrf.powerDown()
