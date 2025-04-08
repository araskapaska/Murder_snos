import telebot
from telebot import types
import requests
import json
import os

# Токен твоего бота от BotFather
BOT_TOKEN = "7285681448:AAF0chLLhp4k0uCJbaYn_-yO09wSY1wY-aw"
# Твой ключ от OpenRouter
OPENROUTER_API_KEY = "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"
IMGBB_API_KEY = "5acb9592686c713a75ffca1451572e4d"

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

# Словарь для хранения данных пользователей
users_data = {}

# Главное меню
def main_menu(chat_id):
    user_data = users_data.get(chat_id, {"calories": 0, "water": 0})
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    btn1 = types.KeyboardButton("Я съел что-то 🍽️")
    btn2 = types.KeyboardButton("Попил воды 💧")
    markup.add(btn1, btn2)
    
    calories = user_data["calories"]
    water = user_data["water"]
    bot.send_message(chat_id, 
                    f"Твои калории: {calories} ккал\n"
                    f"Выпито воды: {water} мл / 2000 мл",
                    reply_markup=markup)

# Обработка команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    chat_id = message.chat.id
    if chat_id not in users_data:
        users_data[chat_id] = {"calories": 0, "water": 0}
    bot.reply_to(message, "Привет! Я помогу считать калории и воду 😊")
    main_menu(chat_id)

# Обработка кнопок меню
@bot.message_handler(content_types=['text'])
def handle_text(message):
    chat_id = message.chat.id
    if chat_id not in users_data:
        users_data[chat_id] = {"calories": 0, "water": 0}
    
    if message.text == "Я съел что-то 🍽️":
        bot.send_message(chat_id, "Пришли фото того, что ты съел!")
    elif message.text == "Попил воды 💧":
        bot.send_message(chat_id, "Сколько мл воды ты выпил?")
    else:
        main_menu(chat_id)

# Обработка фото
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    chat_id = message.chat.id
    
    # Получаем файл фото
    file_id = message.photo[-1].file_id
    file_info = bot.get_file(file_id)
    file_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_info.file_path}"
    
    # Скачиваем фото
    file_response = requests.get(file_url)
    if file_response.status_code != 200:
        bot.send_message(chat_id, "Не удалось скачать фото 😔")
        return
    
    # Загружаем на imgbb
    imgbb_url = "https://api.imgbb.com/1/upload"
    imgbb_payload = {
        "key": IMGBB_API_KEY,
        "image": file_response.content,
    }
    imgbb_response = requests.post(imgbb_url, files={"image": file_response.content})
    
    if imgbb_response.status_code != 200:
        bot.send_message(chat_id, "Не удалось загрузить фото на хостинг 😔")
        return
    
    image_url = imgbb_response.json()["data"]["url"]
    
    # Запрос к OpenRouter
    response = requests.post(
        url="https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost",
            "X-Title": "CalorieCounterBot"
        },
        data=json.dumps({
            "model": "google/gemini-2.5-pro-exp-03-25:free",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Привет, ты ассистент в моём приложении, которое помогает считать калории. Вот фото, что съел пользователь. Опиши, что это, чем оно полезно и сколько примерно в нём калорий. Без лишнего текста."
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        }
                    ]
                }
            ]
        })
    )
    
    # Обработка ответа от нейросети
    if response.status_code == 200:
        result = response.json()
        answer = result["choices"][0]["message"]["content"]
        
        # Парсим калории из ответа
        try:
            calories = int(''.join(filter(str.isdigit, answer.split("калорий")[0].split()[-1])))
            users_data[chat_id]["calories"] += calories
        except:
            calories = 0
        
        bot.send_message(chat_id, answer)
        main_menu(chat_id)
    else:
        bot.send_message(chat_id, "Не получилось распознать еду 😔 Попробуй ещё раз!")

# Обработка ввода воды
@bot.message_handler(content_types=['text'], regexp=r'^\d+$')
def handle_water(message):
    chat_id = message.chat.id
    water_ml = int(message.text)
    users_data[chat_id]["water"] += water_ml
    
    water_total = users_data[chat_id]["water"]
    bot.send_message(chat_id, f"Записал! Ты выпил {water_ml} мл. Всего: {water_total}/2000 мл 💧")
    if water_total >= 2000:
        bot.send_message(chat_id, "Ура! Цель на день достигнута 🎉")
    main_menu(chat_id)

# Запуск бота
print(" bot") 
bot.polling(none_stop=True)
