#!/usr/bin/env python3
"""
Telegram Number Lookup Bot (Fixed & Working)
"""

import os
import logging
import re
from typing import Dict, Any
from datetime import datetime

import aiohttp
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)
from telegram.constants import ParseMode

# ------------------ LOAD ENV ------------------

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = os.getenv("API_URL", "https://root-coders-apix.deno.dev/")
API_KEY = os.getenv("API_KEY")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN missing in .env")
if not API_KEY:
    raise ValueError("API_KEY missing in .env")

# ------------------ CONFIG ------------------

PHONE_REGEX = r'^[6-9]\d{9}$'
MAX_HISTORY = 20
user_search_history = {}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

bot_username = None


# ------------------ BOT CLASS ------------------

class NumberLookupBot:

    # ---------- START ----------
    @staticmethod
    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "👋 Hello!\n\n"
            "Send:\n"
            "`/num 9876543210`\n\n"
            "Or just type 10-digit number directly.",
            parse_mode=ParseMode.MARKDOWN
        )

    # ---------- HELP ----------
    @staticmethod
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📱 Use:\n"
            "`/num 9876543210`\n\n"
            "📜 /history - View recent searches",
            parse_mode=ParseMode.MARKDOWN
        )

    # ---------- NUM COMMAND (FIXED) ----------
    @staticmethod
    async def num_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

        if not context.args:
            await update.message.reply_text(
                "❌ Please provide a number.\nExample:\n`/num 9876543210`",
                parse_mode=ParseMode.MARKDOWN
            )
            return

        number = context.args[0]
        await NumberLookupBot.lookup_number(update, context, number)

    # ---------- LOOKUP ----------
    @staticmethod
    async def lookup_number(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        number: str,
        from_callback: bool = False
    ):

        if not re.match(PHONE_REGEX, number):
            await update.effective_message.reply_text(
                "❌ Invalid Indian mobile number.",
            )
            return

        user_id = update.effective_user.id

        # Save history
        if user_id not in user_search_history:
            user_search_history[user_id] = []

        user_search_history[user_id].append((number, datetime.now()))

        if len(user_search_history[user_id]) > MAX_HISTORY:
            user_search_history[user_id] = user_search_history[user_id][-MAX_HISTORY:]

        await update.effective_message.reply_chat_action("typing")

        try:
            result = await NumberLookupBot.call_api(number)

            if not result.get("success"):
                await update.effective_message.reply_text(
                    f"❌ API Error: {result.get('message', 'Unknown error')}"
                )
                return

            data = result.get("data", [])

            if not data:
                await update.effective_message.reply_text(
                    f"ℹ️ No records found for `{number}`",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            formatted = await NumberLookupBot.format_response(data, number)

            await update.effective_message.reply_text(
                formatted,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )

        except Exception as e:
            logger.error(str(e))
            await update.effective_message.reply_text("❌ Something went wrong.")

    # ---------- API CALL ----------
    @staticmethod
    async def call_api(number: str) -> Dict[str, Any]:

        url = f"{API_URL}?num={number}&key={API_KEY}"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=10) as response:
                if response.status != 200:
                    return {"success": False, "message": "API error"}

                return await response.json()

    # ---------- FORMAT ----------
    @staticmethod
    async def format_response(data: list, searched_number: str) -> str:

        lines = []
        lines.append(f"🔍 Results for: `{searched_number}`")
        lines.append(f"📊 Records: {len(data)}\n")

        for i, record in enumerate(data, 1):

            lines.append("════════════════════")
            lines.append(f"👤 Record {i}")
            lines.append(f"Name: {record.get('name', 'N/A')}")
            lines.append(f"Father: {record.get('father_name', 'N/A')}")
            lines.append(f"Mobile: `{record.get('mobile', 'N/A')}`")
            lines.append(f"Circle: {record.get('circle', 'N/A')}")
            lines.append(f"ID: `{record.get('id_number', 'N/A')}`")

            if record.get("address"):
                lines.append(f"Address: {record.get('address')}")

            if record.get("email"):
                lines.append(f"Email: {record.get('email')}")

            lines.append("")

        lines.append("📜 /history to see recent searches")

        return "\n".join(lines)

    # ---------- HISTORY ----------
    @staticmethod
    async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):

        user_id = update.effective_user.id
        history = user_search_history.get(user_id, [])

        if not history:
            await update.message.reply_text("📭 No history found.")
            return

        keyboard = []
        for num, time in history[-10:]:
            keyboard.append([
                InlineKeyboardButton(
                    f"{num}",
                    callback_data=f"num_{num}"
                )
            ])

        await update.message.reply_text(
            "📋 Click to search again:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    # ---------- BUTTON ----------
    @staticmethod
    async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

        query = update.callback_query
        await query.answer()

        if query.data.startswith("num_"):
            number = query.data.replace("num_", "")
            await NumberLookupBot.lookup_number(update, context, number)

    # ---------- AUTO NUMBER DETECT ----------
    @staticmethod
    async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

        text = update.message.text.strip()

        if re.match(PHONE_REGEX, text):
            await NumberLookupBot.lookup_number(update, context, text)
        else:
            await update.message.reply_text(
                "Send 10-digit number or use /num command."
            )


# ------------------ INIT ------------------

async def post_init(application: Application):
    global bot_username
    bot = application.bot
    me = await bot.get_me()
    bot_username = me.username
    logger.info(f"Bot started as @{bot_username}")


def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", NumberLookupBot.start))
    app.add_handler(CommandHandler("help", NumberLookupBot.help_command))
    app.add_handler(CommandHandler("num", NumberLookupBot.num_command))
    app.add_handler(CommandHandler("history", NumberLookupBot.history))

    app.add_handler(CallbackQueryHandler(NumberLookupBot.button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, NumberLookupBot.handle_message))

    logger.info("Bot running...")
    app.run_polling()


if __name__ == "__main__":
    main()
