import logging
import re
import yt_dlp
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

# 1. Logging Setup
logging.basicConfig(level=logging.INFO)

# Helper to escape MarkdownV2 special characters
def escape_md(text):
    if not text: return ""
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))

# 2. Enhanced Extraction Logic
def get_advanced_info(url):
    ydl_opts = {
        'quiet': True,
        'skip_download': True,
        'noplaylist': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        if not info:
            return None

        # Extracting best formats
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

# 3. Bot Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✨ *YouTube Advance Downloader* ✨\n\nSend a link to get full metadata!", parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    if "youtube.com" not in url and "youtu.be" not in url:
        return

    wait_msg = await update.message.reply_text("🔍 *Scanning YouTube Servers...*", parse_mode='Markdown')

    try:
        data = get_advanced_info(url)
        if not data:
            await wait_msg.edit_text("❌ Error: Could not fetch data.")
            return

        # Formatting duration to MM:SS
        mins, secs = divmod(data['duration'], 60)
        duration_str = f"{mins}:{secs:02d}"

        # Building the stylish response
        caption = (
            f"🎬 *{escape_md(data['title'])}*\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 *Channel:* `{escape_md(data['uploader'])}` \n"
            f"⏱️ *Duration:* `{duration_str}` \n"
            f"👁️ *Views:* `{data['views']:,}` \n"
            f"👍 *Likes:* `{data['likes']}` \n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"📥 [Download Video \(MP4\)]({data['video_url']})\n"
            f"🎵 [Download Audio \(MP3\)]({data['audio_url']})\n"
            f"🖼️ [Download Thumbnail]({data['thumbnail']})"
        )

        # Send as a Photo with caption
        await update.message.reply_photo(
            photo=data['thumbnail'],
            caption=caption,
            parse_mode='MarkdownV2'
        )
        await wait_msg.delete()

    except Exception as e:
        logging.error(e)
        await wait_msg.edit_text(f"❌ *Script Error:* `{escape_md(str(e))}`", parse_mode='MarkdownV2')

# 4. Execution
if __name__ == '__main__':
    TOKEN = '8245872361:AAFFOP814_N1VI6brkwbR58LCnRIq13RBhQ' # 🔥 Put your token here
    
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))

    print("🚀 Advanced Bot is Live!")
    app.run_polling()
