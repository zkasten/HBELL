import time
import sys
import threading
import socket
import datetime
import os
import configparser

# HBELL Wifi Multicast Receiver
# V1.3.0
#
# 2026-02-05 Refectored legacy code, Added ACK handling from multiple servers - Hyukjoo

LOG_DIR = '/home/pi/log'


class DailyLogWriter:
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
            self._file = open(os.path.join(self.log_dir, f"{today}-wifi.log"), 'a')
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


_log = DailyLogWriter(LOG_DIR)
sys.stdout = _log
sys.stderr = _log

config = configparser.ConfigParser()

try:
    config.read('/home/pi/HBELL-Sender/hbell.cfg')

    STORE_NUMBER   = config['STORE']['ADDRESS']
    ALIVE_INTERVAL = int(config['NRF24']['ALIVE_INTERVAL'])
    MAX_SVR_NO     = int(config['STORE']['MAX_SVR_NO'])
    
    MCAST_GRP      = config['WIFI-M']['MCAST_GRP']
    MCAST_PORT     = int(config['WIFI-M']['MCAST_PORT'])
    MCAST_TIMEOUT  = int(config['WIFI-M']['MCAST_TIMEOUT'])
    MCAST_RETR_CNT = int(config['WIFI-M']['MCAST_RETRY_CNT'])
except Exception as e:
    print(f"Config error: {e}")
    sys.exit(1)

client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
client_socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
client_socket.bind(('', 55001))
client_socket.settimeout(MCAST_TIMEOUT)
socket_lock = threading.Lock()

def send_message(number, is_delete):
    try:
        formatted_number = str(number)
        prefix = '-' if is_delete else '+'
        message = f"{STORE_NUMBER},{prefix},{formatted_number}".encode('utf-8')
        ack_info = set()

        with socket_lock:
            for i in range(MCAST_RETR_CNT):
                client_socket.sendto(message, (MCAST_GRP, MCAST_PORT))
                time.sleep(0.05)
                client_socket.sendto(message, (MCAST_GRP, MCAST_PORT))
                if formatted_number == '0000':
                    break
                
                while True:
                    try:
                        data, server = client_socket.recvfrom(1024)
                        print(data)
                        print(data.decode('utf-8'))
                        ack_info.add(data.decode('utf-8'))
                        print(f"Received ACK: '{data.decode()}' from {server}")
                        print(f"Server Cnt: {len(ack_info)}")
                        if len(ack_info) >= MAX_SVR_NO:
                            break
                    except socket.timeout:
                        print(f"Timeout. ACK count: {len(ack_info)}/{MAX_SVR_NO}")
                        break
                
                if len(ack_info) >= MAX_SVR_NO:
                    return "ok"
                print(f"Retry {i+1}/{MCAST_RETR_CNT}")

        return "fail"
    except Exception as e:
        print(f"-ERR: send_message - {e}")
        return "error"

def start_server_thread():
    while True:
        try:
            server()
        except Exception as e:
            print(f"-Err: server crashed- {e}")
        time.sleep(5)

def server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(('localhost', 7000))
        s.listen()
        while True:
            conn, addr = s.accept()
            with conn:
                try:
                    data = conn.recv(1024)
                    if not data:
                        continue

                    msg = data.decode().strip()
                    arr = msg.split(',')
                    
                    if len(arr) != 2 or arr[1] not in ['+', '-']:
                        conn.sendall(b"-ERR: invalid format\n")
                        continue
                    
                    is_delete = (arr[1] == '-')
                    result = send_message(arr[0], is_delete)
                    conn.sendall(result.encode())
                except Exception as e:
                    print(f"-ERR: Connection error- {e}\n")
                    try:
                        conn.sendall(b"error")
                    except:
                        pass

def aliveCheck():
    try:
        while True:
            send_message('0000', is_delete=True)
            time.sleep(ALIVE_INTERVAL)

    except KeyboardInterrupt:
        print("break!")
    
def stressTest():
    try:
        i = 0
        while True:
            send_message(str(i), is_delete=False)
            time.sleep(1)
            if i == 9999:
                i = 0
            i+= 1

    except KeyboardInterrupt:
        print("break!")

def main():

    try:
#        thread3 = threading.Thread(target=stressTest, args=())
#        thread3.start()
#        thread3.join()

        threading.Thread(target=aliveCheck, daemon=True).start()
        start_server_thread()

    finally:
        client_socket.close()

if __name__ == '__main__':
    main()