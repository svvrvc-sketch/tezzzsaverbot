import os
import json
import asyncio
import yt_dlp
import re
import inspect
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent

# Bot sozlamalari
API_TOKEN = '8747746960:AAFPVKsQ4o5gfbayRUlbOOQ_rXGGoY5hMJY'
ADMIN_ID = 5111794979  # Telegram ID raqamingiz

# --- SOZLAMALAR ---
USE_PREMIUM_SYSTEM = False   
USE_MANDATORY_SUB = True     
REQUIRED_CHANNEL = "@svpains" 
DAILY_FREE_LIMIT = 5        

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
    waiting_for_premium_id = State()

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

def init_user_data(data, user_id):
    today = datetime.now().strftime("%Y-%m-%d")
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "lang": "uz",
            "is_premium": False,
            "downloads_today": 0,
            "last_download_date": today,
            "stats": {"instagram": 0, "tiktok": 0, "youtube": 0, "pinterest": 0}
        }
    else:
        if "is_premium" not in data["users"][user_id]:
            data["users"][user_id]["is_premium"] = False
        if "downloads_today" not in data["users"][user_id]:
            data["users"][user_id]["downloads_today"] = 0
        if "last_download_date" not in data["users"][user_id]:
            data["users"][user_id]["last_download_date"] = today
        if "stats" not in data["users"][user_id]:
            data["users"][user_id]["stats"] = {"instagram": 0, "tiktok": 0, "youtube": 0, "pinterest": 0}
            
    if data["users"][user_id]["last_download_date"] != today:
        data["users"][user_id]["downloads_today"] = 0
        data["users"][user_id]["last_download_date"] = today
    return data

LANGUAGES = {
    "uz": {
        "start": "⚡️ **Xush kelibsiz!**\nMenga ijtimoiy tarmoqlardan (Instagram, TikTok, YouTube, Pinterest) havola yuboring, men uni bir zumda yuklab beraman! 🚀",
        "error_domain": "⚠️ Xatolik! Havola faqat Instagram, YouTube, TikTok yoki Pinterest tarmog‘iga tegishli bo‘lishi kerak.",
        "wait": "⏳ Video tahlil qilinmoqda...",
        "choose_format": "🎬 Havola aniqlandi! Yuklab olish formatini tanlang:",
        "success": "⚡️ @tezzzsaverbot orqali yuklab olindi!",
        "fail": "❌ Yuklashda xatolik yuz berdi. Havola yopiq bo'lishi mumkin.",
        "sub_required": f"⚠️ **Botdan foydalanish uchun kanalimizga a'zo bo'lishingiz shart!**\n\nIltimos, pastdagi kanalga a'zo bo'lib, keyin qaytadan tekshirib ko'ring.",
        "limit_reached": f"🚫 **Kunlik tekin limit tugadi!**",
        "check_sub_btn": "✅ A'zo bo'ldim / Tekshirish"
    },
    "ru": {
        "start": "⚡️ **Добро пожаловать!**\nОтправьте мне ссылку из соцсетей, и я мгновенно скачаю её для вас! 🚀",
        "error_domain": "⚠️ Ошибка! Неверный домен.",
        "wait": "⏳ Видео анализируется...",
        "choose_format": "🎬 Ссылка обнаружена! Выберите формат:",
        "success": "⚡️ Скачано с помощью @tezzzsaverbot!",
        "fail": "❌ Произошла ошибка при скачивании.",
        "sub_required": f"⚠️ **Для использования бота вы должны подписаться на наш канал!**",
        "limit_reached": f"🚫 **Дневной бесплатный лимит исчерпан!**",
        "check_sub_btn": "✅ Я подписался"
    },
    "en": {
        "start": "⚡️ **Welcome!**\nSend me a link from social media, and I will download it instantly! 🚀",
        "error_domain": "⚠️ Error! Invalid domain.",
        "wait": "⏳ Analyzing video...",
        "choose_format": "🎬 Link detected! Choose format:",
        "success": "⚡️ Downloaded via @tezzzsaverbot!",
        "fail": "❌ Error occurred during download.",
        "sub_required": f"⚠️ **To use the bot, you must subscribe to our channel!**",
        "limit_reached": f"🚫 **Daily free limit reached!**",
        "check_sub_btn": "✅ I subscribed"
    }
}

