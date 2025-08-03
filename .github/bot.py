#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# 🔥 PHOENIX PROXY BOT 12.0 🔥

import os
import sys
import time
import random
import requests
import threading
from datetime import datetime, timedelta
from telegram import Bot, Update, ParseMode
from telegram.ext import Updater, CommandHandler, CallbackContext
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
CONFIG = {
    "PROXY_SOURCES": {
        "SOCKS5": [
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
            "https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt"
        ],
        "HTTPS": [
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
            "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt"
        ],
        "SOCKS4": [
            "https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4",
            "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
            "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt"
        ]
    },
    "PROXY_FILES": {
        "SOCKS5": "phoenix_socks5.txt",
        "HTTPS": "phoenix_https.txt",
        "SOCKS4": "phoenix_socks4.txt"
    },
    "UPDATE_INTERVAL": 300,  # 5 minutes in seconds
    "MAX_PROXIES": 5000,  # Max proxies to collect per type
    "VALIDATION_SITES": [
        "https://www.google.com",
        "https://www.facebook.com",
        "https://www.amazon.com"
    ],
    "VALIDATION_TIMEOUT": 5,
    "MAX_THREADS": 100
}

# Telegram Bot Token from environment
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not TELEGRAM_TOKEN:
    sys.exit("Error: TELEGRAM_BOT_TOKEN not found in .env file")

# Initialize bot
bot = Bot(token=TELEGRAM_TOKEN)

