"""
ربات تلگرامی دانلود ریلز و پست اینستاگرام
نیازمندی‌ها: python-telegram-bot, yt-dlp
"""

import os
import re
import logging
import asyncio
import uuid

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.constants import ChatAction, ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)

import yt_dlp

# ---------------------------------------------------------------------------
# تنظیمات
# ---------------------------------------------------------------------------

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8438757317:AAGnhpSuv8ud-TO-WxbA3EcuVg8HCO86e9Q")
DOWNLOAD_DIR = "downloads"
MAX_TELEGRAM_SIZE_MB = 50  # محدودیت پیش‌فرض ارسال فایل توسط ربات‌ها

INSTAGRAM_URL_PATTERN = re.compile(
    r"(https?://(?:www\.)?instagram\.com/(?:reel|reels|p|tv)/[A-Za-z0-9_\-]+/?\S*)"
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

os.makedirs(DOWNLOAD_DIR, exist_ok=True)


# ---------------------------------------------------------------------------
# متن‌های رابط کاربری
# ---------------------------------------------------------------------------

WELCOME_TEXT = (
    "👋 <b>سلام! به ربات دانلود اینستاگرام خوش اومدی</b>\n\n"
    "🎬 فقط کافیه لینک یه <b>ریلز</b> یا <b>پست</b> اینستاگرام رو برام بفرستی، "
    "منم اونو دانلود می‌کنم و همینجا برات می‌فرستم.\n\n"
    "✨ <b>امکانات:</b>\n"
    "• دانلود ریلز، پست و ویدیو IGTV\n"
    "• کیفیت اصلی بدون واترمارک\n"
    "• سرعت بالا ⚡\n\n"
    "🔗 یه لینک بفرست و شروع کن!"
)

HELP_TEXT = (
    "📖 <b>راهنمای استفاده</b>\n\n"
    "۱. وارد اینستاگرام شو و روی پست یا ریلز موردنظر بزن «کپی لینک»\n"
    "۲. لینک رو همینجا برام بفرست\n"
    "۳. چند ثانیه صبر کن تا فایل رو برات بفرستم ✅\n\n"
    "⚠️ فقط پست‌های <b>پابلیک (عمومی)</b> قابل دانلود هستن."
)


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📖 راهنما", callback_data="help"),
                InlineKeyboardButton("ℹ️ درباره ربات", callback_data="about"),
            ]
        ]
    )


def result_keyboard(original_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔗 مشاهده در اینستاگرام", url=original_link)],
            [InlineKeyboardButton("🔄 دانلود لینک دیگه", callback_data="new_download")],
        ]
    )


# ---------------------------------------------------------------------------
# دستورات
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        WELCOME_TEXT,
        parse_mode=ParseMode.HTML,
        reply_markup=main_menu_keyboard(),
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help":
        await query.message.reply_text(HELP_TEXT, parse_mode=ParseMode.HTML)
    elif query.data == "about":
        await query.message.reply_text(
            "🤖 این ربات با پایتون و کتابخانه‌های\n"
            "<code>python-telegram-bot</code> و <code>yt-dlp</code> ساخته شده.",
            parse_mode=ParseMode.HTML,
        )
    elif query.data == "new_download":
        await query.message.reply_text("🔗 لینک جدید رو بفرست تا دانلودش کنم.")


# ---------------------------------------------------------------------------
# دانلود از اینستاگرام
# ---------------------------------------------------------------------------

def download_instagram_media(url: str, out_dir: str) -> dict:
    """با yt-dlp رسانه رو دانلود می‌کند و مسیر فایل و اطلاعات را برمی‌گرداند."""
    file_id = str(uuid.uuid4())
    outtmpl = os.path.join(out_dir, f"{file_id}.%(ext)s")

    ydl_opts = {
        "outtmpl": outtmpl,
        "format": "mp4/best",
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        # اگر پست خصوصی/محدود بود و کوکی داشتی، این خط رو فعال کن:
        # "cookiefile": "cookies.txt",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filepath = ydl.prepare_filename(info)

    return {
        "filepath": filepath,
        "title": info.get("title") or "Instagram media",
        "is_video": os.path.splitext(filepath)[1].lower() in (".mp4", ".mov", ".mkv"),
    }


# ---------------------------------------------------------------------------
# هندلر اصلی پیام‌ها
# ---------------------------------------------------------------------------

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    match = INSTAGRAM_URL_PATTERN.search(text)

    if not match:
        await update.message.reply_text(
            "❌ لینک معتبر اینستاگرام پیدا نکردم.\n"
            "لطفاً یه لینک ریلز یا پست اینستاگرام بفرست، مثل:\n"
            "<code>https://www.instagram.com/reel/xxxxxxx/</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    url = match.group(1)
    status_msg = await update.message.reply_text("⏳ در حال دریافت اطلاعات لینک...")

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_VIDEO
    )

    try:
        await status_msg.edit_text("📥 در حال دانلود، چند لحظه صبر کن...")

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, download_instagram_media, url, DOWNLOAD_DIR
        )

        filepath = result["filepath"]
        size_mb = os.path.getsize(filepath) / (1024 * 1024)

        if size_mb > MAX_TELEGRAM_SIZE_MB:
            await status_msg.edit_text(
                f"⚠️ حجم فایل ({size_mb:.1f} مگابایت) بیشتر از محدودیت ارسال "
                f"({MAX_TELEGRAM_SIZE_MB} مگابایت) است و قابل ارسال نیست."
            )
            os.remove(filepath)
            return

        await status_msg.edit_text("📤 در حال ارسال فایل...")

        caption = f"✅ <b>{result['title']}</b>\n\n🤖 دانلود شده توسط ربات"

        with open(filepath, "rb") as f:
            if result["is_video"]:
                await update.message.reply_video(
                    video=f,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=result_keyboard(url),
                    supports_streaming=True,
                )
            else:
                await update.message.reply_photo(
                    photo=f,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    reply_markup=result_keyboard(url),
                )

        await status_msg.delete()
        os.remove(filepath)

    except Exception as exc:  # noqa: BLE001
        logger.exception("خطا در دانلود لینک: %s", url)
        await status_msg.edit_text(
            "❌ متأسفانه دانلود این لینک با خطا مواجه شد.\n"
            "ممکنه پست خصوصی باشه یا لینک نامعتبر باشه.\n\n"
            f"<i>جزئیات فنی: {str(exc)[:200]}</i>",
            parse_mode=ParseMode.HTML,
        )


# ---------------------------------------------------------------------------
# اجرای ربات
# ---------------------------------------------------------------------------

def main():
    if BOT_TOKEN == "PUT-YOUR-TELEGRAM-BOT-TOKEN-HERE":
        raise SystemExit(
            "⚠️ توکن ربات را تنظیم نکرده‌ای. متغیر محیطی BOT_TOKEN را ست کن "
            "یا مستقیم داخل کد جایگزین کن."
        )

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("ربات در حال اجراست...")
    app.run_polling()


if __name__ == "__main__":
    main()