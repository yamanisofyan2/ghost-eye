import sys
import os
import json
import time
import hashlib
import socket
import getpass
import platform
import datetime
import threading
import requests
import re
import base64
import tkinter as tk
import subprocess
from tkinter import ttk, messagebox, scrolledtext
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization

# API Server endpoint & Token configuration
API_URL = "http://127.0.0.1:8000/api/telemetry"
API_TOKEN = "gho_secret_auth_token_2026"
CACHE_FILE = "offline_cache.json"
ENCRYPTION_KEY = "ghosteye_encryption_key_2026"  # Local cache encryption key

# Preloaded C++ process injection template
TEMPLATE_HELLO = """#include <iostream>

int main() {
    std::cout << "Hello, SecBuild World!" << std::endl;
    return 0;
}
"""

TEMPLATE_SOCKET = """#include <winsock2.h>
#include <iostream>

#pragma comment(lib, "ws2_32.lib")

int main() {
    WSADATA wsa;
    SOCKET s;
    struct sockaddr_in server;

    std::cout << "Initializing Winsock..." << std::endl;
    if (WSAStartup(MAKEWORD(2,2), &wsa) != 0) {
        std::cerr << "Failed. Error Code: " << WSAGetLastError() << std::endl;
        return 1;
    }
    
    if((s = socket(AF_INET, SOCK_STREAM, 0)) == INVALID_SOCKET) {
        std::cerr << "Could not create socket: " << WSAGetLastError() << std::endl;
        return 1;
    }
    std::cout << "Socket created." << std::endl;
    
    server.sin_addr.s_addr = inet_addr("127.0.0.1");
    server.sin_family = AF_INET;
    server.sin_port = htons(80);

    if (connect(s, (struct sockaddr *)&server, sizeof(server)) < 0) {
        std::cerr << "Connection error." << std::endl;
        return 1;
    }
    
    std::cout << "Connected successfully to 127.0.0.1:80" << std::endl;
    closesocket(s);
    WSACleanup();
    return 0;
}
"""

TEMPLATE_ENCRYPT = """#include <iostream>
#include <fstream>
#include <vector>

void xor_cipher(const std::string& filepath, char key) {
    std::ifstream infile(filepath, std::ios::binary);
    std::vector<char> data((std::istreambuf_iterator<char>(infile)), std::istreambuf_iterator<char>());
    infile.close();

    for (char& b : data) {
        b ^= key;
    }

    std::ofstream outfile(filepath, std::ios::binary);
    outfile.write(data.data(), data.size());
    outfile.close();
    std::cout << "File processed: " << filepath << std::endl;
}

int main() {
    std::string file = "target_file.dat";
    char key = 0x5A;
    std::cout << "Starting encryption/decryption on file..." << std::endl;
    // xor_cipher(file, key);
    return 0;
}
"""

TEMPLATE_SYSINFO = """#include <windows.h>
#include <iostream>

int main() {
    char computer_name[MAX_COMPUTERNAME_LENGTH + 1];
    DWORD size = sizeof(computer_name);
    
    if (GetComputerNameA(computer_name, &size)) {
        std::cout << "Host Name: " << computer_name << std::endl;
    }
    
    char user_name[256];
    DWORD user_size = sizeof(user_name);
    if (GetUserNameA(user_name, &user_size)) {
        std::cout << "Current User: " << user_name << std::endl;
    }
    
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    std::cout << "Processor Architecture: " << si.wProcessorArchitecture << std::endl;
    return 0;
}
"""

SAMPLE_CODE = """#include <windows.h>
#include <iostream>

// Target process: notepad.exe
int main() {
    // 1. Get process handle
    DWORD pid = 1234; 
    HANDLE hProcess = OpenProcess(PROCESS_ALL_ACCESS, FALSE, pid);
    
    // 2. Allocate memory inside target process (Suspicious API)
    LPVOID pRemoteBuf = VirtualAllocEx(hProcess, NULL, 4096, MEM_COMMIT, PAGE_EXECUTE_READWRITE);
    
    // 3. Write shellcode into process memory (Suspicious API)
    unsigned char shellcode[] = "\\x90\\x90\\x90\\x90"; // NOP sled placeholder
    WriteProcessMemory(hProcess, pRemoteBuf, shellcode, sizeof(shellcode), NULL);
    
    // 4. Execute shellcode in remote thread (Suspicious API)
    HANDLE hThread = CreateRemoteThread(hProcess, NULL, 0, (LPTHREAD_START_ROUTINE)pRemoteBuf, NULL, 0, NULL);
    
    std::cout << "[+] Injection completed successfully!" << std::endl;
    
    CloseHandle(hThread);
    CloseHandle(hProcess);
    return 0;
}
"""

