import sys
import psutil
import subprocess
import threading
import time
import socket
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QComboBox,
    QCheckBox,
    QFrame,
    QLineEdit,
    QGridLayout,
    QGroupBox,
)
from PyQt5.QtGui import QFont, QIntValidator
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtMultimedia import QSound


class SystemMonitor(QMainWindow):
    update_signal = pyqtSignal(dict)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("System Monitor")
        self.setGeometry(100, 100, 800, 800)

        self.alarm_active = False
        self.monitored_process = None
        self.monitor_process = False

        self.init_ui()
        self.update_signal.connect(self.update_ui)

        self.alarm_sound = QSound("alarm.wav")

        # Start updating system info
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_system_info)
        self.update_timer.start(1000)  # Update every second

        # Start monitoring thread
        self.monitoring_thread = threading.Thread(
            target=self.monitor_system, daemon=True
        )
        self.monitoring_thread.start()

    def init_ui(self):
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # Title
        title_label = QLabel("System Monitor")
        title_label.setFont(QFont("Arial", 24, QFont.Bold))
        layout.addWidget(title_label)

        # Settings
        settings_group = QGroupBox("Alarm Settings")
        settings_layout = QGridLayout()
        settings_group.setLayout(settings_layout)

        self.alarm_settings = {
            "RAM Usage": {
                "checkbox": QCheckBox("Enable"),
                "input": QLineEdit("85"),
                "unit": "%",
            },
            "CPU Temperature": {
                "checkbox": QCheckBox("Enable"),
                "input": QLineEdit("105"),
                "unit": "°C",
            },
            "GPU Temperature": {
                "checkbox": QCheckBox("Enable"),
                "input": QLineEdit("80"),
                "unit": "°C",
            },
            "Internet": {"checkbox": QCheckBox("Enable"), "input": None, "unit": None},
        }

        for i, (name, setting) in enumerate(self.alarm_settings.items()):
            settings_layout.addWidget(QLabel(name), i, 0)
            settings_layout.addWidget(setting["checkbox"], i, 1)
            if setting["input"]:
                setting["input"].setValidator(
                    QIntValidator(0, 100)
                    if name == "RAM Usage"
                    else QIntValidator(0, 150)
                )
                settings_layout.addWidget(setting["input"], i, 2)
                settings_layout.addWidget(QLabel(setting["unit"]), i, 3)

        layout.addWidget(settings_group)

        # Process monitoring controls
        process_layout = QHBoxLayout()
        self.monitor_process_checkbox = QCheckBox("Monitor Process")
        self.monitor_process_checkbox.stateChanged.connect(
            self.toggle_process_monitoring
        )
        process_layout.addWidget(self.monitor_process_checkbox)

        self.process_combo = QComboBox()
        self.process_combo.setEnabled(False)
        self.update_process_list()
        process_layout.addWidget(self.process_combo)

        layout.addLayout(process_layout)

        # Buttons
        button_layout = QHBoxLayout()
        start_button = QPushButton("Start Monitoring")
        start_button.clicked.connect(self.start_monitoring)
        button_layout.addWidget(start_button)

        stop_button = QPushButton("Stop Alarm")
        stop_button.clicked.connect(self.stop_alarm)
        button_layout.addWidget(stop_button)

        layout.addLayout(button_layout)

        # System indicators
        self.indicators = {}
        self.alarm_levels = {}
        for indicator in [
            "RAM Usage",
            "CPU Temperature",
            "GPU Temperature",
            "Internet",
            "Monitored Process",
        ]:
            self.create_indicator(layout, indicator)

        # Status label
        self.status_label = QLabel("Status: Not monitoring")
        self.status_label.setFont(QFont("Arial", 12, QFont.Bold))
        layout.addWidget(self.status_label)

        layout.addStretch(1)  # Add stretch to push everything to the top

    def create_indicator(self, parent_layout, text):
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setFrameShadow(QFrame.Raised)
        layout = QHBoxLayout(frame)

        label = QLabel(f"{text}:")
        label.setFont(QFont("Arial", 12))
        layout.addWidget(label)

        value_label = QLabel("N/A")
        value_label.setFont(QFont("Arial", 12, QFont.Bold))
        value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(value_label)

        alarm_level_label = QLabel("Alarm: N/A")
        alarm_level_label.setFont(QFont("Arial", 10))
        alarm_level_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(alarm_level_label)

        parent_layout.addWidget(frame)
        self.indicators[text] = value_label
        self.alarm_levels[text] = alarm_level_label

    def update_process_list(self):
        processes = sorted([p.name() for p in psutil.process_iter(["name"])])
        self.process_combo.clear()
        self.process_combo.addItems(processes)

    def toggle_process_monitoring(self, state):
        self.monitor_process = bool(state)
        self.process_combo.setEnabled(self.monitor_process)
        if not self.monitor_process:
            self.monitored_process = None
            self.update_indicator("Monitored Process", "Disabled", "gray")
            self.update_alarm_level("Monitored Process", "N/A")

    def start_monitoring(self):
        if self.monitor_process:
            self.monitored_process = self.process_combo.currentText()
            if not self.monitored_process:
                self.update_status("Please select a process", "red")
                return
        else:
            self.monitored_process = None

        self.update_status("Monitoring...", "green")

    def monitor_system(self):
        while True:
            if (
                (
                    self.alarm_settings["Internet"]["checkbox"].isChecked()
                    and not self.check_internet()
                )
                or (
                    self.alarm_settings["RAM Usage"]["checkbox"].isChecked()
                    and self.check_ram_usage()
                )
                or (
                    self.alarm_settings["CPU Temperature"]["checkbox"].isChecked()
                    and self.check_cpu_temperature()
                )
                or (
                    self.alarm_settings["GPU Temperature"]["checkbox"].isChecked()
                    and self.check_gpu_temperature()
                )
                or (self.monitor_process and self.check_process_status())
            ):
                self.trigger_alarm()
            time.sleep(5)

    def check_internet(self):
        try:
            socket.create_connection(("8.8.8.8", 53), timeout=3)
            return True
        except OSError:
            return False

    def check_ram_usage(self):
        threshold = float(self.alarm_settings["RAM Usage"]["input"].text())
        return psutil.virtual_memory().percent >= threshold

    def check_cpu_temperature(self):
        threshold = float(self.alarm_settings["CPU Temperature"]["input"].text())
        try:
            temps = psutil.sensors_temperatures()
            if "coretemp" in temps:
                return max(temp.current for temp in temps["coretemp"]) >= threshold
            return False
        except:
            return False

    def check_gpu_temperature(self):
        threshold = float(self.alarm_settings["GPU Temperature"]["input"].text())
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
            )
            temperature = int(result.stdout.strip())
            return temperature >= threshold
        except:
            return False

    def check_process_status(self):
        return self.monitored_process not in (
            p.name() for p in psutil.process_iter(["name"])
        )

    def trigger_alarm(self):
        if not self.alarm_active:
            self.alarm_active = True
            # Play continuously
            self.alarm_sound.setLoops(100)
            self.alarm_sound.play()
            self.update_status("Alarm triggered!", "red")

    def stop_alarm(self):
        self.alarm_active = False
        self.alarm_sound.stop()
        self.update_status("Alarm stopped", "orange")

    def update_status(self, text, color):
        self.status_label.setText(f"Status: {text}")
        self.status_label.setStyleSheet(f"color: {color};")

    def update_system_info(self):
        info = {}

        # RAM usage
        ram_usage = psutil.virtual_memory().percent
        info["RAM Usage"] = (f"{ram_usage:.1f}%", self.get_usage_color(ram_usage))
        self.update_alarm_level(
            "RAM Usage",
            self.get_alarm_level(
                ram_usage, float(self.alarm_settings["RAM Usage"]["input"].text())
            ),
        )

        # CPU temperature
        try:
            temps = psutil.sensors_temperatures()
            if "coretemp" in temps:
                cpu_temp = max(temp.current for temp in temps["coretemp"])
                info["CPU Temperature"] = (
                    f"{cpu_temp:.1f}°C",
                    self.get_temp_color(cpu_temp),
                )
                self.update_alarm_level(
                    "CPU Temperature",
                    self.get_alarm_level(
                        cpu_temp,
                        float(self.alarm_settings["CPU Temperature"]["input"].text()),
                    ),
                )
            else:
                info["CPU Temperature"] = ("N/A", "gray")
                self.update_alarm_level("CPU Temperature", "N/A")
        except:
            info["CPU Temperature"] = ("N/A", "gray")
            self.update_alarm_level("CPU Temperature", "N/A")

        # GPU temperature
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=temperature.gpu",
                    "--format=csv,noheader,nounits",
                ],
                capture_output=True,
                text=True,
            )
            temperature = int(result.stdout.strip())
            info["GPU Temperature"] = (
                f"{temperature}°C",
                self.get_temp_color(temperature),
            )
            self.update_alarm_level(
                "GPU Temperature",
                self.get_alarm_level(
                    temperature,
                    float(self.alarm_settings["GPU Temperature"]["input"].text()),
                ),
            )
        except:
            info["GPU Temperature"] = ("N/A", "gray")
            self.update_alarm_level("GPU Temperature", "N/A")

        # Internet status
        internet_status = "Connected" if self.check_internet() else "Disconnected"
        info["Internet"] = (
            internet_status,
            "green" if internet_status == "Connected" else "red",
        )
        self.update_alarm_level(
            "Internet", "OK" if internet_status == "Connected" else "Alarm"
        )

        # Monitored process status
        if self.monitor_process and self.monitored_process:
            process_status = (
                "Running"
                if self.monitored_process
                in (p.name() for p in psutil.process_iter(["name"]))
                else "Not Running"
            )
            info["Monitored Process"] = (
                f"{self.monitored_process} ({process_status})",
                "green" if process_status == "Running" else "red",
            )
            self.update_alarm_level(
                "Monitored Process", "OK" if process_status == "Running" else "Alarm"
            )
        elif self.monitor_process:
            info["Monitored Process"] = ("None selected", "gray")
            self.update_alarm_level("Monitored Process", "N/A")
        else:
            info["Monitored Process"] = ("Disabled", "gray")
            self.update_alarm_level("Monitored Process", "N/A")

        self.update_signal.emit(info)

    def update_ui(self, info):
        for key, (value, color) in info.items():
            self.update_indicator(key, value, color)

    def update_indicator(self, name, value, color):
        self.indicators[name].setText(value)
        self.indicators[name].setStyleSheet(f"color: {color};")

    def update_alarm_level(self, name, level):
        self.alarm_levels[name].setText(f"Alarm: {level}")
        color = "green" if level == "OK" else "red" if level == "Alarm" else "gray"
        self.alarm_levels[name].setStyleSheet(f"color: {color};")

    def get_usage_color(self, value):
        if value < 60:
            return "green"
        elif value < 80:
            return "orange"
        else:
            return "red"

    def get_temp_color(self, value):
        if value < 60:
            return "green"
        elif value < 80:
            return "orange"
        else:
            return "red"

    def get_alarm_level(self, value, threshold):
        if value < threshold:
            return "OK"
        else:
            return "Alarm"


if __name__ == "__main__":
    app = QApplication(sys.argv)
    monitor = SystemMonitor()
    monitor.show()
    sys.exit(app.exec_())
