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
    
    # Таблица истории использования подписок
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usage_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subscription_id INTEGER NOT NULL,
            week_start_date DATE NOT NULL,
            usage_score INTEGER NOT NULL CHECK(usage_score >= 1 AND usage_score <= 10),
            date_recorded TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE,
            UNIQUE(subscription_id, week_start_date)
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


def get_all_subs(user_id, include_id=False, exclude_zkh=False, include_usage=False):
    """
    Функция для получения подписок пользователя.
    
    Args:
        user_id: ID пользователя
        include_id: Если True, включает id подписки в результат
        exclude_zkh: Если True, исключает подписки категории 'Коммуналка / ЖКХ'
        include_usage: Если True, включает среднюю оценку использования
    
    Returns:
        Список кортежей с данными подписок
    """
    conn = create_connection()
    cursor = conn.cursor()
    
    # Формируем SELECT в зависимости от параметров
    if include_usage:
        # С JOIN для получения данных об использовании
        select_fields = 's.id, s.service_name, s.price, s.category, s.importance, COALESCE(AVG(uh.usage_score), NULL) as avg_usage'
        from_clause = 'FROM subscriptions s LEFT JOIN usage_history uh ON s.id = uh.subscription_id'
        group_by = 'GROUP BY s.id'
    elif include_id:
        select_fields = 'id, service_name, price, category, importance'
        from_clause = 'FROM subscriptions'
        group_by = ''
    else:
        select_fields = 'service_name, price, category, importance'
        from_clause = 'FROM subscriptions'
        group_by = ''
    
    # Формируем WHERE
    if include_usage:
        # При JOIN нужно указывать префикс таблицы
        where_clause = 'WHERE s.user_id = ?'
    else:
        where_clause = 'WHERE user_id = ?'
    
    params = [user_id]
    
    if exclude_zkh:
        if include_usage:
            where_clause += " AND s.category != 'Коммуналка / ЖКХ'"
        else:
            where_clause += " AND category != 'Коммуналка / ЖКХ'"
    
    query = f'SELECT {select_fields} {from_clause} {where_clause} {group_by}'
    
    cursor.execute(query, tuple(params))
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


def save_usage_score(subscription_id, user_id, week_start_date, usage_score):
    """Сохранить оценку использования за неделю"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO usage_history 
        (subscription_id, week_start_date, usage_score)
        VALUES (?, ?, ?)
    ''', (subscription_id, week_start_date, usage_score))
    conn.commit()
    conn.close()


def get_average_usage_score(subscription_id, weeks=4):
    """Получить среднюю оценку использования за последние N недель"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT AVG(usage_score) 
        FROM usage_history 
        WHERE subscription_id = ?
        ORDER BY week_start_date DESC
        LIMIT ?
    ''', (subscription_id, weeks))
    result = cursor.fetchone()
    conn.close()
    if result and result[0] is not None:
        return round(result[0], 2)
    return None


def check_subscription_rated(subscription_id, week_start_date):
    """Проверить, была ли подписка оценена за указанную неделю"""
    conn = create_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT usage_score FROM usage_history 
        WHERE subscription_id = ? AND week_start_date = ?
    ''', (subscription_id, week_start_date))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None


def get_rated_subscriptions_for_week(user_id, week_start_date):
    """Получить список ID подписок, которые уже оценены за неделю"""
    conn = create_connection()
    cursor = conn.cursor()
    # Получаем через JOIN с subscriptions, так как user_id убрали из usage_history
    cursor.execute('''
        SELECT DISTINCT uh.subscription_id 
        FROM usage_history uh
        JOIN subscriptions s ON uh.subscription_id = s.id
        WHERE s.user_id = ? AND uh.week_start_date = ?
    ''', (user_id, week_start_date))
    result = [row[0] for row in cursor.fetchall()]
    conn.close()
    return result


def get_unused_subscriptions(user_id, weeks_threshold=3):
    """
    Получить подписки, которые не использовались более N недель.
    
    Args:
        user_id: ID пользователя
        weeks_threshold: Количество недель неиспользования для уведомления
    
    Returns:
        Список кортежей (sub_id, service_name, price, last_usage_week, weeks_unused)
    """
    conn = create_connection()
    cursor = conn.cursor()
    
    # Получаем все подписки пользователя (кроме ЖКХ) с информацией о последнем использовании
    cursor.execute('''
        SELECT s.id, s.service_name, s.price, 
               MAX(uh.week_start_date) as last_usage_week,
               CASE 
                   WHEN MAX(uh.week_start_date) IS NOT NULL THEN
                       CAST((julianday('now') - julianday(MAX(uh.week_start_date))) / 7 AS INTEGER)
                   ELSE
                       CAST((julianday('now') - julianday(s.date_added)) / 7 AS INTEGER)
               END as weeks_unused
        FROM subscriptions s
        LEFT JOIN usage_history uh ON s.id = uh.subscription_id
        WHERE s.user_id = ? AND s.category != 'Коммуналка / ЖКХ'
        GROUP BY s.id, s.service_name, s.price, s.date_added
        HAVING weeks_unused >= ?
    ''', (user_id, weeks_threshold))
    
    rows = cursor.fetchall()
    conn.close()
    return rows