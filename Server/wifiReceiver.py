import socket
import datetime
import os

serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
serversocket.bind(('0.0.0.0', 8089))
serversocket.listen(5) # become a server socket, maximum 5 connections



# Log File Setup
def setup_log_file():
    cur_date = datetime.date.today()
#    log_dir = "./log"
    log_dir = "/home/pi/log"
    os.makedirs(log_dir, exist_ok=True) # Create log directory
    log_file = os.path.join(log_dir, f"{cur_date}.log")
    #rcv_log_file = os.path.join(log_dir, f"rcv_{cur_date}.log")
    rcv_log_file = os.path.join(log_dir, f"{cur_date}.log")
    return log_file, rcv_log_file

if __name__ == '__main__':

    log_file, rcv_log_file = setup_log_file()
    print("Starting to receive data...")

    while True:
        while True:
            connection, address = serversocket.accept()
            message = connection.recv(64)
            if len(message) > 0:
                print (f"Received: {message}")
                print (type(message))
                d_msg = message.decode("utf-8")
                arr = d_msg.split(',')
                print(arr)
                if len(arr) != 3:
                    print("Invalid message format")
                    continue

                now = datetime.datetime.now()
                ts = now.strftime("%H:%M:%S")
                with open(rcv_log_file, "a") as file:
                    file.write(ts +"|"+ d_msg + "\n")

                
                if arr[1] == '+':
                    message = f"{arr[0]},-,{arr[2]}\n{d_msg}"
                elif arr[1] == '-':
                    message = d_msg
                with open(log_file, "a") as file:
                    file.write(message + "\n")
                
                connection.close()
                break

