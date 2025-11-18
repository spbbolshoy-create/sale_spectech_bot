import sqlite3
from datetime import datetime

def init_db():
    conn = sqlite3.connect('cargo_bot.db')
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            username TEXT,
            full_name TEXT,
            is_admin BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Таблица объявлений с статусом модерации
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT,
            description TEXT,
            photo_id TEXT,
            price TEXT,
            contact TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'pending', -- pending, approved, rejected
            admin_contact TEXT DEFAULT NULL, -- контакт админа для связи
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    conn.commit()
    conn.close()

def add_user(telegram_id, username, full_name):
    conn = sqlite3.connect('cargo_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO users (telegram_id, username, full_name) VALUES (?, ?, ?)', 
                   (telegram_id, username, full_name))
    conn.commit()
    conn.close()

def add_ad(user_id, title, description, photo_id, price, contact):
    conn = sqlite3.connect('cargo_bot.db')
    cursor = conn.cursor()
    cursor.execute('INSERT INTO ads (user_id, title, description, photo_id, price, contact, status) VALUES (?, ?, ?, ?, ?, ?, ?)', 
                   (user_id, title, description, photo_id, price, contact, 'pending'))
    conn.commit()
    conn.close()

def get_approved_ads():
    """Только одобренные объявления для пользователей"""
    conn = sqlite3.connect('cargo_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ads.*, users.username 
        FROM ads 
        JOIN users ON ads.user_id = users.telegram_id 
        WHERE ads.status = 'approved'
        ORDER BY ads.created_at DESC
    ''')
    ads = cursor.fetchall()
    conn.close()
    return ads

def get_pending_ads():
    """Объявления на модерации для админа"""
    conn = sqlite3.connect('cargo_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ads.*, users.username, users.telegram_id
        FROM ads 
        JOIN users ON ads.user_id = users.telegram_id 
        WHERE ads.status = 'pending'
        ORDER BY ads.created_at DESC
    ''')
    ads = cursor.fetchall()
    conn.close()
    return ads

def get_all_ads():
    """Все объявления для админа"""
    conn = sqlite3.connect('cargo_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT ads.*, users.username, users.telegram_id
        FROM ads 
        JOIN users ON ads.user_id = users.telegram_id 
        ORDER BY ads.created_at DESC
    ''')
    ads = cursor.fetchall()
    conn.close()
    return ads

def get_user_ads(user_id):
    conn = sqlite3.connect('cargo_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM ads WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
    ads = cursor.fetchall()
    conn.close()
    return ads

def update_ad_status(ad_id, status, admin_contact=None):
    conn = sqlite3.connect('cargo_bot.db')
    cursor = conn.cursor()
    if admin_contact:
        cursor.execute('UPDATE ads SET status = ?, admin_contact = ? WHERE id = ?', (status, admin_contact, ad_id))
    else:
        cursor.execute('UPDATE ads SET status = ? WHERE id = ?', (status, ad_id))
    conn.commit()
    conn.close()

def delete_ad(ad_id):
    conn = sqlite3.connect('cargo_bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM ads WHERE id = ?', (ad_id,))
    conn.commit()
    conn.close()

# Инициализация БД при импорте
init_db()

def get_user_ads_by_ad_id(ad_id):
    """Получить объявление по ID для уведомления пользователя"""
    conn = sqlite3.connect('cargo_bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM ads WHERE id = ?', (ad_id,))
    ads = cursor.fetchall()
    conn.close()
    return ads