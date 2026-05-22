import asyncio, aiosqlite, os, random
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
from threading import Thread

# ⚠️ SECURITY: Use environment variable instead of hardcoded token
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN environment variable not set!")

OWNER_ID = 866169035 
bot = Bot(token=TOKEN, allowed_updates=["message", "callback_query"])
dp = Dispatcher()

app = Flask(__name__)
@app.route('/')
def home(): 
    return "OK"

def run_flask(): 
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 10000)))

async def init_db():
    async with aiosqlite.connect("bio_game.db") as db:
        await db.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, name TEXT, bio_exp INTEGER DEFAULT 0, resources REAL DEFAULT 0,
            pathogen_name TEXT DEFAULT 'Вирус', pathogens_count INTEGER DEFAULT 1,
            lab_level INTEGER DEFAULT 1, contagiousness INTEGER DEFAULT 1, immunity INTEGER DEFAULT 1, 
            lethality INTEGER DEFAULT 1, security_service INTEGER DEFAULT 1, 
            ops_total INTEGER DEFAULT 0, ops_won INTEGER DEFAULT 0, prevented INTEGER DEFAULT 0, is_banned INTEGER DEFAULT 0)""")
        await db.commit()

def get_main_kb(user_id):
    kb = [[InlineKeyboardButton(text="🧪 Лаба", callback_data="lab"), InlineKeyboardButton(text="🧬 Патоген", callback_data="pathogen")],
          [InlineKeyboardButton(text="💰 Ресурсы", callback_data="res"), InlineKeyboardButton(text="⚔️ Атака", callback_data="attack")]]
    if user_id == OWNER_ID:
        kb.append([InlineKeyboardButton(text="⚙️ ROOT-ПАНЕЛЬ", callback_data="root_admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.callback_query(F.data.in_(["lab", "pathogen", "res", "attack", "root_admin"]))
async def menu_handler(call: CallbackQuery):
    try:
        if call.data == "root_admin" and call.from_user.id != OWNER_ID: 
            await call.answer("❌ Доступ запрещен", show_alert=True)
            return
        
        async with aiosqlite.connect("bio_game.db") as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE id=?", (call.from_user.id,))
            u = await cursor.fetchone()
        
        if not u:
            await call.answer("❌ Пользователь не найден. Используйте /start", show_alert=True)
            return
        
        if u["is_banned"]:
            await call.answer("🚫 Вы заблокированы", show_alert=True)
            return

        if call.data == "attack":
            async with aiosqlite.connect("bio_game.db") as db:
                db.row_factory = aiosqlite.Row
                cursor = await db.execute("SELECT id, name, resources, immunity FROM users WHERE id != ? ORDER BY RANDOM() LIMIT 1", (call.from_user.id,))
                victim = await cursor.fetchone()
            
            if victim:
                chance = 0.5 + (u["lethality"] * 0.05) - (victim["immunity"] * 0.05)
                if random.random() < chance:
                    loot = victim["resources"] * 0.1
                    async with aiosqlite.connect("bio_game.db") as db:
                        await db.execute("UPDATE users SET resources = resources + ? WHERE id=?", (loot, call.from_user.id))
                        await db.execute("UPDATE users SET resources = resources - ? WHERE id=?", (loot, victim["id"]))
                        await db.commit()
                    await call.answer(f"✅ Успех! Украдено {loot:.1f} ресурсов.", show_alert=True)
                else:
                    await call.answer("🛡 Атака отбита! Высокий иммунитет жертвы.", show_alert=True)
            else:
                await call.answer("❌ Нет доступных врагов", show_alert=True)
            return

        status = "👑 ВЛАДЕЛЕЦ" if call.from_user.id == OWNER_ID else "🧬 Мутант"
        win_rate = (u["ops_won"] / u["ops_total"] * 100) if u["ops_total"] > 0 else 0
        
        text = (f"Статус: {status}\n"
                f"🏷 Патоген: {u['pathogen_name']} (x{u['pathogens_count']})\n"
                f"🧪 Квал: {u['lab_level']} ур.\n\n"
                f"⚡️ НАВЫКИ:\n"
                f"🦠 Заразность: {u['contagiousness']} | 🛡 Иммунитет: {u['immunity']}\n"
                f"💀 Летальность: {u['lethality']} | 👮 СБ: {u['security_service']}\n\n"
                f"📊 СТАТИСТИКА:\n"
                f"☣️ Опыт: {u['bio_exp']} | 🧬 Рес: {u['resources']:.1f}k\n"
                f"😷 Спецопер: {u['ops_won']}/{u['ops_total']} ({win_rate:.1f}%)\n"
                f"🕶 Предотвращено: {u['prevented']}")
        
        await call.message.edit_text(text, reply_markup=get_main_kb(call.from_user.id))
        await call.answer()
    
    except Exception as e:
        print(f"Error in menu_handler: {e}")
        await call.answer(f"❌ Ошибка: {str(e)}", show_alert=True)

@dp.message(F.text.lower().contains("заразить"))
async def infect_cmd(msg: Message):
    try:
        async with aiosqlite.connect("bio_game.db") as db:
            await db.execute("UPDATE users SET pathogens_count = pathogens_count + 1 WHERE id=?", (msg.from_user.id,))
            await db.commit()
        await msg.answer("🦠 Патоген внедрен!")
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {str(e)}")

@dp.message(Command("start"))
async def start(msg: Message):
    try:
        async with aiosqlite.connect("bio_game.db") as db:
            await db.execute("INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)", (msg.from_user.id, msg.from_user.first_name))
            await db.commit()
        await msg.answer("Система BioGame активна.", reply_markup=get_main_kb(msg.from_user.id))
    except Exception as e:
        await msg.answer(f"❌ Ошибка инициализации: {str(e)}")

@dp.message(Command("ban"))
async def ban(msg: Message):
    if msg.from_user.id != OWNER_ID: 
        await msg.answer("❌ Доступ запрещен")
        return
    
    args = msg.text.split()
    if len(args) < 2:
        await msg.answer("❌ Использование: /ban <user_id>")
        return
    
    try:
        user_id = int(args[1])
        async with aiosqlite.connect("bio_game.db") as db:
            await db.execute("UPDATE users SET is_banned = 1 WHERE id=?", (user_id,))
            await db.commit()
        await msg.answer(f"🚫 Юзер {user_id} заблокирован.")
    except ValueError:
        await msg.answer("❌ ID должно быть числом")
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {str(e)}")

@dp.message(Command("sudo"))
async def sudo(msg: Message):
    if msg.from_user.id != OWNER_ID: 
        await msg.answer("❌ Доступ запрещен")
        return
    
    args = msg.text.split()
    if len(args) < 4:
        await msg.answer("❌ Использование: /sudo <column> <user_id> <value>")
        return
    
    try:
        column = args[1]
        user_id = int(args[2])
        value = int(args[3])
        
        # Белый список колонн для безопасности
        allowed_columns = ["bio_exp", "resources", "lab_level", "contagiousness", "immunity", "lethality", "security_service", "ops_total", "ops_won", "prevented", "pathogens_count"]
        
        if column not in allowed_columns:
            await msg.answer(f"❌ Колонна '{column}' не разрешена")
            return
        
        async with aiosqlite.connect("bio_game.db") as db:
            await db.execute(f"UPDATE users SET {column} = {column} + ? WHERE id=?", (value, user_id))
            await db.commit()
        await msg.answer(f"✅ ROOT: {column} +{value} д��я {user_id}")
    except ValueError:
        await msg.answer("❌ user_id и value должны быть числами")
    except Exception as e:
        await msg.answer(f"❌ Ошибка: {str(e)}")

if __name__ == "__main__":
    Thread(target=run_flask, daemon=True).start()
    asyncio.run(init_db())
    asyncio.run(dp.start_polling(bot))
