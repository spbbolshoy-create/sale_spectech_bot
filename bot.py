import telebot
import sqlite3
import os
import datetime
import signal
import sys
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
import database as db
import config

bot = telebot.TeleBot(config.BOT_TOKEN)

# Состояния для добавления объявления
user_states = {}

# Хранилище для пагинации (в памяти)
user_pagination = {}

# Функция для резервного копирования БД
def backup_database():
    """Создание резервной копии базы данных"""
    try:
        if os.path.exists('cargo_bot.db'):
            backup_name = f"backup/cargo_bot_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
            os.makedirs('backup', exist_ok=True)
            import shutil
            shutil.copy2('cargo_bot.db', backup_name)
            print(f"Создан бэкап: {backup_name}")
    except Exception as e:
        print(f"Ошибка при создании бэкапа: {e}")

# Функция для корректного завершения работы
def signal_handler(sig, frame):
    print("\n\n✅ Бот корректно остановлен")
    sys.exit(0)

# Регистрируем обработчик сигналов
signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

# Клавиатуры
def main_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('📋 Посмотреть объявления'))
    keyboard.add(KeyboardButton('➕ Добавить объявление'))
    keyboard.add(KeyboardButton('📞 Мои объявления'))
    return keyboard

def admin_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('📋 Все объявления'))
    keyboard.add(KeyboardButton('⏳ Модерация'))
    keyboard.add(KeyboardButton('📊 Статистика'))
    keyboard.add(KeyboardButton('📝 Список номеров'))
    keyboard.add(KeyboardButton('👤 Пользовательский режим'))
    return keyboard

def user_admin_keyboard():
    """Клавиатура для админа в пользовательском режиме"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('📋 Посмотреть объявления'))
    keyboard.add(KeyboardButton('➕ Добавить объявление'))
    keyboard.add(KeyboardButton('📞 Мои объявления'))
    keyboard.add(KeyboardButton('👑 Админ-режим'))
    return keyboard

def cancel_keyboard():
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('❌ Отмена'))
    return keyboard

def photo_choice_keyboard():
    """Клавиатура для выбора после добавления фото"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add(KeyboardButton('📸 Добавить еще фото'))
    keyboard.add(KeyboardButton('✅ Завершить добавление фото'))
    keyboard.add(KeyboardButton('❌ Отмена'))
    return keyboard

# Команда /start
@bot.message_handler(commands=['start'])
def start_command(message):
    try:
        user_id = message.from_user.id
        username = message.from_user.username
        full_name = message.from_user.full_name
        
        # Добавляем пользователя в БД
        db.add_user(user_id, username, full_name)
        
        # Проверяем админа
        if user_id in config.ADMIN_IDS:
            bot.send_message(message.chat.id, "👑 Добро пожаловать, администратор!", reply_markup=admin_keyboard())
        else:
            bot.send_message(message.chat.id, "🚛 Добро пожаловать в бот грузовой техники!", reply_markup=main_keyboard())
    except Exception as e:
        print(f"Ошибка в start_command: {e}")

# Функция для создания клавиатуры пагинации
def create_pagination_keyboard(page, total_pages, prefix="view"):
    keyboard = InlineKeyboardMarkup(row_width=3)
    
    buttons = []
    if page > 0:
        buttons.append(InlineKeyboardButton("⬅️ Назад", callback_data=f"{prefix}_{page-1}"))
    
    buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="current_page"))
    
    if page < total_pages - 1:
        buttons.append(InlineKeyboardButton("Вперед ➡️", callback_data=f"{prefix}_{page+1}"))
    
    keyboard.add(*buttons)
    return keyboard

# Функция для отправки объявления с медиа-группой
def send_ad_with_media_group(chat_id, caption, photo_ids, keyboard=None, parse_mode='Markdown'):
    """Отправляет объявление с группой фотографий и возвращает IDs сообщений"""
    message_ids = []
    try:
        if not photo_ids:
            # Если нет фото, отправляем просто текст
            if keyboard:
                msg = bot.send_message(chat_id, caption, reply_markup=keyboard, parse_mode=parse_mode)
            else:
                msg = bot.send_message(chat_id, caption, parse_mode=parse_mode)
            message_ids.append(msg.message_id)
            return message_ids

        # Если photo_ids - это строка (старый формат), преобразуем в список
        if isinstance(photo_ids, str):
            if photo_ids.startswith('[') and photo_ids.endswith(']'):
                photo_ids = eval(photo_ids)
            else:
                photo_ids = [photo_ids]

        if len(photo_ids) == 1:
            # Если одна фотография, отправляем с подписью
            if keyboard:
                msg = bot.send_photo(chat_id, photo_ids[0], caption=caption, reply_markup=keyboard, parse_mode=parse_mode)
            else:
                msg = bot.send_photo(chat_id, photo_ids[0], caption=caption, parse_mode=parse_mode)
            message_ids.append(msg.message_id)
        else:
            # Если несколько фотографий, создаем медиа-группу
            media_group = []
            for i, photo_id in enumerate(photo_ids):
                if i == 0:
                    # Первое фото с подписью
                    media_group.append(InputMediaPhoto(photo_id, caption=caption, parse_mode=parse_mode))
                else:
                    # Остальные фото без подписи
                    media_group.append(InputMediaPhoto(photo_id))
            
            # Отправляем медиа-группу
            messages = bot.send_media_group(chat_id, media_group)
            for msg in messages:
                message_ids.append(msg.message_id)
            
            # Отправляем клавиатуру отдельным сообщением
            if keyboard:
                msg = bot.send_message(chat_id, "💡 Используйте кнопки для навигации:", reply_markup=keyboard)
                message_ids.append(msg.message_id)
                
    except Exception as e:
        print(f"Ошибка в send_ad_with_media_group: {e}")
        # Fallback: отправляем текстовое сообщение
        if keyboard:
            msg = bot.send_message(chat_id, caption, reply_markup=keyboard, parse_mode=parse_mode)
        else:
            msg = bot.send_message(chat_id, caption, parse_mode=parse_mode)
        message_ids.append(msg.message_id)
    
    return message_ids

