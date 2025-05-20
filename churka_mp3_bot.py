import telebot
from telebot import types
from telebot.types import BotCommand
import sqlite3
import datetime
import threading
import time
import re
import os
from flask import Flask

app = Flask(__name__)

@app.route('/')
def home():
    return "Бот работает!", 200

bot = telebot.TeleBot("7424169031:AAE_fq0v6boMqkaW4m4Fu-mXBYYYJtQYa9w")

def setup_commands():
    commands = [
        BotCommand("start", "Начать работу с ботом"),
        BotCommand("progress", "Ваш текущий прогресс"),
        BotCommand("settime", "Изменить время напоминаний"),
        BotCommand("timezone", "Изменить часовой пояс"),
        BotCommand("help", "Помощь по командам")
    ]
    bot.set_my_commands(commands)

def init_db():
    conn = sqlite3.connect('habits.db', check_same_thread=False)
    cursor = conn.cursor()

    cursor.execute('''
    CREATE TABLE IF NOT EXISTS habits (
        user_id INTEGER,
        habit TEXT,
        reminder_time TEXT,
        current_streak INTEGER DEFAULT 0,
        max_streak INTEGER DEFAULT 0,
        last_reminder_date TEXT,
        last_message_id INTEGER,
        timezone TEXT DEFAULT '+03:00',
        PRIMARY KEY (user_id, habit)
    )
    ''')
    conn.commit()
    return conn, cursor

db_conn, db_cursor = init_db()

@bot.message_handler(commands=['start'])
def start(message):
    markup = types.InlineKeyboardMarkup()
    create_habit_button = types.InlineKeyboardButton("Добавить привычку🦾", callback_data="create")
    markup.add(create_habit_button)

    bot.send_message(
        message.chat.id,
        "Привет, я помогу тебе выработать привычку\n\n"
        "Нажми на кнопку 'Добавить привычку'",
        reply_markup=markup
    )

@bot.callback_query_handler(func=lambda call: call.data == "create")
def handle_button(call):
    create_habit(call.message)

def create_habit(message):
    cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    cancel_markup.add(types.KeyboardButton("Отмена❌"))

    bot.send_message(
        message.chat.id,
        "Напишите название для вашей привычки (или нажмите 'Отмена'):",
        reply_markup=cancel_markup
    )
    bot.register_next_step_handler(message, ask_habit)

