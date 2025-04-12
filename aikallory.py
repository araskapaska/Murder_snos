import telebot
from telebot import types
import requests
import json
import os

# Токен твоего бота от BotFather
API_TOKEN = "7771305300:AAHgd-M-EYmL3kq9XSn3dHTDDNNkhOWaUhU"
bot = telebot.TeleBot(API_TOKEN)

# Ключ для OpenRouter
OPENROUTER_API_KEY = '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'

# Подключение к базе данных SQLite
conn = sqlite3.connect('calorie_tracker.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        daily_limit INTEGER DEFAULT 1200,
        current_date TEXT
    )
''')
cursor.execute('''
    CREATE TABLE IF NOT EXISTS food_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        date TEXT,
        food_name TEXT,
        calories INTEGER,
        protein INTEGER,
        fat INTEGER,
        carbs INTEGER
    )
''')
conn.commit()

# Функция для получения текущей даты
def get_current_date():
    return str(date.today())

# Функция для проверки и обновления даты
def check_and_reset_date(user_id):
    cursor.execute('SELECT current_date FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    current_date = get_current_date()
    
    if result is None:
        cursor.execute('INSERT INTO users (user_id, current_date) VALUES (?, ?)', 
                      (user_id, current_date))
        conn.commit()
    elif result[0] != current_date:
        cursor.execute('UPDATE users SET current_date = ?, daily_limit = 1200 WHERE user_id = ?', 
                      (current_date, user_id))
        cursor.execute('DELETE FROM food_log WHERE user_id = ? AND date != ?', 
                      (user_id, current_date))
        conn.commit()

# Функция для получения текущего потребления калорий
def get_daily_calories(user_id):
    current_date = get_current_date()
    cursor.execute('SELECT SUM(calories) FROM food_log WHERE user_id = ? AND date = ?', 
                  (user_id, current_date))
    result = cursor.fetchone()
    return result[0] if result[0] is not None else 0

# Функция для запроса к OpenRouter
def get_food_info(food_name):
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": "google/gemini-2.5-pro-exp-03-25:free",
            "messages": [
                {
                    "role": "user",
                    "content": f"Привет, ты ассистент в моём приложении для мерки каллорий. Пользователь съел: {food_name}. Пришли в формате JSON приблизительные данные о продукте (к|б|ж|у)"
                }
            ]
        })
    )
    
    if response.status_code == 200:
        data = response.json()
        try:
            # Предполагаем, что ответ приходит в формате JSON внутри content
            content = json.loads(data['choices'][0]['message']['content'])
            return content
        except:
            return None
    return None

# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    check_and_reset_date(user_id)
    
    # Создание клавиатуры
    markup = telebot.types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = telebot.types.KeyboardButton("Можно")
    btn2 = telebot.types.KeyboardButton("Назначить другой рацион")
    markup.add(btn1, btn2)
    
    daily_calories = get_daily_calories(user_id)
    cursor.execute('SELECT daily_limit FROM users WHERE user_id = ?', (user_id,))
    limit = cursor.fetchone()[0]
    
    bot.reply_to(message, 
                f"Сегодня ты съел: {daily_calories} ккал (из {limit} ккал)",
                reply_markup=markup)

# Обработчик кнопок
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    check_and_reset_date(user_id)
    
    cursor.execute('SELECT daily_limit FROM users WHERE user_id = ?', (user_id,))
    limit = cursor.fetchone()[0]
    
    if message.text == "Можно":
        bot.reply_to(message, "Напиши, что ты съел")
        bot.register_next_step_handler(message, add_food)
    elif message.text == "Назначить другой рацион":
        bot.reply_to(message, "Введи новый лимит калорий (в ккал)")
        bot.register_next_step_handler(message, set_new_limit)
    else:
        bot.reply_to(message, "Пожалуйста, используй кнопки")

# Функция добавления еды
def add_food(message):
    user_id = message.from_user.id
    food_name = message.text
    current_date = get_current_date()
    
    # Запрос к OpenRouter
    food_info = get_food_info(food_name)
    
    if food_info and all(key in food_info for key in ['к', 'б', 'ж', 'у']):
        calories = food_info['к']
        protein = food_info['б']
        fat = food_info['ж']
        carbs = food_info['у']
        
        # Сохранение в базу
        cursor.execute('''
            INSERT INTO food_log (user_id, date, food_name, calories, protein, fat, carbs)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, current_date, food_name, calories, protein, fat, carbs))
        conn.commit()
        
        # Проверка лимита
        daily_calories = get_daily_calories(user_id)
        cursor.execute('SELECT daily_limit FROM users WHERE user_id = ?', (user_id,))
        limit = cursor.fetchone()[0]
        
        response = f"Добавлено: {food_name}\n"
        response += f"Калории: {calories} ккал\n"
        response += f"Белки: {protein} г\n"
        response += f"Жиры: {fat} г\n"
        response += f"Углеводы: {carbs} г\n"
        response += f"Сегодня съедено: {daily_calories} ккал (из {limit} ккал)"
        
        if daily_calories > limit:
            response += "\n⚠️ Внимание! Ты превысил дневной лимит калорий!"
        
        bot.reply_to(message, response)
    else:
        bot.reply_to(message, "Не удалось получить информацию о продукте. Попробуй еще раз.")

# Функция установки нового лимита
def set_new_limit(message):
    user_id = message.from_user.id
    try:
        new_limit = int(message.text)
        if new_limit > 0:
            cursor.execute('UPDATE users SET daily_limit = ? WHERE user_id = ?', 
                         (new_limit, user_id))
            conn.commit()
            bot.reply_to(message, f"Новый лимит установлен: {new_limit} ккал")
        else:
            bot.reply_to(message, "Лимит должен быть положительным числом")
    except ValueError:
        bot.reply_to(message, "Пожалуйста, введи число")

# Запуск бота
bot.polling()
