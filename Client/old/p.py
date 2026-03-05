import time
import spidev
#from RF24 import RF24, RF24_PA_HIGH, RF24_1MBPS
from RF24 import RF24, RF24_PA_HIGH, RF24_250KBPS
import sys
import termios
import tty
import threading

# 2025-04-22 : change signal strength MAX -> HIGH
#              change channel 75 -> 76

# SPI 설정
spi = spidev.SpiDev()
try:
    spi.open(0, 0)
    spi.max_speed_hz = 2000000  # 2MHz 설정 (안정성 확보)
    spi.close()
    print("SPI 장치 접근 성공: /dev/spidev0.0")
except IOError as e:
    print(f"SPI 장치 열기 실패: {e}")
    raise SystemExit("SPI 설정을 확인하세요")

# nRF24L01 설정
nrf = RF24(24, 0)  # CE: GPIO 24, CSN: SPI 0
###################################################################
#    ADDRESS                                                      #
pipe = b"\xe6\xf0\xf0\xf0\xf0"
###################################################################

print("nRF24L01 초기화 시도...")
if not nrf.begin():
    print("초기화 실패: nRF24L01 모듈이 응답하지 않습니다.")
    raise RuntimeError("nRF24L01 하드웨어 초기화 실패!")

nrf.setPALevel(RF24_PA_HIGH)
#nrf.setDataRate(RF24_1MBPS)
nrf.setDataRate(RF24_250KBPS)
nrf.setChannel(94)
#nrf.setChannel(80)  4/27/2025 # RF 채널을 76으로 설정 (0~125 사이 값, 기본값은 76)
nrf.enableDynamicPayloads()
nrf.setAutoAck(True)  # 자동 응답 활성화
nrf.setRetries(10, 15)  # 재시도 설정 (최대 15번, 5ms 간격)
nrf.openWritingPipe(pipe)
nrf.stopListening()

print("nRF24L01 설정 완료.")
nrf.printDetails()

STORE_NUMBER = "001"  # 3자리 스토어 넘버 (기본값 001, 필요시 변경 가능)

def send_message(number, is_negative):
    """ 메시지를 전송하는 함수 """
    formatted_number = str(number)
    if is_negative:
        data_to_send = f"{STORE_NUMBER},-,{formatted_number}"
    else:
        data_to_send = f"{STORE_NUMBER},+,{formatted_number}"
    data = data_to_send.encode('utf-8')
    if nrf.write(data):
        print(f"전송 성공: {data_to_send}")
    else:
        print(f"전송 실패: {data_to_send}")
        nrf.printDetails()  # 실패 시 상태 출력

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
                        if 1 <= number <= 99999:
                            send_message(number, is_negative=False)  # "+" 형식으로 전송
                        else:
                            print(f"입력 범위 오류: {number}, 1에서 99999까지 입력하세요.")
                    except ValueError:
                        print("잘못된 숫자 형식입니다.")
                    buffer = ""  # 버퍼 초기화
                else:
                    print("빈 메시지는 전송되지 않습니다.")
    
            elif char in ('+', 'a', 'b', 'c'):  # +, a, b, c 키
                if buffer:
                    try:
                        number = int(buffer)
                        if 1 <= number <= 99999:
                            send_message(number, is_negative=True)  # "-" 형식으로 즉시 전송
                        else:
                            print(f"입력 범위 오류: {number}, 1에서 99999까지 입력하세요.")
                    except ValueError:
                        print("잘못된 숫자 형식입니다.")
                    buffer = ""  # 버퍼 초기화
                else:
                    print("빈 메시지는 전송되지 않습니다.")
    
            elif char.isdigit():  # 숫자 입력
                buffer += char  # 버퍼에 숫자 추가
    
            else:  # 잘못된 입력
                print(f"잘못된 입력: '{char}', 숫자와 '+', 'a', 'b', 'c'만 입력하세요.")
                buffer = ""  # 버퍼 초기화
    
    except KeyboardInterrupt:
        print("사용자에 의해 중지됨.")
    finally:
        # 터미널 설정 복원 및 nRF24L01 종료
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original_settings)
        nrf.powerDown()

def aliveCheck():
    try:
        while True:
            send_message('0000', is_negative=True)
            time.sleep(10)

    except KeyboardInterrupt:
        print("사용자에 의해 중지됨.")
    finally:
        # 터미널 설정 복원 및 nRF24L01 종료
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, original_settings)
        nrf.powerDown()
    
thread1 = threading.Thread(target=keypad, args=())
thread2 = threading.Thread(target=aliveCheck, args=())

thread1.start()
thread2.start()

thread1.join()
thread2.join()