# Функция для удаления предыдущих сообщений объявления
def delete_previous_ad_messages(chat_id, user_id):
    """Удаляет все сообщения предыдущего объявления"""
    try:
        if user_id in user_pagination and 'current_message_ids' in user_pagination[user_id]:
            for msg_id in user_pagination[user_id]['current_message_ids']:
                try:
                    bot.delete_message(chat_id, msg_id)
                except Exception as e:
                    # Если сообщение уже удалено или недоступно, игнорируем ошибку
                    pass
            user_pagination[user_id]['current_message_ids'] = []
    except Exception as e:
        print(f"Ошибка при удалении предыдущих сообщений: {e}")

# Просмотр одобренных объявлений с пагинацией
@bot.message_handler(func=lambda message: message.text == '📋 Посмотреть объявления')
def show_ads(message):
    try:
        ads = db.get_approved_ads()
        
        if not ads:
            bot.send_message(message.chat.id, "😔 Пока нет объявлений.")
            return
        
        # Сохраняем объявления для пользователя
        user_id = message.from_user.id
        user_pagination[user_id] = {
            'ads': ads,
            'total_pages': len(ads),
            'current_page': 0,
            'type': 'view',
            'current_message_ids': []  # Для хранения ID текущих сообщений
        }
        
        # Показываем первое объявление
        show_ad_page(message.chat.id, user_id, 0)
    except Exception as e:
        print(f"Ошибка в show_ads: {e}")
        bot.send_message(message.chat.id, "Произошла ошибка при загрузке объявлений.")

# Функция показа конкретной страницы с объявлением (для пользователей)
def show_ad_page(chat_id, user_id, page):
    try:
        if user_id not in user_pagination or user_pagination[user_id]['type'] != 'view':
            bot.send_message(chat_id, "Сессия просмотра истекла. Начните заново.")
            return
        
        # Удаляем предыдущее объявление
        delete_previous_ad_messages(chat_id, user_id)
        
        user_data = user_pagination[user_id]
        ads = user_data['ads']
        total_pages = user_data['total_pages']
        
        if page < 0 or page >= total_pages:
            bot.send_message(chat_id, "Объявление не найдено.")
            return
        
        user_data['current_page'] = page
        ad = ads[page]
        
        # Структура ad зависит от запроса
        if len(ad) >= 10:  # Для get_approved_ads
            ad_id, user_id_ad, title, description, photo_id, price, contact, created_at, status, admin_contact, username = ad
        else:  # Для get_user_ads
            ad_id, user_id_ad, title, description, photo_id, price, contact, created_at, status, admin_contact = ad
            username = "Вы"
        
        # Красивое форматирование с "воздухом"
        caption = f"""
🚛 *{title}*

📝 *Описание:*
{description}

💰 *Стоимость:*
{price}

🆔 *Номер объявления:* `{ad_id}`

📞 *Для связи:*
Напишите администратору @{config.ADMIN_USERNAME} и укажите номер объявления
"""
        
        keyboard = create_pagination_keyboard(page, total_pages, "view")
        
        # Используем новую функцию для отправки с медиа-группой
        message_ids = send_ad_with_media_group(chat_id, caption, photo_id, keyboard)
        
        # Сохраняем ID сообщений для последующего удаления
        user_pagination[user_id]['current_message_ids'] = message_ids
        
    except Exception as e:
        print(f"Ошибка в show_ad_page: {e}")

# Обработка пагинации для просмотра объявлений
@bot.callback_query_handler(func=lambda call: call.data.startswith('view_'))
def handle_view_pagination(call):
    try:
        user_id = call.from_user.id
        page = int(call.data.split('_')[1])
        
        # Показываем новую страницу (старое объявление удалится в show_ad_page)
        show_ad_page(call.message.chat.id, user_id, page)
    except Exception as e:
        print(f"Ошибка в handle_view_pagination: {e}")

# Начало добавления объявления
@bot.message_handler(func=lambda message: message.text == '➕ Добавить объявление')
def start_add_ad(message):
    try:
        user_states[message.from_user.id] = {
            'step': 'title',
            'photos': []  # Список для хранения фото
        }
        
        help_text = """
📝 *Создание объявления - Шаг 1/5*

✏️ *Введите заголовок объявления:*

💡 *Примеры хороших заголовков:*
• Аренда самосвала HOWO 371
• Продажа грузовика MAN TGS 28.480
• Лизинг автокрана Liebherr LTM 1050
• Сдам в аренду экскаватор-погрузчик JCB 4CX

🚫 *Нельзя:* 
• "Продам машину" (слишком общее)
• "Срочно!!!" (избегайте восклицаний)
• "Лучшая цена" (неинформативно)
"""
        
        bot.send_message(message.chat.id, help_text, parse_mode='Markdown', reply_markup=cancel_keyboard())
    except Exception as e:
        print(f"Ошибка в start_add_ad: {e}")

