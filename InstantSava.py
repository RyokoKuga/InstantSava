import customtkinter as ctk
from tkinter import filedialog
import http.server
import socketserver
import threading
import os
import webbrowser
import urllib.parse
import html
import io
import json
import sys
import socket
from pathlib import Path
from functools import partial

# --- 1. 定数とパスの設定 ---
APP_NAME = "InstantSava"

def get_config_path():
    if sys.platform == "win32":
        base_dir = Path(os.getenv('APPDATA', Path.home() / "AppData/Roaming"))
    elif sys.platform == "darwin":
        base_dir = Path.home() / "Library" / "Application Support"
    else:
        base_dir = Path.home() / ".config"
    config_dir = base_dir / APP_NAME
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "config.json"

CONFIG_FILE = get_config_path()

def get_local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# --- 2. カスタムアラートダイアログ (修正済み) ---
class SavaFarmAlert(ctk.CTkToplevel):
    def __init__(self, parent, title, message):
        super().__init__(parent)
        
        # チラつき防止: 描画準備ができるまで隠す
        self.withdraw()
        
        self.title(title)
        self.geometry("340x200")
        self.resizable(False, False)
        self.transient(parent)
        
        ctk.CTkLabel(self, text="⚠️", font=("Helvetica", 40)).pack(pady=(20, 10))
        ctk.CTkLabel(self, text=message, font=("Helvetica", 13), wraplength=280).pack(pady=10)
        ctk.CTkButton(self, text="OK", width=100, command=self.destroy).pack(pady=15)

        # 座標計算の前に最新の状態に更新
        self.update_idletasks()
        
        # 親ウィンドウの中央に配置
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")

        # 準備完了後に表示してフォーカスを奪う
        self.deiconify()
        self.grab_set()

