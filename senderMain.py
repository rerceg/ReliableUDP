from ReliableUDP import ReliableUDP

RECEIVER_IP = "192.168.1.21"
RECEIVER_PORT = 5000


if __name__ == '__main__':
    f = open("IMG_20191225_171736_400.jpg", "rb")
    msg = f.read()
    f.close()
    reliable_udp = ReliableUDP(mss=10000, time_to_wait_for_connection=10)
    reliable_udp.connect((RECEIVER_IP, RECEIVER_PORT))
    reliable_udp.sendall(bytes("IMG_20191225_171736_400(1).jpg", 'utf8'))
    reliable_udp.sendall(msg)