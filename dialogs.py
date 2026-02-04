import customtkinter as ctk
from tkinter import messagebox
import tkinter as tk
import datetime
import calendar
from datetime import timedelta
from tkinter import filedialog

def time_str_to_minutes(time_str: str) -> int:
    try:
        h, m = map(int, time_str.split(":"))
        return h * 60 + m
    except Exception:
        return 0


def minutes_to_time_str(minutes: int) -> str:
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"


def get_appointment_duration(conn, appointment_id, default_service_id=None) -> int:
    """Продолжительность сеанса в минутах, основанная на одной услуге в поле ID_Услуги."""
    cur = conn.cursor()

    service_id = default_service_id
    if not service_id:
        # Пытаемся взять услугу из самой записи
        cur.execute('SELECT "ID_Услуги" FROM "Записи" WHERE ID = ?', (appointment_id,))
        row = cur.fetchone()
        service_id = row["ID_Услуги"] if row else None

    if service_id:
        cur.execute('SELECT "Длительность" FROM "Услуги" WHERE ID = ?', (service_id,))
        r = cur.fetchone()
        if r and r["Длительность"]:
            try:
                return int(r["Длительность"])
            except Exception:
                pass

    # Значение по умолчанию, если ничего не нашли
    return 30

def center_dialog(parent, dialog):
    dialog.update_idletasks()
    x = parent.winfo_x() + (parent.winfo_width() // 2) - (dialog.winfo_reqwidth() // 2)
    y = parent.winfo_y() + (parent.winfo_height() // 2) - (dialog.winfo_reqheight() // 2)
    dialog.geometry(f"+{x}+{y}")

def open_add_finance_dialog(app):
    """Диалог добавления финансовой операции"""
    dialog = ctk.CTkToplevel(app)
    dialog.title("Добавить финансовую операцию")
    dialog.geometry("400x350")
    center_dialog(app, dialog)
    dialog.transient(app)
    dialog.grab_set()
    dialog.grid_columnconfigure(1, weight=1)

    fields = {
        "Тип": ctk.CTkComboBox(dialog, values=["Доход", "Расход"]),
        "Сумма": ctk.CTkEntry(dialog, placeholder_text="Например, 1500.50"),
        "Дата": ctk.CTkEntry(dialog),
        "Описание": ctk.CTkEntry(dialog, placeholder_text="например: Консультация")
    }
    fields["Тип"].set("Доход")
    fields["Дата"].insert(0, datetime.date.today().strftime('%Y-%m-%d'))

    for i, (label, widget) in enumerate(fields.items()):
        ctk.CTkLabel(dialog, text=f"{label}:").grid(row=i, column=0, padx=10, pady=10, sticky="w")
        widget.grid(row=i, column=1, padx=10, pady=10, sticky="ew")

    def save_finance_record():
        tip = fields["Тип"].get()
        summa_str = fields["Сумма"].get().strip()
        data_str = fields["Дата"].get().strip()
        opisanie = fields["Описание"].get().strip()

        if not all([tip, summa_str, data_str, opisanie]):
            messagebox.showwarning("Предупреждение", "Заполните все поля.", parent=dialog)
            return
        try:
            summa = float(summa_str.replace(',', '.'))
            app.conn.execute(
                'INSERT INTO "Финансы" ("Тип", "Сумма", "Дата", "Описание") VALUES (?, ?, ?, ?)',
                (tip, summa, data_str, opisanie)
            )
            app.conn.commit()
            messagebox.showinfo("Успех", "Добавлено.", parent=dialog)
            dialog.destroy()
            app._display_entity_data("Финансы")
        except Exception as e:
            messagebox.showerror("Ошибка", str(e), parent=dialog)

    ctk.CTkButton(dialog, text="Сохранить", command=save_finance_record,
                  fg_color="green").grid(row=4, columnspan=2, pady=20, sticky="ew")

def open_add_service_dialog(app):
    dialog = ctk.CTkToplevel(app)
    dialog.title("Добавить: Услуга")
    dialog.geometry("500x320")
    center_dialog(app, dialog)
    dialog.transient(app)
    dialog.grab_set()
    dialog.grid_columnconfigure(1, weight=1)

    row = 0

    ctk.CTkLabel(dialog, text="Название:").grid(row=row, column=0, padx=10, pady=5, sticky="w")
    entry_name = ctk.CTkEntry(dialog)
    entry_name.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
    row += 1

    ctk.CTkLabel(dialog, text="Цена:").grid(row=row, column=0, padx=10, pady=5, sticky="w")
    entry_price = ctk.CTkEntry(dialog)
    entry_price.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
    row += 1

    ctk.CTkLabel(dialog, text="Длительность (мин):").grid(
        row=row, column=0, padx=10, pady=5, sticky="w")
    entry_duration = ctk.CTkEntry(dialog)
    entry_duration.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
    row += 1

    def save():
        name = entry_name.get().strip()
        price_str = entry_price.get().strip()
        duration_str = entry_duration.get().strip()

        if not all([name, price_str, duration_str]):
            messagebox.showwarning("Предупреждение",
                                   "Заполните все основные поля.",
                                   parent=dialog)
            return

        try:
            price = float(price_str.replace(',', '.'))
            duration = int(duration_str)
        except ValueError:
            messagebox.showerror("Ошибка",
                                 "Неверный формат цены или длительности.",
                                 parent=dialog)
            return

        if duration <= 0 or duration % 30 != 0:
            messagebox.showerror(
                "Ошибка",
                "Длительность должна быть положительной и кратной 30 минутам "
                "(например: 30, 60, 90, 120).",
                parent=dialog
            )
            return

        cursor = app.conn.cursor()
        cursor.execute(
            'INSERT INTO "Услуги" ("Название", "Цена", "Длительность") VALUES (?, ?, ?)',
            (name, price, duration)
        )

        app.conn.commit()
        messagebox.showinfo("Успех", "Услуга добавлена.", parent=dialog)
        dialog.destroy()
        app._display_entity_data("Услуги")

    ctk.CTkButton(dialog, text="Сохранить", command=save,
                  fg_color="green").grid(row=row, column=0, columnspan=2,
                                         padx=10, pady=10, sticky="ew")


def open_edit_service_dialog(app):
    if app.selected_card is None:
        messagebox.showwarning("Предупреждение", "Выберите услугу.")
        return

    service_id = app.selected_card.record_id
    cursor = app.conn.cursor()
    cursor.execute('SELECT * FROM "Услуги" WHERE ID = ?', (service_id,))
    service = cursor.fetchone()
    if not service:
        messagebox.showerror("Ошибка", "Услуга не найдена.", parent=app)
        return

    dialog = ctk.CTkToplevel(app)
    dialog.title(f"Изменить: {service['Название']}")
    dialog.geometry("500x320")
    center_dialog(app, dialog)
    dialog.transient(app)
    dialog.grab_set()
    dialog.grid_columnconfigure(1, weight=1)

    row = 0

    ctk.CTkLabel(dialog, text="Название:").grid(
        row=row, column=0, padx=10, pady=5, sticky="w")
    entry_name = ctk.CTkEntry(dialog)
    entry_name.insert(0, str(service['Название']))
    entry_name.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
    row += 1

    ctk.CTkLabel(dialog, text="Цена:").grid(
        row=row, column=0, padx=10, pady=5, sticky="w")
    entry_price = ctk.CTkEntry(dialog)
    entry_price.insert(0, str(service['Цена']))
    entry_price.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
    row += 1

    ctk.CTkLabel(dialog, text="Длительность (мин):").grid(
        row=row, column=0, padx=10, pady=5, sticky="w")
    entry_duration = ctk.CTkEntry(dialog)
    entry_duration.insert(0, str(service['Длительность']))
    entry_duration.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
    row += 1

    def save():
        name = entry_name.get().strip()
        price_str = entry_price.get().strip()
        duration_str = entry_duration.get().strip()

        if not all([name, price_str, duration_str]):
            messagebox.showwarning("Предупреждение",
                                   "Заполните все основные поля.",
                                   parent=dialog)
            return

        try:
            price = float(price_str.replace(',', '.'))
            duration = int(duration_str)
        except ValueError:
            messagebox.showerror("Ошибка",
                                 "Неверный формат цены или длительности.",
                                 parent=dialog)
            return

        cursor = app.conn.cursor()
        cursor.execute(
            'UPDATE "Услуги" SET "Название"=?, "Цена"=?, "Длительность"=? WHERE ID=?',
            (name, price, duration, service_id)
        )

        app.conn.commit()
        messagebox.showinfo("Успех", "Услуга обновлена.", parent=dialog)
        dialog.destroy()
        app._display_entity_data("Услуги")

    ctk.CTkButton(dialog, text="Сохранить", command=save,
                  fg_color="green").grid(row=row, column=0, columnspan=2,
                                         padx=10, pady=10, sticky="ew")

def open_add_appointment_dialog(app):
    """Диалог добавления записи (сеанса) с одной выбранной услугой."""
    dialog = ctk.CTkToplevel(app)
    dialog.title("Добавить: Запись")
    center_dialog(app, dialog)
    dialog.transient(app)
    dialog.grab_set()

    cursor = app.conn.cursor()
    cursor.execute('SELECT "ID", "ФИО" FROM "Клиенты"')
    clients = cursor.fetchall()
    name_to_id_cli = {c['ФИО']: c['ID'] for c in clients if c['ФИО']}

    cursor.execute('SELECT ID, "Название", "Длительность" FROM "Услуги" ORDER BY "Название"')
    all_services = cursor.fetchall()
    service_name_to_info = {
        s["Название"]: (s["ID"], int(s["Длительность"] or 30))
        for s in all_services
        if s["Название"]
    }

    cursor.execute('SELECT "ID", "Название" FROM "Эскизы" ORDER BY "Название"')
    sketches = cursor.fetchall()
    name_to_id_sketch = {s["Название"]: s["ID"] for s in sketches if s["Название"]}

    fields = {}
    row = 0

    ctk.CTkLabel(dialog, text="Дата").grid(row=row, column=0, padx=10, pady=5)
    entry_date = ctk.CTkEntry(dialog, state="disabled")
    entry_date.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
    entry_date.insert(0, str(datetime.date.today()))
    fields['Дата'] = entry_date
    btn_pick_date = ctk.CTkButton(dialog, text="Выбрать дату")
    btn_pick_date.grid(row=row, column=2, padx=6, pady=5)
    row += 1

    def open_date_picker(parent, target_entry):
        top = tk.Toplevel(parent)
        top.title("Выберите дату")
        top.transient(parent)
        top.grab_set()
        center_dialog(parent, top)

        cur_date = datetime.date.today().replace(day=1)
        header = tk.Frame(top)
        header.pack(fill="x", pady=4)
        month_label = tk.Label(header,
                               text=cur_date.strftime('%B %Y').capitalize(),
                               font=("Arial", 12, "bold"))
        month_label.pack(side="top", pady=2)
        cal_fr = tk.Frame(top)
        cal_fr.pack(padx=6, pady=6)

        def render(month_date):
            for w in cal_fr.winfo_children():
                w.destroy()
            month_label.config(text=month_date.strftime('%B %Y').capitalize())
            cal = calendar.monthcalendar(month_date.year, month_date.month)
            days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
            for c, d in enumerate(days):
                lbl = tk.Label(cal_fr, text=d, width=4, fg="#666666")
                lbl.grid(row=0, column=c)
            for r, week in enumerate(cal, start=1):
                for c, d in enumerate(week):
                    if d == 0:
                        tk.Label(cal_fr, text="", width=4).grid(row=r, column=c, padx=2, pady=2)
                        continue

                    def on_choose(day=d, md=month_date):
                        chosen = datetime.date(md.year, md.month, day)
                        target_entry.configure(state="normal")
                        target_entry.delete(0, tk.END)
                        target_entry.insert(0, str(chosen))
                        target_entry.configure(state="disabled")
                        top.destroy()

                    btn = tk.Button(cal_fr, text=str(d), width=4, command=on_choose)
                    if datetime.date.today() == datetime.date(
                        month_date.year, month_date.month, d
                    ):
                        btn.config(relief='solid')
                    btn.grid(row=r, column=c, padx=2, pady=2)

        def prev_month():
            nonlocal cur_date
            y = cur_date.year
            m = cur_date.month - 1
            if m < 1:
                m = 12
                y -= 1
            cur_date = cur_date.replace(year=y, month=m, day=1)
            render(cur_date)

        def next_month():
            nonlocal cur_date
            y = cur_date.year
            m = cur_date.month + 1
            if m > 12:
                m = 1
                y += 1
            cur_date = cur_date.replace(year=y, month=m, day=1)
            render(cur_date)

        nav = tk.Frame(top)
        nav.pack(fill="x")
        tk.Button(nav, text="◀", command=prev_month, width=3).pack(side="left", padx=6)
        tk.Button(nav, text="▶", command=next_month, width=3).pack(side="right", padx=6)

        render(cur_date)

    btn_pick_date.configure(command=lambda: open_date_picker(dialog, entry_date))
    ctk.CTkLabel(dialog, text="Клиент").grid(row=row, column=0, padx=10, pady=5)
    combo_cli = ctk.CTkComboBox(dialog, values=list(name_to_id_cli.keys()))
    combo_cli.grid(row=row, column=1, padx=10, pady=5)
    fields['ID_Клиента'] = combo_cli
    row += 1

    if name_to_id_sketch:
        ctk.CTkLabel(dialog, text="Эскиз (опционально)").grid(row=row, column=0, padx=10, pady=5, sticky="w")
        combo_sketch = ctk.CTkComboBox(dialog, values=list(name_to_id_sketch.keys()))
        combo_sketch.set("")
        combo_sketch.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
        fields["ID_Эскиза"] = combo_sketch
        row += 1

    ctk.CTkLabel(dialog, text="Услуга").grid(row=row, column=0, padx=10, pady=5, sticky="w")
    combo_service = ctk.CTkComboBox(dialog, values=list(service_name_to_info.keys()))
    combo_service.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
    row += 1


    ctk.CTkLabel(dialog, text="Время").grid(row=row, column=0, padx=10, pady=5)
    combo_time = ctk.CTkEntry(dialog, state="disabled")
    combo_time.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
    combo_time._slots = []
    btn_pick_time = ctk.CTkButton(dialog, text="Выбрать время")
    btn_pick_time.grid(row=row, column=2, padx=6, pady=5)
    fields['Время'] = combo_time
    row += 1

    def open_time_picker(parent, target_entry):
        top = tk.Toplevel(parent)
        top.title("Выберите время")
        top.transient(parent)
        top.grab_set()
        center_dialog(parent, top)

        list_frame = tk.Frame(top)
        list_frame.pack(fill="both", expand=True, padx=6, pady=6)
        scrollbar = tk.Scrollbar(list_frame)
        scrollbar.pack(side="right", fill="y")
        listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                             width=20, height=12)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.config(command=listbox.yview)

        slots = []
        fmt = "%H:%M"
        start = datetime.datetime.strptime("08:00", fmt)
        end = datetime.datetime.strptime("22:00", fmt)
        t_ = start
        while t_ <= end:
            slots.append(t_.strftime(fmt))
            t_ += timedelta(minutes=30)

        for s in slots:
            listbox.insert("end", s)

        def choose_time(_evt=None):
            sel = listbox.curselection()
            if not sel:
                return
            value = listbox.get(sel[0])
            target_entry.configure(state="normal")
            target_entry.delete(0, tk.END)
            target_entry.insert(0, value)
            target_entry.configure(state="disabled")
            top.destroy()

        listbox.bind("<Double-Button-1>", choose_time)
        btn_frame = tk.Frame(top)
        btn_frame.pack(fill="x", pady=6)
        tk.Button(btn_frame, text="OK", command=choose_time).pack(side="right", padx=6)

    btn_pick_time.configure(command=lambda: open_time_picker(dialog, combo_time))

    def save():
        date_val = fields['Дата'].get()
        cli_val = combo_cli.get()
        time_val = fields['Время'].get()

        sketch_id = None
        if "ID_Эскиза" in fields:
            sketch_name = fields["ID_Эскиза"].get().strip()
            if sketch_name:
                sketch_id = name_to_id_sketch.get(sketch_name)

        if not all([date_val, cli_val, time_val]):
            messagebox.showwarning("!",
                                   "Заполните все поля и выберите время.",
                                   parent=dialog)
            return

        service_name = combo_service.get().strip()
        if not service_name or service_name not in service_name_to_info:
            messagebox.showwarning("!", "Выберите услугу.", parent=dialog)
            return

        service_id, total_duration = service_name_to_info[service_name]

        # Разбор времени
        try:
            parts = time_val.split(":")
            if len(parts) != 2:
                raise ValueError()
            hour = int(parts[0])
            minute = int(parts[1])
            if hour < 0 or hour > 23 or minute < 0 or minute > 59:
                raise ValueError()
        except Exception:
            messagebox.showerror("Ошибка",
                                 "Неверный формат времени. Используйте HH:MM.",
                                 parent=dialog)
            return

        # Грубая проверка по времени работы салона
        if hour < 8 or hour > 22 or (hour == 22 and minute > 0):
            messagebox.showerror("Ошибка",
                                 "Время должно быть в интервале 08:00–22:00 (включительно).",
                                 parent=dialog)
            return

        time_val_norm = f"{hour:02d}:{minute:02d}"
        cli_id = name_to_id_cli.get(cli_val)

        if not cli_id:
            messagebox.showerror("Ошибка", "Выберите клиента.", parent=dialog)
            return

        # ===== создаём курсор =====
        cur = app.conn.cursor()
        start_minute = time_str_to_minutes(time_val_norm)
        end_minute = start_minute + total_duration
        # Время работы по умолчанию: 08:00–22:00
        if start_minute < time_str_to_minutes("08:00") or end_minute > time_str_to_minutes("22:00"):
            messagebox.showerror(
                "Ошибка",
                "Запись выходит за пределы рабочего времени (08:00–22:00).",
                parent=dialog,
            )
            return

        cur.execute(
            'SELECT ID, "Время", "ID_Услуги" FROM "Записи" '
            'WHERE "Дата"=?',
            (date_val,)
        )
        existing = cur.fetchall()

        for ex in existing:
            ex_start = time_str_to_minutes(ex["Время"])
            ex_dur = get_appointment_duration(
                app.conn,
                ex["ID"],
                ex["ID_Услуги"] if "ID_Услуги" in ex.keys() else None
            )
            ex_end = ex_start + ex_dur
            if not (end_minute <= ex_start or start_minute >= ex_end):
                messagebox.showerror(
                    "Ошибка",
                    f"На это время уже есть запись: {ex['Время']}–{minutes_to_time_str(ex_end)}.",
                    parent=dialog,
                )
                return

        cur.execute(
            'INSERT INTO "Записи" ("Дата","Время","ID_Клиента","ID_Услуги","ID_Эскиза") '
            'VALUES (?,?,?,?,?)',
            (date_val, time_val_norm, cli_id, service_id, sketch_id)
        )

        app.conn.commit()
        messagebox.showinfo(
            "Успех",
            "Запись создана.",
            parent=dialog,
        )

        dialog.destroy()
        app._display_entity_data(app.current_entity)

    ctk.CTkButton(dialog, text="Сохранить", command=save).grid(
        row=row, columnspan=2, pady=10
    )


def open_edit_record_dialog(app):
    """Диалог редактирования записи"""
    if app.selected_card is None:
        messagebox.showwarning("Предупреждение", "Выберите карточку.")
        return
    if app.current_entity in ["Расписание", "Финансы"]:
        messagebox.showwarning("Предупреждение", "Редактирование здесь не поддерживается.")
        return
    if app.current_entity == "Услуги":
        open_edit_service_dialog(app)
        return

    record_id = app.selected_card.record_id
    entity_name = app.current_entity
    columns = app._get_table_columns(entity_name)
    data_columns = [(name, t) for name, t in columns if name.upper() != 'ID']
    # сущность "Сотрудники" в проекте тату-мастера не используется

    cursor = app.conn.cursor()
    cursor.execute(f'SELECT * FROM "{entity_name}" WHERE ID=?', (record_id,))
    record = cursor.fetchone()
    if not record:
        messagebox.showerror("Ошибка", "Запись не найдена.", parent=app)
        return

    dialog = ctk.CTkToplevel(app)
    dialog.title(f"Изменить #{record_id}")
    center_dialog(app, dialog)
    dialog.transient(app)
    dialog.grab_set()

    if entity_name == "Записи":
        cursor = app.conn.cursor()
        cursor.execute('SELECT "ID", "ФИО" FROM "Клиенты"')
        clients = cursor.fetchall()
        name_to_id_cli = {c['ФИО']: c['ID'] for c in clients if c['ФИО']}

        row = 0

        ctk.CTkLabel(dialog, text="Дата").grid(row=row, column=0, padx=10, pady=5)
        entry_date = ctk.CTkEntry(dialog, state="disabled")
        entry_date.grid(row=row, column=1, padx=10, pady=5, sticky="ew")
        entry_date.insert(0, str(record['Дата']))
        row += 1

        def open_date_picker(parent, target_entry):
            top = tk.Toplevel(parent)
            top.title("Выберите дату")
            top.transient(parent)
            top.grab_set()
            center_dialog(parent, top)

            cur_date = datetime.date.today().replace(day=1)
            header = tk.Frame(top)
            header.pack(fill="x", pady=4)
            month_label = tk.Label(header,
                                   text=cur_date.strftime('%B %Y').capitalize(),
                                   font=("Arial", 12, "bold"))
            month_label.pack(side="top", pady=2)
            cal_fr = tk.Frame(top)
            cal_fr.pack(padx=6, pady=6)

            def render(month_date):
                for w in cal_fr.winfo_children():
                    w.destroy()
                month_label.config(text=month_date.strftime('%B %Y').capitalize())
                cal = calendar.monthcalendar(month_date.year, month_date.month)
                days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
                for c, d in enumerate(days):
                    tk.Label(cal_fr, text=d, width=4, fg="#666666").grid(row=0, column=c)
                for r, week in enumerate(cal, start=1):
                    for c, d in enumerate(week):
                        if d == 0:
                            tk.Label(cal_fr, text="", width=4).grid(row=r, column=c, padx=2, pady=2)
                            continue

                        def on_choose(day=d, md=month_date):
                            chosen = datetime.date(md.year, md.month, day)
                            target_entry.configure(state="normal")
                            target_entry.delete(0, tk.END)
                            target_entry.insert(0, str(chosen))
                            target_entry.configure(state="disabled")
                            top.destroy()

                        btn = tk.Button(cal_fr, text=str(d), width=4, command=on_choose)
                        if datetime.date.today() == datetime.date(
                                month_date.year, month_date.month, d
                        ):
                            btn.config(relief='solid')
                        btn.grid(row=r, column=c, padx=2, pady=2)

            def prev_month():
                nonlocal cur_date
                y = cur_date.year
                m = cur_date.month - 1
                if m < 1:
                    m = 12
                    y -= 1
                cur_date = cur_date.replace(year=y, month=m, day=1)
                render(cur_date)

            def next_month():
                nonlocal cur_date
                y = cur_date.year
                m = cur_date.month + 1
                if m > 12:
                    m = 1
                    y += 1
                cur_date = cur_date.replace(year=y, month=m, day=1)
                render(cur_date)

            nav = tk.Frame(top)
            nav.pack(fill="x")
            tk.Button(nav, text="◀", command=prev_month, width=3).pack(side="left", padx=6)
            tk.Button(nav, text="▶", command=next_month, width=3).pack(side="right", padx=6)
            render(cur_date)

        btn_pick_date = ctk.CTkButton(dialog, text="Выбрать дату",
                                      command=lambda: open_date_picker(dialog, entry_date))
        btn_pick_date.grid(row=row - 1, column=2, padx=6, pady=5)

        ctk.CTkLabel(dialog, text="Клиент").grid(row=row, column=0, padx=10, pady=5)
        combo_cli = ctk.CTkComboBox(dialog, values=list(name_to_id_cli.keys()))
        combo_cli.grid(row=row, column=1, padx=10, pady=5)
        try:
            current_cli = next(
                k for k, v in name_to_id_cli.items() if v == record['ID_Клиента']
            )
            combo_cli.set(current_cli)
        except StopIteration:
            pass
        row += 1

        service_name = None
        if record["ID_Услуги"]:
            cursor.execute(
                'SELECT "Название" FROM "Услуги" WHERE ID = ?',
                (record["ID_Услуги"],)
            )
            r = cursor.fetchone()
            if r:
                service_name = r["Название"]

        if service_name:
            ctk.CTkLabel(dialog, text="Услуга:").grid(row=row, column=0, padx=10, pady=5, sticky="w")
            ctk.CTkLabel(
                dialog,
                text=service_name,
                wraplength=260,
                justify="left",
            ).grid(row=row, column=1, columnspan=2, padx=10, pady=5, sticky="w")
            row += 1

        ctk.CTkLabel(dialog, text="Время").grid(row=row, column=0, padx=10, pady=5)
        combo_time = ctk.CTkEntry(dialog, state='disabled')
        combo_time.grid(row=row, column=1, padx=10, pady=5, sticky='ew')
        combo_time._slots = []
        btn_pick_time = ctk.CTkButton(dialog, text='Выбрать время')
        btn_pick_time.grid(row=row, column=2, padx=6, pady=5)

        combo_time.configure(state='normal')
        combo_time.delete(0, tk.END)
        combo_time.insert(0, record['Время'])
        combo_time.configure(state='disabled')
        row += 1

        entry_date.bind('<FocusOut>', lambda e: update_time_options())
        def update_time_options(*_):
            combo_time._slots = []

        def open_time_picker(parent, target_entry):
            top = tk.Toplevel(parent)
            top.title('Выберите время')
            top.transient(parent)
            top.grab_set()
            center_dialog(parent, top)

            list_frame = tk.Frame(top)
            list_frame.pack(fill='both', expand=True, padx=6, pady=6)
            scrollbar = tk.Scrollbar(list_frame)
            scrollbar.pack(side='right', fill='y')
            listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set,
                                 width=20, height=12)
            listbox.pack(side='left', fill='both', expand=True)
            scrollbar.config(command=listbox.yview)

            slots = []
            fmt = '%H:%M'
            start = datetime.datetime.strptime('08:00', fmt)
            end = datetime.datetime.strptime('22:00', fmt)
            t_ = start
            while t_ <= end:
                slots.append(t_.strftime(fmt))
                t_ += timedelta(minutes=30)

            for s in slots:
                listbox.insert('end', s)

            def choose_time(_evt=None):
                sel = listbox.curselection()
                if not sel:
                    return
                value = listbox.get(sel[0])
                target_entry.configure(state='normal')
                target_entry.delete(0, tk.END)
                target_entry.insert(0, value)
                target_entry.configure(state='disabled')
                top.destroy()

            listbox.bind('<Double-Button-1>', choose_time)
            btn_frame = tk.Frame(top)
            btn_frame.pack(fill='x', pady=6)
            tk.Button(btn_frame, text='OK', command=choose_time).pack(side='right', padx=6)

        btn_pick_time.configure(command=lambda: open_time_picker(dialog, combo_time))

        def save_record():
            date_val = entry_date.get()
            cli_val = combo_cli.get()
            time_val = combo_time.get()

            if not all([date_val, cli_val, time_val]):
                messagebox.showwarning('!',
                                       'Заполните все поля и выберите время, согласно смене сотрудника.')
                return

            try:
                parts = time_val.split(':')
                if len(parts) != 2:
                    raise ValueError()
                hour = int(parts[0])
                minute = int(parts[1])
            except Exception:
                messagebox.showerror('Ошибка',
                                     'Неверный формат времени. Используйте HH:MM.',
                                     parent=dialog)
                return

            if hour < 8 or hour > 22 or (hour == 22 and minute > 0):
                messagebox.showerror('Ошибка',
                                     'Время должно быть в интервале 08:00–22:00 (включительно).',
                                     parent=dialog)
                return

            cli_id = name_to_id_cli.get(cli_val)
            if not cli_id:
                messagebox.showerror("Ошибка", "Выберите клиента.", parent=dialog)
                return

            total_duration = get_appointment_duration(
                app.conn,
                record_id,
                record["ID_Услуги"] if "ID_Услуги" in record.keys() else None
            )
            start_minute = time_str_to_minutes(time_val)
            end_minute = start_minute + total_duration

            cursor.execute(
                'SELECT ID, "Время", "ID_Услуги" FROM "Записи" '
                'WHERE "Дата"=? AND ID<>?',
                (date_val, record_id)
            )
            existing = cursor.fetchall()
            for ex in existing:
                ex_start = time_str_to_minutes(ex["Время"])
                ex_dur = get_appointment_duration(
                    app.conn,
                    ex["ID"],
                    ex["ID_Услуги"] if "ID_Услуги" in ex.keys() else None
                )
                ex_end = ex_start + ex_dur
                if not (end_minute <= ex_start or start_minute >= ex_end):
                    messagebox.showerror(
                        "Ошибка",
                        f"На это время уже есть запись: {ex['Время']}–{minutes_to_time_str(ex_end)}.",
                        parent=dialog,
                    )
                    return

            cursor.execute(
                'UPDATE "Записи" SET "Дата"=?, "Время"=?, "ID_Клиента"=? WHERE ID=?',
                (date_val, time_val, cli_id, record_id)
            )
            app.conn.commit()
            dialog.destroy()
            app._display_entity_data(entity_name)

        ctk.CTkButton(dialog, text='Сохранить', command=save_record).grid(
            row=row, columnspan=3, pady=10)
        return

    entries = {}
    for i, (name, _) in enumerate(data_columns):
        ctk.CTkLabel(dialog, text=name).grid(row=i, column=0, padx=10, pady=5)
        e = ctk.CTkEntry(dialog)
        e.insert(0, str(record[name]))
        e.grid(row=i, column=1, padx=10, pady=5)
        entries[name] = e

    def save():
        updates = []
        vals = []
        for name, _ in data_columns:
            updates.append(f'"{name}" = ?')
            vals.append(entries[name].get())
        vals.append(record_id)
        app.conn.execute(
            f'UPDATE "{entity_name}" SET {", ".join(updates)} WHERE ID=?',
            vals
        )
        app.conn.commit()
        dialog.destroy()
        app._display_entity_data(entity_name)

    ctk.CTkButton(dialog, text="Сохранить", command=save).grid(
        row=len(data_columns), columnspan=2, pady=10
    )


