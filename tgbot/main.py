"""Telegram bot entry point. Wires Telegram → TelegramMCPAgent → OpenAI + MCP."""
import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agent import TelegramMCPAgent

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! I'm an AI assistant connected to MCP tools. "
        "Ask me anything, or use /tools to see what I can do."
    )


async def tools_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent: TelegramMCPAgent = context.bot_data["agent"]
    tools = await agent.list_tools()
    if not tools:
        await update.message.reply_text("No MCP tools available.")
    else:
        text = "Available MCP tools:\n" + "\n".join(f"- {t}" for t in tools)
        await update.message.reply_text(text)


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    agent: TelegramMCPAgent = context.bot_data["agent"]
    user_message = update.message.text
    chat_id = update.effective_chat.id

    await context.bot.send_chat_action(chat_id=chat_id, action="typing")
    try:
        response = await agent.chat(user_message, conversation_id=str(chat_id))
    except Exception as e:
        logger.exception("Agent failed")
        response = f"Sorry, I hit an error: {e}"

    await update.message.reply_text(response)


async def post_init(app: Application):
    """Startup hook: spawn the MCP server, init the agent, store on bot_data."""
    agent = TelegramMCPAgent()
    await agent.connect()
    app.bot_data["agent"] = agent


async def post_shutdown(app: Application):
    agent: TelegramMCPAgent = app.bot_data.get("agent")
    if agent:
        await agent.disconnect()


def main():
    load_dotenv()
    token = os.environ["TELEGRAM_BOT_TOKEN"]

    app = (
        Application.builder()
        .token(token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("tools", tools_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
