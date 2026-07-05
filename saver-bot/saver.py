import os
import json
import asyncio
import yt_dlp
import re
import inspect
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiohttp import web

# --- BOT SOZLAMALARI ---
API_TOKEN = '8747746960:AAFPVKsQ4o5gfbayRUlbOOQ_rXGGoY5hMJY'
ADMIN_ID = 5111794979  

USE_MANDATORY_SUB = True     
REQUIRED_CHANNEL = "@openwebacademy" 

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

DOWNLOAD_DIR = "downloads"
DATA_FILE = "users.json"
COOKIES_FILE = "cookies.txt"

if not os.path.exists(DOWNLOAD_DIR):
    os.makedirs(DOWNLOAD_DIR)

class AdminStates(StatesGroup):
    waiting_for_broadcast = State()
    waiting_for_ban_id = State()

def load_data():
    if not os.path.exists(DATA_FILE): return {"users": {}, "banned": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f: return json.load(f)
    except: return {"users": {}, "banned": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f: json.dump(data, f, ensure_ascii=False, indent=4)

def init_user_data(data, user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    if user_id not in data["users"]:
        data["users"][user_id] = {"lang": "uz", "downloads_today": 0, "last_download_date": today, "stats": {"instagram": 0, "tiktok": 0, "youtube": 0, "pinterest": 0}}
    return data

LANGUAGES = {
    "uz": {
        "start": "⚡️ **Xush kelibsiz!**\nMenga ijtimoiy tarmoqlardan (Instagram, TikTok, YouTube) havola yuboring, yuklab beraman! 🚀",
        "wait": "⏳ Musiqa qidirilmoqda va tahlil qilinmoqda (Shazam)...",
        "choose_format": "🎬 Havola aniqlandi! Tanlang:",
        "success": "⚡️ @tezzzsaverbot orqali yuklab olindi!",
        "fail": "❌ Xatolik yuz berdi. Yuklab bo'lmadi.",
        "sub_required": "⚠️ **Botdan foydalanish uchun kanalimizga a'zo bo'lishingiz shart!**",
        "check_sub_btn": "✅ A'zo bo'ldim / Tekshirish"
    },
    "ru": {
        "start": "⚡️ **Добро пожаловать!**\nОтправьте мне ссылку, и я скачаю её! 🚀",
        "wait": "⏳ Поиск и анализ музыки (Shazam)...",
        "choose_format": "🎬 Ссылка обнаружена! Выберите:",
        "success": "⚡️ Скачано с помощью @tezzzsaverbot!",
        "fail": "❌ Произошла ошибка при скачивании.",
        "sub_required": "⚠️ **Для использования бота вы должны подписаться на канал!**",
        "check_sub_btn": "✅ Я подписался"
    },
    "en": {
        "start": "⚡️ **Welcome!**\nSend me a link, and I will download it! 🚀",
        "wait": "⏳ Searching and analyzing music (Shazam)...",
        "choose_format": "🎬 Link detected! Choose:",
        "success": "⚡️ Downloaded via @tezzzsaverbot!",
        "fail": "❌ Error occurred during download.",
        "sub_required": "⚠️ **To use the bot, you must subscribe to our channel!**",
        "check_sub_btn": "✅ I subscribed"
    }
}

async def is_subscribed(user_id):
    if not USE_MANDATORY_SUB: return True
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=int(user_id))
        return member.status in ["member", "administrator", "creator"]
    except: return True

def check_ban(func):
    async def wrapper(message_or_call, *args, **kwargs):
        user_id = str(message_or_call.from_user.id)
        data = load_data()
        if user_id in data.get("banned", []):
            if isinstance(message_or_call, types.Message):
                await message_or_call.answer("🚫 Botdan foydalanish huquqingiz cheklangan.")
            return
        sig = inspect.signature(func)
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return await func(message_or_call, *args, **filtered_kwargs)
    return wrapper

@dp.message(CommandStart())
@check_ban
async def cmd_start(message: types.Message):
    user_id = str(message.from_user.id)
    data = load_data(); data = init_user_data(data, user_id); save_data(data)
    
    if not await is_subscribed(user_id):
        sub_builder = InlineKeyboardBuilder()
        sub_builder.row(types.InlineKeyboardButton(text="📢 Kanalga o'tish", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@','') }"))
        sub_builder.row(types.InlineKeyboardButton(text=LANGUAGES["uz"]["check_sub_btn"], callback_data="check_subscription"))
        await message.answer(LANGUAGES["uz"]["sub_required"], reply_markup=sub_builder.as_markup(), parse_mode="Markdown")
        return

    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
        types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
        types.InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")
    )
    if message.from_user.id == ADMIN_ID:
        builder.row(types.InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel"))
        
    await message.answer("🌐 Tilni tanlang / Choose language / Выберите язык:", reply_markup=builder.as_markup())

# --- TILNI O'ZGARTIRISH HENDLERI ---
@dp.callback_query(F.data.startswith("lang_"))
@check_ban
async def set_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]; user_id = str(callback.from_user.id)
    data = load_data(); data = init_user_data(data, user_id)
    data["users"][user_id]["lang"] = lang; save_data(data)
    await callback.message.edit_text(LANGUAGES[lang]["start"], parse_mode="Markdown")

# --- ADMIN PANEL HENDLERLARI ---
@dp.callback_query(F.data == "admin_panel")
async def open_admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    data = load_data()
    admin_text = f"📊 **Bot Statistikasi**\n\n👥 Jami foydalanuvchilar: `{len(data['users'])}` ta\n🚫 Bloklanganlar: `{len(data['banned'])}` ta"
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📢 Rassilka", callback_data="admin_broadcast"), types.InlineKeyboardButton(text="🚫 Ban / Unban", callback_data="admin_ban"))
    builder.row(types.InlineKeyboardButton(text="📂 Bazani yuklash", callback_data="admin_get_db"))
    await callback.message.edit_text(admin_text, parse_mode="Markdown", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "admin_get_db")
async def admin_get_db(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    if os.path.exists(DATA_FILE):
        await bot.send_document(chat_id=callback.from_user.id, document=types.FSInputFile(DATA_FILE), caption="📂 Bot bazasi.")
    else: await callback.answer("Baza topilmadi.")

@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.message.edit_text("📢 Rassilka xabarini yuboring:")

@dp.message(AdminStates.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    data = load_data(); users = list(data["users"].keys())
    for u in users:
        try: await bot.copy_message(chat_id=int(u), from_chat_id=message.chat.id, message_id=message.message_id)
        except: pass
    await message.answer("✅ Rassilka yakunlandi!")

@dp.callback_query(F.data == "admin_ban")
async def start_ban(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(AdminStates.waiting_for_ban_id)
    await callback.message.edit_text("🚫 Bloklamoqchi bo'lgan ID raqamni yuboring:")

@dp.message(AdminStates.waiting_for_ban_id)
async def do_ban(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    target_id = message.text.strip()
    data = load_data()
    if target_id in data["banned"]:
        data["banned"].remove(target_id); msg = "Blokdan chiqdi."
    else:
        data["banned"].append(target_id); msg = "Bloklandi."
    save_data(data)
    await message.answer(msg)

@dp.callback_query(F.data == "check_subscription")
async def check_sub(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    if await is_subscribed(user_id):
        await callback.message.delete()
        await callback.message.answer("🎉 Rahmat! Havola yuborishingiz mumkin.")
    else: await callback.answer("⚠️ Kanalga a'zo bo'ling!", show_alert=True)

# --- HAVOLALARNI QABUL QILISH TIZIMI ---
@dp.message(F.text)
@check_ban
async def handle_messages(message: types.Message):
    user_id = str(message.from_user.id); data = load_data(); data = init_user_data(data, user_id); lang = data["users"][user_id].get("lang", "uz")
    urls = re.findall(r'(https?://[^\s]+)', message.text)
    if not urls: return

    if not await is_subscribed(user_id):
        sub_builder = InlineKeyboardBuilder()
        sub_builder.row(types.InlineKeyboardButton(text="📢 Kanalga o'tish", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@','') }"))
        sub_builder.row(types.InlineKeyboardButton(text=LANGUAGES[lang]["check_sub_btn"], callback_data="check_subscription"))
        return await message.answer(LANGUAGES[lang]["sub_required"], reply_markup=sub_builder.as_markup())

    url = urls[0]
    platform = None
    if "instagram.com" in url: platform = "instagram"
    elif "tiktok.com" in url: platform = "tiktok"
    elif "youtube.com" in url or "youtu.be" in url: platform = "youtube"
    elif "pinterest.com" in url or "pin.it" in url: platform = "pinterest"

    if not platform: return

    data["users"][user_id]["last_url"] = url; save_data(data)
    bot_info = await bot.get_me()

    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="💾 Saqlash", callback_data=f"dl_video|{platform}"))
    builder.row(types.InlineKeyboardButton(text="📩 Qo'shiqni yuklab olish", callback_data=f"shazam_search|{platform}"))
    builder.row(types.InlineKeyboardButton(text="👈 Guruhga qo'shish ⤴️", url=f"https://t.me/{bot_info.username}?startgroup=true"))
    
    await message.answer(LANGUAGES[lang]["choose_format"], reply_markup=builder.as_markup())

# --- SHAZAM TIZIMI (QIDIRUV VA 1-5 TUGMAR) ---
@dp.callback_query(F.data.startswith("shazam_search"))
@check_ban
async def shazam_search_callback(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id); data = load_data(); lang = data["users"].get(user_id, {}).get("lang", "uz")
    url = data["users"].get(user_id, {}).get("last_url", "")
    if not url: return await callback.answer("Havola topilmadi.")

    await callback.message.edit_text("🔍 Videodagi original musiqa nomi aniqlanmoqda...")

    ydl_opts = {'quiet': True, 'no_warnings': True}
    if os.path.exists(COOKIES_FILE): ydl_opts['cookiefile'] = COOKIES_FILE

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=False))
        
        search_query = info.get('track') or info.get('title')
        artist = info.get('artist') or ""
        if artist and artist not in search_query:
            search_query = f"{artist} - {search_query}"
            
        search_query = re.sub(r'[#@\-\n]', ' ', search_query).strip()

        await callback.message.edit_text(f"🎵 Original nom: **{search_query}**\n🚀 YouTube'dan eng yaxshi talqinlar qidirilmoqda...")

        search_opts = {'format': 'bestaudio/best', 'quiet': True, 'extract_flat': True}
        search_results = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(search_opts).extract_info(f"ytsearch5:{search_query}", download=False))
        
        entries = search_results.get('entries', [])
        if not entries:
            return await callback.message.edit_text("❌ Afsuski, original musiqa variantlari topilmadi.")

        response_text = f"🎵 **{search_query}** uchun topilgan original musiqalar:\n\n"
        builder = InlineKeyboardBuilder()
        buttons = []

        for idx, entry in enumerate(entries):
            title = entry.get('title', 'Noma\'lum musiqa')
            duration = entry.get('duration')
            duration_str = f" {int(duration//60)}:{int(duration%60):02d}" if duration else ""
            
            response_text += f"{idx+1}. {title}**{duration_str}**\n"
            buttons.append(types.InlineKeyboardButton(text=str(idx+1), callback_data=f"szdl|{entry.get('id')}"))

        bot_info = await bot.get_me()
        builder.row(*buttons)
        builder.row(types.InlineKeyboardButton(text="🎬 Video formatda saqlash", callback_data="dl_video|youtube"))
        builder.row(types.InlineKeyboardButton(text="👈 Guruhga qo'shish ⤴️", url=f"https://t.me/{bot_info.username}?startgroup=true"))

        data["users"][user_id]["shazam_results"] = {e.get('id'): e.get('title') for e in entries}
        save_data(data)

        await callback.message.edit_text(response_text, reply_markup=builder.as_markup(), parse_mode="Markdown")

    except Exception as e:
        print(f"Shazam error: {e}")
        await callback.message.edit_text("❌ Musiqani aniqlashda xatolik yuz berdi.")

# --- TUZATILGAN AUDIO YUKLASH TIZIMI ---
@dp.callback_query(F.data.startswith("szdl"))
@check_ban
async def download_shazam_audio(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id); data = load_data(); lang = data["users"].get(user_id, {}).get("lang", "uz")
    video_id = callback.data.split("|")[1]
    audio_title = data["users"].get(user_id, {}).get("shazam_results", {}).get(video_id, "Original Audio")
    
    await callback.message.edit_text(f"⏳ **{audio_title}** yuklab olinmoqda...")
    audio_url = f"https://www.youtube.com/watch?v={video_id}"
    
    # FFMPEG'siz ham muammosiz yuklashi uchun formatni 'bestaudio' qildik va postprocessor olib tashlandi
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, f'{video_id}.%(ext)s'),
        'quiet': True,
        'no_warnings': True
    }
    
    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(audio_url, download=True))
        
        # Yuklangan fayl formatini tekshirish (m4a, webm, ogg bo'lishi mumkin)
        ext = info.get('ext', 'm4a')
        filename = os.path.join(DOWNLOAD_DIR, f"{video_id}.{ext}")
        
        if not os.path.exists(filename):
            for potential_ext in ['m4a', 'webm', 'mp3', 'ogg']:
                test_path = os.path.join(DOWNLOAD_DIR, f"{video_id}.{potential_ext}")
                if os.path.exists(test_path):
                    filename = test_path
                    break

        if os.path.exists(filename):
            file_input = types.FSInputFile(filename)
            await bot.send_audio(
                chat_id=callback.message.chat.id,
                audio=file_input,
                caption=f"🎵 **{audio_title}**\n\n⚡️ @tezzzsaverbot orqali yuklab olindi!",
                title=audio_title,
                performer="Tezzz Saver Shazam"
            )
            await callback.message.delete()
            os.remove(filename)
        else:
            await callback.message.edit_text("❌ Faylni yuklashda xatolik. Sarlavha juda uzun bo'lishi mumkin.")
    except Exception as e:
        print(f"Audio download error: {e}")
        await callback.message.edit_text("❌ Original musiqani yuklashda muammo bo'ldi. Render cheklovi.")

# --- VIDEONI ODDIY YUKLASH ---
@dp.callback_query(F.data.startswith("dl_video"))
@check_ban
async def download_video_format(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id); data = load_data()
    url = data["users"].get(user_id, {}).get("last_url", "")
    if not url: return await callback.answer("Xato.")

    await callback.message.edit_text("⏳ Video yuklanmoqda...")
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'quiet': True
    }
    if os.path.exists(COOKIES_FILE): ydl_opts['cookiefile'] = COOKIES_FILE

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=True))
        filename = yt_dlp.YoutubeDL(ydl_opts).prepare_filename(info)
        
        base = os.path.splitext(filename)[0]
        for ext in ['mp4', 'mkv', 'webm', 'mov']:
            if os.path.exists(f"{base}.{ext}"): filename = f"{base}.{ext}"; break

        if os.path.exists(filename):
            await bot.send_video(chat_id=callback.message.chat.id, video=types.FSInputFile(filename), caption="⚡️ @tezzzsaverbot orqali yuklab olindi!")
            await callback.message.delete()
            os.remove(filename)
    except Exception as e:
        print(e)
        await callback.message.edit_text("❌ Videoni yuklab bo'lmadi.")

# --- WEB SERVER ---
async def handle_root(request): return web.Response(text="Bot is perfectly running!")
async def start_web_server():
    app = web.Application(); app.router.add_get('/', handle_root)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000))).start()

async def main():
    asyncio.create_task(start_web_server())
    await dp.start_polling(bot)

if __name__ == '__main__': asyncio.run(main())