# --- 3. セキュリティ & 利便性強化版ハンドラー ---
class SavaFarmHandler(http.server.SimpleHTTPRequestHandler):
    def list_directory(self, path):
        try:
            list_dir = [f for f in os.listdir(path) if not f.startswith('.')]
        except OSError:
            self.send_error(404, "No permission to list directory")
            return None
        
        list_dir.sort(key=lambda a: a.lower())
        displaypath = html.escape(urllib.parse.unquote(self.path))
        
        icon_folder = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#3B8ED0" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>'
        icon_file = '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#AAA" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M13 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"></path><polyline points="13 2 13 9 20 9"></polyline></svg>'

        html_tmpl = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>InstantSava - {displaypath}</title>
    <style>
        body {{ font-family: "Segoe UI", sans-serif; background-color: #1A1A1A; color: #DCE4EE; padding: 40px; }}
        .container {{ max-width: 900px; margin: 0 auto; background: #242424; border-radius: 12px; padding: 30px; border: 1px solid #333; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
        .header {{ display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #333; padding-bottom: 15px; margin-bottom: 20px; }}
        h1 {{ font-size: 18px; margin: 0; font-family: "Cascadia Code", monospace; }}
        .brand {{ color: #3B8ED0; font-weight: bold; font-size: 14px; letter-spacing: 1px; }}
        ul {{ list-style: none; padding: 0; }}
        li {{ border-radius: 6px; transition: 0.2s; }}
        li:hover {{ background: #2C2C2C; transform: translateX(5px); }}
        a {{ display: flex; align-items: center; padding: 10px 15px; color: #DCE4EE; text-decoration: none; font-size: 14px; }}
        .icon {{ margin-right: 12px; display: flex; align-items: center; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{displaypath}</h1>
            <span class="brand">INSTANTSAVA</span>
        </div>
        <ul>
        {"<li><a href='..'><span class='icon'>" + icon_folder + "</span><span>../ (Parent Directory)</span></a></li>" if self.path != "/" else ""}
        """

        for name in list_dir:
            fullname = os.path.join(path, name)
            is_dir = os.path.isdir(fullname)
            icon = icon_folder if is_dir else icon_file
            linkname = name + "/" if is_dir else name
            html_tmpl += f'<li><a href="{urllib.parse.quote(linkname)}"><span class="icon">{icon}</span><span>{html.escape(linkname)}</span></a></li>'

        html_tmpl += "</ul></div></body></html>"
        
        encoded = html_tmpl.encode('utf-8', 'surrogateescape')
        f = io.BytesIO(encoded)
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        return f

# --- 4. ポートの即時解放を可能にするサーバークラス ---
class ReusableTCPServer(socketserver.TCPServer):
    allow_reuse_address = True

# --- 5. 環境設定モーダル (修正済み) ---
class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        
        # チラつき防止
        self.withdraw()
        
        self.title("InstantSava Settings")
        self.geometry("500x330")
        self.parent = parent
        self.transient(parent)
        self.resizable(False, False)

        ctk.CTkLabel(self, text="Environment Settings", font=("Helvetica", 20, "bold"), text_color="#3B8ED0").pack(pady=(25, 20))
        
        self.sec_path = ctk.CTkFrame(self, fg_color="transparent")
        self.sec_path.pack(fill="x", padx=40)
        ctk.CTkLabel(self.sec_path, text="Target Directory:", font=("Helvetica", 12)).pack(anchor="w")
        
        self.path_row = ctk.CTkFrame(self.sec_path, fg_color="transparent")
        self.path_row.pack(fill="x", pady=(5, 15))
        self.entry_path = ctk.CTkEntry(self.path_row, placeholder_text="Select folder...")
        self.entry_path.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.entry_path.insert(0, parent.config.get("last_path", ""))
        
        self.btn_browse = ctk.CTkButton(self.path_row, text="Browse", width=80, fg_color="#444", command=self.browse_path)
        self.btn_browse.pack(side="right")

        ctk.CTkLabel(self, text="Port Number (1024-65535):", font=("Helvetica", 12)).pack(padx=40, anchor="w")
        self.port_entry = ctk.CTkEntry(self, width=120, justify="center")
        self.port_entry.pack(pady=(5, 15))
        self.port_entry.insert(0, parent.config.get("last_port", "8000"))

        self.btn_save = ctk.CTkButton(self, text="Apply & Close", font=("Helvetica", 13, "bold"), 
                                     fg_color="#3B8ED0", hover_color="#2B6DA0", height=40, command=self.save_settings)
        self.btn_save.pack(pady=(15, 5))

        # 座標計算と表示
        self.update_idletasks()
        x = parent.winfo_x() + (parent.winfo_width() // 2) - (self.winfo_width() // 2)
        y = parent.winfo_y() + (parent.winfo_height() // 2) - (self.winfo_height() // 2)
        self.geometry(f"+{x}+{y}")
        
        self.deiconify()
        self.grab_set()

    def browse_path(self):
        path = filedialog.askdirectory()
        if path:
            self.entry_path.delete(0, "end")
            self.entry_path.insert(0, path)

    def save_settings(self):
        port_raw = self.port_entry.get()
        if not port_raw.isdigit() or not (1024 <= int(port_raw) <= 65535):
            SavaFarmAlert(self, "Invalid Port", "Please enter a port number between 1024 and 65535.")
            return

        self.parent.config["last_path"] = self.entry_path.get()
        self.parent.config["last_port"] = port_raw
        self.parent.save_config()
        self.parent.update_display()
        self.destroy()

# --- 6. メインアプリケーション ---
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SavaFarmMain(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("InstantSava")
        self.geometry("400x420")
        self.resizable(False, False)

        self.httpd = None
        self._lock = threading.Lock()
        self.config = {"last_path": str(Path.home()), "last_port": "8000"}
        self.load_config()

        self.setup_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def setup_ui(self):
        ctk.CTkLabel(self, text="InstantSava", font=("Helvetica", 32, "bold"), text_color="#3B8ED0").pack(pady=(40, 5))
        ctk.CTkLabel(self, text="Unified UI Local Server", font=("Helvetica", 12), text_color="gray").pack(pady=(0, 30))

        self.info_card = ctk.CTkFrame(self, fg_color="#222", corner_radius=12, border_width=1, border_color="#333")
        self.info_card.pack(padx=40, fill="x", pady=10)
        
        self.path_info = ctk.CTkLabel(self.info_card, text="", font=("Helvetica", 12), text_color="#DCE4EE", wraplength=280)
        self.path_info.pack(pady=(18, 4))
        self.port_info = ctk.CTkLabel(self.info_card, text="", font=("Helvetica", 12, "bold"), text_color="#3B8ED0")
        self.port_info.pack(pady=(0, 18))
        
        self.update_display()

        self.btn_launch = ctk.CTkButton(self, text="Launch Server", font=("Helvetica", 16, "bold"), 
                                       height=55, corner_radius=8, command=self.toggle_server)
        self.btn_launch.pack(pady=25, padx=40, fill="x")

        self.btn_settings = ctk.CTkButton(self, text="⚙  Preferences", width=120, fg_color="transparent", 
                                         text_color="gray", hover_color="#222", command=self.open_settings)
        self.btn_settings.pack(side="bottom", pady=20)

    def update_display(self):
        path = self.config.get("last_path", "None selected")
        port = self.config.get("last_port", "8000")
        display_path = (path[:40] + '...') if len(path) > 40 else path
        self.path_info.configure(text=f"Folder: {display_path}")
        self.port_info.configure(text=f"Port: {port}")

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self.config.update(json.load(f))
            except Exception: pass

    def save_config(self):
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception: pass

    def open_settings(self):
        if self.httpd: return 
        SettingsWindow(self)

    def toggle_server(self):
        if self.httpd is None:
            self.start_server()
        else:
            self.stop_server()

    def start_server(self):
        path = self.config["last_path"]
        port = int(self.config["last_port"])
        local_ip = get_local_ip()

        if not os.path.exists(path):
            SavaFarmAlert(self, "Path Error", "The selected directory does not exist.")
            return

        def run_thread():
            handler = partial(SavaFarmHandler, directory=path)
            try:
                with ReusableTCPServer(("127.0.0.1", port), handler) as server:
                    with self._lock:
                        self.httpd = server
                    server.serve_forever()
            except Exception as e:
                with self._lock:
                    self.httpd = None
                self.after(0, lambda: SavaFarmAlert(self, "Server Error", f"Could not start server.\nMaybe port {port} is in use?"))
                self.after(0, self.stop_server)

        threading.Thread(target=run_thread, daemon=True).start()
        
        self.btn_launch.configure(text="Stop Server", fg_color="#E74C3C", hover_color="#C0392B")
        self.btn_settings.configure(state="disabled")
        self.info_card.configure(border_color="#27AE60")
        self.port_info.configure(text=f"Online: http://{local_ip}:{port}")
        
        webbrowser.open(f"http://localhost:{port}")

    def stop_server(self):
        with self._lock:
            if self.httpd:
                server_to_stop = self.httpd
                self.httpd = None
                threading.Thread(target=server_to_stop.shutdown, daemon=True).start()
            
        self.btn_launch.configure(text="Launch Server", fg_color="#3B8ED0", hover_color="#2B6DA0")
        self.btn_settings.configure(state="normal")
        self.info_card.configure(border_color="#333")
        self.update_display()

    def on_closing(self):
        if self.httpd:
            with self._lock:
                server_to_stop = self.httpd
                threading.Thread(target=server_to_stop.shutdown, daemon=True).start()
        self.destroy()
        os._exit(0)

if __name__ == "__main__":
    app = SavaFarmMain()
    app.mainloop()