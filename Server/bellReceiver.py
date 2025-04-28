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
    pipe = b"\xe6\xf0\xf0\xf0\xf0"
############################################
    if not nrf.begin():
        print("nRF24L01 initialization failed! Check hardware connection.")
        raise RuntimeError("nRF24L01 hardware initialization failed!")
    nrf.setPALevel(RF24_PA_HIGH)
    #nrf.setDataRate(RF24_1MBPS)
    nrf.setDataRate(RF24_250KBPS)
    nrf.setChannel(94)
  # nrf.setChannel(80) 4/27/2025
    nrf.enableDynamicPayloads()
    nrf.setAutoAck(True)
    nrf.openReadingPipe(1, pipe)
    nrf.startListening()
    return nrf

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
