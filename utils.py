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


def generate_bar_chart(subscriptions_with_usage):
    """Гистограмма: Стоимость за единицу удовольствия по подпискам"""
    if not subscriptions_with_usage:
        return None

    import database as db
    
    names = []
    cost_per_unit = []
    
    for sub in subscriptions_with_usage:
        if len(sub) == 6:
            sub_id, name, price, category, importance, avg_usage = sub
        else:
            # Старый формат без использования
            name, price, category, importance = sub
            avg_usage = None
        
        if avg_usage is not None and importance > 0 and avg_usage > 0:
            cost = price / (importance * float(avg_usage))
            names.append(name)
            cost_per_unit.append(cost)
        elif avg_usage is None:
            # Если нет данных - показываем как очень высокую стоимость
            names.append(name)
            cost_per_unit.append(999)  # Маркер для "нет данных"
    
    if not names:
        return None

    plt.figure(figsize=(12, 6))
    x = range(len(names))
    colors = []
    for cost in cost_per_unit:
        if cost == 999:
            colors.append('gray')  # Нет данных
        elif cost > 50:
            colors.append('red')  # Высокая стоимость
        elif cost > 30:
            colors.append('orange')  # Средняя стоимость
        else:
            colors.append('green')  # Низкая стоимость (оптимально)
    
    bars = plt.bar(x, [c if c != 999 else 0 for c in cost_per_unit], color=colors, alpha=0.7)
    
    # Добавляем подписи для подписок без данных
    for i, (bar, cost) in enumerate(zip(bars, cost_per_unit)):
        if cost == 999:
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5, 
                    'Нет данных', ha='center', va='bottom', fontsize=8, color='gray')
        else:
            plt.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2, 
                    f'{cost:.1f}₽', ha='center', va='bottom', fontsize=8)
    
    plt.xticks(x, names, rotation=45, ha='right')
    plt.ylabel('Стоимость за единицу удовольствия (₽)')
    plt.title('Эффективность подписок')
    plt.axhline(y=50, color='red', linestyle='--', alpha=0.5, label='Порог неэффективности (50₽)')
    plt.axhline(y=30, color='orange', linestyle='--', alpha=0.5, label='Средняя эффективность (30₽)')
    plt.legend()
    plt.grid(axis='y', alpha=0.3)
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    buf.seek(0)
    plt.close()
    return buf


def analyze_efficiency(subscriptions_with_usage):
    """
    Анализ эффективности трат на основе стоимости за единицу удовольствия.
    subscriptions_with_usage: список кортежей (id, name, price, category, importance, avg_usage)
    где avg_usage - средняя оценка использования за последние 4 недели (1-10) или None
    """
    recommendations = []
    total_waste = 0

    for sub in subscriptions_with_usage:
        # Распаковываем данные
        if len(sub) == 6:
            sub_id, name, price, category, importance, avg_usage = sub
        else:
            # Обратная совместимость
            name, price, category, importance = sub
            avg_usage = None

        # Если нет данных об использовании
        if avg_usage is None:
            recommendations.append(
                f"ℹ️ <b>{name}</b>: Нет данных об использовании. "
                f"Используйте команду /survey для оценки частоты использования подписки."
            )
            continue

        # Преобразуем avg_usage в float
        avg_usage = float(avg_usage) if avg_usage is not None else 0
        
        # Расчет "стоимости за единицу удовольствия"
        # Формула: цена / (важность * частота использования)
        if importance > 0 and avg_usage > 0:
            cost_per_pleasure_unit = price / (importance * avg_usage)
        else:
            cost_per_pleasure_unit = None
        
        # Градация по стоимости за единицу удовольствия
        if cost_per_pleasure_unit:
            if cost_per_pleasure_unit > 100:
                # Очень высокая стоимость - точно отменить
                recommendations.append(
                    f"❌ <b>{name}</b>: Очень высокая стоимость за единицу удовольствия ({cost_per_pleasure_unit:.1f}₽). "
                    f"Важность: {importance}/10, использование: {avg_usage:.1f}/10. "
                    f"Рекомендуем отменить."
                )
                total_waste += price  # Полная экономия
            elif cost_per_pleasure_unit > 50:
                # Высокая стоимость - стоит подумать
                recommendations.append(
                    f"⚠️ <b>{name}</b>: Высокая стоимость за единицу удовольствия ({cost_per_pleasure_unit:.1f}₽). "
                    f"Важность: {importance}/10, использование: {avg_usage:.1f}/10. "
                    f"Стоит подумать о более дешевой альтернативе."
                )
                total_waste += price * 0.5  # Частичная экономия
            elif cost_per_pleasure_unit > 30:
                # Средняя стоимость - можно оставить, но следить
                recommendations.append(
                    f"💡 <b>{name}</b>: Средняя стоимость за единицу удовольствия ({cost_per_pleasure_unit:.1f}₽). "
                    f"Важность: {importance}/10, использование: {avg_usage:.1f}/10. "
                    f"Можно оставить, но следите за использованием."
                )
                total_waste += price * 0.2  # Минимальная экономия
            # Если <= 30 - оптимально, не добавляем рекомендацию

    if not recommendations:
        return "✅ Ваши траты выглядят оптимально! Все подписки используются эффективно.", 0

    return "\n".join(recommendations), total_waste


def calculate_monthly_forecast(subscriptions):
    """Простой расчет итогов"""
    total = sum(s[1] for s in subscriptions)
    year_total = total * 12
    return total, year_total