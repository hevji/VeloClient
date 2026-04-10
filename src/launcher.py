"""
launcher.py — Velo Client
PyQt6 WebEngine launcher with frameless window + QWebChannel bridge.

Requirements:
    pip install PyQt6 PyQt6-WebEngine
"""

import json
import os
import sys
import subprocess
import threading
import shutil

from PyQt6.QtWidgets import QApplication, QMainWindow, QFileDialog
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebChannel import QWebChannel
from PyQt6.QtCore import QObject, pyqtSlot, pyqtSignal, QUrl, Qt, QSize, QTimer
from PyQt6.QtGui import QIcon

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT           = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE    = os.path.join(ROOT, "config", "client_config.json")
COOKIES_DIR    = os.path.join(ROOT, "cookies")
COOKIES_FILE   = os.path.join(COOKIES_DIR, "cookies.json")
SCRIPTS_DIR    = os.path.join(ROOT, "scripts")
RESOURCES_DIR  = os.path.join(ROOT, "resources")
MANIFEST_FILE  = os.path.join(RESOURCES_DIR, "manifest.json")
UI_DIR         = os.path.join(ROOT, "ui")
KRUNKER_SCRIPT = os.path.join(ROOT, "krunker", "krunker.py")

for d in [COOKIES_DIR, SCRIPTS_DIR, RESOURCES_DIR, os.path.join(ROOT, "config")]:
    os.makedirs(d, exist_ok=True)

# ── Default config ────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "crosshair": {
        "enabled": False, "style": "cross", "color": "#2dd4bf",
        "size": 12, "thickness": 2, "gap": 4, "opacity": 1.0,
        "outline": True, "outline_color": "#000000"
    },
    "client": {
        "fps_limit_enabled": False, "fps_limit": 144,
        "fullscreen": True,
        "window_size_enabled": False, "window_width": 1280, "window_height": 720,
        "keep_launcher_open": True, "debug_logs": False,
        "block_ads": True, "enable_gpu": True,
        "show_menu_keybind": "`",
        "resource_swapper": False,
        "custom_css_enabled": False, "custom_css": "",
        "chrome_flags_enabled": False, "chrome_flags": ""
    },
    "scripts": {}
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            cfg = json.load(f)
        for section, values in DEFAULT_CONFIG.items():
            cfg.setdefault(section, {})
            if isinstance(values, dict):
                for k, v in values.items():
                    cfg[section].setdefault(k, v)
        return cfg
    return json.loads(json.dumps(DEFAULT_CONFIG))

def save_config(cfg):
    with open(CONFIG_FILE, "w") as f:
        json.dump(cfg, f, indent=2)


# ── Bridge ────────────────────────────────────────────────────────────────────
class Bridge(QObject):
    logReceived = pyqtSignal(str)   # Python → JS

    def __init__(self, window):
        super().__init__()
        self._win = window

    def _log(self, msg: str):
        line = f"[LAUNCHER] {msg}"
        print(line, flush=True)
        self.logReceived.emit(line)

    # Config
    @pyqtSlot(result=str)
    def getConfig(self):
        return json.dumps(load_config())

    @pyqtSlot(str)
    def saveConfig(self, cfg_json: str):
        save_config(json.loads(cfg_json))
        self._log("Config saved")

    # Scripts
    @pyqtSlot(result=str)
    def getScripts(self):
        os.makedirs(SCRIPTS_DIR, exist_ok=True)
        files = sorted(f for f in os.listdir(SCRIPTS_DIR) if f.endswith(".js"))
        cfg = load_config().get("scripts", {})
        return json.dumps([{"name": f, "enabled": cfg.get(f, True)} for f in files])

    @pyqtSlot()
    def openScriptsFolder(self):
        os.startfile(SCRIPTS_DIR)

    # Resources
    @pyqtSlot(result=str)
    def getResources(self):
        if not os.path.exists(MANIFEST_FILE):
            return json.dumps({"swaps": []})
        with open(MANIFEST_FILE) as f:
            return f.read()

    @pyqtSlot()
    def openResourcesFolder(self):
        os.startfile(RESOURCES_DIR)

    # Cookies
    @pyqtSlot(result=str)
    def getCookiesInfo(self):
        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE) as f:
                data = json.load(f)
            return json.dumps({"exists": True, "count": len(data)})
        return json.dumps({"exists": False, "count": 0})

    @pyqtSlot()
    def clearCookies(self):
        if os.path.exists(COOKIES_FILE):
            os.remove(COOKIES_FILE)
        self._log("Cookies cleared")

    @pyqtSlot()
    def exportCookies(self):
        if not os.path.exists(COOKIES_FILE):
            return
        dest, _ = QFileDialog.getSaveFileName(
            None, "Export Cookies", "cookies_backup.json", "JSON Files (*.json)"
        )
        if dest:
            shutil.copy(COOKIES_FILE, dest)
            self._log(f"Cookies exported to {dest}")

    # Window controls
    @pyqtSlot()
    def minimize(self):
        self._win.showMinimized()

    @pyqtSlot()
    def maximize(self):
        if self._win.isMaximized():
            self._win.showNormal()
        else:
            self._win.showMaximized()

    @pyqtSlot()
    def closeWindow(self):
        self._win.close()

    @pyqtSlot(int, int)
    def moveWindow(self, dx: int, dy: int):
        pos = self._win.pos()
        self._win.move(pos.x() + dx, pos.y() + dy)

    # Signal to tell JS to enter/exit console mode
    consoleModeChanged = pyqtSignal(bool)

    # Launch
    @pyqtSlot(str)
    def launch(self, cfg_json: str):
        cfg = json.loads(cfg_json)
        save_config(cfg)
        self._log("Launching krunker.py")

        def run():
            proc = subprocess.Popen(
                [sys.executable, KRUNKER_SCRIPT],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, bufsize=1, cwd=ROOT,
            )
            self.logReceived.emit("[LAUNCHER] Krunker process started")
            self.consoleModeChanged.emit(True)
            for line in proc.stdout:
                line = line.rstrip()
                if line:
                    self.logReceived.emit(f"[KRUNKER] {line}")
            proc.wait()
            self.logReceived.emit(f"[LAUNCHER] Krunker exited (code {proc.returncode})")
            self.consoleModeChanged.emit(False)

        threading.Thread(target=run, daemon=True).start()


