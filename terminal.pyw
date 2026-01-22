import sys
import os
import json
import subprocess
import threading
from PySide6.QtWidgets import (
    QApplication, QWidget, QTextEdit, QLineEdit,
    QPushButton, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea
)
from PySide6.QtCore import Qt, QPoint, Signal, QObject
import traceback

# ================= CONFIG =================
WIDTH = 1000
HEIGHT = 560
TOPBAR_HEIGHT = 30
INPUT_HEIGHT = 30
RADIUS = 12

# ================= PATHS =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(BASE_DIR, "config")
ASCII_FILE = os.path.join(CONFIG_DIR, "ascii-art.txt")
SETTINGS_FILE = os.path.join(CONFIG_DIR, "settings.json")
CRASH_FILE = os.path.join(BASE_DIR, "htl.crash")

# ================= LOAD ASCII =================
ascii_art = ""
if os.path.exists(ASCII_FILE):
    try:
        with open(ASCII_FILE, "r", encoding="utf-8") as f:
            ascii_art = f.read()
    except Exception as e:
        with open(CRASH_FILE, "a", encoding="utf-8") as f:
            f.write(f"Failed to read ascii-art.txt: {e}\n")
        ascii_art = ""

# ================= THREAD-SAFE SIGNAL =================
class Writer(QObject):
    write_signal = Signal(str, str)

