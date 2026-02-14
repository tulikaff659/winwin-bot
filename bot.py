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
MIN_WITHDRAW = 25000         # Minimal yechish summasi
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
    """O‘yinlar ro‘yxati + bosh menyu tugmasi."""
    keyboard = []
    for game in games_data.keys():
        keyboard.append([InlineKeyboardButton(game, callback_data=f"game_{game}")])
    keyboard.append([InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")])
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

def get_main_keyboard() -> InlineKeyboardMarkup:
    """Asosiy menyu tugmalari:
       - 1-qator: O‘yinlar ro‘yxati
       - 2-qator: Pul ishlash | Balans (yonma-yon)
    """
    keyboard = [
        [InlineKeyboardButton("🎮 O‘yinlar ro‘yxati", callback_data="show_games")],
        [
            InlineKeyboardButton("💰 Pul ishlash", callback_data="earn"),
            InlineKeyboardButton("💵 Balans", callback_data="balance")
        ]
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

# ------------------- START HANDLER -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start komandasi – bitta xabar va barcha tugmalar."""
    user = update.effective_user
    user_id = user.id
    args = context.args

    # Referralni tekshirish
    referred_by = None
    if args and args[0].startswith("ref_"):
        try:
            ref_user_id = int(args[0].replace("ref_", ""))
            if ref_user_id != user_id:
                referred_by = ref_user_id
        except:
            pass

    # Foydalanuvchini yaratish (agar mavjud bo‘lmasa)
    user_data = await ensure_user(user_id, referred_by)

    # Agar referral bo‘lsa va referer mavjud bo‘lsa, bonus berish
    if referred_by and str(referred_by) in users_data:
        referer_data = users_data[str(referred_by)]
        if user_data.get("referred_by") is None:  # yangi foydalanuvchi
            user_data["referred_by"] = referred_by
            referer_data["balance"] += REFERRAL_BONUS
            referer_data["referrals"] = referer_data.get("referrals", 0) + 1
            save_users(users_data)
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

    # Bitta xabar – barcha tugmalar bilan
    text = (
        "🎰 *WinWin Bukmekeriga xush kelibsiz!* 🎰\n\n"
        "🔥 *Premium bonuslar* va har hafta yangi yutuqlar sizni kutmoqda!\n"
        "📊 *O‘yinlar uchun maxsus yutish strategiyalari* va *signal* xizmati orqali g‘alaba qozonish imkoniyatingizni oshiring.\n\n"
        "💰 Bu yerda nafaqat o‘ynab, balki *pul ishlashingiz* mumkin:\n"
        "– Do‘stlaringizni taklif qiling va har bir taklif uchun *2500 so‘m* oling.\n"
        "– Start bonus sifatida *15000 so‘m* hamyoningizga tushadi.\n\n"
        "👇 Quyidagi tugmalar orqali imkoniyatlarni kashf eting:"
    )
    await update.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# ------------------- BOSH MENYUGA QAYTISH -------------------
async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bosh menyu tugmasi bosilganda yangi xabar yuboradi."""
    query = update.callback_query
    await query.answer()
    text = (
        "🎰 *WinWin Bukmekeriga xush kelibsiz!* 🎰\n\n"
        "🔥 *Premium bonuslar* va har hafta yangi yutuqlar sizni kutmoqda!\n"
        "📊 *O‘yinlar uchun maxsus yutish strategiyalari* va *signal* xizmati orqali g‘alaba qozonish imkoniyatingizni oshiring.\n\n"
        "💰 Bu yerda nafaqat o‘ynab, balki *pul ishlashingiz* mumkin:\n"
        "– Do‘stlaringizni taklif qiling va har bir taklif uchun *2500 so‘m* oling.\n"
        "– Start bonus sifatida *15000 so‘m* hamyoningizga tushadi.\n\n"
        "👇 Quyidagi tugmalar orqali imkoniyatlarni kashf eting:"
    )
    await query.message.reply_text(
        text,
        parse_mode="Markdown",
        reply_markup=get_main_keyboard()
    )

# ------------------- O‘YINLAR -------------------
async def show_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not games_data:
        await query.edit_message_text(
            "Hozircha hech qanday o‘yin mavjud emas.",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]])
        )
        return
    text = "🎮 Quyidagi oyinlardan birini tanlang va pul ishlashni boshlang:"
    await query.edit_message_text(text, reply_markup=get_game_keyboard())

async def game_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    # Bosh menyuga qaytish tugmasi
    back_button = [[InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]]

    # Agar tashqi havola tugmasi bo‘lsa, uni ham qo‘shamiz (faqat rasm/matn xabariga)
    reply_markup = None
    if button_text and button_url:
        keyboard = [[InlineKeyboardButton(button_text, url=button_url)], back_button[0]]
        reply_markup = InlineKeyboardMarkup(keyboard)
    else:
        reply_markup = InlineKeyboardMarkup(back_button)

    # 1. APK faylini yuborish (agar mavjud bo‘lsa)
    if file_id:
        await query.message.reply_document(document=file_id)

    # 2. Rasm yoki matnni yuborish (bosh menyu tugmasi bilan)
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

# ------------------- PUL ISHLASH, BALANS, PUL CHIQARISH -------------------
async def earn_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    await ensure_user(user_id)

    referral_link = get_referral_link(user_id)
    text = (
        "💰 *Qanday qilib pul ishlash mumkin?*\n\n"
        "Har bir do‘stingizni botga taklif qilganingiz uchun *2500 so‘m* olasiz.\n"
        "Do‘stingiz botga start bosishi bilan sizning balansingizga bonus tushadi.\n\n"
        "Sizning referral havolangiz:\n"
        f"`{referral_link}`\n\n"
        "Havolani do‘stlaringizga yuboring yoki quyidagi tugma orqali ulashing."
    )
    share_url = f"https://t.me/share/url?url={referral_link}&text=Bu%20bot%20orqali%20pul%20ishlash%20mumkin!%20Keling%2C%20birga%20boshlaymiz."
    keyboard = [
        [InlineKeyboardButton("📤 Ulashish", url=share_url)],
        [InlineKeyboardButton("💸 Pul chiqarish", callback_data="withdraw")],
        [InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def balance_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    keyboard = [
        [InlineKeyboardButton("💸 Pul chiqarish", callback_data="withdraw")],
        [InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def withdraw_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("💳 Pul chiqarish", url="https://futbolinsidepulyechish.netlify.app/")],
        [InlineKeyboardButton("◀️ Bosh menyu", callback_data="main_menu")]
    ]
    await query.edit_message_text(
        "Pul yechish uchun quyidagi tugmani bosing:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ------------------- ADMIN PANEL (umumiy callbacklar) -------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Siz admin emassiz.")
        return
    await update.message.reply_text("👨‍💻 Admin paneli:", reply_markup=get_admin_keyboard())

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panelidagi callbacklarni boshqaradi (admin_add va edit_ dan tashqari)."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Siz admin emassiz.")
        return

    data = query.data

    if data == "admin_remove_list":
        if not games_data:
            await query.edit_message_text("Hech qanday o‘yin mavjud emas.")
            return
        await query.edit_message_text(
            "O‘chiriladigan o‘yinni tanlang:",
            reply_markup=get_games_list_keyboard("remove_")
        )

    elif data == "admin_edit_list":
        if not games_data:
            await query.edit_message_text("Hech qanday o‘yin mavjud emas.")
            return
        await query.edit_message_text(
            "Tahrirlanadigan o‘yinni tanlang:",
            reply_markup=get_games_list_keyboard("edit_")
        )

    elif data == "admin_stats":
        if not games_data:
            await query.edit_message_text("Statistika uchun maʼlumot yo‘q.")
            return
        lines = ["📊 Statistika:"]
        total = 0
        for name, game in games_data.items():
            views = game.get("views", 0)
            lines.append(f"• {name}: {views} marta ko‘rilgan")
            total += views
        lines.append(f"\nJami: {total} marta")
        await query.edit_message_text("\n".join(lines), reply_markup=get_admin_keyboard())

    elif data == "admin_close":
        await query.edit_message_text("Panel yopildi.")

    elif data == "admin_back":
        await query.edit_message_text("Admin paneli:", reply_markup=get_admin_keyboard())

    elif data.startswith("remove_"):
        game_name = data.replace("remove_", "")
        context.user_data["remove_game"] = game_name
        keyboard = [
            [InlineKeyboardButton("✅ Ha", callback_data="confirm_remove")],
            [InlineKeyboardButton("❌ Yo‘q", callback_data="admin_back")]
        ]
        await query.edit_message_text(
            f"'{game_name}' o‘yinini o‘chirishni tasdiqlaysizmi?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif data == "confirm_remove":
        game_name = context.user_data.get("remove_game")
        if game_name and game_name in games_data:
            del games_data[game_name]
            save_games(games_data)
            await query.edit_message_text(
                f"✅ '{game_name}' o‘chirildi.",
                reply_markup=get_admin_keyboard()
            )
        else:
            await query.edit_message_text("Xatolik yuz berdi.", reply_markup=get_admin_keyboard())

    # edit_ bilan boshlangan callbacklar endi bu yerda emas, ular alohida handlerlar tomonidan boshqariladi
    return

# ------------------- ADD GAME KONVERSATSIYASI (entry point) -------------------
async def admin_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add Game tugmasi bosilganda ishga tushadi."""
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Siz admin emassiz.")
        return ConversationHandler.END

    context.user_data["add_game"] = {}
    await query.edit_message_text("Yangi o‘yin nomini kiriting:")
    return ADD_NAME

# ------------------- ADD GAME HOLATLARI -------------------
ADD_NAME, ADD_TEXT, ADD_PHOTO, ADD_FILE, ADD_BUTTON_TEXT, ADD_BUTTON_URL = range(6)

async def add_game_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        name = update.message.text.strip()
        if not name:
            await update.message.reply_text("Nom bo‘sh bo‘lishi mumkin emas. Qayta kiriting:")
            return ADD_NAME
        if name in games_data:
            await update.message.reply_text("Bu nom allaqachon mavjud. Boshqa nom kiriting:")
            return ADD_NAME
        context.user_data["add_game"]["name"] = name
        await update.message.reply_text("Endi o‘yin matnini kiriting (HTML teglar bilan):")
        return ADD_TEXT
    except Exception as e:
        logger.error(f"add_game_name xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi. Qaytadan urinib ko‘ring.")
        return ConversationHandler.END

async def add_game_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        text = update.message.text
        context.user_data["add_game"]["text"] = text
        await update.message.reply_text(
            "Matn saqlandi. Endi rasm yuboring (ixtiyoriy) yoki /skip ni bosing."
        )
        return ADD_PHOTO
    except Exception as e:
        logger.error(f"add_game_text xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message.photo:
            photo_id = update.message.photo[-1].file_id
            context.user_data["add_game"]["photo_id"] = photo_id
            await update.message.reply_text("Rasm saqlandi. Endi fayl (APK) yuboring (ixtiyoriy) yoki /skip ni bosing.")
        else:
            await update.message.reply_text("Iltimos, rasm yuboring yoki /skip ni bosing.")
            return ADD_PHOTO
        return ADD_FILE
    except Exception as e:
        logger.error(f"add_game_photo xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_photo_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["add_game"]["photo_id"] = None
        await update.message.reply_text("Rasm o‘tkazib yuborildi. Endi fayl (APK) yuboring (ixtiyoriy) yoki /skip ni bosing.")
        return ADD_FILE
    except Exception as e:
        logger.error(f"add_game_photo_skip xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message.document:
            file_id = update.message.document.file_id
            context.user_data["add_game"]["file_id"] = file_id
        else:
            context.user_data["add_game"]["file_id"] = None
        await update.message.reply_text(
            "Fayl saqlandi. Endi tugma matnini kiriting (ixtiyoriy) yoki /skip ni bosing.\n"
            "Masalan: '🎮 O‘yin sayti'"
        )
        return ADD_BUTTON_TEXT
    except Exception as e:
        logger.error(f"add_game_file xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_file_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["add_game"]["file_id"] = None
        await update.message.reply_text(
            "Fayl o‘tkazib yuborildi. Endi tugma matnini kiriting (ixtiyoriy) yoki /skip ni bosing.\n"
            "Masalan: '🎮 O‘yin sayti'"
        )
        return ADD_BUTTON_TEXT
    except Exception as e:
        logger.error(f"add_game_file_skip xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        button_text = update.message.text.strip()
        context.user_data["add_game"]["button_text"] = button_text
        await update.message.reply_text(
            "Tugma matni saqlandi. Endi tugma havolasini (URL) kiriting (ixtiyoriy) yoki /skip ni bosing.\n"
            "Masalan: https://example.com"
        )
        return ADD_BUTTON_URL
    except Exception as e:
        logger.error(f"add_game_button_text xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_button_text_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["add_game"]["button_text"] = None
        await update.message.reply_text(
            "Tugma matni o‘tkazib yuborildi. Endi tugma havolasini (URL) kiriting (ixtiyoriy) yoki /skip ni bosing."
        )
        return ADD_BUTTON_URL
    except Exception as e:
        logger.error(f"add_game_button_text_skip xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_button_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        button_url = update.message.text.strip()
        context.user_data["add_game"]["button_url"] = button_url
        # Saqlash
        game_data = context.user_data["add_game"]
        games_data[game_data["name"]] = {
            "text": game_data["text"],
            "photo_id": game_data.get("photo_id"),
            "file_id": game_data.get("file_id"),
            "button_text": game_data.get("button_text"),
            "button_url": game_data.get("button_url"),
            "views": 0
        }
        save_games(games_data)
        await update.message.reply_text(
            f"✅ '{game_data['name']}' o‘yini qo‘shildi!",
            reply_markup=get_admin_keyboard()
        )
        context.user_data.pop("add_game", None)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"add_game_button_url xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_button_url_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["add_game"]["button_url"] = None
        game_data = context.user_data["add_game"]
        games_data[game_data["name"]] = {
            "text": game_data["text"],
            "photo_id": game_data.get("photo_id"),
            "file_id": game_data.get("file_id"),
            "button_text": game_data.get("button_text"),
            "button_url": None,
            "views": 0
        }
        save_games(games_data)
        await update.message.reply_text(
            f"✅ '{game_data['name']}' o‘yini qo‘shildi!",
            reply_markup=get_admin_keyboard()
        )
        context.user_data.pop("add_game", None)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"add_game_button_url_skip xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def add_game_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Qo‘shish bekor qilindi.", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# ------------------- EDIT GAME KONVERSATSIYALARI -------------------
EDIT_ACTION, EDIT_TEXT, EDIT_PHOTO, EDIT_FILE, EDIT_BUTTON_TEXT, EDIT_BUTTON_URL = range(6, 12)

async def edit_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Yangi matnni kiriting (HTML teglar bilan):")
    return EDIT_TEXT

async def edit_photo_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Yangi rasmni yuboring (reply orqali):")
    return EDIT_PHOTO

async def edit_file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Yangi faylni (APK) yuboring (reply orqali):")
    return EDIT_FILE

async def edit_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Yangi tugma matnini kiriting (ixtiyoriy, /skip):")
    return EDIT_BUTTON_TEXT

async def edit_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        button_text = update.message.text.strip()
        context.user_data["edit_button_text"] = button_text
        await update.message.reply_text(
            "Tugma matni saqlandi. Endi tugma havolasini (URL) kiriting (ixtiyoriy, /skip):"
        )
        return EDIT_BUTTON_URL
    except Exception as e:
        logger.error(f"edit_button_text xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def edit_button_text_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["edit_button_text"] = None
        await update.message.reply_text("Tugma matni o‘tkazib yuborildi. Endi tugma havolasini (URL) kiriting (ixtiyoriy, /skip):")
        return EDIT_BUTTON_URL
    except Exception as e:
        logger.error(f"edit_button_text_skip xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def edit_button_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        button_url = update.message.text.strip()
        game_name = context.user_data["edit_game"]
        button_text = context.user_data.get("edit_button_text")
        games_data[game_name]["button_text"] = button_text
        games_data[game_name]["button_url"] = button_url
        save_games(games_data)
        await update.message.reply_text(f"✅ Tugma maʼlumotlari yangilandi.", reply_markup=get_admin_keyboard())
        context.user_data.pop("edit_game", None)
        context.user_data.pop("edit_button_text", None)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"edit_button_url xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def edit_button_url_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        game_name = context.user_data["edit_game"]
        button_text = context.user_data.get("edit_button_text")
        games_data[game_name]["button_text"] = button_text
        games_data[game_name]["button_url"] = None
        save_games(games_data)
        await update.message.reply_text(f"✅ Tugma maʼlumotlari yangilandi (faqat matn, havolasiz).", reply_markup=get_admin_keyboard())
        context.user_data.pop("edit_game", None)
        context.user_data.pop("edit_button_text", None)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"edit_button_url_skip xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def edit_game_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        game_name = context.user_data["edit_game"]
        new_text = update.message.text
        games_data[game_name]["text"] = new_text
        save_games(games_data)
        await update.message.reply_text(f"✅ Matn yangilandi.", reply_markup=get_admin_keyboard())
        context.user_data.pop("edit_game", None)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"edit_game_text xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def edit_game_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message.photo:
            photo_id = update.message.photo[-1].file_id
            game_name = context.user_data["edit_game"]
            games_data[game_name]["photo_id"] = photo_id
            save_games(games_data)
            await update.message.reply_text(f"✅ Rasm yangilandi.", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text("Iltimos, rasm yuboring.")
            return EDIT_PHOTO
        context.user_data.pop("edit_game", None)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"edit_game_photo xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def edit_game_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update.message.document:
            file_id = update.message.document.file_id
            game_name = context.user_data["edit_game"]
            games_data[game_name]["file_id"] = file_id
            save_games(games_data)
            await update.message.reply_text(f"✅ Fayl yangilandi.", reply_markup=get_admin_keyboard())
        else:
            await update.message.reply_text("Iltimos, fayl yuboring.")
            return EDIT_FILE
        context.user_data.pop("edit_game", None)
        return ConversationHandler.END
    except Exception as e:
        logger.error(f"edit_game_file xatosi: {traceback.format_exc()}")
        await update.message.reply_text("Xatolik yuz berdi.")
        return ConversationHandler.END

async def edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tahrirlash bekor qilindi.", reply_markup=get_admin_keyboard())
    context.user_data.pop("edit_game", None)
    context.user_data.pop("edit_button_text", None)
    return ConversationHandler.END

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
    app.add_handler(CallbackQueryHandler(back_to_main, pattern="^main_menu$"))

    # Admin panel (umumiy callbacklar) – admin_add va edit_ dan tashqari
    app.add_handler(CallbackQueryHandler(
        admin_callback_handler,
        pattern="^(admin_remove_list|admin_edit_list|admin_stats|admin_close|admin_back|remove_|confirm_remove)$"
    ))
    app.add_handler(CommandHandler("admin", admin_panel))

    # ------------------- ADD GAME CONVERSATION -------------------
    add_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_add_callback, pattern="^admin_add$")],
        states={
            ADD_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_name)],
            ADD_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_text)],
            ADD_PHOTO: [
                MessageHandler(filters.PHOTO, add_game_photo),
                CommandHandler("skip", add_game_photo_skip)
            ],
            ADD_FILE: [
                MessageHandler(filters.Document.ALL, add_game_file),
                CommandHandler("skip", add_game_file_skip)
            ],
            ADD_BUTTON_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_button_text),
                CommandHandler("skip", add_game_button_text_skip)
            ],
            ADD_BUTTON_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_button_url),
                CommandHandler("skip", add_game_button_url_skip)
            ],
        },
        fallbacks=[CommandHandler("cancel", add_game_cancel)],
    )
    app.add_handler(add_conv)

    # ------------------- EDIT GAME CONVERSATIONS -------------------
    # Matn
    edit_text_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_text_callback, pattern="^edit_text$")],
        states={
            EDIT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, edit_game_text)],
        },
        fallbacks=[CommandHandler("cancel", edit_cancel)],
    )
    app.add_handler(edit_text_conv)

    # Rasm
    edit_photo_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_photo_callback, pattern="^edit_photo$")],
        states={
            EDIT_PHOTO: [MessageHandler(filters.PHOTO, edit_game_photo)],
        },
        fallbacks=[CommandHandler("cancel", edit_cancel)],
    )
    app.add_handler(edit_photo_conv)

    # Fayl
    edit_file_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_file_callback, pattern="^edit_file$")],
        states={
            EDIT_FILE: [MessageHandler(filters.Document.ALL, edit_game_file)],
        },
        fallbacks=[CommandHandler("cancel", edit_cancel)],
    )
    app.add_handler(edit_file_conv)

    # Tugma (button)
    edit_button_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(edit_button_callback, pattern="^edit_button$")],
        states={
            EDIT_BUTTON_TEXT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_button_text),
                CommandHandler("skip", edit_button_text_skip)
            ],
            EDIT_BUTTON_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_button_url),
                CommandHandler("skip", edit_button_url_skip)
            ],
        },
        fallbacks=[CommandHandler("cancel", edit_cancel)],
    )
    app.add_handler(edit_button_conv)

    logger.info("Bot ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
