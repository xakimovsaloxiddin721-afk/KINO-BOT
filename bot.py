import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

from config import BOT_TOKEN, ADMIN_IDS
import database as db

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Majburiy obuna kanali
CHANNEL_USERNAME = "@top_uz_kino"
CHANNEL_URL = "https://t.me/top_uz_kino"

# Admin "kino qo'shish" jarayoni
pending_add: dict[int, str] = {}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------- MAJBURIY OBUNA ----------

async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(
            chat_id=CHANNEL_USERNAME,
            user_id=user_id
        )

        return member.status in ("member", "administrator", "creator") or (
            member.status == "restricted" and member.is_member
        )

    except Exception as e:
        logging.error(f"Obuna tekshirish xatosi: {e}")
        return False


def subscription_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📢 Kanalga obuna bo‘lish",
                    url=CHANNEL_URL
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ Obunani tekshirish",
                    callback_data="check_subscription"
                )
            ]
        ]
    )


async def require_subscription(message: Message) -> bool:
    # Adminlar uchun majburiy obuna shart emas
    if is_admin(message.from_user.id):
        return True

    subscribed = await is_subscribed(message.from_user.id)

    if not subscribed:
        await message.answer(
            "🔒 <b>Botdan foydalanish uchun kanalimizga obuna bo‘ling!</b>\n\n"
            "1️⃣ Quyidagi tugma orqali kanalga kiring\n"
            "2️⃣ Kanalga obuna bo‘ling\n"
            "3️⃣ <b>✅ Obunani tekshirish</b> tugmasini bosing",
            parse_mode="HTML",
            reply_markup=subscription_keyboard()
        )
        return False

    return True


@dp.callback_query(F.data == "check_subscription")
async def check_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id

    if await is_subscribed(user_id):
        await callback.message.edit_text(
            "✅ <b>Obuna tasdiqlandi!</b>\n\n"
            "🎬 Endi kino kodini yuborishingiz mumkin.",
            parse_mode="HTML"
        )
        await callback.answer("✅ Obuna tasdiqlandi!")
    else:
        await callback.answer(
            "❌ Siz hali kanalga obuna bo‘lmagansiz!",
            show_alert=True
        )


# ---------- FOYDALANUVCHI QISMI ----------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await db.add_user(message.from_user.id)

    if not await require_subscription(message):
        return

    await message.answer(
        "Salom! 🎬\n\n"
        "Kino kodini yuboring, men sizga kinoni jo‘nataman.\n"
        "Masalan: <code>101</code>",
        parse_mode="HTML",
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    if not await require_subscription(message):
        return

    text = (
        "ℹ️ <b>Yordam</b>\n\n"
        "Kino kodini raqam shaklida yuboring (masalan: 101), "
        "bot sizga videoni yuboradi.\n\n"
        "Agar kino topilmasa, kod noto‘g‘ri yoki hali qo‘shilmagan bo‘lishi mumkin."
    )

    if is_admin(message.from_user.id):
        text += (
            "\n\n<b>Admin buyruqlari:</b>\n"
            "/add &lt;kod&gt; — video reply qilib kino qo‘shish\n"
            "/delete &lt;kod&gt; — kinoni o‘chirish\n"
            "/stats — statistika\n"
            "/top — eng ko‘p ko‘rilgan kinolar"
        )

    await message.answer(text, parse_mode="HTML")


@dp.message(F.text.regexp(r"^\d+$"))
async def send_movie_by_code(message: Message):

    if not await require_subscription(message):
        return

    code = message.text.strip()
    movie = await db.get_movie(code)

    if movie:
        _, file_id, title, views = movie
        caption = f"🎬 {title}" if title else f"Kod: {code}"
        await message.answer_video(file_id, caption=caption)
    else:
        await message.answer(
            "❌ Bunday kodli kino topilmadi. Kodni tekshirib qayta yuboring."
        )


# ---------- ADMIN QISMI ----------

@dp.message(Command("add"))
async def cmd_add(message: Message):

    if not is_admin(message.from_user.id):
        return

    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        await message.answer(
            "Foydalanish: video xabarga reply qilib\n"
            "<code>/add 101</code>",
            parse_mode="HTML",
        )
        return

    code = parts[1].strip()

    if message.reply_to_message and message.reply_to_message.video:

        file_id = message.reply_to_message.video.file_id
        title = message.reply_to_message.caption or ""

        ok = await db.add_movie(
            code,
            file_id,
            title,
            message.from_user.id
        )

        if ok:
            await message.answer(
                f"✅ Kino qo‘shildi. Kod: <code>{code}</code>",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"⚠️ Bu kod band: <code>{code}</code>. "
                f"Boshqa kod tanlang.",
                parse_mode="HTML"
            )

    else:
        pending_add[message.from_user.id] = code

        await message.answer(
            f"📹 Endi <code>{code}</code> kodi uchun "
            f"videoni shu yerga yuboring.",
            parse_mode="HTML",
        )


@dp.message(F.video)
async def handle_video_upload(message: Message):

    admin_id = message.from_user.id

    if is_admin(admin_id) and admin_id in pending_add:

        code = pending_add.pop(admin_id)
        file_id = message.video.file_id
        title = message.caption or ""

        ok = await db.add_movie(
            code,
            file_id,
            title,
            admin_id
        )

        if ok:
            await message.answer(
                f"✅ Kino qo‘shildi. Kod: <code>{code}</code>",
                parse_mode="HTML"
            )
        else:
            await message.answer(
                f"⚠️ Bu kod band: <code>{code}</code>",
                parse_mode="HTML"
            )


@dp.message(Command("delete"))
async def cmd_delete(message: Message):

    if not is_admin(message.from_user.id):
        return

    parts = message.text.split(maxsplit=1)

    if len(parts) < 2:
        await message.answer(
            "Foydalanish: <code>/delete 101</code>",
            parse_mode="HTML"
        )
        return

    code = parts[1].strip()
    ok = await db.delete_movie(code)

    if ok:
        await message.answer(
            f"🗑 Kod <code>{code}</code> o‘chirildi.",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"Bunday kod topilmadi: <code>{code}</code>",
            parse_mode="HTML"
        )


@dp.message(Command("stats"))
async def cmd_stats(message: Message):

    if not is_admin(message.from_user.id):
        return

    movies = await db.movie_count()
    users = await db.user_count()

    await message.answer(
        f"📊 <b>Statistika</b>\n\n"
        f"🎬 Kinolar soni: {movies}\n"
        f"👤 Foydalanuvchilar: {users}",
        parse_mode="HTML"
    )


@dp.message(Command("top"))
async def cmd_top(message: Message):

    if not is_admin(message.from_user.id):
        return

    rows = await db.top_movies(10)

    if not rows:
        await message.answer("Hali kinolar yo‘q.")
        return

    text = "🏆 <b>Eng ko‘p ko‘rilgan kinolar</b>\n\n"

    for i, (code, title, views) in enumerate(rows, 1):
        name = title or f"Kod {code}"
        text += f"{i}. {name} (kod: {code}) — {views} marta\n"

    await message.answer(
        text,
        parse_mode="HTML"
    )


# ---------- RENDER WEB SERVER ----------

async def start_fake_webserver():
    """Render Web Service uchun HTTP port."""

    from aiohttp import web

    port = int(os.getenv("PORT", 0))

    if not port:
        return

    async def health(request):
        return web.Response(text="Bot ishlayapti ✅")

    app = web.Application()
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        port
    )

    await site.start()


# ---------- START ----------

async def main():

    await db.init_db()

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await start_fake_webserver()

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
        
