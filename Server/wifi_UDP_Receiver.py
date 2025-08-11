import socket
import datetime
import os
import queue
import psutil

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

host = '0.0.0.0'
port = 8089

server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server_socket.bind((host, port))

print(f"UDP Server listening on {host}:{port}")

#serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#serversocket.bind(('0.0.0.0', 8089))
#serversocket.listen(5) # become a server socket, maximum 5 connections

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
            print(f"Received message: {msg} from {addr}")
            data, addr = server_socket.recvfrom(1024)
            msg = data.decode('utf-8')
            arr = msg.split(',')
            if len(arr) != 3:
                print("Invalid message format")
                continue
            if not arr[0].isdigit():
                continue
            if not arr[2].replace('\n','').isdigit():
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
                if arr[0] != STORE_NUMBER:
                    print("Store number mismatch:"+ STORE_NUMBER)
                    continue
                message = f"{message}"
                q.put(message)
                
            if IS_MULTI == 'N' and arr[0] != STORE_NUMBER:
                    print("Store number mismatch:"+ STORE_NUMBER)
                    continue
                
            if arr[1] == '+':
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