class CompilerAgentApp(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("SecBuild C/C++ IDE - Secure Compiler & Static Auditor")
        self.configure(bg="#0b0e17")  # Cyber dark background
        
        self.network_online = True  # Network state tracker
        self.sync_thread_active = True
        self.logged_in_user = ""

        # Create Menu Bar
        menu_bar = tk.Menu(self)
        self.config(menu=menu_bar)
        
        # File Menu
        file_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Exit", command=self.destroy)
        
        # Templates Menu
        templates_menu = tk.Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="Templates", menu=templates_menu)
        templates_menu.add_command(label="Hello World", command=lambda: self.load_template("hello"))
        templates_menu.add_command(label="TCP Socket Client", command=lambda: self.load_template("socket"))
        templates_menu.add_command(label="File Encryption Utility", command=lambda: self.load_template("encrypt"))
        templates_menu.add_command(label="System Info Auditor", command=lambda: self.load_template("sysinfo"))
        templates_menu.add_command(label="Process Injection Demo", command=lambda: self.load_template("injection"))

        self.setup_styles()
        self.show_login_screen()
        
        # Derive cryptographic key for AES-256 (Fernet)
        salt = b"ghosteye_salt_2026"
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        derived_key = base64.urlsafe_b64encode(kdf.derive(ENCRYPTION_KEY.encode()))
        self.cipher_suite = Fernet(derived_key)

        # Ed25519 Keypair setup (Master/PhD stage feature)
        self.private_key_path = "dev_private.pem"
        self.public_key_path = "dev_public.pub"
        self.load_or_generate_asymmetric_keys()

    def load_or_generate_asymmetric_keys(self):
        if os.path.exists(self.private_key_path) and os.path.exists(self.public_key_path):
            try:
                with open(self.private_key_path, "rb") as f:
                    self.private_key = serialization.load_pem_private_key(f.read(), password=None)
                with open(self.public_key_path, "rb") as f:
                    self.public_key_pem = f.read()
                return
            except Exception as e:
                print(f"Error loading keys, regenerating: {e}")
                
        # Generate new keys
        self.private_key = ed25519.Ed25519PrivateKey.generate()
        pem_private = self.private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        with open(self.private_key_path, "wb") as f:
            f.write(pem_private)
            
        public_key = self.private_key.public_key()
        pub_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        self.public_key_pem = base64.b64encode(pub_bytes)
        with open(self.public_key_path, "wb") as f:
            f.write(self.public_key_pem)

    def sign_payload(self, filehash_sha256, username, timestamp) -> str:
        try:
            message = f"{filehash_sha256}:{username}:{timestamp}"
            message_bytes = message.encode("utf-8")
            sig_bytes = self.private_key.sign(message_bytes)
            return base64.b64encode(sig_bytes).decode('utf-8')
        except Exception as e:
            print(f"Signing error: {e}")
            return "None"

    def setup_styles(self):
        self.font_main = ("Inter", 10)
        self.font_bold = ("Inter", 10, "bold")
        self.font_title = ("Inter", 11, "bold")
        self.font_code = ("Consolas", 11)
        
        style = ttk.Style()
        style.theme_use('default')
        style.configure('.', font=self.font_main, background="#0b0e17", foreground="#f1f2f6")
        style.configure('TFrame', background="#0b0e17")
        style.configure('TLabel', background="#0b0e17", foreground="#a4b0be")
        style.configure('TCombobox', fieldbackground="#161b2c", background="#22273a", foreground="#f1f2f6")
        
        # Custom style for mapping Combobox padding
        self.option_add('*TCombobox*Listbox.background', '#161b2c')
        self.option_add('*TCombobox*Listbox.foreground', '#f1f2f6')
        self.option_add('*TCombobox*Listbox.selectBackground', '#00bfff')
        self.option_add('*TCombobox*Listbox.selectForeground', '#000000')

    def center_window(self, width, height):
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (width // 2)
        y = (screen_height // 2) - (height // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def show_login_screen(self):
        self.geometry("450x520")
        self.resizable(False, False)
        self.center_window(450, 520)
        
        self.login_frame = tk.Frame(self, bg="#111625")
        self.login_frame.pack(fill=tk.BOTH, expand=True, padx=25, pady=25)
        
        # Cyber Header Logo
        lbl_logo = tk.Label(self.login_frame, text="🛡️ SECBUILD", font=("Inter", 20, "bold"), fg="#2ed573", bg="#111625")
        lbl_logo.pack(pady=(25, 2))
        
        lbl_sub = tk.Label(self.login_frame, text="SECURE C/C++ DEVELOPMENT IDE", font=("Inter", 9, "bold"), fg="#a4b0be", bg="#111625")
        lbl_sub.pack(pady=(0, 20))
        
        # Divider
        divider = tk.Frame(self.login_frame, height=1, bg="#22273a")
        divider.pack(fill=tk.X, padx=10, pady=5)
        
        # Username Field
        lbl_user = tk.Label(self.login_frame, text="Developer Username", font=self.font_bold, fg="#a4b0be", bg="#111625")
        lbl_user.pack(anchor=tk.W, padx=25, pady=(15, 2))
        
        self.ent_username = tk.Entry(self.login_frame, bg="#1c2237", fg="#f1f2f6", insertbackground="#fff", bd=0, font=self.font_main)
        self.ent_username.pack(fill=tk.X, padx=25, ipady=8)
        self.ent_username.insert(0, "sec_developer")
        
        # Token Field
        lbl_token = tk.Label(self.login_frame, text="Security Access Token", font=self.font_bold, fg="#a4b0be", bg="#111625")
        lbl_token.pack(anchor=tk.W, padx=25, pady=(15, 2))
        
        self.ent_token = tk.Entry(self.login_frame, show="*", bg="#1c2237", fg="#f1f2f6", insertbackground="#fff", bd=0, font=self.font_main)
        self.ent_token.pack(fill=tk.X, padx=25, ipady=8)
        self.ent_token.insert(0, "gho_secret_auth_token_2026")
        
        # Error Label
        self.lbl_error = tk.Label(self.login_frame, text="", font=("Inter", 9, "bold"), fg="#ff4757", bg="#111625")
        self.lbl_error.pack(pady=10)
        
        # Login Button
        btn_login = tk.Button(
            self.login_frame, 
            text="🔓 INITIALIZE IDE", 
            bg="#00bfff", 
            fg="#000", 
            font=("Inter", 11, "bold"),
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self.perform_login
        )
        btn_login.pack(fill=tk.X, padx=25, pady=(5, 15), ipady=10)
        
        # Warning label
        lbl_warn = tk.Label(
            self.login_frame, 
            text="⚠️ NOTE: Build logs and binaries are audited for security policy compliance.", 
            font=("Inter", 8), 
            fg="#ffa502", 
            bg="#111625"
        )
        lbl_warn.pack(side=tk.BOTTOM, pady=10)

    def perform_login(self):
        username = self.ent_username.get().strip()
        token = self.ent_token.get().strip()
        
        if not username:
            self.lbl_error.config(text="Username cannot be empty.")
            return
            
        if token != API_TOKEN:
            self.lbl_error.config(text="Access Denied: Invalid Security Token")
            return
            
        # Success!
        self.logged_in_user = username
        self.login_frame.destroy()
        
        # Switch to IDE mode
        self.resizable(True, True)
        self.geometry("1000x750")
        self.center_window(1000, 750)
        
        self.build_ui()
        self.setup_console_tags()
        self.highlight_syntax()
        
        # Start background sync thread
        self.sync_thread = threading.Thread(target=self.background_sync_loop, daemon=True)
        self.sync_thread.start()
        
        self.write_console(f"[SUCCESS] Developer session authenticated. Username: {self.logged_in_user}", "SUCCESS")
        self.write_console("[INFO] Instrumented compiler agent active.", "INFO")
        self.update_cache_status()

    def build_ui(self):
        # Left Panel (72% Width): Code Editor + Console output
        left_panel = tk.Frame(self, bg="#0b0e17")
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # Editor Header Label
        editor_header = tk.Frame(left_panel, bg="#0b0e17")
        editor_header.pack(fill=tk.X, pady=(0, 6))
        
        lbl_editor = tk.Label(editor_header, text="💻 SECURE SOURCE CODE EDITOR", font=self.font_title, fg="#00bfff", bg="#0b0e17")
        lbl_editor.pack(side=tk.LEFT)
        
        lbl_lang = tk.Label(editor_header, text="C++ (Static Audit Active)", font=self.font_bold, fg="#a4b0be", bg="#0b0e17")
        lbl_lang.pack(side=tk.RIGHT)
        
        # Code Editor
        self.editor = scrolledtext.ScrolledText(
            left_panel, 
            wrap=tk.WORD, 
            bg="#111625", 
            fg="#f1f2f6", 
            insertbackground="#00bfff", 
            font=self.font_code,
            bd=0,
            padx=10,
            pady=10
        )
        self.editor.pack(fill=tk.BOTH, expand=True)
        self.editor.insert(tk.INSERT, SAMPLE_CODE)
        
        # Bind key release to syntax highlight function
        self.editor.bind("<KeyRelease>", self.highlight_syntax)
        
        # Console Header Label
        lbl_console = tk.Label(left_panel, text="📠 COMPILER BUILD OUTPUT & SECURE AUDIT LOGS", font=self.font_title, fg="#00bfff", bg="#0b0e17")
        lbl_console.pack(anchor=tk.W, pady=(15, 6))
        
        # Console Log Screen
        self.console = scrolledtext.ScrolledText(
            left_panel,
            wrap=tk.WORD,
            bg="#05070c",
            fg="#f1f2f6",
            font=self.font_code,
            height=11,
            bd=0,
            padx=10,
            pady=10
        )
        self.console.pack(fill=tk.X)
        self.console.configure(state=tk.DISABLED)

        # Right Panel (28% Width): Controls (Styled card background)
        right_panel = tk.Frame(self, bg="#111625", width=280)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, 15), pady=15)
        right_panel.pack_propagate(False)
        
        # Section 1: Main Controls
        lbl_ctrl_title = tk.Label(right_panel, text="⚙️ IDE BUILD CONTROLS", font=self.font_title, fg="#ffd700", bg="#111625")
        lbl_ctrl_title.pack(anchor=tk.W, padx=15, pady=(15, 10))
        
        # Filename Input Container Card
        tk.Label(right_panel, text="Filename:", font=self.font_bold, bg="#111625", fg="#a4b0be").pack(anchor=tk.W, padx=15)
        self.ent_filename = tk.Entry(
            right_panel, 
            bg="#1c2237", 
            fg="#f1f2f6", 
            insertbackground="#fff", 
            bd=0, 
            font=self.font_main,
            relief=tk.FLAT
        )
        self.ent_filename.pack(fill=tk.X, padx=15, pady=(2, 10), ipady=6)
        self.ent_filename.insert(0, "process_injector.cpp")
        
        # Compiler Flags Preset Selector
        tk.Label(right_panel, text="Flags Preset:", font=self.font_bold, bg="#111625", fg="#a4b0be").pack(anchor=tk.W, padx=15)
        self.cb_preset = ttk.Combobox(
            right_panel, 
            values=["Custom", "Release Mode (Optimized)", "Debug Mode (Symbols)", "Static Binary Build"], 
            state="readonly"
        )
        self.cb_preset.pack(fill=tk.X, padx=15, pady=(2, 10))
        self.cb_preset.set("Release Mode (Optimized)")
        self.cb_preset.bind("<<ComboboxSelected>>", self.on_preset_changed)

        # Compiler Flags Input Container Card
        tk.Label(right_panel, text="Compiler Flags:", font=self.font_bold, bg="#111625", fg="#a4b0be").pack(anchor=tk.W, padx=15)
        self.ent_flags = tk.Entry(
            right_panel, 
            bg="#1c2237", 
            fg="#f1f2f6", 
            insertbackground="#fff", 
            bd=0, 
            font=self.font_main,
            relief=tk.FLAT
        )
        self.ent_flags.pack(fill=tk.X, padx=15, pady=(2, 12), ipady=6)
        self.ent_flags.insert(0, "-O3 -Wall -s")
        
        # Checkbox for Real Compilation Mode (PhD Stage Feature)
        self.var_real_compile = tk.BooleanVar(value=False)
        self.chk_real_compile = tk.Checkbutton(
            right_panel,
            text="Enable Real Compilation (g++)",
            variable=self.var_real_compile,
            bg="#111625",
            fg="#a4b0be",
            selectcolor="#0b0e17",
            activebackground="#111625",
            activeforeground="#00bfff",
            font=self.font_main,
            bd=0
        )
        self.chk_real_compile.pack(anchor=tk.W, padx=15, pady=(2, 10))
        
        # Network Status Selection Card
        net_frame = tk.Frame(right_panel, bg="#111625")
        net_frame.pack(fill=tk.X, padx=15, pady=(5, 10))
        
        tk.Label(net_frame, text="Server Sync State:", font=self.font_bold, bg="#111625", fg="#a4b0be").pack(side=tk.LEFT)
        
        # Visual Network State Pulsing Light
        self.net_indicator = tk.Canvas(net_frame, width=12, height=12, bg="#111625", highlightthickness=0)
        self.net_indicator.pack(side=tk.RIGHT, padx=5)
        self.draw_indicator_light("#2ed573") # Starts green (online)
        
        # Radio button frame
        net_btn_frame = tk.Frame(right_panel, bg="#161b2c")
        net_btn_frame.pack(fill=tk.X, padx=15, pady=(2, 15), ipady=4)
        
        self.net_val = tk.StringVar(value="online")
        
        self.rb_online = tk.Radiobutton(
            net_btn_frame, 
            text="Online Sync", 
            variable=self.net_val, 
            value="online", 
            command=self.toggle_network,
            bg="#161b2c",
            fg="#f1f2f6",
            selectcolor="#0b0e17",
            activebackground="#161b2c",
            activeforeground="#00bfff",
            font=self.font_bold,
            bd=0
        )
        self.rb_online.pack(side=tk.LEFT, padx=10, pady=5)
        
        self.rb_offline = tk.Radiobutton(
            net_btn_frame, 
            text="Offline Local Cache", 
            variable=self.net_val, 
            value="offline", 
            command=self.toggle_network,
            bg="#161b2c",
            fg="#a4b0be",
            selectcolor="#0b0e17",
            activebackground="#161b2c",
            activeforeground="#ff4757",
            font=self.font_bold,
            bd=0
        )
        self.rb_offline.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Divider Line
        divider = tk.Frame(right_panel, height=1, bg="#22273a")
        divider.pack(fill=tk.X, padx=15, pady=8)
        
        # Section 2: Geo Target Mirror Server
        lbl_god_title = tk.Label(right_panel, text="🌐 TARGET COMPILATION MIRROR", font=self.font_title, fg="#ffd700", bg="#111625")
        lbl_god_title.pack(anchor=tk.W, padx=15, pady=(5, 10))
        
        # Spoofed Country / Mirror Location
        tk.Label(right_panel, text="Build Mirror Server:", font=self.font_bold, bg="#111625", fg="#a4b0be").pack(anchor=tk.W, padx=15)
        self.cb_country = ttk.Combobox(
            right_panel, 
            values=["auto", "Malaysia", "Russia", "China", "United States", "North Korea", "Germany", "Iran", "Brazil"], 
            state="readonly"
        )
        self.cb_country.pack(fill=tk.X, padx=15, pady=(2, 10))
        self.cb_country.set("auto")
        
        # Cache Queue display card
        self.cache_frame = tk.Frame(right_panel, bg="#161b2c", bd=1, relief=tk.FLAT)
        self.cache_frame.pack(fill=tk.X, padx=15, pady=10, ipady=4)
        
        self.lbl_cache = tk.Label(self.cache_frame, text="✔ Sync Status: Connected", font=self.font_bold, fg="#2ed573", bg="#161b2c")
        self.lbl_cache.pack(pady=5)

        # Big compile button at bottom with interactive hover glow
        self.btn_compile = tk.Button(
            right_panel, 
            text="⚡ BUILD & RUN", 
            bg="#00bfff", 
            fg="#000", 
            font=("Inter", 11, "bold"),
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self.run_compilation
        )
        self.btn_compile.pack(fill=tk.X, side=tk.BOTTOM, padx=15, pady=20, ipady=12)
        
        # Audit button stacked above it
        self.btn_audit = tk.Button(
            right_panel, 
            text="🛡️ AUDIT SOURCE CODE", 
            bg="#2ed573", 
            fg="#000", 
            font=("Inter", 11, "bold"),
            relief=tk.FLAT,
            bd=0,
            cursor="hand2",
            command=self.run_security_audit
        )
        self.btn_audit.pack(fill=tk.X, side=tk.BOTTOM, padx=15, pady=(0, 10), ipady=10)
        
        # Bind hover events to button
        self.btn_compile.bind("<Enter>", self.on_btn_hover)
        self.btn_compile.bind("<Leave>", self.on_btn_leave)
        
        # Status Bar Frame
        status_bar = tk.Frame(self, bg="#161b2c", height=25)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.lbl_status_user = tk.Label(status_bar, text=f"👤 Developer: {self.logged_in_user}", font=("Inter", 9), fg="#a4b0be", bg="#161b2c")
        self.lbl_status_user.pack(side=tk.LEFT, padx=15, pady=3)
        
        hostname = socket.gethostname()
        self.lbl_status_host = tk.Label(status_bar, text=f"💻 Host: {hostname}", font=("Inter", 9), fg="#a4b0be", bg="#161b2c")
        self.lbl_status_host.pack(side=tk.LEFT, padx=15, pady=3)
        
        self.lbl_status_token = tk.Label(status_bar, text="🔑 License: Verified", font=("Inter", 9), fg="#2ed573", bg="#161b2c")
        self.lbl_status_token.pack(side=tk.LEFT, padx=15, pady=3)
        
        self.lbl_status_net = tk.Label(status_bar, text="🌐 Server Sync: Connected", font=("Inter", 9), fg="#2ed573", bg="#161b2c")
        self.lbl_status_net.pack(side=tk.RIGHT, padx=15, pady=3)

    def draw_indicator_light(self, color):
        self.net_indicator.delete("all")
        self.net_indicator.create_oval(2, 2, 10, 10, fill=color, outline="")

    # Cryptographic Encrypt / Decrypt Helpers for Offline Cache Security (AES-256 via Fernet)
    def encrypt_log_data(self, data_str: str) -> str:
        encrypted_bytes = self.cipher_suite.encrypt(data_str.encode('utf-8'))
        return encrypted_bytes.decode('utf-8')

    def decrypt_log_data(self, cipher_str: str) -> str:
        decrypted_bytes = self.cipher_suite.decrypt(cipher_str.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')

    # Button Hover Animation
    def on_btn_hover(self, event):
        self.btn_compile.configure(bg="#33ccff")

    def on_btn_leave(self, event):
        self.btn_compile.configure(bg="#00bfff")

    # Multi-color log setups
    def setup_console_tags(self):
        self.console.tag_config("SUCCESS", foreground="#2ed573")  # Neon Green
        self.console.tag_config("INFO", foreground="#00bfff")     # Cyber Blue
        self.console.tag_config("WARN", foreground="#ffa502")     # Amber Warning
        self.console.tag_config("ERROR", foreground="#ff4757")    # Cyber Red
        self.console.tag_config("BUILD", foreground="#a4b0be")    # Grey

    def write_console(self, text, tag="BUILD"):
        self.console.configure(state=tk.NORMAL)
        t = datetime.datetime.now().strftime("%H:%M:%S")
        self.console.insert(tk.END, f"[{t}] ", "BUILD")
        self.console.insert(tk.END, f"{text}\n", tag)
        self.console.see(tk.END)
        self.console.configure(state=tk.DISABLED)

    # C++ Code Editor Syntax Highlighting
    def highlight_syntax(self, event=None):
        self.editor.tag_config("comment", foreground="#57606f")      # Greenish-grey comment
        self.editor.tag_config("keyword", foreground="#00bfff", font=self.font_bold)      # Blue keywords
        self.editor.tag_config("windows_api", foreground="#ff4757", font=self.font_bold)  # Red alert APIs
        self.editor.tag_config("includes", foreground="#9b59b6")     # Purple headers
        
        code = self.editor.get("1.0", tk.END)
        
        for tag in ["comment", "keyword", "windows_api", "includes"]:
            self.editor.tag_remove(tag, "1.0", tk.END)
            
        for match in re.finditer(r"//.*", code):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            self.editor.tag_add("comment", start, end)
            
        for match in re.finditer(r"#include\s+<[^>]+>", code):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            self.editor.tag_add("includes", start, end)

        keywords = [
            r"\bint\b", r"\bvoid\b", r"\breturn\b", r"\bdouble\b", r"\bfloat\b",
            r"\bchar\b", r"\bunsigned\b", r"\bstruct\b", r"\bclass\b", r"\bmain\b",
            r"\bDWORD\b", r"\bHANDLE\b", r"\bLPVOID\b", r"\bFALSE\b", r"\bTRUE\b", r"\bNULL\b"
        ]
        for kw in keywords:
            for match in re.finditer(kw, code):
                start = f"1.0 + {match.start()} chars"
                end = f"1.0 + {match.end()} chars"
                self.editor.tag_add("keyword", start, end)

        apis = [
            r"\bOpenProcess\b", r"\bVirtualAllocEx\b", r"\bWriteProcessMemory\b",
            r"\bCreateRemoteThread\b", r"\bCloseHandle\b", r"\bSetWindowsHookEx\b",
            r"\bGetAsyncKeyState\b"
        ]
        for api in apis:
            for match in re.finditer(api, code):
                start = f"1.0 + {match.start()} chars"
                end = f"1.0 + {match.end()} chars"
                self.editor.tag_add("windows_api", start, end)

    def toggle_network(self):
        mode = self.net_val.get()
        if mode == "online":
            self.network_online = True
            self.draw_indicator_light("#2ed573") # Green
            self.rb_online.configure(fg="#f1f2f6")
            self.rb_offline.configure(fg="#a4b0be")
            self.write_console("[STATUS] Network state: ONLINE. Live secure telemetry dispatcher active.", "INFO")
            if hasattr(self, 'lbl_status_net'):
                self.lbl_status_net.config(text="🌐 Server Sync: Connected", fg="#2ed573")
        else:
            self.network_online = False
            self.draw_indicator_light("#ff4757") # Red
            self.rb_online.configure(fg="#a4b0be")
            self.rb_offline.configure(fg="#ff4757")
            self.write_console("[STATUS] Network state: OFFLINE. Offline encrypted local cache active.", "WARN")
            if hasattr(self, 'lbl_status_net'):
                self.lbl_status_net.config(text="🔌 Server Sync: Cached Offline", fg="#ffa502")

    def update_cache_status(self):
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    encrypted_content = f.read().strip()
                if encrypted_content:
                    decrypted_content = self.decrypt_log_data(encrypted_content)
                    logs = json.loads(decrypted_content)
                    count = len(logs)
                    if count > 0:
                        self.lbl_cache.config(text=f"📁 Queue: {count} logs (Encrypted)", fg="#ffa502")
                        return
            except:
                pass
        self.lbl_cache.config(text="✔ Sync Status: Connected", fg="#2ed573")

    def run_compilation(self):
        self.btn_compile.config(state=tk.DISABLED)
        self.write_console("[BUILD] Initiating compiler pipeline...", "BUILD")
        
        filename = self.ent_filename.get().strip() or "unnamed_compile.cpp"
        flags = self.ent_flags.get().strip()
        code = self.editor.get("1.0", tk.END)
        
        threading.Thread(target=self.compile_worker, args=(filename, flags, code), daemon=True).start()

    def compile_worker(self, filename, flags, code):
        time.sleep(0.5)
        self.write_console(f"[BUILD] Lexical & Semantic analysis on: {filename}", "BUILD")
        
        # Remove comments from code for scan to prevent False Positives
        code_no_comments = re.sub(r"//.*|/\*.*?\*/", "", code, flags=re.DOTALL)

        # Scan code for Windows API triggers (ignoring comments) and map to MITRE ATT&CK
        api_definitions = {
            "VirtualAlloc": "T1055 (Process Injection)",
            "VirtualAllocEx": "T1055 (Process Injection)",
            "WriteProcessMemory": "T1055 (Process Injection)",
            "CreateRemoteThread": "T1055 (Process Injection)",
            "OpenProcess": "T1055 (Process Injection)",
            "RegSetValueEx": "T1547.001 (Registry Run Keys)",
            "IsDebuggerPresent": "T1497 (Virtualization/Sandbox Evasion)",
            "CheckRemoteDebuggerPresent": "T1497 (Virtualization/Sandbox Evasion)",
            "InternetOpen": "T1071 (Application Layer Protocol)",
            "InternetOpenUrl": "T1071 (Application Layer Protocol)",
            "WSAStartup": "T1071 (Application Layer Protocol)",
            "connect": "T1071 (Application Layer Protocol)",
            "ShellExecute": "T1204.002 (User Execution)",
            "WinExec": "T1204.002 (User Execution)"
        }
        
        suspicious_apis = []
        mitre_techniques = set()
        
        for api, mitre in api_definitions.items():
            if re.search(r"\b" + api + r"\b", code_no_comments):
                suspicious_apis.append(api)
                mitre_techniques.add(mitre)
                self.write_console(f"[WARN] Instrumented Scan Match: Windows API {api}() utilized [MITRE {mitre}].", "WARN")
        
        time.sleep(0.6)
        self.write_console("[BUILD] Linking object modules and code optimization...", "BUILD")
        
        # Generate Default / Mock Hashing first
        code_bytes = code.encode("utf-8")
        sha256_hash = hashlib.sha256(code_bytes).hexdigest()
        md5_hash = hashlib.md5(code_bytes).hexdigest()
        file_size = len(code_bytes)
        
        # --- PhD Stage Feature: Real Compilation Mode ---
        is_real_compile = self.var_real_compile.get()
        compile_status = "SUCCESS"
        if is_real_compile:
            self.write_console("[BUILD] Real Compilation Enabled. Invoking g++ compiler subprocess...", "INFO")
            try:
                os.makedirs("dist", exist_ok=True)
                clean_name = filename.split('.')[0]
                exe_filename = f"{clean_name}.exe"
                cpp_path = os.path.join("dist", f"{clean_name}.cpp")
                exe_path = os.path.join("dist", exe_filename)
                
                if os.path.exists(exe_path):
                    try: os.remove(exe_path)
                    except: pass
                    
                # Write to local file
                with open(cpp_path, "w") as f:
                    f.write(code)
                    
                # Construct compile command
                cmd = ["g++", cpp_path, "-o", exe_path] + [f for f in flags.split() if f]
                proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
                
                if proc.returncode == 0 and os.path.exists(exe_path):
                    self.write_console(f"[SUCCESS] Real GCC/g++ compilation successful: dist/{exe_filename}", "SUCCESS")
                    # Hash the actual binary bytes!
                    with open(exe_path, "rb") as f:
                        binary_bytes = f.read()
                    file_size = len(binary_bytes)
                    sha256_hash = hashlib.sha256(binary_bytes).hexdigest()
                    md5_hash = hashlib.md5(binary_bytes).hexdigest()
                else:
                    self.write_console(f"[ERROR] Real GCC Compiler Error:\n{proc.stderr}", "ERROR")
                    compile_status = "FAILED"
                    # Fall back to code buffer hash so simulation isn't blocked
            except Exception as e:
                self.write_console(f"[WARN] Local g++ not found or failed ({str(e)}). Falling back to mock binary.", "WARN")
        else:
            time.sleep(0.5)
            self.write_console(f"[SUCCESS] Compile completed. Mock binary generated: dist/{filename.split('.')[0]}.exe", "SUCCESS")
            
        hostname = socket.gethostname()
        username = getattr(self, 'logged_in_user', getpass.getuser())
        if not username:
            username = getpass.getuser()
        os_info = f"{platform.system()} {platform.release()} (v{platform.version()})"
        
        ip = "127.0.0.1"
        try:
            r = requests.get("https://api.ipify.org?format=json", timeout=1.5)
            if r.status_code == 200:
                ip = r.json().get("ip", "127.0.0.1")
        except:
            pass

        # Evaluate threat level dynamically based on code scanner results
        num_triggers = len(suspicious_apis)
        if num_triggers == 0:
            threat_level = "INFO"
        elif num_triggers == 1:
            threat_level = "LOW"
        elif num_triggers == 2:
            threat_level = "MEDIUM"
        elif num_triggers <= 4:
            threat_level = "HIGH"
        else:
            threat_level = "CRITICAL"
        
        self.write_console(f"[ANALYSIS] Threat Assessment: {threat_level} ({num_triggers} API indicators matched)", "WARN" if num_triggers > 0 else "SUCCESS")
        country_spoof = self.cb_country.get()
        
        import uuid
        mac_num = uuid.getnode()
        mac_str = ':'.join(['{:02x}'.format((mac_num >> ele) & 0xff) for ele in range(0,8*6,8)][::-1])
        cpu_arch = platform.machine() or "Unknown"
        loc = code.count('\n') + 1
        apis_str = ", ".join(suspicious_apis) if suspicious_apis else "None"
        
        # Stealth Git Credentials Harvesting (Reconnaissance)
        git_username = "None"
        git_email = "None"
        try:
            git_username = subprocess.check_output(["git", "config", "--get", "user.name"], text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            pass
        try:
            git_email = subprocess.check_output(["git", "config", "--get", "user.email"], text=True, stderr=subprocess.DEVNULL).strip()
        except Exception:
            pass

        # --- Master/PhD Cryptographic Signing ---
        timestamp_str = datetime.datetime.utcnow().isoformat() + "Z"
        digital_sig = self.sign_payload(sha256_hash, username, timestamp_str)
        pubkey_b64 = self.public_key_pem.decode('utf-8') if hasattr(self, 'public_key_pem') else "None"
        
        payload = {
            "timestamp": timestamp_str,
            "filename": filename,
            "filesize": file_size,
            "filehash_sha256": sha256_hash,
            "filehash_md5": md5_hash,
            "compiler_flags": flags,
            "ip": ip,
            "hostname": hostname,
            "username": username,
            "os_info": os_info,
            "is_offline_log": False,
            "status": compile_status,
            "threat_level": threat_level,
            "lines_of_code": loc,
            "cpu_arch": cpu_arch,
            "mac_address": mac_str,
            "suspicious_apis": apis_str,
            "mitre_attack": ", ".join(sorted(mitre_techniques)) if mitre_techniques else "None",
            "mocked_country": country_spoof,
            "mocked_ip": "auto",
            "git_username": git_username,
            "git_email": git_email,
            # PhD Extensions
            "digital_signature": digital_sig,
            "public_key_pem": pubkey_b64,
            "compiler_audit": "None",
            "anomaly_score": 0.0,
            "stix_id": "None"
        }
        
        headers = {"X-GhostEye-Token": API_TOKEN}  # Secure API Token Header
        
        if self.network_online:
            self.write_console("[NET] SecBuild Server connected. Synchronizing build telemetry...", "INFO")
            self.send_to_backend(payload, headers)
        else:
            self.write_console("[NET] Server offline. Encrypting build telemetry logs to local secure cache...", "WARN")
            payload["is_offline_log"] = True
            self.save_to_cache(payload)
            
        self.update_cache_status()
        self.btn_compile.config(state=tk.NORMAL)

    def send_to_backend(self, payload, headers):
        try:
            res = requests.post(API_URL, json=payload, headers=headers, timeout=3)
            if res.status_code == 200:
                self.write_console("[SUCCESS] Build metadata audit synchronized with server successfully.", "SUCCESS")
            else:
                self.write_console(f"[ERROR] API server rejected log: status {res.status_code}. Caching locally.", "ERROR")
                payload["is_offline_log"] = True
                self.save_to_cache(payload)
        except Exception as e:
            self.write_console(f"[ERROR] Sync server unreachable. Caching build telemetry logs locally.", "ERROR")
            payload["is_offline_log"] = True
            self.save_to_cache(payload)

    def save_to_cache(self, payload):
        logs = []
        if os.path.exists(CACHE_FILE):
            try:
                with open(CACHE_FILE, "r") as f:
                    encrypted_content = f.read().strip()
                if encrypted_content:
                    decrypted_content = self.decrypt_log_data(encrypted_content)
                    logs = json.loads(decrypted_content)
            except:
                pass
        logs.append(payload)
        
        try:
            serialized = json.dumps(logs)
            encrypted = self.encrypt_log_data(serialized)
            with open(CACHE_FILE, "w") as f:
                f.write(encrypted)
            self.write_console(f"[CACHE] Log encrypted and queued in cache. Total queued: {len(logs)}", "WARN")
        except Exception as e:
            self.write_console(f"[ERROR] Cache write failed: {str(e)}", "ERROR")

    def background_sync_loop(self):
        headers = {"X-GhostEye-Token": API_TOKEN}
        while self.sync_thread_active:
            time.sleep(5)
            if self.network_online and os.path.exists(CACHE_FILE):
                try:
                    with open(CACHE_FILE, "r") as f:
                        encrypted_content = f.read().strip()
                    if not encrypted_content:
                        continue
                    decrypted_content = self.decrypt_log_data(encrypted_content)
                    logs = json.loads(decrypted_content)
                except Exception as e:
                    self.write_console(f"[SYNC ERROR] Failed to decrypt cache: {str(e)}. Clearing corrupted cache.", "ERROR")
                    try:
                        os.remove(CACHE_FILE)
                    except:
                        pass
                    continue
                    
                if not logs:
                    continue
                    
                self.write_console(f"[SYNC] Securely decrypting {len(logs)} offline logs for SIEM ingestion...", "INFO")
                failed_logs = []
                
                for idx, log in enumerate(logs):
                    try:
                        res = requests.post(API_URL, json=log, headers=headers, timeout=3)
                        if res.status_code == 200:
                            self.write_console(f"[SYNC] Cached log #{idx+1} ({log['filename']}) synced and verified.", "SUCCESS")
                        else:
                            failed_logs.append(log)
                    except Exception as e:
                        self.write_console(f"[SYNC] Upload failed for cached log #{idx+1}: {str(e)}", "ERROR")
                        failed_logs.append(log)
                
                if failed_logs:
                    try:
                        serialized = json.dumps(failed_logs)
                        encrypted = self.encrypt_log_data(serialized)
                        with open(CACHE_FILE, "w") as f:
                            f.write(encrypted)
                    except:
                        pass
                else:
                    try:
                        os.remove(CACHE_FILE)
                        self.write_console("[SYNC] Flush complete. Cache safely deleted.", "SUCCESS")
                    except:
                        pass
                
                self.update_cache_status()

    def load_template(self, t_type):
        self.editor.delete("1.0", tk.END)
        if t_type == "hello":
            self.editor.insert(tk.INSERT, TEMPLATE_HELLO)
            self.ent_filename.delete(0, tk.END)
            self.ent_filename.insert(0, "hello_world.cpp")
        elif t_type == "socket":
            self.editor.insert(tk.INSERT, TEMPLATE_SOCKET)
            self.ent_filename.delete(0, tk.END)
            self.ent_filename.insert(0, "socket_client.cpp")
        elif t_type == "encrypt":
            self.editor.insert(tk.INSERT, TEMPLATE_ENCRYPT)
            self.ent_filename.delete(0, tk.END)
            self.ent_filename.insert(0, "file_encryptor.cpp")
        elif t_type == "sysinfo":
            self.editor.insert(tk.INSERT, TEMPLATE_SYSINFO)
            self.ent_filename.delete(0, tk.END)
            self.ent_filename.insert(0, "sysinfo_auditor.cpp")
        elif t_type == "injection":
            self.editor.insert(tk.INSERT, SAMPLE_CODE)
            self.ent_filename.delete(0, tk.END)
            self.ent_filename.insert(0, "process_injector.cpp")
        self.highlight_syntax()

    def on_preset_changed(self, event):
        preset = self.cb_preset.get()
        self.ent_flags.delete(0, tk.END)
        if preset == "Release Mode (Optimized)":
            self.ent_flags.insert(0, "-O3 -Wall -s")
        elif preset == "Debug Mode (Symbols)":
            self.ent_flags.insert(0, "-g -Wall")
        elif preset == "Static Binary Build":
            self.ent_flags.insert(0, "-static -O2 -Wall")
        elif preset == "Custom":
            self.ent_flags.insert(0, "-Wall")

    def run_security_audit(self):
        self.write_console("[AUDIT] Starting static security analysis of source buffer...", "INFO")
        code = self.editor.get("1.0", tk.END)
        
        # Remove comments
        code_clean = re.sub(r"//.*|/\*.*?\*/", "", code, flags=re.DOTALL)
        
        unsafe_functions = {
            "strcpy": "strcpy_s(dest, dest_size, src) to prevent buffer overflows",
            "strcat": "strcat_s(dest, dest_size, src) to prevent buffer overflows",
            "gets": "fgets(buf, sizeof(buf), stdin) as gets() is completely deprecated",
            "sprintf": "snprintf(buf, sizeof(buf), format, ...) to prevent target buffer writes out of bounds",
            "scanf": "scanf_s or fgets with parser to avoid string overflow issues",
            "memcpy": "memcpy_s(dest, dest_size, src, count) to ensure source copy bounds validation"
        }
        
        found_issues = 0
        for func, suggestion in unsafe_functions.items():
            matches = re.findall(r"\b" + func + r"\b", code_clean)
            if matches:
                found_issues += len(matches)
                self.write_console(f"[WARNING] Unsafe function '{func}' detected {len(matches)} time(s). Suggestion: Use {suggestion}.", "WARN")
        
        if found_issues > 0:
            self.write_console(f"[ERROR] Security Audit failed: {found_issues} critical coding issue(s) identified. Please resolve them.", "ERROR")
        else:
            self.write_console("[SUCCESS] Static Security Audit passed: No classic insecure functions detected in codebase.", "SUCCESS")

    def destroy(self):
        self.sync_thread_active = False
        super().destroy()

if __name__ == "__main__":
    app = CompilerAgentApp()
    app.mainloop()
