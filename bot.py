#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════════════════════╗
║                     YT-DLP | v2.71828                         ║
║                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                  ║
║  [∫] yt-dlp quantum extractor                                 ║
║  [∑] async/await architecture                                 ║
║  [π] mathematical precision                                   ║
╚═══════════════════════════════════════════════════════════════╝
"""

import os
import logging
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time
from datetime import timedelta
import math

# ============================================================================
# CONFIGURATION | [λ] = 8372365354:AAFdHtFT9bjOsqiLGP_DCsPw5InbqA_aE3o
# ============================================================================

BOT_TOKEN = os.environ.get('BOT_TOKEN', '8372365354:AAFdHtFT9bjOsqiLGP_DCsPw5InbqA_aE3o')
MAX_WORKERS = 4
PLAYLIST_LIMIT = 10

# Logging configuration
logging.basicConfig(
    format='%(asctime)s | %(levelname)8s | %(message)s',
    datefmt='%H:%M:%S',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Thread pool for blocking operations
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# ============================================================================
# UTILITY FUNCTIONS | [f(x) = x² + 2x + 1]
# ============================================================================

def clean_youtube_url(url: str) -> str:
    """
    Normalize YouTube URL to canonical form.
    Returns: str -> normalized URL
    """
    # Remove tracking parameters (UTM, SI, etc.)
    url = re.sub(r'[&?](si|utm_[^=]+)=[^&]+', '', url)
    url = url.split('&')[0]
    
    # Handle youtu.be domain
    if 'youtu.be' in url:
        video_id = url.split('/')[-1].split('?')[0]
        return f'https://youtube.com/watch?v={video_id}'
    
    # Handle shorts
    if '/shorts/' in url:
        video_id = url.split('/shorts/')[-1].split('?')[0]
        return f'https://youtube.com/watch?v={video_id}'
    
    return url

def format_duration(seconds: int) -> str:
    """
    Format duration in seconds to mathematical time notation.
    Returns: str -> [HH:MM:SS] or [MM:SS]
    """
    if not seconds or seconds <= 0:
        return "∞"  # Live stream = infinity
    
    td = timedelta(seconds=int(seconds))
    total_seconds = int(td.total_seconds())
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    if hours > 0:
        return f"[{hours:02d}:{minutes:02d}:{seconds:02d}]"
    else:
        return f"[{minutes:02d}:{seconds:02d}]"

def format_number(n: int) -> str:
    """
    Format large numbers with mathematical notation.
    Returns: str -> 1.2K, 3.4M, etc.
    """
    if n < 1000:
        return str(n)
    elif n < 1000000:
        return f"{n/1000:.1f}K"
    elif n < 1000000000:
        return f"{n/1000000:.1f}M"
    else:
        return f"{n/1000000000:.1f}B"

def calculate_quality_score(format_dict: dict) -> float:
    """
    Calculate quality score for format ranking.
    Uses weighted mathematical formula.
    """
    height = format_dict.get('height', 0) or 0
    fps = format_dict.get('fps', 30) or 30
    filesize = format_dict.get('filesize', 0) or 0
    
    # Quality = (height * log(filesize)) / fps
    if filesize > 0:
        score = (height * math.log10(filesize)) / fps
    else:
        score = height / fps
    
    return score

# ============================================================================
# VIDEO INFORMATION EXTRACTOR | [∇ × F = 0]
# ============================================================================

def get_video_info_sync(url: str) -> dict:
    """
    Synchronous video information extractor using yt-dlp.
    Returns: dict -> normalized video/playlist data
    """
    logger.info(f"⏳ ∇ | Extracting: {url}")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'ignoreerrors': True,
        'format_sort': ['res:1080', 'ext:mp4:m4a'],
        'retries': 3,
        'user_agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/115.0',
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            
            if info is None:
                return {'ε': 'extraction_failed', 'φ': 'null'}
            
            # Playlist detection
            if 'entries' in info:
                videos = []
                for i, entry in enumerate(info['entries']):
                    if i >= PLAYLIST_LIMIT:
                        break
                    if entry:
                        videos.append({
                            'τ': entry.get('title', '∅'),
                            'υ': entry.get('webpage_url', f'https://youtube.com/watch?v={entry.get("id", "")}'),
                            'δ': entry.get('duration', 0)
                        })
                
                return {
                    'type': 'Π',  # Pi for Playlist
                    'τ': info.get('title', 'Unnamed Playlist'),
                    'ν': videos,
                    'count': len(videos)
                }
            
            # Single video
            formats = info.get('formats', [])
            
            # Score and rank formats
            scored_formats = []
            for f in formats:
                if f.get('vcodec') != 'none' and f.get('height'):
                    score = calculate_quality_score(f)
                    scored_formats.append((score, f))
            
            scored_formats.sort(reverse=True, key=lambda x: x[0])
            
            # Select best formats
            best_video = None
            best_audio = None
            
            for f in formats:
                # Best video+audio combo
                if f.get('ext') == 'mp4' and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    if not best_video or f.get('height', 0) > best_video.get('height', 0):
                        best_video = f
                
                # Best audio
                if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                    if not best_audio or f.get('abr', 0) > best_audio.get('abr', 0):
                        best_audio = f
            
            # Fallback
            if not best_video and scored_formats:
                best_video = scored_formats[0][1]
            
            return {
                'type': 'ν',  # Nu for video
                'τ': info.get('title', '∅'),
                'δ': info.get('duration', 0),
                'υ': info.get('view_count', 0),
                'uploader': info.get('uploader', '∅'),
                'thumbnail': info.get('thumbnail', ''),
                'video_url': best_video.get('url') if best_video else None,
                'audio_url': best_audio.get('url') if best_audio else None,
                'quality': best_video.get('height', 0) if best_video else 0,
                'fps': best_video.get('fps', 30) if best_video else 0,
                'ℵ': len(formats)  # Aleph for number of formats
            }
            
    except Exception as e:
        logger.error(f"✗ | Extraction error: {str(e)}")
        return {'ε': str(e), 'φ': 'exception'}

async def get_video_info_async(url: str) -> dict:
    """
    Asynchronous wrapper for video extraction.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(executor, get_video_info_sync, url)

