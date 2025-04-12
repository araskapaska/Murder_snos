import telebot
import requests
import json
from datetime import datetime, date
import os

# Инициализация бота
API_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN'  # Замените на ваш токен Telegram бота
bot = telebot.TeleBot(API_TOKEN)

# Ключ для OpenRouter
OPENROUTER_API_KEY = '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'

# Путь к JSON-файлу для хранения данных
DATA_FILE = 'calorie_tracker.json'

# Функция для загрузки данных из JSON
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {"users": {}}

# Функция для сохранения данных в JSON
def save_data(data):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# Функция для получения текущей даты
def get_current_date():
    return str(date.today())

# Функция для проверки и обновления даты
def check_and_reset_date(user_id):
    data = load_data()
    current_date = get_current_date()
    user_id = str(user_id)  # Ключи в JSON — строки
    
    if user_id not in data["users"]:
        data["users"][user_id] = {
            "daily_limit": 1200,
            "current_date": current_date,
            "food_log": []
        }
    elif data["users"][user_id]["current_date"] != current_date:
        data["users"][user_id]["current_date"] = current_date
        data["users"][user_id]["food_log"] = []  # Сброс лога за новый день
        data["users"][user_id]["daily_limit"] = 1200  # Сброс лимита
    
    save_data(data)
    return data

# Функция для получения текущего потребления калорий
def get_daily_calories(user_id):
    data = load_data()
    user_id = str(user_id)
    if user_id not in data["users"]:
        return 0
    
    total_calories = sum(item["calories"] for item in data["users"][user_id]["food_log"])
    return total_calories

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
    data = load_data()
    limit = data["users"][str(user_id)]["daily_limit"]
    
    bot.reply_to(message, 
                f"Сегодня ты съел: {daily_calories} ккал (из {limit} ккал)",
                reply_markup=markup)

# Обработчик кнопок
@bot.message_handler(content_types=['text'])
def handle_text(message):
    user_id = message.from_user.id
    check_and_reset_date(user_id)
    
    data = load_data()
    limit = data["users"][str(user_id)]["daily_limit"]
    
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
        
        # Сохранение в JSON
        data = load_data()
        user_id = str(user_id)
        food_entry = {
            "date": current_date,
            "food_name": food_name,
            "calories": calories,
            "protein": protein,
            "fat": fat,
            "carbs": carbs
        }
        data["users"][user_id]["food_log"].append(food_entry)
        save_data(data)
        
        # Проверка лимита
        daily_calories = get_daily_calories(user_id)
        limit = data["users"][user_id]["daily_limit"]
        
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
            data = load_data()
            data["users"][str(user_id)]["daily_limit"] = new_limit
            save_data(data)
            bot.reply_to(message, f"Новый лимит установлен: {new_limit} ккал")
        else:
            bot.reply_to(message, "Лимит должен быть положительным числом")
    except ValueError:
        bot.reply_to(message, "Пожалуйста, введи число")

# Запуск бота
bot.polling()
