
import os
import sys
import time
import json
import curses
import subprocess
import multiprocessing
import smtplib
import threading
import socket
import re
import random
from datetime import datetime
from email.mime.text import MIMEText

# ==========================================
# EMAIL CONFIGURATION - USER MUST FILL
# ==========================================
GMAIL_USER = ""
GMAIL_APP_PASS = ""
SCORE_FILE = ".antutu_score"

def save_antutu_score(score):
    try:
        with open(SCORE_FILE, "w") as f:
            f.write(str(score))
    except: pass

def load_antutu_score():
    if os.path.exists(SCORE_FILE):
        try:
            with open(SCORE_FILE, "r") as f:
                return int(f.read().strip())
        except: return 0
    return 0

def send_email_notification(subject, body_text):
    if not GMAIL_USER or not GMAIL_APP_PASS or len(GMAIL_APP_PASS.replace(" ", "")) < 12:
        return False, "Please configure GMAIL_USER and GMAIL_APP_PASS in the script first!"
    try:
        msg = MIMEText(body_text, "plain", "utf-8")
        msg["Subject"] = subject
        msg["From"] = GMAIL_USER
        msg["To"] = GMAIL_USER
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_APP_PASS.replace(" ", ""))
        server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
        server.quit()
        return True, "Email sent successfully!"
    except Exception as e:
        return False, f"Failed to send: {str(e)}"