# ── Titlebar injected CSS/HTML ────────────────────────────────────────────────
TITLEBAR_CSS = """
#velo-titlebar {
  position: fixed;
  top: 0; left: 0; right: 0;
  height: 38px;
  display: flex;
  align-items: center;
  background: #0e0f12;
  border-bottom: 1px solid rgba(255,255,255,0.06);
  z-index: 99999;
  user-select: none;
}
#velo-tb-logo {
  padding: 0 14px;
  display: flex;
  align-items: center;
  gap: 3px;
  font-family: 'Space Grotesk', sans-serif;
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 1.5px;
  flex-shrink: 0;
}
.velo-tb-name   { color: #e2e4ea; }
.velo-tb-client { color: #2dd4bf; }
#velo-tb-drag   { flex: 1; height: 100%; cursor: default; }
#velo-tb-controls {
  display: flex;
  align-items: center;
  padding: 0 6px;
  gap: 1px;
}
.velo-tb-btn {
  width: 32px; height: 32px;
  display: flex; align-items: center; justify-content: center;
  background: none; border: none;
  color: rgba(255,255,255,0.3);
  border-radius: 5px;
  cursor: pointer;
  transition: background 0.12s, color 0.12s;
}
.velo-tb-btn:hover          { background: rgba(255,255,255,0.07); color: rgba(255,255,255,0.8); }
.velo-tb-btn.tb-close:hover { background: #c0392b; color: #fff; }
body  { padding-top: 38px !important; box-sizing: border-box; }
#app  { height: calc(100vh - 38px) !important; }
"""


# ── Main Window ───────────────────────────────────────────────────────────────
class VeloWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Velo Client")
        self.setMinimumSize(QSize(900, 600))
        self.resize(QSize(960, 660))
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)

        self.view = QWebEngineView(self)
        self.setCentralWidget(self.view)

        self.channel = QWebChannel()
        self.bridge  = Bridge(self)
        self.channel.registerObject("bridge", self.bridge)
        self.view.page().setWebChannel(self.channel)

        # Push log lines and console mode changes to JS on the main thread
        self.bridge.logReceived.connect(self._dispatch_log)
        self.bridge.consoleModeChanged.connect(self._on_console_mode)

        self.view.setUrl(QUrl.fromLocalFile(os.path.join(UI_DIR, "index.html")))
        self.view.loadFinished.connect(self._inject_titlebar)

    def _inject_titlebar(self, ok):
        if not ok:
            return
        # Escape backticks/backslashes for JS template literal
        css  = TITLEBAR_CSS.replace("\\", "\\\\").replace("`", "\\`")
        self.view.page().runJavaScript(f"""
(function() {{
    if (document.getElementById('velo-titlebar')) return;
    const style = document.createElement('style');
    style.textContent = `{css}`;
    document.head.appendChild(style);

    const bar = document.createElement('div');
    bar.id = 'velo-titlebar';
    bar.innerHTML = `
        <div id="velo-tb-logo">
            <span class="velo-tb-name">VELO</span>
            <span class="velo-tb-client">CLIENT</span>
        </div>
        <div id="velo-tb-drag"></div>
        <div id="velo-tb-controls">
            <button class="velo-tb-btn" title="Minimize" onclick="new QWebChannel(qt.webChannelTransport, c => c.objects.bridge.minimize())">
                <svg width="11" height="2" viewBox="0 0 11 2"><rect width="11" height="2" rx="1" fill="currentColor"/></svg>
            </button>
            <button class="velo-tb-btn" title="Maximize" onclick="new QWebChannel(qt.webChannelTransport, c => c.objects.bridge.maximize())">
                <svg width="11" height="11" viewBox="0 0 11 11"><rect x="0.75" y="0.75" width="9.5" height="9.5" rx="1.5" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>
            </button>
            <button class="velo-tb-btn tb-close" title="Close" onclick="new QWebChannel(qt.webChannelTransport, c => c.objects.bridge.closeWindow())">
                <svg width="11" height="11" viewBox="0 0 11 11">
                    <line x1="1" y1="1" x2="10" y2="10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    <line x1="10" y1="1" x2="1" y2="10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                </svg>
            </button>
        </div>
    `;
    document.body.insertBefore(bar, document.body.firstChild);
}})();
        """)

    def _dispatch_log(self, line: str):
        safe = line.replace("\\", "\\\\").replace("`", "\\`").replace("\n", " ")
        self.view.page().runJavaScript(
            f"typeof appendLog !== 'undefined' && appendLog(`{safe}`);"
        )

    def _on_console_mode(self, entering: bool):
        if entering:
            self.view.page().runJavaScript("typeof enterConsoleMode !== 'undefined' && enterConsoleMode();")
            self.showNormal()
        else:
            self.view.page().runJavaScript("typeof exitConsoleMode !== 'undefined' && exitConsoleMode();")

    def mouseDoubleClickEvent(self, event):
        if event.position().y() < 38:
            self.showNormal() if self.isMaximized() else self.showMaximized()
        super().mouseDoubleClickEvent(event)


# ── Entry ─────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Velo Client")
    win = VeloWindow()
    win.show()
    sys.exit(app.exec())