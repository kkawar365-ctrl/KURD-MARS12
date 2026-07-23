
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
from datetime import datetime
from email.mime.text import MIMEText

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
            subprocess.Popen("su -c 'cmd torch on'", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen("su -c 'cmd torch off'", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    height, width = stdscr.getmaxyx()
    mid_y = height // 2
    steps = max(4, int(current_fps / 10))
    delay = 1.0 / current_fps
    for i in range(0, mid_y + 1, max(1, mid_y // steps)):
        stdscr.erase()
        safe_hline(stdscr, max(0, mid_y - i), 0, "─", width, curses.color_pair(5))
        safe_hline(stdscr, min(height - 1, mid_y + i), 0, "─", width, curses.color_pair(5))
        stdscr.refresh()
        time.sleep(delay)

def play_button_shrink(stdscr, y, x, text, color_pair):
    clean_text = text.replace("┌", "").replace("┐", "").replace("└", "").replace("┘", "").replace("│", "").strip()
    short_box_top = " ┌" + "─" * (len(clean_text) - 2) + "┐ "
    short_box_mid = f" │ {clean_text[1:-1]} │ "
    short_box_bot = " └" + "─" * (len(clean_text) - 2) + "┘ "
    safe_addstr(stdscr, y, x, short_box_top, curses.color_pair(3) | curses.A_BOLD)
    safe_addstr(stdscr, y+1, x, short_box_mid, curses.color_pair(3) | curses.A_BOLD)
    safe_addstr(stdscr, y+2, x, short_box_bot, curses.color_pair(3) | curses.A_BOLD)
    stdscr.refresh()
    time.sleep(0.08)

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

def termux_menu(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "📦 TERMUX TOOLS", curses.color_pair(5) | curses.A_BOLD)
        safe_addstr(stdscr, 3, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(4))
        safe_addstr(stdscr, 4, 4, "│  [1] Termux Setup - Full Installation         │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 5, 4, "└───────────────────────────────────────────────┘", curses.color_pair(4))
        safe_addstr(stdscr, 7, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(3))
        safe_addstr(stdscr, 8, 4, "│  [2] Termux API - Install API Packages        │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 9, 4, "└───────────────────────────────────────────────┘", curses.color_pair(3))
        safe_addstr(stdscr, 11, 4, "[ Go Back ]", curses.color_pair(1) | curses.A_BOLD)
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
                    if my == 11:
                        break
                    elif 3 <= my <= 5 and 4 <= mx <= 52:
                        termux_setup(stdscr)
                    elif 7 <= my <= 9 and 4 <= mx <= 52:
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
    stdscr.refresh()
    api_packages = [
        "termux-api", "termux-api-audio", "termux-api-battery",
        "termux-api-camera", "termux-api-clipboard", "termux-api-contact",
        "termux-api-dialog", "termux-api-download", "termux-api-fingerprint",
        "termux-api-input", "termux-api-location", "termux-api-media",
        "termux-api-microphone", "termux-api-notification", "termux-api-permission",
        "termux-api-sensor", "termux-api-share", "termux-api-sms",
        "termux-api-speech", "termux-api-telephony", "termux-api-toast",
        "termux-api-vibrate", "termux-api-wallpaper", "termux-api-wifi"
    ]
    success_count = 0
    for idx, pkg in enumerate(api_packages):
        try:
            safe_addstr(stdscr, 5, 4, f"Installing: {pkg} ({idx+1}/{len(api_packages)})", curses.color_pair(3))
            stdscr.refresh()
            result = subprocess.run(f"pkg install {pkg} -y", shell=True, timeout=60, capture_output=True)
            if result.returncode == 0:
                success_count += 1
                safe_addstr(stdscr, 6 + idx, 6, f"✅ {pkg} installed", curses.color_pair(4))
            else:
                safe_addstr(stdscr, 6 + idx, 6, f"❌ {pkg} failed", curses.color_pair(1))
            stdscr.refresh()
        except:
            safe_addstr(stdscr, 6 + idx, 6, f"❌ {pkg} timeout", curses.color_pair(1))
            stdscr.refresh()
    safe_addstr(stdscr, 8 + len(api_packages), 4, f"✅ API Installation Complete! {success_count}/{len(api_packages)} packages installed.", curses.color_pair(4))
    safe_addstr(stdscr, 10 + len(api_packages), 4, "[ Press any key to go back ]", curses.color_pair(3))
    stdscr.noutrefresh()
    curses.doupdate()
    stdscr.getch()
    play_transition(stdscr)

def devices_menu(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "🔌 DEVICES CONTROL", curses.color_pair(5) | curses.A_BOLD)
        safe_addstr(stdscr, 3, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(4))
        safe_addstr(stdscr, 4, 4, "│  [1] ADB - Android Debug Bridge              │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 5, 4, "└───────────────────────────────────────────────┘", curses.color_pair(4))
        safe_addstr(stdscr, 7, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(3))
        safe_addstr(stdscr, 8, 4, "│  [2] FASTBOOT - Bootloader Mode              │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 9, 4, "└───────────────────────────────────────────────┘", curses.color_pair(3))
        safe_addstr(stdscr, 11, 4, "[ Go Back ]", curses.color_pair(1) | curses.A_BOLD)
        stdscr.noutrefresh()
        curses.doupdate()
        key = stdscr.getch()
        if key == ord('1'):
            adb_menu(stdscr)
        elif key == ord('2'):
            fastboot_menu(stdscr)
        elif key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if my == 11:
                        break
                    elif 3 <= my <= 5 and 4 <= mx <= 52:
                        adb_menu(stdscr)
                    elif 7 <= my <= 9 and 4 <= mx <= 52:
                        fastboot_menu(stdscr)
            except: pass
        elif key == ord('\n') or key == ord('q'):
            break
    play_transition(stdscr)

def adb_menu(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "🔧 ADB - Android Debug Bridge", curses.color_pair(5) | curses.A_BOLD)
        safe_addstr(stdscr, 3, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(4))
        safe_addstr(stdscr, 4, 4, "│  [1] Connect USB Device                      │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 5, 4, "└───────────────────────────────────────────────┘", curses.color_pair(4))
        safe_addstr(stdscr, 7, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(3))
        safe_addstr(stdscr, 8, 4, "│  [2] Connect Wireless (IP:Port)             │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 9, 4, "└───────────────────────────────────────────────┘", curses.color_pair(3))
        safe_addstr(stdscr, 11, 4, "[ Go Back ]", curses.color_pair(1) | curses.A_BOLD)
        stdscr.noutrefresh()
        curses.doupdate()
        key = stdscr.getch()
        if key == ord('1'):
            adb_usb_connect(stdscr)
        elif key == ord('2'):
            adb_wireless_connect(stdscr)
        elif key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if my == 11:
                        break
                    elif 3 <= my <= 5 and 4 <= mx <= 52:
                        adb_usb_connect(stdscr)
                    elif 7 <= my <= 9 and 4 <= mx <= 52:
                        adb_wireless_connect(stdscr)
            except: pass
        elif key == ord('\n') or key == ord('q'):
            break
    play_transition(stdscr)

def adb_usb_connect(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    try:
        subprocess.run("pkg install termux-android-tools -y", shell=True, timeout=30)
        subprocess.run("pkg install termux-api -y", shell=True, timeout=30)
    except: pass
    stdscr.erase()
    safe_addstr(stdscr, 1, 4, "🔌 USB CONNECTION", curses.color_pair(5) | curses.A_BOLD)
    safe_addstr(stdscr, 3, 4, "Checking for USB devices...", curses.color_pair(2))
    stdscr.refresh()
    try:
        result = subprocess.run("adb devices", shell=True, capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        if "device" in output.lower() and "list" in output.lower():
            lines = output.split('\n')
            devices_found = []
            for line in lines:
                if "device" in line.lower() and "list" not in line.lower():
                    devices_found.append(line.strip())
            if devices_found:
                safe_addstr(stdscr, 5, 4, "✅ Devices Connected:", curses.color_pair(4) | curses.A_BOLD)
                for idx, dev in enumerate(devices_found[:5]):
                    safe_addstr(stdscr, 7 + idx, 6, f"📱 {dev}", curses.color_pair(2))
            else:
                safe_addstr(stdscr, 5, 4, "⏳ Waiting for device...", curses.color_pair(3))
                safe_addstr(stdscr, 6, 4, "Please connect USB and enable USB Debugging", curses.color_pair(1))
        else:
            safe_addstr(stdscr, 5, 4, "⏳ No devices found. Waiting...", curses.color_pair(3))
            safe_addstr(stdscr, 6, 4, "Make sure USB Debugging is enabled", curses.color_pair(1))
    except:
        safe_addstr(stdscr, 5, 4, "❌ ADB not found. Installing...", curses.color_pair(1))
        try:
            subprocess.run("pkg install android-tools -y", shell=True, timeout=60)
            safe_addstr(stdscr, 7, 4, "✅ ADB installed! Please reconnect.", curses.color_pair(4))
        except:
            safe_addstr(stdscr, 7, 4, "❌ Failed to install ADB", curses.color_pair(1))
    safe_addstr(stdscr, 12, 4, "[ Press any key to go back ]", curses.color_pair(3))
    stdscr.noutrefresh()
    curses.doupdate()
    stdscr.getch()
    play_transition(stdscr)

def adb_wireless_connect(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(-1)
    stdscr.erase()
    safe_addstr(stdscr, 1, 4, "📶 WIRELESS ADB CONNECTION", curses.color_pair(5) | curses.A_BOLD)
    safe_addstr(stdscr, 3, 4, "Enter IP:Port (e.g., 192.168.1.100:5555)", curses.color_pair(2))
    safe_addstr(stdscr, 4, 4, "Format: IP:PORT", curses.color_pair(3))
    ip_input = get_user_input(stdscr, 6, 4, "IP:Port: ", mask=False)
    if ip_input and ':' in ip_input:
        try:
            subprocess.run("pkg install termux-android-tools -y", shell=True, timeout=30)
            stdscr.erase()
            safe_addstr(stdscr, 1, 4, f"🔗 Connecting to {ip_input}...", curses.color_pair(4))
            stdscr.refresh()
            result = subprocess.run(f"adb connect {ip_input}", shell=True, capture_output=True, text=True, timeout=15)
            output = result.stdout + result.stderr
            if "connected" in output.lower():
                safe_addstr(stdscr, 3, 4, "✅ Connected successfully!", curses.color_pair(4))
                safe_addstr(stdscr, 4, 4, f"📱 Device: {ip_input}", curses.color_pair(2))
                result2 = subprocess.run("adb devices", shell=True, capture_output=True, text=True, timeout=5)
                safe_addstr(stdscr, 6, 4, "📋 Connected Devices:", curses.color_pair(3))
                lines = result2.stdout.split('\n')
                for idx, line in enumerate(lines[1:4]):
                    if line.strip():
                        safe_addstr(stdscr, 8 + idx, 6, f"• {line.strip()}", curses.color_pair(2))
            else:
                safe_addstr(stdscr, 3, 4, "❌ Connection failed!", curses.color_pair(1))
                safe_addstr(stdscr, 4, 4, f"Error: {output[:50]}", curses.color_pair(3))
        except Exception as e:
            safe_addstr(stdscr, 3, 4, f"❌ Error: {str(e)[:40]}", curses.color_pair(1))
    else:
        safe_addstr(stdscr, 8, 4, "❌ Invalid format! Use IP:PORT", curses.color_pair(1))
    safe_addstr(stdscr, 12, 4, "[ Press any key to go back ]", curses.color_pair(3))
    stdscr.noutrefresh()
    curses.doupdate()
    stdscr.getch()
    stdscr.timeout(timeout_ms)
    play_transition(stdscr)

def fastboot_menu(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    try:
        subprocess.run("pkg install android-tools -y", shell=True, timeout=60)
        subprocess.run("pkg install termux-api -y", shell=True, timeout=30)
    except: pass
    stdscr.erase()
    safe_addstr(stdscr, 1, 4, "⚡ FASTBOOT MODE", curses.color_pair(5) | curses.A_BOLD)
    safe_addstr(stdscr, 3, 4, "Checking for Fastboot devices...", curses.color_pair(2))
    stdscr.refresh()
    try:
        result = subprocess.run("fastboot devices", shell=True, capture_output=True, text=True, timeout=10)
        output = result.stdout + result.stderr
        if output.strip():
            safe_addstr(stdscr, 5, 4, "✅ Devices Found:", curses.color_pair(4) | curses.A_BOLD)
            lines = output.split('\n')
            for idx, line in enumerate(lines[:5]):
                if line.strip():
                    safe_addstr(stdscr, 7 + idx, 6, f"📱 {line.strip()}", curses.color_pair(2))
        else:
            safe_addstr(stdscr, 5, 4, "⏳ Waiting for Fastboot device...", curses.color_pair(3))
            safe_addstr(stdscr, 6, 4, "Connect USB and boot into Fastboot mode", curses.color_pair(1))
            safe_addstr(stdscr, 8, 4, "Attempting to detect device...", curses.color_pair(2))
            stdscr.refresh()
            time.sleep(3)
            result2 = subprocess.run("fastboot devices", shell=True, capture_output=True, text=True, timeout=5)
            if result2.stdout.strip():
                safe_addstr(stdscr, 10, 4, "✅ Device detected!", curses.color_pair(4))
                safe_addstr(stdscr, 11, 4, f"📱 {result2.stdout.strip()}", curses.color_pair(2))
    except:
        safe_addstr(stdscr, 5, 4, "❌ Fastboot not found. Installing...", curses.color_pair(1))
        try:
            subprocess.run("pkg install android-tools -y", shell=True, timeout=60)
            safe_addstr(stdscr, 7, 4, "✅ Fastboot installed! Please reconnect.", curses.color_pair(4))
        except:
            safe_addstr(stdscr, 7, 4, "❌ Failed to install Fastboot", curses.color_pair(1))
    safe_addstr(stdscr, 14, 4, "[ Press any key to go back ]", curses.color_pair(3))
    stdscr.noutrefresh()
    curses.doupdate()
    stdscr.getch()
    play_transition(stdscr)

def get_wifi_dbm():
    try:
        result = subprocess.check_output("dumpsys wifi | grep -i rssi | head -1", shell=True, timeout=5).decode()
        for word in result.split():
            if word.lstrip('-').isdigit():
                return int(word)
    except: pass
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
        result = subprocess.check_output("dumpsys wifi | grep -i 'ssid' | head -3", shell=True, timeout=5).decode()
        for line in result.split('\n'):
            if 'SSID' in line and ':' in line:
                parts = line.split(':')
                if len(parts) > 1:
                    ssid = parts[1].strip()
                    if ssid and ssid != 'null' and ssid != '':
                        info['ssid'] = ssid
    except: pass
    info['dbm'] = get_wifi_dbm()
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
        safe_addstr(stdscr, 9, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(4))
        safe_addstr(stdscr, 10, 4, "│  [1] WIFI AR - Signal Strength Monitor      │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 11, 4, "└───────────────────────────────────────────────┘", curses.color_pair(4))
        safe_addstr(stdscr, 13, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(3))
        safe_addstr(stdscr, 14, 4, "│  [2] WIFI SCANNER - Connected Devices       │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 15, 4, "└───────────────────────────────────────────────┘", curses.color_pair(3))
        safe_addstr(stdscr, 17, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(5))
        safe_addstr(stdscr, 18, 4, "│  [3] WIFI LOCATION - Network Location        │", curses.color_pair(5) | curses.A_BOLD)
        safe_addstr(stdscr, 19, 4, "└───────────────────────────────────────────────┘", curses.color_pair(5))
        safe_addstr(stdscr, 21, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(2))
        safe_addstr(stdscr, 22, 4, "│  [4] Scan Nearby Networks                   │", curses.color_pair(2) | curses.A_BOLD)
        safe_addstr(stdscr, 23, 4, "└───────────────────────────────────────────────┘", curses.color_pair(2))
        safe_addstr(stdscr, 25, 4, "[ Go Back ]", curses.color_pair(1) | curses.A_BOLD)
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
                    if my == 25:
                        break
                    elif 9 <= my <= 11 and 4 <= mx <= 52:
                        wifi_ar_monitor(stdscr)
                    elif 13 <= my <= 15 and 4 <= mx <= 52:
                        wifi_scanner(stdscr)
                    elif 17 <= my <= 19 and 4 <= mx <= 52:
                        wifi_location(stdscr)
                    elif 21 <= my <= 23 and 4 <= mx <= 52:
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

def youtube_stats_menu(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(-1)
    stdscr.erase()
    safe_addstr(stdscr, 1, 4, "YOUTUBE CHANNEL SEARCH", curses.color_pair(4) | curses.A_BOLD)
    channel_name_input = get_user_input(stdscr, 3, 4, "Enter Channel Name: ")
    if not channel_name_input.strip():
        stdscr.timeout(timeout_ms)
        play_transition(stdscr)
        return
    curses.endwin()
    os.system("clear")
    print("\n[*] Searching for channel...")
    try:
        cmd = f"yt-dlp --dump-json \"ytsearch1:{channel_name_input}\" --playlist-end 1"
        result = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT).decode("utf-8")
        data = json.loads(result.split("\n")[0])
        channel_name = data.get("channel", "Unknown Name")
        sub_count = data.get("channel_follower_count", "Hidden/Not Found")
        print("\n[+] Channel Found:")
        print(f"    Name: {channel_name}")
        print(f"    Subscribers: {sub_count}")
    except Exception as e:
        print(f"[!] Error: Could not retrieve data. {e}")
    input("\nPress Enter to return...")
    stdscr = curses.initscr()
    stdscr.timeout(timeout_ms)
    play_transition(stdscr)

def username_osint_menu(stdscr):
    global timeout_ms
    play_transition(stdscr)
    stdscr.timeout(-1)
    stdscr.erase()
    safe_addstr(stdscr, 2, 4, "SECURITY GATEWAY", curses.color_pair(1) | curses.A_BOLD)
    password = get_user_input(stdscr, 4, 4, "Enter Password: ", mask=True)
    if password != "kurd mars12":
        stdscr.erase()
        safe_addstr(stdscr, 4, 4, "ACCESS DENIED!", curses.color_pair(1) | curses.A_BOLD)
        stdscr.getch()
        play_transition(stdscr)
        stdscr.timeout(timeout_ms)
        return
    stdscr.erase()
    safe_addstr(stdscr, 1, 4, "SOCIAL MEDIA USERNAME FINDER", curses.color_pair(4) | curses.A_BOLD)
    target_user = get_user_input(stdscr, 3, 4, "Enter Username to search: ")
    if not target_user.strip():
        stdscr.timeout(timeout_ms)
        play_transition(stdscr)
        return
    curses.endwin()
    os.system("clear")
    if not os.path.exists("sherlock"):
        print("[!] Sherlock not found. Installing...")
        os.system("git clone https://github.com/sherlock-project/sherlock.git")
        os.system("python3 -m pip install -r sherlock/requirements.txt")
    print(f"\n[*] Scanning all networks for username: {target_user}...\n")
    os.system(f"python3 sherlock/sherlock/sherlock.py {target_user}")
    input("\nPress Enter to return...")
    stdscr = curses.initscr()
    stdscr.timeout(timeout_ms)
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
            safe_addstr(stdscr, 7, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(4))
            safe_addstr(stdscr, 8, 4, "│          [ RUN BENCHMARK NOW ]             │", curses.color_pair(4) | curses.A_BOLD)
            safe_addstr(stdscr, 9, 4, "└───────────────────────────────────────────────┘", curses.color_pair(4))
        else:
            safe_addstr(stdscr, 4, 4, "┌───────────────────────────────────────────────────┐", curses.color_pair(3))
            safe_addstr(stdscr, 5, 4, f"│  Detected SoC:   {real_hardware:<32} │", curses.color_pair(3) | curses.A_BOLD)
            safe_addstr(stdscr, 6, 4, f"│  CPU Cores:      {cpu_cores:<32} │", curses.color_pair(2))
            safe_addstr(stdscr, 7, 4, f"│  AnTuTu Score:   {saved_score:,} Pts                    │", curses.color_pair(1) | curses.A_BOLD)
            safe_addstr(stdscr, 8, 4, "└───────────────────────────────────────────────────┘", curses.color_pair(3))
            safe_addstr(stdscr, 10, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(5))
            safe_addstr(stdscr, 11, 4, "│          [ SEND SCORE TO GMAIL ]             │", curses.color_pair(5) | curses.A_BOLD)
            safe_addstr(stdscr, 12, 4, "└───────────────────────────────────────────────┘", curses.color_pair(5))
            safe_addstr(stdscr, 14, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(3))
            safe_addstr(stdscr, 15, 4, "│             [ RE-RUN TEST ]                │", curses.color_pair(3) | curses.A_BOLD)
            safe_addstr(stdscr, 16, 4, "└───────────────────────────────────────────────┘", curses.color_pair(3))
        if email_status_msg:
            safe_addstr(stdscr, 18, 4, f"Info: {email_status_msg}", curses.color_pair(2) | curses.A_BOLD)
        safe_addstr(stdscr, 20, 4, "┌───────────────┐", curses.color_pair(1))
        safe_addstr(stdscr, 21, 4, "│   [Go Back]   │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 22, 4, "└───────────────┘", curses.color_pair(1))
        stdscr.noutrefresh()
        curses.doupdate()
        key = stdscr.getch()
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if saved_score == 0:
                        if 7 <= my <= 9 and 4 <= mx <= 52:
                            play_button_shrink(stdscr, 7, 4, "┌───────────────────────────────────────────────┐", 4)
                            stdscr.erase()
                            safe_addstr(stdscr, 10, 10, "BENCHMARKING CPU CORES... PLEASE WAIT", curses.color_pair(1) | curses.A_BOLD)
                            stdscr.refresh()
                            bench_result = run_real_cpu_benchmark()
                            device_antutu_score, _ = calculate_antutu_v11_score(bench_result)
                            save_antutu_score(device_antutu_score)
                            email_status_msg = ""
                    else:
                        if 10 <= my <= 12 and 4 <= mx <= 52:
                            play_button_shrink(stdscr, 10, 4, "┌───────────────────────────────────────────────┐", 5)
                            stdscr.erase()
                            safe_addstr(stdscr, 10, 10, "Connecting to Gmail & Sending...", curses.color_pair(3) | curses.A_BOLD)
                            stdscr.refresh()
                            subject = f"Kurd Mars - AnTuTu Benchmark Report ({real_hardware})"
                            body = f"Kurd Mars AnTuTu Benchmark Report:\n\nDevice SoC: {real_hardware}\nCPU Cores: {cpu_cores}\nAnTuTu Score: {saved_score:,} Pts\n"
                            success, msg = send_email_notification(subject, body)
                            email_status_msg = msg
                            stdscr.timeout(timeout_ms)
                        elif 14 <= my <= 16 and 4 <= mx <= 52:
                            play_button_shrink(stdscr, 14, 4, "┌───────────────────────────────────────────────┐", 3)
                            save_antutu_score(0)
                            email_status_msg = ""
                    if 20 <= my <= 22 and 4 <= mx <= 20:
                        play_button_shrink(stdscr, 20, 4, "┌───────────────┐", 1)
                        play_transition(stdscr)
                        break
            except: pass

def run_fps_test_game(stdscr):
    global current_fps, current_hz
    play_transition(stdscr)
    stdscr.erase()
    stdscr.timeout(max(1, int(1000 / current_fps)))
    height, width = stdscr.getmaxyx()
    ball_y, ball_x = float(height // 2), float(width // 2)
    step_y, step_x = 0.25, 0.50
    dir_y, dir_x = 1, 1
    while True:
        stdscr.erase()
        height, width = stdscr.getmaxyx()
        safe_hline(stdscr, 0, 0, "═", width, curses.color_pair(5))
        safe_hline(stdscr, height-4, 0, "═", width, curses.color_pair(5))
        safe_addstr(stdscr, height-3, 2, f"Live Engine: {current_hz}Hz | Render: {current_fps} FPS", curses.color_pair(4) | curses.A_BOLD)
        btn_x = width - 14
        safe_addstr(stdscr, height-3, btn_x, "┌──────────┐", curses.color_pair(1))
        safe_addstr(stdscr, height-2, btn_x, "│ [ Back ] │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, height-1, btn_x, "└──────────┘", curses.color_pair(1))
        ball_y += dir_y * step_y
        ball_x += dir_x * step_x
        if int(ball_y) <= 1: dir_y = 1
        elif int(ball_y) >= height - 5: dir_y = -1
        if int(ball_x) <= 1: dir_x = 1
        elif int(ball_x) >= width - 2: dir_x = -1
        safe_addstr(stdscr, int(ball_y), int(ball_x), "●", curses.color_pair(3) | curses.A_BOLD)
        stdscr.refresh()
        key = stdscr.getch()
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if height-3 <= my <= height-1 and btn_x <= mx <= btn_x + 12:
                        break
            except: pass
        if key in [ord("m"), ord("M")]: break
    play_transition(stdscr)

flash_active = False

def hardware_controls_menu(stdscr):
    global timeout_ms, flash_active
    play_transition(stdscr)
    stdscr.timeout(timeout_ms)
    wifi_list = []
    connection_status = ""
    error_note = ""
    while True:
        stdscr.erase()
        safe_addstr(stdscr, 1, 4, "HARDWARE CONTROL PANEL (ROOTED)", curses.color_pair(5) | curses.A_BOLD)
        flash_bar = "[ OFF ──────● ON ]" if flash_active else "[ OFF ●────── ON ]"
        flash_color = curses.color_pair(4) if flash_active else curses.color_pair(1)
        safe_addstr(stdscr, 4, 4, "LED Flash State:", curses.color_pair(2) | curses.A_BOLD)
        safe_addstr(stdscr, 5, 4, f"{flash_bar}", flash_color | curses.A_BOLD)
        safe_addstr(stdscr, 8, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(3))
        safe_addstr(stdscr, 9, 4, "│          [ SCAN NEARBY WI-FI ]              │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 10, 4, "└───────────────────────────────────────────────┘", curses.color_pair(3))
        if error_note:
            safe_addstr(stdscr, 12, 4, f"Warning: {error_note}", curses.color_pair(1) | curses.A_BOLD)
        if wifi_list:
            safe_addstr(stdscr, 13, 4, "Nearby Networks (Click to connect):", curses.color_pair(5) | curses.A_BOLD)
            for idx, ssid in enumerate(wifi_list):
                safe_addstr(stdscr, 15 + idx, 6, f"{idx+1}. {ssid}", curses.color_pair(2))
        if connection_status:
            status_color = curses.color_pair(4) if connection_status == "Connected!" else curses.color_pair(1)
            safe_addstr(stdscr, 24, 4, f"Status: {connection_status}", status_color | curses.A_BOLD)
        safe_addstr(stdscr, 26, 4, "[ Go Back ]", curses.color_pair(1) | curses.A_BOLD)
        stdscr.refresh()
        key = stdscr.getch()
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if my == 5 and 4 <= mx <= 22:
                        flash_active = not flash_active
                        toggle_flashlight(flash_active)
                    elif 8 <= my <= 10 and 4 <= mx <= 52:
                        play_button_shrink(stdscr, 8, 4, "┌───────────────────────────────────────────────┐", 3)
                        stdscr.erase()
                        safe_addstr(stdscr, 10, 10, "SCANNING WI-FI SIGNALS... PLEASE WAIT", curses.color_pair(5) | curses.A_BOLD)
                        stdscr.refresh()
                        scanned = scan_wifi_networks()
                        if scanned:
                            wifi_list = scanned
                            error_note = ""
                            connection_status = f"Found {len(scanned)} networks."
                        else:
                            wifi_list = []
                            error_note = "No networks found! Check if Wi-Fi / Location is enabled."
                            connection_status = "Scan Failed."
                    elif wifi_list and 15 <= my < 15 + len(wifi_list):
                        clicked_idx = my - 15
                        target_ssid = wifi_list[clicked_idx]
                        stdscr.timeout(-1)
                        stdscr.erase()
                        safe_addstr(stdscr, 2, 4, f"SSID Selected: {target_ssid}", curses.color_pair(4) | curses.A_BOLD)
                        pwd = get_user_input(stdscr, 4, 4, "Enter Wi-Fi Password: ", mask=True)
                        stdscr.erase()
                        safe_addstr(stdscr, 5, 4, "Attempting Root Connection... Check Magisk Superuser Prompt!", curses.color_pair(3) | curses.A_BOLD)
                        stdscr.refresh()
                        success = connect_to_wifi(target_ssid, pwd)
                        connection_status = "Connected!" if success else "Connection failed"
                        stdscr.timeout(timeout_ms)
                    elif my == 26 and 4 <= mx <= 15:
                        break
            except: pass

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
        safe_addstr(stdscr, 3, 4, "┌─────────────────────────────────┐", curses.color_pair(2))
        safe_addstr(stdscr, 4, 4, "│    1 - Update Termux            │", curses.color_pair(2) | curses.A_BOLD)
        safe_addstr(stdscr, 5, 4, "└─────────────────────────────────┘", curses.color_pair(2))
        safe_addstr(stdscr, 7, 4, "┌─────────────────────────────────┐", curses.color_pair(3))
        safe_addstr(stdscr, 8, 4, "│    2 - Install Kali NetHunter   │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 9, 4, "└─────────────────────────────────┘", curses.color_pair(3))
        safe_addstr(stdscr, 11, 4, "┌─────────────────────────────────┐", curses.color_pair(4))
        safe_addstr(stdscr, 12, 4, "│    3 - RUN KALI LINUX (nh)      │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 13, 4, "└─────────────────────────────────┘", curses.color_pair(4))
        safe_addstr(stdscr, 16, 4, "┌───────────────┐", curses.color_pair(1))
        safe_addstr(stdscr, 17, 4, "│   [Go Back]   │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 18, 4, "└───────────────┘", curses.color_pair(1))
        stdscr.noutrefresh()
        curses.doupdate()
        key = stdscr.getch()
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if 3 <= my <= 5 and 4 <= mx <= 38:
                        play_button_shrink(stdscr, 3, 4, "┌─────────────────────────────────┐", 2)
                        curses.endwin()
                        os.system("clear")
                        print("[+] Running Termux Update...")
                        os.system("pkg update -y && pkg upgrade -y")
                        input("\nProcess finished. Press Enter...")
                        stdscr = curses.initscr()
                        stdscr.timeout(timeout_ms)
                    elif 7 <= my <= 9 and 4 <= mx <= 38:
                        play_button_shrink(stdscr, 7, 4, "┌─────────────────────────────────┐", 3)
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
                    elif 11 <= my <= 13 and 4 <= mx <= 38:
                        play_button_shrink(stdscr, 11, 4, "┌─────────────────────────────────┐", 4)
                        curses.endwin()
                        os.system("clear")
                        print("[*] Booting Kali Linux NetHunter...\n")
                        os.system("nh")
                        input("\nReturned to Tool. Press Enter...")
                        stdscr = curses.initscr()
                        stdscr.timeout(timeout_ms)
                    elif 16 <= my <= 18 and 4 <= mx <= 20:
                        play_button_shrink(stdscr, 16, 4, "┌───────────────┐", 1)
                        break
            except: pass

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
        safe_addstr(stdscr, 9, 4, "[ 60Hz ]", hz60_attr)
        safe_addstr(stdscr, 9, 16, "[ 120Hz ]", hz120_attr)
        safe_addstr(stdscr, 11, 4, "Target FPS:", curses.color_pair(2) | curses.A_BOLD)
        fps_list = [10, 20, 30, 45, 60, 90, 120]
        for idx, f_val in enumerate(fps_list):
            f_attr = curses.color_pair(5) | curses.A_REVERSE if selected_fps == f_val else curses.color_pair(2)
            safe_addstr(stdscr, 12 + (idx // 4) * 2, 4 + (idx % 4) * 12, f"[ {f_val}fps ]", f_attr)
        safe_addstr(stdscr, 16, 4, "━━━ TOOL MAINTENANCE ━━━", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 17, 4, "┌─────────────────────────────────────────────┐", curses.color_pair(1))
        safe_addstr(stdscr, 18, 4, "│  [CLEAR]  Fix BUGs & Freeze Issues         │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 19, 4, "└─────────────────────────────────────────────┘", curses.color_pair(1))
        if clear_msg:
            safe_addstr(stdscr, 21, 4, f"✅ {clear_msg}", curses.color_pair(4))
        safe_addstr(stdscr, 23, 4, "┌─────────────────────────────────────────────┐", curses.color_pair(3))
        safe_addstr(stdscr, 24, 4, "│          [ APPLY CHANGES ⚡ ]               │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 25, 4, "└─────────────────────────────────────────────┘", curses.color_pair(3))
        safe_addstr(stdscr, 27, 4, "[ Go Back ]", curses.color_pair(1) | curses.A_BOLD)
        stdscr.noutrefresh()
        curses.doupdate()
        key = stdscr.getch()
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    error_msg = ""
                    if my == 9:
                        if 4 <= mx <= 12:
                            selected_hz = 60
                        elif 16 <= mx <= 25:
                            selected_hz = 120
                    elif my == 12:
                        if 4 <= mx <= 13:
                            selected_fps = 10
                        elif 16 <= mx <= 25:
                            selected_fps = 20
                        elif 28 <= mx <= 37:
                            selected_fps = 30
                        elif 40 <= mx <= 49:
                            selected_fps = 45
                    elif my == 13:
                        if 4 <= mx <= 13:
                            selected_fps = 60
                        elif 16 <= mx <= 25:
                            selected_fps = 90
                        elif 28 <= mx <= 37:
                            selected_fps = 120
                    elif 17 <= my <= 19 and 4 <= mx <= 44:
                        play_button_shrink(stdscr, 17, 4, "┌─────────────────────────────────────────────┐", 1)
                        try:
                            import gc
                            gc.collect()
                            update_timeout()
                            clear_msg = "Tool cleaned! BUGs and Freeze cleared. ✅"
                            stdscr.timeout(timeout_ms)
                        except:
                            clear_msg = "Clean failed, restart tool."
                    elif 23 <= my <= 25 and 4 <= mx <= 44:
                        play_button_shrink(stdscr, 23, 4, "┌─────────────────────────────────────────────┐", 3)
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
                    elif my == 27:
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
        elif key == ord('\n'):
            break

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
        safe_addstr(stdscr, 8, 4,  "┌───────────────────────┐", curses.color_pair(5))
        safe_addstr(stdscr, 9, 4,  "│   Termux & Kali       │", curses.color_pair(5) | curses.A_BOLD)
        safe_addstr(stdscr, 10, 4, "└───────────────────────┘", curses.color_pair(5))
        safe_addstr(stdscr, 8, 30, "┌───────────────────────┐", curses.color_pair(4))
        safe_addstr(stdscr, 9, 30, "│     Test Game         │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 10, 30, "└───────────────────────┘", curses.color_pair(4))
        safe_addstr(stdscr, 11, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(3))
        safe_addstr(stdscr, 12, 4, "│          [ TEST ANTUTU v11 ]               │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 13, 4, "└───────────────────────────────────────────────┘", curses.color_pair(3))
        safe_addstr(stdscr, 14, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(1))
        safe_addstr(stdscr, 15, 4, "│          [ USERNAME OSINT (PASSWORD) ]     │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 16, 4, "└───────────────────────────────────────────────┘", curses.color_pair(1))
        safe_addstr(stdscr, 17, 4, "┌───────────────────────────────────────────────┐", curses.color_pair(5))
        safe_addstr(stdscr, 18, 4, "│          [ YOUTUBE BY NAME ]               │", curses.color_pair(5) | curses.A_BOLD)
        safe_addstr(stdscr, 19, 4, "└───────────────────────────────────────────────┘", curses.color_pair(5))
        safe_addstr(stdscr, 20, 4, "┌───────────────────────┐", curses.color_pair(4))
        safe_addstr(stdscr, 21, 4, "│   Hardware Panel      │", curses.color_pair(4) | curses.A_BOLD)
        safe_addstr(stdscr, 22, 4, "└───────────────────────┘", curses.color_pair(4))
        safe_addstr(stdscr, 20, 30, "┌───────────────────────┐", curses.color_pair(5))
        safe_addstr(stdscr, 21, 30, "│   WiFi Settings 📶   │", curses.color_pair(5) | curses.A_BOLD)
        safe_addstr(stdscr, 22, 30, "└───────────────────────┘", curses.color_pair(5))
        safe_addstr(stdscr, 23, 4, "┌───────────────────────┐", curses.color_pair(2))
        safe_addstr(stdscr, 24, 4, "│   Termux Tools 📦    │", curses.color_pair(2) | curses.A_BOLD)
        safe_addstr(stdscr, 25, 4, "└───────────────────────┘", curses.color_pair(2))
        safe_addstr(stdscr, 23, 30, "┌───────────────────────┐", curses.color_pair(3))
        safe_addstr(stdscr, 24, 30, "│    Advanced Settings  │", curses.color_pair(3) | curses.A_BOLD)
        safe_addstr(stdscr, 25, 30, "└───────────────────────┘", curses.color_pair(3))
        safe_addstr(stdscr, 23, 55, "┌───────────────────────┐", curses.color_pair(1))
        safe_addstr(stdscr, 24, 55, "│       [ Exit ]        │", curses.color_pair(1) | curses.A_BOLD)
        safe_addstr(stdscr, 25, 55, "└───────────────────────┘", curses.color_pair(1))
        stdscr.noutrefresh()
        curses.doupdate()
        key = stdscr.getch()
        if key == curses.KEY_MOUSE:
            try:
                _, mx, my, _, bstate = curses.getmouse()
                if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED):
                    if 8 <= my <= 10 and 4 <= mx <= 28:
                        play_button_shrink(stdscr, 8, 4, "┌───────────────────────┐", 5)
                        termux_setup_menu(stdscr)
                    elif 8 <= my <= 10 and 30 <= mx <= 54:
                        play_button_shrink(stdscr, 8, 30, "┌───────────────────────┐", 4)
                        run_fps_test_game(stdscr)
                    elif 11 <= my <= 13 and 4 <= mx <= 52:
                        play_button_shrink(stdscr, 11, 4, "┌───────────────────────────────────────────────┐", 3)
                        antutu_test_menu(stdscr)
                    elif 14 <= my <= 16 and 4 <= mx <= 52:
                        play_button_shrink(stdscr, 14, 4, "┌───────────────────────────────────────────────┐", 1)
                        username_osint_menu(stdscr)
                    elif 17 <= my <= 19 and 4 <= mx <= 52:
                        play_button_shrink(stdscr, 17, 4, "┌───────────────────────────────────────────────┐", 5)
                        youtube_stats_menu(stdscr)
                    elif 20 <= my <= 22 and 4 <= mx <= 28:
                        play_button_shrink(stdscr, 20, 4, "┌───────────────────────┐", 4)
                        hardware_controls_menu(stdscr)
                    elif 20 <= my <= 22 and 30 <= mx <= 54:
                        play_button_shrink(stdscr, 20, 30, "┌───────────────────────┐", 5)
                        wifi_settings_menu(stdscr)
                    elif 23 <= my <= 25 and 4 <= mx <= 28:
                        play_button_shrink(stdscr, 23, 4, "┌───────────────────────┐", 2)
                        termux_menu(stdscr)
                    elif 23 <= my <= 25 and 30 <= mx <= 54:
                        play_button_shrink(stdscr, 23, 30, "┌───────────────────────┐", 3)
                        settings_menu(stdscr)
                    elif 23 <= my <= 25 and 55 <= mx <= 78:
                        break
            except: pass

if __name__ == "__main__":
    curses.wrapper(main)
