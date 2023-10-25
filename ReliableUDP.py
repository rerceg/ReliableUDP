import socket
import select
from random import randrange
import math
from threading import Timer

header_size = 11

class ReliableUDP:
    def __init__(self, n_of_segments_in_window=20, mss=1461, send_ack_after_n_segments_recv=4, time_to_wait_for_connection=20):
        self.lAddr = None
        self.rAddr = None
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._seq_num = randrange(4294967296)
        self._ack_num = None
        self._mss = min(mss, 65496)
        self._n_of_segments_in_window = n_of_segments_in_window
        self._window_size = min(n_of_segments_in_window*(self._mss + header_size), 65535)
        self._rWindow_size = 0
        self._congestion_window_factor = 4
        self._slow_start_treshold = n_of_segments_in_window
        self._max_congestion_window_factor = None
        self._buffer = bytes()
        self._temp_buffer = {}
        self._segments = []
        self._send_ack_timer = Timer(0.5, self._timer_says_send_ack)
        self._send_duplicate_ack_timer_flag = False
        self._send_duplicate_ack_timer = Timer(0.8, self._timer_says_send_ack)
        self._resend_segments_timer = Timer(1, self._timer_says_resend_segments)
        self.time_to_wait_for_connection = time_to_wait_for_connection
        self._resolving_timer_callback_flag = False
        self._ack_counter = 0
        self._next_segment = 0
        self._n_of_acked_segments = 0
        self._last_received_ack = -1
        self._expected_acks = []
        self.send_ack_after_n_segments_recv = send_ack_after_n_segments_recv
        self._connection_error_counter = 0


    def _timer_says_resend_segments(self):
        self._resolving_timer_callback_flag = True
        if self._connection_error_counter >= 10:
            return self._timer_says_connection_failed()
        print("timer opalio")
        self._next_segment = self._n_of_acked_segments
        self._congestion_window_factor = max(4, self._congestion_window_factor/2)
        self._slow_start_treshold = self._congestion_window_factor
        self._rWindow_size = self._congestion_window_factor * (self._mss + header_size)
        self._connection_error_counter += 1
        self._expected_acks = []
        self._send_next_window()
        self._resolving_timer_callback_flag = False

    def _timer_says_send_ack(self):
        self._resolving_timer_callback_flag = True
        print("timer odreagirao")
        self._check_temp_buffer()
        if self._ack_counter:
            self._window_size = min(self._n_of_segments_in_window * (self._mss + header_size), 65535)
        else:
            if self._connection_error_counter >= 10:
                return self._timer_says_connection_failed()
            self._window_size = (self._mss + header_size)
            self._connection_error_counter += 1

        self._increment_seq_num(1)
        ack_header = self._create_header(self._seq_num, self._ack_num, 16, self._window_size)
        self._ack_counter = 0
        print(f"sending ack:{self._ack_num}")
        self._sock.sendto(ack_header, self.rAddr)

        self._send_duplicate_ack_timer.cancel()
        self._send_duplicate_ack_timer_flag = True
        self._send_duplicate_ack_timer = Timer(0.8, self._timer_says_send_ack)
        self._send_duplicate_ack_timer.start()
        self._resolving_timer_callback_flag = False

    
    def _timer_says_connection_failed(self):
        self.close()
        raise Exception("Connection failed")
    
    def _mss_option(self):
        option_bytes_string = '{:08b}'.format(2) + '{:08b}'.format(4) + '{:016b}'.format(self._mss)
        return option_bytes_string

    def _parse_header(self, data):
        seq_num = int.from_bytes(data[:4], byteorder='big')
        ack_num = int.from_bytes(data[4:8], byteorder='big')
        options_len_and_flags = '{:08b}'.format(data[8])
        options_len = int(options_len_and_flags[:3], 2)
        flags = options_len_and_flags[3:]
        window_size = int.from_bytes(data[9:11], byteorder='big')
        options = data[11:(11 + (options_len)*4)] if options_len > 0 else None
        return [seq_num, ack_num, flags, window_size, options]

    def _increment_seq_num(self, segment_size):
        new_seq_num = self._seq_num + segment_size
        if new_seq_num > 4294967295:
            self._seq_num = new_seq_num - 4294967296
        else:
            self._seq_num = new_seq_num

    def _set_ack_num(self, new_ack_num):
        if new_ack_num > 4294967295:
            self._ack_num = new_ack_num - 4294967296
        else:
            self._ack_num = new_ack_num

    def _second_shake_confirmation(self, data, addr):
        if addr != self.rAddr:
            return False
        seq_num, ack_num, flags, window_size, options = self._parse_header(data)
        if options:
            if int.from_bytes(options[0:1], byteorder='big') == 2:
                length = int.from_bytes(options[1:2], byteorder='big')
                receiver_mss = int.from_bytes(options[2:4], byteorder='big')
                self._mss = min(self._mss, receiver_mss)
                self._max_congestion_window_factor = round(65535/self._mss)
            else:
                return False
        else:
            return False
        if flags[0] == '0':
            return False
        if flags[3] == '0':
            return False
        if ack_num != (self._seq_num + 1):
            return False
        self._rWindow_size = window_size
        self._set_ack_num(seq_num + 1)
        return True

    
    def _first_shake_confirmation(self, data, addr):
        self.rAddr = addr
        seq_num, ack_num, flags, window_size, options = self._parse_header(data)
        if options:
            if int.from_bytes(options[0:1], byteorder='big') == 2:
                length = int.from_bytes(options[1:2], byteorder='big')
                sender_mss = int.from_bytes(options[2:4], byteorder='big')
                self._mss = min(self._mss, sender_mss)
                self._window_size = min(self._n_of_segments_in_window * (self._mss + header_size), 65535)
                self._max_congestion_window_factor = round(65535/self._mss)
            else:
                return False
        else:
            return False
        if flags[3] == '0':
            return False
        self._rWindow_size = window_size
        self._set_ack_num(seq_num + 1)
        return True
    
    def _third_shake_confirmation(self, data, addr):
        if addr != self.rAddr:
            return False
        _, ack_num, flags, _, _ = self._parse_header(data)
        if flags[0] == '0':
            return False
        if ack_num != (self._seq_num + 1):
            return False
        return True
        
    def _unpack_data(self, data):
        seq_num, ack_num, flags, window_size, options = self._parse_header(data)
        self._rWindow_size = window_size
        options_len = 0 if not options else len(options)
        payload = data[(11 + (options_len)*4):]
        return [seq_num, ack_num, flags, options, payload]
    
    def bind(self, localAddress):
        self.lAddr = localAddress
        self._sock.bind(localAddress)

    def listen(self):
        print(f"Listening on port {self.lAddr[1]}")

    def connect(self, rAddr):
        self.rAddr = rAddr
        connection_failed_timer = Timer(self.time_to_wait_for_connection, self._timer_says_connection_failed)
        header = self._create_header(self._seq_num, 0, 2, self._window_size, self._mss_option())
        print("1st shake initialization")
        self._sock.sendto(header, rAddr)
        connection_failed_timer.start()
        data, addr = self._sock.recvfrom(15)
        connection_failed_timer.cancel()
        print("2nd shake recived")
        if self._second_shake_confirmation(data, addr):
            self._increment_seq_num(1)
            header = self._create_header(self._seq_num, self._ack_num, 16, self._window_size)
            print("3rd shake initialization")
            self._sock.sendto(header, self.rAddr)
            print("connected")
        else:
            print("Connection failed")


    def accept(self):
        connection_failed_timer = Timer(self.time_to_wait_for_connection, self._timer_says_connection_failed)
        connection_failed_timer.start()
        data, addr = self._sock.recvfrom(15)
        connection_failed_timer.cancel()
        print("1st shake recived")
        if self._first_shake_confirmation(data, addr):
            header = self._create_header(self._seq_num, self._ack_num, 18, self._window_size, self._mss_option())
            print("2nd shake initialization")
            self._sock.sendto(header, self.rAddr)
            connection_failed_timer = Timer(self.time_to_wait_for_connection, self._timer_says_connection_failed)
            connection_failed_timer.start()
            data, addr = self._sock.recvfrom(11)
            connection_failed_timer.cancel()
            print("3rd shake recived")
            if self._third_shake_confirmation(data, addr):
                print("connected")
                self._increment_seq_num(1)
                return (self, self.rAddr)
            else:
                print("Connection failed")
                return (self, None)
        else:
            print("Connection failed")
            return (self, None)

    def _convert_data_to_segments(self, data):
        size = len(data)
        n_of_segments = math.ceil(size / self._mss)
        self._segments = []
        for i in range(n_of_segments):
            curr_segment_size = self._mss if size >= self._mss else size
            size -= self._mss
            flags = 8 if i == (n_of_segments - 1) else 0
            curr_header = self._create_header(self._seq_num, 0, flags, self._window_size)
            segment_w_h = curr_header + data[i*self._mss:(i*self._mss) + curr_segment_size]
            self._segments.append((segment_w_h, self._seq_num))
            self._increment_seq_num(curr_segment_size)

    def _send_next_window(self):
        self._resend_segments_timer.cancel()
        self._resend_segments_timer = Timer(1, self._timer_says_resend_segments)
        while self._next_segment <= (len(self._segments) - 1) and (self._rWindow_size >= len(self._segments[self._next_segment][0])):
            self._rWindow_size -= len(self._segments[self._next_segment][0])
            self._sock.sendto(self._segments[self._next_segment][0], self.rAddr)
            self._next_segment += 1
            if self._last_received_ack != ((self._segments[self._next_segment - 1][1] + len(self._segments[self._next_segment - 1][0]) - header_size) % 4294967296):
                if self._next_segment < (len(self._segments) - 1):
                    self._expected_acks.append(self._segments[self._next_segment][1])
                elif self._next_segment == (len(self._segments) - 1):
                    self._expected_acks.append((self._segments[self._next_segment][1] + len(self._segments[self._next_segment][0]) - header_size) % 4294967296)
                elif len(self._segments) == 1:
                    self._expected_acks.append((self._segments[0][1] + len(self._segments[0][0]) - header_size) % 4294967296)
        self._resend_segments_timer.start()


    def _wait_for_ack(self):
        reader, _, _ = select.select([self._sock], [], [])
        if self._resolving_timer_callback_flag:
            return False
        data, addr = self._sock.recvfrom(self._mss + header_size)
        if addr != self.rAddr:
            return False
        self._resend_segments_timer.cancel()
        self._resend_segments_timer = Timer(1, self._timer_says_resend_segments)
        seq_num, rAck_num, _, _, _ = self._unpack_data(data)
        if self._last_received_ack == rAck_num:
            print(f"received double ack: {rAck_num}")
            self._next_segment = self._n_of_acked_segments
            self._congestion_window_factor = max(4, self._congestion_window_factor/2)
            self._slow_start_treshold = self._congestion_window_factor
            self._connection_error_counter = 0
        else:
            try:
                i = self._expected_acks.index(rAck_num)
                if self._last_received_ack > rAck_num:
                    self._last_received_ack -= 4294967296
                n_of_acked_segments_incr = round((rAck_num - self._last_received_ack)/self._mss)
                self._n_of_acked_segments += n_of_acked_segments_incr
                self._last_received_ack = rAck_num
                if rAck_num == self._seq_num:
                    self._set_ack_num(seq_num)
                    return True
                self._expected_acks = self._expected_acks[(i+1):]
                self._connection_error_counter = 0
                if self._congestion_window_factor < self._max_congestion_window_factor:
                    if self._congestion_window_factor > self._slow_start_treshold:
                        self._congestion_window_factor += 1
                    else:
                        self._congestion_window_factor += n_of_acked_segments_incr
            except:
                pass
        self._rWindow_size = min(self._rWindow_size, self._congestion_window_factor*(self._mss + header_size))

        return False

    def sendall(self, data):
        self._last_received_ack = self._seq_num
        self._convert_data_to_segments(data)
        self._next_segment = 0
        self._n_of_acked_segments = 0
        self._expected_acks = []
        self._connection_error_counter = 0
        self._congestion_window_factor = 4
        self._slow_start_treshold = self._n_of_segments_in_window
        self._rWindow_size = min(self._rWindow_size, self._congestion_window_factor*(self._mss + header_size))
        while True:
            if self._next_segment <= (len(self._segments) - 1) and (self._rWindow_size >= len(self._segments[self._next_segment][0])):
                self._send_next_window()
            if self._wait_for_ack():
                return


    def _handle_last_segment_recv(self, payload, seq_num):
        self._send_duplicate_ack_timer_flag = False
        self._send_ack_timer.cancel()
        self._send_duplicate_ack_timer.cancel()
        self._increment_seq_num(1)
        self._buffer += payload
        last_ack = seq_num + len(payload)
        if last_ack > 4294967295:
            last_ack -= 4294967296
        ack_header = self._create_header(self._seq_num, last_ack, 16, self._window_size)
        self._sock.sendto(ack_header, self.rAddr)
        self._set_ack_num(last_ack)
        print("last ack sent")
        return self._buffer


    def _handle_sending_ack(self):
        self._send_duplicate_ack_timer_flag = False
        self._send_duplicate_ack_timer.cancel()
        self._send_duplicate_ack_timer = Timer(0.8, self._timer_says_send_ack)        
        self._window_size = min(self._ack_counter * (self._mss + header_size), 65535)
        self._increment_seq_num(1)
        ack_header = self._create_header(self._seq_num, self._ack_num, 16, self._window_size)
        self._ack_counter = 0
        self._sock.sendto(ack_header, self.rAddr)
        self._send_duplicate_ack_timer_flag = True
        self._send_duplicate_ack_timer.start()

    def recvall(self):
        self._buffer = bytes()
        self._temp_buffer = {}
        last_seq = -1
        last_segment = None
        self._connection_error_counter = 0
        self._send_duplicate_ack_timer_flag = True
        self._send_duplicate_ack_timer = Timer(2, self._timer_says_send_ack)
        self._send_duplicate_ack_timer.start()
        while True:
            readers, _, _ = select.select([self._sock], [], [])
            if self._resolving_timer_callback_flag:
                continue
            
            data, addr = self._sock.recvfrom(self._mss + header_size)
            
            if addr != self.rAddr:
                continue

            self._send_ack_timer.cancel()
            self._connection_error_counter = 0
            seq_num, _, flags, _, payload = self._unpack_data(data)
            if flags[1] == '1' and seq_num == self._ack_num:
                return self._handle_last_segment_recv(payload, seq_num)
            elif flags[1] == '1' and seq_num != self._ack_num:
                last_seq = seq_num
                last_segment = payload
            else:
                if seq_num == self._ack_num:
                    self._send_duplicate_ack_timer_flag = False
                    self._send_duplicate_ack_timer.cancel()
                    
                    self._buffer += payload
                    self._set_ack_num(seq_num + len(payload))
                    self._ack_counter += 1
                else:
                    if not self._send_duplicate_ack_timer_flag and self._ack_counter == 0:
                        self._send_duplicate_ack_timer = Timer(0.8, self._timer_says_send_ack)
                        self._send_duplicate_ack_timer_flag = True
                        self._send_duplicate_ack_timer.start()
                    self._temp_buffer[seq_num] = [payload, 1]
                
                self._check_temp_buffer()
                if self._ack_num == last_seq:
                        return self._handle_last_segment_recv(last_segment, last_seq)

            if self._ack_counter < self.send_ack_after_n_segments_recv and self._ack_counter > 0:
                self._send_ack_timer = Timer(0.5, self._timer_says_send_ack)
                self._send_ack_timer.start()
            elif self._ack_counter >= self.send_ack_after_n_segments_recv:
                self._handle_sending_ack()


    def _check_temp_buffer(self):
        flag = self._ack_num in self._temp_buffer.keys()
        if flag:
            self._send_duplicate_ack_timer_flag = False
            self._send_duplicate_ack_timer.cancel()
        if flag or len(self._temp_buffer) == 24:
            sorted_seq_nums = sorted(list(self._temp_buffer.keys()))
            skip_flag = False
            curr_seq_num = sorted_seq_nums[0]
            next_index = 1 % len(sorted_seq_nums)
            for i in range(len(sorted_seq_nums)):
                if skip_flag:
                    skip_flag = False
                    continue
                if ((curr_seq_num + len(self._temp_buffer[curr_seq_num][0])) % 4294967296 == sorted_seq_nums[next_index]) and sorted_seq_nums[next_index] != self._ack_num:
                    skip_flag = True
                    to_append = self._temp_buffer.pop(sorted_seq_nums[next_index])
                    self._temp_buffer[curr_seq_num][0] += to_append[0]
                    self._temp_buffer[curr_seq_num][1] += to_append[1]
                else:
                    curr_seq_num = sorted_seq_nums[next_index]
                
                next_index = (next_index + 1) % len(sorted_seq_nums)
            if flag:
                segments_to_append, n_of_segments_to_append = self._temp_buffer.pop(self._ack_num)
                self._ack_counter += n_of_segments_to_append
                self._set_ack_num(self._ack_num + len(segments_to_append))
                self._buffer += segments_to_append
        if len(self._temp_buffer) > 24:
            self._temp_buffer.clear()
            

    def close(self):
        self._sock.close()

    def _create_header(self, seq_num, ack_num, flags, window_size, options=0):
        options_len = 0 if options == 0 else int(len(options)/32)
        atributes = '{:032b}'.format(seq_num) + '{:032b}'.format(ack_num) + '{:03b}'.format(options_len) + '{:05b}'.format(flags) + '{:016b}'.format(window_size)
        if options != 0:
            atributes += options
        atributes_in_bytes = []
        for i in range(round(len(atributes)/8)):
            atributes_in_bytes.append(int(atributes[(i*8) : (i*8) + 8], 2))
        
        return bytes(atributes_in_bytes)

    def __del__(self):
        self._sock.close()
