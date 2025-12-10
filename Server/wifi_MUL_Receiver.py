import socket
import datetime
import os
import queue
import psutil
import configparser
import struct

# 2025-08-11 : Initial created based on wifiReceiver.py - Hyukjo
#              use IS_MULTI (Y/N) to determine if multi-store is enabled : hbell.cfg

FILE_ALIVE1 = "/home/pi/log/alive1.txt"
FILE_ALIVE2 = "/home/pi/log/alive2.txt"
FILE_ALIVE3 = "/home/pi/log/alive3.txt"
FILE_ALIVE4 = "/home/pi/log/alive4.txt"

config = configparser.ConfigParser()
config.read('/home/pi/hbell.cfg')
STORE_NUMBER = config['STORE']['ADDRESS']
IS_MULTI = config['STORE'].get('IS_MULTI', 'N').upper()

#host = '0.0.0.0'
#port = 8089
#server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#server_socket.bind((host, port))

MCAST_GRP = '224.0.0.1'
MCAST_PORT = 5007
BUFF_SIZE = 1024
server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
server_socket.bind(('', MCAST_PORT))
mreq = struct.pack('4sl', socket.inet_aton(MCAST_GRP), socket.INADDR_ANY)
server_socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

#print(f"UDP Server listening on {host}:{port}")

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

if __name__ == '__main__':
    q = queue.Queue()
    log_file = setup_log_file()
    print("Starting to receive data...")
    try:
        while True:
#            data, addr = server_socket.recvfrom(1024)
            data, addr = server_socket.recvfrom(BUFF_SIZE)

            message = data.decode('utf-8')
            print(f"Received message: {message} from {addr}")

            arr = message.split(',')
            if len(arr) != 3:
                print("Invalid message format")
                continue
            if not arr[0].isdigit():
                continue
            if not arr[2].replace("\r", "").replace("\n", "").isdigit():
                continue
            if arr[0][0] != STORE_NUMBER[0]:
#                print("store group mismatch - continue")
#                print(arr)
                continue
            
            if IS_MULTI == 'N' and arr[0] != STORE_NUMBER:
                    print("Store number mismatch:"+ str(arr[0]))
                    continue

            if arr[1] == '-':
                if arr[0][0] != STORE_NUMBER[0]:  # Store Group & number check
                    continue
                if arr[2] == '0000': # Alive Signal
                    print("Alive Signal received")
                    if arr[0][2] == '1':
                        touch_file(FILE_ALIVE1)
                    if arr[0][2] == '2':
                        touch_file(FILE_ALIVE2)
                    if arr[0][2] == '3':
                        touch_file(FILE_ALIVE3)
                    if arr[0][2] == '4':
                        touch_file(FILE_ALIVE4)
                    continue
                else: # Number Deletion
                    message = f"{message}"
                    q.put(message)
                
            elif arr[1] == '+':
                    message = f"{arr[0]},-,{arr[2]}\n{message}"
                    q.put(message)
                    
            if is_file_open(log_file):
                #time.sleep(0.01)
                print(f"--WAIT for file to be closed: {log_file}")
                continue
            else:
                print(f"Writing to log file: {log_file}")

                with open(log_file, "a") as file:
                    print("Q size:", str(q.qsize()))
                    while not q.empty():
                        print("write======"+ str(q.qsize()))
                        file.write(q.get() + "\n")

    except KeyboardInterrupt:
        print("Server stopped by user.")
    finally:
        server_socket.close()