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
        "start": "⚡️ **Xush kelibsiz!**\nMenga ijtimoiy tarmoqlardan (Instagram, TikTok, YouTube, Pinterest) havola yuboring, uni bir zumda yuklab beraman! 🚀",
        "wait": "⏳ Video yuklanmoqda, iltimos kuting...",
        "choose_format": "🎬 YouTube videosi aniqlandi! Yuklab olish sifatini tanlang:",
        "success": "⚡️ @tezzzsaverbot orqali yuklab olindi!",
        "fail": "❌ Yuklashda xatolik yuz berdi yoki havola noto'g'ri.",
        "sub_required": "⚠️ **Botdan foydalanish uchun kanalimizga a'zo bo'lishingiz shart!**",
        "check_sub_btn": "✅ A'zo bo'ldim / Tekshirish"
    },
    "ru": {
        "start": "⚡️ **Добро пожаловать!**\nОтправьте мне ссылку, и я скачаю её! 🚀",
        "wait": "⏳ Видео скачивается, подождите...",
        "choose_format": "🎬 Обнаружено видео YouTube! Выберите качество:",
        "success": "⚡️ Скачано с помощью @tezzzsaverbot!",
        "fail": "❌ Ошибка при скачивании.",
        "sub_required": "⚠️ **Для использования бота подпишитесь на канал!**",
        "check_sub_btn": "✅ Я подписался"
    },
    "en": {
        "start": "⚡️ **Welcome!**\nSend me a link, and I will download it! 🚀",
        "wait": "⏳ Video is downloading, please wait...",
        "choose_format": "🎬 YouTube video detected! Choose quality:",
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

# --- TIL HANDLERI ---
@dp.callback_query(F.data.startswith("lang_"))
@check_ban
async def set_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]; user_id = str(callback.from_user.id)
    data = load_data(); data = init_user_data(data, user_id)
    data["users"][user_id]["lang"] = lang; save_data(data)
    await callback.message.edit_text(LANGUAGES[lang]["start"], parse_mode="Markdown")

# --- TO'G'RILANGAN ADMIN PANEL ---
@dp.callback_query(F.data == "admin_panel")
async def open_admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    data = load_data()
    admin_text = f"📊 **Bot Statistikasi**\n\n👥 Jami foydalanuvchilar: `{len(data['users'])}` ta\n🚫 Bloklanganlar: `{len(data['banned'])}` ta"
    builder = InlineKeyboardBuilder()
    builder.row(types.InlineKeyboardButton(text="📢 Xabar yuborish (Rassilka)", callback_data="admin_broadcast"), types.InlineKeyboardButton(text="🚫 Ban / Unban", callback_data="admin_ban"))
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
    await callback.message.edit_text("📢 Rassilka xabarini (matn, rasm yoki video) yuboring:")

# --- MUTLAQ TO'G'RILANGAN RASSILKA TIZIMI ---
@dp.message(AdminStates.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    
    data = load_data()
    users = list(data["users"].keys())
    
    status_msg = await message.answer(f"⏳ Xabar `{len(users)}` ta foydalanuvchiga yuborilmoqda...")
    
    success_count = 0
    fail_count = 0
    
    for u in users:
        try:
            # ID larni integer (son) ko'rinishida yuborish majburiy
            await bot.copy_message(
                chat_id=int(u), 
                from_chat_id=message.chat.id, 
                message_id=message.message_id
            )
            success_count += 1
            # Telegram bloklamasligi uchun qisqa uzilish
            await asyncio.sleep(0.05)
        except Exception as e:
            fail_count += 1
            pass
            
    await status_msg.edit_text(
        f"✅ **Rassilka yakunlandi!**\n\n"
        f"🚀 Muvaffaqiyatli: `{success_count}` ta\n"
        f"❌ Yuborilmadi (Botni bloklaganlar): `{fail_count}` ta",
        parse_mode="Markdown"
    )

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

    if platform == "youtube":
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(text="🎬 720p Video", callback_data="yt_dl|720"),
            types.InlineKeyboardButton(text="📺 360p Video", callback_data="yt_dl|360")
        )
        await message.answer(LANGUAGES[lang]["choose_format"], reply_markup=builder.as_markup())
    else:
        status_msg = await message.answer(LANGUAGES[lang]["wait"])
        ydl_format = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
        await process_video_download(status_msg, url, lang, ydl_format)

@dp.callback_query(F.data.startswith("yt_dl|"))
@check_ban
async def youtube_download_callback(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id); data = load_data(); lang = data["users"].get(user_id, {}).get("lang", "uz")
    url = data["users"].get(user_id, {}).get("last_url", "")
    if not url: return await callback.answer("Xatolik.")

    quality = callback.data.split("|")[1]
    ydl_format = f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/best[height<={quality}]/best'
    
    await callback.message.edit_text(LANGUAGES[lang]["wait"])
    await process_video_download(callback.message, url, lang, ydl_format)

async def process_video_download(msg_to_edit, url, lang, ydl_format):
    bot_info = await bot.get_me()
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="👈 Guruhga qo'shish ⤴️", url=f"https://t.me/{bot_info.username}?startgroup=true"),
        types.InlineKeyboardButton(text="🚀 Ulashish", url=f"https://t.me/share/url?url=https://t.me/{bot_info.username}?start=share")
    )

    ydl_opts = {
        'format': ydl_format,
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'quiet': True,
        'no_warnings': True
    }
    if os.path.exists(COOKIES_FILE): ydl_opts['cookiefile'] = COOKIES_FILE

    try:
        loop = asyncio.get_event_loop()
        info = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(ydl_opts).extract_info(url, download=True))
        filename = yt_dlp.YoutubeDL(ydl_opts).prepare_filename(info)
        
        base = os.path.splitext(filename)[0]
        for ext in ['mp4', 'mkv', 'webm', 'mov']:
            if os.path.exists(f"{base}.{ext}"): 
                filename = f"{base}.{ext}"
                break

        if os.path.exists(filename):
            file_input = types.FSInputFile(filename)
            await bot.send_video(
                chat_id=msg_to_edit.chat.id, 
                video=file_input, 
                caption=LANGUAGES[lang]["success"],
                reply_markup=builder.as_markup()
            )
            await msg_to_edit.delete()
            os.remove(filename)
        else:
            await msg_to_edit.edit_text(LANGUAGES[lang]["fail"])
    except Exception as e:
        print(f"Download Error: {e}")
        await msg_to_edit.edit_text(LANGUAGES[lang]["fail"])

# --- WEB SERVER ---
async def handle_root(request): return web.Response(text="Bot is running completely fixed!")
async def start_web_server():
    app = web.Application(); app.router.add_get('/', handle_root)
    runner = web.AppRunner(app); await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 10000))).start()

async def main():
    asyncio.create_task(start_web_server())
    await dp.start_polling(bot)

if __name__ == '__main__': asyncio.run(main())