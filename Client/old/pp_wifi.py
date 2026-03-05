import time
import sys
import termios
import tty
import threading
import socket
import datetime
import os
import configparser

import socket

# 2025-08-14 : Initial Created - Hyukjoo

config = configparser.ConfigParser()
config.read('/home/pi/hbell.cfg')

STORE_NUMBER = config['STORE']['ADDRESS']
ALIVE_INTERVAL = int(config['NRF24']['ALIVE_INTERVAL'])

PORT = 8089
client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
client_socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
broadcast_address = ('<broadcast>', PORT)

# Log File Setup
def setup_log_file():
    cur_date = datetime.date.today()
    log_dir = "/home/pi/log"
    os.makedirs(log_dir, exist_ok=True) # Create log directory
    log_file = os.path.join(log_dir, f"{cur_date}.log")
    rcv_log_file = os.path.join(log_dir, f"rcv_{cur_date}.log")
    return log_file, rcv_log_file

def send_message(number, is_negative):
    global client_socket, broadcast_address
    formatted_number = str(number)
    if is_negative:
        data_to_send = f"{STORE_NUMBER},-,{formatted_number}"
    else:
        data_to_send = f"{STORE_NUMBER},+,{formatted_number}"
    client_socket.sendto(data_to_send.encode('utf-8'), broadcast_address)


# 사용자 안내 메시지
print("숫자를 입력하고 엔터 키를 누르면 '스토어번호,+,입력숫자' 형식으로 전송됩니다.")
print("입력 중 +, a, b, c 키를 누르면 '스토어번호,-,입력숫자' 형식으로 즉시 전송됩니다.")

# 터미널 설정 저장
original_settings = termios.tcgetattr(sys.stdin)

def keypad():
    try:
        # cbreak 모드로 설정: 문자 단위 입력 처리, 에코 활성화
        tty.setcbreak(sys.stdin)
        buffer = ""  # 입력 숫자를 저장할 버퍼
        while True:
            char = sys.stdin.read(1)  # 한 글자씩 읽기
    
            if char == '\n':  # 엔터 키
                if buffer:
                    try:
                        number = int(buffer)
                        if 1 <= number <= 9999:
                            print(number)
                            send_message(number, is_negative=False)  # "+" 형식으로 전송
                        else:
                            print(f"입력 범위 오류: {number}, 1에서 99999까지 입력하세요.")
                    except ValueError:
                        print("잘못된 숫자 형식입니다.")
                    buffer = ""  # 버퍼 초기화
                else:
                    print("빈 메시지는 전송되지 않습니다.")
    
            elif char in ('+', 'a', 'b'):  # +, a, b, c 키
                if buffer:
                    try:
                        number = int(buffer)
                        if 1 <= number <= 9999:
                            print(number)
                            send_message(number, is_negative=True)  # "-" 형식으로 즉시 전송
                        else:
                            print(f"입력 범위 오류: {number}, 1에서 99999까지 입력하세요.")
                    except ValueError:
                        print("잘못된 숫자 형식입니다.")
                    buffer = ""  # 버퍼 초기화
                else:
                    print("빈 메시지는 전송되지 않습니다.")

            elif char in ('c'):
                print("Send RING signal")
                send_message('99999', is_negative=True)  # Send Ring signa
    
            elif char.isdigit():  # 숫자 입력
                buffer += char  # 버퍼에 숫자 추가
    
            else:  # 잘못된 입력
                print(f"잘못된 입력: '{char}', 숫자와 '+', 'a', 'b', 'c'만 입력하세요.")
                buffer = ""  # 버퍼 초기화
    
    except KeyboardInterrupt:
        print("사용자에 의해 중지됨.")
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original_settings)

def aliveCheck():
    try:
        while True:
            send_message('0000', is_negative=True)
            time.sleep(ALIVE_INTERVAL)

    except KeyboardInterrupt:
        print("사용자에 의해 중지됨.")
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original_settings)
    
def stressTest():
    try:
        i = 0
        while True:
            send_message(str(i), is_negative=False)
            time.sleep(1)
            if i == 9999:
                i = 0
            i+= 1

    except KeyboardInterrupt:
        print("사용자에 의해 중지됨.")
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original_settings)

thread1 = threading.Thread(target=keypad, args=())
thread2 = threading.Thread(target=aliveCheck, args=())
#thread3 = threading.Thread(target=stressTest, args=())

thread1.start()
thread2.start()
#thread3.start()

thread1.join()
thread2.join()
#thread3.join()


