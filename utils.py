# utils.py
import matplotlib.pyplot as plt
import io


def generate_pie_chart(data):
    """
    Генерирует круговую диаграмму расходов.
    data: список кортежей (категория, сумма)
    Возвращает байтовый объект картинки.
    """
    if not data:
        return None

    categories = [item[0] for item in data]
    costs = [item[1] for item in data]

    # Настройка графика
    plt.figure(figsize=(6, 6))
    plt.pie(costs, labels=categories, autopct='%1.1f%%', startangle=140)
    plt.title('Распределение бюджета')

    # Сохраняем в буфер памяти, а не в файл (чтобы не мусорить на диске)
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()

    return buf


def generate_bar_chart(subscriptions):
    """Гистограмма: Цена vs Важность (отмасштабированная)"""
    if not subscriptions:
        return None

    names = [s[0] for s in subscriptions]
    prices = [s[1] for s in subscriptions]
    # Умножаем важность на 100 для наглядности на фоне цен
    importance = [s[3] * 100 for s in subscriptions]

    plt.figure(figsize=(10, 6))
    x = range(len(names))
    plt.bar(x, prices, width=0.4, label='Цена (руб)', align='center')
    plt.bar(x, importance, width=0.4, label='Польза (усл. ед)', align='edge')

    plt.xticks(x, names, rotation=45)
    plt.legend()
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf


def analyze_efficiency(subscriptions):
    """
    Анализ эффективности трат.
    Формула: Если важность низкая (<5), а цена высокая (>1000), рекомендуем отменить.
    """
    recommendations = []
    total_waste = 0

    for sub in subscriptions:
        name, price, category, importance = sub

        # Логика рекомендаций (как в описании проекта)
        if importance < 4 and price > 500:
            recommendations.append(
                f"⚠️ <b>{name}</b>: Вы тратите {price}р, но оценили важность всего на {importance}/10. Стоит отменить."
            )
            total_waste += price
        elif importance < 2:
            recommendations.append(
                f"❌ <b>{name}</b>: Низкая полезность ({importance}/10). Зачем вы за это платите?"
            )
            total_waste += price

    if not recommendations:
        return "✅ Ваши траты выглядят оптимально!", 0

    return "\n".join(recommendations), total_waste


def calculate_monthly_forecast(subscriptions):
    """Простой расчет итогов"""
    total = sum(s[1] for s in subscriptions)
    year_total = total * 12
    return total, year_total