# ================= TERMINAL =================
class Terminal(QWidget):
    ASF_COMMANDS = {
        "Farm": ["!farm", "!pause", "!resume"],
        "Control": ["!start", "!stop", "!shutdown", "!exit"],
        "Status": ["!status", "!update"]
    }

    def __init__(self):
        super().__init__()
        try:
            self.init_ui()
            self.asf_process = None
            self.writer = Writer()
            self.writer.write_signal.connect(self.write_colored)
            self.load_settings()
            self.start_asf()
        except Exception as e:
            self.log_crash("Error initializing Terminal", e)
            raise

    # ================= UI INIT =================
    def init_ui(self):
        self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(WIDTH, HEIGHT)
        self.center()
        self.drag_pos = QPoint()

        self.container = QWidget(self)
        self.container.setObjectName("container")
        self.container.setGeometry(0, 0, WIDTH, HEIGHT)

        # === TOP BAR ===
        self.top = QWidget(self.container)
        self.top.setFixedHeight(TOPBAR_HEIGHT)
        self.top.setObjectName("top")
        top_layout = QHBoxLayout(self.top)
        top_layout.setContentsMargins(12, 0, 0, 0)
        top_layout.setSpacing(8)
        top_layout.addWidget(self.dot("#ff5f56", 11, self.close))
        top_layout.addWidget(self.dot("#ffbd2e", 11, self.showMinimized))
        top_layout.addWidget(self.dot("#27c93f", 11, self.toggle_max))
        top_layout.addStretch()

        # === OUTPUT QTextEdit ===
        self.text = QTextEdit(self.container)
        self.text.setReadOnly(True)
        self.text.setGeometry(0, TOPBAR_HEIGHT, WIDTH, HEIGHT - TOPBAR_HEIGHT - INPUT_HEIGHT)

        # === INPUT QLineEdit ===
        self.input = QLineEdit(self.container)
        self.input.setGeometry(0, HEIGHT - INPUT_HEIGHT, WIDTH, INPUT_HEIGHT)
        self.input.returnPressed.connect(self.run_command)

        # === BUTTON ASF COMMANDS COLT DREAPTA JOS ===
        self.cmd_button = QPushButton("ASF Commands", self.container)
        self.cmd_button.setFixedSize(130, 30)
        self.cmd_button.setStyleSheet("""
            QPushButton {
                color: white;
                background: #1a1a1a;
                border-radius: 5px;
            }
            QPushButton:hover {
                background: #333;
            }
        """)
        self.cmd_button.clicked.connect(self.show_commands_popup)
        self.cmd_button.move(WIDTH - 140, HEIGHT - 40)
        self.cmd_button.raise_()

        # === STYLE =================
        self.setStyleSheet(f"""
            QWidget#container {{
                background: rgba(0, 0, 0, 204);
                border-radius: {RADIUS}px;
            }}
            QWidget#top {{
                background: #0a0a0a;
                border-top-left-radius: {RADIUS}px;
                border-top-right-radius: {RADIUS}px;
            }}
            QTextEdit, QLineEdit {{
                background: transparent;
                color: white;
                border: none;
                font-family: Consolas;
                font-size: 11pt;
                padding: 6px;
            }}
        """)

        if ascii_art:
            self.write(ascii_art)
            self.write("")

        self.input.setFocus()

    # ================= DOT =================
    def dot(self, color, size, action):
        w = QWidget()
        w.setFixedSize(size, size)
        w.setStyleSheet(f"background:{color}; border-radius:{size//2}px;")
        w.mousePressEvent = lambda e: action()
        return w

    # ================= WRITE =================
    def write(self, msg):
        self.text.append(msg)

    def write_colored(self, msg, color):
        self.text.append(f'<span style="color:{color}">{msg}</span>')
        self.text.verticalScrollBar().setValue(self.text.verticalScrollBar().maximum())

    # ================= LOAD SETTINGS =================
    def load_settings(self):
        try:
            self.asf_path = ""
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.asf_path = data.get("ASF_path", "").replace("\\", "/")
                    self.write(f"[INFO] ASF path loaded: {self.asf_path}")
            else:
                self.write("[WARN] settings.json not found in config/")
                self.log_crash("settings.json not found", "")
        except Exception as e:
            self.log_crash("Failed to load settings.json", e)

    # ================= START ASF =================
    def start_asf(self):
        try:
            if self.asf_path and os.path.exists(self.asf_path):
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = 0  # SW_HIDE

                self.asf_process = subprocess.Popen(
                    [self.asf_path],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.PIPE,
                    bufsize=1,
                    universal_newlines=True,
                    startupinfo=startupinfo,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                self.write(f"[INFO] ASF started: {self.asf_path}")
                threading.Thread(target=self.read_output, daemon=True).start()
            else:
                self.write("[WARN] ASF path invalid or not found in settings.json.")
                self.log_crash("ASF path invalid or not found", "")
        except Exception as e:
            self.log_crash("Could not start ASF", e)

    # ================= READ OUTPUT =================
    def read_output(self):
        try:
            if not self.asf_process:
                return
            for line in self.asf_process.stdout:
                self.color_line(line.strip(), False)
            for line in self.asf_process.stderr:
                self.color_line(line.strip(), True)
        except Exception as e:
            self.log_crash("Error reading ASF output", e)

    # ================= COLOR LINE =================
    def color_line(self, line, is_stderr=False):
        color = "white"
        upper = line.upper()
        if "ERROR" in upper or is_stderr:
            color = "red"
        elif "WARNING" in upper:
            color = "yellow"
        elif "SUCCESS" in upper:
            color = "green"
        elif "INFO" in upper:
            color = "white"
        self.writer.write_signal.emit(line, color)

    # ================= RUN COMMAND =================
    def run_command(self):
        cmd = self.input.text().strip()
        self.input.clear()
        if not cmd:
            return
        self.write(f"> {cmd}")
        try:
            if cmd.lower() in ("exit", "quit"):
                self.close()
            elif cmd.lower() == "cls":
                self.text.clear()
                if ascii_art:
                    self.write(ascii_art)
            elif self.asf_process:
                self.asf_process.stdin.write(cmd + "\n")
                self.asf_process.stdin.flush()
            else:
                os.system(cmd)
        except Exception as e:
            self.log_crash(f"Failed to run command: {cmd}", e)

    # ================= SHOW COMMANDS POPUP =================
    def show_commands_popup(self):
        popup = QWidget(self)
        popup.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        popup.setAttribute(Qt.WA_TranslucentBackground)
        popup.setFixedSize(300, 400)
        popup.setFocusPolicy(Qt.StrongFocus)  # pentru a primi input tastatura
        popup.keyPressEvent = lambda e: self.popup_keypress(e, popup)

        # Container transparent
        container = QWidget(popup)
        container.setGeometry(0, 0, 300, 400)
        container.setStyleSheet("""
            QWidget { background: rgba(10,10,10,220); border-radius: 12px; }
        """)

        # === TOP BAR cu dot-uri + titlu ===
        top_bar = QWidget(container)
        top_bar.setGeometry(0, 0, 300, 30)
        top_layout = QHBoxLayout(top_bar)
        top_layout.setContentsMargins(6,0,6,0)
        top_layout.addWidget(self.dot("#ff5f56", 11, lambda: popup.close()))
        top_layout.addWidget(self.dot("#ffbd2e", 11, lambda: popup.hide()))
        top_layout.addWidget(self.dot("#27c93f", 11, lambda: popup.showNormal()))
        top_layout.addStretch()
        title = QLabel("ASF Commands", top_bar)
        title.setStyleSheet("color:white; font-weight:bold;")
        title.setAlignment(Qt.AlignCenter)
        top_layout.addWidget(title, alignment=Qt.AlignCenter)

        # Drag complet pe tot containerul
        def start_drag(e):
            popup.drag_pos = e.globalPosition().toPoint()
        def move_drag(e):
            if hasattr(popup, "drag_pos") and not popup.drag_pos.isNull():
                delta = e.globalPosition().toPoint() - popup.drag_pos
                popup.move(popup.pos() + delta)
                popup.drag_pos = e.globalPosition().toPoint()
        def end_drag(e):
            popup.drag_pos = QPoint()
        container.mousePressEvent = start_drag
        container.mouseMoveEvent = move_drag
        container.mouseReleaseEvent = end_drag

        # === Scrollarea cu comenzi ===
        scroll = QScrollArea(container)
        scroll.setGeometry(10, 40, 280, 350)
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 0px; }
            QScrollBar:horizontal { height: 0px; }
        """)
        content = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0,0,0,0)
        layout.setSpacing(2)
        content.setLayout(layout)
        scroll.setWidget(content)

        # Adaugam comenzi grupate
        for category, commands in self.ASF_COMMANDS.items():
            lbl = QLabel(category)
            lbl.setStyleSheet("color: cyan; font-weight:bold; padding:2px;")
            layout.addWidget(lbl)
            for cmd in commands:
                btn = QPushButton(cmd)
                btn.setStyleSheet("""
                    QPushButton { color:white; background:#1a1a1a; border-radius:4px; padding:4px; text-align:left; }
                    QPushButton:hover { background:#333; }
                """)
                btn.clicked.connect(lambda checked, c=cmd: self.send_command_from_popup(c, popup))
                layout.addWidget(btn)
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            sep.setFrameShadow(QFrame.Sunken)
            sep.setStyleSheet("color: rgba(255,255,255,50);")
            layout.addWidget(sep)

        popup.show()
        # focus pe primul buton
        first_btns = popup.findChildren(QPushButton)
        if first_btns:
            first_btns[0].setFocus()

    # ================= SEND COMMAND FROM POPUP =================
    def send_command_from_popup(self, command, popup):
        if self.asf_process:
            try:
                self.asf_process.stdin.write(command + "\n")
                self.asf_process.stdin.flush()
                self.write(f"> {command}")
            except Exception as e:
                self.log_crash(f"Failed to send command from popup: {command}", e)
        popup.close()

    # ================= POPUP KEY PRESS =================
    def popup_keypress(self, event, popup):
        focus_widget = QApplication.focusWidget()
        buttons = popup.findChildren(QPushButton)
        if not buttons:
            return
        idx = buttons.index(focus_widget) if focus_widget in buttons else -1
        if event.key() in (Qt.Key_Enter, Qt.Key_Return):
            if isinstance(focus_widget, QPushButton):
                focus_widget.click()
        elif event.key() == Qt.Key_Up:
            new_idx = (idx - 1) % len(buttons)
            buttons[new_idx].setFocus()
        elif event.key() == Qt.Key_Down:
            new_idx = (idx + 1) % len(buttons)
            buttons[new_idx].setFocus()

    # ================= DRAG =================
    def mousePressEvent(self, e):
        if e.position().y() <= TOPBAR_HEIGHT:
            self.drag_pos = e.globalPosition().toPoint()
    def mouseMoveEvent(self, e):
        if not self.drag_pos.isNull():
            delta = e.globalPosition().toPoint() - self.drag_pos
            self.move(self.pos() + delta)
            self.drag_pos = e.globalPosition().toPoint()
    def mouseReleaseEvent(self, e):
        self.drag_pos = QPoint()

    # ================= WINDOW =================
    def toggle_max(self):
        self.showNormal() if self.isMaximized() else self.showMaximized()
    def center(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.center().x() - WIDTH // 2, screen.center().y() - HEIGHT // 2)

    # ================= CLOSE EVENT =================
    def closeEvent(self, event):
        try:
            if self.asf_process and self.asf_process.poll() is None:
                self.write("[INFO] Stopping ASF...")
                self.asf_process.terminate()
                self.asf_process.wait()
        except Exception as e:
            self.log_crash("Error stopping ASF", e)
        event.accept()

    # ================= LOG CRASH =================
    def log_crash(self, message, exception):
        with open(CRASH_FILE, "a", encoding="utf-8") as f:
            f.write(f"{message}\n")
            if exception:
                f.write(f"{traceback.format_exc()}\n")

# ================= RUN =================
if __name__ == "__main__":
    try:
        app = QApplication(sys.argv)
        win = Terminal()
        win.show()
        sys.exit(app.exec())
    except Exception as e:
        with open(CRASH_FILE, "a", encoding="utf-8") as f:
            f.write("Fatal error starting Terminal:\n")
            f.write(f"{traceback.format_exc()}\n")
