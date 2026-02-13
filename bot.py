import json
import logging
import os
from pathlib import Path
from typing import Dict

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

# ------------------- KONVERSATSIYA HOLATLARI -------------------
ADD_NAME, ADD_TEXT, ADD_PHOTO, ADD_FILE, ADD_BUTTON_TEXT, ADD_BUTTON_URL = range(6)
EDIT_SELECT, EDIT_ACTION, EDIT_TEXT, EDIT_PHOTO, EDIT_FILE, EDIT_BUTTON_TEXT, EDIT_BUTTON_URL = range(6, 13)

# ------------------- FOYDALANUVCHI HANDLERLARI -------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "🎰 *WinWin Bukmekeriga xush kelibsiz!*\n\n"
        "🎯 Ishonchli o‘yinlar tahlili\n"
        "📊 Slot o‘yinlarini analiz qilish\n"
        "💡 Qayerda, qachon va qanday g‘alaba qilish sirlari\n\n"
        "👇 Boshlash uchun quyidagi tugmani bosing:"
    )
    keyboard = [[InlineKeyboardButton("✨ Shaffof tugma", callback_data="show_games")]]
    await update.message.reply_text(
        welcome_text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not games_data:
        await query.edit_message_text("Hozircha hech qanday o‘yin mavjud emas.")
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

    # Statistika
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

# ------------------- ADMIN PANEL (umumiy callbacklar) -------------------
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Siz admin emassiz.")
        return
    await update.message.reply_text("👨‍💻 Admin paneli:", reply_markup=get_admin_keyboard())

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin panelidagi barcha callbacklarni boshqaradi (add/edit dan tashqari)."""
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

    elif data.startswith("edit_"):
        game_name = data.replace("edit_", "")
        context.user_data["edit_game"] = game_name
        keyboard = [
            [InlineKeyboardButton("✏️ Matn", callback_data="edit_text")],
            [InlineKeyboardButton("🖼 Rasm", callback_data="edit_photo")],
            [InlineKeyboardButton("📁 Fayl (APK)", callback_data="edit_file")],
            [InlineKeyboardButton("🔗 Tugma", callback_data="edit_button")],
            [InlineKeyboardButton("◀️ Back", callback_data="admin_back")]
        ]
        await query.edit_message_text(
            f"'{game_name}' – nimani tahrirlaysiz?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    return

# ------------------- ADD GAME KONVERSATSIYASI -------------------
async def admin_add_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not is_admin(query.from_user.id):
        await query.edit_message_text("Siz admin emassiz.")
        return ConversationHandler.END

    context.user_data["add_game"] = {}
    await query.edit_message_text("Yangi o‘yin nomini kiriting:")
    return ADD_NAME

async def add_game_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if name in games_data:
        await update.message.reply_text("Bu nom allaqachon mavjud. Boshqa nom kiriting:")
        return ADD_NAME
    context.user_data["add_game"]["name"] = name
    await update.message.reply_text("Endi o‘yin matnini kiriting (HTML teglar bilan):")
    return ADD_TEXT

async def add_game_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    context.user_data["add_game"]["text"] = text
    await update.message.reply_text(
        "Matn saqlandi. Endi rasm yuboring (ixtiyoriy) yoki /skip ni bosing."
    )
    return ADD_PHOTO

async def add_game_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo_id = update.message.photo[-1].file_id
        context.user_data["add_game"]["photo_id"] = photo_id
        await update.message.reply_text("Rasm saqlandi. Endi fayl (APK) yuboring (ixtiyoriy) yoki /skip ni bosing.")
    else:
        await update.message.reply_text("Iltimos, rasm yuboring yoki /skip ni bosing.")
        return ADD_PHOTO
    return ADD_FILE

async def add_game_photo_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_game"]["photo_id"] = None
    await update.message.reply_text("Rasm o‘tkazib yuborildi. Endi fayl (APK) yuboring (ixtiyoriy) yoki /skip ni bosing.")
    return ADD_FILE

async def add_game_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def add_game_file_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_game"]["file_id"] = None
    await update.message.reply_text(
        "Fayl o‘tkazib yuborildi. Endi tugma matnini kiriting (ixtiyoriy) yoki /skip ni bosing.\n"
        "Masalan: '🎮 O‘yin sayti'"
    )
    return ADD_BUTTON_TEXT

async def add_game_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    button_text = update.message.text.strip()
    context.user_data["add_game"]["button_text"] = button_text
    await update.message.reply_text(
        "Tugma matni saqlandi. Endi tugma havolasini (URL) kiriting (ixtiyoriy) yoki /skip ni bosing.\n"
        "Masalan: https://example.com"
    )
    return ADD_BUTTON_URL

async def add_game_button_text_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["add_game"]["button_text"] = None
    await update.message.reply_text(
        "Tugma matni o‘tkazib yuborildi. Endi tugma havolasini (URL) kiriting (ixtiyoriy) yoki /skip ni bosing."
    )
    return ADD_BUTTON_URL

async def add_game_button_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def add_game_button_url_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def add_game_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Qo‘shish bekor qilindi.", reply_markup=get_admin_keyboard())
    return ConversationHandler.END

# ------------------- EDIT GAME KONVERSATSIYALARI -------------------
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
    button_text = update.message.text.strip()
    context.user_data["edit_button_text"] = button_text
    await update.message.reply_text(
        "Tugma matni saqlandi. Endi tugma havolasini (URL) kiriting (ixtiyoriy, /skip):"
    )
    return EDIT_BUTTON_URL

async def edit_button_text_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["edit_button_text"] = None
    await update.message.reply_text("Tugma matni o‘tkazib yuborildi. Endi tugma havolasini (URL) kiriting (ixtiyoriy, /skip):")
    return EDIT_BUTTON_URL

async def edit_button_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def edit_button_url_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_name = context.user_data["edit_game"]
    button_text = context.user_data.get("edit_button_text")
    games_data[game_name]["button_text"] = button_text
    games_data[game_name]["button_url"] = None
    save_games(games_data)
    await update.message.reply_text(f"✅ Tugma maʼlumotlari yangilandi (faqat matn, havolasiz).", reply_markup=get_admin_keyboard())
    context.user_data.pop("edit_game", None)
    context.user_data.pop("edit_button_text", None)
    return ConversationHandler.END

async def edit_game_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    game_name = context.user_data["edit_game"]
    new_text = update.message.text
    games_data[game_name]["text"] = new_text
    save_games(games_data)
    await update.message.reply_text(f"✅ Matn yangilandi.", reply_markup=get_admin_keyboard())
    context.user_data.pop("edit_game", None)
    return ConversationHandler.END

async def edit_game_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def edit_game_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def edit_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Tahrirlash bekor qilindi.", reply_markup=get_admin_keyboard())
    context.user_data.pop("edit_game", None)
    context.user_data.pop("edit_button_text", None)
    return ConversationHandler.END

# ------------------- ASOSIY -------------------
def main():
    app = Application.builder().token(TOKEN).build()

    # Oddiy handlerlar
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(show_games, pattern="^show_games$"))
    app.add_handler(CallbackQueryHandler(game_callback, pattern="^game_"))
    
    # Admin panel callbacklari (add/edit dan tashqari)
    app.add_handler(CallbackQueryHandler(
        admin_callback_handler,
        pattern="^(admin_remove_list|admin_edit_list|admin_stats|admin_close|admin_back|remove_|edit_|confirm_remove)$"
    ))

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