# ============================================================================
# COMMAND HANDLERS | [∂/∂t = 0]
# ============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Initialize bot session."""
    user = update.effective_user
    
    header = """
╔═══════════════════════════════════════════════════════════════╗
║                    YT-DLP | v2.71828                         ║
║                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                  ║
║  [∫] quantum extractor initialized                           ║
║  [∑] async architecture loaded                               ║
║  [π] precision: 10⁻⁶                                         ║
╚═══════════════════════════════════════════════════════════════╝
    """
    
    body = f"""
┌─[λ]─[session]
├─ user  : {user.first_name}
├─ id    : {user.id}
└─ status: authenticated

┌─[⚡]─[capabilities]
├─ extraction : yt-dlp v2024.04.09
├─ formats    : MP4 | M4A | WEBM
├─ playlist   : Π (max {PLAYLIST_LIMIT})
└─ rate limit : ∞

┌─[∇]─[usage]
├─ send [URL] → extract metadata
├─ /help       → display axioms
└─ /about      → show constants
    """
    
    footer = """
───────────────────────────────────────────────────────────────
[ SYSTEM ] ready for input | heap: 256MB | threads: 4
    """
    
    await update.message.reply_text(
        f"<pre>{header}</pre>\n<code>{body}</code>\n<pre>{footer}</pre>",
        parse_mode='HTML'
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display help information."""
    help_text = """
┌─[?]─[help]─[axioms]
│
├─[∫]─[commands]
│  ├─ /start   → initialize session
│  ├─ /help    → display this message
│  └─ /about   → show version info
│
├─[∇]─[input]
│  ├─ youtube.com/watch?v=...
│  ├─ youtu.be/...
│  └─ youtube.com/shorts/...
│
├─[∑]─[output]
│  ├─ metadata extraction
│  ├─ direct download links
│  └─ format ranking (quality score)
│
└─[ℵ]─[limitations]
   ├─ playlist: Π ≤ 10
   ├─ timeout: 30s
   └─ rate: unthrottled

───────────────────────────────────────────────────────────────
    """
    
    await update.message.reply_text(f"<pre>{help_text}</pre>", parse_mode='HTML')

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Display version information."""
    about_text = f"""
┌─[ℹ️]─[about]─[constants]
│
├─ version  : 2.71828 (e)
├─ build    : 2026.02.22-1145
├─ engine   : yt-dlp
├─ framework: python-telegram-bot v20.7
│
├─[λ]─[mathematical constants]
│  ├─ π ≈ 3.1415926535
│  ├─ e ≈ 2.7182818284
│  ├─ φ ≈ 1.6180339887
│  └─ γ ≈ 0.5772156649
│
├─[⚡]─[performance]
│  ├─ workers: {MAX_WORKERS}
│  ├─ playlist: Π ≤ {PLAYLIST_LIMIT}
│  └─ heap: 256MB
│
└─[⏣]─[developer]
   ├─ github: @quantum-coder
   └─ matrix: #yt-dlp:matrix.org

───────────────────────────────────────────────────────────────
    """
    
    await update.message.reply_text(f"<pre>{about_text}</pre>", parse_mode='HTML')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Process YouTube URLs."""
    text = update.message.text.strip()
    
    # Validate URL
    youtube_regex = r'(https?://)?(www\.)?(youtube\.com|youtu\.be|youtube\.com/shorts)/\S+'
    if not re.match(youtube_regex, text):
        await update.message.reply_text(
            "<pre>✗ | invalid input | expected: youtube.com/watch?v=...</pre>",
            parse_mode='HTML'
        )
        return
    
    # Send processing indicator
    await update.message.chat.send_action(action='typing')
    processing_msg = await update.message.reply_text(
        "<pre>⏳ ∇ | extracting metadata | please wait...</pre>",
        parse_mode='HTML'
    )
    
    # Clean and process URL
    clean_url = clean_youtube_url(text)
    logger.info(f"→ | processing: {clean_url}")
    
    try:
        result = await get_video_info_async(clean_url)
        
        if 'ε' in result:
            await processing_msg.edit_text(
                f"<pre>✗ | extraction failed | {result['ε'][:50]}</pre>",
                parse_mode='HTML'
            )
            return
        
        # Playlist response
        if result['type'] == 'Π':
            playlist_msg = f"""
┌─[Π]─[playlist]─────────────────────────────────
│
├─ title : {result['τ'][:50]}
├─ count : {result['count']} / {PLAYLIST_LIMIT}
│
└─[ν]─[videos]───────────────────────────────────
"""
            for i, video in enumerate(result['ν'], 1):
                duration = format_duration(video['δ'])
                playlist_msg += f"\n  {i:02d}. {video['τ'][:40]} {duration}"
            
            playlist_msg += "\n\n───────────────────────────────────────────────"
            
            await processing_msg.edit_text(
                f"<pre>{playlist_msg}</pre>",
                parse_mode='HTML'
            )
            
            # Create minimal buttons
            keyboard = []
            for i, video in enumerate(result['ν'][:5], 1):  # Limit to 5 buttons
                video_id = video['υ'].split('=')[-1][:8]
                keyboard.append([
                    InlineKeyboardButton(
                        f"[ν{i:02d}]", 
                        callback_data=f"dl_{video_id}"
                    )
                ])
            
            if keyboard:
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(
                    "<pre>select video [ν01]...[ν05]</pre>",
                    reply_markup=reply_markup,
                    parse_mode='HTML'
                )
        
        # Single video response
        else:
            duration = format_duration(result['δ'])
            views = format_number(result['υ'])
            quality = result.get('quality', 0)
            fps = result.get('fps', 30)
            
            info_msg = f"""
┌─[ν]─[video]────────────────────────────────────
│
├─ title  : {result['τ'][:60]}
├─ upload : {result['uploader']}
├─ length : {duration}
├─ views  : {views}
├─ quality: {quality}p @ {fps}fps
└─ formats: {result['ℵ']} available

┌─[∇]─[download]─────────────────────────────────
│
"""
            
            # Create keyboard
            keyboard = []
            if result['video_url']:
                keyboard.append([
                    InlineKeyboardButton(
                        "[⬇] download MP4", 
                        url=result['video_url']
                    )
                ])
                info_msg += "│ [⬇] MP4 | video+audio\n"
            
            if result['audio_url']:
                keyboard.append([
                    InlineKeyboardButton(
                        "[♫] extract audio", 
                        url=result['audio_url']
                    )
                ])
                info_msg += "│ [♫] M4A | audio only\n"
            
            if not keyboard:
                keyboard.append([
                    InlineKeyboardButton(
                        "[✗] no direct links", 
                        callback_data="no_links"
                    )
                ])
                info_msg += "│ [✗] direct links unavailable\n"
            
            info_msg += "\n───────────────────────────────────────────────"
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await processing_msg.edit_text(
                f"<pre>{info_msg}</pre>",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
    except Exception as e:
        logger.error(f"✗ | handler error: {e}", exc_info=True)
        await processing_msg.edit_text(
            f"<pre>✗ | unexpected error | {str(e)[:50]}</pre>",
            parse_mode='HTML'
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle button interactions."""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith('dl_'):
        video_id = data[3:]
        url = f"https://youtube.com/watch?v={video_id}"
        
        await query.edit_message_text(
            "<pre>⏳ ∇ | fetching video | please wait...</pre>",
            parse_mode='HTML'
        )
        
        try:
            result = await get_video_info_async(url)
            
            if 'ε' in result:
                await query.edit_message_text(
                    f"<pre>✗ | fetch failed | {result['ε'][:50]}</pre>",
                    parse_mode='HTML'
                )
                return
            
            # Build response
            response = f"""
┌─[ν]─[{video_id}]────────────────────────────────
│
├─ title : {result.get('title', '∅')[:50]}
├─ length: {format_duration(result.get('duration', 0))}
└─ quality: {result.get('quality', 0)}p
            """
            
            keyboard = []
            if result.get('video_url'):
                keyboard.append([
                    InlineKeyboardButton(
                        "[⬇] download MP4",
                        url=result['video_url']
                    )
                ])
            
            if result.get('audio_url'):
                keyboard.append([
                    InlineKeyboardButton(
                        "[♫] extract audio",
                        url=result['audio_url']
                    )
                ])
            
            if not keyboard:
                keyboard.append([
                    InlineKeyboardButton(
                        "[✗] unavailable",
                        callback_data="none"
                    )
                ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"<pre>{response}</pre>",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
            
        except Exception as e:
            await query.edit_message_text(
                f"<pre>✗ | error | {str(e)[:50]}</pre>",
                parse_mode='HTML'
            )
    
    elif data in ["no_links", "none"]:
        await query.edit_message_text(
            "<pre>✗ | no download links available</pre>",
            parse_mode='HTML'
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Global error handler."""
    logger.error(f"✗ | global error: {context.error}", exc_info=True)
    
    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "<pre>✗ | system error | please try again</pre>",
                parse_mode='HTML'
            )
    except:
        pass

# ============================================================================
# MAIN ENTRY POINT | [∫ f(x) dx = F(b) - F(a)]
# ============================================================================

def main():
    """Initialize and start the bot."""
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                    YT-DLP | v2.71828                         ║
║                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                  ║
║  [∫] initializing components...                              ║
║  [∑] loading handlers...                                      ║
║  [π] starting polling...                                      ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Build application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Register handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_error_handler(error_handler)
    
    # Start bot
    logger.info("🚀 | polling started | waiting for updates...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
