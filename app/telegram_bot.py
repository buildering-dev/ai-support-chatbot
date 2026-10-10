"""Telegram channel for the same support bot.

Create a bot with @BotFather, put the token in TELEGRAM_BOT_TOKEN, then:
    python -m app.telegram_bot
"""
from __future__ import annotations

import logging
import re

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from .bot import SupportBot
from .config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("telegram_bot")

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
bot = SupportBot(settings)
# chats where the bot is waiting for the customer's contact details after a handoff
_waiting_for_contact: dict[int, str] = {}


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        f"Hi! I'm the {settings.business_name} assistant. Ask me about products, orders, shipping or returns.\n"
        "Type /reset to start over."
    )


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    bot.reset(f"tg-{chat_id}")
    _waiting_for_contact.pop(chat_id, None)
    await update.message.reply_text("Conversation cleared.")


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    text = (update.message.text or "").strip()
    session = f"tg-{chat_id}"

    if chat_id in _waiting_for_contact:
        email = EMAIL_RE.search(text)
        if email:
            name = text.replace(email.group(0), "").strip(" ,-") or (update.effective_user.full_name or "")
            bot.save_lead("telegram", session, name, email.group(0), _waiting_for_contact.pop(chat_id))
            await update.message.reply_text("Thanks! The team will email you shortly.")
            return
        _waiting_for_contact.pop(chat_id)  # they moved on; treat as a new question

    await context.bot.send_chat_action(chat_id, "typing")
    reply = bot.answer(text, session=session, channel="telegram")
    msg = reply.answer
    if reply.handoff:
        _waiting_for_contact[chat_id] = text
        msg += "\n\nJust reply with your name and email."
    elif reply.sources:
        msg += "\n\nSource: " + "; ".join(reply.sources)
    await update.message.reply_text(msg)


def main() -> None:
    if not settings.telegram_token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN (from @BotFather) first.")
    application = Application.builder().token(settings.telegram_token).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("reset", reset))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))
    log.info("Telegram bot running (provider=%s)", bot.llm.name)
    application.run_polling()


if __name__ == "__main__":
    main()