# Обработка отмены
@bot.message_handler(func=lambda message: message.text == '❌ Отмена')
def cancel_addition(message):
    user_id = message.from_user.id
    if user_id in user_states:
        del user_states[user_id]
    
    # Возвращаем правильную клавиатуру в зависимости от пользователя
    if user_id in config.ADMIN_IDS:
        # Проверяем, в каком режиме находится админ
        if 'user_mode' in user_states.get(user_id, {}):
            bot.send_message(message.chat.id, "❌ Добавление объявления отменено.", reply_markup=user_admin_keyboard())
        else:
            bot.send_message(message.chat.id, "❌ Добавление объявления отменено.", reply_markup=admin_keyboard())
    else:
        bot.send_message(message.chat.id, "❌ Добавление объявления отменено.", reply_markup=main_keyboard())

# Обработка шагов добавления объявления
@bot.message_handler(func=lambda message: message.from_user.id in user_states and message.text != '❌ Отмена' and message.text != '📸 Добавить еще фото' and message.text != '✅ Завершить добавление фото')
def handle_ad_steps(message):
    try:
        user_id = message.from_user.id
        state = user_states.get(user_id, {})
        
        if state.get('step') == 'title':
            if len(message.text) < 5:
                bot.send_message(message.chat.id, "❌ Заголовок слишком короткий. Минимум 5 символов. Попробуйте еще раз:")
                return
                
            user_states[user_id] = {
                'step': 'description', 
                'title': message.text,
                'photos': state.get('photos', [])
            }
            
            help_text = """
📝 *Создание объявления - Шаг 2/5*

📄 *Введите описание техники:*

💡 *Что указать в описании:*
• Год выпуска
• Состояние (новый, б/у, после капремонта)
• Технические характеристики
• Дополнительное оборудование
• Особенности и преимущества

📋 *Пример хорошего описания:*
"Грузовик 2020 года, пробег 150 000 км. Отличное техническое состояние, регулярное ТО. 
Полная комплектация: кондиционер, круиз-контроль, спальное место. 
Возможна аренда с водителем."
"""
            bot.send_message(message.chat.id, help_text, parse_mode='Markdown', reply_markup=cancel_keyboard())
        
        elif state.get('step') == 'description':
            if len(message.text) < 20:
                bot.send_message(message.chat.id, "❌ Описание слишком короткое. Минимум 20 символов. Опишите технику подробнее:")
                return
                
            user_states[user_id] = {
                'step': 'price', 
                'title': state['title'], 
                'description': message.text,
                'photos': state.get('photos', [])
            }
            
            help_text = """
📝 *Создание объявления - Шаг 3/5*

💰 *Введите цену или условия аренды/лизинга:*

💡 *Примеры правильного оформления:*
• *Аренда:* 15 000 руб/сутки
• *Продажа:* 2 500 000 руб
• *Лизинг:* 150 000 руб/месяц
• *Обмен:* рассмотрю варианты

📋 *Можно указать несколько вариантов:*
"Аренда: 25 000 руб/сутки
Продажа: 4 800 000 руб
Лизинг: 200 000 руб/месяц"
"""
            bot.send_message(message.chat.id, help_text, parse_mode='Markdown', reply_markup=cancel_keyboard())
        
        elif state.get('step') == 'price':
            user_states[user_id] = {
                'step': 'contact', 
                'title': state['title'], 
                'description': state['description'], 
                'price': message.text,
                'photos': state.get('photos', [])
            }
            
            help_text = """
📝 *Создание объявления - Шаг 4/5*

📞 *Введите ваши контактные данные:*

💡 *Рекомендуемый формат:*
• Телефон: +7 XXX XXX-XX-XX
• Telegram: @ваш_username
• Email: example@mail.ru

🚫 *Не публикуйте:* 
• Полный номер телефона без маски
• Личные адреса
• Другую личную информацию

📋 *Пример:*
"Телефон: +7 912 345-67-89
Telegram: @ivan_ivanov"
"""
            bot.send_message(message.chat.id, help_text, parse_mode='Markdown', reply_markup=cancel_keyboard())
        
        elif state.get('step') == 'contact':
            user_states[user_id] = {
                'step': 'photo', 
                'title': state['title'], 
                'description': state['description'], 
                'price': state['price'], 
                'contact': message.text,
                'photos': state.get('photos', [])
            }
            
            help_text = """
📝 *Создание объявления - Шаг 5/5*

📸 *Отправьте фото техники:*

💡 *Рекомендации по фото:*
• Хорошее освещение
• Четкое изображение
• Несколько ракурсов
• Основные узлы и агрегаты

🖼 *Можно добавить до 5 фотографий*
📎 *Отправьте первое фото*
"""
            bot.send_message(message.chat.id, help_text, parse_mode='Markdown', reply_markup=cancel_keyboard())
            
    except Exception as e:
        print(f"Ошибка в handle_ad_steps: {e}")

