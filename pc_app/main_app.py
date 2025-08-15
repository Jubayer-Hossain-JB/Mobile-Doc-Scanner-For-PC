import sys
import os
import cv2
import numpy as np
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QLabel, QSizePolicy,
                             QStackedWidget)
from PyQt5.QtCore import Qt, QTimer, QPropertyAnimation, pyqtProperty
from PyQt5.QtGui import QImage, QPixmap, QColor


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
        self.layout.setContentsMargins(0, 0, 5, 0)  # L, T, R, B
        self.layout.setSpacing(10)

        self.title = QLabel("Document Scanner")
        self.title.setAlignment(Qt.AlignCenter)
        style = "color: #ecf0f1; font-size: 16px; font-weight: bold;"
        self.title.setStyleSheet(style)

        self.layout.addStretch()
        self.layout.addWidget(self.title)
        self.layout.addStretch()

        self.btn_min = QPushButton("-")
        self.btn_close = QPushButton("×")

        self.btn_min.setFixedSize(26, 26)
        self.btn_close.setFixedSize(26, 26)

        # Apply specific styles for title bar buttons
        buttons = [(self.btn_min, '#f1c40f'),
                   (self.btn_close, '#e74c3c')]
        for btn, bg_color in buttons:
            darker_color = QColor(bg_color).darker(120).name()
            btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: {bg_color};
                    color: white;
                    border: none;
                    border-radius: 13px;
                    font-weight: bold;
                    font-size: 14px;
                }}
                QPushButton:hover {{
                    background-color: {darker_color};
                }}
            """)

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

        # --- Main Content Area using QStackedWidget for different states ---
        self.stacked_widget = QStackedWidget()
        self.container_layout.addWidget(self.stacked_widget)

        # --- "Searching" State Widget ---
        self.searching_widget = QWidget()
        self.searching_layout = QVBoxLayout(self.searching_widget)
        self.searching_label = QLabel("Searching for device...")
        self.searching_label.setAlignment(Qt.AlignCenter)
        self.searching_label.setStyleSheet("font-size: 24px; color: #ecf0f1;")
        self.searching_layout.addWidget(self.searching_label)
        self.stacked_widget.addWidget(self.searching_widget)

        # --- "Connected" State Widget (Video Feed) ---
        self.video_widget = QWidget()
        self.video_widget.setStyleSheet("background-color: transparent;")
        self.video_layout = QVBoxLayout(self.video_widget)
        self.video_feed = QLabel()
        self.video_feed.setObjectName("videoFeed")
        self.video_feed.setAlignment(Qt.AlignCenter)
        self.video_feed.setSizePolicy(
            QSizePolicy.Expanding, QSizePolicy.Expanding
        )
        self.video_layout.addWidget(self.video_feed)

        self.capture_button = AnimatedButton("Capture")
        self.capture_button.set_colors(QColor("#3498db"), QColor("#2980b9"))
        self.capture_button.clicked.connect(self.capture_frame)
        self.video_layout.addWidget(self.capture_button, 0, Qt.AlignCenter)
        self.stacked_widget.addWidget(self.video_widget)

        self.setStyleSheet("""
            #container {
                background-color: #2c3e50;
                border-radius: 15px;
            }
            CustomTitleBar, #searching_widget {
                background-color: transparent;
            }
            #videoFeed {
                background-color: black;
                border-radius: 10px;
                margin: 10px;
            }
        """)

        # --- Simulation and State Machine Setup ---
        self.simulator = FrameSimulator()
        self.processor = FrameProcessor()

        # Timer for video feed
        self.video_timer = QTimer(self)
        self.video_timer.timeout.connect(self.update_frame)

        # Timer to simulate connection
        self.connection_timer = QTimer(self)
        self.connection_timer.setSingleShot(True)
        self.connection_timer.timeout.connect(self.on_device_connected)
        self.connection_timer.start(3000)  # Simulate 3 second connection time

    def on_device_connected(self):
        print("Device connected!")
        self.stacked_widget.setCurrentWidget(self.video_widget)
        self.video_timer.start(1000 // 30)  # 30 FPS

    def update_frame(self):
        # Get a frame from the simulator
        self.current_frame = self.simulator.generate_frame()

        # Process it (pass-through in simulation)
        processed_frame = self.processor.process_data(self.current_frame)

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