# ========================= УНИВЕРСАЛЬНОЕ ДОБАВЛЕНИЕ =================

def open_add_record_dialog(app):
    """Универсальный диалог добавления записи"""
    if app.current_entity == "Финансы":
        open_add_finance_dialog(app)
        return
    if app.current_entity == "Записи":
        open_add_appointment_dialog(app)
        return
    if app.current_entity == "Услуги":
        open_add_service_dialog(app)
        return
    if app.current_entity == "Эскизы":
        open_add_sketch_dialog(app)
        return

    dialog = ctk.CTkToplevel(app)
    dialog.title(f"Добавить: {app.current_entity}")
    center_dialog(app, dialog)
    dialog.transient(app)
    dialog.grab_set()

    columns = [(c[0], c[1]) for c in app._get_table_columns(app.current_entity) if c[0] != 'ID']
    entries = []
    for i, (name, _) in enumerate(columns):
        ctk.CTkLabel(dialog, text=name).grid(row=i, column=0, padx=10, pady=5)
        e = ctk.CTkEntry(dialog)
        e.grid(row=i, column=1, padx=10, pady=5)
        entries.append(e)

    def save():
        vals = [e.get() for e in entries]
        cols = ", ".join([f'"{c[0]}"' for c in columns])
        qs = ", ".join(["?"] * len(columns))
        app.conn.execute(
            f'INSERT INTO "{app.current_entity}" ({cols}) VALUES ({qs})',
            vals
        )
        app.conn.commit()
        dialog.destroy()
        app._display_entity_data(app.current_entity)

    ctk.CTkButton(dialog, text="Сохранить", command=save).grid(
        row=len(columns), columnspan=2, pady=10
    )
