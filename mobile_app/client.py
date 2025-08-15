import socket
import time
import cv2
import numpy as np
import struct

# Create a TCP socket
client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# Connect the socket to the server's address and port
server_address = ('127.0.0.1', 8000)
print(f'Connecting to {server_address[0]}:{server_address[1]}')
client_socket.connect(server_address)
print('Connected to server.')

# Create a blank image
width, height = 640, 480
blank_frame = np.zeros((height, width, 3), dtype=np.uint8)
cv2.putText(blank_frame, "Streaming from client", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

try:
    while True:
        # Create a blank frame
        frame = blank_frame.copy()
        # add a timestamp
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

        # Encode the frame as JPEG
        result, frame = cv2.imencode('.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        data = frame.tobytes()

        # Pack the message size and send it
        message_size = struct.pack(">L", len(data))
        client_socket.sendall(message_size)

        # Send the actual frame data
        client_socket.sendall(data)

        print(f"Sent frame of size {len(data)} bytes")
        time.sleep(1/30) # 30 fps

except (BrokenPipeError, ConnectionResetError):
    print("Connection to server lost.")

finally:
    print("Closing socket.")
    client_socket.close()
