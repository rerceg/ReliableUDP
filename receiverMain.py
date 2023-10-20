from ReliableUDP import ReliableUDP

LOCAL_IP = "192.168.1.21"
LOCAL_PORT = 5000


if __name__ == '__main__':
    reliable_udp = ReliableUDP(mss=5450, time_to_wait_for_connection=10)
    reliable_udp.bind((LOCAL_IP, LOCAL_PORT))
    reliable_udp.listen()
    conn, addr = reliable_udp.accept()
    name = conn.recvall()
    data = conn.recvall()
    f = open(name.decode('utf8'), "wb")
    f.write(data)
    f.close()