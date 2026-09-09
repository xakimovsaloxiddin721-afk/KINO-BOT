import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from config import BOT_TOKEN, ADMIN_IDS
import database as db

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Admin "kino qo'shish" jarayonini vaqtinchalik eslab turish uchun
# {admin_id: "kutilayotgan_kod"}
pending_add: dict[int, str] = {}


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


# ---------- FOYDALANUVCHI QISMI ----------

@dp.message(CommandStart())
async def cmd_start(message: Message):
    await db.add_user(message.from_user.id)
    await message.answer(
        "Salom! 🎬\n\n"
        "Kino kodini yuboring, men sizga kinoni jo'nataman.\n"
        "Masalan: <code>101</code>",
        parse_mode="HTML",
    )


@dp.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "ℹ️ <b>Yordam</b>\n\n"
        "Kino kodini raqam shaklida yuboring (masalan: 101), "
        "bot sizga videoni yuboradi.\n\n"
        "Agar kino topilmasa, kod noto'g'ri yoki hali qo'shilmagan bo'lishi mumkin."
    )
    if is_admin(message.from_user.id):
        text += (
            "\n\n<b>Admin buyruqlari:</b>\n"
            "/add &lt;kod&gt; — video reply qilib kino qo'shish\n"
            "/delete &lt;kod&gt; — kinoni o'chirish\n"
            "/stats — statistika\n"
            "/top — eng ko'p ko'rilgan kinolar"
        )
    await message.answer(text, parse_mode="HTML")


@dp.message(F.text.regexp(r"^\d+$"))
async def send_movie_by_code(message: Message):
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
            "Foydalanish: video xabarga reply qilib\n<code>/add 101</code>",
            parse_mode="HTML",
        )
        return
    code = parts[1].strip()

    if message.reply_to_message and message.reply_to_message.video:
        file_id = message.reply_to_message.video.file_id
        title = message.reply_to_message.caption or ""
        ok = await db.add_movie(code, file_id, title, message.from_user.id)
        if ok:
            await message.answer(f"✅ Kino qo'shildi. Kod: <code>{code}</code>", parse_mode="HTML")
        else:
            await message.answer(f"⚠️ Bu kod band: <code>{code}</code>. Boshqa kod tanlang.", parse_mode="HTML")
    else:
        # Reply qilinmagan bo'lsa — videoni keyin yuborishini kutamiz
        pending_add[message.from_user.id] = code
        await message.answer(
            f"📹 Endi <code>{code}</code> kodi uchun videoni shu yerga yuboring.",
            parse_mode="HTML",
        )


@dp.message(F.video)
async def handle_video_upload(message: Message):
    admin_id = message.from_user.id
    if is_admin(admin_id) and admin_id in pending_add:
        code = pending_add.pop(admin_id)
        file_id = message.video.file_id
        title = message.caption or ""
        ok = await db.add_movie(code, file_id, title, admin_id)
        if ok:
            await message.answer(f"✅ Kino qo'shildi. Kod: <code>{code}</code>", parse_mode="HTML")
        else:
            await message.answer(f"⚠️ Bu kod band: <code>{code}</code>", parse_mode="HTML")


@dp.message(Command("delete"))
async def cmd_delete(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Foydalanish: <code>/delete 101</code>", parse_mode="HTML")
        return
    code = parts[1].strip()
    ok = await db.delete_movie(code)
    if ok:
        await message.answer(f"🗑 Kod <code>{code}</code> o'chirildi.", parse_mode="HTML")
    else:
        await message.answer(f"Bunday kod topilmadi: <code>{code}</code>", parse_mode="HTML")


@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        return
    movies = await db.movie_count()
    users = await db.user_count()
    await message.answer(
        f"📊 <b>Statistika</b>\n\n🎬 Kinolar soni: {movies}\n👤 Foydalanuvchilar: {users}",
        parse_mode="HTML",
    )


@dp.message(Command("top"))
async def cmd_top(message: Message):
    if not is_admin(message.from_user.id):
        return
    rows = await db.top_movies(10)
    if not rows:
        await message.answer("Hali kinolar yo'q.")
        return
    text = "🏆 <b>Eng ko'p ko'rilgan kinolar</b>\n\n"
    for i, (code, title, views) in enumerate(rows, 1):
        name = title or f"Kod {code}"
        text += f"{i}. {name} (kod: {code}) — {views} marta\n"
    await message.answer(text, parse_mode="HTML")


async def start_fake_webserver():
    """Render 'Web Service' turi HTTP portini talab qiladi.
    Shu sababli bot bilan bir qatorda mayda web-server ishga tushiramiz.
    Railway yoki VPS'da bu shart emas, lekin zarar ham qilmaydi."""
    import os
    from aiohttp import web

    port = int(os.getenv("PORT", 0))
    if not port:
        return  # PORT berilmagan bo'lsa (masalan Railway worker), kerak emas

    async def health(request):
        return web.Response(text="Bot ishlayapti ✅")

    app = web.Application()
    app.router.add_get("/", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()


async def main():
    await db.init_db()
    await bot.delete_webhook(drop_pending_updates=True)
    await start_fake_webserver()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
