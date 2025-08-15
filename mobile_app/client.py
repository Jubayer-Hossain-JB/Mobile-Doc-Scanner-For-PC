import socket
import time
import cv2
import numpy as np
import struct
import threading
from zeroconf import ServiceBrowser, Zeroconf
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.camera import Camera
from kivy.clock import Clock


class ServiceListener:
    def __init__(self, app):
        self.app = app
        self.server_info = None

    def remove_service(self, zeroconf, type, name):
        status = f"Lost PC: {name}"
        Clock.schedule_once(lambda dt: self.app.update_status(status))
        self.server_info = None

    def add_service(self, zeroconf, type, name):
        info = zeroconf.get_service_info(type, name)
        if info:
            self.server_info = info
            Clock.schedule_once(lambda dt: self.app.found_server(info))


class ScannerLayout(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'vertical'

        self.camera = Camera(play=True, resolution=(640, 480))
        self.add_widget(self.camera)

        self.status_label = Label(text="Searching for PC...", size_hint_y=0.1)
        self.add_widget(self.status_label)

        self.stream_button = Button(text="Start Streaming", size_hint_y=0.1)
        self.stream_button.bind(on_press=self.toggle_streaming)
        self.add_widget(self.stream_button)

        self.streaming = False
        self.server_info = None
        self.network_thread = None

    def update_status_from_main(self, message):
        self.status_label.text = message

    def found_server_from_main(self, info):
        self.server_info = info
        host = socket.inet_ntoa(info.addresses[0])
        port = info.port
        self.status_label.text = f"Found PC at {host}:{port}"

    def toggle_streaming(self, instance):
        if self.streaming:
            self.stop_streaming()
        else:
            if self.server_info:
                self.start_streaming()

    def start_streaming(self):
        self.streaming = True
        self.stream_button.text = "Stop Streaming"
        self.network_thread = threading.Thread(target=self.stream_video)
        self.network_thread.daemon = True
        self.network_thread.start()

    def stop_streaming(self):
        self.streaming = False
        self.stream_button.text = "Start Streaming"
        # The thread will stop on its own when the socket closes

    def stream_video(self):
        host = socket.inet_ntoa(self.server_info.addresses[0])
        port = self.server_info.port
        status = f"Connecting to {host}:{port}"
        Clock.schedule_once(lambda dt: self.update_status_from_main(status))

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            client_socket.connect((host, port))
            status = "Connected. Streaming..."
            Clock.schedule_once(lambda dt: self.update_status_from_main(status))

            while self.streaming:
                # Kivy camera texture is not thread-safe.
                # For this PoC, we generate a blank frame instead of
                # implementing a complex texture-passing queue.
                width, height = 640, 480
                frame = np.zeros((height, width, 3), dtype=np.uint8)
                cv2.putText(frame, "Live from Kivy App", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                timestamp = time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
                cv2.putText(frame, timestamp, (10, 60),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

                result, enc_frame = cv2.imencode(
                    '.jpg', frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
                data = enc_frame.tobytes()

                message_size = struct.pack(">L", len(data))
                client_socket.sendall(message_size)
                client_socket.sendall(data)
                time.sleep(1/30)

        except Exception as e:
            status = f"Error: {e}"
            Clock.schedule_once(lambda dt: self.update_status_from_main(status))
        finally:
            client_socket.close()
            self.streaming = False
            status = "Disconnected."
            Clock.schedule_once(lambda dt: self.update_status_from_main(status))
            Clock.schedule_once(
                lambda dt: setattr(self.stream_button, 'text',
                                   "Start Streaming"))


class MobileScannerApp(App):
    def build(self):
        self.layout = ScannerLayout()
        return self.layout

    def on_start(self):
        self.zeroconf = Zeroconf()
        self.listener = ServiceListener(self)
        self.browser = ServiceBrowser(
            self.zeroconf, "_documentscanner._tcp.local.", self.listener)

    def on_stop(self):
        self.zeroconf.close()
        if self.layout.network_thread and self.layout.network_thread.is_alive():
            self.layout.stop_streaming()

    def update_status(self, message):
        self.layout.update_status_from_main(message)

    def found_server(self, info):
        self.layout.found_server_from_main(info)


if __name__ == '__main__':
    MobileScannerApp().run()
