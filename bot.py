#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
╔═══════════════════════════════════════════════════════════════╗
║              YT-DLP | RENDER-PROD v2.71830                   ║
║                ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━                  ║
║  [∫] single-process architecture                             ║
║  [∑] webhook with secret token                               ║
║  [π] production locked                                       ║
╚═══════════════════════════════════════════════════════════════╝
"""

import os
import sys
import logging
import yt_dlp
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from telegram.ext import PicklePersistence
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import math
from flask import Flask, request
import threading
import signal
import time

# ============================================================================
# RENDER CONFIGURATION - MUST BE FIRST
# ============================================================================

# Get token from environment - NO DEFAULTS!
BOT_TOKEN = os.environ.get('BOT_TOKEN')
if not BOT_TOKEN:
    print("❌ FATAL: BOT_TOKEN environment variable not set!")
    print("➡️  Go to Render Dashboard > Environment Variables")
    print("➡️  Add BOT_TOKEN = your_actual_bot_token_from_BotFather")
    sys.exit(1)

# Render settings
PORT = int(os.environ.get('PORT', 10000))  # Render default is 10000
RENDER_EXTERNAL_URL = os.environ.get('RENDER_EXTERNAL_URL')
if not RENDER_EXTERNAL_URL:
    print("⚠️  Warning: RENDER_EXTERNAL_URL not set, using localhost")
    RENDER_EXTERNAL_URL = f"https://localhost:{PORT}"

# Generate a webhook secret automatically
import secrets
WEBHOOK_SECRET = secrets.token_urlsafe(32)
WEBHOOK_PATH = f"/webhook/{WEBHOOK_SECRET}"

# Performance settings
MAX_WORKERS = int(os.environ.get('MAX_WORKERS', 2))  # Lower for Render's free tier
PLAYLIST_LIMIT = int(os.environ.get('PLAYLIST_LIMIT', 5))  # Lower to save memory

# ============================================================================
# LOGGING - Write to stdout for Render logs
# ============================================================================

logging.basicConfig(
    format='%(asctime)s | %(levelname)8s | %(message)s',
    datefmt='%H:%M:%S',
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)]  # Only stdout for Render
)
logger = logging.getLogger(__name__)

# Thread pool with proper cleanup
executor = ThreadPoolExecutor(max_workers=MAX_WORKERS)

# ============================================================================
# YOUR EXISTING UTILITY FUNCTIONS (KEEP THEM ALL)
# ============================================================================

def clean_youtube_url(url: str) -> str:
    """Normalize YouTube URL to canonical form."""
    url = re.sub(r'[&?](si|utm_[^=]+)=[^&]+', '', url)
    url = url.split('&')[0]
    
    if 'youtu.be' in url:
        video_id = url.split('/')[-1].split('?')[0]
        return f'https://youtube.com/watch?v={video_id}'
    
    if '/shorts/' in url:
        video_id = url.split('/shorts/')[-1].split('?')[0]
        return f'https://youtube.com/watch?v={video_id}'
    
    return url

def format_duration(seconds: int) -> str:
    """Format duration in seconds to mathematical time notation."""
    if not seconds or seconds <= 0:
        return "∞"
    
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
    """Format large numbers with mathematical notation."""
    if n < 1000:
        return str(n)
    elif n < 1000000:
        return f"{n/1000:.1f}K"
    elif n < 1000000000:
        return f"{n/1000000:.1f}M"
    else:
        return f"{n/1000000000:.1f}B"

def calculate_quality_score(format_dict: dict) -> float:
    """Calculate quality score for format ranking."""
    height = format_dict.get('height', 0) or 0
    fps = format_dict.get('fps', 30) or 30
    filesize = format_dict.get('filesize', 0) or 0
    
    if filesize > 0:
        score = (height * math.log10(filesize)) / fps
    else:
        score = height / fps
    
    return score

# ============================================================================
# VIDEO EXTRACTION - WITH TIMEOUTS
# ============================================================================

def get_video_info_sync(url: str) -> dict:
    """Synchronous video information extractor with timeout."""
    logger.info(f"⏳ ∇ | Extracting: {url}")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'ignoreerrors': True,
        'format_sort': ['res:720', 'ext:mp4:m4a'],  # Lower default for speed
        'retries': 2,
        'timeout': 20,  # Shorter timeout for Render
        'socket_timeout': 20,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
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
                    'type': 'Π',
                    'τ': info.get('title', 'Unnamed Playlist'),
                    'ν': videos,
                    'count': len(videos)
                }
            
            # Single video
            formats = info.get('formats', [])
            
            scored_formats = []
            for f in formats:
                if f.get('vcodec') != 'none' and f.get('height'):
                    score = calculate_quality_score(f)
                    scored_formats.append((score, f))
            
            scored_formats.sort(reverse=True, key=lambda x: x[0])
            
            best_video = None
            best_audio = None
            
            for f in formats:
                if f.get('ext') == 'mp4' and f.get('vcodec') != 'none' and f.get('acodec') != 'none':
                    if not best_video or f.get('height', 0) > best_video.get('height', 0):
                        best_video = f
                
                if f.get('vcodec') == 'none' and f.get('acodec') != 'none':
                    if not best_audio or f.get('abr', 0) > best_audio.get('abr', 0):
                        best_audio = f
            
            if not best_video and scored_formats:
                best_video = scored_formats[0][1]
            
            return {
                'type': 'ν',
                'τ': info.get('title', '∅'),
                'δ': info.get('duration', 0),
                'υ': info.get('view_count', 0),
                'uploader': info.get('uploader', '∅'),
                'thumbnail': info.get('thumbnail', ''),
                'video_url': best_video.get('url') if best_video else None,
                'audio_url': best_audio.get('url') if best_audio else None,
                'quality': best_video.get('height', 0) if best_video else 0,
                'fps': best_video.get('fps', 30) if best_video else 0,
                'ℵ': len(formats)
            }
            
    except Exception as e:
        logger.error(f"✗ | Extraction error: {str(e)}")
        return {'ε': str(e), 'φ': 'exception'}

async def get_video_info_async(url: str) -> dict:
    """Asynchronous wrapper with proper executor handling."""
    loop = asyncio.get_event_loop()
    try:
        return await loop.run_in_executor(executor, get_video_info_sync, url)
    except Exception as e:
        logger.error(f"Async extraction error: {e}")
        return {'ε': str(e), 'φ': 'async_error'}

# ============================================================================
# TELEGRAM HANDLERS (Your existing handlers - kept exactly as you had them)
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
├─ extraction : yt-dlp
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
    
    youtube_regex = r'(https?://)?(www\.)?(youtube\.com|youtu\.be|youtube\.com/shorts)/\S+'
    if not re.match(youtube_regex, text):
        await update.message.reply_text(
            "<pre>✗ | invalid input | expected: youtube.com/watch?v=...</pre>",
            parse_mode='HTML'
        )
        return
    
    await update.message.chat.send_action(action='typing')
    processing_msg = await update.message.reply_text(
        "<pre>⏳ ∇ | extracting metadata | please wait...</pre>",
        parse_mode='HTML'
    )
    
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
            
            keyboard = []
            for i, video in enumerate(result['ν'][:5], 1):
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

# ============================================================================
# SIMPLIFIED RENDER WEBHOOK SETUP
# ============================================================================

# Create Flask app for health checks and webhook
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 YT-DLP Bot is running on Render!"

@flask_app.route('/health')
def health():
    return "OK", 200

@flask_app.route(WEBHOOK_PATH, methods=['POST'])
def webhook():
    """Handle Telegram webhook requests"""
    if not application:
        return "Application not ready", 503
    
    # Convert Flask request to dict and process
    update_data = request.get_json(force=True)
    
    # Create a task in the bot's event loop
    asyncio.run_coroutine_threadsafe(
        application.process_update(
            Update.de_json(update_data, application.bot)
        ),
        application.loop
    )
    return "OK", 200

def run_flask():
    """Run Flask in a separate thread"""
    flask_app.run(host='0.0.0.0', port=PORT)

# Global application reference
application = None

async def setup_webhook(app):
    """Setup webhook for Telegram"""
    webhook_url = f"{RENDER_EXTERNAL_URL}{WEBHOOK_PATH}"
    logger.info(f"🔗 Setting webhook: {webhook_url}")
