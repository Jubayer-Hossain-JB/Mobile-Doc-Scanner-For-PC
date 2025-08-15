import sys
import os
import cv2
import numpy as np
import time
import socket
import struct
from zeroconf import ServiceInfo, Zeroconf
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QSizePolicy,
                             QStackedWidget)
from PyQt5.QtCore import (Qt, QTimer, QPropertyAnimation, pyqtProperty,
                          QThread, pyqtSignal)
from PyQt5.QtGui import QImage, QPixmap, QColor


# --- Networking Server Thread ---
class ServerThread(QThread):
    client_connected = pyqtSignal(str)
    client_disconnected = pyqtSignal()
    frame_received = pyqtSignal(bytes)

    def __init__(self, port=8000):
        super().__init__()
        self.port = port
        self.running = True

    def run(self):
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.bind(('0.0.0.0', self.port))
        server_socket.listen(1)

        while self.running:
            print(f"Server listening on port {self.port}...")
            try:
                conn, addr = server_socket.accept()
                self.client_connected.emit(str(addr))

                payload_size_struct = struct.Struct('>L')
                data = b''

                while self.running:
                    while len(data) < payload_size_struct.size:
                        packet = conn.recv(4096)
                        if not packet:
                            break
                        data += packet
                    if not data:
                        break

                    packed_msg_size = data[:payload_size_struct.size]
                    data = data[payload_size_struct.size:]
                    msg_size = payload_size_struct.unpack(packed_msg_size)[0]

                    while len(data) < msg_size:
                        data += conn.recv(4096)

                    frame_data = data[:msg_size]
                    data = data[msg_size:]
                    self.frame_received.emit(frame_data)

                conn.close()
                self.client_disconnected.emit()
            except Exception as e:
                print(f"Server error: {e}")
                self.client_disconnected.emit()

        server_socket.close()
        print("Server thread stopped.")

    def stop(self):
        self.running = False
        # To unblock the accept() call
        try:
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(
                ('127.0.0.1', self.port))
        except Exception:
            pass


# --- Frame Processor ---
class FrameProcessor:
    def process_frame_data(self, frame_data):
        if frame_data:
            frame = cv2.imdecode(np.frombuffer(frame_data,
                                               dtype=np.uint8),
                                 cv2.IMREAD_COLOR)
            return frame
        return None