# Обработка фото
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        user_id = message.from_user.id
        state = user_states.get(user_id, {})
        
        if state.get('step') == 'photo':
            photo_id = message.photo[-1].file_id
            
            # Добавляем фото в список
            if 'photos' not in state:
                state['photos'] = []
            
            state['photos'].append(photo_id)
            user_states[user_id] = state
            
            photo_count = len(state['photos'])
            
            if photo_count >= 5:
                # Достигнут лимит фото
                help_text = f"""
📸 *Добавлено {photo_count} из 5 фото*

✅ *Максимальное количество фото достигнуто*

Вы можете:
• ✅ Завершить добавление фото и отправить объявление
• ❌ Отменить создание объявления
"""
                bot.send_message(message.chat.id, help_text, parse_mode='Markdown', reply_markup=photo_choice_keyboard())
            else:
                # Можно добавить еще фото
                help_text = f"""
📸 *Добавлено {photo_count} из 5 фото*

Вы можете:
• 📸 Добавить еще фото
• ✅ Завершить добавление фото и отправить объявление
• ❌ Отменить создание объявления
"""
                bot.send_message(message.chat.id, help_text, parse_mode='Markdown', reply_markup=photo_choice_keyboard())
                
    except Exception as e:
        print(f"Ошибка в handle_photo: {e}")

# Обработка завершения добавления фото
@bot.message_handler(func=lambda message: message.text == '✅ Завершить добавление фото' and message.from_user.id in user_states)
def finish_photos(message):
    try:
        user_id = message.from_user.id
        state = user_states.get(user_id, {})
        
        if state.get('step') == 'photo' and state.get('photos'):
            # Сохраняем объявление в БД (статус 'pending')
            # Сохраняем список фото как JSON строку
            photo_ids_str = str(state['photos'])
            
            db.add_ad(user_id, state['title'], state['description'], photo_ids_str, state['price'], state['contact'])
            
            # Очищаем состояние
            del user_states[user_id]
            
            # Уведомляем админа о новом объявлении
            notify_admin_about_new_ad(user_id, state['title'])
            
            # Определяем правильную клавиатуру для ответа
            if user_id in config.ADMIN_IDS:
                # Если админ находится в пользовательском режиме
                if any(msg.text == '👤 Пользовательский режим' for msg in [message]):
                    bot.send_message(message.chat.id, "✅ Объявление успешно отправлено на модерацию!", reply_markup=user_admin_keyboard())
                else:
                    bot.send_message(message.chat.id, "✅ Объявление успешно отправлено на модерацию!", reply_markup=admin_keyboard())
            else:
                bot.send_message(message.chat.id, "✅ Объявление успешно отправлено на модерацию!", reply_markup=main_keyboard())
                
        else:
            bot.send_message(message.chat.id, "❌ Сначала добавьте хотя бы одно фото.", reply_markup=cancel_keyboard())
            
    except Exception as e:
        print(f"Ошибка в finish_photos: {e}")

# Обработка добавления еще фото
@bot.message_handler(func=lambda message: message.text == '📸 Добавить еще фото' and message.from_user.id in user_states)
def add_more_photos(message):
    try:
        user_id = message.from_user.id
        state = user_states.get(user_id, {})
        
        if state.get('step') == 'photo':
            photo_count = len(state.get('photos', []))
            
            if photo_count >= 5:
                bot.send_message(message.chat.id, "❌ Достигнут лимит в 5 фото. Завершите добавление.", reply_markup=photo_choice_keyboard())
            else:
                help_text = f"""
📸 *Добавлено {photo_count} из 5 фото*

Отправьте следующее фото:
"""
                bot.send_message(message.chat.id, help_text, parse_mode='Markdown', reply_markup=photo_choice_keyboard())
                
    except Exception as e:
        print(f"Ошибка в add_more_photos: {e}")

# Уведомление админа о новом объявлении
def notify_admin_about_new_ad(user_id, title):
    try:
        for admin_id in config.ADMIN_IDS:
            bot.send_message(admin_id, f"🆕 Новое объявление на модерацию!\n\nЗаголовок: {title}\n\nИспользуйте раздел '⏳ Модерация' для просмотра.")
    except Exception as e:
        print(f"Ошибка в notify_admin_about_new_ad: {e}")

# Мои объявления с пагинацией
@bot.message_handler(func=lambda message: message.text == '📞 Мои объявления')
def my_ads(message):
    try:
        user_id = message.from_user.id
        ads = db.get_user_ads(user_id)
        
        if not ads:
            bot.send_message(message.chat.id, "У вас пока нет объявлений.")
            return
        
        # Сохраняем объявления для пользователя
        user_pagination[user_id] = {
            'ads': ads,
            'total_pages': len(ads),
            'current_page': 0,
            'type': 'my',
            'current_message_ids': []  # Для хранения ID текущих сообщений
        }
        
        # Показываем первое объявление
        show_my_ad_page(message.chat.id, user_id, 0)
    except Exception as e:
        print(f"Ошибка в my_ads: {e}")

