import sys
import sqlite3
import shutil
from pathlib import Path
from datetime import date, timedelta

from PyQt5 import QtWidgets, QtCore, QtGui


class PhoneMaskEdit(QtWidgets.QLineEdit):
    """
    Поле ввода телефона без жёсткой маски.

    Разрешаем пользователю вводить номер в любом удобном виде
    (+79991234567, 8 999 123-45-67 и т.п.), а корректность проверяем
    уже при сохранении по количеству цифр.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        # Подсказка по ожидаемому формату, но без ограничения ввода
        self.setPlaceholderText("+7XXXXXXXXXX")


class NewSessionDialog(QtWidgets.QDialog):
    """Диалог для записи нового сеанса."""

    def __init__(self, parent=None, db_path: Path | None = None, day_text: str = "", time_text: str = ""):
        super().__init__(parent)
        self.db_path = db_path
        self._saved_data = None
        self.setWindowTitle("Запись нового сеанса")
        self.setModal(True)
        self.resize(400, 450)
        
        # Проверяем, есть ли уже запись на это время
        self.has_existing_appointment = False
        if db_path and day_text and time_text:
            self.has_existing_appointment = self._check_existing_appointment(day_text, time_text)

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

        # Поля даты и времени только для просмотра (передаются из расписания)
        self.date_edit.setReadOnly(True)
        self.time_edit.setReadOnly(True)

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
        
        # Если есть существующая запись, показываем кнопку "Удалить", иначе "Назад"
        if self.has_existing_appointment:
            btn_action = QtWidgets.QPushButton("Удалить")
            btn_action.clicked.connect(self.on_delete)
        else:
            btn_action = QtWidgets.QPushButton("Назад")
            btn_action.clicked.connect(self.reject)

        btn_save.setFixedHeight(32)
        btn_action.setFixedHeight(32)

        buttons_layout.addStretch(1)
        buttons_layout.addWidget(btn_save)
        buttons_layout.addWidget(btn_action)
        buttons_layout.addStretch(1)

        main_layout.addLayout(buttons_layout)

        btn_save.clicked.connect(self.on_save)

    def on_save(self):
        """Проверка обязательных полей и закрытие диалога при успехе."""
        date_text = self.date_edit.text().strip()
        time_text = self.time_edit.text().strip()
        client_text = self.client_combo.currentText().strip()
        service_text = self.service_combo.currentText().strip()
        price_text = self.price_edit.text().strip()
        
        client_data = self.client_combo.currentData()
        service_data = self.service_combo.currentData()

        # Проверяем все обязательные поля
        if not date_text or not time_text or not client_text or not service_text or not price_text:
            QtWidgets.QMessageBox.warning(
                self,
                "Ошибка",
                "Поля «Дата», «Время», «Клиент», «Услуга» и «Стоимость» обязательны для заполнения.",
            )
            return
        
        if client_data is None or service_data is None:
            QtWidgets.QMessageBox.warning(
                self,
                "Ошибка",
                "Поля «Клиент» и «Услуга» должны быть выбраны из списка.",
            )
            return

        service_id, service_price = service_data
        client_id = client_data
        sketch_id = self.sketch_combo.currentData()

        # Сохраняем введённые данные для последующей записи в БД
        try:
            price_value = float(price_text or 0)
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

    def _check_existing_appointment(self, date_text: str, time_text: str) -> bool:
        """Проверить, есть ли уже запись на это время."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                'SELECT COUNT(*) FROM "записи" WHERE date = ? AND time = ?',
                (date_text, time_text)
            )
            result = cur.fetchone()
            count = result[0] if result else 0
            return count > 0
        finally:
            try:
                conn.close()
            except Exception:
                pass
    
    def on_delete(self):
        """Удалить существующую запись."""
        reply = QtWidgets.QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы уверены, что хотите удалить запись на {self.date_edit.text()} в {self.time_edit.text()}?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply != QtWidgets.QMessageBox.Yes:
            return
        
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                'DELETE FROM "записи" WHERE date = ? AND time = ?',
                (self.date_edit.text().strip(), self.time_edit.text().strip())
            )
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass
        
        QtWidgets.QMessageBox.information(self, "Успех", "Запись успешно удалена.")
        self.reject()  # Закрываем диалог

    def _load_clients(self):
        """Загрузить список клиентов из базы данных в выпадающий список."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT id, name FROM \"клиенты\" ORDER BY name")
            rows = cur.fetchall()
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self.client_combo.clear()
        for client_id, name in rows:
            self.client_combo.addItem(name, client_id)

    def _load_services(self):
        """Загрузить список услуг из базы данных в выпадающий список."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT id, name, price FROM \"услуги\" ORDER BY name")
            rows = cur.fetchall()
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self.service_combo.clear()
        for service_id, name, price in rows:
            # В userData сохраняем и id, и цену
            self.service_combo.addItem(name, (service_id, price))

    def _load_sketches(self):
        """Загрузить список эскизов из базы данных в выпадающий список."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT id, title FROM \"эскизы\" ORDER BY title")
            rows = cur.fetchall()
        finally:
            try:
                conn.close()
            except Exception:
                pass

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
        self.resize(1366, 768)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Track the current week's Monday (start of week)
        today = date.today()
        self.week_start = today - timedelta(days=today.weekday())

        # Navigation controls for weeks
        nav_widget = QtWidgets.QWidget()
        nav_layout = QtWidgets.QHBoxLayout(nav_widget)
        nav_layout.setContentsMargins(6, 6, 6, 6)
        btn_prev = QtWidgets.QPushButton("← Предыдущая неделя")
        btn_today = QtWidgets.QPushButton("Сегодня")
        btn_next = QtWidgets.QPushButton("Следующая неделя →")
        nav_layout.addWidget(btn_prev)
        nav_layout.addStretch(1)
        nav_layout.addWidget(btn_today)
        nav_layout.addStretch(1)
        nav_layout.addWidget(btn_next)
        btn_prev.clicked.connect(self.prev_week)
        btn_next.clicked.connect(self.next_week)
        btn_today.clicked.connect(self.goto_today)

        layout.addWidget(nav_widget)

        self.table = QtWidgets.QTableWidget()
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.table.setColumnCount(7)
        self.table.setRowCount(10)  # часы с 9 до 18 включительно (10 строк)

        # Запомним часы для сопоставления с временными метками в записях
        self.hours = [f"{h}:00" for h in range(9, 19)]

        # Заголовки столбцов — дни недели + неделя, начинающаяся с self.week_start
        self._set_week_headers()

        # Заполняем каждую ячейку временем по умолчанию; вертикальные заголовки не используем
        light_green = QtGui.QColor(220, 245, 220)  # Более светлый зелёный (пастель)
        light_red = QtGui.QColor(245, 220, 220)    # Более светлый красный (пастель)
        dark_text = QtGui.QColor(30, 30, 30)        # Тёмный текст для контраста
        for row, hour in enumerate(self.hours):
            for col in range(7):
                item = QtWidgets.QTableWidgetItem(hour)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setBackground(light_green)
                item.setForeground(dark_text)
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

        layout.addWidget(self.table, 1)
        # Загрузим записи для отображаемой недели
        self._load_appointments_for_week()

        # Помещаем кнопку "Назад" в контейнер внизу и центрируем её
        btn_container = QtWidgets.QWidget()
        btn_layout = QtWidgets.QHBoxLayout(btn_container)
        btn_layout.setContentsMargins(8, 8, 8, 8)
        btn_layout.addStretch(1)
        btn_layout.addWidget(btn_back)
        btn_layout.addStretch(1)
        layout.addWidget(btn_container)

    def on_cell_clicked(self, row: int, column: int):
        """Обработка клика по ячейке расписания: открываем окно записи сеанса."""
        day_item = self.table.horizontalHeaderItem(column)
        full_header = day_item.text() if day_item else ""

        # Ожидается формат: 'Понедельник  02/12' → берём только дату после последнего пробела
        day_text = full_header.split()[-1] if full_header else ""

        # Получаем время из списка часов по индексу строки
        time_text = self.hours[row] if row < len(self.hours) else ""

        dialog = NewSessionDialog(self, db_path=self.db_path, day_text=day_text, time_text=time_text)
        result = dialog.exec_()
        
        # Флаг для отслеживания, была ли запись удалена
        appointment_deleted = False
        
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
                    INSERT INTO "записи" (client_id, date, time, service_id, sketch_id, price, status, notes)
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
        else:
            # Диалог был отклонен - проверяем, была ли удалена запись
            # Это происходит, когда пользователь нажимает "Удалить"
            appointment_deleted = dialog.has_existing_appointment and not dialog._check_existing_appointment(day_text, time_text)
        
        # Всегда перезагружаем расписание после закрытия диалога
        # (независимо от того, была ли добавлена новая запись или удалена существующая)
        self._load_appointments_for_week()

    def _set_week_headers(self):
        """Установить заголовки столбцов как дни недели с датами текущей недели."""
        # Используем self.week_start как понедельник отображаемой недели
        monday = getattr(self, 'week_start', date.today() - timedelta(days=date.today().weekday()))

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

    def prev_week(self):
        """Перейти на предыдущую неделю и обновить отображение."""
        self.week_start = self.week_start - timedelta(days=7)
        self._refresh_week()

    def next_week(self):
        """Перейти на следующую неделю и обновить отображение."""
        self.week_start = self.week_start + timedelta(days=7)
        self._refresh_week()

    def goto_today(self):
        """Вернуться к текущей неделе (сегодня)."""
        today = date.today()
        self.week_start = today - timedelta(days=today.weekday())
        self._refresh_week()

    def _refresh_week(self):
        """Обновить заголовки и содержимое таблицы для текущей недели."""
        # Сброс ячеек к значению времени по умолчанию (светло-зелёный — нет записи)
        light_green = QtGui.QColor(220, 245, 220)  # Более светлый зелёный (пастель)
        dark_text = QtGui.QColor(30, 30, 30)        # Тёмный текст для контраста
        for row, hour in enumerate(self.hours):
            for col in range(7):
                item = self.table.item(row, col)
                if item is None:
                    item = QtWidgets.QTableWidgetItem()
                    self.table.setItem(row, col, item)
                item.setText(hour)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setBackground(light_green)
                item.setForeground(dark_text)

        self._set_week_headers()
        self._load_appointments_for_week()

    def _load_appointments_for_week(self):
        """Загрузить записи из БД и отобразить их для текущей недели."""
        # Сначала очищаем все ячейки, возвращая их в исходное состояние (пустые, светло-зелёные)
        light_green = QtGui.QColor(220, 245, 220)  # Более светлый зелёный (пастель)
        dark_text = QtGui.QColor(30, 30, 30)        # Тёмный текст для контраста
        
        for row, hour in enumerate(self.hours):
            for col in range(7):
                item = self.table.item(row, col)
                if item is None:
                    item = QtWidgets.QTableWidgetItem()
                    self.table.setItem(row, col, item)
                item.setText(hour)
                item.setBackground(light_green)
                item.setForeground(dark_text)
        
        # Теперь загружаем записи из БД и отображаем их
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute('SELECT client_id, date, time, price FROM "записи"')
            rows = cur.fetchall()
        finally:
            try:
                conn.close()
            except Exception:
                pass

        # Собираем отображаемые даты в формате ДД/ММ из заголовков
        headers = [self.table.horizontalHeaderItem(c).text().split()[-1] for c in range(7)]

        # Цвета
        light_red = QtGui.QColor(245, 220, 220)    # Более светлый красный (пастель)

        for client_id, date_text, time_text, price in rows:
            # Поддерживаем совпадение по формату ДД/MM
            if date_text in headers:
                col = headers.index(date_text)
                # Найдём строку по времени
                try:
                    row = self.hours.index(time_text)
                except ValueError:
                    # Если точного совпадения нет, пропускаем
                    continue

                item = self.table.item(row, col)
                if item is None:
                    item = QtWidgets.QTableWidgetItem()
                    self.table.setItem(row, col, item)
                
                item.setText(f"{time_text}\n{int(price)} руб." if price is not None else time_text)
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                item.setBackground(light_red)
                item.setForeground(dark_text)


class ClientsWindow(QtWidgets.QWidget):
    """Окно со списком всех записанных клиентов."""

    def __init__(self, db_path: Path, parent=None):
        super().__init__(parent)
        self.db_path = db_path

        self.setWindowTitle("Список клиентов")
        self.resize(1366, 768)

        layout = QtWidgets.QVBoxLayout(self)

        self.table = QtWidgets.QTableWidget()
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ФИО", "Телефон", "День рождения", "Комментарии"])
        # Настроим приоритеты растяжения колонок: имя и комментарии растягиваются,
        # телефон и день рождения занимают минимально нужное пространство.
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)        # ФИО
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # Телефон
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)  # День рождения
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)        # Комментарии
        self.table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        # Сделаем таблицу неизменяемой (read-only)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        # Двойной клик открывает диалог редактирования
        self.table.doubleClicked.connect(self.on_client_double_click)

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

    def on_client_double_click(self, index):
        """Обработка двойного клика: открыть диалог редактирования клиента."""
        row = index.row()
        if row < 0:
            return

        item = self.table.item(row, 0)
        if item is None:
            return

        client_id = item.data(QtCore.Qt.UserRole)
        # Загрузим данные клиента и откроем диалог редактирования
        self.edit_client(client_id)

    def _load_clients(self):
        """Загрузить всех клиентов из базы данных в таблицу."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT id, name, phone, birthday, notes FROM \"клиенты\" ORDER BY name")
            rows = cur.fetchall()
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self.table.setRowCount(len(rows))
        for row_idx, (client_id, name, phone, birthday, notes) in enumerate(rows):
            name_item = QtWidgets.QTableWidgetItem(name or "")
            # Сохраняем id клиента в скрытых данных строки
            name_item.setData(QtCore.Qt.UserRole, client_id)
            self.table.setItem(row_idx, 0, name_item)
            self.table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(phone or ""))
            self.table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(birthday or ""))
            self.table.setItem(row_idx, 3, QtWidgets.QTableWidgetItem(notes or ""))

    def add_client(self):
        """Открыть диалог для добавления нового клиента."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Добавление клиента")
        dialog_layout = QtWidgets.QVBoxLayout(dialog)

        form = QtWidgets.QFormLayout()
        name_edit = QtWidgets.QLineEdit()
        phone_edit = PhoneMaskEdit()
        birthday_edit = QtWidgets.QLineEdit()
        notes_edit = QtWidgets.QTextEdit()

        form.addRow("ФИО*:", name_edit)
        form.addRow("Телефон*:", phone_edit)
        form.addRow("День рождения*:", birthday_edit)
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

        def validate_russian_phone(phone: str) -> bool:
            """Проверить российский номер по количеству цифр без строгого формата."""
            digits = "".join(ch for ch in phone if ch.isdigit())
            if len(digits) < 10 or len(digits) > 15:
                return False
            # Приводим номера, начинающиеся с 8, к формату на 7
            if digits.startswith("8"):
                digits = "7" + digits[1:]
            # Ожидаем российский номер: 11 цифр и начинается с 7
            return len(digits) == 11 and digits.startswith("7")

        def on_save():
            name = name_edit.text().strip()
            phone = phone_edit.text().strip()
            birthday = birthday_edit.text().strip()
            notes = notes_edit.toPlainText().strip()

            # Проверяем все обязательные поля
            if not name:
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Поле «ФИО» обязательно для заполнения.")
                return
            
            if not phone:
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Поле «Телефон» обязательно для заполнения.")
                return
            
            if not validate_russian_phone(phone):
                QtWidgets.QMessageBox.warning(
                    dialog, 
                    "Ошибка", 
                    "Номер телефона должен быть в формате российского номера.\n"
                    "Примеры: +7 (999) 123-45-67, 8 (999) 123-45-67, +79991234567"
                )
                return
            
            if not birthday:
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Поле «День рождения» обязательно для заполнения.")
                return

            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO \"клиенты\" (name, phone, birthday, notes) VALUES (?, ?, ?, ?)",
                    (name, phone, birthday, notes),
                )
                conn.commit()
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

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
            cur.execute("DELETE FROM \"клиенты\" WHERE id = ?", (client_id,))
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self._load_clients()

    def edit_client(self, client_id):
        """Открыть диалог для редактирования существующего клиента."""
        # Загружаем данные клиента
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute('SELECT name, phone, birthday, notes FROM "клиенты" WHERE id = ?', (client_id,))
            row = cur.fetchone()
        finally:
            try:
                conn.close()
            except Exception:
                pass

        if not row:
            return

        name, phone, birthday, notes = row

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Редактирование клиента")
        dialog_layout = QtWidgets.QVBoxLayout(dialog)

        form = QtWidgets.QFormLayout()
        name_edit = QtWidgets.QLineEdit()
        phone_edit = PhoneMaskEdit()
        birthday_edit = QtWidgets.QLineEdit()
        notes_edit = QtWidgets.QTextEdit()

        name_edit.setText(name or "")
        phone_edit.setText(phone or "")
        birthday_edit.setText(birthday or "")
        notes_edit.setPlainText(notes or "")

        form.addRow("ФИО*:", name_edit)
        form.addRow("Телефон*:", phone_edit)
        form.addRow("День рождения*:", birthday_edit)
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
            btn_cancel_cal = QtWidgets.QPushButton("Отмена")
            btns.addStretch(1)
            btns.addWidget(btn_ok)
            btns.addWidget(btn_cancel_cal)
            btns.addStretch(1)
            cal_layout.addLayout(btns)

            def set_date():
                qdate = calendar.selectedDate()
                birthday_edit.setText(qdate.toString("dd/MM/yyyy"))
                cal_dialog.accept()

            btn_ok.clicked.connect(set_date)
            btn_cancel_cal.clicked.connect(cal_dialog.reject)

            cal_dialog.exec_()

        birthday_edit.setReadOnly(True)
        birthday_edit.mousePressEvent = lambda event: (choose_birthday(), None)[1]

        def validate_russian_phone(phone: str) -> bool:
            """Проверить российский номер по количеству цифр без строгого формата."""
            digits = "".join(ch for ch in phone if ch.isdigit())
            if len(digits) < 10 or len(digits) > 15:
                return False
            if digits.startswith("8"):
                digits = "7" + digits[1:]
            return len(digits) == 11 and digits.startswith("7")

        def on_save():
            new_name = name_edit.text().strip()
            new_phone = phone_edit.text().strip()
            new_birthday = birthday_edit.text().strip()
            new_notes = notes_edit.toPlainText().strip()

            # Проверяем все обязательные поля
            if not new_name:
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Поле «ФИО» обязательно для заполнения.")
                return
            
            if not new_phone:
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Поле «Телефон» обязательно для заполнения.")
                return
            
            if not validate_russian_phone(new_phone):
                QtWidgets.QMessageBox.warning(
                    dialog, 
                    "Ошибка", 
                    "Номер телефона должен быть в формате российского номера.\n"
                    "Примеры: +7 (999) 123-45-67, 8 (999) 123-45-67, +79991234567"
                )
                return
            
            if not new_birthday:
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Поле «День рождения» обязательно для заполнения.")
                return

            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    'UPDATE "клиенты" SET name = ?, phone = ?, birthday = ?, notes = ? WHERE id = ?',
                    (new_name, new_phone, new_birthday, new_notes, client_id),
                )
                conn.commit()
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            self._load_clients()
            dialog.accept()

        btn_save.clicked.connect(on_save)
        btn_cancel.clicked.connect(dialog.reject)

        dialog.exec_()


class ServicesWindow(QtWidgets.QWidget):
    """Окно со списком услуг: просмотр, добавление и редактирование."""

    def __init__(self, db_path: Path, parent=None):
        super().__init__(parent)
        self.db_path = db_path

        self.setWindowTitle("Список услуг")
        self.resize(1366, 768)

        layout = QtWidgets.QVBoxLayout(self)

        # Таблица услуг
        self.table = QtWidgets.QTableWidget()
        self.table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Название", "Цена (руб.)", "Комментарий"])
        # Настроим приоритеты растяжения: название и комментарий растягиваются, цена — по содержимому
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)        # Название
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # Цена
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.Stretch)        # Комментарий
        self.table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)
        # Таблица read-only, редактирование через двойной клик
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.doubleClicked.connect(self.on_service_double_click)

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
        btn_add.clicked.connect(self.add_service)
        btn_delete.clicked.connect(self.delete_service)

        self._load_services()

    def on_service_double_click(self, index):
        """Обработка двойного клика: открыть диалог редактирования услуги."""
        row = index.row()
        if row < 0:
            return

        item = self.table.item(row, 0)
        if item is None:
            return

        service_id = item.data(QtCore.Qt.UserRole)
        self.edit_service(service_id)

    def _load_services(self):
        """Загрузить все услуги из базы данных в таблицу."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute('SELECT id, name, price, description FROM "услуги" ORDER BY name')
            rows = cur.fetchall()
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self.table.setRowCount(len(rows))
        for row_idx, (service_id, name, price, description) in enumerate(rows):
            name_item = QtWidgets.QTableWidgetItem(name or "")
            name_item.setData(QtCore.Qt.UserRole, service_id)
            self.table.setItem(row_idx, 0, name_item)
            
            price_text = f"{price:.2f}" if price is not None else ""
            self.table.setItem(row_idx, 1, QtWidgets.QTableWidgetItem(price_text))
            self.table.setItem(row_idx, 2, QtWidgets.QTableWidgetItem(description or ""))

    def add_service(self):
        """Открыть диалог для добавления новой услуги."""
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Добавление услуги")
        dialog_layout = QtWidgets.QVBoxLayout(dialog)

        form = QtWidgets.QFormLayout()
        name_edit = QtWidgets.QLineEdit()
        price_edit = QtWidgets.QLineEdit()
        comment_edit = QtWidgets.QTextEdit()

        form.addRow("Название*:", name_edit)
        form.addRow("Цена (руб.)*:", price_edit)
        form.addRow("Комментарий:", comment_edit)

        dialog_layout.addLayout(form)

        btns_layout = QtWidgets.QHBoxLayout()
        btn_save = QtWidgets.QPushButton("Сохранить")
        btn_cancel = QtWidgets.QPushButton("Отмена")
        btns_layout.addStretch(1)
        btns_layout.addWidget(btn_save)
        btns_layout.addWidget(btn_cancel)
        btns_layout.addStretch(1)

        dialog_layout.addLayout(btns_layout)

        def on_save():
            name = name_edit.text().strip()
            if not name:
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Поле «Название» обязательно для заполнения.")
                return
            
            price_text = price_edit.text().strip()
            if not price_text:
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Поле «Цена» обязательно для заполнения.")
                return
            
            try:
                price = float(price_text)
            except ValueError:
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Цена должна быть числом.")
                return
            
            comment = comment_edit.toPlainText().strip()

            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    'INSERT INTO "услуги" (name, price, description) VALUES (?, ?, ?)',
                    (name, price, comment),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Услуга с таким названием уже существует.")
                return
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            self._load_services()
            dialog.accept()

        btn_save.clicked.connect(on_save)
        btn_cancel.clicked.connect(dialog.reject)

        dialog.exec_()

    def edit_service(self, service_id):
        """Открыть диалог для редактирования существующей услуги."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute('SELECT name, price, description FROM "услуги" WHERE id = ?', (service_id,))
            row = cur.fetchone()
        finally:
            try:
                conn.close()
            except Exception:
                pass

        if not row:
            return

        name, price, description = row

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Редактирование услуги")
        dialog_layout = QtWidgets.QVBoxLayout(dialog)

        form = QtWidgets.QFormLayout()
        name_edit = QtWidgets.QLineEdit()
        price_edit = QtWidgets.QLineEdit()
        comment_edit = QtWidgets.QTextEdit()

        name_edit.setText(name or "")
        price_edit.setText(str(price or ""))
        comment_edit.setPlainText(description or "")

        form.addRow("Название*:", name_edit)
        form.addRow("Цена (руб.)*:", price_edit)
        form.addRow("Комментарий:", comment_edit)

        dialog_layout.addLayout(form)

        btns_layout = QtWidgets.QHBoxLayout()
        btn_save = QtWidgets.QPushButton("Сохранить")
        btn_cancel = QtWidgets.QPushButton("Отмена")
        btns_layout.addStretch(1)
        btns_layout.addWidget(btn_save)
        btns_layout.addWidget(btn_cancel)
        btns_layout.addStretch(1)

        dialog_layout.addLayout(btns_layout)

        def on_save():
            new_name = name_edit.text().strip()
            if not new_name:
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Поле «Название» обязательно для заполнения.")
                return
            
            new_price_text = price_edit.text().strip()
            if not new_price_text:
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Поле «Цена» обязательно для заполнения.")
                return
            
            try:
                new_price = float(new_price_text)
            except ValueError:
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Цена должна быть числом.")
                return
            
            new_comment = comment_edit.toPlainText().strip()

            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    'UPDATE "услуги" SET name = ?, price = ?, description = ? WHERE id = ?',
                    (new_name, new_price, new_comment, service_id),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Услуга с таким названием уже существует.")
                return
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            self._load_services()
            dialog.accept()

        btn_save.clicked.connect(on_save)
        btn_cancel.clicked.connect(dialog.reject)

        dialog.exec_()

    def delete_service(self):
        """Удалить выбранную услугу из базы данных."""
        row = self.table.currentRow()
        if row < 0:
            QtWidgets.QMessageBox.information(self, "Удаление услуги", "Сначала выберите услугу в списке.")
            return

        item = self.table.item(row, 0)
        if item is None:
            return

        service_id = item.data(QtCore.Qt.UserRole)
        service_name = item.text()

        reply = QtWidgets.QMessageBox.question(
            self,
            "Подтверждение удаления",
            f"Вы действительно хотите удалить услугу «{service_name}»?\n"
            f"Все связанные записи сеансов также будут изменены.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        conn = sqlite3.connect(self.db_path)
        try:
            cur = conn.cursor()
            cur.execute('DELETE FROM "услуги" WHERE id = ?', (service_id,))
            conn.commit()
        finally:
            try:
                conn.close()
            except Exception:
                pass

        self._load_services()


class SketchesWindow(QtWidgets.QWidget):
    """Окно с эскизами: просмотр и добавление новых."""

    def __init__(self, db_path: Path, parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.media_dir = Path("sketches")
        self.media_dir.mkdir(exist_ok=True)

        self.setWindowTitle("Список эскизов")
        self.resize(1366, 768)

        layout = QtWidgets.QVBoxLayout(self)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
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
        self.list_widget.itemDoubleClicked.connect(self.on_sketch_double_click)

        self._load_sketches()

    def _load_sketches(self):
        """Загрузить эскизы из базы и показать их."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("SELECT id, title, description, image_path FROM \"эскизы\" ORDER BY id DESC")
            rows = cur.fetchall()
        finally:
            try:
                conn.close()
            except Exception:
                pass

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

    def on_sketch_double_click(self, item: QtWidgets.QListWidgetItem):
        """Редактировать эскиз по двойному клику."""
        if item is None:
            return
        sketch_id = item.data(QtCore.Qt.UserRole)
        if sketch_id is not None:
            self.edit_sketch(sketch_id)

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
                    "INSERT INTO \"эскизы\" (title, description, image_path) VALUES (?, ?, ?)",
                    (title, description, str(target_path)),
                )
                conn.commit()
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            self._load_sketches()
            dialog.accept()

        btn_save.clicked.connect(on_save)
        btn_cancel.clicked.connect(dialog.reject)

        dialog.exec_()

    def edit_sketch(self, sketch_id: int):
        """Редактирование существующего эскиза."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute('SELECT title, description, image_path FROM "эскизы" WHERE id = ?', (sketch_id,))
            row = cur.fetchone()
        finally:
            try:
                conn.close()
            except Exception:
                pass

        if not row:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Эскиз не найден.")
            return

        current_title, current_description, current_image_path = row

        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Редактировать эскиз")
        dialog_layout = QtWidgets.QVBoxLayout(dialog)

        form = QtWidgets.QFormLayout()
        title_edit = QtWidgets.QLineEdit()
        description_edit = QtWidgets.QTextEdit()
        image_path_edit = QtWidgets.QLineEdit()
        image_path_edit.setReadOnly(True)
        select_btn = QtWidgets.QPushButton("Выбрать изображение")

        title_edit.setText(current_title or "")
        description_edit.setPlainText(current_description or "")
        image_path_edit.setText(current_image_path or "")

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
                    "Необходимо указать название и выбрать файл изображения.",
                )
                return

            # Определяем путь к исходному файлу (для проверки существования)
            src_path = Path(image_source)
            if not src_path.is_absolute():
                src_path = Path.cwd() / src_path

            if not src_path.exists():
                QtWidgets.QMessageBox.warning(dialog, "Ошибка", "Выбранный файл не существует.")
                return

            final_image_path = image_source

            # Если выбран новый файл, копируем его в медиакаталог
            if image_source != (current_image_path or ""):
                target_name = f"{int(QtCore.QDateTime.currentSecsSinceEpoch())}_{src_path.name}"
                target_path = self.media_dir / target_name
                try:
                    shutil.copy(src_path, target_path)
                except OSError as exc:
                    QtWidgets.QMessageBox.critical(dialog, "Ошибка копирования", str(exc))
                    return
                final_image_path = str(target_path)

            conn = sqlite3.connect(self.db_path)
            try:
                cur = conn.cursor()
                cur.execute(
                    'UPDATE "эскизы" SET title = ?, description = ?, image_path = ? WHERE id = ?',
                    (title, description, final_image_path, sketch_id),
                )
                conn.commit()
            finally:
                try:
                    conn.close()
                except Exception:
                    pass

            self._load_sketches()
            dialog.accept()

        btn_save.clicked.connect(on_save)
        btn_cancel.clicked.connect(dialog.reject)

        dialog.exec_()

DB_NAME = "тату_мастер.db"
SESSION_BASE_PRICE = 2000  # базовая стоимость одного сеанса, руб.




def _prepare_and_migrate_db(db_path: Path) -> None:
    """Ensure DB file exists under `db_path` and migrate English table names to Russian.

    If an old file named 'tattoo_master.db' exists and the new file does not,
    create a copy. Then inside the DB, rename tables:
      clients -> клиенты
      services -> услуги
      sketches -> эскизы
      appointments -> записи

    A backup of the DB is created alongside as '<name>.bak' before schema changes.
    """
    old_file = Path("tattoo_master.db")
    # If old file exists and new file doesn't, copy it
    if old_file.exists() and not db_path.exists():
        try:
            shutil.copy(old_file, db_path)
        except OSError:
            pass

    if not db_path.exists():
        return

    # Create a backup
    backup_path = db_path.with_suffix(db_path.suffix + ".bak")
    try:
        shutil.copy(db_path, backup_path)
    except OSError:
        pass

    mapping = {
        "clients": "клиенты",
        "services": "услуги",
        "sketches": "эскизы",
        "appointments": "записи",
    }

    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        for old, new in mapping.items():
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (old,))
            has_old = cur.fetchone() is not None
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (new,))
            has_new = cur.fetchone() is not None
            if has_old and not has_new:
                # Use quoted identifiers to allow non-ASCII names
                cur.execute(f'ALTER TABLE "{old}" RENAME TO "{new}"')
        # If the Russian clients table still has an "email" column, migrate it away.
        try:
            cur.execute('PRAGMA table_info("клиенты")')
            cols = [r[1] for r in cur.fetchall()]
        except Exception:
            cols = []
        if 'email' in cols:
            # Create new table without email
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS "клиенты_new" (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    phone TEXT,
                    birthday TEXT,
                    notes TEXT
                )
                """
            )
            # Build select list mapping existing columns; use NULL when missing
            select_cols = []
            for col in ('id', 'name', 'phone', 'birthday', 'notes'):
                if col in cols:
                    select_cols.append(col)
                else:
                    select_cols.append('NULL')
            cur.execute(
                f'INSERT INTO "клиенты_new" (id, name, phone, birthday, notes) SELECT {", ".join(select_cols)} FROM "клиенты"'
            )
            cur.execute('DROP TABLE "клиенты"')
            cur.execute('ALTER TABLE "клиенты_new" RENAME TO "клиенты"')
        conn.commit()
    finally:
        try:
            conn.close()
        except Exception:
            pass