# --- Animated Button ---
class AnimatedButton(QPushButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor(0, 0, 0)
        self.animation = QPropertyAnimation(self, b"color")
        self.animation.setDuration(200)

    @pyqtProperty(QColor)
    def color(self):
        return self._color

    @color.setter
    def color(self, color):
        self._color = color
        self.update_style()

    def set_colors(self, base_color, hover_color):
        self.base_color = base_color
        self.hover_color = hover_color
        self.color = self.base_color

    def update_style(self):
        style = f"""
            background-color: {self._color.name()};
            color: white;
            border: none;
            padding: 15px 30px;
            font-size: 18px;
            border-radius: 10px;
            margin-bottom: 10px;
            outline: none;
        """
        self.setStyleSheet(style)

    def enterEvent(self, event):
        self.animation.setEndValue(self.hover_color)
        self.animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animation.setEndValue(self.base_color)
        self.animation.start()
        super().leaveEvent(event)


# --- Custom GUI Components ---
class CustomTitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(0, 0, 5, 0)
        self.layout.setSpacing(10)
        self.title = QLabel("Document Scanner")
        self.title.setAlignment(Qt.AlignCenter)
        self.title.setStyleSheet(
            "color: #ecf0f1; font-size: 16px; font-weight: bold;")
        self.layout.addStretch()
        self.layout.addWidget(self.title)
        self.layout.addStretch()
        self.btn_min = QPushButton("-")
        self.btn_close = QPushButton("×")
        self.btn_min.setFixedSize(26, 26)
        self.btn_close.setFixedSize(26, 26)
        buttons = [(self.btn_min, '#f1c40f'), (self.btn_close, '#e74c3c')]
        for btn, bg_color in buttons:
            darker_color = QColor(bg_color).darker(120).name()
            btn.setStyleSheet(
                f"""QPushButton {{
                    background-color: {bg_color};
                    color: white; border: none;
                    border-radius: 13px;
                    font-weight: bold;
                    font-size: 14px;
                    }}
                    QPushButton:hover {{
                    background-color: {darker_color};
                    }}""")
        self.layout.addWidget(self.btn_min)
        self.layout.addWidget(self.btn_close)
        self.setLayout(self.layout)
        self.btn_close.clicked.connect(self.parent.close)
        self.btn_min.clicked.connect(self.parent.showMinimized)
        self.start_move_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_move_pos = event.globalPos()

    def mouseMoveEvent(self, event):
        if self.start_move_pos:
            delta = event.globalPos() - self.start_move_pos
            self.parent.move(self.parent.pos() + delta)
            self.start_move_pos = event.globalPos()

    def mouseReleaseEvent(self, event):
        self.start_move_pos = None


# --- Main Application Window ---
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMinimumSize(800, 600)
        self.current_frame = None
        self.processor = FrameProcessor()

        # Main container
        self.container = QWidget()
        self.container.setObjectName("container")
        self.setCentralWidget(self.container)
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(1, 1, 1, 1)
        self.container.setLayout(self.container_layout)

        # Custom Title Bar
        self.title_bar = CustomTitleBar(self)
        self.container_layout.addWidget(self.title_bar)

        # Main Content Area using QStackedWidget for different states
        self.stacked_widget = QStackedWidget()
        self.container_layout.addWidget(self.stacked_widget)

        # "Searching/Listening" State Widget
        self.searching_widget = QWidget()
        self.searching_layout = QVBoxLayout(self.searching_widget)
        self.searching_label = QLabel("Listening for connection...")
        self.searching_label.setAlignment(Qt.AlignCenter)
        self.searching_label.setStyleSheet(
            "font-size: 24px; color: #ecf0f1;")
        self.searching_layout.addWidget(self.searching_label)
        self.stacked_widget.addWidget(self.searching_widget)

        # "Connected" State Widget (Video Feed)
        self.video_widget = QWidget()
        self.video_widget.setStyleSheet("background-color: transparent;")
        self.video_layout = QVBoxLayout(self.video_widget)
        self.video_feed = QLabel("Waiting for video feed...")
        self.video_feed.setObjectName("videoFeed")
        self.video_feed.setAlignment(Qt.AlignCenter)
        self.video_feed.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.video_layout.addWidget(self.video_feed)
        self.capture_button = AnimatedButton("Capture")
        self.capture_button.set_colors(QColor("#3498db"), QColor("#2980b9"))
        self.capture_button.clicked.connect(self.capture_frame)
        self.video_layout.addWidget(self.capture_button, 0, Qt.AlignCenter)
        self.stacked_widget.addWidget(self.video_widget)

        self.setStyleSheet("""
            #container { background-color: #2c3e50; border-radius: 15px; }
            CustomTitleBar, #searching_widget { background-color: transparent; }
            #videoFeed {
                background-color: black;
                border-radius: 10px;
                margin: 10px;
            }
        """)

        # Networking Setup
        self.server_thread = ServerThread()
        self.server_thread.client_connected.connect(self.on_client_connected)
        on_disconnect = self.on_client_disconnected
        self.server_thread.client_disconnected.connect(on_disconnect)
        self.server_thread.frame_received.connect(self.on_frame_received)
        self.server_thread.start()

        # Zeroconf Setup
        self.zeroconf = Zeroconf()
        self.register_service()

    def register_service(self):
        service_type = "_documentscanner._tcp.local."
        service_name = "PC Document Scanner." + service_type
        try:
            # Get local IP address
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()

            info = ServiceInfo(
                service_type,
                service_name,
                addresses=[socket.inet_aton(ip_address)],
                port=self.server_thread.port,
                properties={'app': 'DocScanner'},
            )
            print(f"Registering service '{service_name}' on "
                  f"{ip_address}:{self.server_thread.port}")
            self.zeroconf.register_service(info)
        except Exception as e:
            print(f"Error registering service: {e}")
            self.searching_label.setText(
                "Error: Could not register service on network.")

    def on_client_connected(self, client_address):
        print(f"Client connected: {client_address}")
        self.title_bar.title.setText(f"Connected to {client_address}")
        self.stacked_widget.setCurrentWidget(self.video_widget)

    def on_client_disconnected(self):
        print("Client disconnected.")
        self.title_bar.title.setText("Document Scanner")
        self.video_feed.setText(
            "Connection lost. Listening for new connection...")
        self.stacked_widget.setCurrentWidget(self.searching_widget)
        self.searching_label.setText(
            "Connection lost. Listening for new connection...")

    def on_frame_received(self, frame_data):
        processed_frame = self.processor.process_frame_data(frame_data)
        if processed_frame is not None:
            self.current_frame = processed_frame
            h, w, ch = processed_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(processed_frame.data, w, h, bytes_per_line,
                              QImage.Format_RGB888).rgbSwapped()
            pixmap = QPixmap.fromImage(qt_image)
            self.video_feed.setPixmap(pixmap)

    def capture_frame(self):
        if self.current_frame is not None:
            save_dir = "doc_scanned"
            if not os.path.exists(save_dir):
                os.makedirs(save_dir)
            filename = f"scan_{time.strftime('%Y%m%d_%H%M%S')}.jpg"
            filepath = os.path.join(save_dir, filename)
            success = cv2.imwrite(filepath, self.current_frame)
            if success:
                self.title_bar.title.setText(f"Saved to {filepath}")
                QTimer.singleShot(
                    3000,
                    lambda: self.title_bar.title.setText("Document Scanner"))
            else:
                self.title_bar.title.setText("Error: Could not save frame!")
                QTimer.singleShot(
                    3000,
                    lambda: self.title_bar.title.setText("Document Scanner"))

    def closeEvent(self, event):
        print("Closing application...")
        self.zeroconf.close()
        self.server_thread.stop()
        self.server_thread.wait()
        event.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