# Функция показа конкретной страницы с моим объявлением
def show_my_ad_page(chat_id, user_id, page):
    try:
        if user_id not in user_pagination or user_pagination[user_id]['type'] != 'my':
            bot.send_message(chat_id, "Сессия просмотра истекла. Начните заново.")
            return
        
        # Удаляем предыдущее объявление
        delete_previous_ad_messages(chat_id, user_id)
        
        user_data = user_pagination[user_id]
        ads = user_data['ads']
        total_pages = user_data['total_pages']
        
        if page < 0 or page >= total_pages:
            bot.send_message(chat_id, "Объявление не найдено.")
            return
        
        user_data['current_page'] = page
        ad = ads[page]
        ad_id, user_id_ad, title, description, photo_id, price, contact, created_at, status, admin_contact = ad
        
        status_icons = {
            'pending': '⏳',
            'approved': '✅',
            'rejected': '❌'
        }
        
        caption = f"""
🚛 *{title}*

📝 *Описание:*
{description}

💰 *Стоимость:*
{price}

📞 *Ваши контакты:*
{contact}

🆔 *Номер объявления:* `{ad_id}`

📊 *Статус:* {status_icons.get(status, '❓')} {status}
"""
        
        keyboard = InlineKeyboardMarkup(row_width=3)
        
        # Кнопки пагинации
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"my_{page-1}"))
        
        pagination_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="current"))
        
        if page < total_pages - 1:
            pagination_buttons.append(InlineKeyboardButton("➡️", callback_data=f"my_{page+1}"))
        
        keyboard.add(*pagination_buttons)
        
        # Кнопка удаления
        keyboard.add(InlineKeyboardButton("❌ Удалить", callback_data=f"delete_{ad_id}"))
        
        # Используем новую функцию для отправки с медиа-группой
        message_ids = send_ad_with_media_group(chat_id, caption, photo_id, keyboard)
        
        # Сохраняем ID сообщений для последующего удаления
        user_pagination[user_id]['current_message_ids'] = message_ids
        
    except Exception as e:
        print(f"Ошибка в show_my_ad_page: {e}")

# Обработка пагинации для моих объявлений
@bot.callback_query_handler(func=lambda call: call.data.startswith('my_'))
def handle_my_pagination(call):
    try:
        user_id = call.from_user.id
        page = int(call.data.split('_')[1])
        
        # Показываем новую страницу (старое объявление удалится в show_my_ad_page)
        show_my_ad_page(call.message.chat.id, user_id, page)
    except Exception as e:
        print(f"Ошибка в handle_my_pagination: {e}")

# Модерация объявлений для админа
@bot.message_handler(func=lambda message: message.text == '⏳ Модерация' and message.from_user.id in config.ADMIN_IDS)
def admin_moderation(message):
    try:
        ads = db.get_pending_ads()
        
        if not ads:
            bot.send_message(message.chat.id, "Нет объявлений на модерации.")
            return
        
        # Сохраняем объявления для админа
        user_id = message.from_user.id
        user_pagination[user_id] = {
            'ads': ads,
            'total_pages': len(ads),
            'current_page': 0,
            'type': 'mod',
            'current_message_ids': []  # Для хранения ID текущих сообщений
        }
        
        # Показываем первое объявление на модерации
        show_moderation_ad_page(message.chat.id, user_id, 0)
    except Exception as e:
        print(f"Ошибка в admin_moderation: {e}")

# Функция показа объявления на модерации
def show_moderation_ad_page(chat_id, user_id, page):
    try:
        if user_id not in user_pagination or user_pagination[user_id]['type'] != 'mod':
            bot.send_message(chat_id, "Сессия модерации истекла. Начните заново.")
            return
        
        # Удаляем предыдущее объявление
        delete_previous_ad_messages(chat_id, user_id)
        
        user_data = user_pagination[user_id]
        ads = user_data['ads']
        total_pages = user_data['total_pages']
        
        if page < 0 or page >= total_pages:
            bot.send_message(chat_id, "Объявление не найдено.")
            return
        
        user_data['current_page'] = page
        ad = ads[page]
        ad_id, user_id_ad, title, description, photo_id, price, contact, created_at, status, admin_contact, username, telegram_id = ad
        
        caption = f"""
🆕 *ОБЪЯВЛЕНИЕ НА МОДЕРАЦИЮ*

🚛 *{title}*

📝 *Описание:*
{description}

💰 *Стоимость:*
{price}

👤 *Автор:* @{username} (ID: {telegram_id})
📞 *Контакты:* {contact}

🆔 *Номер объявления:* `{ad_id}`
"""
        
        keyboard = InlineKeyboardMarkup(row_width=3)
        
        # Кнопки пагинации
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"mod_{page-1}"))
        
        pagination_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="current"))
        
        if page < total_pages - 1:
            pagination_buttons.append(InlineKeyboardButton("➡️", callback_data=f"mod_{page+1}"))
        
        keyboard.add(*pagination_buttons)
        
        # Кнопки модерации
        keyboard.add(
            InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{ad_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{ad_id}")
        )
        
        # Используем новую функцию для отправки с медиа-группой
        message_ids = send_ad_with_media_group(chat_id, caption, photo_id, keyboard)
        
        # Сохраняем ID сообщений для последующего удаления
        user_pagination[user_id]['current_message_ids'] = message_ids
        
    except Exception as e:
        print(f"Ошибка в show_moderation_ad_page: {e}")

# Обработка пагинации для модерации
@bot.callback_query_handler(func=lambda call: call.data.startswith('mod_'))
def handle_moderation_pagination(call):
    try:
        user_id = call.from_user.id
        page = int(call.data.split('_')[1])
        
        # Показываем новую страницу (старое объявление удалится в show_moderation_ad_page)
        show_moderation_ad_page(call.message.chat.id, user_id, page)
    except Exception as e:
        print(f"Ошибка в handle_moderation_pagination: {e}")

# Одобрение объявления
@bot.callback_query_handler(func=lambda call: call.data.startswith('approve_'))
def approve_ad(call):
    try:
        ad_id = call.data.split('_')[1]
        
        # Обновляем статус объявления
        db.update_ad_status(ad_id, 'approved', admin_contact=f"@{call.from_user.username}")
        
        # Уведомляем пользователя
        user_ads = db.get_user_ads_by_ad_id(ad_id)
        if user_ads and len(user_ads) > 0:
            user_id = user_ads[0][1]  # user_id из объявления
            bot.send_message(user_id, f"✅ Ваше объявление одобрено! Теперь оно видно другим пользователям.")
        
        # Удаляем сообщение модерации
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "Объявление одобрено")
        
        # Показываем следующее объявление на модерации, если есть
        user_id = call.from_user.id
        if user_id in user_pagination and user_pagination[user_id]['type'] == 'mod':
            user_data = user_pagination[user_id]
            current_page = user_data['current_page']
            ads = user_data['ads']
            
            # Обновляем список объявлений
            remaining_ads = db.get_pending_ads()
            if remaining_ads and len(remaining_ads) > 0:
                user_pagination[user_id]['ads'] = remaining_ads
                user_pagination[user_id]['total_pages'] = len(remaining_ads)
                # Показываем текущую страницу или первую, если текущей нет
                new_page = min(current_page, len(remaining_ads) - 1) if current_page < len(remaining_ads) else 0
                show_moderation_ad_page(call.message.chat.id, user_id, new_page)
            else:
                bot.send_message(call.message.chat.id, "Все объявления промодерированы!")
    except Exception as e:
        print(f"Ошибка в approve_ad: {e}")

