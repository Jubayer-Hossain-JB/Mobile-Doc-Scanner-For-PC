import sys
import os
import cv2
import numpy as np
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QSizePolicy)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QImage, QPixmap


# --- Frame Simulation Logic (from previous step) ---

class FrameSimulator:
    def __init__(self, width=640, height=480):
        self.width = width
        self.height = height
        self.blank_frame = np.zeros((height, width, 3), dtype=np.uint8)
        cv2.putText(self.blank_frame, "Simulated Video Feed", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        cv2.putText(self.blank_frame, "Device: SimDroid_S24",
                    (10, height - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)

    def generate_frame(self):
        frame = self.blank_frame.copy()
        # Add milliseconds
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        cv2.putText(frame, timestamp, (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        return frame  # Return the raw frame for direct use


class FrameProcessor:
    def process_frame_data(self, frame_data):
        # In the real app, this would decode. Here, it's a pass-through.
        return frame_data


# --- Custom GUI Components ---

class CustomTitleBar(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.layout = QHBoxLayout()
        self.layout.setContentsMargins(10, 0, 0, 0)

        self.title = QLabel("Document Scanner")
        self.title.setAlignment(Qt.AlignCenter)
        style = "color: #ecf0f1; font-size: 16px; font-weight: bold;"
        self.title.setStyleSheet(style)

        self.layout.addWidget(self.title)

        self.btn_min = QPushButton("-")
        self.btn_max = QPushButton("+")
        self.btn_close = QPushButton("×")

        self.btn_min.setFixedSize(30, 30)
        self.btn_max.setFixedSize(30, 30)
        self.btn_close.setFixedSize(30, 30)

        # Apply specific styles for title bar buttons
        buttons = [(self.btn_min, '#f1c40f'),
                   (self.btn_max, '#2ecc71'),
                   (self.btn_close, '#e74c3c')]
        for btn, bg_color in buttons:
            darker_color = QPixmap(bg_color).toImage().darker(120).name()
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_color};
                    color: white;
                    border: none;
                    border-radius: 15px;
                    font-weight: bold;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background-color: {darker_color};
                }}
            """)

        self.layout.addWidget(self.btn_min)
        self.layout.addWidget(self.btn_max)
        self.layout.addWidget(self.btn_close)

        self.setLayout(self.layout)

        self.btn_close.clicked.connect(self.parent.close)
        self.btn_min.clicked.connect(self.parent.showMinimized)
        self.btn_max.clicked.connect(self.toggle_maximize)

        self.start_move_pos = None

    def toggle_maximize(self):
        if self.parent.isMaximized():
            self.parent.showNormal()
        else:
            self.parent.showMaximized()

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

        # Main content area
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.container_layout.addWidget(self.content_widget)

        # Video feed
        self.video_feed = QLabel("Connecting to device...")
        self.video_feed.setAlignment(Qt.AlignCenter)
        policy = QSizePolicy.Expanding
        self.video_feed.setSizePolicy(policy, policy)
        self.content_layout.addWidget(self.video_feed)

        # Capture button
        self.capture_button = QPushButton("Capture")
        self.capture_button.clicked.connect(self.capture_frame)
        self.content_layout.addWidget(self.capture_button, 0, Qt.AlignCenter)

        self.setStyleSheet("""
            #container {
                background-color: #2c3e50;
                border-radius: 15px;
                border: 2px solid #34495e;
            }
            #video_feed {
                background-color: black;
                border-radius: 10px;
                margin: 10px;
            }
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 15px 30px;
                font-size: 18px;
                border-radius: 10px;
                margin-bottom: 10px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)

        # --- Simulation Setup ---
        self.simulator = FrameSimulator()
        self.processor = FrameProcessor()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(1000 // 30)  # 30 FPS

    def update_frame(self):
        # Get a frame from the simulator
        self.current_frame = self.simulator.generate_frame()

        # Process it (pass-through in simulation)
        processed_frame = self.processor.process_frame_data(self.current_frame)

        # Convert to QPixmap and display
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

            # imwrite handles BGR conversion
            success = cv2.imwrite(filepath, self.current_frame)

            if success:
                print(f"Frame captured and saved to {filepath}")
                # Optional: Show a temporary confirmation message on the GUI
                self.title_bar.title.setText(f"Saved to {filepath}")
                QTimer.singleShot(
                    3000,
                    lambda: self.title_bar.title.setText("Document Scanner")
                )
            else:
                print(f"Error: Could not save frame to {filepath}")
                self.title_bar.title.setText("Error: Could not save frame!")
                QTimer.singleShot(
                    3000,
                    lambda: self.title_bar.title.setText("Document Scanner")
                )


if __name__ == '__main__':
    app = QApplication(sys.argv)
    main_win = MainWindow()
    main_win.show()
    sys.exit(app.exec_())
