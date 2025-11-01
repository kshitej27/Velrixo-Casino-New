import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# ===============================
#  SETUP LOGGING
# ===============================
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ===============================
#  BOT TOKEN (replace this after revoking old one)
# ===============================
BOT_TOKEN = "8437765248:AAFAm4IiUWC22nAs1Od_Cy3ue_bkpqPSWtE"

# ===============================
#  BASIC COMMANDS
# ===============================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome to the game bot! Use /help to see commands.")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🎮 Available Commands:\n"
        "/start - Begin your journey\n"
        "/balance - Check your coins\n"
        "/daily - Claim daily rewards\n"
        "/redeem <code> - Redeem special gift codes\n"
        "/duel @user <amount> - Challenge another player\n"
        "/referral - Get your invite link\n"
        "/games - See all playable games\n"
    )
    await update.message.reply_text(help_text)

async def balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Placeholder for balance system (to link with SQLite or JSON storage)
    await update.message.reply_text("💰 Your current balance is: 1000 coins")

async def daily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🎁 You claimed your daily 100 coins!")

async def redeem(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) == 0:
        await update.message.reply_text("⚠️ Usage: /redeem <code>")
    else:
        code = context.args[0]
        # Simulate checking code in database
        await update.message.reply_text(f"✅ Code '{code}' redeemed successfully! You got 500 coins.")

async def duel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚔️ Duel system coming soon... stay tuned!")

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    link = f"https://t.me/YourBotUsername?start={user_id}"
    await update.message.reply_text(f"🔗 Share this link to invite friends:\n{link}")

async def games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎲 Available games:\n"
        "1️⃣ /dicegame - Roll the dice\n"
        "2️⃣ /coinflip - Flip a coin\n"
        "3️⃣ /guess - Guess the number\n"
        "4️⃣ /slots - Spin to win"
    )

# ===============================
#  MAIN FUNCTION
# ===============================
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance))
    application.add_handler(CommandHandler("daily", daily))
    application.add_handler(CommandHandler("redeem", redeem))
    application.add_handler(CommandHandler("duel", duel))
    application.add_handler(CommandHandler("referral", referral))
    application.add_handler(CommandHandler("games", games))

    # Run bot correctly (avoids event loop issues)
    logger.info("🚀 Bot is running...")
    application.run_polling()

if __name__ == "__main__":
    main()