# Отклонение объявления
@bot.callback_query_handler(func=lambda call: call.data.startswith('reject_'))
def reject_ad(call):
    try:
        ad_id = call.data.split('_')[1]
        
        # Обновляем статус объявления
        db.update_ad_status(ad_id, 'rejected')
        
        # Уведомляем пользователя
        user_ads = db.get_user_ads_by_ad_id(ad_id)
        if user_ads and len(user_ads) > 0:
            user_id = user_ads[0][1]  # user_id из объявления
            bot.send_message(user_id, f"❌ Ваше объявление отклонено модератором. Если вы считаете это ошибкой, свяжитесь с администратором.")
        
        # Удаляем сообщение модерации
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.answer_callback_query(call.id, "Объявление отклонено")
        
        # Показываем следующее объявление на модерации, если есть
        user_id = call.from_user.id
        if user_id in user_pagination and user_pagination[user_id]['type'] == 'mod':
            user_data = user_pagination[user_id]
            current_page = user_data['current_page']
            ads = user_data['ads']
            
            # Обновляем список объявлений
            remaining_ads = db.get_pending_ads()
            if remaining_ads and len(remaining_ads) > 0:
                user_pagination[user_id]['ads'] = remaining_ads
                user_pagination[user_id]['total_pages'] = len(remaining_ads)
                # Показываем текущую страницу или первую, если текущей нет
                new_page = min(current_page, len(remaining_ads) - 1) if current_page < len(remaining_ads) else 0
                show_moderation_ad_page(call.message.chat.id, user_id, new_page)
            else:
                bot.send_message(call.message.chat.id, "Все объявления промодерированы!")
    except Exception as e:
        print(f"Ошибка в reject_ad: {e}")

# Админские функции с пагинацией
@bot.message_handler(func=lambda message: message.text == '📋 Все объявления' and message.from_user.id in config.ADMIN_IDS)
def admin_all_ads(message):
    try:
        ads = db.get_all_ads()
        
        if not ads:
            bot.send_message(message.chat.id, "Нет объявлений.")
            return
        
        # Сохраняем объявления для админа
        user_id = message.from_user.id
        user_pagination[user_id] = {
            'ads': ads,
            'total_pages': len(ads),
            'current_page': 0,
            'type': 'admin',
            'current_message_ids': []  # Для хранения ID текущих сообщений
        }
        
        # Показываем первое объявление
        show_admin_ad_page(message.chat.id, user_id, 0)
    except Exception as e:
        print(f"Ошибка в admin_all_ads: {e}")

