import time
import spidev
#from RF24 import RF24, RF24_PA_MAX, RF24_1MBPS
from RF24 import RF24, RF24_PA_HIGH, RF24_250KBPS
import sys
import termios
import tty
import threading
import socket
import datetime
import os
import configparser

# 2025-09-25 : CHG pp.py -> bellSender.py for LCD sender - Hyukjoo
# 2025-06-05 : add configparser - Hyukjoo
# 2025-04-22 : change signal strength MAX -> HIGH
#              change channel 75 -> 76

config = configparser.ConfigParser()
config.read('/home/pi/hbell.cfg')

SERVER_IP = '10.142.36.190'

STORE_NUMBER = config['STORE']['ADDRESS']
ALIVE_INTERVAL = int(config['NRF24']['ALIVE_INTERVAL'])

# SPI 설정
spi = spidev.SpiDev()
try:
    spi.open(0, 0)
    spi.max_speed_hz = int(config['NRF24']['SPI_SPEED'])
    spi.close()
    print("SPI 장치 접근 성공: /dev/spidev0.0")
except IOError as e:
    print(f"SPI 장치 열기 실패: {e}")
    raise SystemExit("SPI 설정을 확인하세요")

# nRF24L01 설정
nrf = RF24(24, 0)  # CE: GPIO 24, CSN: SPI 0
###################################################################
#    ADDRESS                                                      #
pipe = config['NRF24']['PIPE'].encode('utf-8') 
#pipe = config['NRF24']['ADDRESS']
###################################################################

print("nRF24L01 초기화 시도...")
if not nrf.begin():
    print("초기화 실패: nRF24L01 모듈이 응답하지 않습니다.")
    raise RuntimeError("nRF24L01 하드웨어 초기화 실패!")

###################################################################
#    RF SETTING                                                   #
nrf.setPALevel(RF24_PA_HIGH)
nrf.setDataRate(RF24_250KBPS)
#nrf.setPALevel(config['NRF24']['PA_LEVEL'])
#nrf.setDataRate(config['NRF24']['DATA_RATE'])
#nrf.setPALevel(RF24_PA_MAX)
#nrf.setDataRate(RF24_1MBPS)
###################################################################

###################################################################
#    CHANNEL                                                      #
nrf.setChannel(int(config['NRF24']['CHANNEL']))
###################################################################

nrf.openReadingPipe(0, pipe)

nrf.enableDynamicPayloads()
nrf.setAutoAck(True)  # 자동 응답 활성화

nrf.setRetries(int(config['NRF24']['RETRY_CNT']), int(config['NRF24']['RETRY_INTERVAL']))
nrf.openWritingPipe(pipe)
nrf.stopListening()

nrf.printDetails()

# Log File Setup
def setup_log_file():
    cur_date = datetime.date.today()
    log_dir = "/home/pi/log"
    os.makedirs(log_dir, exist_ok=True) # Create log directory
    log_file = os.path.join(log_dir, f"{cur_date}.log")
    rcv_log_file = os.path.join(log_dir, f"rcv_{cur_date}.log")
    return log_file, rcv_log_file

def send_message(number, is_negative):
    result = "fail"
    """ 메시지를 전송하는 함수 """
    formatted_number = str(number)
    if is_negative:
        data_to_send = f"{STORE_NUMBER},-,{formatted_number}"
    else:
        data_to_send = f"{STORE_NUMBER},+,{formatted_number}"
    data = data_to_send.encode('utf-8')
    if nrf.write(data):
        result = "ok"
        print(f"전송 성공: {data_to_send}")
    else:
        print(f"전송 실패: {data_to_send}")
        nrf.printDetails()  # 실패 시 상태 출력
        
    return result

# 사용자 안내 메시지
print("숫자를 입력하고 엔터 키를 누르면 '스토어번호,+,입력숫자' 형식으로 전송됩니다.")
print("입력 중 +, a, b, c 키를 누르면 '스토어번호,-,입력숫자' 형식으로 즉시 전송됩니다.")

# 터미널 설정 저장
# original_settings = termios.tcgetattr(sys.stdin)

def start_server_thread():
    while True:
        try:
            t = threading.Thread(target=server, daemon=True)
            t.start()
            t.join()
        except Exception as e:
            print(f"-Err: {e}")
        time.sleep(1)

