# database.py
import sqlite3
from config import DB_NAME


def create_connection():
    """Создает подключение к БД"""
    return sqlite3.connect(DB_NAME)


def init_db():
    """Инициализация таблиц при старте"""
    conn = create_connection()
    cursor = conn.cursor()

    # Таблица подписок
    # Добавили поле importance (важность) для расчета эффективности
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS subscriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            service_name TEXT NOT NULL,
            price REAL NOT NULL,
            category TEXT NOT NULL,
            importance INTEGER DEFAULT 5,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()


def add_subscription(user_id, name, price, category, importance):
    """Добавление новой записи"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO subscriptions (user_id, service_name, price, category, importance)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, name, price, category, importance))
    conn.commit()
    conn.close()


def get_all_subs(user_id):
    """Получить все подписки пользователя"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT service_name, price, category, importance FROM subscriptions WHERE user_id = ?', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_subs_with_ids(user_id):
    """Получить подписки с ID для удаления"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, service_name, price FROM subscriptions WHERE user_id = ?', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_stats_by_category(user_id):
    """Группировка расходов по категориям для графика"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT category, SUM(price) 
        FROM subscriptions 
        WHERE user_id = ? 
        GROUP BY category
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()
    return rows


def delete_sub_by_id(sub_id):
    """Удаление по первичному ключу"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM subscriptions WHERE id = ?', (sub_id,))
    conn.commit()
    conn.close()