class PhoenixProxyBot:
    def __init__(self):
        self.proxies = {
            "SOCKS5": [],
            "HTTPS": [],
            "SOCKS4": []
        }
        self.last_update = {
            "SOCKS5": None,
            "HTTPS": None,
            "SOCKS4": None
        }
        self.lock = threading.Lock()
        self.update_thread = None
        self.running = False
        
        # Start background updater
        self.start_background_updater()

    def start_background_updater(self):
        """Start the background proxy updater thread"""
        if self.update_thread and self.update_thread.is_alive():
            return
            
        self.running = True
        self.update_thread = threading.Thread(target=self.background_updater)
        self.update_thread.daemon = True
        self.update_thread.start()

    def background_updater(self):
        """Background thread that updates proxies periodically"""
        while self.running:
            try:
                self.update_all_proxies()
                
                # Calculate sleep time until next update
                now = datetime.now()
                next_update = now + timedelta(seconds=CONFIG["UPDATE_INTERVAL"])
                
                while now < next_update and self.running:
                    time.sleep(1)
                    now = datetime.now()
                    
            except Exception as e:
                print(f"Background updater error: {e}")
                time.sleep(60)

    def update_all_proxies(self):
        """Update all proxy types"""
        for proxy_type in ["SOCKS5", "HTTPS", "SOCKS4"]:
            try:
                self.update_proxies(proxy_type)
                self.validate_proxies(proxy_type)
                self.last_update[proxy_type] = datetime.now()
                print(f"Updated {proxy_type} proxies: {len(self.proxies[proxy_type])}")
            except Exception as e:
                print(f"Error updating {proxy_type} proxies: {e}")

    def update_proxies(self, proxy_type):
        """Fetch fresh proxies from sources"""
        new_proxies = []
        
        for source in CONFIG["PROXY_SOURCES"][proxy_type]:
            try:
                response = requests.get(source, timeout=10)
                if response.status_code == 200:
                    new_proxies.extend(response.text.splitlines())
            except Exception as e:
                print(f"Error fetching from {source}: {e}")
                continue
        
        # Clean and deduplicate proxies
        cleaned_proxies = []
        for proxy in new_proxies:
            proxy = proxy.strip()
            if proxy and ":" in proxy:
                cleaned_proxies.append(proxy)
        
        # Remove duplicates
        unique_proxies = list(set(cleaned_proxies))
        
        # Limit the number of proxies
        if len(unique_proxies) > CONFIG["MAX_PROXIES"]:
            unique_proxies = unique_proxies[:CONFIG["MAX_PROXIES"]]
        
        with self.lock:
            self.proxies[proxy_type] = unique_proxies
            
        # Save to file
        with open(CONFIG["PROXY_FILES"][proxy_type], 'w') as f:
            f.write("\n".join(unique_proxies))

    def validate_proxies(self, proxy_type):
        """Validate proxies with multi-threading"""
        if not self.proxies[proxy_type]:
            return
            
        valid_proxies = []
        lock = threading.Lock()
        
        def test_proxy(proxy):
            try:
                proxies = {
                    "http": f"{proxy_type.lower()}://{proxy}",
                    "https": f"{proxy_type.lower()}://{proxy}"
                }
                
                # Test with multiple sites
                for site in random.sample(CONFIG["VALIDATION_SITES"], 2):
                    try:
                        start = time.time()
                        response = requests.get(
                            site,
                            proxies=proxies,
                            timeout=CONFIG["VALIDATION_TIMEOUT"]
                        )
                        if response.status_code == 200 and (time.time() - start) < 3:
                            with lock:
                                valid_proxies.append(proxy)
                            break
                    except:
                        continue
            except:
                pass
        
        # Use ThreadPoolExecutor for validation
        with ThreadPoolExecutor(max_workers=CONFIG["MAX_THREADS"]) as executor:
            executor.map(test_proxy, self.proxies[proxy_type])
        
        with self.lock:
            self.proxies[proxy_type] = valid_proxies
            
        # Update file with only valid proxies
        with open(CONFIG["PROXY_FILES"][proxy_type], 'w') as f:
            f.write("\n".join(valid_proxies))

    def get_proxy_count(self, proxy_type):
        """Get count of available proxies"""
        with self.lock:
            return len(self.proxies.get(proxy_type, []))

    def get_proxy_list(self, proxy_type, limit=50):
        """Get list of proxies with optional limit"""
        with self.lock:
            proxies = self.proxies.get(proxy_type, [])
            return proxies[:limit]

    def get_last_update_time(self, proxy_type):
        """Get formatted last update time"""
        if not self.last_update[proxy_type]:
            return "Never"
        return self.last_update[proxy_type].strftime("%Y-%m-%d %H:%M:%S")

    def get_next_update_time(self):
        """Get formatted next update time"""
        now = datetime.now()
        next_update = now + timedelta(seconds=CONFIG["UPDATE_INTERVAL"])
        return next_update.strftime("%H:%M:%S")

    def format_proxy_message(self, proxy_type):
        """Create beautifully formatted message for Telegram"""
        count = self.get_proxy_count(proxy_type)
        last_update = self.get_last_update_time(proxy_type)
        next_update = self.get_next_update_time()
        
        emoji = {
            "SOCKS5": "🔥",
            "HTTPS": "⚡",
            "SOCKS4": "💎"
        }.get(proxy_type, "📌")
        
        message = [
            f"{emoji} *{proxy_type} Proxies - PHOENIX CRACKER 12.0* {emoji}",
            "",
            f"📦 *Count:* `{count}`",
            f"🔄 *Last Updated:* `{last_update}`",
            f"⏳ *Next Update:* `{next_update}`",
            f"📁 *Source:* `{CONFIG['PROXY_FILES'][proxy_type]}`",
            "",
            "*Sample Proxies:*",
        ]
        
        # Add sample proxies (first 5)
        sample_proxies = self.get_proxy_list(proxy_type, 5)
        for proxy in sample_proxies:
            message.append(f"`{proxy}`")
        
        message.extend([
            "",
            "💡 *Tip:* Use /get_{} to download full list".format(proxy_type.lower()),
            "",
            "⚡ *Powered by PHOENIX CRACKER 12.0* ⚡"
        ])
        
        return "\n".join(message)

    def send_proxy_file(self, chat_id, proxy_type):
        """Send the actual proxy file to user"""
        filename = CONFIG["PROXY_FILES"][proxy_type]
        if not os.path.exists(filename):
            return False
            
        with open(filename, 'rb') as f:
            bot.send_document(
                chat_id=chat_id,
                document=f,
                filename=f"phoenix_{proxy_type.lower()}_proxies.txt",
                caption=f"⚡ PHOENIX {proxy_type} Proxies - {datetime.now().strftime('%Y-%m-%d')} ⚡"
            )
        return True