def server():
    HOST = 'localhost'
    PORT = 6000

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        while True:
            conn, addr = s.accept()
            with conn:
                while True:
                    data = conn.recv(1024)
                    is_negative = False
                    if not data:
                        break
                    msg = data.decode()
                    arr = msg.split(',')
                    if len(arr) != 2:
                        break
                    if arr[1] == '-':
                        is_negative = True
                    result = send_message(msg , is_negative)  # "+" 형식으로 전송
                    conn.sendall(result.encode())
    

def keypad():
    try:
        log_file, rcv_log_file = setup_log_file()
        # cbreak 모드로 설정: 문자 단위 입력 처리, 에코 활성화
        tty.setcbreak(sys.stdin)
        buffer = ""  # 입력 숫자를 저장할 버퍼
        while True:
    
            char = sys.stdin.read(1)  # 한 글자씩 읽기
    
            if char == '\n':  # 엔터 키
                if buffer:
                    try:
                        number = int(buffer)
                        if 1 <= number <= 99999:
                            send_message(number, is_negative=False)  # "+" 형식으로 전송

                            # clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            # clientsocket.connect((SERVER_IP, 8089))
                            # # clientsocket.send(b'001,+,123')
                            # msg = STORE_NUMBER +",+,"+ str(number)
                            # print("send wifi:"+ msg)
                            # clientsocket.send(msg.encode('utf-8'))
                            # clientsocket.shutdown(socket.SHUT_RDWR)
                            # clientsocket.close()
                            # now = datetime.datetime.now()
                            # ts = now.strftime("%H:%M:%S")
                            # with open(rcv_log_file, "a") as file:
                            #     file.write(ts +"|"+ msg + "\n")
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
                        if 1 <= number <= 99999:
                            send_message(number, is_negative=True)  # "-" 형식으로 즉시 전송

                            # clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                            # clientsocket.connect((SERVER_IP, 8089))
                            # # clientsocket.send(b'001,+,123')
                            # msg = STORE_NUMBER +",-,"+ str(number)
                            # print("send wifi:"+ msg)
                            # clientsocket.send(msg.encode('utf-8'))
                            # clientsocket.shutdown(socket.SHUT_RDWR)
                            # clientsocket.close()
                            # now = datetime.datetime.now()
                            # ts = now.strftime("%H:%M:%S")
                            # with open(rcv_log_file, "a") as file:
                            #     file.write(ts +"|"+ msg + "\n")
                        else:
                            print(f"입력 범위 오류: {number}, 1에서 99999까지 입력하세요.")
                    except ValueError:
                        print("잘못된 숫자 형식입니다.")
                    buffer = ""  # 버퍼 초기화
                else:
                    print("빈 메시지는 전송되지 않습니다.")
    
            elif char in ('c'):
                send_message('99999', is_negative=True)  # Alive Signal 전송
                
            elif char.isdigit():  # 숫자 입력
                buffer += char  # 버퍼에 숫자 추가
    
            else:  # 잘못된 입력
                print(f"잘못된 입력: '{char}', 숫자와 '+', 'a', 'b', 'c'만 입력하세요.")
                buffer = ""  # 버퍼 초기화
    
    except KeyboardInterrupt:
        print("사용자에 의해 중지됨.")
    finally:
        # 터미널 설정 복원 및 nRF24L01 종료
        # termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original_settings)
        nrf.powerDown()

def aliveCheck():
    try:
        while True:
            send_message('0000', is_negative=True)
            time.sleep(ALIVE_INTERVAL)

    except KeyboardInterrupt:
        print("사용자에 의해 중지됨.")
    finally:
        # 터미널 설정 복원 및 nRF24L01 종료
        # termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original_settings)
        nrf.powerDown()
    
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
        # 터미널 설정 복원 및 nRF24L01 종료
        # termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original_settings)
        nrf.powerDown()


#thread1 = threading.Thread(target=server, args=())
#thread1 = threading.Thread(target=keypad, args=())
#thread2 = threading.Thread(target=aliveCheck, args=())
#thread3 = threading.Thread(target=stressTest, args=())

#thread1.start()
#thread2.start()
#thread3.start()

#thread1.join()
#thread2.join()
#thread3.join()

threading.Thread(target=aliveCheck, daemon=True).start()
start_server_thread()
