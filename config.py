import locale
import sys

if sys.platform.startswith('win'):
    locale.setlocale(locale.LC_TIME, 'Russian')
else:
    locale.setlocale(locale.LC_TIME, 'ru_RU.UTF-8')

# Отдельная БД под проект тату-мастера
DATABASE_NAME = "tattoo_db.sqlite"

FIXED_ENTITIES = [
    "Финансы",
    "Расписание",
    "Записи",
    "Услуги",
    "Клиенты",
    "Эскизы",
]

INITIAL_SCHEMAS = {
    "Услуги": "ID INTEGER PRIMARY KEY AUTOINCREMENT, Название TEXT, Цена REAL, Длительность INTEGER",
    "Клиенты": "ID INTEGER PRIMARY KEY AUTOINCREMENT, ФИО TEXT, Телефон TEXT",
    # Для совместимости оставляем ID_Услуги (как «основная услуга»), а список услуг живёт в таблице Запись_Услуги
    "Записи": "ID INTEGER PRIMARY KEY AUTOINCREMENT, Дата TEXT, Время TEXT, ID_Клиента INTEGER, ID_Услуги INTEGER",
    "Финансы": "ID INTEGER PRIMARY KEY AUTOINCREMENT, Тип TEXT, Сумма REAL, Дата TEXT, Описание TEXT",
    # Эскизы: хранение каталога идей/референсов (файл — путь на диске)
    "Эскизы": "ID INTEGER PRIMARY KEY AUTOINCREMENT, Название TEXT, Стиль TEXT, Описание TEXT, Файл TEXT",
}