# Функция показа конкретной страницы для админа
def show_admin_ad_page(chat_id, user_id, page):
    try:
        if user_id not in user_pagination or user_pagination[user_id]['type'] != 'admin':
            bot.send_message(chat_id, "Сессия просмотра истекла. Начните заново.")
            return
        
        # Удаляем предыдущее объявление
        delete_previous_ad_messages(chat_id, user_id)
        
        user_data = user_pagination[user_id]
        ads = user_data['ads']
        total_pages = user_data['total_pages']
        
        if page < 0 or page >= total_pages:
            bot.send_message(chat_id, "Объявление не найдено.")
            return
        
        user_data['current_page'] = page
        ad = ads[page]
        ad_id, user_id_ad, title, description, photo_id, price, contact, created_at, status, admin_contact, username, telegram_id = ad
        
        status_icons = {
            'pending': '⏳ Ожидает модерации',
            'approved': '✅ Одобрено',
            'rejected': '❌ Отклонено'
        }
        
        caption = f"""
🚛 *{title}*

📝 *Описание:*
{description}

💰 *Стоимость:*
{price}

👤 *Автор:* @{username} (ID: {telegram_id})
📞 *Контакты:* {contact}

🆔 *Номер объявления:* `{ad_id}`
📊 *Статус:* {status_icons.get(status, '❓ Неизвестно')}
"""
        
        keyboard = InlineKeyboardMarkup(row_width=3)
        
        # Кнопки пагинации
        pagination_buttons = []
        if page > 0:
            pagination_buttons.append(InlineKeyboardButton("⬅️", callback_data=f"admin_{page-1}"))
        
        pagination_buttons.append(InlineKeyboardButton(f"{page+1}/{total_pages}", callback_data="current"))
        
        if page < total_pages - 1:
            pagination_buttons.append(InlineKeyboardButton("➡️", callback_data=f"admin_{page+1}"))
        
        keyboard.add(*pagination_buttons)
        
        # Кнопка удаления для админа
        keyboard.add(InlineKeyboardButton("❌ Удалить", callback_data=f"admin_delete_{ad_id}"))
        
        # Используем новую функцию для отправки с медиа-группой
        message_ids = send_ad_with_media_group(chat_id, caption, photo_id, keyboard)
        
        # Сохраняем ID сообщений для последующего удаления
        user_pagination[user_id]['current_message_ids'] = message_ids
        
    except Exception as e:
        print(f"Ошибка в show_admin_ad_page: {e}")

# Обработка пагинации для админа
@bot.callback_query_handler(func=lambda call: call.data.startswith('admin_') and not call.data.startswith('admin_delete_'))
def handle_admin_pagination(call):
    try:
        user_id = call.from_user.id
        page = int(call.data.split('_')[1])
        
        # Показываем новую страницу (старое объявление удалится в show_admin_ad_page)
        show_admin_ad_page(call.message.chat.id, user_id, page)
    except Exception as e:
        print(f"Ошибка в handle_admin_pagination: {e}")

# Список номеров объявлений для админа с кликабельными номерами
@bot.message_handler(func=lambda message: message.text == '📝 Список номеров' and message.from_user.id in config.ADMIN_IDS)
def list_ad_ids(message):
    try:
        ads = db.get_all_ads()
        
        if not ads:
            bot.send_message(message.chat.id, "Нет объявлений.")
            return
        
        # Формируем список с инлайн-кнопками
        ad_list_text = "📋 *Список номеров объявлений:*\n\n"
        keyboard = InlineKeyboardMarkup(row_width=4)
        buttons = []
        
        for ad in ads:
            ad_id, user_id_ad, title, description, photo_id, price, contact, created_at, status, admin_contact, username, telegram_id = ad
            
            status_emoji = {
                'pending': '⏳',
                'approved': '✅', 
                'rejected': '❌'
            }.get(status, '❓')
            
            # Добавляем кнопку с номером объявления
            buttons.append(InlineKeyboardButton(f"{status_emoji}{ad_id}", callback_data=f"open_ad_{ad_id}"))
            
            # Добавляем текст для отображения
            short_title = title[:25] + "..." if len(title) > 25 else title
            ad_list_text += f"{status_emoji} `{ad_id}` - {short_title}\n"
        
        # Разбиваем кнопки на строки по 4 кнопки
        for i in range(0, len(buttons), 4):
            keyboard.add(*buttons[i:i+4])
        
        # Добавляем кнопку "Закрыть"
        keyboard.add(InlineKeyboardButton("❌ Закрыть", callback_data="close_list"))
        
        bot.send_message(message.chat.id, ad_list_text, parse_mode='Markdown', reply_markup=keyboard)
            
    except Exception as e:
        print(f"Ошибка в list_ad_ids: {e}")
        bot.send_message(message.chat.id, "Ошибка при получении списка объявлений.")

# Функция для открытия объявления по ID
def open_ad_by_id(chat_id, ad_id, user_id=None):
    try:
        # Получаем все объявления
        ads = db.get_all_ads()
        
        # Ищем нужное объявление
        target_ad = None
        for ad in ads:
            if ad[0] == ad_id:  # ad[0] - это ID объявления
                target_ad = ad
                break
        
        if not target_ad:
            bot.send_message(chat_id, "❌ Объявление не найдено.")
            return
        
        # Распаковываем данные объявления
        (ad_id, user_id_ad, title, description, photo_id, price, contact, created_at, status, admin_contact, username, telegram_id) = target_ad
        
        status_icons = {
            'pending': '⏳ Ожидает модерации',
            'approved': '✅ Одобрено',
            'rejected': '❌ Отклонено'
        }
        
        caption = f"""
🚛 *{title}*

📝 *Описание:*
{description}

💰 *Стоимость:*
{price}

👤 *Автор:* @{username} (ID: {telegram_id})
📞 *Контакты:* {contact}

🆔 *Номер объявления:* `{ad_id}`
📊 *Статус:* {status_icons.get(status, '❓ Неизвестно')}
"""
        
        keyboard = InlineKeyboardMarkup()
        keyboard.add(
            InlineKeyboardButton("❌ Удалить", callback_data=f"admin_delete_{ad_id}"),
            InlineKeyboardButton("📋 К списку", callback_data="back_to_list")
        )
        
        # Используем новую функцию для отправки с медиа-группой
        send_ad_with_media_group(chat_id, caption, photo_id, keyboard)
            
    except Exception as e:
        print(f"Ошибка в open_ad_by_id: {e}")
        bot.send_message(chat_id, "❌ Ошибка при открытии объявления.")