def open_finance_date_picker(app, target_entry):
    """Открыть календарь и записать выбранную дату в target_entry (формат YYYY-MM-DD)."""
    top = tk.Toplevel(app)
    top.title("Выберите дату")
    top.transient(app)
    top.grab_set()
    top.geometry("300x320")
    center_dialog(app, top)

    cur_date = datetime.date.today().replace(day=1)
    header = tk.Frame(top)
    header.pack(fill="x", pady=4)
    month_label = tk.Label(header, text=cur_date.strftime('%B %Y').capitalize(), font=("Arial", 12, "bold"))
    month_label.pack(side="top", pady=2)
    cal_fr = tk.Frame(top)
    cal_fr.pack(padx=6, pady=6)

    def render(month_date):
        for w in cal_fr.winfo_children():
            w.destroy()
        month_label.config(text=month_date.strftime('%B %Y').capitalize())
        cal = calendar.monthcalendar(month_date.year, month_date.month)
        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        for c, d in enumerate(days):
            tk.Label(cal_fr, text=d, width=4, fg="#666666").grid(row=0, column=c)
        for r, week in enumerate(cal, start=1):
            for c, d in enumerate(week):
                if d == 0:
                    tk.Label(cal_fr, text="", width=4).grid(row=r, column=c, padx=2, pady=2)
                    continue

                def on_choose(day=d, md=month_date):
                    chosen = datetime.date(md.year, md.month, day)
                    target_entry.delete(0, tk.END)
                    target_entry.insert(0, str(chosen))
                    top.destroy()

                btn = tk.Button(cal_fr, text=str(d), width=4, command=on_choose)
                if datetime.date.today() == datetime.date(month_date.year, month_date.month, d):
                    btn.config(relief='solid')
                btn.grid(row=r, column=c, padx=2, pady=2)

    def prev_month():
        nonlocal cur_date
        y, m = (cur_date.year, cur_date.month - 1) if cur_date.month > 1 else (cur_date.year - 1, 12)
        cur_date = cur_date.replace(year=y, month=m)
        render(cur_date)

    def next_month():
        nonlocal cur_date
        y, m = (cur_date.year, cur_date.month + 1) if cur_date.month < 12 else (cur_date.year + 1, 1)
        cur_date = cur_date.replace(year=y, month=m)
        render(cur_date)

    nav = tk.Frame(top)
    nav.pack(fill="x", pady=5)
    tk.Button(nav, text="◀", command=prev_month, width=3).pack(side="left", padx=10)
    tk.Button(nav, text="▶", command=next_month, width=3).pack(side="right", padx=10)
    render(cur_date)


