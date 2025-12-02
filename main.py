import sys
import sqlite3
import shutil
from pathlib import Path
from datetime import date, timedelta

from PyQt5 import QtWidgets, QtCore, QtGui


class NewSessionDialog(QtWidgets.QDialog):
    """Диалог для записи нового сеанса."""

    def __init__(self, parent=None, db_path: Path | None = None, day_text: str = "", time_text: str = ""):
        super().__init__(parent)
        self.db_path = db_path
        self._saved_data = None
        self.setWindowTitle("Запись нового сеанса")
        self.setModal(True)
        self.resize(400, 450)

        main_layout = QtWidgets.QVBoxLayout(self)

        form_layout = QtWidgets.QFormLayout()

        # Поля формы
        self.date_edit = QtWidgets.QLineEdit()
        self.time_edit = QtWidgets.QLineEdit()
        self.client_combo = QtWidgets.QComboBox()
        self.service_combo = QtWidgets.QComboBox()
        self.sketch_combo = QtWidgets.QComboBox()
        self.price_edit = QtWidgets.QLineEdit()
        self.comment_edit = QtWidgets.QTextEdit()

        # Поле стоимости только для просмотра (автоматический расчёт)
        self.price_edit.setReadOnly(True)

        # Загружаем данные из БД в списки
        if self.db_path is not None:
            self._load_clients()
            self._load_services()
            self._load_sketches()

        # Автоматический пересчёт стоимости при смене услуги
        self.service_combo.currentIndexChanged.connect(self._update_price)

        # Предзаполняем дату и время
        self.date_edit.setText(day_text)
        self.time_edit.setText(time_text)

        # Изначально посчитаем стоимость
        self._update_price()

        form_layout.addRow("Дата:", self.date_edit)
        form_layout.addRow("Время:", self.time_edit)
        form_layout.addRow("Клиент:", self.client_combo)
        form_layout.addRow("Услуга:", self.service_combo)
        form_layout.addRow("Эскиз:", self.sketch_combo)
        form_layout.addRow("Стоимость:", self.price_edit)
        form_layout.addRow("Комментарий:", self.comment_edit)

        main_layout.addLayout(form_layout)

        # Кнопки в один ряд
        buttons_layout = QtWidgets.QHBoxLayout()
        btn_save = QtWidgets.QPushButton("Записать")
        btn_back = QtWidgets.QPushButton("Назад")

        btn_save.setFixedHeight(32)
        btn_back.setFixedHeight(32)

        buttons_layout.addStretch(1)
        buttons_layout.addWidget(btn_save)
        buttons_layout.addWidget(btn_back)
        buttons_layout.addStretch(1)

        main_layout.addLayout(buttons_layout)

        btn_save.clicked.connect(self.on_save)
        btn_back.clicked.connect(self.reject)  # закрытие без сохранения

    def on_save(self):
        """Проверка обязательных полей и закрытие диалога при успехе."""
        client_text = self.client_combo.currentText().strip()
        service_text = self.service_combo.currentText().strip()
        client_data = self.client_combo.currentData()
        service_data = self.service_combo.currentData()

        if not client_text or not service_text or client_data is None or service_data is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Ошибка",
                "Поля «Клиент» и «Услуга» являются обязательными для заполнения.",
            )
            return

        service_id, service_price = service_data
        client_id = client_data
        sketch_id = self.sketch_combo.currentData()

        # Сохраняем введённые данные для последующей записи в БД
        try:
            price_value = float(self.price_edit.text().strip() or 0)
        except ValueError:
            price_value = 0.0

        self._saved_data = {
            "date": self.date_edit.text().strip(),
            "time": self.time_edit.text().strip(),
            "client_id": client_id,
            "service_id": service_id,
            "sketch_id": sketch_id,
            "price": price_value,
            "comment": self.comment_edit.toPlainText().strip(),
        }

        self.accept()

    def _load_clients(self):
        """Загрузить список клиентов из базы данных в выпадающий список."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT id, name FROM clients ORDER BY name")
            rows = cur.fetchall()
        finally:
            conn.close()

        self.client_combo.clear()
        for client_id, name in rows:
            self.client_combo.addItem(name, client_id)

    def _load_services(self):
        """Загрузить список услуг из базы данных в выпадающий список."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT id, name, price FROM services ORDER BY name")
            rows = cur.fetchall()
        finally:
            conn.close()

        self.service_combo.clear()
        for service_id, name, price in rows:
            # В userData сохраняем и id, и цену
            self.service_combo.addItem(name, (service_id, price))

    def _load_sketches(self):
        """Загрузить список эскизов из базы данных в выпадающий список."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT id, title FROM sketches ORDER BY title")
            rows = cur.fetchall()
        finally:
            conn.close()

        self.sketch_combo.clear()
        # Добавляем пустой вариант на случай, если эскиз не выбран
        self.sketch_combo.addItem("", None)
        for sketch_id, title in rows:
            self.sketch_combo.addItem(title, sketch_id)

    def _update_price(self):
        """Пересчитать стоимость: базовая цена сеанса + цена выбранной услуги."""
        data = self.service_combo.currentData()
        service_price = 0
        if isinstance(data, tuple) and len(data) == 2:
            _, service_price = data

        total = SESSION_BASE_PRICE + (service_price or 0)
        self.price_edit.setText(str(int(total)))

    def get_data(self):
        """Вернуть сохранённые данные формы (или None, если не сохранено)."""
        return self._saved_data


class ScheduleWindow(QtWidgets.QWidget):
    """Окно с расписанием: 7 дней по горизонтали, часы 9-18 по вертикали."""

    def __init__(self, db_path: Path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.setWindowTitle("Текущие записи")
        self.resize(800, 500)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.table = QtWidgets.QTableWidget()
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.table.setColumnCount(7)
        self.table.setRowCount(10)  # часы с 9 до 18 включительно (10 строк)

        # Заголовки столбцов — дни недели + текущая неделя (дата в формате ДД/ММ)
        self._set_week_headers()

        # Заполняем каждую ячейку временем, вертикальные заголовки не используем
        hours = [f"{h}:00" for h in range(9, 19)]
        for row, hour in enumerate(hours):
            for col in range(7):
                item = QtWidgets.QTableWidgetItem(hour)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                self.table.setItem(row, col, item)

        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)

        # Каждая клетка кликабельна
        self.table.cellClicked.connect(self.on_cell_clicked)

        # Кнопка "Назад" внизу
        btn_back = QtWidgets.QPushButton("Назад")
        btn_back.setFixedHeight(40)
        btn_back.clicked.connect(self.close)

        layout.addWidget(self.table)
        layout.addWidget(btn_back)

    def on_cell_clicked(self, row: int, column: int):
        """Обработка клика по ячейке расписания: открываем окно записи сеанса."""
        day_item = self.table.horizontalHeaderItem(column)
        full_header = day_item.text() if day_item else ""

        # Ожидается формат: 'Понедельник  02/12' → берём только дату после последнего пробела
        day_text = full_header.split()[-1] if full_header else ""

        cell_item = self.table.item(row, column)
        time_text = cell_item.text() if cell_item else ""

        dialog = NewSessionDialog(self, db_path=self.db_path, day_text=day_text, time_text=time_text)
        result = dialog.exec_()
        if result == QtWidgets.QDialog.Accepted:
            data = dialog.get_data()
            if not data:
                return

            # Записываем новый сеанс в БД
            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO appointments (client_id, date, time, service_id, sketch_id, price, status, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        data["client_id"],
                        data["date"],
                        data["time"],
                        data["service_id"],
                        data["sketch_id"],
                        data["price"],
                        "Запланирован",
                        data["comment"],
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            # Обновляем внешний вид ячейки: красный фон и цена под временем
            item = self.table.item(row, column)
            if item is None:
                item = QtWidgets.QTableWidgetItem()
                self.table.setItem(row, column, item)

            display_text = f"{time_text}\n{int(data['price'])} руб."
            item.setText(display_text)
            item.setTextAlignment(QtCore.Qt.AlignCenter)
            item.setBackground(QtGui.QColor(255, 150, 150))  # светло-красный

    def _set_week_headers(self):
        """Установить заголовки столбцов как дни недели с датами текущей недели."""
        # Определяем понедельник текущей недели
        today = date.today()
        monday = today - timedelta(days=today.weekday())

        day_names = [
            "Понедельник",
            "Вторник",
            "Среда",
            "Четверг",
            "Пятница",
            "Суббота",
            "Воскресенье",
        ]

        headers = []
        for i in range(7):
            day_date = monday + timedelta(days=i)
            headers.append(f"{day_names[i]}  {day_date:%d/%m}")

        self.table.setHorizontalHeaderLabels(headers)


class ClientsWindow(QtWidgets.QWidget):
    """Окно со списком всех записанных клиентов."""

    def __init__(self, db_path: Path, parent=None):
        super().__init__(parent)
        self.db_path = db_path

        self.setWindowTitle("Список клиентов")
        self.resize(800, 500)

        layout = QtWidgets.QVBoxLayout(self)

        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ФИО", "Телефон", "День рождения", "Комментарии"])
        self.table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)

        # Кнопки снизу: Добавить, Удалить, Назад
        buttons_layout = QtWidgets.QHBoxLayout()
        btn_add = QtWidgets.QPushButton("Добавить")
        btn_delete = QtWidgets.QPushButton("Удалить")
        btn_back = QtWidgets.QPushButton("Назад")
        btn_add.setFixedHeight(40)
        btn_delete.setFixedHeight(40)
        btn_back.setFixedHeight(40)
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(btn_add)
        buttons_layout.addWidget(btn_delete)
        buttons_layout.addWidget(btn_back)
        buttons_layout.addStretch(1)

        layout.addWidget(self.table)
        layout.addLayout(buttons_layout)

        btn_back.clicked.connect(self.close)
        btn_add.clicked.connect(self.add_client)
        btn_delete.clicked.connect(self.delete_client)

        self._load_clients()

    def _load_clients(self):
        """Загрузить всех клиентов из базы данных в таблицу."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT id, name, phone, email, notes FROM clients ORDER BY name")
            rows = cur.fetchall()
        finally:
            conn.close()

        self.table.setRowCount(len(rows))
        for row_idx, (client_id, name, phone, email, notes) in enumerate(rows):
            name_item = QtWidgets.QTableWidgetItem(name or "")
            # Сохраняем id клиента в скрытых данных строки
            name_item.setData(QtCore.Qt.UserRole, client_id)
            self.table.setItem(row_idx, 0, name_item)
            self.table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(phone or ""))
            self.table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(email or ""))
            self.table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(notes or ""))

    def add_client(self):
        """Открыть диалог для добавления нового клиента."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Добавление клиента")
        dialog_layout = QtWidgets.QVBoxLayout(dialog)

        form = QtWidgets.QFormLayout()
        name_edit = QtWidgets.QLineEdit()
        phone_edit = QtWidgets.QLineEdit()
        birthday_edit = QtWidgets.QLineEdit()
        notes_edit = QtWidgets.QTextEdit()

        form.addRow("ФИО*:", name_edit)
        form.addRow("Телефон:", phone_edit)
        form.addRow("День рождения:", birthday_edit)
        form.addRow("Комментарии:", notes_edit)

        dialog_layout.addLayout(form)

        btns_layout = QtWidgets.QHBoxLayout()
        btn_save = QtWidgets.QPushButton("Сохранить")
        btn_cancel = QtWidgets.QPushButton("Отмена")
        btns_layout.addStretch(1)
        btns_layout.addWidget(btn_save)
        btns_layout.addWidget(btn_cancel)
        btns_layout.addStretch(1)

        dialog_layout.addLayout(btns_layout)

        def choose_birthday():
            """Открыть календарь для выбора дня рождения."""
            cal_dialog = QtWidgets.QDialog(dialog)
            cal_dialog.setWindowTitle("Выбор даты рождения")
            cal_layout = QtWidgets.QVBoxLayout(cal_dialog)

            calendar = QtWidgets.QCalendarWidget()
            calendar.setGridVisible(True)
            cal_layout.addWidget(calendar)

            btns = QtWidgets.QHBoxLayout()
            btn_ok = QtWidgets.QPushButton("Выбрать")
            btn_cancel = QtWidgets.QPushButton("Отмена")
            btns.addStretch(1)
            btns.addWidget(btn_ok)
            btns.addWidget(btn_cancel)
            btns.addStretch(1)
            cal_layout.addLayout(btns)

            def set_date():
                qdate = calendar.selectedDate()
                birthday_edit.setText(qdate.toString("dd/MM/yyyy"))
                cal_dialog.accept()

            btn_ok.clicked.connect(set_date)
            btn_cancel.clicked.connect(cal_dialog.reject)

            cal_dialog.exec_()

        # При нажатии на поле "День рождения" открываем календарь
        birthday_edit.setReadOnly(True)
        birthday_edit.mousePressEvent = lambda event: (choose_birthday(), None)[1]

        def on_save():
            name = name_edit.text().strip()
            if not name:
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Поле «ФИО» обязательно для заполнения.")
                return
            phone = phone_edit.text().strip()
            birthday = birthday_edit.text().strip()
            notes = notes_edit.toPlainText().strip()

            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO clients (name, phone, email, notes) VALUES (?, ?, ?, ?)",
                    (name, phone, birthday, notes),
                )
                conn.commit()
            finally:
                conn.close()

            self._load_clients()
            dialog.accept()

        btn_save.clicked.connect(on_save)
        btn_cancel.clicked.connect(dialog.reject)

        dialog.exec_()

    def delete_client(self):
        """Удалить выбранного клиента из базы данных."""
        row = self.table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.information(self, "Удаление клиента", "Сначала выберите клиента в списке.")
            return

        item = self.table.item(row, 0)
        if item is None:
            return

        client_id = item.data(QtCore.Qt.UserRole)
        client_name = item.text()

        reply = QtWidgets.QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы действительно хотите удалить клиента «{client_name}»?\n"
            f"Все связанные записи сеансов также будут удалены.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM clients WHERE id = ?", (client_id,))
            conn.commit()
        finally:
            conn.close()

        self._load_clients()


class SketchesWindow(QtWidgets.QWidget):
    """Окно с эскизами: просмотр и добавление новых."""

    def __init__(self, db_path: Path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.media_dir = Path("sketches")
        self.media_dir.mkdir(exist_ok=True)

        self.setWindowTitle("Список эскизов")
        self.resize(900, 600)

        layout = QtWidgets.QVBoxLayout(self)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setViewMode(QtWidgets.QListView.IconMode)
        self.list_widget.setIconSize(QtCore.QSize(200, 200))
        self.list_widget.setResizeMode(QtWidgets.QListView.Adjust)
        self.list_widget.setMovement(QtWidgets.QListView.Static)
        self.list_widget.setSpacing(15)

        buttons_layout = QtWidgets.QHBoxLayout()
        btn_add = QtWidgets.QPushButton("Добавить эскиз")
        btn_back = QtWidgets.QPushButton("Назад")
        btn_add.setFixedHeight(40)
        btn_back.setFixedHeight(40)

        buttons_layout.addStretch(1)
        buttons_layout.addWidget(btn_add)
        buttons_layout.addWidget(btn_back)
        buttons_layout.addStretch(1)

        layout.addWidget(self.list_widget)
        layout.addLayout(buttons_layout)

        btn_back.clicked.connect(self.close)
        btn_add.clicked.connect(self.add_sketch)

        self._load_sketches()

    def _load_sketches(self):
        """Загрузить эскизы из базы и показать их."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT id, title, description, image_path FROM sketches ORDER BY id DESC")
            rows = cur.fetchall()
        finally:
            conn.close()

        self.list_widget.clear()
        for sketch_id, title, description, image_path in rows:
            item = QtWidgets.QListWidgetItem(title or "Без названия")
            item.setData(QtCore.Qt.UserRole, sketch_id)
            tooltip = description or ""
            if image_path:
                tooltip = f"{title}\n{description}" if description else title
            item.setToolTip(tooltip)

            if image_path:
                img_path = Path(image_path)
                if not img_path.is_absolute():
                    img_path = Path.cwd() / img_path
                if img_path.exists():
                    pixmap = QtGui.QPixmap(str(img_path))
                    if not pixmap.isNull():
                        item.setIcon(QtGui.QIcon(pixmap))

            self.list_widget.addItem(item)

    def add_sketch(self):
        """Добавление нового эскиза."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Добавить новый эскиз")
        dialog_layout = QtWidgets.QVBoxLayout(dialog)

        form = QtWidgets.QFormLayout()
        title_edit = QtWidgets.QLineEdit()
        description_edit = QtWidgets.QTextEdit()
        image_path_edit = QtWidgets.QLineEdit()
        image_path_edit.setReadOnly(True)
        select_btn = QtWidgets.QPushButton("Выбрать изображение")

        def choose_image():
            file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
                dialog,
                "Выбор изображения",
                "",
                "Изображения (*.png *.jpg *.jpeg *.bmp *.gif)",
            )
            if file_path:
                image_path_edit.setText(file_path)

        select_btn.clicked.connect(choose_image)

        form.addRow("Название*:", title_edit)
        form.addRow("Описание:", description_edit)
        image_layout = QtWidgets.QHBoxLayout()
        image_layout.addWidget(image_path_edit)
        image_layout.addWidget(select_btn)
        form.addRow("Файл изображения*:", image_layout)

        dialog_layout.addLayout(form)

        buttons_layout = QtWidgets.QHBoxLayout()
        btn_save = QtWidgets.QPushButton("Сохранить")
        btn_cancel = QtWidgets.QPushButton("Отмена")
        buttons_layout.addStretch(1)
        buttons_layout.addWidget(btn_save)
        buttons_layout.addWidget(btn_cancel)
        buttons_layout.addStretch(1)

        dialog_layout.addLayout(buttons_layout)

        def on_save():
            title = title_edit.text().strip()
            image_source = image_path_edit.text().strip()
            description = description_edit.toPlainText().strip()

            if not title or not image_source:
                QtWidgets.QMessageBox.warning(
                    dialog,
                    "Ошибка",
                    "Необходимо указать название и выбрать изображение эскиза.",
                )
                return

            src_path = Path(image_source)
            if not src_path.exists():
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Выбранный файл не существует.")
                return

            # Копируем файл в каталог sketches с уникальным именем
            target_name = f"{int(QtCore.QDateTime.currentSecsSinceEpoch())}_{src_path.name}"
            target_path = self.media_dir / target_name
            try:
                shutil.copy(src_path, target_path)
            except OSError as exc:
                QtWidgets.QMessageBox.critical(dialog, "Ошибка копирования", str(exc))
                return

            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO sketches (title, description, image_path) VALUES (?, ?, ?)",
                    (title, description, str(target_path)),
                )
                conn.commit()
            finally:
                conn.close()

            self._load_sketches()
            dialog.accept()

        btn_save.clicked.connect(on_save)
        btn_cancel.clicked.connect(dialog.reject)

        dialog.exec_()

DB_NAME = "tattoo_master.db"
SESSION_BASE_PRICE = 2000  # базовая стоимость одного сеанса, руб.


def init_db(db_path: Path) -> None:
    """Инициализация базы данных (создание таблиц, если их еще нет)."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Таблица клиентов
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            notes TEXT
        )
        """
    )

    # Таблица услуг
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            price REAL,
            description TEXT
        )
        """
    )

    # Таблица эскизов
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS sketches (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            image_path TEXT
        )
        """
    )

    # Таблица услуг / сеансов (записи)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT,
            service_id INTEGER,
            sketch_id INTEGER,
            price REAL,
            status TEXT,
            notes TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES services(id),
            FOREIGN KEY (sketch_id) REFERENCES sketches(id)
        )
        """
    )

    # Если база была создана раньше и в таблице appointments нет новых колонок,
    # добавим их через ALTER TABLE, чтобы избежать ошибок вида
    # "no column named service_id".
    cur.execute("PRAGMA table_info(appointments)")
    existing_cols = {row[1] for row in cur.fetchall()}  # row[1] = name

    if "service_id" not in existing_cols:
        cur.execute("ALTER TABLE appointments ADD COLUMN service_id INTEGER")
    if "sketch_id" not in existing_cols:
        cur.execute("ALTER TABLE appointments ADD COLUMN sketch_id INTEGER")

    # Заполним таблицу услуг примерами, если она пустая
    cur.execute("SELECT COUNT(*) FROM services")
    count_services = cur.fetchone()[0]
    if count_services == 0:
        cur.executemany(
            "INSERT INTO services (name, price, description) VALUES (?, ?, ?)",
            [
                ("Татуировка (маленькая)", 3000, "Небольшие татуировки до 5 см"),
                ("Татуировка (средняя)", 6000, "Средние татуировки до 15 см"),
                ("Татуировка (большая)", 12000, "Крупные татуировки"),
                ("Обновление татуировки", 4000, "Обновление старых татуировок"),
                ("Консультация", 0, "Предварительная консультация клиента"),
            ],
        )

    conn.commit()
    conn.close()