# Обработка открытия объявления по ID
@bot.callback_query_handler(func=lambda call: call.data.startswith('open_ad_'))
def handle_open_ad(call):
    try:
        ad_id = int(call.data.split('_')[2])
        
        # Удаляем предыдущее сообщение со списком
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        # Открываем объявление
        open_ad_by_id(call.message.chat.id, ad_id, call.from_user.id)
        
    except Exception as e:
        print(f"Ошибка в handle_open_ad: {e}")

# Обработка возврата к списку
@bot.callback_query_handler(func=lambda call: call.data == 'back_to_list')
def handle_back_to_list(call):
    try:
        # Удаляем текущее сообщение
        bot.delete_message(call.message.chat.id, call.message.message_id)
        
        # Показываем список номеров заново
        list_ad_ids(call.message)
        
    except Exception as e:
        print(f"Ошибка в handle_back_to_list: {e}")

# Обработка закрытия списка
@bot.callback_query_handler(func=lambda call: call.data == 'close_list')
def handle_close_list(call):
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
        bot.send_message(call.message.chat.id, "Список закрыт.", reply_markup=admin_keyboard())
    except Exception as e:
        print(f"Ошибка в handle_close_list: {e}")

# Переключение в пользовательский режим для админа
@bot.message_handler(func=lambda message: message.text == '👤 Пользовательский режим' and message.from_user.id in config.ADMIN_IDS)
def user_mode(message):
    bot.send_message(message.chat.id, "Переключено в пользовательский режим", reply_markup=user_admin_keyboard())

# Возврат в админ-режим
@bot.message_handler(func=lambda message: message.text == '👑 Админ-режим' and message.from_user.id in config.ADMIN_IDS)
def back_to_admin_mode(message):
    bot.send_message(message.chat.id, "Возврат в админ-режим", reply_markup=admin_keyboard())

# Статистика для админа
@bot.message_handler(func=lambda message: message.text == '📊 Статистика' and message.from_user.id in config.ADMIN_IDS)
def admin_stats(message):
    try:
        conn = sqlite3.connect('cargo_bot.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM users')
        users_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM ads')
        ads_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM ads WHERE status = "approved"')
        approved_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM ads WHERE status = "pending"')
        pending_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM ads WHERE status = "rejected"')
        rejected_count = cursor.fetchone()[0]
        
        conn.close()
        
        stats_text = f"""
📊 *Статистика:*

👥 *Пользователей:* {users_count}
📋 *Всего объявлений:* {ads_count}
✅ *Одобрено:* {approved_count}
⏳ *На модерации:* {pending_count}
❌ *Отклонено:* {rejected_count}
"""
        bot.send_message(message.chat.id, stats_text, parse_mode='Markdown')
    except Exception as e:
        print(f"Ошибка в admin_stats: {e}")

# Обработка удаления объявлений
@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_') or call.data.startswith('admin_delete_'))
def handle_delete(call):
    try:
        if call.data.startswith('delete_'):
            ad_id = call.data.split('_')[1]
            db.delete_ad(ad_id)
            bot.answer_callback_query(call.id, "Объявление удалено")
            bot.delete_message(call.message.chat.id, call.message.message_id)
            
            # Определяем правильную клавиатуру для ответа
            if call.from_user.id in config.ADMIN_IDS:
                bot.send_message(call.message.chat.id, "Объявление удалено.", reply_markup=user_admin_keyboard())
            else:
                bot.send_message(call.message.chat.id, "Объявление удалено.", reply_markup=main_keyboard())
        
        elif call.data.startswith('admin_delete_') and call.from_user.id in config.ADMIN_IDS:
            ad_id = call.data.split('_')[2]
            db.delete_ad(ad_id)
            bot.answer_callback_query(call.id, "Объявление удалено администратором")
            bot.delete_message(call.message.chat.id, call.message.message_id)
            bot.send_message(call.message.chat.id, "Объявление удалено.", reply_markup=admin_keyboard())
    except Exception as e:
        print(f"Ошибка в handle_delete: {e}")

# Обработка любых других сообщений
@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    try:
        if message.from_user.id in config.ADMIN_IDS:
            # Проверяем, в каком режиме находится админ
            if hasattr(message, 'text') and message.text == '👑 Админ-режим':
                bot.send_message(message.chat.id, "Используйте кнопки меню", reply_markup=admin_keyboard())
            else:
                bot.send_message(message.chat.id, "Используйте кнопки меню", reply_markup=user_admin_keyboard())
        else:
            bot.send_message(message.chat.id, "Используйте кнопки меню", reply_markup=main_keyboard())
    except Exception as e:
        print(f"Ошибка в handle_other_messages: {e}")

# Запуск бота
if __name__ == '__main__':
    backup_database()  # Создаем бэкап при запуске
    print("Бот запущен...")
    try:
        bot.infinity_polling()
    except Exception as e:
        print(f"Бот остановлен с ошибкой: {e}")
    finally:
        print("Работа бота завершена")