def open_schedule_date_picker(app):
    top = tk.Toplevel(app)
    top.title("Выберите дату")
    top.transient(app)
    top.grab_set()
    top.geometry("300x320")

    # Центрируем окно
    center_dialog(app, top)

    # Текущая дата для календаря
    cur_date = app.schedule_date.replace(day=1)

    header = tk.Frame(top)
    header.pack(fill="x", pady=4)

    month_label = tk.Label(header, text=cur_date.strftime('%B %Y').capitalize(), font=("Arial", 12, "bold"))
    month_label.pack(side="top", pady=2)

    cal_fr = tk.Frame(top)
    cal_fr.pack(padx=6, pady=6)

    def render(month_date):
        for w in cal_fr.winfo_children():
            w.destroy()
        month_label.config(text=month_date.strftime('%B %Y').capitalize())
        cal = calendar.monthcalendar(month_date.year, month_date.month)

        days = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
        for c, d in enumerate(days):
            tk.Label(cal_fr, text=d, width=4, fg="#666666").grid(row=0, column=c)

        for r, week in enumerate(cal, start=1):
            for c, d in enumerate(week):
                if d == 0:
                    tk.Label(cal_fr, text="", width=4).grid(row=r, column=c, padx=2, pady=2)
                    continue

                def on_choose(day=d, md=month_date):
                    chosen = datetime.date(md.year, md.month, day)
                    app.schedule_date = chosen
                    app._display_entity_data("Расписание")
                    top.destroy()

                btn = tk.Button(cal_fr, text=str(d), width=4, command=on_choose)
                if datetime.date.today() == datetime.date(month_date.year, month_date.month, d):
                    btn.config(relief='solid')
                btn.grid(row=r, column=c, padx=2, pady=2)

    def prev_month():
        nonlocal cur_date
        y, m = (cur_date.year, cur_date.month - 1) if cur_date.month > 1 else (cur_date.year - 1, 12)
        cur_date = cur_date.replace(year=y, month=m)
        render(cur_date)

    def next_month():
        nonlocal cur_date
        y, m = (cur_date.year, cur_date.month + 1) if cur_date.month < 12 else (cur_date.year + 1, 1)
        cur_date = cur_date.replace(year=y, month=m)
        render(cur_date)

    nav = tk.Frame(top)
    nav.pack(fill="x", pady=5)
    tk.Button(nav, text="◀", command=prev_month, width=3).pack(side="left", padx=10)
    tk.Button(nav, text="▶", command=next_month, width=3).pack(side="right", padx=10)

    render(cur_date)


