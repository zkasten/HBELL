import socket

clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

SERVER_IP = "10.142.36.127"
#clientsocket.connect((SERVER_IP, 8089))
clientsocket.connect(('10.142.36.127', 8089))
#clientsocket.send(b'hello')
clientsocket.send(b'001,+,123')
clientsocket.shutdown(socket.SHUT_RDWR)
clientsocket.close()

clientsocket.connect(('10.142.36.127', 8089))
clientsocket.send(b'001,+,456')
clientsocket.shutdown(socket.SHUT_RDWR)
clientsocket.close()


