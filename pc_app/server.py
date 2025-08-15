import socket
import struct
import cv2
import numpy as np

# Create a TCP socket
server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Bind the socket to a public host and a port
server_address = ('0.0.0.0', 8000)
print(f'Starting up on {server_address[0]}:{server_address[1]}', flush=True)
server_socket.bind(server_address)

# Listen for incoming connections
server_socket.listen(1)

# Wait for a connection
print('Waiting for a connection...', flush=True)
connection, client_address = server_socket.accept()
print(f'Connection from {client_address}', flush=True)

# Struct to unpack the message size
payload_size_struct = struct.Struct('>L')
data = b''

try:
    while True:
        # Retrieve message size
        while len(data) < payload_size_struct.size:
            packet = connection.recv(4096)
            if not packet:
                break
            data += packet

        if not data:
            break

        packed_msg_size = data[:payload_size_struct.size]
        data = data[payload_size_struct.size:]
        msg_size = payload_size_struct.unpack(packed_msg_size)[0]

        # Retrieve all data based on message size
        while len(data) < msg_size:
            data += connection.recv(4096)

        frame_data = data[:msg_size]
        data = data[msg_size:]

        # Decode frame
        frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)

        if frame is not None:
            print(f"Received frame of size {len(frame_data)} bytes", flush=True)
            # In a real app, you would display the frame here
            # cv2.imshow('Video', frame)
            # if cv2.waitKey(1) & 0xFF == ord('q'):
            #     break
        else:
            print("Could not decode frame", flush=True)

finally:
    print("Closing connection.", flush=True)
    connection.close()
    server_socket.close()
    # cv2.destroyAllWindows()
