# main.py
"""
Velrixo Casino Bot - Full release (10+ games, SQLite, redeem codes, referrals, PvP, admin system)
Owner username: @Velrixo
Token embedded as requested (KEEP THIS FILE PRIVATE)
"""

import os
import random
import sqlite3
import logging
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# ---------- CONFIG ----------
# Prefer environment variable if set (safer). If not set, fallback to embedded token.
BOT_TOKEN = os.getenv("BOT_TOKEN") or "8437765248:AAFAm4IiUWC22nAs1Od_Cy3ue_bkpqPSWtE"
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "Velrixo").lstrip("@")   # without @
DB_FILE = "velrixo_casino.db"
CURRENCY = "$VCB"
REF_BONUS_DEFAULT = 500

# ---------- LOGGING ----------
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("velrixo_casino")

# ---------- DB ----------
_conn = sqlite3.connect(DB_FILE, check_same_thread=False)
_cur = _conn.cursor()

def init_db():
    _cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
      user_id INTEGER PRIMARY KEY,
      username TEXT,
      balance INTEGER DEFAULT 1000,
      xp INTEGER DEFAULT 0,
      level INTEGER DEFAULT 1,
      last_daily TEXT DEFAULT '',
      streak INTEGER DEFAULT 0,
      ref_code TEXT,
      referred_by TEXT
    )""")
    _cur.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
    _cur.execute("""
    CREATE TABLE IF NOT EXISTS redeem_codes (
      code TEXT PRIMARY KEY,
      amount INTEGER,
      uses_allowed INTEGER DEFAULT 1,
      uses_count INTEGER DEFAULT 0,
      creator_id INTEGER,
      created_at TEXT
    )""")
    _cur.execute("""
    CREATE TABLE IF NOT EXISTS used_codes (
      code TEXT,
      user_id INTEGER,
      used_at TEXT,
      PRIMARY KEY(code,user_id)
    )""")
    _cur.execute("""
    CREATE TABLE IF NOT EXISTS packets (
      user_id INTEGER PRIMARY KEY,
      amount INTEGER DEFAULT 0,
      last_redeem TEXT DEFAULT ''
    )""")
    _conn.commit()
    log.info("Database initialized.")

# ---------- UTIL ----------
def ensure_user(user_id, username=None):
    _cur.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
    if not _cur.fetchone():
        code = f"VCB{random.randint(10000,99999)}"
        _cur.execute("INSERT INTO users(user_id, username, balance, xp, level, last_daily, streak, ref_code) VALUES (?,?,?,?,?,?,?,?)",
                     (user_id, username or "", 1000, 0, 1, "", 0, code))
        _conn.commit()
        _cur.execute("INSERT OR IGNORE INTO redeem_codes(code,amount,uses_allowed,uses_count,creator_id,created_at) VALUES (?,?,?,?,?,?)",
                     (code, REF_BONUS_DEFAULT, 0, 0, user_id, datetime.utcnow().isoformat()))
        _conn.commit()
        return code
    else:
        if username:
            _cur.execute("UPDATE users SET username=? WHERE user_id=?", (username, user_id))
            _conn.commit()
    return None

def get_user_row(user_id):
    _cur.execute("SELECT user_id, username, balance, xp, level, last_daily, streak, ref_code, referred_by FROM users WHERE user_id=?", (user_id,))
    return _cur.fetchone()

def get_balance(user_id):
    row = get_user_row(user_id)
    if row:
        return row[2]
    ensure_user(user_id)
    return 1000

def set_balance(user_id, amount):
    ensure_user(user_id)
    _cur.execute("UPDATE users SET balance=? WHERE user_id=?", (int(amount), user_id))
    _conn.commit()

def change_balance(user_id, delta):
    ensure_user(user_id)
    bal = get_balance(user_id)
    new = bal + int(delta)
    if new < 0:
        new = 0
    _cur.execute("UPDATE users SET balance=? WHERE user_id=?", (new, user_id))
    _conn.commit()
    return new

def add_xp(user_id, xp):
    ensure_user(user_id)
    _cur.execute("UPDATE users SET xp = xp + ? WHERE user_id=?", (xp, user_id))
    _conn.commit()
    _cur.execute("SELECT xp, level FROM users WHERE user_id=?", (user_id,))
    row = _cur.fetchone()
    if row:
        xp_now, level = row
        while xp_now >= level * 100:
            level += 1
            _cur.execute("UPDATE users SET level=? WHERE user_id=?", (level, user_id))
            _conn.commit()

def can_claim_daily(user_id):
    row = get_user_row(user_id)
    if not row or not row[5]:
        return True
    try:
        last = datetime.fromisoformat(row[5])
    except Exception:
        return True
    return datetime.utcnow() - last >= timedelta(hours=24)

def set_daily_time(user_id):
    row = get_user_row(user_id)
    last = row[5] if row else ""
    new_streak = 1
    if last:
        try:
            last_dt = datetime.fromisoformat(last)
            if datetime.utcnow() - last_dt <= timedelta(hours=48):
                new_streak = (row[6] or 0) + 1
        except:
            new_streak = 1
    _cur.execute("UPDATE users SET last_daily=?, streak=? WHERE user_id=?", (datetime.utcnow().isoformat(), new_streak, user_id))
    _conn.commit()

def is_admin(user_id):
    _cur.execute("SELECT 1 FROM admins WHERE user_id=?", (user_id,))
    return bool(_cur.fetchone())

def add_admin(user_id):
    _cur.execute("INSERT OR IGNORE INTO admins(user_id) VALUES (?)", (user_id,))
    _conn.commit()

def remove_admin(user_id):
    _cur.execute("DELETE FROM admins WHERE user_id=?", (user_id,))
    _conn.commit()

def make_code(code, amount, uses_allowed, creator_id):
    now = datetime.utcnow().isoformat()
    _cur.execute("INSERT OR REPLACE INTO redeem_codes(code,amount,uses_allowed,uses_count,creator_id,created_at) VALUES (?,?,?,?,?,?)",
                 (code, int(amount), int(uses_allowed), 0, creator_id, now))
    _conn.commit()

def get_code_row(code):
    _cur.execute("SELECT code, amount, uses_allowed, uses_count, creator_id FROM redeem_codes WHERE code=?", (code,))
    return _cur.fetchone()

def mark_code_used(code, user_id):
    now = datetime.utcnow().isoformat()
    _cur.execute("INSERT OR IGNORE INTO used_codes(code,user_id,used_at) VALUES (?,?,?)", (code, user_id, now))
    _cur.execute("UPDATE redeem_codes SET uses_count = uses_count + 1 WHERE code=?", (code,))
    _conn.commit()

def user_used_code(code, user_id):
    _cur.execute("SELECT 1 FROM used_codes WHERE code=? AND user_id=?", (code, user_id))
    return bool(_cur.fetchone())

def give_packet(user_id, amount):
    _cur.execute("INSERT OR REPLACE INTO packets(user_id,amount,last_redeem) VALUES (?,?, COALESCE((SELECT last_redeem FROM packets WHERE user_id=?), ''))", (user_id, amount, user_id))
    _conn.commit()

def get_packet(user_id):
    _cur.execute("SELECT amount, last_redeem FROM packets WHERE user_id=?", (user_id,))
    return _cur.fetchone()

def set_packet_redeemed(user_id):
    _cur.execute("UPDATE packets SET last_redeem=? WHERE user_id=?", (datetime.utcnow().isoformat(), user_id))
    _conn.commit()

def max_bet_allowed(user_id, requested):
    bal = get_balance(user_id)
    limit = max(1, bal // 10)  # 10% of balance
    return min(requested, limit)

# ---------- COMMANDS ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # auto-promote owner username to admin on first start
    if user.username and user.username.lower() == OWNER_USERNAME.lower():
        add_admin(user.id)
    arg = context.args[0] if context.args else None
    ensure_user(user.id, user.username or user.first_name)
    # if started with redeem/referral code
    if arg:
        code_info = get_code_row(arg)
        if code_info:
            code, amt, uses_allowed, uses_count, creator = code_info
            if (uses_allowed == 0 or uses_count < uses_allowed) and not user_used_code(code, user.id):
                if creator != user.id:
                    change_balance(user.id, amt)
                    mark_code_used(code, user.id)
    row = get_user_row(user.id)
    bal = get_balance(user.id)
    await update.message.reply_text(
        f"🎰 Velrixo Casino Bot 🎰\nWelcome {user.first_name} — Balance: {bal} {CURRENCY}\n"
        f"Your referral code: `{row[7]}`\nUse `/referral` to share your code.\nUse /help for commands.",
        parse_mode="Markdown"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Main commands:\n"
        "/start [CODE] - register (use CODE to redeem if valid)\n"
        "/profile - see stats\n"
        "/dailybonus\n"
        "/spin (100)\n"
        "/bet <amount>\n"
        "/coinflip <heads/tails> <amount>\n"
        "/blackjack\n"
        "/dart <amount>\n"
        "/bowl <amount>\n"
        "/crash <amount>\n"
        "/rocket <amount>\n"
        "/guess <1-10> <amount>\n"
        "/mines <amount>\n"
        "/dragontiger <dragon/tiger> <amount>\n"
        "/duel @user <amount>\n"
        "/referral\n"
        "/redeem <CODE>\n"
        "/redeempacket\n"
        "/leaderboard\n"
        "Admin: /makecode /addadmin /removeadmin /givepacket /addcash /setcash /broadcast"
    )

async def profile_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid, update.effective_user.username or update.effective_user.first_name)
    row = get_user_row(uid)
    bal = row[2]; xp = row[3]; level = row[4]; streak = row[6]
    await update.message.reply_text(f"👤 {update.effective_user.first_name}\n💰 Balance: {bal} {CURRENCY}\n🧠 Level: {level} XP:{xp}\n🔥 Streak: {streak} days\nReferral: `{row[7]}`", parse_mode="Markdown")

# -- daily bonus
async def dailybonus_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid)
    if can_claim_daily(uid):
        bonus = random.randint(200, 500)
        row = get_user_row(uid)
        streak = row[6] or 0
        bonus += min(streak * 50, 500)
        change_balance(uid, bonus)
        set_daily_time(uid)
        add_xp(uid, 5)
        await update.message.reply_text(f"🎁 Daily bonus: +{bonus} {CURRENCY}\n💰 Now: {get_balance(uid)} {CURRENCY}")
    else:
        await update.message.reply_text("⏳ You already claimed daily bonus in the last 24 hours.")

# -- spin (fixed-bet slot)
async def spin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bet = 100
    if get_balance(uid) < bet:
        await update.message.reply_text("❌ Need 100 to spin.")
        return
    symbols = ["🍒","🍋","🔔","⭐","💎","7️⃣"]
    res = [random.choice(symbols) for _ in range(3)]
    if len(set(res)) == 1:
        win = bet * 6
        change_balance(uid, win)
        text = f"🎰 {' '.join(res)}\n🎉 JACKPOT! +{win} {CURRENCY}"
    elif len(set(res)) == 2:
        win = bet * 2
        change_balance(uid, win)
        text = f"🎰 {' '.join(res)}\nNice! +{win} {CURRENCY}"
    else:
        change_balance(uid, -bet)
        text = f"🎰 {' '.join(res)}\n😢 Lost {bet} {CURRENCY}"
    text += f"\n💰 Balance: {get_balance(uid)} {CURRENCY}"
    await update.message.reply_text(text)

# -- bet (50/50)
async def bet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /bet <amount>")
        return
    try:
        amt = int(context.args[0])
    except:
        await update.message.reply_text("Enter number.")
        return
    amt = max(1, amt)
    amt = max_bet_allowed(uid, amt)
    if amt > get_balance(uid):
        await update.message.reply_text("Not enough balance.")
        return
    if random.random() < 0.5:
        change_balance(uid, amt)
        add_xp(uid, 2)
        await update.message.reply_text(f"🔥 You won +{amt} {CURRENCY}\n💰 Now: {get_balance(uid)} {CURRENCY}")
    else:
        change_balance(uid, -amt)
        await update.message.reply_text(f"💀 You lost -{amt} {CURRENCY}\n💰 Now: {get_balance(uid)} {CURRENCY}")

# -- coinflip
async def coinflip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /coinflip <heads/tails> <amount>")
        return
    choice = context.args[0].lower()
    try:
        amt = int(context.args[1])
    except:
        await update.message.reply_text("Enter number.")
        return
    amt = max_bet_allowed(uid, amt)
    if amt > get_balance(uid):
        await update.message.reply_text("Not enough.")
        return
    result = random.choice(["heads","tails"])
    if result == choice:
        change_balance(uid, amt)
        add_xp(uid, 2)
        await update.message.reply_text(f"🪙 {result} — You won +{amt} {CURRENCY}\n💰 Now: {get_balance(uid)} {CURRENCY}")
    else:
        change_balance(uid, -amt)
        await update.message.reply_text(f"🪙 {result} — You lost -{amt} {CURRENCY}\n💰 Now: {get_balance(uid)} {CURRENCY}")

# -- blackjack (simple)
async def blackjack_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    bet = 100
    if get_balance(uid) < bet:
        await update.message.reply_text("Not enough for blackjack.")
        return
    player = random.randint(12,21)
    dealer = random.randint(12,21)
    if player > dealer:
        change_balance(uid, bet)
        await update.message.reply_text(f"🎉 You win! {player} vs {dealer} (+{bet})\n💰 Now: {get_balance(uid)} {CURRENCY}")
    elif player == dealer:
        await update.message.reply_text(f"😐 Tie: {player} vs {dealer} (no change)\n💰 Now: {get_balance(uid)} {CURRENCY}")
    else:
        change_balance(uid, -bet)
        await update.message.reply_text(f"💀 Dealer wins: {player} vs {dealer} (-{bet})\n💰 Now: {get_balance(uid)} {CURRENCY}")

# -- dart
async def dart_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /dart <amount>")
        return
    try:
        amt = int(context.args[0])
    except:
        await update.message.reply_text("Enter number.")
        return
    amt = max_bet_allowed(uid, amt)
    if amt > get_balance(uid):
        await update.message.reply_text("Not enough.")
        return
    target = random.randint(1,100)
    if target <= 10:
        change_balance(uid, amt)
        await update.message.reply_text(f"🎯 BULLSEYE! +{amt} {CURRENCY}\n💰 Now: {get_balance(uid)} {CURRENCY}")
    elif target <= 30:
        change_balance(uid, - (amt//2))
        await update.message.reply_text(f"😅 Near miss — lost half (-{amt//2})\n💰 Now: {get_balance(uid)} {CURRENCY}")
    else:
        change_balance(uid, -amt)
        await update.message.reply_text(f"💥 Miss! -{amt}\n💰 Now: {get_balance(uid)} {CURRENCY}")

# -- bowl
async def bowl_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /bowl <amount>")
        return
    try:
        amt = int(context.args[0])
    except:
        await update.message.reply_text("Enter number.")
        return
    amt = max_bet_allowed(uid, amt)
    if amt > get_balance(uid):
        await update.message.reply_text("Not enough.")
        return
    roll = random.randint(0,10)
    if roll == 10:
        win = int(amt * 3)
        change_balance(uid, win)
        await update.message.reply_text(f"🎳 STRIKE! +{win}\n💰 Now: {get_balance(uid)} {CURRENCY}")
    elif roll >= 7:
        win = int(amt * 1.5)
        change_balance(uid, win)
        await update.message.reply_text(f"🎳 Good! +{win}\n💰 Now: {get_balance(uid)} {CURRENCY}")
    else:
        change_balance(uid, -amt)
        await update.message.reply_text(f"🎳 Gutter! -{amt}\n💰 Now: {get_balance(uid)} {CURRENCY}")

# -- crash (simple / rocket)
async def crash_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /crash <amount>")
        return
    try:
        amt = int(context.args[0])
    except:
        await update.message.reply_text("Enter number.")
        return
    amt = max_bet_allowed(uid, amt)
    if amt > get_balance(uid):
        await update.message.reply_text("Not enough.")
        return
    crash_point = round(random.uniform(1.0, 8.0), 2)
    if crash_point > 5:
        crash_point = round(random.uniform(1.0, 5.0), 2)
    payout = int(amt * crash_point)
    change_balance(uid, payout - amt)
    await update.message.reply_text(f"🚀 Crash x{crash_point} — net +{payout-amt}\n💰 Now: {get_balance(uid)} {CURRENCY}")

# -- guess / lucky number
async def guess_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /guess <1-10> <amount>")
        return
    try:
        guess = int(context.args[0]); amt = int(context.args[1])
    except:
        await update.message.reply_text("Enter numbers.")
        return
    if not 1 <= guess <= 10:
        await update.message.reply_text("Guess 1-10.")
        return
    amt = max_bet_allowed(uid, amt)
    if amt > get_balance(uid):
        await update.message.reply_text("Not enough.")
        return
    secret = random.randint(1,10)
    if guess == secret:
        win = amt * 10
        change_balance(uid, win)
        await update.message.reply_text(f"🎉 Right! Number {secret}. +{win}\n💰 Now: {get_balance(uid)} {CURRENCY}")
    else:
        change_balance(uid, -amt)
        await update.message.reply_text(f"❌ Wrong. Number {secret}. -{amt}\n💰 Now: {get_balance(uid)} {CURRENCY}")

# -- mines
async def mines_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /mines <amount>")
        return
    try:
        amt = int(context.args[0])
    except:
        await update.message.reply_text("Enter amount.")
        return
    amt = max_bet_allowed(uid, amt)
    if amt > get_balance(uid):
        await update.message.reply_text("Not enough.")
        return
    safe = random.randint(0,4)
    if safe <= 2:
        win = amt * 2
        change_balance(uid, win)
        await update.message.reply_text(f"🟩 Safe! +{win}\n💰 Now: {get_balance(uid)} {CURRENCY}")
    else:
        change_balance(uid, -amt)
        await update.message.reply_text(f"💥 Boom! -{amt}\n💰 Now: {get_balance(uid)} {CURRENCY}")

# -- dragon tiger
async def dragontiger_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /dragontiger <dragon/tiger> <amount>")
        return
    choice = context.args[0].lower()
    try:
        amt = int(context.args[1])
    except:
        await update.message.reply_text("Enter number.")
        return
    amt = max_bet_allowed(uid, amt)
    if amt > get_balance(uid):
        await update.message.reply_text("Not enough.")
        return
    d = random.randint(1,13); t = random.randint(1,13)
    if (choice == "dragon" and d > t) or (choice=="tiger" and t > d):
        change_balance(uid, amt)
        await update.message.reply_text(f"🐉{d} vs 🐯{t} — You won +{amt}\n💰 Now: {get_balance(uid)} {CURRENCY}")
    elif d == t:
        await update.message.reply_text(f"🐉{d} = 🐯{t} — Tie (no change).")
    else:
        change_balance(uid, -amt)
        await update.message.reply_text(f"🐉{d} vs 🐯{t} — You lost -{amt}\n💰 Now: {get_balance(uid)} {CURRENCY}")

# -- duel PvP
async def duel_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2 and not update.message.reply_to_message:
        await update.message.reply_text("Usage: /duel @username <amount> (or reply + /duel <amount>)")
        return
    sender = update.effective_user
    if update.message.reply_to_message:
        target_user = update.message.reply_to_message.from_user
        try:
            amt = int(context.args[0])
        except:
            await update.message.reply_text("Usage: reply to user and /duel <amount>")
            return
    else:
        target_name = context.args[0].lstrip("@"); amt = int(context.args[1])
        _cur.execute("SELECT user_id FROM users WHERE username=? COLLATE NOCASE", (target_name,))
        r = _cur.fetchone()
        if not r:
            await update.message.reply_text("Target not registered.")
            return
        target_user = type('U',(object,),{"id":r[0],"username":target_name})
    amt = max_bet_allowed(sender.id, amt)
    if amt > get_balance(sender.id):
        await update.message.reply_text("You don't have enough.")
        return
    if amt > get_balance(target_user.id):
        await update.message.reply_text("Target doesn't have enough.")
        return
    s_roll = random.randint(1,100); t_roll = random.randint(1,100)
    if s_roll > t_roll:
        change_balance(sender.id, amt); change_balance(target_user.id, -amt)
        await update.message.reply_text(f"⚔️ You rolled {s_roll} vs {t_roll} — You win +{amt} {CURRENCY}")
    elif s_roll < t_roll:
        change_balance(sender.id, -amt); change_balance(target_user.id, amt)
        await update.message.reply_text(f"⚔️ You rolled {s_roll} vs {t_roll} — You lost -{amt} {CURRENCY}")
    else:
        await update.message.reply_text(f"⚔️ Tie {s_roll} — No change.")

# -- referral
async def referral_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    ensure_user(uid, update.effective_user.username or update.effective_user.first_name)
    row = get_user_row(uid)
    await update.message.reply_text(f"🔗 Your referral code: `{row[7]}`\nShare: `/start {row[7]}`", parse_mode="Markdown")

# -- redeem by code
async def redeem_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not context.args:
        await update.message.reply_text("Usage: /redeem <CODE>")
        return
    code = context.args[0].strip()
    row = get_code_row(code)
    if not row:
        await update.message.reply_text("❌ Invalid code.")
        return
    _code, amount, uses_allowed, uses_count, creator = row
    if user_used_code(code, uid):
        await update.message.reply_text("❌ You already used this code.")
        return
    if uses_allowed != 0 and uses_count >= uses_allowed:
        await update.message.reply_text("❌ This code has reached its total usage limit.")
        return
    change_balance(uid, amount)
    mark_code_used(code, uid)
    await update.message.reply_text(f"🎁 Redeemed +{amount} {CURRENCY}!\n💰 Now: {get_balance(uid)} {CURRENCY}")

# -- admin: makecode
async def makecode_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ Only admins can create codes.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /makecode CODE AMOUNT [uses_allowed]\nSet uses_allowed=0 for unlimited.")
        return
    code = context.args[0].strip()
    try:
        amount = int(context.args[1])
    except:
        await update.message.reply_text("Amount must be number.")
        return
    uses_allowed = 1
    if len(context.args) >= 3:
        try:
            uses_allowed = int(context.args[2])
        except:
            uses_allowed = 1
    make_code(code, amount, uses_allowed, uid)
    await update.message.reply_text(f"✅ Code `{code}` created: {amount} {CURRENCY} — uses_allowed: {uses_allowed}", parse_mode="Markdown")

# -- admin: add/remove/list admins
async def addadmin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ Only admins can add admins.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /addadmin <user_id>")
        return
    try:
        new_id = int(context.args[0])
    except:
        await update.message.reply_text("Provide numeric user id.")
        return
    add_admin(new_id)
    await update.message.reply_text(f"✅ Added admin: {new_id}")

async def removeadmin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ Only admins can remove admins.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /removeadmin <user_id>")
        return
    try:
        rem_id = int(context.args[0])
    except:
        await update.message.reply_text("Provide numeric user id.")
        return
    remove_admin(rem_id)
    await update.message.reply_text(f"✅ Removed admin: {rem_id}")

async def adminlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ Only admins can view admin list.")
        return
    _cur.execute("SELECT user_id FROM admins")
    rows = _cur.fetchall()
    text = "Admins:\n" + "\n".join(str(r[0]) for r in rows)
    await update.message.reply_text(text)

# -- givepacket
async def givepacket_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ Only admins can give packets.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /givepacket @username amount")
        return
    target = context.args[0].lstrip("@")
    try:
        amt = int(context.args[1])
    except:
        await update.message.reply_text("Amount must be number.")
        return
    _cur.execute("SELECT user_id FROM users WHERE username=? COLLATE NOCASE", (target,))
    r = _cur.fetchone()
    if not r:
        await update.message.reply_text("Target user not found (they must /start first).")
        return
    give_packet(r[0], amt)
    await update.message.reply_text(f"✅ Assigned packet {amt} {CURRENCY} to @{target}")

# -- redeem_packet (user)
async def redeem_packet_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    pkt = get_packet(uid)
    if not pkt:
        await update.message.reply_text("❌ No assigned packet.")
        return
    amount, last_redeem = pkt
    if last_redeem:
        try:
            last = datetime.fromisoformat(last_redeem)
            if datetime.utcnow() - last < timedelta(days=30):
                next_allowed = last + timedelta(days=30)
                days = (next_allowed - datetime.utcnow()).days
                await update.message.reply_text(f"🕐 You already redeemed this month. Next in {days} days.")
                return
        except:
            pass
    if amount <= 0:
        await update.message.reply_text("❌ Packet amount is zero.")
        return
    change_balance(uid, amount)
    set_packet_redeemed(uid)
    await update.message.reply_text(f"🎁 Redeemed +{amount} {CURRENCY} — Now: {get_balance(uid)} {CURRENCY}")

# -- leaderboard
async def leaderboard_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _cur.execute("SELECT username, balance FROM users ORDER BY balance DESC LIMIT 10")
    rows = _cur.fetchall()
    text = "🏆 Top Players 🏆\n"
    for i,(u,b) in enumerate(rows, start=1):
        text += f"{i}. @{u or 'Anonymous'} — {b} {CURRENCY}\n"
    await update.message.reply_text(text)

# -- admin economy commands
async def addcash_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ Only admins.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /addcash @username amount")
        return
    target = context.args[0].lstrip("@")
    try:
        amt = int(context.args[1])
    except:
        await update.message.reply_text("Enter amount.")
        return
    _cur.execute("SELECT user_id FROM users WHERE username=? COLLATE NOCASE", (target,))
    r = _cur.fetchone()
    if not r:
        await update.message.reply_text("User not found.")
        return
    change_balance(r[0], amt)
    await update.message.reply_text(f"✅ Added {amt} {CURRENCY} to @{target}")

async def removecash_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ Only admins.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /removecash @username amount")
        return
    target = context.args[0].lstrip("@")
    try:
        amt = int(context.args[1])
    except:
        await update.message.reply_text("Enter amount.")
        return
    _cur.execute("SELECT user_id FROM users WHERE username=? COLLATE NOCASE", (target,))
    r = _cur.fetchone()
    if not r:
        await update.message.reply_text("User not found.")
        return
    change_balance(r[0], -amt)
    await update.message.reply_text(f"✅ Removed {amt} {CURRENCY} from @{target}")

async def setcash_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ Only admins.")
        return
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /setcash @username amount")
        return
    target = context.args[0].lstrip("@")
    try:
        amt = int(context.args[1])
    except:
        await update.message.reply_text("Enter amount.")
        return
    _cur.execute("SELECT user_id FROM users WHERE username=? COLLATE NOCASE", (target,))
    r = _cur.fetchone()
    if not r:
        await update.message.reply_text("User not found.")
        return
    set_balance(r[0], amt)
    await update.message.reply_text(f"✅ Set @{target} balance to {amt} {CURRENCY}")

async def broadcast_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("❌ Only admins.")
        return
    if not context.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    msg = " ".join(context.args)
    _cur.execute("SELECT user_id FROM users")
    users = _cur.fetchall()
    for (u,) in users:
        try:
            await context.bot.send_message(u, f"📢 Admin broadcast:\n\n{msg}")
        except:
            pass
    await update.message.reply_text("✅ Broadcast attempted.")

# ---------- START (non-async main used by Railway) ----------
def main():
    init_db()
    if not BOT_TOKEN:
        log.error("No BOT_TOKEN provided. Set BOT_TOKEN env var or embed token in file.")
        return

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # Public commands
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("profile", profile_cmd))
    app.add_handler(CommandHandler("dailybonus", dailybonus_cmd))
    app.add_handler(CommandHandler("spin", spin_cmd))
    app.add_handler(CommandHandler("bet", bet_cmd))
    app.add_handler(CommandHandler("coinflip", coinflip_cmd))
    app.add_handler(CommandHandler("blackjack", blackjack_cmd))
    app.add_handler(CommandHandler("dart", dart_cmd))
    app.add_handler(CommandHandler("bowl", bowl_cmd))
    app.add_handler(CommandHandler("crash", crash_cmd))
    app.add_handler(CommandHandler("rocket", crash_cmd))  # rocket synonym
    app.add_handler(CommandHandler("guess", guess_cmd))
    app.add_handler(CommandHandler("mines", mines_cmd))
    app.add_handler(CommandHandler("dragontiger", dragontiger_cmd))
    app.add_handler(CommandHandler("duel", duel_cmd))
    app.add_handler(CommandHandler("referral", referral_cmd))
    app.add_handler(CommandHandler("redeem", redeem_cmd))
    app.add_handler(CommandHandler("redeempacket", redeem_packet_cmd))
    app.add_handler(CommandHandler("leaderboard", leaderboard_cmd))

    # Admin commands
    app.add_handler(CommandHandler("makecode", makecode_cmd))
    app.add_handler(CommandHandler("addadmin", addadmin_cmd))
    app.add_handler(CommandHandler("removeadmin", removeadmin_cmd))
    app.add_handler(CommandHandler("adminlist", adminlist_cmd))
    app.add_handler(CommandHandler("givepacket", givepacket_cmd))
    app.add_handler(CommandHandler("addcash", addcash_cmd))
    app.add_handler(CommandHandler("removecash", removecash_cmd))
    app.add_handler(CommandHandler("setcash", setcash_cmd))
    app.add_handler(CommandHandler("broadcast", broadcast_cmd))

    log.info("Velrixo Casino Bot starting...")
    # Use run_polling() (synchronous) - avoids asyncio loop close issues on Railway
    app.run_polling()

if __name__ == "__main__":
    main()
