
import logging
import re
import os
import yt_dlp
from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# --- RENDER KEEP-ALIVE ---
app = Flask('')
@app.route('/')
def home(): return "OAuth2 Bot is Running!"

def run():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)

def escape_md(text):
    if not text: return ""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))

# --- OAUTH2 EXTRACTION LOGIC ---
def get_advanced_info(url):
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'noplaylist': True,
        # OAuth2 Setup
        'username': 'oauth2',
        'cache_dir': './yt_dlp_cache', # Token yahan save hoga
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info: return None

            formats = info.get("formats", [])
            best_mp4 = next((f for f in formats if f.get("ext") == "mp4" and f.get("vcodec") != "none" and f.get("acodec") != "none"), None)
            best_audio = next((f for f in formats if f.get("vcodec") == "none" and f.get("acodec") != "none"), None)

            return {
                "title": info.get("title"),
                "uploader": info.get("uploader"),
                "views": info.get("view_count", 0),
                "duration": info.get("duration", 0),
                "likes": info.get("like_count", "N/A"),
                "thumbnail": info.get("thumbnail"),
                "video_url": best_mp4["url"] if best_mp4 else None,
                "audio_url": best_audio["url"] if best_audio else None,
            }
    except Exception as e:
        logging.error(f"Error: {e}")
        return str(e)

# --- BOT HANDLERS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔥 *YouTube OAuth2 Downloader*\n\nFirst time link bhejne par logs check karein authentication ke liye!", parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" not in url and "youtu.be" not in url: return

    wait_msg = await update.message.reply_text("⚡ *Checking Authorization...*", parse_mode='Markdown')

    data = get_advanced_info(url)
    
    # Agar OAuth code chahiye toh wo logs me aayega
    if isinstance(data, str) and "To give yt-dlp access to your account" in data:
        await wait_msg.edit_text("🔑 *Action Required:*\nCheck Render Logs, copy the 8-digit code and authorize at [google.com/device](https://google.com/device)", parse_mode='Markdown')
        return

    if not data or isinstance(data, str):
        await wait_msg.edit_text(f"❌ *Error:* `{escape_md(str(data))}`", parse_mode='MarkdownV2')
        return

    # Formatting UI
    mins, secs = divmod(data['duration'], 60)
    duration_str = f"{mins}:{secs:02d}"

    caption = (
        f"🎬 *{escape_md(data['title'])}*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 *Channel:* `{escape_md(data['uploader'])}` \n"
        f"⏱️ *Duration:* `{duration_str}` \n"
        f"👁️ *Views:* `{data['views']:,}` \n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"📥 [Video Link]({data['video_url']})\n"
        f"🎵 [Audio Link]({data['audio_url']})"
    )

    await update.message.reply_photo(photo=data['thumbnail'], caption=caption, parse_mode='MarkdownV2')
    await wait_msg.delete()

if __name__ == '__main__':
    keep_alive()
    TOKEN = "8512110174:AAF7l7tegd4rpogl9E07Vz4qf-St2OMgX5c" # @BotFather se naya wala lein
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🚀 Bot started with OAuth2 support!")
    app.run_polling()
