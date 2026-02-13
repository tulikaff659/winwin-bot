import json
import logging
import os
import asyncio
import traceback
from pathlib import Path
from typing import Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# ------------------- SOZLAMALAR -------------------
TOKEN = os.environ.get("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = 6935090105  # Admin Telegram ID
DATA_FILE = "games.json"
USERS_FILE = "users.json"

REFERRAL_BONUS = 2500        # Har bir taklif uchun bonus
START_BONUS = 15000          # Startdan keyin beriladigan bonus
MIN_WITHDRAW = 25000          # Minimal yechish summasi
BOT_USERNAME = "YourBotUsername"  # Botning @username (havola yaratish uchun)

# ------------------- LOGLASH -------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ------------------- MAʼLUMOTLAR SAQLASH -------------------
def load_games() -> Dict:
    if Path(DATA_FILE).exists():
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_games(games: Dict):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(games, f, ensure_ascii=False, indent=4)

games_data = load_games()

def load_users() -> Dict:
    if Path(USERS_FILE).exists():
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(users: Dict):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

users_data = load_users()

# ------------------- YORDAMCHI FUNKSIYALAR -------------------
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

def get_game_keyboard() -> InlineKeyboardMarkup:
    keyboard = []
    for game in games_data.keys():
        keyboard.append([InlineKeyboardButton(game, callback_data=f"game_{game}")])
    return InlineKeyboardMarkup(keyboard)

def get_admin_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("➕ Add Game", callback_data="admin_add")],
        [InlineKeyboardButton("➖ Remove Game", callback_data="admin_remove_list")],
        [InlineKeyboardButton("✏️ Edit Game", callback_data="admin_edit_list")],
        [InlineKeyboardButton("📊 Statistics", callback_data="admin_stats")],
        [InlineKeyboardButton("❌ Close", callback_data="admin_close")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_games_list_keyboard(action_prefix: str) -> InlineKeyboardMarkup:
    keyboard = []
    for game in games_data.keys():
        keyboard.append([InlineKeyboardButton(game, callback_data=f"{action_prefix}{game}")])
    keyboard.append([InlineKeyboardButton("◀️ Back", callback_data="admin_back")])
    return InlineKeyboardMarkup(keyboard)

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    """Asosiy menyu tugmalari: Pul ishlash, Balans, Pul chiqarish."""
    keyboard = [
        [InlineKeyboardButton("💰 Pul ishlash", callback_data="earn")],
        [InlineKeyboardButton("💵 Balans", callback_data="balance")],
        [InlineKeyboardButton("💸 Pul chiqarish", callback_data="withdraw")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_referral_link(user_id: int) -> str:
    """Foydalanuvchi uchun referral havola yaratish."""
    return f"https://t.me/{BOT_USERNAME}?start=ref_{user_id}"

async def ensure_user(user_id: int, referred_by: Optional[int] = None) -> dict:
    """Foydalanuvchi maʼlumotlarini yaratish yoki olish."""
    user_id_str = str(user_id)
    if user_id_str not in users_data:
        users_data[user_id_str] = {
            "balance": 0,
            "referred_by": referred_by,
            "referrals": 0,
            "start_bonus_given": False,
            "registered_at": None  # optional
        }
        save_users(users_data)
    return users_data[user_id_str]

async def give_start_bonus(user_id: int, context: ContextTypes.DEFAULT_TYPE):
    """1-2 daqiqadan so‘ng start bonusini berish."""
    await asyncio.sleep(90)  # 1.5 daqiqa
    user_id_str = str(user_id)
    if user_id_str in users_data and not users_data[user_id_str].get("start_bonus_given", False):
        users_data[user_id_str]["balance"] += START_BONUS
        users_data[user_id_str]["start_bonus_given"] = True
        save_users(users_data)
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🎉 Tabriklaymiz! Sizga start bonusi sifatida {START_BONUS} so‘m berildi. Endi balansingiz: {users_data[user_id_str]['balance']} so‘m."
            )
        except Exception as e:
            logger.error(f"Bonus xabarini yuborishda xatolik: {e}")

# ------------------- HANDLERLAR -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komandasi – chiroyli xabar, referral qayta ishlash va menyu."""
    user = update.effective_user
    user_id = user.id
    args = context.args

    # Referralni tekshirish
    referred_by = None
    if args and args[0].startswith("ref_"):
        try:
            ref_user_id = int(args[0].replace("ref_", ""))
            if ref_user_id != user_id:  # o‘zini o‘zi taklif qilmasin
                referred_by = ref_user_id
        except:
            pass

    # Foydalanuvchini yaratish (agar mavjud bo‘lmasa)
    user_data = await ensure_user(user_id, referred_by)

    # Agar referral bo‘lsa va referer mavjud bo‘lsa, bonus berish
    if referred_by and str(referred_by) in users_data:
        referer_data = users_data[str(referred_by)]
        # Referalni bir marta hisoblash uchun tekshirish (har bir yangi user faqat bir marta bonus keltiradi)
        # Agar referred_by allaqachon o‘rnatilgan bo‘lsa, qayta bonus bermaymiz
        if user_data.get("referred_by") is None:  # yangi foydalanuvchi
            # Referalni yangilash
            user_data["referred_by"] = referred_by
            # Refererga bonus qo‘shish
            referer_data["balance"] += REFERRAL_BONUS
            referer_data["referrals"] = referer_data.get("referrals", 0) + 1
            save_users(users_data)
            # Refererga xabar yuborish
            try:
                await context.bot.send_message(
                    chat_id=referred_by,
                    text=f"🎉 Sizning taklifingiz orqali yangi foydalanuvchi (@{user.username or user.first_name}) qo‘shildi! Balansingizga {REFERRAL_BONUS} so‘m qo‘shildi. Hozirgi balans: {referer_data['balance']} so‘m."
                )
            except Exception as e:
                logger.error(f"Refererga xabar yuborishda xatolik: {e}")

    # Start bonusini rejalashtirish (agar hali berilmagan bo‘lsa)
    if not user_data.get("start_bonus_given", False):
        asyncio.create_task(give_start_bonus(user_id, context))

    # Chiroyli xabar (avvalgi)
    welcome_text = (
        "🎰 *WinWin Bukmekeriga xush kelibsiz!*\n\n"
        "🎯 Ishonchli o‘yinlar tahlili\n"
        "📊 Slot o‘yinlarini analiz qilish\n"
        "💡 Qayerda, qachon va qanday g‘alaba qilish sirlari\n\n"
        "👇 Boshlash uchun quyidagi tugmani bosing:"
    )
    shaffof_tugma = [[InlineKeyboardButton("✨ Shaffof tugma", callback_data="show_games")]]
    await update.message.reply_text(
        welcome_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(shaffof_tugma)
    )

    # Asosiy menyu (pul ishlash, balans, pul chiqarish)
    menu_text = (
        "🛠 *Qo‘shimcha imkoniyatlar:*\n\n"
        "💰 *Pul ishlash* – do‘stlaringizni taklif qiling va bonus oling.\n"
        "💵 *Balans* – hisobingizdagi mablag‘ni ko‘ring.\n"
        "💸 *Pul chiqarish* – mablag‘ni kartangizga yechib oling."
    )
    await update.message.reply_text(
        menu_text,
        parse_mode="Markdown",
        reply_markup=get_main_menu_keyboard()
    )

async def show_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """'Shaffof tugma' bosilganda – o‘yinlar ro‘yxati."""
    query = update.callback_query
    await query.answer()
    if not games_data:
        await query.edit_message_text("Hozircha hech qanday o‘yin mavjud emas.")
        return
    text = "🎮 Quyidagi oyinlardan birini tanlang va pul ishlashni boshlang:"
    await query.edit_message_text(text, reply_markup=get_game_keyboard())

async def game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """O‘yin tanlanganda kontent yuborish."""
    query = update.callback_query
    await query.answer()
    game_name = query.data.replace("game_", "")
    game = games_data.get(game_name)
    if not game:
        await query.message.reply_text("Bu o‘yin topilmadi.")
        return

    game["views"] = game.get("views", 0) + 1
    save_games(games_data)

    text = game.get("text", "Maʼlumot hozircha kiritilmagan.")
    photo_id = game.get("photo_id")
    file_id = game.get("file_id")
    button_text = game.get("button_text")
    button_url = game.get("button_url")

    reply_markup = None
    if button_text and button_url:
        keyboard = [[InlineKeyboardButton(button_text, url=button_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)

    if photo_id:
        await query.message.reply_photo(
            photo=photo_id,
            caption=text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )
    else:
        await query.message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

    if file_id:
        await query.message.reply_document(document=file_id)

# ------------------- YANGI MENYU TUGMALARI -------------------
async def earn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pul ishlash bo‘limi – referral havola va tushuntirish."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    await ensure_user(user_id)  # mavjudligini tekshirish

    referral_link = get_referral_link(user_id)
    text = (
        "💰 *Qanday qilib pul ishlash mumkin?*\n\n"
        "Har bir do‘stingizni botga taklif qilganingiz uchun *2500 so‘m* olasiz.\n"
        "Do‘stingiz botga start bosishi bilan sizning balansingizga bonus tushadi.\n\n"
        "Sizning referral havolangiz:\n"
        f"`{referral_link}`\n\n"
        "Havolani do‘stlaringizga yuboring yoki quyidagi tugma orqali ulashing."
    )
    # Ulashish tugmasi – Telegram share URL
    share_url = f"https://t.me/share/url?url={referral_link}&text=Bu%20bot%20orqali%20pul%20ishlash%20mumkin!%20Keling%2C%20birga%20boshlaymiz."
    keyboard = [[InlineKeyboardButton("📤 Ulashish", url=share_url)]]
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi balansini ko‘rsatish."""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_data = await ensure_user(user_id)
    balance = user_data.get("balance", 0)
    referrals = user_data.get("referrals", 0)
    text = (
        f"💵 *Sizning balansingiz:*\n\n"
        f"Balans: *{balance} so‘m*\n"
        f"Taklif qilgan do‘stlaringiz: *{referrals}*\n\n"
        f"Minimal yechish summasi: {MIN_WITHDRAW} so‘m."
    )
    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=get_main_menu_keyboard())

async def withdraw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Pul chiqarish – hozircha tashqi havola."""
    query = update.callback_query
    await query.answer()
    # Hozircha test.com ga yo‘naltiruvchi tugma
    keyboard = [[InlineKeyboardButton("💳 Pul chiqarish", url="https://test.com")]]
    await query.edit_message_text(
        "Pul yechish uchun quyidagi tugmani bosing:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ------------------- ADMIN PANEL (o‘yinlar) -------------------
# (Bu qism avvalgi kod bilan bir xil, o‘zgartirilmagan)
# ... [admin panel kodlari] ...

# Qisqalik uchun admin panel kodlari to‘liq keltirilmagan, ammo sizning oldingi kodingizni saqlab qolishingiz kerak.
# Quyida faqat asosiy admin funksiyalari keltirilgan (siz to‘liq admin panelni qo‘shishingiz lozim).

# ------------------- ADMIN PANEL (qisqa) -------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Siz admin emassiz.")
        return
    await update.message.reply_text("👨‍💻 Admin paneli:", reply_markup=get_admin_keyboard())

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # To‘liq admin panel kodi (oldingi versiyadan)
    pass  # Bu yerga to‘liq admin kodini qo‘ying

# ------------------- ASOSIY -------------------
def main():
    app = Application.builder().token(TOKEN).build()

    # Asosiy handlerlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(show_games, pattern="^show_games$"))
    app.add_handler(CallbackQueryHandler(game_callback, pattern="^game_"))
    app.add_handler(CallbackQueryHandler(earn_callback, pattern="^earn$"))
    app.add_handler(CallbackQueryHandler(balance_callback, pattern="^balance$"))
    app.add_handler(CallbackQueryHandler(withdraw_callback, pattern="^withdraw$"))

    # Admin panel
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^(admin_|remove_|edit_|confirm_remove)"))

    # Conversation handlerlar (add/edit) – oldingi koddagidek
    # (To‘liq kodda bu yerga add_conv, edit_conv va h.k. qo‘shiladi)

    logger.info("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
