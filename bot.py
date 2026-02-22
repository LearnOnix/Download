#!/usr/bin/env python3
"""
Telegram Number Lookup Bot
Uses external API to fetch details by phone number
"""

import os
import logging
import re
from typing import Optional, Dict, Any
from datetime import datetime

import requests
import aiohttp
import asyncio
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
API_URL = os.getenv('API_URL', 'https://root-coders-apix.deno.dev/')
API_KEY = os.getenv('API_KEY')
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# Validate required config
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in .env file")
if not API_KEY:
    raise ValueError("API_KEY not found in .env file")

# Setup logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Constants
PHONE_REGEX = r'^[6-9]\d{9}$'  # Indian mobile numbers start with 6-9 and are 10 digits
MAX_HISTORY = 20  # Number of searches to remember per user

# In-memory storage (use database for production)
user_search_history = {}

class NumberLookupBot:
    """Main bot class with all handlers"""
    
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        user = update.effective_user
        welcome_msg = (
            f"👋 Hello {user.first_name}!\n\n"
            "I can lookup details for Indian mobile numbers.\n\n"
            "📱 **Commands:**\n"
            "/num `<10-digit number>` - Lookup a phone number\n"
            "/history - View your search history\n"
            "/help - Show this help message\n\n"
            "**Example:** `/num 9876543210`\n\n"
            "⚠️ Results may include linked family members and alternate numbers."
        )
        await update.message.reply_text(welcome_msg, parse_mode='Markdown')
        
        # Log to admins if configured
        if ADMIN_IDS:
            for admin_id in ADMIN_IDS:
                try:
                    await context.bot.send_message(
                        admin_id,
                        f"🆕 New user: {user.first_name} (@{user.username}) [ID: {user.id}]"
                    )
                except:
                    pass
    
    @staticmethod
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command"""
        help_text = (
            "🔍 **Number Lookup Bot Help**\n\n"
            "**Usage:**\n"
            "• Send `/num 9876543210` with any 10-digit Indian mobile number\n"
            "• Results show personal details and linked family members\n\n"
            "**Features:**\n"
            "✓ Search history (last 20 searches)\n"
            "✓ Auto-detects Indian numbers\n"
            "✓ Shows alternate numbers as clickable links\n"
            "✓ Family member connections\n\n"
            "**Privacy:** We don't store your searches permanently.\n\n"
            "Report issues to @YourUsername"
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')
    
    @staticmethod
    async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Show user's search history"""
        user_id = update.effective_user.id
        history = user_search_history.get(user_id, [])
        
        if not history:
            await update.message.reply_text("📭 You haven't searched any numbers yet.")
            return
        
        # Create inline keyboard with history items
        keyboard = []
        for num, timestamp in history[-10:]:  # Show last 10
            time_str = timestamp.strftime("%H:%M")
            keyboard.append([InlineKeyboardButton(
                f"{num} (at {time_str})",
                callback_data=f"num_{num}"
            )])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "📋 **Your Recent Searches:**\nClick to search again:",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
    
    @staticmethod
    async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button clicks"""
        query = update.callback_query
        await query.answer()
        
        if query.data.startswith('num_'):
            number = query.data.replace('num_', '')
            # Trigger the number lookup
            await NumberLookupBot.lookup_number(
                update, context, number, from_callback=True
            )
    
    @staticmethod
    async def lookup_number(
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE, 
        number: str,
        from_callback: bool = False
    ):
        """Perform the actual number lookup"""
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name
        
        # Send typing indicator
        if from_callback:
            await update.callback_query.message.reply_chat_action('typing')
        else:
            await update.message.reply_chat_action('typing')
        
        # Validate number format
        if not re.match(PHONE_REGEX, number):
            error_msg = (
                f"❌ Invalid number: `{number}`\n\n"
                "Please provide a valid 10-digit Indian mobile number.\n"
                "Example: `/num 9876543210`"
            )
            if from_callback:
                await update.callback_query.message.reply_text(
                    error_msg, parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(error_msg, parse_mode='Markdown')
            return
        
        # Log the search
        logger.info(f"User {user_id} ({user_name}) searched for {number}")
        
        # Add to history
        if user_id not in user_search_history:
            user_search_history[user_id] = []
        user_search_history[user_id].append((number, datetime.now()))
        # Keep only last MAX_HISTORY
        if len(user_search_history[user_id]) > MAX_HISTORY:
            user_search_history[user_id] = user_search_history[user_id][-MAX_HISTORY:]
        
        # Call the API
        try:
            result = await NumberLookupBot.call_api(number)
            
            if not result.get('success'):
                error_msg = f"❌ API Error: {result.get('message', 'Unknown error')}"
                if from_callback:
                    await update.callback_query.message.reply_text(error_msg)
                else:
                    await update.message.reply_text(error_msg)
                return
            
            data = result.get('data', [])
            if not data:
                no_data_msg = f"ℹ️ No records found for number `{number}`"
                if from_callback:
                    await update.callback_query.message.reply_text(
                        no_data_msg, parse_mode='Markdown'
                    )
                else:
                    await update.message.reply_text(no_data_msg, parse_mode='Markdown')
                return
            
            # Format the response
            response = await NumberLookupBot.format_response(data, number)
            
            # Send the result
            if from_callback:
                await update.callback_query.message.reply_text(
                    response, parse_mode='Markdown', disable_web_page_preview=True
                )
            else:
                await update.message.reply_text(
                    response, parse_mode='Markdown', disable_web_page_preview=True
                )
                
        except Exception as e:
            logger.error(f"Error looking up {number}: {str(e)}")
            error_msg = f"❌ An error occurred: {str(e)[:100]}"
            if from_callback:
                await update.callback_query.message.reply_text(error_msg)
            else:
                await update.message.reply_text(error_msg)
    
    @staticmethod
    async def call_api(number: str) -> Dict[str, Any]:
        """Call the external API to get number details"""
        # Build URL with parameters
        url = f"{API_URL}?num={number}&key={API_KEY}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    return {
                        'success': False,
                        'message': f"API returned status {response.status}"
                    }
                return await response.json()
    
    @staticmethod
    async def format_response(data: list, searched_number: str) -> str:
        """Format the API response into a readable message"""
        lines = []
        lines.append(f"🔍 **Results for:** `{searched_number}`")
        lines.append(f"📊 **Records found:** {len(data)}\n")
        
        for idx, record in enumerate(data, 1):
            lines.append(f"**{'═'*30}**")
            lines.append(f"**👤 Record #{idx}**")
            lines.append(f"**Name:** {record.get('name', 'N/A')}")
            lines.append(f"**Father:** {record.get('father_name', 'N/A')}")
            lines.append(f"**Mobile:** `{record.get('mobile', 'N/A')}`")
            
            alt_mobile = record.get('alt_mobile')
            if alt_mobile and alt_mobile != searched_number:
                # Make alternate number clickable for quick lookup
                lines.append(f"**Alternate:** [{alt_mobile}](https://t.me/{(await get_bot_username())}?start=lookup_{alt_mobile})")
            elif alt_mobile:
                lines.append(f"**Alternate:** `{alt_mobile}`")
            
            lines.append(f"**Circle:** {record.get('circle', 'N/A')}")
            lines.append(f"**ID:** `{record.get('id_number', 'N/A')}`")
            
            address = record.get('address', 'N/A')
            if address and address != 'N/A':
                # Truncate long addresses
                if len(address) > 100:
                    address = address[:97] + "..."
                lines.append(f"**Address:** {address}")
            
            email = record.get('email')
            if email:
                lines.append(f"**Email:** {email}")
            
            lines.append("")  # Blank line between records
        
        # Add footer with instructions
        lines.append("**─" * 20 + "**")
        lines.append("🔄 Click on alternate numbers to search them")
        lines.append("📝 Use /history to see your recent searches")
        
        return "\n".join(lines)
    
    @staticmethod
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle regular messages (try to interpret as phone number)"""
        text = update.message.text.strip()
        
        # Check if message looks like a phone number
        if re.match(PHONE_REGEX, text):
            await NumberLookupBot.lookup_number(update, context, text)
        else:
            # Not a number, show help
            await update.message.reply_text(
                "Please send a 10-digit mobile number or use /num command.\n"
                "Example: `/num 9876543210`",
                parse_mode='Markdown'
            )
    
    @staticmethod
    async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle errors"""
        logger.error(f"Update {update} caused error {context.error}")
        
        # Notify user
        error_msg = "❌ An unexpected error occurred. Please try again later."
        if update and update.effective_message:
            await update.effective_message.reply_text(error_msg)

# Global variable to store bot username (set during startup)
bot_username = None

async def get_bot_username():
    """Get the bot's username for generating Telegram links"""
    global bot_username
    if not bot_username:
        # This will be set during initialization
        return "your_bot_username"
    return bot_username

async def post_init(application: Application):
    """Set bot username after initialization"""
    global bot_username
    bot = application.bot
    bot_user = await bot.get_me()
    bot_username = bot_user.username
    logger.info(f"Bot started: @{bot_username}")

def main():
    """Main function to run the bot"""
    # Create application
    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )
    
    # Add handlers
    application.add_handler(CommandHandler("start", NumberLookupBot.start))
    application.add_handler(CommandHandler("help", NumberLookupBot.help_command))
    application.add_handler(CommandHandler("history", NumberLookupBot.history))
    application.add_handler(CommandHandler("num", NumberLookupBot.lookup_number))
    
    # Handle button callbacks
    application.add_handler(CallbackQueryHandler(NumberLookupBot.button_callback))
    
    # Handle regular messages (for direct number input)
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, NumberLookupBot.handle_message))
    
    # Add error handler
    application.add_error_handler(NumberLookupBot.error_handler)
    
    # Start the bot
    logger.info("Starting bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
