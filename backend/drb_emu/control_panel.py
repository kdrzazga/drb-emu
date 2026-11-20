import os
import queue
import socket
import subprocess
import sys
import threading
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import scrolledtext

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ManagedProcess:
    def __init__(self, name, command, working_directory, output_queue):
        self.name = name
        self.command = command
        self.working_directory = working_directory
        self.output_queue = output_queue
        self.process = None

    def is_running(self):
        return self.process is not None and self.process.poll() is None

    def start(self):
        if self.is_running():
            self.output_queue.put(f"[{self.name}] already running\n")
            return
        environment = dict(os.environ, PYTHONUNBUFFERED="1", NO_COLOR="1", FORCE_COLOR="0")
        self.process = subprocess.Popen(
            self.command,
            cwd=self.working_directory,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        )
        self.output_queue.put(f"[{self.name}] started (pid {self.process.pid})\n")
        threading.Thread(target=self._forward_output, args=(self.process,), daemon=True).start()

    def _forward_output(self, process):
        for line in process.stdout:
            self.output_queue.put(f"[{self.name}] {line}")
        self.output_queue.put(f"[{self.name}] exited with code {process.wait()}\n")

    def kill(self):
        if not self.is_running():
            return
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(self.process.pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        else:
            self.process.kill()
        self.output_queue.put(f"[{self.name}] killed\n")


class ControlPanel:
    def __init__(self):
        self.title = "drb-emu control panel"
        self.ui_url = "http://localhost:5173/"
        self.ui_port = 5173
        self.refresh_interval_ms = 200
        self.output_queue = queue.Queue()
        self.waiting_to_open_browser = False

        npm_executable = "npm.cmd" if sys.platform == "win32" else "npm"
        self.server = ManagedProcess("server", [sys.executable, "-m", "drb_emu"], PROJECT_ROOT, self.output_queue)
        self.seeder = ManagedProcess("seed", [sys.executable, "-m", "drb_emu.seed"], PROJECT_ROOT, self.output_queue)
        self.ui = ManagedProcess("ui", [npm_executable, "run", "dev"], PROJECT_ROOT / "frontend", self.output_queue)
        self.educational_demo = ManagedProcess("demo", [sys.executable, "-m", "drb_emu.education.lecture"], PROJECT_ROOT, self.output_queue)
        self.processes = [self.server, self.seeder, self.ui, self.educational_demo]

        self.window = tk.Tk()
        self.window.title(self.title)
        self.window.geometry("1000x560")
        self.window.protocol("WM_DELETE_WINDOW", self.close)
        self.replace_existing_data = tk.BooleanVar(value=False)
        self.status_labels = {}
        self._build_layout()

    def _build_layout(self):
        button_bar = tk.Frame(self.window, padx=8, pady=8)
        button_bar.pack(fill=tk.X)
        tk.Button(button_bar, text="Start server", width=16, command=self.start_server).pack(side=tk.LEFT, padx=4)
        tk.Button(button_bar, text="Populate data", width=16, command=self.populate_data).pack(side=tk.LEFT, padx=4)
        tk.Checkbutton(button_bar, text="replace existing", variable=self.replace_existing_data).pack(side=tk.LEFT)
        tk.Button(button_bar, text="Start UI", width=16, command=self.start_ui).pack(side=tk.LEFT, padx=4)
        tk.Button(button_bar, text="Show educational demo", width=20, command=self.educational_demo.start).pack(side=tk.LEFT, padx=4)
        tk.Button(button_bar, text="Kill all", width=16, fg="white", bg="#c0392b", command=self.kill_all).pack(side=tk.RIGHT, padx=4)

        status_bar = tk.Frame(self.window, padx=8)
        status_bar.pack(fill=tk.X)
        for managed_process in self.processes:
            label = tk.Label(status_bar, width=20, anchor="w")
            label.pack(side=tk.LEFT, padx=4)
            self.status_labels[managed_process.name] = label

        self.log = scrolledtext.ScrolledText(self.window, state=tk.DISABLED, font=("Consolas", 10), bg="#10141c", fg="#d8dee9")
        self.log.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

    def start_server(self):
        self.server.start()

    def populate_data(self):
        self.seeder.command = [sys.executable, "-m", "drb_emu.seed"] + (["--replace"] if self.replace_existing_data.get() else [])
        self.seeder.start()

    def start_ui(self):
        was_running = self.ui.is_running()
        self.ui.start()
        if was_running:
            webbrowser.open(self.ui_url)
        else:
            self.waiting_to_open_browser = True

    def kill_all(self):
        for managed_process in self.processes:
            managed_process.kill()
        self.waiting_to_open_browser = False

    def close(self):
        self.kill_all()
        self.window.destroy()

    def _ui_port_open(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.settimeout(0.05)
            return probe.connect_ex(("127.0.0.1", self.ui_port)) == 0

    def _refresh(self):
        self._append_pending_output()
        for managed_process in self.processes:
            running = managed_process.is_running()
            self.status_labels[managed_process.name].config(
                text=f"{managed_process.name}: {'running' if running else 'stopped'}",
                fg="#1e8449" if running else "#7f8c8d",
            )
        if self.waiting_to_open_browser:
            if not self.ui.is_running():
                self.waiting_to_open_browser = False
            elif self._ui_port_open():
                self.waiting_to_open_browser = False
                webbrowser.open(self.ui_url)
        self.window.after(self.refresh_interval_ms, self._refresh)

    def _append_pending_output(self):
        lines = []
        while not self.output_queue.empty():
            lines.append(self.output_queue.get_nowait())
        if not lines:
            return
        self.log.config(state=tk.NORMAL)
        self.log.insert(tk.END, "".join(lines))
        self.log.see(tk.END)
        self.log.config(state=tk.DISABLED)

    def run(self):
        self._refresh()
        self.window.mainloop()


def main():
    ControlPanel().run()


if __name__ == "__main__":
    main()
