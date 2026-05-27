# ============================================================
#                MX GAMER AUTO URL NOTIFIER
# ============================================================
#
#  🚀 Auto Detect Tunnel URL
#  📡 Send URL To Telegram Automatically
#  🔥 Works With Cloudflared Tunnel
#
# ============================================================

import subprocess
import requests
import re
import time

# ============================================================
# TELEGRAM CONFIG
# ============================================================

BOT_TOKEN = "8670148368:AAFhDL7Yyyqe10vkdDTAktm_Pfl8plaqrGM"
CHAT_ID = "8624574265"

# ============================================================
# SEND MESSAGE FUNCTION
# ============================================================

def send_telegram_message(text):
    try:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

        data = {
            "chat_id": CHAT_ID,
            "text": text
        }

        response = requests.post(url, data=data)

        if response.status_code == 200:
            print("[✓] Message Sent Successfully")
        else:
            print("[!] Telegram Error")

    except Exception as e:
        print("[ERROR]", e)

# ============================================================
# START CLOUDFLARED
# ============================================================

print("🚀 Starting Cloudflare Tunnel...")

process = subprocess.Popen(
    ["cloudflared", "tunnel", "--url", "http://localhost:5000"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

# ============================================================
# DETECT URL
# ============================================================

url_found = False

for line in process.stdout:

    print(line.strip())

    match = re.search(
        r"https://[-a-zA-Z0-9]+\.trycloudflare\.com",
        line
    )

    if match and not url_found:

        tunnel_url = match.group(0)

        print(f"\n[✓] Tunnel URL Found: {tunnel_url}")

        # SEND TO TELEGRAM
        send_telegram_message(
            f"🔥 NEW TUNNEL URL GENERATED 🔥\n\n"
            f"🌍 URL:\n{tunnel_url}"
        )

        url_found = True

# ============================================================
# END
# ============================================================