def ask_habit(message):
    if message.text == "Отмена❌":
        bot.send_message(
            message.chat.id,
            "Добавление привычки отменено",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return start(message)

    habit = message.text.strip()

    if not habit or len(habit) > 100:
        bot.send_message(
            message.chat.id,
            "Название привычки должно быть от 1 до 100 символов. Попробуйте еще раз:"
        )
        return create_habit(message)

    try:
        db_cursor.execute(
            "INSERT OR REPLACE INTO habits (user_id, habit) VALUES (?, ?)",
            (message.chat.id, habit)
        )
        db_conn.commit()
        
        timezone_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        timezone_markup.add(
            types.KeyboardButton("Москва (+3)"),
            types.KeyboardButton("Киев (+2)"),
            types.KeyboardButton("Другой")
        )
        
        bot.send_message(
            message.chat.id,
            "Выберите ваш часовой пояс:",
            reply_markup=timezone_markup
        )
        bot.register_next_step_handler(message, set_timezone)
        
    except sqlite3.Error as e:
        bot.send_message(
            message.chat.id,
            "Произошла ошибка при сохранении привычки"
        )
        print("DB Error:", e)

def set_timezone(message):
    timezone_map = {
        "Москва (+3)": "+03:00",
        "Киев (+2)": "+02:00"
    }
    
    if message.text in timezone_map:
        timezone = timezone_map[message.text]
    elif message.text == "Другой":
        bot.send_message(
            message.chat.id,
            "Введите ваш часовой пояс в формате ±HH:MM (например, +05:00 или -08:00):",
            reply_markup=types.ReplyKeyboardRemove()
        )
        bot.register_next_step_handler(message, validate_custom_timezone)
        return
    else:
        bot.send_message(message.chat.id, "Пожалуйста, выберите вариант из предложенных")
        return ask_habit(message)
    
    db_cursor.execute(
        "UPDATE habits SET timezone = ? WHERE user_id = ?",
        (timezone, message.chat.id)
    )
    db_conn.commit()
    
    cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    cancel_markup.add(types.KeyboardButton("Отмена❌"))
    bot.send_message(
        message.chat.id,
        "Во сколько вы хотите получать уведомления о привычке? (ЧЧ:ММ)\n"
        "Укажите время в вашем часовом поясе (например 08:30)",
        reply_markup=cancel_markup
    )
    bot.register_next_step_handler(message, validate_time_input)

def validate_custom_timezone(message):
    if not re.match(r'^[+-](0[0-9]|1[0-2]):[0-5][0-9]$', message.text):
        bot.send_message(
            message.chat.id,
            "Неверный формат часового пояса. Пожалуйста, используйте формат ±HH:MM (например, +05:00 или -08:00)"
        )
        return ask_habit(message)
    
    db_cursor.execute(
        "UPDATE habits SET timezone = ? WHERE user_id = ?",
        (message.text, message.chat.id)
    )
    db_conn.commit()
    
    cancel_markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    cancel_markup.add(types.KeyboardButton("Отмена❌"))
    bot.send_message(
        message.chat.id,
        "Во сколько вы хотите получать уведомления о привычке? (ЧЧ:ММ)\n"
        "Укажите время в вашем часовом поясе (например 08:30)",
        reply_markup=cancel_markup
    )
    bot.register_next_step_handler(message, validate_time_input)

def validate_time_input(message):
    if message.text == "Отмена❌":
        bot.send_message(
            message.chat.id,
            "Добавление привычки отменено",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return start(message)
    
    time_input = message.text.strip()

    if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', time_input):
        bot.send_message(
            message.chat.id,
            "⛔ Неверный формат времени! Пожалуйста, введите время в формате ЧЧ:MM (например, 08:30 или 21:45)\n"
            "Часы должны быть от 00 до 23, минуты от 00 до 59."
        )
        bot.register_next_step_handler(message, validate_time_input)
        return

    try:
        db_cursor.execute(
            "UPDATE habits SET reminder_time = ? WHERE user_id = ?",
            (time_input, message.chat.id)
        )
        db_conn.commit()

        # Получаем часовой пояс для отображения
        db_cursor.execute(
            "SELECT timezone FROM habits WHERE user_id = ? LIMIT 1",
            (message.chat.id,)
        )
        timezone = db_cursor.fetchone()[0]

        bot.send_message(
            message.chat.id,
            f"✅ Отлично! Буду напоминать о привычке каждый день в {time_input} "
            f"(по вашему местному времени, часовой пояс {timezone}).",
            reply_markup=types.ReplyKeyboardRemove()
        )

    except sqlite3.Error as e:
        bot.send_message(
            message.chat.id,
            "Ошибка при сохранении времени напоминания"
        )
        print("DB Error:", e)

def send_reminders():
    now_utc = datetime.datetime.utcnow()
    
    # Получаем всех пользователей с их часовыми поясами
    db_cursor.execute(
        "SELECT DISTINCT user_id, timezone FROM habits WHERE reminder_time IS NOT NULL"
    )
    users = db_cursor.fetchall()
    
    for user_id, timezone in users:
        try:
            # Преобразуем часовой пояс в timedelta
            tz_sign = 1 if timezone[0] == '+' else -1
            tz_hours = int(timezone[1:3])
            tz_minutes = int(timezone[4:6])
            tz_delta = datetime.timedelta(
                hours=tz_hours * tz_sign,
                minutes=tz_minutes * tz_sign
            )
            
            # Вычисляем локальное время пользователя
            user_local_time = now_utc + tz_delta
            current_time_str = user_local_time.strftime("%H:%M")
            today_date = user_local_time.strftime("%Y-%m-%d")
            
            # Проверяем, нужно ли отправлять напоминание
            db_cursor.execute(
                """SELECT habit FROM habits 
                WHERE user_id = ? 
                AND reminder_time = ?
                AND (last_reminder_date IS NULL OR last_reminder_date != ?)""",
                (user_id, current_time_str, today_date)
            )
            habits = db_cursor.fetchall()
            
            for (habit,) in habits:
                markup = types.InlineKeyboardMarkup()
                yes_btn = types.InlineKeyboardButton("✅ Сделал", callback_data=f"done_{habit}")
                no_btn = types.InlineKeyboardButton("❌ Пропустил", callback_data=f"skip_{habit}")
                markup.add(yes_btn, no_btn)

                try:
                    sent_msg = bot.send_message(
                        user_id,
                        f"⏰ Напоминание: {habit}! Ты сегодня выполнил?",
                        reply_markup=markup
                    )

                    db_cursor.execute(
                        """UPDATE habits 
                        SET last_reminder_date = ?, 
                        last_message_id = ? 
                        WHERE user_id = ? AND habit = ?""",
                        (today_date, sent_msg.message_id, user_id, habit)
                    )
                    db_conn.commit()

                except Exception as e:
                    print(f"Ошибка при отправке пользователю {user_id}: {e}")
                    
        except Exception as e:
            print(f"Ошибка при обработке пользователя {user_id}: {e}")

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)

        if "_" not in call.data:
            return

        action, habit = call.data.split("_", 1)
        user_id = call.message.chat.id
        today = datetime.datetime.now().strftime("%Y-%m-%d")

        db_cursor.execute(
            "SELECT last_reminder_date, current_streak FROM habits WHERE user_id = ? AND habit = ?",
            (user_id, habit)
        )
        result = db_cursor.fetchone()

        if not result:
            bot.answer_callback_query(call.id, "Привычка не найдена!")
            return

        last_date, current_streak = result

        if last_date == today:
            bot.answer_callback_query(call.id, "Вы уже отмечали эту привычку сегодня!")
            return

        if action == "done":
            new_streak = current_streak + 1
            db_cursor.execute(
                """UPDATE habits 
                SET current_streak = ?, 
                    max_streak = MAX(max_streak, ?),
                    last_reminder_date = ?
                WHERE user_id = ? AND habit = ?""",
                (new_streak, new_streak, today, user_id, habit)
            )
            db_conn.commit()

            bot.send_message(
                user_id,
                f"🔥 Отлично! Текущая серия: {new_streak} дней!"
            )

        elif action == "skip":
            db_cursor.execute(
                "UPDATE habits SET current_streak = 0, last_reminder_date = ? WHERE user_id = ? AND habit = ?",
                (today, user_id, habit)
            )
            db_conn.commit()

            bot.send_message(
                user_id,
                "😢 Серия прервана. Начни заново завтра!"
            )

        bot.answer_callback_query(call.id)

    except Exception as e:
        print(f"Error in callback: {e}")
        bot.answer_callback_query(call.id, "Произошла ошибка")

@bot.message_handler(commands=['help'])
def show_help(message):
    help_text = """
📋 <b>Доступные команды:</b>

/start - Начать работу с ботом
/progress - Показать текущий прогресс
/settime - Изменить время напоминания
/timezone - Изменить часовой пояс
/help - Показать это сообщение

ℹ️ Просто введите команду или нажмите на неё в меню.
"""
    bot.send_message(message.chat.id, help_text, parse_mode='HTML')

@bot.message_handler(commands=['progress'])
def progress(message):
    try:
        db_cursor.execute(
            "SELECT habit, current_streak, max_streak FROM habits WHERE user_id = ?",
            (message.chat.id,)
        )
        habits = db_cursor.fetchall()

        if not habits:
            bot.send_message(message.chat.id, "У тебя пока нет активных привычек.")
            return

        response = "📊 Твой прогресс:\n"
        for habit, streak, max_streak in habits:
            response += f"- {habit}: текущая серия {streak} дней (рекорд: {max_streak})\n"

        bot.send_message(message.chat.id, response)

    except sqlite3.Error as e:
        print("SQLite error:", e)
        bot.send_message(message.chat.id, "Ошибка при загрузке прогресса. Попробуйте позже.")
    except Exception as e:
        print("Error:", e)
        bot.send_message(message.chat.id, "Неизвестная ошибка 😢")

@bot.message_handler(commands=['timezone'])
def change_timezone(message):
    timezone_markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    timezone_markup.add(
        types.KeyboardButton("Москва (+3)"),
        types.KeyboardButton("Киев (+2)"),
        types.KeyboardButton("Другой")
    )
    
    bot.send_message(
        message.chat.id,
        "Выберите ваш часовой пояс:",
        reply_markup=timezone_markup
    )
    bot.register_next_step_handler(message, process_timezone_change)

def process_timezone_change(message):
    timezone_map = {
        "Москва (+3)": "+03:00",
        "Киев (+2)": "+02:00"
    }
    
    if message.text in timezone_map:
        timezone = timezone_map[message.text]
    elif message.text == "Другой":
        bot.send_message(
            message.chat.id,
            "Введите ваш часовой пояс в формате ±HH:MM (например, +05:00 или -08:00):",
            reply_markup=types.ReplyKeyboardRemove()
        )
        bot.register_next_step_handler(message, process_custom_timezone)
        return
    else:
        bot.send_message(message.chat.id, "Пожалуйста, выберите вариант из предложенных")
        return change_timezone(message)
    
    db_cursor.execute(
        "UPDATE habits SET timezone = ? WHERE user_id = ?",
        (timezone, message.chat.id)
    )
    db_conn.commit()
    
    bot.send_message(
        message.chat.id,
        f"Часовой пояс успешно изменен на {timezone}",
        reply_markup=types.ReplyKeyboardRemove()
    )

def process_custom_timezone(message):
    if not re.match(r'^[+-](0[0-9]|1[0-2]):[0-5][0-9]$', message.text):
        bot.send_message(
            message.chat.id,
            "Неверный формат часового пояса. Пожалуйста, используйте формат ±HH:MM (например, +05:00 или -08:00)"
        )
        return change_timezone(message)
    
    db_cursor.execute(
        "UPDATE habits SET timezone = ? WHERE user_id = ?",
        (message.text, message.chat.id)
    )
    db_conn.commit()
    
    bot.send_message(
        message.chat.id,
        f"Часовой пояс успешно изменен на {message.text}",
        reply_markup=types.ReplyKeyboardRemove()
    )

def reminder_scheduler():
    while True:
        try:
            send_reminders()
            time.sleep(60 - datetime.datetime.now().second)
        except Exception as e:
            print(f"Ошибка в scheduler: {e}")
            time.sleep(10)

def run_bot():
    setup_commands()
    scheduler_thread = threading.Thread(target=reminder_scheduler, daemon=True)
    scheduler_thread.start()

    while True:
        try:
            print("Бот запущен и работает...")
            bot.polling(none_stop=True, interval=1, timeout=30)
        except Exception as e:
            print(f"Произошла ошибка: {str(e)}")
            print("Попытка перезапуска через 10 секунд...")
            time.sleep(10)

if __name__ == "__main__":
    try:
        flask_thread = threading.Thread(
            target=app.run,
            kwargs={'host': '0.0.0.0', 'port': int(os.environ.get('PORT', 5000))},
            daemon=True
        )
        flask_thread.start()
        
        run_bot()
    finally:
        db_conn.close()