class MainWindow(QtWidgets.QMainWindow):
    """Главное окно информационной системы тату-мастера."""

    def __init__(self, db_path: Path):
        super().__init__()
        self.db_path = db_path
        self.setWindowTitle("Информационная система тату-мастера")
        self.resize(900, 600)

        self._setup_ui()

    def _setup_ui(self):
        # Главное меню
        central = QtWidgets.QWidget()
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(40, 40, 40, 40)
        main_layout.setSpacing(30)

        # Заголовок ИС сверху
        title_label = QtWidgets.QLabel("Информационная система \"Тату-Мастер\"")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        font = title_label.font()
        font.setPointSize(20)
        font.setBold(True)
        title_label.setFont(font)

        # Контейнер для кнопок по центру
        buttons_container = QtWidgets.QWidget()
        buttons_layout = QtWidgets.QVBoxLayout(buttons_container)
        buttons_layout.setSpacing(15)
        buttons_layout.setAlignment(QtCore.Qt.AlignCenter)

        btn_current = QtWidgets.QPushButton("Текущие записи")
        btn_clients = QtWidgets.QPushButton("Список клиентов")
        btn_sketches = QtWidgets.QPushButton("Список эскизов")
        btn_exit = QtWidgets.QPushButton("Выход")

        # Сделаем кнопки крупнее
        button_font = btn_current.font()
        button_font.setPointSize(14)
        btn_current.setFont(button_font)
        btn_clients.setFont(button_font)
        btn_sketches.setFont(button_font)
        btn_exit.setFont(button_font)

        btn_current.setMinimumHeight(60)
        btn_clients.setMinimumHeight(60)
        btn_sketches.setMinimumHeight(60)
        btn_exit.setMinimumHeight(60)

        # Ширина кнопок
        button_width = 320
        btn_current.setMinimumWidth(button_width)
        btn_clients.setMinimumWidth(button_width)
        btn_sketches.setMinimumWidth(button_width)
        btn_exit.setMinimumWidth(button_width)

        buttons_layout.addWidget(btn_current)
        buttons_layout.addWidget(btn_clients)
        buttons_layout.addWidget(btn_sketches)
        buttons_layout.addWidget(btn_exit)

        # Размещаем: заголовок, растяжка, блок кнопок, растяжка
        main_layout.addWidget(title_label)
        main_layout.addStretch(1)
        main_layout.addWidget(buttons_container, alignment=QtCore.Qt.AlignCenter)
        main_layout.addStretch(2)

        # Действия кнопок
        btn_current.clicked.connect(self.open_schedule_window)
        btn_clients.clicked.connect(self.open_clients_window)
        btn_sketches.clicked.connect(self.open_sketches_window)
        btn_exit.clicked.connect(self.close)

        self.setCentralWidget(central)

    def open_schedule_window(self):
        """Открыть окно с текущими записями (расписание на 7 дней)."""
        window = ScheduleWindow(self.db_path, self)
        window.showMaximized()

    def open_clients_window(self):
        """Открыть окно со списком клиентов."""
        window = ClientsWindow(self.db_path, self)
        window.show()

    def open_sketches_window(self):
        """Открыть окно с эскизами."""
        window = SketchesWindow(self.db_path, self)
        window.show()

    def _create_clients_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        # Таблица клиентов
        self.clients_table = QtWidgets.QTableWidget()
        self.clients_table.setColumnCount(4)
        self.clients_table.setHorizontalHeaderLabels(
            ["ФИО", "Телефон", "E-mail", "Заметки"]
        )
        self.clients_table.horizontalHeader().setStretchLastSection(True)

        # Кнопки
        buttons_layout = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Добавить клиента")
        edit_btn = QtWidgets.QPushButton("Изменить")
        delete_btn = QtWidgets.QPushButton("Удалить")

        buttons_layout.addWidget(add_btn)
        buttons_layout.addWidget(edit_btn)
        buttons_layout.addWidget(delete_btn)
        buttons_layout.addStretch()

        layout.addWidget(self.clients_table)
        layout.addLayout(buttons_layout)

        return widget

    def _create_appointments_tab(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)

        self.appointments_table = QtWidgets.QTableWidget()
        self.appointments_table.setColumnCount(6)
        self.appointments_table.setHorizontalHeaderLabels(
            ["Клиент", "Дата", "Время", "Услуга", "Цена", "Статус"]
        )
        self.appointments_table.horizontalHeader().setStretchLastSection(True)

        buttons_layout = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Добавить запись")
        edit_btn = QtWidgets.QPushButton("Изменить")
        delete_btn = QtWidgets.QPushButton("Удалить")

        buttons_layout.addWidget(add_btn)
        buttons_layout.addWidget(edit_btn)
        buttons_layout.addWidget(delete_btn)
        buttons_layout.addStretch()

        layout.addWidget(self.appointments_table)
        layout.addLayout(buttons_layout)

        return widget


def main():
    app = QtWidgets.QApplication(sys.argv)

    db_path = Path(DB_NAME)
    init_db(db_path)

    window = MainWindow(db_path)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()