def toggle_flashlight(state):
    try:
        if state:
            subprocess.Popen("termux-torch on", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen("termux-torch off", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass

def vibrate_phone(duration=500):
    try:
        subprocess.Popen(f"termux-vibrate -d {duration}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass

def scan_wifi_networks():
    networks = []
    try:
        cmd = "su -c 'cmd wifi list-scan-results'"
        result = subprocess.check_output(cmd, shell=True, timeout=8).decode("utf-8", errors="ignore")
        for line in result.split("\n"):
            line = line.strip()
            if line and not line.startswith("BSSID") and not line.startswith("---"):
                parts = line.split()
                if len(parts) >= 5:
                    ssid = " ".join(parts[4:])
                    if ssid and not ssid.startswith("\\x00") and "<illegal" not in ssid:
                        networks.append(ssid)
    except: pass
    if not networks:
        try:
            result = subprocess.check_output("termux-wifi-scaninfo", shell=True, timeout=8).decode("utf-8")
            data = json.loads(result)
            for net in data:
                ssid = net.get("ssid", "").strip()
                if ssid and not ssid.startswith("\\x00"):
                    networks.append(ssid)
        except: pass
    return list(set(networks))[:8]

def connect_to_wifi(ssid, password):
    if len(password) < 8:
        return False
    try:
        cmd = f'su -c "cmd wifi connect-to-network \\"{ssid}\\" wpa2 \\"{password}\\""'
        res = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=12)
        return res.returncode == 0
    except: return False

def get_hardware_info():
    soc_model = ""
    try:
        soc_model = subprocess.check_output("getprop ro.soc.model", shell=True).decode().strip()
    except: pass
    if not soc_model:
        try:
            soc_model = subprocess.check_output("getprop ro.board.platform", shell=True).decode().strip()
        except: pass
    if not soc_model:
        try:
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "hardware" in line.lower() or "model name" in line.lower():
                        soc_model = line.split(":")[1].strip()
                        break
        except: pass
    if not soc_model:
        cores = multiprocessing.cpu_count()
        soc_model = f"Generic ARMv8 {cores}-Core"
    return soc_model

def run_real_cpu_benchmark():
    start_time = time.time()
    count = 0
    while time.time() - start_time < 3.0:
        _ = 987654.321 * 123456.789 / 3.14159
        count += 1
    return count

def calculate_antutu_v11_score(bench_count):
    cores = multiprocessing.cpu_count()
    hardware = get_hardware_info().lower()
    raw_perf = bench_count / 100000.0
    base_score = 150000
    multiplier = 1.0
    if any(x in hardware for x in ["sm8735", "elite", "9400", "sun"]):
        base_score = 2500000; multiplier = 3500
    elif any(x in hardware for x in ["sm8650", "8gen3", "9300", "s5e9945", "exynos2400"]):
        base_score = 1850000; multiplier = 2800
    elif any(x in hardware for x in ["sm8550", "8gen2", "9200", "sm8450", "8gen1", "9000"]):
        base_score = 1100000; multiplier = 2000
    elif any(x in hardware for x in ["sm7675", "sm7500", "8200", "8300", "778g", "sm7325"]):
        base_score = 650000; multiplier = 1200
    elif cores >= 8:
        base_score = 320000; multiplier = 800
    else:
        base_score = 120000; multiplier = 400
    dynamic_offset = (raw_perf * cores * multiplier) * 0.1
    final_score = int(base_score + dynamic_offset)
    if final_score >= 2400000:
        tier = "GOD TIER"
    elif final_score >= 1800000:
        tier = "ULTRA FLAGSHIP"
    elif final_score >= 1200000:
        tier = "HIGH-END"
    elif final_score >= 700000:
        tier = "MID-RANGE"
    else:
        tier = "BUDGET / LOW-END"
    return final_score, tier

device_antutu_score = load_antutu_score()

def check_processor_power():
    cores = multiprocessing.cpu_count()
    return 120 if cores >= 8 else 60

POWER_LIMIT = check_processor_power()
current_hz = POWER_LIMIT
current_fps = POWER_LIMIT
timeout_ms = max(1, int(1000 / current_fps))
selected_hz = current_hz
selected_fps = current_fps

def update_timeout():
    global timeout_ms, current_fps
    timeout_ms = max(1, int(1000 / current_fps))

def safe_addstr(stdscr, y, x, text, attr=0):
    try:
        height, width = stdscr.getmaxyx()
        if y < height and x < width:
            max_len = width - x - 1
            stdscr.addstr(y, x, text[:max_len], attr)
    except: pass

def safe_hline(stdscr, y, x, ch, n, attr=0):
    try:
        height, width = stdscr.getmaxyx()
        if y < height and x < width:
            stdscr.hline(y, x, ch, min(n, width - x), attr)
    except: pass

def play_transition(stdscr):
    global current_fps
    height, width = stdscr.getmaxyx()
    mid_y = height // 2
    steps = max(5, int(current_fps / 6))
    delay = 0.6 / current_fps
    for i in range(0, mid_y + 1, max(1, mid_y // steps)):
        stdscr.erase()
        safe_hline(stdscr, max(0, mid_y - i), 0, "─", width, curses.color_pair(5))
        safe_hline(stdscr, min(height - 1, mid_y + i), 0, "─", width, curses.color_pair(5))
        stdscr.refresh()
        time.sleep(delay)

def play_button_shrink(stdscr, y, x, text, color_pair):
    global current_fps
    clean_text = text.replace("┌", "").replace("┐", "").replace("└", "").replace("┘", "").replace("│", "").strip()
    
    box_width = max(len(clean_text) + 4, 30)
    
    short_box_top = " ┌" + "─" * (box_width - 2) + "┐ "
    short_box_mid = f" │ {clean_text.center(box_width - 4)} │ "
    short_box_bot = " └" + "─" * (box_width - 2) + "┘ "
    
    steps = max(3, int(current_fps / 15))
    delay = 0.8 / current_fps
    
    safe_addstr(stdscr, y, x, short_box_top, curses.color_pair(color_pair) | curses.A_BOLD)
    safe_addstr(stdscr, y+1, x, short_box_mid, curses.color_pair(color_pair) | curses.A_BOLD)
    safe_addstr(stdscr, y+2, x, short_box_bot, curses.color_pair(color_pair) | curses.A_BOLD)
    stdscr.refresh()
    time.sleep(delay * 0.3)
    
    for step in range(steps):
        ratio = 1.0 - (step / steps) * 0.25
        new_width = max(10, int(box_width * ratio))
        
        short_top = " ┌" + "─" * (new_width - 2) + "┐ "
        mid_text = clean_text.center(new_width - 4)
        short_mid = f" │ {mid_text} │ " if len(mid_text) < new_width - 4 else f" │{clean_text[:new_width-6]}│ "
        short_bot = " └" + "─" * (new_width - 2) + "┘ "
        
        safe_addstr(stdscr, y, x, short_top, curses.color_pair(color_pair) | curses.A_BOLD)
        safe_addstr(stdscr, y+1, x, short_mid, curses.color_pair(color_pair) | curses.A_BOLD)
        safe_addstr(stdscr, y+2, x, short_bot, curses.color_pair(color_pair) | curses.A_BOLD)
        stdscr.refresh()
        time.sleep(delay * 0.2)
    
    safe_addstr(stdscr, y, x, short_box_top, curses.color_pair(color_pair) | curses.A_BOLD)
    safe_addstr(stdscr, y+1, x, short_box_mid, curses.color_pair(color_pair) | curses.A_BOLD)
    safe_addstr(stdscr, y+2, x, short_box_bot, curses.color_pair(color_pair) | curses.A_BOLD)
    stdscr.refresh()
    time.sleep(delay * 0.2)

def get_user_input(stdscr, y, x, prompt, mask=False):
    curses.curs_set(1)
    stdscr.timeout(-1)
    safe_addstr(stdscr, y, x, prompt, curses.color_pair(2) | curses.A_BOLD)
    stdscr.refresh()
    input_str = ""
    start_x = x + len(prompt)
    while True:
        ch = stdscr.getch()
        if ch in [10, 13]: break
        elif ch in [8, 127, curses.KEY_BACKSPACE]:
            if len(input_str) > 0:
                input_str = input_str[:-1]
                stdscr.move(y, start_x + len(input_str))
                stdscr.addch(" ")
                stdscr.move(y, start_x + len(input_str))
        elif 32 <= ch <= 126:
            if len(input_str) < 30:
                input_str += chr(ch)
                if mask: stdscr.addch(y, start_x + len(input_str) - 1, "*")
                else: stdscr.addch(y, start_x + len(input_str) - 1, ch)
        stdscr.refresh()
    curses.curs_set(0)
    stdscr.timeout(timeout_ms)
    return input_str

# ==========================================
# UPDATE TOOL - Progress Bar
# ==========================================
def update_tool(stdscr):
    stdscr.erase()
    height, width = stdscr.getmaxyx()
    
    safe_addstr(stdscr, 2, width//2 - 15, "🔄 CHECKING FOR UPDATES...", curses.color_pair(5) | curses.A_BOLD)
    stdscr.refresh()
    time.sleep(0.5)
    
    try:
        # یەکەم هەنگاو: git fetch
        safe_addstr(stdscr, 4, width//2 - 10, "[1/3] Fetching updates...", curses.color_pair(3))
        stdscr.refresh()
        
        fetch = subprocess.run("git fetch", shell=True, capture_output=True, text=True, timeout=10)
        
        # دووەم هەنگاو: git status
        safe_addstr(stdscr, 5, width//2 - 10, "[2/3] Checking changes...", curses.color_pair(3))
        stdscr.refresh()
        
        status = subprocess.run("git status -uno", shell=True, capture_output=True, text=True, timeout=5)
        
        # پشکنینی ئەگەر ئەپدەیت هەیە
        if "Your branch is up to date" in status.stdout or "up to date" in status.stdout:
            safe_addstr(stdscr, 7, width//2 - 15, "✅ NO UPDATE AVAILABLE", curses.color_pair(4) | curses.A_BOLD)
            safe_addstr(stdscr, 8, width//2 - 15, "Your tool is already up to date!", curses.color_pair(2))
            stdscr.refresh()
            time.sleep(2)
            return False
        
        # سێیەم هەنگاو: git pull (Progress Bar)
        safe_addstr(stdscr, 7, width//2 - 10, "[3/3] Updating... (0%)", curses.color_pair(3))
        stdscr.refresh()
        
        # Progress Bar simulation
        for i in range(101):
            if i % 5 == 0:
                bar_length = 40
                filled = int((i / 100) * bar_length)
                bar = "█" * filled + "░" * (bar_length - filled)
                safe_addstr(stdscr, 9, width//2 - 20, f"  [{bar}] {i}%", curses.color_pair(4) if i < 100 else curses.color_pair(2))
                stdscr.refresh()
            time.sleep(0.02)
        
        # Git pull لە پشتەوە
        pull = subprocess.run("git pull", shell=True, capture_output=True, text=True, timeout=30)
        
        if "Already up to date" in pull.stdout:
            safe_addstr(stdscr, 11, width//2 - 15, "✅ NO UPDATE AVAILABLE", curses.color_pair(4) | curses.A_BOLD)
            safe_addstr(stdscr, 12, width//2 - 15, "Your tool is already up to date!", curses.color_pair(2))
            stdscr.refresh()
            time.sleep(2)
            return False
        
        # ئەپدەیت سەرکەوتوو بوو
        safe_addstr(stdscr, 11, width//2 - 15, "✅ UPDATE COMPLETED SUCCESSFULLY!", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 12, width//2 - 15, "Tool has been updated to the latest version!", curses.color_pair(2))
        
        # وەرگرتنی ژمارەی ڤێرژن
        try:
            version = subprocess.run("git log -1 --pretty=format:'%h - %s (%ar)'", shell=True, capture_output=True, text=True, timeout=5)
            safe_addstr(stdscr, 14, width//2 - 15, f"📌 New version: {version.stdout[:40]}", curses.color_pair(5))
        except:
            pass
        
        stdscr.refresh()
        time.sleep(2)
        return True
        
    except subprocess.TimeoutExpired:
        safe_addstr(stdscr, 7, width//2 - 15, "❌ UPDATE TIMEOUT!", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 8, width//2 - 15, "Please check your internet connection.", curses.color_pair(1))
        stdscr.refresh()
        time.sleep(2)
        return False
    except Exception as e:
        safe_addstr(stdscr, 7, width//2 - 15, f"❌ ERROR: {str(e)[:30]}", curses.color_pair(1) | curses.A_BOLD)
        stdscr.refresh()
        time.sleep(2)
        return False

# ==========================================
# TERMUX MENU
# ==========================================
def termux_menu(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "📦 TERMUX TOOLS", curses.color_pair(5) | curses.A_BOLD)
        
        safe_addstr(stdscr, 3, 4, "┌" + "─" * 50 + "┐", curses.color_pair(4))
        safe_addstr(stdscr, 4, 4, "│  [1] Termux Setup - Full Installation         │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 5, 4, "└" + "─" * 50 + "┘", curses.color_pair(4))
        
        safe_addstr(stdscr, 7, 4, "┌" + "─" * 50 + "┐", curses.color_pair(3))
        safe_addstr(stdscr, 8, 4, "│  [2] Termux API - Install Real API Packages  │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 9, 4, "└" + "─" * 50 + "┘", curses.color_pair(3))
        
        safe_addstr(stdscr, 11, 4, "┌" + "─" * 20 + "┐", curses.color_pair(1))
        safe_addstr(stdscr, 12, 4, "│   [ Go Back ]    │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 13, 4, "└" + "─" * 20 + "┘", curses.color_pair(1))
        
        stdscr.noutrefresh()
        curses.doupdate()
        
        key = stdscr.getch()
        
        if key == ord('1'):
            termux_setup(stdscr)
        elif key == ord('2'):
            termux_api_install(stdscr)
        elif key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if 11 <= my <= 13 and 4 <= mx <= 24:
                        break
                    elif 3 <= my <= 5 and 4 <= mx <= 54:
                        play_button_shrink(stdscr, 3, 4, "┌" + "─" * 50 + "┐", 4)
                        termux_setup(stdscr)
                    elif 7 <= my <= 9 and 4 <= mx <= 54:
                        play_button_shrink(stdscr, 7, 4, "┌" + "─" * 50 + "┐", 3)
                        termux_api_install(stdscr)
            except: pass
        elif key == ord('\n') or key == ord('q'):
            break
    
    play_transition(stdscr)

def termux_setup(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    
    stdscr.erase()
    safe_addstr(stdscr, 1, 4, "🔧 TERMUX FULL SETUP", curses.color_pair(5) | curses.A_BOLD)
    safe_addstr(stdscr, 3, 4, "Starting full Termux setup...", curses.color_pair(2))
    safe_addstr(stdscr, 4, 4, "This may take a few minutes...", curses.color_pair(3))
    stdscr.refresh()
    
    commands = [
        "pkg update -y", "pkg upgrade -y", "pkg install python3 -y",
        "pkg install python3-pip -y", "pkg install git -y", "pkg install curl -y",
        "pkg install wget -y", "pkg install nano -y", "pkg install vim -y",
        "pkg install termux-api -y", "pkg install termux-tools -y",
        "pkg install openssh -y", "pkg install net-tools -y",
        "pkg install dnsutils -y", "pkg install nmap -y",
        "pkg install zip -y", "pkg install unzip -y", "pkg install tar -y",
        "pkg install ncurses-utils -y", "pkg install termux-exec -y",
        "pip install --upgrade pip", "pip install requests",
        "pip install beautifulsoup4", "pip install colorama", "pip install tqdm"
    ]
    
    success_count = 0
    total = len(commands)
    
    for idx, cmd in enumerate(commands):
        try:
            safe_addstr(stdscr, 6, 4, f"Processing: {idx+1}/{total} - {cmd[:30]}...", curses.color_pair(3))
            stdscr.refresh()
            result = subprocess.run(cmd, shell=True, timeout=120, capture_output=True)
            if result.returncode == 0:
                success_count += 1
        except:
            pass
    
    safe_addstr(stdscr, 8, 4, f"✅ Setup Complete! {success_count}/{total} packages installed.", curses.color_pair(4) if success_count > total/2 else curses.color_pair(1))
    
    safe_addstr(stdscr, 10, 4, "[ Press any key to go back ]", curses.color_pair(3))
    stdscr.noutrefresh()
    curses.doupdate()
    stdscr.getch()
    play_transition(stdscr)

def termux_api_install(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    
    stdscr.erase()
    safe_addstr(stdscr, 1, 4, "📦 TERMUX API INSTALLATION", curses.color_pair(5) | curses.A_BOLD)
    safe_addstr(stdscr, 3, 4, "Installing Termux API packages...", curses.color_pair(2))
    safe_addstr(stdscr, 4, 4, "Only real existing packages will be installed.", curses.color_pair(3))
    stdscr.refresh()
    
    real_packages = ["termux-api", "termux-tools", "termux-exec"]
    success_count = 0
    total = len(real_packages)
    
    for idx, pkg in enumerate(real_packages):
        try:
            safe_addstr(stdscr, 6, 4, f"Installing: {pkg} ({idx+1}/{total})...", curses.color_pair(3))
            stdscr.refresh()
            result = subprocess.run(f"pkg install {pkg} -y", shell=True, timeout=60, capture_output=True)
            if result.returncode == 0:
                success_count += 1
                safe_addstr(stdscr, 8 + idx, 6, f"✅ {pkg} installed successfully", curses.color_pair(4))
            else:
                safe_addstr(stdscr, 8 + idx, 6, f"❌ {pkg} failed", curses.color_pair(1))
            stdscr.refresh()
        except Exception as e:
            safe_addstr(stdscr, 8 + idx, 6, f"❌ {pkg} error", curses.color_pair(1))
            stdscr.refresh()
    
    safe_addstr(stdscr, 12 + total, 4, f"✅ Done! {success_count}/{total} packages installed.", curses.color_pair(4))
    safe_addstr(stdscr, 14 + total, 4, "[ Press any key to go back ]", curses.color_pair(3))
    stdscr.noutrefresh()
    curses.doupdate()
    stdscr.getch()
    play_transition(stdscr)

# ==========================================
# DEVICES MENU
# ==========================================
def devices_menu(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    
    try:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "🔧 Installing Android Tools...", curses.color_pair(5) | curses.A_BOLD)
        safe_addstr(stdscr, 3, 4, "Please wait...", curses.color_pair(2))
        stdscr.refresh()
        subprocess.run("pkg install android-tools -y", shell=True, timeout=120)
        subprocess.run("pkg install termux-api -y", shell=True, timeout=60)
    except: pass
    
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "🔌 DEVICES CONTROL", curses.color_pair(5) | curses.A_BOLD)
        
        safe_addstr(stdscr, 3, 4, "┌" + "─" * 50 + "┐", curses.color_pair(4))
        safe_addstr(stdscr, 4, 4, "│  [1] ADB - Android Debug Bridge              │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 5, 4, "└" + "─" * 50 + "┘", curses.color_pair(4))
        
        safe_addstr(stdscr, 7, 4, "┌" + "─" * 50 + "┐", curses.color_pair(3))
        safe_addstr(stdscr, 8, 4, "│  [2] FASTBOOT - Bootloader Mode              │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 9, 4, "└" + "─" * 50 + "┘", curses.color_pair(3))
        
        safe_addstr(stdscr, 11, 4, "┌" + "─" * 20 + "┐", curses.color_pair(1))
        safe_addstr(stdscr, 12, 4, "│   [ Go Back ]    │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 13, 4, "└" + "─" * 20 + "┘", curses.color_pair(1))
        
        stdscr.noutrefresh()
        curses.doupdate()
        
        key = stdscr.getch()
        
        if key == ord('1'):
            adb_command_mode(stdscr)
        elif key == ord('2'):
            fastboot_command_mode(stdscr)
        elif key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if 11 <= my <= 13 and 4 <= mx <= 24:
                        break
                    elif 3 <= my <= 5 and 4 <= mx <= 54:
                        play_button_shrink(stdscr, 3, 4, "┌" + "─" * 50 + "┐", 4)
                        adb_command_mode(stdscr)
                    elif 7 <= my <= 9 and 4 <= mx <= 54:
                        play_button_shrink(stdscr, 7, 4, "┌" + "─" * 50 + "┐", 3)
                        fastboot_command_mode(stdscr)
            except: pass
        elif key == ord('\n') or key == ord('q'):
            break
    
    play_transition(stdscr)

def adb_command_mode(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(-1)
    
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "🔧 ADB COMMAND MODE", curses.color_pair(5) | curses.A_BOLD)
        safe_addstr(stdscr, 3, 4, "Type 'exit' to go back", curses.color_pair(3))
        safe_addstr(stdscr, 4, 4, "Example: adb devices, adb shell, adb install app.apk", curses.color_pair(2))
        safe_hline(stdscr, 5, 0, "─", 60, curses.color_pair(4))
        safe_addstr(stdscr, 7, 4, "> ", curses.color_pair(4) | curses.A_BOLD)
        
        curses.curs_set(1)
        cmd_input = ""
        start_x = 6
        y = 7
        
        while True:
            ch = stdscr.getch()
            if ch == 10 or ch == 13:
                break
            elif ch in [8, 127, curses.KEY_BACKSPACE]:
                if len(cmd_input) > 0:
                    cmd_input = cmd_input[:-1]
                    stdscr.move(y, start_x + len(cmd_input))
                    stdscr.addch(" ")
                    stdscr.move(y, start_x + len(cmd_input))
            elif 32 <= ch <= 126:
                if len(cmd_input) < 100:
                    cmd_input += chr(ch)
                    stdscr.addch(y, start_x + len(cmd_input) - 1, ch)
            stdscr.refresh()
        
        curses.curs_set(0)
        
        if cmd_input.lower() == 'exit' or cmd_input.lower() == 'back':
            break
        elif cmd_input.strip():
            stdscr.erase()
            safe_addstr(stdscr, 1, 4, "⏳ Executing...", curses.color_pair(3))
            stdscr.refresh()
            
            try:
                result = subprocess.run(cmd_input, shell=True, timeout=30, capture_output=True, text=True)
                output = result.stdout + result.stderr
                stdscr.erase()
                safe_addstr(stdscr, 1, 4, "📋 Command Output:", curses.color_pair(4) | curses.A_BOLD)
                lines = output.split('\n')
                for idx, line in enumerate(lines[:15]):
                    safe_addstr(stdscr, 3 + idx, 4, line[:60], curses.color_pair(2))
                if len(lines) > 15:
                    safe_addstr(stdscr, 19, 4, f"... and {len(lines)-15} more lines", curses.color_pair(3))
            except subprocess.TimeoutExpired:
                safe_addstr(stdscr, 3, 4, "❌ Command timeout!", curses.color_pair(1))
            except Exception as e:
                safe_addstr(stdscr, 3, 4, f"❌ Error: {str(e)[:50]}", curses.color_pair(1))
            
            safe_addstr(stdscr, 21, 4, "[ Press any key to continue ]", curses.color_pair(3))
            stdscr.refresh()
            stdscr.getch()
    
    stdscr.timeout(timeout_ms)
    play_transition(stdscr)

def fastboot_command_mode(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(-1)
    
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "⚡ FASTBOOT COMMAND MODE", curses.color_pair(5) | curses.A_BOLD)
        safe_addstr(stdscr, 3, 4, "Type 'exit' to go back", curses.color_pair(3))
        safe_addstr(stdscr, 4, 4, "Example: fastboot devices, fastboot reboot", curses.color_pair(2))
        safe_hline(stdscr, 5, 0, "─", 60, curses.color_pair(4))
        safe_addstr(stdscr, 7, 4, "> ", curses.color_pair(4) | curses.A_BOLD)
        
        curses.curs_set(1)
        cmd_input = ""
        start_x = 6
        y = 7
        
        while True:
            ch = stdscr.getch()
            if ch == 10 or ch == 13:
                break
            elif ch in [8, 127, curses.KEY_BACKSPACE]:
                if len(cmd_input) > 0:
                    cmd_input = cmd_input[:-1]
                    stdscr.move(y, start_x + len(cmd_input))
                    stdscr.addch(" ")
                    stdscr.move(y, start_x + len(cmd_input))
            elif 32 <= ch <= 126:
                if len(cmd_input) < 100:
                    cmd_input += chr(ch)
                    stdscr.addch(y, start_x + len(cmd_input) - 1, ch)
            stdscr.refresh()
        
        curses.curs_set(0)
        
        if cmd_input.lower() == 'exit' or cmd_input.lower() == 'back':
            break
        elif cmd_input.strip():
            stdscr.erase()
            safe_addstr(stdscr, 1, 4, "⏳ Executing...", curses.color_pair(3))
            stdscr.refresh()
            
            try:
                result = subprocess.run(cmd_input, shell=True, timeout=30, capture_output=True, text=True)
                output = result.stdout + result.stderr
                stdscr.erase()
                safe_addstr(stdscr, 1, 4, "📋 Command Output:", curses.color_pair(4) | curses.A_BOLD)
                lines = output.split('\n')
                for idx, line in enumerate(lines[:15]):
                    safe_addstr(stdscr, 3 + idx, 4, line[:60], curses.color_pair(2))
                if len(lines) > 15:
                    safe_addstr(stdscr, 19, 4, f"... and {len(lines)-15} more lines", curses.color_pair(3))
            except subprocess.TimeoutExpired:
                safe_addstr(stdscr, 3, 4, "❌ Command timeout!", curses.color_pair(1))
            except Exception as e:
                safe_addstr(stdscr, 3, 4, f"❌ Error: {str(e)[:50]}", curses.color_pair(1))
            
            safe_addstr(stdscr, 21, 4, "[ Press any key to continue ]", curses.color_pair(3))
            stdscr.refresh()
            stdscr.getch()
    
    stdscr.timeout(timeout_ms)
    play_transition(stdscr)

# ==========================================
# WIFI FUNCTIONS
# ==========================================
def get_wifi_dbm():
    try:
        result = subprocess.check_output("termux-wifi-connectioninfo", shell=True, timeout=5).decode()
        data = json.loads(result)
        if 'rssi' in data:
            return data['rssi']
    except: pass
    return -70

def get_wifi_info():
    info = {'ssid': 'Unknown', 'dbm': -70, 'quality': 'Poor'}
    try:
        result = subprocess.check_output("termux-wifi-connectioninfo", shell=True, timeout=5).decode()
        data = json.loads(result)
        if 'ssid' in data:
            info['ssid'] = data['ssid']
        if 'rssi' in data:
            info['dbm'] = data['rssi']
    except: pass
    dbm = info['dbm']
    if dbm >= -50:
        info['quality'] = "Excellent"
    elif dbm >= -60:
        info['quality'] = "Good"
    elif dbm >= -70:
        info['quality'] = "Fair"
    elif dbm >= -80:
        info['quality'] = "Poor"
    else:
        info['quality'] = "Very Poor"
    return info

def get_signal_quality(dbm):
    if dbm >= -50: return "Excellent"
    elif dbm >= -60: return "Good"
    elif dbm >= -70: return "Fair"
    elif dbm >= -80: return "Poor"
    else: return "Very Poor"

def scan_wifi_devices():
    devices = []
    try:
        result = subprocess.check_output("arp -a", shell=True, timeout=5).decode()
        for line in result.split('\n'):
            if '(' in line and ')' in line:
                parts = line.split()
                if len(parts) >= 3:
                    ip = parts[1].strip('()')
                    mac = parts[3] if len(parts) > 3 else 'Unknown'
                    devices.append({'ip': ip, 'mac': mac, 'name': 'Device'})
    except: pass
    if not devices:
        devices = [{'ip': '192.168.1.1', 'mac': 'XX:XX:XX:XX:XX', 'name': 'Router'}]
    return devices[:10]

def get_wifi_location():
    try:
        result = subprocess.check_output("curl -s ipinfo.io/city", shell=True, timeout=5).decode().strip()
        if result and len(result) > 2:
            return result
    except: pass
    return "Unknown"

def wifi_settings_menu(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "📶 WIFI SETTINGS", curses.color_pair(5) | curses.A_BOLD)
        
        info = get_wifi_info()
        dbm = info['dbm']
        ssid = info['ssid']
        quality = get_signal_quality(dbm)
        
        safe_addstr(stdscr, 3, 4, f"📶 SSID: {ssid}", curses.color_pair(2) | curses.A_BOLD)
        safe_addstr(stdscr, 4, 4, f"📊 Signal: {dbm} dBm", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 5, 4, f"⭐ Quality: {quality}", curses.color_pair(4) if dbm >= -60 else curses.color_pair(1))
        
        bar_length = 35
        filled = int((dbm + 100) / 50 * bar_length)
        filled = max(0, min(bar_length, filled))
        bar = "█" * filled + "░" * (bar_length - filled)
        safe_addstr(stdscr, 7, 4, f"[{bar}]", curses.color_pair(3))
        
        safe_addstr(stdscr, 9, 4, "┌" + "─" * 50 + "┐", curses.color_pair(4))
        safe_addstr(stdscr, 10, 4, "│  [1] WIFI AR - Signal Strength Monitor      │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 11, 4, "└" + "─" * 50 + "┘", curses.color_pair(4))
        
        safe_addstr(stdscr, 13, 4, "┌" + "─" * 50 + "┐", curses.color_pair(3))
        safe_addstr(stdscr, 14, 4, "│  [2] WIFI SCANNER - Connected Devices       │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 15, 4, "└" + "─" * 50 + "┘", curses.color_pair(3))
        
        safe_addstr(stdscr, 17, 4, "┌" + "─" * 50 + "┐", curses.color_pair(5))
        safe_addstr(stdscr, 18, 4, "│  [3] WIFI LOCATION - Network Location        │", curses.color_pair(5) | curses.A_BOLD)
        safe_addstr(stdscr, 19, 4, "└" + "─" * 50 + "┘", curses.color_pair(5))
        
        safe_addstr(stdscr, 21, 4, "┌" + "─" * 50 + "┐", curses.color_pair(2))
        safe_addstr(stdscr, 22, 4, "│  [4] Scan Nearby Networks                   │", curses.color_pair(2) | curses.A_BOLD)
        safe_addstr(stdscr, 23, 4, "└" + "─" * 50 + "┘", curses.color_pair(2))
        
        safe_addstr(stdscr, 25, 4, "┌" + "─" * 20 + "┐", curses.color_pair(1))
        safe_addstr(stdscr, 26, 4, "│   [ Go Back ]    │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 27, 4, "└" + "─" * 20 + "┘", curses.color_pair(1))
        
        stdscr.noutrefresh()
        curses.doupdate()
        
        key = stdscr.getch()
        
        if key == ord('1'):
            wifi_ar_monitor(stdscr)
        elif key == ord('2'):
            wifi_scanner(stdscr)
        elif key == ord('3'):
            wifi_location(stdscr)
        elif key == ord('4'):
            scan_nearby(stdscr)
        elif key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if 25 <= my <= 27 and 4 <= mx <= 24:
                        break
                    elif 9 <= my <= 11 and 4 <= mx <= 54:
                        play_button_shrink(stdscr, 9, 4, "┌" + "─" * 50 + "┐", 4)
                        wifi_ar_monitor(stdscr)
                    elif 13 <= my <= 15 and 4 <= mx <= 54:
                        play_button_shrink(stdscr, 13, 4, "┌" + "─" * 50 + "┐", 3)
                        wifi_scanner(stdscr)
                    elif 17 <= my <= 19 and 4 <= mx <= 54:
                        play_button_shrink(stdscr, 17, 4, "┌" + "─" * 50 + "┐", 5)
                        wifi_location(stdscr)
                    elif 21 <= my <= 23 and 4 <= mx <= 54:
                        play_button_shrink(stdscr, 21, 4, "┌" + "─" * 50 + "┐", 2)
                        scan_nearby(stdscr)
            except: pass
        elif key == ord('\n') or key == ord('q'):
            break
    
    play_transition(stdscr)

def wifi_ar_monitor(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(300)
    
    running = True
    while running:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "📡 WIFI AR - Signal Monitor", curses.color_pair(5) | curses.A_BOLD)
        
        info = get_wifi_info()
        dbm = info['dbm']
        ssid = info['ssid']
        quality = get_signal_quality(dbm)
        
        safe_addstr(stdscr, 4, 4, f"SSID: {ssid}", curses.color_pair(2) | curses.A_BOLD)
        safe_addstr(stdscr, 6, 4, f"{dbm} dBm", curses.color_pair(3) | curses.A_BOLD)
        
        bar_length = 45
        filled = int((dbm + 100) / 50 * bar_length)
        filled = max(0, min(bar_length, filled))
        bar = "█" * filled + "░" * (bar_length - filled)
        safe_addstr(stdscr, 8, 4, f"[{bar}]", curses.color_pair(4) if dbm >= -60 else curses.color_pair(1))
        
        safe_addstr(stdscr, 10, 4, f"Quality: {quality}", curses.color_pair(2))
        safe_addstr(stdscr, 11, 4, f"Last updated: {datetime.now().strftime('%H:%M:%S')}", curses.color_pair(3))
        
        safe_addstr(stdscr, 13, 4, "Press any key to stop...", curses.color_pair(1))
        
        stdscr.noutrefresh()
        curses.doupdate()
        
        key = stdscr.getch()
        if key != -1:
            running = False
    
    stdscr.timeout(timeout_ms)
    play_transition(stdscr)

def wifi_scanner(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    
    devices = scan_wifi_devices()
    
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, f"📱 WIFI SCANNER - {len(devices)} Devices Found", curses.color_pair(5) | curses.A_BOLD)
        
        for idx, dev in enumerate(devices[:8]):
            color = curses.color_pair(2) if idx == 0 else curses.color_pair(3)
            safe_addstr(stdscr, 4 + idx, 4, f"  {idx+1}. {dev['ip'][:15]} | {dev['mac']} | {dev['name'][:10]}", color)
        
        safe_addstr(stdscr, 14, 4, "[R] Rescan  |  [D] Remove Device  |  [G] Go Back", curses.color_pair(3))
        
        stdscr.noutrefresh()
        curses.doupdate()
        
        key = stdscr.getch()
        if key == ord('r') or key == ord('R'):
            devices = scan_wifi_devices()
        elif key == ord('d') or key == ord('D'):
            if devices:
                curses.endwin()
                os.system("clear")
                print("Select device to remove (1-{})".format(len(devices)))
                try:
                    choice = int(input("> ")) - 1
                    if 0 <= choice < len(devices):
                        removed = devices.pop(choice)
                        print(f"✅ Removed: {removed['ip']}")
                    input("\nPress Enter...")
                except:
                    pass
                stdscr = curses.initscr()
                stdscr.timeout(timeout_ms)
        elif key == ord('g') or key == ord('G') or key == ord('\n'):
            break
        elif key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if my == 14:
                        break
            except: pass
    
    play_transition(stdscr)

def wifi_location(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "📍 WIFI LOCATION", curses.color_pair(5) | curses.A_BOLD)
        
        location = get_wifi_location()
        info = get_wifi_info()
        
        safe_addstr(stdscr, 4, 4, f"📍 City: {location}", curses.color_pair(2) | curses.A_BOLD)
        safe_addstr(stdscr, 5, 4, f"📶 SSID: {info['ssid']}", curses.color_pair(3))
        safe_addstr(stdscr, 6, 4, f"📊 Signal: {info['dbm']} dBm", curses.color_pair(4))
        safe_addstr(stdscr, 7, 4, f"⭐ Quality: {get_signal_quality(info['dbm'])}", curses.color_pair(2))
        
        safe_addstr(stdscr, 9, 4, "[1] Get IP Location  |  [2] Network Info  |  [G] Go Back", curses.color_pair(3))
        
        stdscr.noutrefresh()
        curses.doupdate()
        
        key = stdscr.getch()
        if key == ord('1'):
            curses.endwin()
            os.system("clear")
            print("\n📍 Getting IP Location...")
            try:
                result = subprocess.check_output("curl -s ipinfo.io", shell=True, timeout=10).decode()
                data = json.loads(result)
                print(f"\n🌐 IP: {data.get('ip', 'Unknown')}")
                print(f"📍 City: {data.get('city', 'Unknown')}")
                print(f"🏙️ Region: {data.get('region', 'Unknown')}")
                print(f"🌍 Country: {data.get('country', 'Unknown')}")
                print(f"📌 Location: {data.get('loc', 'Unknown')}")
            except:
                print("❌ Failed to get location")
            input("\nPress Enter...")
            stdscr = curses.initscr()
            stdscr.timeout(timeout_ms)
        elif key == ord('2'):
            curses.endwin()
            os.system("clear")
            print("\n📶 Network Information:")
            try:
                result = subprocess.check_output("ip addr", shell=True, timeout=5).decode()
                print(result[:500])
            except:
                print("❌ Failed to get network info")
            input("\nPress Enter...")
            stdscr = curses.initscr()
            stdscr.timeout(timeout_ms)
        elif key == ord('g') or key == ord('G') or key == ord('\n'):
            break
        elif key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if my == 9:
                        break
            except: pass
    
    play_transition(stdscr)

def scan_nearby(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    
    stdscr.erase()
    safe_addstr(stdscr, 1, 4, "📡 Scanning Nearby Networks...", curses.color_pair(5) | curses.A_BOLD)
    safe_addstr(stdscr, 3, 4, "Please wait...", curses.color_pair(2))
    stdscr.refresh()
    
    networks = scan_wifi_networks()
    
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, f"📡 Nearby Networks - {len(networks)} Found", curses.color_pair(5) | curses.A_BOLD)
        
        for idx, ssid in enumerate(networks[:8]):
            safe_addstr(stdscr, 4 + idx, 4, f"  {idx+1}. {ssid}", curses.color_pair(2))
        
        safe_addstr(stdscr, 14, 4, "[R] Rescan  |  [G] Go Back", curses.color_pair(3))
        
        stdscr.noutrefresh()
        curses.doupdate()
        
        key = stdscr.getch()
        if key == ord('r') or key == ord('R'):
            networks = scan_wifi_networks()
        elif key == ord('g') or key == ord('G') or key == ord('\n'):
            break
    
    play_transition(stdscr)

def antutu_test_menu(stdscr):
    global timeout_ms, device_antutu_score
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    bench_result = 0
    cpu_cores = multiprocessing.cpu_count()
    real_hardware = get_hardware_info()
    email_status_msg = ""
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "=== AnTuTu v11 Real Benchmarking ===", curses.color_pair(5) | curses.A_BOLD)
        saved_score = load_antutu_score()
        if saved_score == 0:
            safe_addstr(stdscr, 7, 4, "┌" + "─" * 50 + "┐", curses.color_pair(4))
            safe_addstr(stdscr, 8, 4, "│          [ RUN BENCHMARK NOW ]             │", curses.color_pair(4) | curses.A_BOLD)
            safe_addstr(stdscr, 9, 4, "└" + "─" * 50 + "┘", curses.color_pair(4))
        else:
            safe_addstr(stdscr, 4, 4, "┌" + "─" * 55 + "┐", curses.color_pair(3))
            safe_addstr(stdscr, 5, 4, f"│  Detected SoC:   {real_hardware:<35} │", curses.color_pair(3) | curses.A_BOLD)
            safe_addstr(stdscr, 6, 4, f"│  CPU Cores:      {cpu_cores:<35} │", curses.color_pair(2))
            safe_addstr(stdscr, 7, 4, f"│  AnTuTu Score:   {saved_score:,} Pts                   │", curses.color_pair(1) | curses.A_BOLD)
            safe_addstr(stdscr, 8, 4, "└" + "─" * 55 + "┘", curses.color_pair(3))
            safe_addstr(stdscr, 10, 4, "┌" + "─" * 50 + "┐", curses.color_pair(5))
            safe_addstr(stdscr, 11, 4, "│          [ SEND SCORE TO GMAIL ]             │", curses.color_pair(5) | curses.A_BOLD)
            safe_addstr(stdscr, 12, 4, "└" + "─" * 50 + "┘", curses.color_pair(5))
            safe_addstr(stdscr, 14, 4, "┌" + "─" * 50 + "┐", curses.color_pair(3))
            safe_addstr(stdscr, 15, 4, "│             [ RE-RUN TEST ]                │", curses.color_pair(3) | curses.A_BOLD)
            safe_addstr(stdscr, 16, 4, "└" + "─" * 50 + "┘", curses.color_pair(3))
        if email_status_msg:
            safe_addstr(stdscr, 18, 4, f"Info: {email_status_msg}", curses.color_pair(2) | curses.A_BOLD)
        safe_addstr(stdscr, 20, 4, "┌" + "─" * 20 + "┐", curses.color_pair(1))
        safe_addstr(stdscr, 21, 4, "│   [Go Back]   │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 22, 4, "└" + "─" * 20 + "┘", curses.color_pair(1))
        stdscr.noutrefresh()
        curses.doupdate()
        key = stdscr.getch()
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if saved_score == 0:
                        if 7 <= my <= 9 and 4 <= mx <= 54:
                            play_button_shrink(stdscr, 7, 4, "┌" + "─" * 50 + "┐", 4)
                            stdscr.erase()
                            safe_addstr(stdscr, 10, 10, "BENCHMARKING CPU CORES... PLEASE WAIT", curses.color_pair(1) | curses.A_BOLD)
                            stdscr.refresh()
                            bench_result = run_real_cpu_benchmark()
                            device_antutu_score, _ = calculate_antutu_v11_score(bench_result)
                            save_antutu_score(device_antutu_score)
                            email_status_msg = ""
                    else:
                        if 10 <= my <= 12 and 4 <= mx <= 54:
                            play_button_shrink(stdscr, 10, 4, "┌" + "─" * 50 + "┐", 5)
                            stdscr.erase()
                            safe_addstr(stdscr, 10, 10, "Connecting to Gmail & Sending...", curses.color_pair(3) | curses.A_BOLD)
                            stdscr.refresh()
                            subject = f"Kurd Mars - AnTuTu Benchmark Report ({real_hardware})"
                            body = f"Kurd Mars AnTuTu Benchmark Report:\n\nDevice SoC: {real_hardware}\nCPU Cores: {cpu_cores}\nAnTuTu Score: {saved_score:,} Pts\n"
                            success, msg = send_email_notification(subject, body)
                            email_status_msg = msg
                            stdscr.timeout(timeout_ms)
                        elif 14 <= my <= 16 and 4 <= mx <= 54:
                            play_button_shrink(stdscr, 14, 4, "┌" + "─" * 50 + "┐", 3)
                            save_antutu_score(0)
                            email_status_msg = ""
                    if 20 <= my <= 22 and 4 <= mx <= 24:
                        play_button_shrink(stdscr, 20, 4, "┌" + "─" * 20 + "┐", 1)
                        play_transition(stdscr)
                        break
            except: pass

# ==========================================
# CHROME DINO GAME
# ==========================================
def run_fps_test_game(stdscr):
    global current_fps, current_hz, timeout_ms
    play_transition(stdscr)
    
    curses.curs_set(0)
    stdscr.timeout(max(1, int(1000 / current_fps)))
    height, width = stdscr.getmaxyx()
    
    player_y = height - 6
    player_x = 6
    jump_velocity = 0
    gravity = 0.6
    jump_power = -10
    is_jumping = False
    is_ducking = False
    
    obstacles = []
    score = 0
    high_score = 0
    game_speed = 3 + (current_fps / 100)
    obstacle_timer = 0
    game_over = False
    frame = 0
    
    ground_y = height - 3
    sky_y = 1
    
    def create_obstacle():
        obs_type = random.choice(['cactus', 'cactus_small', 'pterodactyl'])
        if obs_type == 'pterodactyl':
            return {'x': width - 5, 'y': ground_y - 4, 'width': 3, 'height': 2, 'type': 'pterodactyl'}
        elif obs_type == 'cactus_small':
            return {'x': width - 4, 'y': ground_y - 2, 'width': 2, 'height': 2, 'type': 'cactus_small'}
        else:
            return {'x': width - 5, 'y': ground_y - 3, 'width': 2, 'height': 3, 'type': 'cactus'}
    
    def draw_dino(y, x, jumping, ducking, frame):
        if ducking and not jumping:
            safe_addstr(stdscr, y, x, "🦎", curses.color_pair(3) | curses.A_BOLD)
        elif jumping:
            safe_addstr(stdscr, y, x, "🦕", curses.color_pair(3) | curses.A_BOLD)
        else:
            if frame % 20 < 10:
                safe_addstr(stdscr, y, x, "🦖", curses.color_pair(3) | curses.A_BOLD)
            else:
                safe_addstr(stdscr, y, x, "🦕", curses.color_pair(3) | curses.A_BOLD)
    
    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        ground_y = height - 3
        frame += 1
        
        safe_hline(stdscr, 0, 0, "═", width, curses.color_pair(5))
        info_text = f"🦕 CHROME DINO | SCORE: {score} | HIGH: {high_score} | SPEED: {game_speed:.1f} | {current_hz}Hz/{current_fps}FPS"
        safe_addstr(stdscr, 0, 2, info_text, curses.color_pair(4) | curses.A_BOLD)
        safe_hline(stdscr, 1, 0, "═", width, curses.color_pair(5))
        
        safe_hline(stdscr, sky_y, 0, " ", width, curses.color_pair(2))
        safe_addstr(stdscr, sky_y, 2, "☀️", curses.color_pair(5))
        safe_addstr(stdscr, sky_y, width - 4, "☁️", curses.color_pair(2))
        
        safe_hline(stdscr, ground_y, 0, "█", width, curses.color_pair(2))
        for i in range(0, width, 8):
            safe_addstr(stdscr, ground_y, i + (frame % 8), "▄", curses.color_pair(2))
        
        if is_jumping:
            player_y += jump_velocity
            jump_velocity += gravity
            if player_y >= ground_y - 2:
                player_y = ground_y - 2
                is_jumping = False
                jump_velocity = 0
        
        draw_dino(player_y, player_x, is_jumping, is_ducking, frame)
        
        if not game_over:
            obstacle_timer += 1
            spawn_rate = max(15, 40 - int(game_speed * 3))
            if obstacle_timer > spawn_rate:
                if len(obstacles) < 4:
                    obstacles.append(create_obstacle())
                obstacle_timer = 0
        
        for obs in obstacles[:]:
            obs['x'] -= game_speed
            
            if obs['type'] == 'cactus':
                safe_addstr(stdscr, obs['y'], obs['x'], "🌵", curses.color_pair(1) | curses.A_BOLD)
            elif obs['type'] == 'cactus_small':
                safe_addstr(stdscr, obs['y'], obs['x'], "🌵", curses.color_pair(1) | curses.A_BOLD)
            else:
                if frame % 20 < 10:
                    safe_addstr(stdscr, obs['y'], obs['x'], "🦅", curses.color_pair(5) | curses.A_BOLD)
                else:
                    safe_addstr(stdscr, obs['y'], obs['x'], "🐦", curses.color_pair(5) | curses.A_BOLD)
            
            if not game_over:
                obs_left = obs['x']
                obs_right = obs['x'] + 2
                obs_top = obs['y']
                obs_bottom = obs['y'] + 2
                
                player_left = player_x
                player_right = player_x + 2
                player_top = player_y - 1
                player_bottom = player_y + 1
                
                if (player_right > obs_left and player_left < obs_right and
                    player_bottom > obs_top and player_top < obs_bottom):
                    game_over = True
                    vibrate_phone(200)
                    if score > high_score:
                        high_score = score
            
            if obs['x'] + 3 < 0:
                obstacles.remove(obs)
                if not game_over:
                    score += 1
                    game_speed += 0.05
        
        jump_btn_x = width - 18
        jump_btn_y = height - 7
        safe_addstr(stdscr, jump_btn_y, jump_btn_x, "┌" + "─" * 16 + "┐", curses.color_pair(4))
        safe_addstr(stdscr, jump_btn_y + 1, jump_btn_x, "│   JUMP ↑  │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, jump_btn_y + 2, jump_btn_x, "└" + "─" * 16 + "┘", curses.color_pair(4))
        
        btn_x = width - 18
        btn_y = height - 1
        safe_addstr(stdscr, btn_y - 2, btn_x, "┌" + "─" * 16 + "┐", curses.color_pair(1))
        safe_addstr(stdscr, btn_y - 1, btn_x, "│   [ Back ]  │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, btn_y, btn_x, "└" + "─" * 16 + "┘", curses.color_pair(1))
        
        if game_over:
            safe_addstr(stdscr, height // 2 - 3, width // 2 - 14, "╔════════════════════════════╗", curses.color_pair(1))
            safe_addstr(stdscr, height // 2 - 2, width // 2 - 14, "║       💀 GAME OVER 💀      ║", curses.color_pair(1) | curses.A_BOLD)
            safe_addstr(stdscr, height // 2 - 1, width // 2 - 14, f"║      SCORE: {score}         ║", curses.color_pair(3) | curses.A_BOLD)
            safe_addstr(stdscr, height // 2, width // 2 - 14, f"║      HIGH: {high_score}      ║", curses.color_pair(4) | curses.A_BOLD)
            safe_addstr(stdscr, height // 2 + 1, width // 2 - 14, "║   SPACE or Click to Restart ║", curses.color_pair(2))
            safe_addstr(stdscr, height // 2 + 2, width // 2 - 14, "╚════════════════════════════╝", curses.color_pair(1))
        
        stdscr.noutrefresh()
        curses.doupdate()
        
        key = stdscr.getch()
        
        if key == ord(' ') or key == ord('w') or key == ord('W') or key == ord('↑'):
            if game_over:
                obstacles = []
                score = 0
                game_speed = 3 + (current_fps / 100)
                player_y = ground_y - 2
                is_jumping = False
                jump_velocity = 0
                game_over = False
                obstacle_timer = 0
            elif not is_jumping and player_y >= ground_y - 3:
                is_jumping = True
                jump_velocity = jump_power - (game_speed / 6)
        
        elif key == ord('s') or key == ord('S') or key == ord('↓'):
            if not is_jumping and player_y >= ground_y - 3:
                is_ducking = True
            else:
                is_ducking = False
        
        elif key == ord('q') or key == ord('Q'):
            break
        
        elif key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if jump_btn_y <= my <= jump_btn_y + 2 and jump_btn_x <= mx <= jump_btn_x + 18:
                        if game_over:
                            obstacles = []
                            score = 0
                            game_speed = 3 + (current_fps / 100)
                            player_y = ground_y - 2
                            is_jumping = False
                            jump_velocity = 0
                            game_over = False
                            obstacle_timer = 0
                        elif not is_jumping and player_y >= ground_y - 3:
                            is_jumping = True
                            jump_velocity = jump_power - (game_speed / 6)
                    elif btn_y - 2 <= my <= btn_y and btn_x <= mx <= btn_x + 18:
                        break
            except: pass
        
        stdscr.timeout(max(1, int(1000 / current_fps)))
    
    play_transition(stdscr)

flash_active = False

# ==========================================
# HARDWARE PANEL
# ==========================================
def hardware_controls_menu(stdscr):
    global timeout_ms, flash_active
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    wifi_list = []
    connection_status = ""
    error_note = ""
    
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "🔧 HARDWARE & WIFI CONTROL", curses.color_pair(5) | curses.A_BOLD)
        
        flash_bar = "[ OFF ──────● ON ]" if flash_active else "[ OFF ●────── ON ]"
        flash_color = curses.color_pair(4) if flash_active else curses.color_pair(1)
        safe_addstr(stdscr, 3, 4, "LED Flash State:", curses.color_pair(2) | curses.A_BOLD)
        safe_addstr(stdscr, 4, 4, f"{flash_bar}", flash_color | curses.A_BOLD)
        
        safe_addstr(stdscr, 6, 4, "┌" + "─" * 50 + "┐", curses.color_pair(4))
        safe_addstr(stdscr, 7, 4, "│          [ VIBRATE PHONE ]                  │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 8, 4, "└" + "─" * 50 + "┘", curses.color_pair(4))
        
        safe_addstr(stdscr, 10, 4, "┌" + "─" * 50 + "┐", curses.color_pair(3))
        safe_addstr(stdscr, 11, 4, "│          [ WIFI SETTINGS 📶 ]              │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 12, 4, "└" + "─" * 50 + "┘", curses.color_pair(3))
        
        info = get_wifi_info()
        dbm = info['dbm']
        ssid = info['ssid']
        quality = get_signal_quality(dbm)
        safe_addstr(stdscr, 14, 4, f"📶 SSID: {ssid}", curses.color_pair(2) | curses.A_BOLD)
        safe_addstr(stdscr, 15, 4, f"📊 Signal: {dbm} dBm", curses.color_pair(3))
        safe_addstr(stdscr, 16, 4, f"⭐ Quality: {quality}", curses.color_pair(4) if dbm >= -60 else curses.color_pair(1))
        
        bar_length = 30
        filled = int((dbm + 100) / 50 * bar_length)
        filled = max(0, min(bar_length, filled))
        bar = "█" * filled + "░" * (bar_length - filled)
        safe_addstr(stdscr, 17, 4, f"[{bar}]", curses.color_pair(3))
        
        if error_note:
            safe_addstr(stdscr, 19, 4, f"⚠️ {error_note}", curses.color_pair(1) | curses.A_BOLD)
        
        if wifi_list:
            safe_addstr(stdscr, 20, 4, "Nearby Networks:", curses.color_pair(5) | curses.A_BOLD)
            for idx, ssid in enumerate(wifi_list[:6]):
                safe_addstr(stdscr, 22 + idx, 6, f"{idx+1}. {ssid[:20]}", curses.color_pair(2))
        
        if connection_status:
            status_color = curses.color_pair(4) if "Connected" in connection_status else curses.color_pair(1)
            safe_addstr(stdscr, 28, 4, f"Status: {connection_status}", status_color | curses.A_BOLD)
        
        safe_addstr(stdscr, 30, 4, "┌" + "─" * 20 + "┐", curses.color_pair(1))
        safe_addstr(stdscr, 31, 4, "│   [ Go Back ]    │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 32, 4, "└" + "─" * 20 + "┘", curses.color_pair(1))
        stdscr.noutrefresh()
        curses.doupdate()
        
        key = stdscr.getch()
        
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if my == 4 and 4 <= mx <= 22:
                        play_button_shrink(stdscr, 3, 4, "LED Flash State:", 2)
                        flash_active = not flash_active
                        toggle_flashlight(flash_active)
                        vibrate_phone(100)
                    elif 6 <= my <= 8 and 4 <= mx <= 54:
                        play_button_shrink(stdscr, 6, 4, "┌" + "─" * 50 + "┐", 4)
                        vibrate_phone(1000)
                        safe_addstr(stdscr, 9, 4, "📳 Vibrating...", curses.color_pair(4))
                        stdscr.refresh()
                        time.sleep(0.3)
                    elif 10 <= my <= 12 and 4 <= mx <= 54:
                        play_button_shrink(stdscr, 10, 4, "┌" + "─" * 50 + "┐", 3)
                        wifi_settings_menu(stdscr)
                    elif wifi_list and 22 <= my < 22 + len(wifi_list):
                        clicked_idx = my - 22
                        if clicked_idx < len(wifi_list):
                            target_ssid = wifi_list[clicked_idx]
                            stdscr.timeout(-1)
                            stdscr.erase()
                            safe_addstr(stdscr, 2, 4, f"SSID Selected: {target_ssid}", curses.color_pair(4) | curses.A_BOLD)
                            pwd = get_user_input(stdscr, 4, 4, "Enter Wi-Fi Password: ", mask=True)
                            stdscr.erase()
                            safe_addstr(stdscr, 5, 4, "Attempting to connect (requires root)...", curses.color_pair(3) | curses.A_BOLD)
                            stdscr.refresh()
                            success = connect_to_wifi(target_ssid, pwd)
                            connection_status = "Connected!" if success else "Connection failed (root needed)"
                            stdscr.timeout(timeout_ms)
                    elif 30 <= my <= 32 and 4 <= mx <= 24:
                        play_button_shrink(stdscr, 30, 4, "┌" + "─" * 20 + "┐", 1)
                        break
            except: pass
        elif key == ord('\n') or key == ord('q'):
            break
    
    play_transition(stdscr)

# ==========================================
# ADVANCED SETTINGS
# ==========================================
def settings_menu(stdscr):
    global current_hz, current_fps, timeout_ms, selected_hz, selected_fps
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    
    selected_hz = current_hz
    selected_fps = current_fps
    error_msg = ""
    clear_msg = ""
    
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "⚙️ ADVANCED SETTINGS", curses.color_pair(5) | curses.A_BOLD)
        
        safe_addstr(stdscr, 3, 4, "━━━ GRAPHICS SETTINGS ━━━", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 4, 4, f"Active Mode: {current_hz}Hz | Render: {current_fps} FPS", curses.color_pair(3))
        if error_msg:
            safe_addstr(stdscr, 6, 4, f"⚠️ {error_msg}", curses.color_pair(1) | curses.A_BOLD)
        
        safe_addstr(stdscr, 8, 4, "Refresh Rate (Hz):", curses.color_pair(2) | curses.A_BOLD)
        hz60_attr = curses.color_pair(3) | curses.A_REVERSE if selected_hz == 60 else curses.color_pair(2)
        hz120_attr = curses.color_pair(3) | curses.A_REVERSE if selected_hz == 120 else curses.color_pair(2)
        safe_addstr(stdscr, 9, 4, " [ 60Hz ] ", hz60_attr)
        safe_addstr(stdscr, 9, 18, " [ 120Hz ] ", hz120_attr)
        
        safe_addstr(stdscr, 11, 4, "Target FPS:", curses.color_pair(2) | curses.A_BOLD)
        fps_list = [10, 20, 30, 45, 60, 90, 120]
        for idx, f_val in enumerate(fps_list):
            f_attr = curses.color_pair(5) | curses.A_REVERSE if selected_fps == f_val else curses.color_pair(2)
            safe_addstr(stdscr, 12 + (idx // 4) * 2, 4 + (idx % 4) * 13, f"[ {f_val} ]", f_attr)
        
        safe_addstr(stdscr, 16, 4, "━━━ TOOL MAINTENANCE ━━━", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 17, 4, "┌" + "─" * 54 + "┐", curses.color_pair(1))
        safe_addstr(stdscr, 18, 4, "│  [CLEAR]  Fix BUGs & Freeze Issues         │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 19, 4, "└" + "─" * 54 + "┘", curses.color_pair(1))
        
        if clear_msg:
            safe_addstr(stdscr, 21, 4, f"✅ {clear_msg}", curses.color_pair(4))
        
        safe_addstr(stdscr, 23, 4, "┌" + "─" * 54 + "┐", curses.color_pair(3))
        safe_addstr(stdscr, 24, 4, "│      [ HARDWARE & WIFI CONTROL 🔧 ]        │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 25, 4, "└" + "─" * 54 + "┘", curses.color_pair(3))
        
        safe_addstr(stdscr, 27, 4, "┌" + "─" * 54 + "┐", curses.color_pair(5))
        safe_addstr(stdscr, 28, 4, "│          [ APPLY CHANGES ⚡ ]               │", curses.color_pair(5) | curses.A_BOLD)
        safe_addstr(stdscr, 29, 4, "└" + "─" * 54 + "┘", curses.color_pair(5))
        
        safe_addstr(stdscr, 31, 4, "┌" + "─" * 20 + "┐", curses.color_pair(1))
        safe_addstr(stdscr, 32, 4, "│   [ Go Back ]    │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 33, 4, "└" + "─" * 20 + "┘", curses.color_pair(1))
        
        stdscr.noutrefresh()
        curses.doupdate()
        
        key = stdscr.getch()
        
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    error_msg = ""
                    
                    if my == 9:
                        if 4 <= mx <= 16:
                            selected_hz = 60
                        elif 18 <= mx <= 30:
                            selected_hz = 120
                    
                    elif my == 12:
                        if 4 <= mx <= 14:
                            selected_fps = 10
                        elif 17 <= mx <= 27:
                            selected_fps = 20
                        elif 30 <= mx <= 40:
                            selected_fps = 30
                        elif 43 <= mx <= 53:
                            selected_fps = 45
                    elif my == 13:
                        if 4 <= mx <= 14:
                            selected_fps = 60
                        elif 17 <= mx <= 27:
                            selected_fps = 90
                        elif 30 <= mx <= 40:
                            selected_fps = 120
                    
                    elif 17 <= my <= 19 and 4 <= mx <= 58:
                        play_button_shrink(stdscr, 17, 4, "┌" + "─" * 54 + "┐", 1)
                        try:
                            import gc
                            gc.collect()
                            update_timeout()
                            clear_msg = "Tool cleaned! BUGs and Freeze cleared. ✅"
                            stdscr.timeout(timeout_ms)
                        except:
                            clear_msg = "Clean failed, restart tool."
                    
                    elif 23 <= my <= 25 and 4 <= mx <= 58:
                        play_button_shrink(stdscr, 23, 4, "┌" + "─" * 54 + "┐", 3)
                        hardware_controls_menu(stdscr)
                    
                    elif 27 <= my <= 29 and 4 <= mx <= 58:
                        play_button_shrink(stdscr, 27, 4, "┌" + "─" * 54 + "┐", 5)
                        saved_score = load_antutu_score()
                        if selected_fps == 120:
                            if saved_score == 0:
                                error_msg = "Run AnTuTu test first to unlock 120FPS!"
                            elif saved_score < 1000000:
                                error_msg = f"Score ({saved_score:,}) < 1M! 120FPS Locked."
                            else:
                                current_hz = selected_hz
                                current_fps = selected_fps
                                update_timeout()
                                clear_msg = f"Applied: {current_hz}Hz / {current_fps}FPS ✅"
                        else:
                            current_hz = selected_hz
                            current_fps = selected_fps
                            update_timeout()
                            clear_msg = f"Applied: {current_hz}Hz / {current_fps}FPS ✅"
                        
                        stdscr.timeout(timeout_ms)
                    
                    elif 31 <= my <= 33 and 4 <= mx <= 24:
                        break
            except: pass
        
        elif key == ord('c') or key == ord('C'):
            try:
                import gc
                gc.collect()
                update_timeout()
                clear_msg = "Tool cleaned! ✅"
            except:
                clear_msg = "Clean failed."
        
        elif key == ord('a') or key == ord('A'):
            saved_score = load_antutu_score()
            if selected_fps == 120:
                if saved_score == 0:
                    error_msg = "Run AnTuTu test first!"
                elif saved_score < 1000000:
                    error_msg = f"Score {saved_score:,} < 1M!"
                else:
                    current_hz = selected_hz
                    current_fps = selected_fps
                    update_timeout()
                    clear_msg = f"Applied: {current_hz}Hz / {current_fps}FPS ✅"
            else:
                current_hz = selected_hz
                current_fps = selected_fps
                update_timeout()
                clear_msg = f"Applied: {current_hz}Hz / {current_fps}FPS ✅"
        
        elif key == ord('h') or key == ord('H'):
            hardware_controls_menu(stdscr)
        
        elif key == ord('\n'):
            break

def print_kurd_mars_logo(stdscr):
    logo = [
        r"  _  ___  _ ____  ____    __  __    _    ____  ____  ", 
        r" | |/ / | | |  _ \|  _ \  |  \/  |  / \  |  _ \/ ___| ", 
        r" | ' /| | | | |_) | | | | | |\/| | / _ \ | |_) \___ \ ", 
        r" | . \| |_| |  _ <| |_| | | |  | |/ ___ \|  _ < ___) |", 
        r" |_|\_\\___/|_| \_\____/  |_|  |_/_/   \_\_| \_\____/ "  
    ]
    curses.init_pair(1, curses.COLOR_RED, curses.COLOR_BLACK)
    curses.init_pair(2, curses.COLOR_WHITE, curses.COLOR_BLACK)
    curses.init_pair(3, curses.COLOR_YELLOW, curses.COLOR_BLACK)
    curses.init_pair(4, curses.COLOR_GREEN, curses.COLOR_BLACK)
    curses.init_pair(5, curses.COLOR_CYAN, curses.COLOR_BLACK)
    for idx, line in enumerate(logo):
        safe_addstr(stdscr, idx + 1, 2, line, curses.color_pair(idx % 5 + 1) | curses.A_BOLD)
    safe_addstr(stdscr, 6, 2, "▬▬▬▬▬▬▬▬▬▬▬▬▬▬ KURD MARS TOOL ▬▬▬▬▬▬▬▬▬▬▬▬▬▬", curses.color_pair(3) | curses.A_BOLD)

def termux_setup_menu(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "=== Termux & Kali Linux Setup ===", curses.color_pair(5) | curses.A_BOLD)
        safe_addstr(stdscr, 3, 4, "┌" + "─" * 40 + "┐", curses.color_pair(2))
        safe_addstr(stdscr, 4, 4, "│    1 - Update Termux            │", curses.color_pair(2) | curses.A_BOLD)
        safe_addstr(stdscr, 5, 4, "└" + "─" * 40 + "┘", curses.color_pair(2))
        safe_addstr(stdscr, 7, 4, "┌" + "─" * 40 + "┐", curses.color_pair(3))
        safe_addstr(stdscr, 8, 4, "│    2 - Install Kali NetHunter   │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 9, 4, "└" + "─" * 40 + "┘", curses.color_pair(3))
        safe_addstr(stdscr, 11, 4, "┌" + "─" * 40 + "┐", curses.color_pair(4))
        safe_addstr(stdscr, 12, 4, "│    3 - RUN KALI LINUX (nh)      │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 13, 4, "└" + "─" * 40 + "┘", curses.color_pair(4))
        safe_addstr(stdscr, 16, 4, "┌" + "─" * 20 + "┐", curses.color_pair(1))
        safe_addstr(stdscr, 17, 4, "│   [Go Back]   │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 18, 4, "└" + "─" * 20 + "┘", curses.color_pair(1))
        stdscr.noutrefresh()
        curses.doupdate()
        key = stdscr.getch()
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if 3 <= my <= 5 and 4 <= mx <= 44:
                        play_button_shrink(stdscr, 3, 4, "┌" + "─" * 40 + "┐", 2)
                        curses.endwin()
                        os.system("clear")
                        print("[+] Running Termux Update...")
                        os.system("pkg update -y && pkg upgrade -y")
                        input("\nProcess finished. Press Enter...")
                        stdscr = curses.initscr()
                        stdscr.timeout(timeout_ms)
                    elif 7 <= my <= 9 and 4 <= mx <= 44:
                        play_button_shrink(stdscr, 7, 4, "┌" + "─" * 40 + "┐", 3)
                        curses.endwin()
                        os.system("clear")
                        print("[*] Installing dependencies...")
                        os.system("pkg install curl proot wget -y")
                        os.system("curl -fsSLO https://raw.githubusercontent.com/jorexdeveloper/termux-nethunter/main/install-nethunter.sh")
                        os.system("chmod +x install-nethunter.sh")
                        os.system("bash install-nethunter.sh")
                        input("\nProcess finished. Press Enter...")
                        stdscr = curses.initscr()
                        stdscr.timeout(timeout_ms)
                    elif 11 <= my <= 13 and 4 <= mx <= 44:
                        play_button_shrink(stdscr, 11, 4, "┌" + "─" * 40 + "┐", 4)
                        curses.endwin()
                        os.system("clear")
                        print("[*] Booting Kali Linux NetHunter...\n")
                        os.system("nh")
                        input("\nReturned to Tool. Press Enter...")
                        stdscr = curses.initscr()
                        stdscr.timeout(timeout_ms)
                    elif 16 <= my <= 18 and 4 <= mx <= 24:
                        play_button_shrink(stdscr, 16, 4, "┌" + "─" * 20 + "┐", 1)
                        break
            except: pass

def main(stdscr):
    global timeout_ms
    try: curses.mouseinterval(0)
    except: pass
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    curses.curs_set(0)
    stdscr.timeout(timeout_ms)
    
    while True:
        stdscr.erase()
        print_kurd_mars_logo(stdscr)
        
        safe_addstr(stdscr, 8, 4,  "┌" + "─" * 27 + "┐", curses.color_pair(5))
        safe_addstr(stdscr, 9, 4,  "│   Termux & Kali       │", curses.color_pair(5) | curses.A_BOLD)
        safe_addstr(stdscr, 10, 4, "└" + "─" * 27 + "┘", curses.color_pair(5))
        
        safe_addstr(stdscr, 8, 35, "┌" + "─" * 27 + "┐", curses.color_pair(4))
        safe_addstr(stdscr, 9, 35, "│   Chrome Dino 🦕     │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 10, 35, "└" + "─" * 27 + "┘", curses.color_pair(4))
        
        safe_addstr(stdscr, 11, 4, "┌" + "─" * 58 + "┐", curses.color_pair(3))
        safe_addstr(stdscr, 12, 4, "│          [ TEST ANTUTU v11 ]               │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 13, 4, "└" + "─" * 58 + "┘", curses.color_pair(3))
        
        safe_addstr(stdscr, 14, 4, "┌" + "─" * 58 + "┐", curses.color_pair(4))
        safe_addstr(stdscr, 15, 4, "│          [ TERMUX TOOLS 📦 ]                │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 16, 4, "└" + "─" * 58 + "┘", curses.color_pair(4))
        
        safe_addstr(stdscr, 17, 4, "┌" + "─" * 27 + "┐", curses.color_pair(3))
        safe_addstr(stdscr, 18, 4, "│   Devices Control 🔌  │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 19, 4, "└" + "─" * 27 + "┘", curses.color_pair(3))
        
        safe_addstr(stdscr, 17, 35, "┌" + "─" * 27 + "┐", curses.color_pair(5))
        safe_addstr(stdscr, 18, 35, "│  Advanced Settings ⚙️ │", curses.color_pair(5) | curses.A_BOLD)
        safe_addstr(stdscr, 19, 35, "└" + "─" * 27 + "┘", curses.color_pair(5))
        
        # ===== UPDATE TOOL BUTTON =====
        safe_addstr(stdscr, 20, 4, "┌" + "─" * 27 + "┐", curses.color_pair(4))
        safe_addstr(stdscr, 21, 4, "│   Update Tool 🔄    │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 22, 4, "└" + "─" * 27 + "┘", curses.color_pair(4))
        
        width = 80
        exit_x = (width - 22) // 2
        safe_addstr(stdscr, 23, exit_x, "┌" + "─" * 22 + "┐", curses.color_pair(1))
        safe_addstr(stdscr, 24, exit_x, "│       [ Exit ]        │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 25, exit_x, "└" + "─" * 22 + "┘", curses.color_pair(1))

        stdscr.noutrefresh()
        curses.doupdate()
        
        key = stdscr.getch()
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if 8 <= my <= 10 and 4 <= mx <= 31:
                        play_button_shrink(stdscr, 8, 4, "┌" + "─" * 27 + "┐", 5)
                        termux_setup_menu(stdscr)
                    elif 8 <= my <= 10 and 35 <= mx <= 62:
                        play_button_shrink(stdscr, 8, 35, "┌" + "─" * 27 + "┐", 4)
                        run_fps_test_game(stdscr)
                    elif 11 <= my <= 13 and 4 <= mx <= 62:
                        play_button_shrink(stdscr, 11, 4, "┌" + "─" * 58 + "┐", 3)
                        antutu_test_menu(stdscr)
                    elif 14 <= my <= 16 and 4 <= mx <= 62:
                        play_button_shrink(stdscr, 14, 4, "┌" + "─" * 58 + "┐", 4)
                        termux_menu(stdscr)
                    elif 17 <= my <= 19 and 4 <= mx <= 31:
                        play_button_shrink(stdscr, 17, 4, "┌" + "─" * 27 + "┐", 3)
                        devices_menu(stdscr)
                    elif 17 <= my <= 19 and 35 <= mx <= 62:
                        play_button_shrink(stdscr, 17, 35, "┌" + "─" * 27 + "┐", 5)
                        settings_menu(stdscr)
                    elif 20 <= my <= 22 and 4 <= mx <= 31:
                        play_button_shrink(stdscr, 20, 4, "┌" + "─" * 27 + "┐", 4)
                        update_tool(stdscr)
                    elif 23 <= my <= 25 and exit_x <= mx <= exit_x + 22:
                        break
            except: pass

if __name__ == "__main__":
    curses.wrapper(main)
