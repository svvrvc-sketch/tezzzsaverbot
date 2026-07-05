import os
import json
import asyncio
import yt_dlp
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

# Bot sozlamalari
API_TOKEN = '8747746960:AAFPVKsQ4o5gfbayRUlbOOQ_rXGGoY5hMJY'
ADMIN_ID = 5111794979  # O'zingizning Telegram ID raqamingiz

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

DOWNLOAD_DIR = "downloads"
DATA_FILE = "users.json"

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

def load_data():
    if not os.path.exists(DATA_FILE):
        return {"users": {}, "banned": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"users": {}, "banned": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

LANGUAGES = {
    "uz": {
        "start": "⚡️ **Xush kelibsiz!**\nMenga ijtimoiy tarmoqlardan (Instagram, TikTok, YouTube, Pinterest) havola yuboring, men uni bir zumda yuklab beraman! 🚀\n\n*Meni guruhlarga qo'shsangiz, guruhdagi havolalarni ham avtomatik yuklab beraman!* 🔥",
        "error_domain": "⚠️ Xatolik! Havola faqat Instagram, YouTube, TikTok yoki Pinterest tarmog‘iga tegishli bo‘lishi kerak.",
        "wait": "⏳ Video tahlil qilinmoqda...",
        "yt_choose": "🎬 YouTube videosi aniqlandi! Yuklab olish formatini tanlang:",
        "success": "⚡️ @tezzzsaverbot orqali yuklab olindi!",
        "fail": "❌ Yuklashda xatolik yuz berdi. Havola yopiq, yosh cheklovi mavjud yoki bot bloklangan bo‘lishi mumkin.",
        "banned_msg": "🚫 Siz botdan foydalanishdan bloklangansiz!"
    },
    "ru": {
        "start": "⚡️ **Добро пожаловать!**\nОтправьте мне ссылку из соцсетей (Instagram, TikTok, YouTube, Pinterest), и я мгновенно скачаю её для вас! 🚀\n\n*Добавьте меня в группы, и я буду автоматически скачивать видео и там!* 🔥",
        "error_domain": "⚠️ Ошибка! Ссылка должна быть только из Instagram, YouTube, TikTok или Pinterest.",
        "wait": "⏳ Видео анализируется...",
        "yt_choose": "🎬 Обнаружено видео с YouTube! Выберите формат для скачивания:",
        "success": "⚡️ Скачано с помощью @tezzzsaverbot!",
        "fail": "❌ Произошла ошибка при скачивании. Возможно, ссылка приватная или заблокирована.",
        "banned_msg": "🚫 Вы заблокированы в этом боте!"
    },
    "en": {
        "start": "⚡️ **Welcome!**\nSend me a link from social media (Instagram, TikTok, YouTube, Pinterest), and I will download it instantly! 🚀\n\n*Add me to groups, and I will automatically download videos there too!* 🔥",
        "error_domain": "⚠️ Error! The link must be only from Instagram, YouTube, TikTok, or Pinterest.",
        "wait": "⏳ Analyzing video...",
        "yt_choose": "🎬 YouTube video detected! Choose download format:",
        "success": "⚡️ Downloaded via @tezzzsaverbot!",
        "fail": "❌ Error occurred during download. The link might be private or restricted.",
        "banned_msg": "🚫 You are banned from using this bot!"
    }
}

def check_ban(func):
    async def wrapper(message_or_call, *args, **kwargs):
        user_id = str(message_or_call.from_user.id)
        data = load_data()
        if user_id in data.get("banned", []):
            if isinstance(message_or_call, types.Message):
                await message_or_call.answer("🚫 Access Denied / Bloklangansiz")
            return
        return await func(message_or_call, *args, **kwargs)
    return wrapper

@dp.message(CommandStart())
@check_ban
async def cmd_start(message: types.Message):
    user_id = str(message.from_user.id)
    data = load_data()
    
    if user_id not in data["users"]:
        data["users"][user_id] = {"lang": "uz", "platform": "unknown"}
        save_data(data)
        
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
        types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
        types.InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")
    )
    if message.from_user.id == ADMIN_ID:
        builder.row(types.InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel"))
        
    await message.answer("🌐 Choose language / Tilni tanlang / Выберите язык:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    user_id = str(callback.from_user.id)
    data = load_data()
    data["users"][user_id]["lang"] = lang
    save_data(data)
    await callback.message.edit_text(LANGUAGES[lang]["start"], parse_mode="Markdown")

@dp.callback_query(F.data == "admin_panel")
async def open_admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    data = load_data()
    admin_text = (
        "📊 **Kengaytirilgan Admin Panel**\n\n"
        f"👥 Foydalanuvchilar: **{len(data['users'])} ta**\n"
        f"🚫 Bloklanganlar: **{len(data['banned'])} ta**\n\n"
        "📢 **Rassilka:** `/send [matn]`\n"
        "🚫 **Bloklash:** `/ban [ID]`\n"
        "🔓 **Blokdan ochish:** `/unban [ID]`"
    )
    await callback.message.edit_text(admin_text, parse_mode="Markdown")

@dp.message(Command("send"))
async def admin_broadcast(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    text = message.text.replace("/send", "").strip()
    if not text: return await message.answer("⚠️ Matn yozing.")
    data = load_data()
    status_msg = await message.answer("📢 Rassilka yuborilmoqda...")
    success, failed = 0, 0
    for uid in data["users"].keys():
        try:
            await bot.send_message(chat_id=int(uid), text=text)
            success += 1
            await asyncio.sleep(0.05)
        except: failed += 1
    await status_msg.edit_text(f"✅ Yetkazildi: {success}\n❌ Bloklaganlar: {failed}")

@dp.message(Command("ban"))
async def ban_user(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    uid = message.text.replace("/ban", "").strip()
    if not uid: return await message.answer("⚠️ ID ko'rsating.")
    data = load_data()
    if uid not in data["banned"]:
        data["banned"].append(uid)
        save_data(data)
        await message.answer(f"🚫 Foydalanuvchi {uid} bloklandi.")

@dp.message(Command("unban"))
async def unban_user(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    uid = message.text.replace("/unban", "").strip()
    if not uid: return await message.answer("⚠️ ID ko'rsating.")
    data = load_data()
    if uid in data["banned"]:
        data["banned"].remove(uid)
        save_data(data)
        await message.answer(f"🔓 Foydalanuvchi {uid} blokdan ochildi.")

@dp.message(F.text)
@check_ban
async def handle_messages(message: types.Message):
    user_id = str(message.from_user.id)
    data = load_data()
    
    if user_id not in data["users"]:
        data["users"][user_id] = {"lang": "uz", "platform": "group_user" if message.chat.type != "private" else "private"}
        save_data(data)
        
    lang = data["users"].get(user_id, {}).get("lang", "uz")
    urls = re.findall(r'(https?://[^\s]+)', message.text)
    if not urls: return

    url = urls[0]
    allowed = ["instagram.com", "tiktok.com", "youtube.com", "youtu.be", "pinterest.com", "pin.it"]
    if not any(d in url for d in allowed):
        if message.chat.type == "private":
            await message.answer(LANGUAGES[lang]["error_domain"])
        return
        
    if ("youtube.com" in url or "youtu.be" in url) and message.chat.type == "private":
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(text="🎬 720p (HD)", callback_data=f"yt_720p|{url[:40]}"),
            types.InlineKeyboardButton(text="📺 360p (SD)", callback_data=f"yt_360p|{url[:40]}")
        )
        builder.row(types.InlineKeyboardButton(text="🎵 Faqat MP3", callback_data=f"yt_mp3|{url[:40]}"))
        data["users"][user_id]["last_url"] = url
        save_data(data)
        await message.answer(LANGUAGES[lang]["yt_choose"], reply_markup=builder.as_markup())
    else:
        status_msg = await message.reply(LANGUAGES[lang]["wait"])
        await process_download(status_msg, url, lang, 'bestvideo[height<=480]+bestaudio/best' if "youtube" in url else 'bestvideo+bestaudio/best')

@dp.callback_query(F.data.startswith("yt_"))
async def format_callback(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    data = load_data()
    lang = data["users"].get(user_id, {}).get("lang", "uz")
    url = data["users"].get(user_id, {}).get("last_url", "")
    
    if not url: return await callback.answer("Xatolik.")
    fmt = callback.data.split("|")[0]
    
    ydl_format = 'bestvideo[height<=720]+bestaudio/best'
    if fmt == "yt_360p": ydl_format = 'bestvideo[height<=360]+bestaudio/best'
    elif fmt == "yt_mp3": ydl_format = 'bestaudio/best'
    
    await callback.message.edit_text(LANGUAGES[lang]["wait"])
    await process_download(callback.message, url, lang, ydl_format, is_audio=(fmt=="yt_mp3"))

async def process_download(msg, url, lang, ydl_format, is_audio=False):
    # Server blokirovkalarini aylanib o'tish uchun maxsus yuklagich sozlamalari
    ydl_opts = {
        'format': ydl_format,
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'no_warnings': True,
        'quiet': True,
        # Quyidagi qatorlar Instagram va YouTube bloklarini chetlab o'tishga yordam beradi:
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        },
        'geo_bypass': True,  # Geografik cheklovlarni chetlab o'tish
        'extractor_args': {
            'youtube': {'player_client': ['android', 'web']} # YouTube bot-tizimini aldash
        }
    }
    
    if is_audio:
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filename = ydl.prepare_filename(info)
            if is_audio:
                filename = os.path.splitext(filename)[0] + ".mp3"
            
            if not os.path.exists(filename) and not is_audio:
                base = os.path.splitext(filename)[0]
                for ext in ['mp4', 'mkv', 'webm', 'mov']:
                    if os.path.exists(f"{base}.{ext}"): filename = f"{base}.{ext}"; break

        file_input = types.FSInputFile(filename)
        
        if is_audio:
            await bot.send_audio(chat_id=msg.chat.id, audio=file_input, caption=LANGUAGES[lang]["success"])
        else:
            await bot.send_video(chat_id=msg.chat.id, video=file_input, caption=LANGUAGES[lang]["success"])
            
        await msg.delete()
        if os.path.exists(filename): os.remove(filename)
    except Exception as e:
        print(f"Xatolik tafsiloti: {e}")
        await msg.edit_text(LANGUAGES[lang]["fail"])

@dp.inline_query()
async def inline_download(inline_query: types.InlineQuery):
    url = inline_query.query.strip()
    if not url.startswith("http"): return
    results = [
        InlineQueryResultArticle(
            id="1",
            title="📥 Videoni bu yerga yuklash",
            description=f"Havolani yuborish: {url}",
            input_message_content=InputTextMessageContent(message_text=url)
        )
    ]
    await inline_query.answer(results, cache_time=1)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())