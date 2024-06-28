import asyncio
import logging
import sqlite3
import sys
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.types import Message

TOKEN = "..."

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode='html'))
dp = Dispatcher()

DATABASE_NAME = 'finance.db'

# Создание таблицы для хранения пользователей, доходов, расходов, категорий, целей и бюджета
conn = sqlite3.connect(DATABASE_NAME)
cursor = conn.cursor()

# Создание таблицы пользователей
cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance REAL DEFAULT 0,
        budget REAL
    )
''')

# Создание таблицы доходов
cursor.execute('''
    CREATE TABLE IF NOT EXISTS incomes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL,
        description TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
''')

# Создание таблицы расходов
cursor.execute('''
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        amount REAL,
        description TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
''')

# Создание таблицы целей
cursor.execute('''
    CREATE TABLE IF NOT EXISTS goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        goal TEXT,
        amount REAL,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
''')
#таблица категорий
cursor.execute('''
    CREATE TABLE IF NOT EXISTS expense_categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        category_name TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS budgets (
        user_id INTEGER PRIMARY KEY,
        budget REAL
    )
''')

conn.commit()


@dp.message(CommandStart())
async def send_welcome(message: Message) -> None:
    await message.reply("Здравствуйте! Я помогу вам управлять личными финансами.\n"
                        "Используйте команду /help для получения списка команд.")


@dp.message(Command('help'))
async def send_help(message: Message):
    await message.reply("Там, где указаны дополнительные параметры в квадратных скобках, они требуются обязательно(без скобок, через пробел)\n" 
                        "\n/addincome [сумма] [описание] - добавить доход\n"
                        "/addexpense [сумма] [описание] - добавить расход\n"
                        "/balance - показать баланс\n"
                        "/setbudget [сумма] - установить месячный бюджет\n"
                        "/budget - показать текущий бюджет\n"
                        "/report [период] - получить отчет за период(день, неделя, месяц)\n"
                        "/categories - управлять категориями\n"
                        "/setgoal [цель] [сумма] - установить финансовую цель\n"
                        "/goals - показать финансовые цели")


@dp.message(Command('addincome'))
async def add_income(message: Message):
    try:
        args = message.text.split(maxsplit=2)
        amount = float(args[1])
        description = args[2] if len(args) > 2 else ""
        user_id = message.from_user.id
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Добавление дохода в таблицу incomes
        cursor.execute("INSERT INTO incomes (user_id, amount, description, timestamp) VALUES (?, ?, ?, ?)",
                       (user_id, amount, description, date))

        # Обновление баланса и бюджета пользователя
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?",
                       (amount, user_id))

        cursor.execute("INSERT INTO budgets (user_id, budget) VALUES (?, ?) "
                       "ON CONFLICT(user_id) DO UPDATE SET budget = budget + excluded.budget",
                       (user_id, amount))
        # Обновление целей пользователя (уменьшение необходимой суммы)
        cursor.execute("UPDATE goals SET amount = amount - ? WHERE user_id = ?", (amount, user_id))

        conn.commit()

        await message.reply(f"Доход в размере {amount} добавлен.")
    except Exception as e:
        await message.reply(f"Произошла ошибка при добавлении дохода: {e}")


@dp.message(Command('addexpense'))
async def add_expense(message: Message):
    try:
        args = message.text.split(maxsplit=2)
        amount = float(args[1])
        description = args[2] if len(args) > 2 else ""
        user_id = message.from_user.id
        date = datetime.now().strftime("%Y-%m-%d %H:%M")

        # Добавление расхода в таблицу expenses
        cursor.execute("INSERT INTO expenses (user_id, amount, description, timestamp) VALUES (?, ?, ?, ?)",
                       (user_id, amount, description, date))

        # Обновление баланса и бюджета пользователя
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?",
                       (amount, user_id))
        cursor.execute("UPDATE budgets SET budget = budget - ? WHERE user_id = ?",
                       (amount, user_id))
        # Обновление целей пользователя (увеличение необходимой суммы)
        cursor.execute("UPDATE goals SET amount = amount + ? WHERE user_id = ?", (amount, user_id))

        conn.commit()

        await message.reply(f"Расход в размере {amount} добавлен.")
    except Exception as e:
        await message.reply(f"Произошла ошибка при добавлении расхода: {e}")


@dp.message(Command('balance'))
async def show_balance(message: Message):
    try:
        user_id = message.from_user.id

        cursor.execute('''
            SELECT 
                (SELECT COALESCE(SUM(amount), 0) FROM incomes WHERE user_id = ?) -
                (SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?)
        ''', (user_id, user_id))
        result = cursor.fetchone()
        balance = result[0] if result else 0.0
        await message.reply(f"Текущий баланс: {balance} руб.")
    except Exception as e:
        await message.reply(f"Произошла ошибка при получении баланса: {e}")


@dp.message(Command('setbudget'))
async def set_budget(message: Message):
    try:
        args = message.text.split(maxsplit=1)
        budget = float(args[1])
        user_id = message.from_user.id

        cursor.execute("INSERT INTO budgets (user_id, budget) VALUES (?, ?) "
                       "ON CONFLICT(user_id) DO UPDATE SET budget = excluded.budget",
                       (user_id, budget))
        conn.commit()

        await message.reply(f"Месячный бюджет установлен: {budget} руб.")
    except Exception as e:
        await message.reply(f"Произошла ошибка при установке бюджета: {e}")


@dp.message(Command('budget'))
async def show_budget(message: Message):
    try:
        user_id = message.from_user.id
        cursor.execute("SELECT budget FROM budgets WHERE user_id = ?", (user_id,))
        result = cursor.fetchone()
        budget = result[0] if result else 0.0
        await message.reply(f"Текущий месячный бюджет: {budget} руб.")
    except Exception as e:
        await message.reply(f"Произошла ошибка при получении текущего бюджета: {e}")


@dp.message(Command('report'))
async def generate_report(message: Message):
    try:
        args = message.text.split(maxsplit=1)
        period = args[1]
        user_id = message.from_user.id

        if period == 'день':
            start_date = datetime.now().strftime("%Y-%m-%d")
        elif period == 'неделя':
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        elif period == 'месяц':
            start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        else:
            await message.reply("Неверный период. Используйте 'день', 'неделя' или 'месяц'.")
            return

        cursor.execute('''
            SELECT SUM(amount) FROM incomes WHERE user_id = ? AND timestamp >= ?
        ''', (user_id, start_date))
        total_income = cursor.fetchone()[0] or 0.0

        cursor.execute('''
            SELECT SUM(amount) FROM expenses WHERE user_id = ? AND timestamp >= ?
        ''', (user_id, start_date))
        total_expenses = cursor.fetchone()[0] or 0.0

        report = (f"Отчет за {period}:\n"
                  f"Доходы: {total_income} руб.\n"
                  f"Расходы: {total_expenses} руб.\n"
                  f"Баланс: {total_income - total_expenses} руб.")

        await message.reply(report)

    except Exception as e:
        await message.reply(f"Произошла ошибка при генерации отчета: {e}")


@dp.message(Command('setgoal'))
async def set_goal(message: Message):
    try:
        args = message.text.split(maxsplit=2)
        goal = args[1]
        amount = float(args[2])
        user_id = message.from_user.id

        # Проверяем, существует ли цель для данного пользователя
        cursor.execute("SELECT COUNT(*) FROM goals WHERE user_id = ?", (user_id,))
        count = cursor.fetchone()[0]

        if count > 0:
            # Цель уже существует, обновляем её
            cursor.execute("UPDATE goals SET goal = ?, amount = ? WHERE user_id = ?", (goal, amount, user_id))
        else:
            # Цель не существует, добавляем новую
            cursor.execute("INSERT INTO goals (user_id, goal, amount) VALUES (?, ?, ?)", (user_id, goal, amount))

        conn.commit()

        await message.reply(f"Финансовая цель '{goal}' на сумму {amount} установлена.")
    except Exception as e:
        await message.reply(f"Произошла ошибка при установке финансовой цели: {e}")


@dp.message(Command('goals'))
async def show_goals(message: Message):
    try:
        user_id = message.from_user.id

        cursor.execute("SELECT goal, amount FROM goals WHERE user_id = ?", (user_id,))
        goals = cursor.fetchall()

        if not goals:
            await message.reply("У вас пока нет установленных финансовых целей.")
            return

        response = "Ваши финансовые цели:\n"
        for goal, amount in goals:
            response += f"- {goal}: {amount} руб.\n"

        await message.reply(response)
    except Exception as e:
        await message.reply(f"Произошла ошибка при получении финансовых целей: {e}")


@dp.message(Command('categories'))
async def manage_categories(message: Message):
    await message.reply("Доступные команды для управления категориями:\n"
                        "/addcategory [название] - добавить категорию\n"
                        "/deletecategory [название] - удалить категорию\n"
                        "/listcategories - показать список категорий")


@dp.message(Command('addcategory'))
async def add_category(message: Message):
    try:
        category_name = message.text.split(maxsplit=1)[1]
        user_id = message.from_user.id

        cursor.execute("INSERT INTO expense_categories (user_id, category_name) VALUES (?, ?)",
                       (user_id, category_name))
        conn.commit()

        await message.reply(f"Категория '{category_name}' добавлена.")
    except Exception as e:
        await message.reply(f"Произошла ошибка при добавлении категории: {e}")


@dp.message(Command('deletecategory'))
async def delete_category(message: Message):
    try:
        category_name = message.text.split(maxsplit=1)[1]
        user_id = message.from_user.id

        cursor.execute("DELETE FROM expense_categories WHERE user_id = ? AND category_name = ?",
                       (user_id, category_name))
        conn.commit()

        await message.reply(f"Категория '{category_name}' удалена.")
    except Exception as e:
        await message.reply(f"Произошла ошибка при удалении категории: {e}")


@dp.message(Command('listcategories'))
async def list_categories(message: Message):
    try:
        user_id = message.from_user.id
        cursor.execute("SELECT category_name FROM expense_categories WHERE user_id = ?", (user_id,))
        categories = cursor.fetchall()
        if categories:
            categories_list = "\n".join([f"- {category[0]}" for category in categories])
            await message.reply(f"Список категорий расходов:\n{categories_list}")
        else:
            await message.reply("У вас пока нет добавленных категорий расходов.")
    except Exception as e:
        await message.reply(f"Произошла ошибка при получении списка категорий: {e}")


# Запуск бота
async def main():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
