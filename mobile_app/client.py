import socket
import time
import cv2
import numpy as np
import struct
from zeroconf import ServiceBrowser, Zeroconf


class ServiceListener:
    def __init__(self):
        self.server_info = None

    def remove_service(self, zeroconf, type, name):
        print(f"Service {name} removed")

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            print(f"Service {name} added, service info: {info}")
            self.server_info = info


def discover_server():
    zeroconf = Zeroconf()
    listener = ServiceListener()
    # browser must be kept in scope for discovery to work.
    browser = ServiceBrowser(zeroconf, "_documentscanner._tcp.local.",
                             listener)  # noqa: F841

    print("Searching for PC server on the network...")
    try:
        # Wait for up to 10 seconds to find the service
        for _ in range(20):
            if listener.server_info:
                return listener.server_info
            time.sleep(0.5)
    finally:
        zeroconf.close()
    return None


def run_client(server_info):
    host = socket.inet_ntoa(server_info.addresses[0])
    port = server_info.port

    print(f"Connecting to server at {host}:{port}")
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        client_socket.connect((host, port))
        print("Connected to server.")

        # Create a blank image to stream
        width, height = 640, 480
        blank_frame = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.putText(blank_frame, "Live feed from Mobile Client", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        while True:
            frame = blank_frame.copy()
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            cv2.putText(frame, timestamp, (10, 60),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

            result, encoded_frame = cv2.imencode(
                '.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            data = encoded_frame.tobytes()

            message_size = struct.pack(">L", len(data))
            client_socket.sendall(message_size)
            client_socket.sendall(data)

            print(f"Sent frame of size {len(data)} bytes")
            time.sleep(1/30)

    except (BrokenPipeError, ConnectionResetError):
        print("Connection to server lost.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        print("Closing socket.")
        client_socket.close()


if __name__ == '__main__':
    server_info = discover_server()
    if server_info:
        run_client(server_info)
    else:
        print("Could not find the PC Document Scanner server on the network.")