def init_db(db_path: Path) -> None:
    """Инициализация базы данных (создание таблиц, если их еще нет)."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # Таблица клиентов
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS "клиенты" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone TEXT,
            birthday TEXT,
            notes TEXT
        )
        """
    )

    # Таблица услуг
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS "услуги" (
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
        CREATE TABLE IF NOT EXISTS "эскизы" (
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
        CREATE TABLE IF NOT EXISTS "записи" (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time TEXT,

            service_id INTEGER,
            sketch_id INTEGER,
            price REAL,
            status TEXT,
            notes TEXT,
            FOREIGN KEY (client_id) REFERENCES "клиенты"(id) ON DELETE CASCADE,
            FOREIGN KEY (service_id) REFERENCES "услуги"(id),
            FOREIGN KEY (sketch_id) REFERENCES "эскизы"(id)
        )
        """
    )

    # Если база была создана раньше и в таблице клиенты нет колонки birthday,
    # добавим её через ALTER TABLE
    cur.execute("PRAGMA table_info(\"клиенты\")")
    existing_cols = {row[1] for row in cur.fetchall()}  # row[1] = name

    if "birthday" not in existing_cols:
        cur.execute("ALTER TABLE \"клиенты\" ADD COLUMN birthday TEXT")

    # Если база была создана раньше и в таблице записи нет новых колонок,
    # добавим их через ALTER TABLE, чтобы избежать ошибок вида
    # "no column named service_id".
    cur.execute("PRAGMA table_info(\"записи\")")
    existing_cols = {row[1] for row in cur.fetchall()}  # row[1] = name

    if "service_id" not in existing_cols:
        cur.execute("ALTER TABLE \"записи\" ADD COLUMN service_id INTEGER")
    if "sketch_id" not in existing_cols:
        cur.execute("ALTER TABLE \"записи\" ADD COLUMN sketch_id INTEGER")
    if "duration_hours" not in existing_cols:
        cur.execute("ALTER TABLE \"записи\" ADD COLUMN duration_hours INTEGER DEFAULT 1")

    # Заполним таблицу услуг примерами, если она пустая
    cur.execute("SELECT COUNT(*) FROM \"услуги\"")
    count_services = cur.fetchone()[0]
    if count_services == 0:
        cur.executemany(
            "INSERT INTO \"услуги\" (name, price, description) VALUES (?, ?, ?)",
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
        self.resize(1366, 768)

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
        btn_services = QtWidgets.QPushButton("Список услуг")
        btn_sketches = QtWidgets.QPushButton("Список эскизов")
        btn_exit = QtWidgets.QPushButton("Выход")

        # Сделаем кнопки крупнее
        button_font = btn_current.font()
        button_font.setPointSize(14)
        btn_current.setFont(button_font)
        btn_clients.setFont(button_font)
        btn_services.setFont(button_font)
        btn_sketches.setFont(button_font)
        btn_exit.setFont(button_font)

        btn_current.setMinimumHeight(60)
        btn_clients.setMinimumHeight(60)
        btn_services.setMinimumHeight(60)
        btn_sketches.setMinimumHeight(60)
        btn_exit.setMinimumHeight(60)

        # Ширина кнопок
        button_width = 320
        btn_current.setMinimumWidth(button_width)
        btn_clients.setMinimumWidth(button_width)
        btn_services.setMinimumWidth(button_width)
        btn_sketches.setMinimumWidth(button_width)
        btn_exit.setMinimumWidth(button_width)

        buttons_layout.addWidget(btn_current)
        buttons_layout.addWidget(btn_clients)
        buttons_layout.addWidget(btn_services)
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
        btn_services.clicked.connect(self.open_services_window)
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

    def open_services_window(self):
        """Открыть окно со списком услуг."""
        window = ServicesWindow(self.db_path, self)
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
        self.clients_table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.clients_table.setColumnCount(4)
        self.clients_table.setHorizontalHeaderLabels(
            ["ФИО", "Телефон", "День рождения", "Заметки"]
        )
        # Приоритеты растяжения: имя и заметки растягиваются, телефон и день рождения — по содержимому
        header = self.clients_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)        # ФИО
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # Телефон
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)  # День рождения
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)        # Заметки
        self.clients_table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

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
        self.appointments_table.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        self.appointments_table.setColumnCount(6)
        self.appointments_table.setHorizontalHeaderLabels(
            ["Клиент", "Дата", "Время", "Услуга", "Цена", "Статус"]
        )
        # Приоритеты растяжения: клиент и услуга растягиваются, дата/время/цена — по содержимому
        header = self.appointments_table.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)        # Клиент
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)  # Дата
        header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)  # Время
        header.setSectionResizeMode(3, QtWidgets.QHeaderView.Stretch)        # Услуга
        header.setSectionResizeMode(4, QtWidgets.QHeaderView.ResizeToContents)  # Цена
        header.setSectionResizeMode(5, QtWidgets.QHeaderView.ResizeToContents)  # Статус
        self.appointments_table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeToContents)

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

    # Apply a dark color palette for the whole application
    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(35, 35, 35))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ToolTipBase, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.ToolTipText, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(53, 53, 53))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(220, 220, 220))
    palette.setColor(QtGui.QPalette.BrightText, QtCore.Qt.red)
    palette.setColor(QtGui.QPalette.Link, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(42, 130, 218))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(255, 255, 255))
    app.setPalette(palette)

    # Global stylesheet tweaks for dark theme: tooltips, buttons, inputs, and tables
    app.setStyleSheet(
        "QToolTip{color:#ffffff;background-color:#2a82da;border:1px solid white;}"
        "QPushButton{background-color:#3c3f41;color:#e0e0e0;border:1px solid #555555;padding:6px 10px;border-radius:4px;}"
        "QPushButton:hover{background-color:#505354;}"
        "QPushButton:pressed{background-color:#2d2f30;}"
        "QPushButton:disabled{background-color:#2a2a2a;color:#7a7a7a;}"
        "QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox { background-color: #2b2b2b; color: #e0e0e0; border: 1px solid #444444; }")

    # Table-specific stylesheet appended separately for readability
    app.setStyleSheet(app.styleSheet() + 
        "QTableWidget, QTableView { background-color: #232323; alternate-background-color: #2b2b2b; gridline-color: #3a3a3a; color: #e6e6e6; }")
    app.setStyleSheet(app.styleSheet() + 
        "QHeaderView::section { background-color: #2f2f2f; color: #e6e6e6; padding: 4px; border: 1px solid #444444; }")
    app.setStyleSheet(app.styleSheet() + 
        "QTableWidget::item:selected, QTableView::item:selected { background-color: #3a78c7; color: #ffffff; }")

    db_path = Path(DB_NAME)
    # Подготовка/миграция старой базы и переименование таблиц при необходимости
    _prepare_and_migrate_db(db_path)
    init_db(db_path)

    window = MainWindow(db_path)
    window.show()

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()