def open_add_sketch_dialog(app):
    dialog = ctk.CTkToplevel(app)
    dialog.title("Добавить: Эскиз")
    dialog.geometry("520x360")
    center_dialog(app, dialog)
    dialog.transient(app)
    dialog.grab_set()
    dialog.grid_columnconfigure(1, weight=1)

    row = 0

    ctk.CTkLabel(dialog, text="Название:").grid(row=row, column=0, padx=10, pady=8, sticky="w")
    entry_name = ctk.CTkEntry(dialog)
    entry_name.grid(row=row, column=1, padx=10, pady=8, sticky="ew")
    row += 1

    ctk.CTkLabel(dialog, text="Стиль:").grid(row=row, column=0, padx=10, pady=8, sticky="w")
    entry_style = ctk.CTkEntry(dialog, placeholder_text="Напр: Fine Line, Old School, Realism")
    entry_style.grid(row=row, column=1, padx=10, pady=8, sticky="ew")
    row += 1

    ctk.CTkLabel(dialog, text="Описание:").grid(row=row, column=0, padx=10, pady=8, sticky="nw")
    txt_desc = tk.Text(dialog, height=6, wrap="word")
    txt_desc.grid(row=row, column=1, padx=10, pady=8, sticky="ew")
    row += 1

    ctk.CTkLabel(dialog, text="Файл (опц.):").grid(row=row, column=0, padx=10, pady=8, sticky="w")
    file_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    file_frame.grid(row=row, column=1, padx=10, pady=8, sticky="ew")
    file_frame.grid_columnconfigure(0, weight=1)
    entry_file = ctk.CTkEntry(file_frame, placeholder_text="Путь к картинке/референсу")
    entry_file.grid(row=0, column=0, sticky="ew")

    def pick_file():
        path = filedialog.askopenfilename(
            parent=dialog,
            title="Выберите файл эскиза",
            filetypes=[
                ("Изображения", "*.png;*.jpg;*.jpeg;*.webp;*.gif"),
                ("Все файлы", "*.*"),
            ],
        )
        if path:
            entry_file.delete(0, tk.END)
            entry_file.insert(0, path)

    ctk.CTkButton(file_frame, text="Выбрать...", width=110, command=pick_file).grid(
        row=0, column=1, padx=(8, 0)
    )
    row += 1

    def save():
        name = entry_name.get().strip()
        style = entry_style.get().strip()
        desc = txt_desc.get("1.0", "end").strip()
        file_path = entry_file.get().strip()

        if not name:
            messagebox.showwarning("Предупреждение", "Укажите название эскиза.", parent=dialog)
            return

        cur = app.conn.cursor()
        cur.execute(
            'INSERT INTO "Эскизы" ("Название","Стиль","Описание","Файл") VALUES (?,?,?,?)',
            (name, style, desc, file_path),
        )
        app.conn.commit()
        messagebox.showinfo("Успех", "Эскиз добавлен.", parent=dialog)
        dialog.destroy()
        app._display_entity_data("Эскизы")

    ctk.CTkButton(dialog, text="Сохранить", fg_color="green", command=save).grid(
        row=row, column=0, columnspan=2, padx=10, pady=(12, 10), sticky="ew"
    )