# Telegram command handlers
def start(update: Update, context: CallbackContext):
    """Send welcome message"""
    message = [
        "🔥 *Welcome to PHOENIX PROXY BOT 12.0* 🔥",
        "",
        "I provide *high-quality, fresh proxies* for PHOENIX CRACKER 12.0",
        "",
        "*Available commands:*",
        "/socks5 - Get SOCKS5 proxies",
        "/https - Get HTTPS proxies",
        "/socks4 - Get SOCKS4 proxies",
        "/get_socks5 - Download SOCKS5 list",
        "/get_https - Download HTTPS list",
        "/get_socks4 - Download SOCKS4 list",
        "/status - Show proxy statistics",
        "",
        "⚡ *Auto-updated every 5 minutes* ⚡"
    ]
    
    update.message.reply_text(
        text="\n".join(message),
        parse_mode=ParseMode.MARKDOWN
    )

def send_proxies(update: Update, context: CallbackContext, proxy_type):
    """Send proxy information for specific type"""
    message = phoenix_bot.format_proxy_message(proxy_type)
    update.message.reply_text(
        text=message,
        parse_mode=ParseMode.MARKDOWN
    )

def socks5(update: Update, context: CallbackContext):
    """Handle SOCKS5 command"""
    send_proxies(update, context, "SOCKS5")

def https(update: Update, context: CallbackContext):
    """Handle HTTPS command"""
    send_proxies(update, context, "HTTPS")

def socks4(update: Update, context: CallbackContext):
    """Handle SOCKS4 command"""
    send_proxies(update, context, "SOCKS4")

def get_socks5(update: Update, context: CallbackContext):
    """Handle get_socks5 command"""
    if phoenix_bot.send_proxy_file(update.message.chat_id, "SOCKS5"):
        update.message.reply_text("✅ SOCKS5 proxies sent!")
    else:
        update.message.reply_text("❌ No SOCKS5 proxies available yet")

def get_https(update: Update, context: CallbackContext):
    """Handle get_https command"""
    if phoenix_bot.send_proxy_file(update.message.chat_id, "HTTPS"):
        update.message.reply_text("✅ HTTPS proxies sent!")
    else:
        update.message.reply_text("❌ No HTTPS proxies available yet")

def get_socks4(update: Update, context: CallbackContext):
    """Handle get_socks4 command"""
    if phoenix_bot.send_proxy_file(update.message.chat_id, "SOCKS4"):
        update.message.reply_text("✅ SOCKS4 proxies sent!")
    else:
        update.message.reply_text("❌ No SOCKS4 proxies available yet")

def status(update: Update, context: CallbackContext):
    """Show system status"""
    message = [
        "⚡ *PHOENIX PROXY BOT STATUS* ⚡",
        "",
        f"🔹 *SOCKS5 Proxies:* `{phoenix_bot.get_proxy_count('SOCKS5')}`",
        f"🔹 *HTTPS Proxies:* `{phoenix_bot.get_proxy_count('HTTPS')}`",
        f"🔹 *SOCKS4 Proxies:* `{phoenix_bot.get_proxy_count('SOCKS4')}`",
        "",
        f"🔄 *Next Update:* `{phoenix_bot.get_next_update_time()}`",
        "",
        "🏆 *Powered by PHOENIX CRACKER 12.0* 🏆"
    ]
    
    update.message.reply_text(
        text="\n".join(message),
        parse_mode=ParseMode.MARKDOWN
    )

def error_handler(update: Update, context: CallbackContext):
    """Log errors"""
    print(f"Update {update} caused error {context.error}")

# Initialize the bot
phoenix_bot = PhoenixProxyBot()

def main():
    """Start the bot"""
    updater = Updater(token=TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher

    # Add handlers
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", start))
    dp.add_handler(CommandHandler("socks5", socks5))
    dp.add_handler(CommandHandler("https", https))
    dp.add_handler(CommandHandler("socks4", socks4))
    dp.add_handler(CommandHandler("get_socks5", get_socks5))
    dp.add_handler(CommandHandler("get_https", get_https))
    dp.add_handler(CommandHandler("get_socks4", get_socks4))
    dp.add_handler(CommandHandler("status", status))
    
    # Error handler
    dp.add_error_handler(error_handler)

    # Start the Bot
    updater.start_polling()
    print("🔥 PHOENIX PROXY BOT 12.0 is running...")
    
    # Run the bot until you press Ctrl-C
    updater.idle()
    
    # Cleanup
    phoenix_bot.running = False
    if phoenix_bot.update_thread:
        phoenix_bot.update_thread.join()

if __name__ == '__main__':
    main()
