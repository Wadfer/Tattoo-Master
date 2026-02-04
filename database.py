import sqlite3
import datetime
from config import DATABASE_NAME, INITIAL_SCHEMAS

DEFAULT_TATTOO_SERVICES = [
    ("Консультация (идея/размер/место)", 0.0, 30),
    ("Разработка эскиза", 1500.0, 60),
    ("Тату: небольшая (до 5 см)", 3500.0, 60),
    ("Тату: средняя (5–10 см)", 6500.0, 120),
    ("Тату: большая (10–20 см)", 12000.0, 180),
    ("Перекрытие (cover-up) консультация", 1000.0, 60),
    ("Коррекция/доп.сеанс", 3000.0, 60),
    ("Удаление/сведение (консультация)", 0.0, 30),
]


def get_db_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_database(conn):
    try:
        for entity, schema in INITIAL_SCHEMAS.items():
            conn.execute(f'CREATE TABLE IF NOT EXISTS "{entity}" ({schema})')

        try:
            cursor = conn.cursor()
            cursor.execute('PRAGMA table_info("Клиенты")')
            columns = [col[1] for col in cursor.fetchall()]

            if 'Имя' in columns and 'ФИО' not in columns:
                conn.execute('CREATE TABLE "Клиенты_new" (ID INTEGER PRIMARY KEY AUTOINCREMENT, ФИО TEXT, Телефон TEXT)')
                cursor.execute('SELECT ID, Имя, Телефон FROM "Клиенты"')
                rows = cursor.fetchall()
                for r in rows:
                    conn.execute('INSERT INTO "Клиенты_new" (ID, ФИО, Телефон) VALUES (?, ?, ?)', 
                                (r['ID'], r['Имя'], r['Телефон']))
                conn.execute('DROP TABLE "Клиенты"')
                conn.execute('ALTER TABLE "Клиенты_new" RENAME TO "Клиенты"')
        except sqlite3.Error as e:
            print(f"Ошибка миграции таблицы Клиенты: {e}")

        try:
            cursor = conn.cursor()
            cursor.execute('PRAGMA table_info("Записи")')
            columns = [col[1] for col in cursor.fetchall()]
            if 'ID_Услуги' not in columns:
                conn.execute('ALTER TABLE "Записи" ADD COLUMN "ID_Услуги" INTEGER')
            if 'ID_Эскиза' not in columns:
                conn.execute('ALTER TABLE "Записи" ADD COLUMN "ID_Эскиза" INTEGER')
        except sqlite3.Error:
            pass

        # Сидирование услуг для тату-мастера (если таблица пустая)
        try:
            cur = conn.cursor()
            cur.execute('SELECT COUNT(*) FROM "Услуги"')
            cnt = cur.fetchone()[0] or 0
            if cnt == 0:
                cur.executemany(
                    'INSERT INTO "Услуги" ("Название","Цена","Длительность") VALUES (?,?,?)',
                    DEFAULT_TATTOO_SERVICES,
                )
        except sqlite3.Error:
            pass

        # Удаляем больше не используемую таблицу связей "Запись_Услуги"
        try:
            conn.execute('DROP TABLE IF EXISTS "Запись_Услуги"')
        except sqlite3.Error:
            pass

        conn.commit()
    except sqlite3.Error as e:
        from tkinter import messagebox
        messagebox.showerror("Ошибка БД", f"Ошибка инициализации таблиц: {e}")