async def is_subscribed(user_id):
    if not USE_MANDATORY_SUB:
        return True
    try:
        member = await bot.get_chat_member(chat_id=REQUIRED_CHANNEL, user_id=int(user_id))
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Obunani tekshirishda xato: {e}")
        return True

# MUTLAQ XAVFSIZ DEKORATOR: Ortiqcha argumentlarni dinamik ravishda o'chirib tashlaydi
def check_ban(func):
    async def wrapper(message_or_call, *args, **kwargs):
        user_id = str(message_or_call.from_user.id)
        data = load_data()
        if user_id in data.get("banned", []):
            if isinstance(message_or_call, types.Message):
                await message_or_call.answer("🚫 Botdan foydalanish huquqingiz cheklangan (Banned).")
            return
        
        # Funksiya qabul qila oladigan argumentlarni aniqlaymiz va faqat o'shalarni uzatamiz
        sig = inspect.signature(func)
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return await func(message_or_call, *args, **filtered_kwargs)
    return wrapper

@dp.message(CommandStart())
@check_ban
async def cmd_start(message: types.Message):
    user_id = str(message.from_user.id)
    data = load_data()
    data = init_user_data(data, user_id)
    save_data(data)
        
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
        types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
        types.InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")
    )
    if message.from_user.id == ADMIN_ID:
        builder.row(types.InlineKeyboardButton(text="⚙️ Admin Panel", callback_data="admin_panel"))
        
    if not await is_subscribed(user_id):
        sub_builder = InlineKeyboardBuilder()
        sub_builder.row(types.InlineKeyboardButton(text="📢 Kanalga o'tish", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@','') }"))
        sub_builder.row(types.InlineKeyboardButton(text=LANGUAGES["uz"]["check_sub_btn"], callback_data="check_subscription"))
        await message.answer(LANGUAGES["uz"]["sub_required"], reply_markup=sub_builder.as_markup(), parse_mode="Markdown")
    else:
        await message.answer("🌐 Choose language / Tilni tanlang / Выберите язык:", reply_markup=builder.as_markup())

# --- ADMIN PANEL ---
@dp.callback_query(F.data == "admin_panel")
async def open_admin_panel(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    data = load_data()
    
    ig, tk, yt, pin = 0, 0, 0, 0
    for u in data["users"].values():
        st = u.get("stats", {})
        ig += st.get("instagram", 0)
        tk += st.get("tiktok", 0)
        yt += st.get("youtube", 0)
        pin += st.get("pinterest", 0)
        
    admin_text = (
        f"📊 **Bot Statistikasi**\n\n"
        f"👥 Jami foydalanuvchilar: `{len(data['users'])}` ta\n"
        f"🚫 Bloklanganlar: `{len(data['banned'])}` ta\n\n"
        f"📥 **Yuklashlar statistikasi:**\n"
        f"📸 Instagram: {ig} ta | 🎵 TikTok: {tk} ta\n"
        f"🎬 YouTube: {yt} ta | 📌 Pinterest: {pin} ta\n\n"
        f"Boshqaruv funksiyasini tanlang:"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="📢 Rassilka (Xabar)", callback_data="admin_broadcast"),
        types.InlineKeyboardButton(text="🚫 Ban / Unban", callback_data="admin_ban")
    )
    builder.row(
        types.InlineKeyboardButton(text="📂 Bazani yuklash", callback_data="admin_get_db"),
        types.InlineKeyboardButton(text="🔄 Yangilash", callback_data="admin_panel")
    )
    
    await callback.message.edit_text(admin_text, parse_mode="Markdown", reply_markup=builder.as_markup())

@dp.callback_query(F.data == "admin_get_db")
async def admin_get_db(callback: types.CallbackQuery):
    if callback.from_user.id != ADMIN_ID: return
    if os.path.exists(DATA_FILE):
        file_input = types.FSInputFile(DATA_FILE)
        await bot.send_document(chat_id=callback.from_user.id, document=file_input, caption="📂 Bot foydalanuvchilarining to'liq bazasi.")
        await callback.answer("Baza yuborildi.")
    else:
        await callback.answer("Baza fayli topilmadi.", show_alert=True)

@dp.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.message.edit_text("📢 Barcha foydalanuvchilarga yuborilishi kerak bo'lgan xabarni yuboring:")

@dp.message(AdminStates.waiting_for_broadcast)
async def do_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    data = load_data()
    users = list(data["users"].keys())
    status_msg = await message.answer(f"⏳ Xabar yuborish boshlandi (0/{len(users)})...")
    success_count = 0
    
    for idx, user_id in enumerate(users):
        try:
            await bot.copy_message(chat_id=int(user_id), from_chat_id=message.chat.id, message_id=message.message_id)
            success_count += 1
        except: pass
        if (idx + 1) % 20 == 0:
            try: await status_msg.edit_text(f"⏳ Yuborilmoqda... ({idx + 1}/{len(users)})")
            except: pass
        await asyncio.sleep(0.05)
    await status_msg.edit_text(f"✅ **Rassilka yakunlandi!**\n\n🎯 Muvaffaqiyatli yetkazildi: {success_count} ta foydalanuvchiga.")

@dp.callback_query(F.data == "admin_ban")
async def start_ban(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != ADMIN_ID: return
    await state.set_state(AdminStates.waiting_for_ban_id)
    await callback.message.edit_text("🚫 Bloklamoqchi bo'lgan foydalanuvchining Telegram ID raqamini yuboring:")

@dp.message(AdminStates.waiting_for_ban_id)
async def do_ban(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.clear()
    target_id = message.text.strip()
    if not target_id.isdigit(): return await message.answer("⚠️ Xato ID.")
    data = load_data()
    if target_id in data["banned"]:
        data["banned"].remove(target_id)
        save_data(data)
        await message.answer(f"✅ Foydalanuvchi `{target_id}` blokdan chiqarildi.")
    else:
        data["banned"].append(target_id)
        save_data(data)
        await message.answer(f"🚫 Foydalanuvchi `{target_id}` bloklandi.")

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    user_id = str(callback.from_user.id)
    data = load_data()
    data = init_user_data(data, user_id)
    data["users"][user_id]["lang"] = lang
    save_data(data)
    await callback.message.edit_text(LANGUAGES[lang]["start"], parse_mode="Markdown")

@dp.callback_query(F.data == "check_subscription")
async def check_subscription_callback(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    data = load_data()
    lang = data["users"].get(user_id, {}).get("lang", "uz")
    if await is_subscribed(user_id):
        await callback.message.delete()
        
        builder = InlineKeyboardBuilder()
        builder.row(
            types.InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
            types.InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            types.InlineKeyboardButton(text="🇺🇸 English", callback_data="lang_en")
        )
        await callback.message.answer("🌐 Choose language / Tilni tanlang / Выберите язык:", reply_markup=builder.as_markup())
    else:
        await callback.answer("⚠️ Siz hali ham kanalga a'zo bo'lmadingiz!", show_alert=True)

# --- XABARLARNI QABUL QILISH ---
@dp.message(F.text)
@check_ban
async def handle_messages(message: types.Message):
    user_id = str(message.from_user.id)
    data = load_data()
    data = init_user_data(data, user_id)
    lang = data["users"][user_id]["lang"]

    urls = re.findall(r'(https?://[^\s]+)', message.text)
    if not urls: return

    if not await is_subscribed(user_id):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📢 Kanalga o'tish", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@','') }"))
        builder.row(types.InlineKeyboardButton(text=LANGUAGES[lang]["check_sub_btn"], callback_data="check_subscription"))
        return await message.answer(LANGUAGES[lang]["sub_required"], reply_markup=builder.as_markup(), parse_mode="Markdown")

    url = urls[0]
    platform = None
    if "instagram.com" in url: platform = "instagram"
    elif "tiktok.com" in url: platform = "tiktok"
    elif "youtube.com" in url or "youtu.be" in url: platform = "youtube"
    elif "pinterest.com" in url or "pin.it" in url: platform = "pinterest"

    if not platform:
        if message.chat.type == "private": await message.answer(LANGUAGES[lang]["error_domain"])
        return

    builder = InlineKeyboardBuilder()
    if platform == "youtube":
        builder.row(
            types.InlineKeyboardButton(text="🎬 720p (HD)", callback_data=f"dl_hd|{platform}"),
            types.InlineKeyboardButton(text="📺 360p (SD)", callback_data=f"dl_sd|{platform}")
        )
    else:
        builder.row(types.InlineKeyboardButton(text="🎬 Videoni yuklash", callback_data=f"dl_best|{platform}"))
    
    builder.row(types.InlineKeyboardButton(text="🎵 Faqat MP3 (Musiqasini ajratish)", callback_data=f"dl_mp3|{platform}"))
    
    data["users"][user_id]["last_url"] = url
    save_data(data)
    await message.answer(LANGUAGES[lang]["choose_format"], reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("dl_"))
async def format_callback(callback: types.CallbackQuery):
    user_id = str(callback.from_user.id)
    data = load_data()
    lang = data["users"].get(user_id, {}).get("lang", "uz")
    url = data["users"].get(user_id, {}).get("last_url", "")
    if not url: return await callback.answer("Xatolik.")

    if not await is_subscribed(user_id):
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="📢 Kanalga o'tish", url=f"https://t.me/{REQUIRED_CHANNEL.replace('@','') }"))
        builder.row(types.InlineKeyboardButton(text=LANGUAGES[lang]["check_sub_btn"], callback_data="check_subscription"))
        return await callback.message.edit_text(LANGUAGES[lang]["sub_required"], reply_markup=builder.as_markup(), parse_mode="Markdown")

    action = callback.data.split("|")[0]
    platform = callback.data.split("|")[1]
    
    ydl_format = 'bestvideo+bestaudio/best'
    is_audio = False
    
    if action == "dl_hd": ydl_format = 'bestvideo[height<=720]+bestaudio/best'
    elif action == "dl_sd": ydl_format = 'bestvideo[height<=360]+bestaudio/best'
    elif action == "dl_mp3": 
        ydl_format = 'bestaudio/best'
        is_audio = True

    await callback.message.edit_text(LANGUAGES[lang]["wait"])
    
    success = await process_download(callback.message, url, lang, ydl_format, is_audio)
    
    if success:
        data = load_data()
        data = init_user_data(data, user_id)
        data["users"][user_id]["downloads_today"] += 1
        data["users"][user_id]["stats"][platform] = data["users"][user_id]["stats"].get(platform, 0) + 1
        save_data(data)

async def process_download(msg, url, lang, ydl_format, is_audio=False):
    ydl_opts = {
        'format': ydl_format,
        'outtmpl': os.path.join(DOWNLOAD_DIR, '%(id)s.%(ext)s'),
        'no_warnings': True,
        'quiet': True,
        'geo_bypass': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
    }
    
    if os.path.exists(COOKIES_FILE):
        ydl_opts['cookiefile'] = COOKIES_FILE

    if is_audio:
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    try:
        loop = asyncio.get_event_loop()
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)

        filename = await loop.run_in_executor(None, download)
        if is_audio: filename = os.path.splitext(filename)[0] + ".mp3"
        
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
        return True
    except Exception as e:
        print(f"Yuklashda xato: {e}")
        await msg.edit_text(LANGUAGES[lang]["fail"])
        return False

# --- INLINE REJIM ---
@dp.inline_query()
async def inline_handler(inline_query: types.InlineQuery):
    text = inline_query.query.strip()
    urls = re.findall(r'(https?://[^\s]+)', text)
    if not urls: return

    url = urls[0]
    allowed = ["instagram.com", "tiktok.com", "youtube.com", "youtu.be", "pinterest.com", "pin.it"]
    if not any(d in url for d in allowed): return

    results = [
        InlineQueryResultArticle(
            id="1",
            title="🎬 Videoni yuklash (Tezzz Saver)",
            description=f"Havolani guruhga yuborish: {url[:30]}...",
            input_text_content=InputTextMessageContent(message_text=url)
        )
    ]
    await inline_query.answer(results, cache_time=1)

async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())