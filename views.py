import customtkinter as ctk
import datetime
import calendar
import tkinter as tk
from tkinter import messagebox
import locale
import os
from dialogs import time_str_to_minutes, minutes_to_time_str, get_appointment_duration

try:
    from PIL import Image
except Exception:  # Pillow может отсутствовать в окружении
    Image = None

def get_finance_data_by_range(conn, start_date, end_date):
    """Запрос к БД: прибыль и список операций за период [start_date, end_date]."""
    cursor = conn.cursor()
    cursor.execute(
        """SELECT SUM(Сумма) FROM "Финансы"
           WHERE Тип = 'Доход' AND Дата BETWEEN ? AND ?""",
        (str(start_date), str(end_date)),
    )
    total_income = cursor.fetchone()[0] or 0.0

    cursor.execute(
        """SELECT SUM(Сумма) FROM "Финансы"
           WHERE Тип = 'Расход' AND Дата BETWEEN ? AND ?""",
        (str(start_date), str(end_date)),
    )
    total_expense = cursor.fetchone()[0] or 0.0

    cursor.execute(
        """SELECT * FROM "Финансы"
           WHERE Дата BETWEEN ? AND ?
           ORDER BY Дата DESC, ID DESC""",
        (str(start_date), str(end_date)),
    )
    transactions = cursor.fetchall()

    return {
        "profit": total_income - total_expense,
        "transactions": transactions,
    }


def display_finance_report_view(app):
    from dialogs import open_finance_date_picker

    app.top_controls.grid_columnconfigure((0, 1, 2, 3, 4, 5), weight=0)
    app.top_controls.grid_columnconfigure(1, weight=1)
    app.top_controls.grid_columnconfigure(3, weight=1)

    ctk.CTkLabel(app.top_controls, text="Начальная дата:").grid(row=0, column=0, padx=(10, 5), pady=10, sticky="w")
    entry_start = ctk.CTkEntry(app.top_controls, width=120)
    entry_start.insert(0, app.finance_date_start.strftime("%Y-%m-%d"))
    entry_start.grid(row=0, column=1, padx=5, pady=10, sticky="ew")
    ctk.CTkButton(
        app.top_controls,
        text="Выбрать дату",
        width=110,
        command=lambda: open_finance_date_picker(app, entry_start),
    ).grid(row=0, column=2, padx=5, pady=10, sticky="w")

    ctk.CTkLabel(app.top_controls, text="Конечная дата:").grid(row=0, column=3, padx=(15, 5), pady=10, sticky="w")
    entry_end = ctk.CTkEntry(app.top_controls, width=120)
    entry_end.insert(0, app.finance_date_end.strftime("%Y-%m-%d"))
    entry_end.grid(row=0, column=4, padx=5, pady=10, sticky="ew")
    ctk.CTkButton(
        app.top_controls,
        text="Выбрать дату",
        width=110,
        command=lambda: open_finance_date_picker(app, entry_end),
    ).grid(row=0, column=5, padx=5, pady=10, sticky="w")

    def apply_range():
        try:
            start_str = entry_start.get().strip()
            end_str = entry_end.get().strip()
            app.finance_date_start = datetime.datetime.strptime(start_str, "%Y-%m-%d").date()
            app.finance_date_end = datetime.datetime.strptime(end_str, "%Y-%m-%d").date()
            if app.finance_date_start > app.finance_date_end:
                messagebox.showwarning("Предупреждение", "Начальная дата не может быть позже конечной.", parent=app)
                return
            app._display_entity_data("Финансы")
        except ValueError:
            messagebox.showwarning("Предупреждение", "Введите даты в формате ГГГГ-ММ-ДД.", parent=app)

    ctk.CTkButton(
        app.top_controls,
        text="Показать прибыль",
        fg_color="#1F6AA5",
        command=apply_range,
    ).grid(row=0, column=6, padx=15, pady=10, sticky="ew")

    finance_data = get_finance_data_by_range(
        app.conn, app.finance_date_start, app.finance_date_end
    )

    for widget in app.scrollable_cards_frame.winfo_children():
        widget.destroy()

    app.scrollable_cards_frame.configure(
        label_text=f"Финансы ({len(finance_data['transactions'])} операций)"
    )

    summary_frame = ctk.CTkFrame(app.scrollable_cards_frame, fg_color="transparent")
    summary_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
    summary_frame.grid_columnconfigure(0, weight=1)

    period_text = f"{app.finance_date_start.strftime('%d.%m.%Y')} — {app.finance_date_end.strftime('%d.%m.%Y')}"
    profit_color = "#32CD32" if finance_data["profit"] >= 0 else "#FF4500"
    profit_frame = ctk.CTkFrame(summary_frame, border_width=2, border_color=profit_color)
    profit_frame.grid(row=0, column=0, padx=5, sticky="ew")
    profit_frame.grid_columnconfigure(0, weight=1)
    ctk.CTkLabel(
        profit_frame,
        text=f"Прибыль за период {period_text}",
        text_color="#A9A9A9",
    ).pack(pady=(8, 0))
    ctk.CTkLabel(
        profit_frame,
        text=f"{finance_data['profit']:,.2f} руб.",
        font=("Arial", 22, "bold"),
        text_color=profit_color,
    ).pack(pady=(0, 8))

    for i, trans in enumerate(finance_data["transactions"]):
        fr = ctk.CTkFrame(app.scrollable_cards_frame)
        fr.grid(row=i + 2, column=0, sticky="ew", padx=10, pady=2)
        ctk.CTkLabel(fr, text=trans["Дата"]).pack(side="left", padx=10)
        color = "#32CD32" if trans["Тип"] == "Доход" else "#FF4500"
        ctk.CTkLabel(
            fr,
            text=f"{trans['Сумма']:,.2f}",
            text_color=color,
        ).pack(side="left", padx=10)
        ctk.CTkLabel(fr, text=trans["Описание"]).pack(side="left", padx=10)


def get_appointment_data(conn, date):

    cur = conn.cursor()

    cur.execute(
        """
        SELECT 
            z.ID,
            z.Время,
            z.ID_Услуги,
            c.ФИО as Клиент,
            u.Название as Услуга
        FROM "Записи" z
        LEFT JOIN "Клиенты" c ON z.ID_Клиента = c.ID
        LEFT JOIN "Услуги" u ON z.ID_Услуги = u.ID
        WHERE z.Дата = ?
        ORDER BY z.Время
    """,
        (str(date),),
    )

    base_records = cur.fetchall()
    appointments = []

    for r in base_records:
        rid = r["ID"]

        service_names = []
        if r["Услуга"]:
            service_names = [r["Услуга"]]

        total_duration = get_appointment_duration(conn, rid, r["ID_Услуги"])
        start_min = time_str_to_minutes(r["Время"])
        end_min = start_min + total_duration

        details = (
            f"Кл: {r['Клиент'] or 'Неизвестно'}, "
        )
        if service_names:
            details += "Усл: " + " + ".join(service_names)
        else:
            details += "Усл: не указаны"

        appointments.append(
            {
                "id": rid,
                "time": r["Время"],
                "start_min": start_min,
                "end_min": end_min,
                "details": details,
            }
        )

    return appointments


def display_schedule_view(app, appointments, date):
    from dialogs import open_schedule_date_picker

    try:
        if app.tk.call("tk", "windowingsystem") == "win32":
            locale.setlocale(locale.LC_TIME, "Russian")
        else:
            locale.setlocale(locale.LC_TIME, "ru_RU.UTF-8")
    except Exception:
        pass
    for w in app.top_controls.winfo_children():
        w.destroy()

    app.top_controls.grid_columnconfigure(0, weight=0)
    app.top_controls.grid_columnconfigure(1, weight=1)
    app.top_controls.grid_columnconfigure(2, weight=0)

    btn_pick = ctk.CTkButton(
        app.top_controls,
        text="Выбрать дату",
        fg_color="#1F6AA5",
        hover_color="#144870",
        width=120,
        command=lambda: open_schedule_date_picker(app),
    )
    btn_pick.grid(row=0, column=0, padx=10, pady=10, sticky="w")

    date_str = date.strftime("%d %B %Y")
    lbl_date = ctk.CTkLabel(
        app.top_controls,
        text=date_str,
        font=ctk.CTkFont(size=20),
    )
    lbl_date.grid(row=0, column=1)

    for w in app.scrollable_cards_frame.winfo_children():
        w.destroy()

    header_text = (
        f"Расписание на {date.strftime('%d %B %Y').lower()} "
        f"({len(appointments)} записей)"
    )
    app.scrollable_cards_frame.configure(label_text=header_text)

    slot_map = {}

    for ap in appointments:
        t = ap["start_min"]
        first = True
        while t < ap["end_min"]:
            time_key = minutes_to_time_str(t)
            slot_map[time_key] = {"app": ap, "head": first}
            first = False
            t += 30

    timeline_frame = ctk.CTkFrame(app.scrollable_cards_frame, fg_color="transparent")
    timeline_frame.pack(fill="both", expand=True, padx=5, pady=5)
    timeline_frame.columnconfigure(1, weight=1)

    row_idx = 0
    for hour in range(7, 22):
        for minute in (0, 30):
            time_key = f"{hour:02d}:{minute:02d}"
            if minute == 0:
                ctk.CTkLabel(
                    timeline_frame,
                    text=time_key,
                    font=ctk.CTkFont(size=13),
                    width=50,
                ).grid(row=row_idx, column=0, padx=(0, 10), pady=2, sticky="n")
            else:
                ctk.CTkLabel(timeline_frame, text="", width=50).grid(
                    row=row_idx, column=0
                )

            slot_info = slot_map.get(time_key)

            if slot_info:
                ap = slot_info["app"]
                is_head = slot_info["head"]

                if is_head:
                    slot_color = "#3A8FCD"
                    text_info = ap["details"]
                    fg_text = "white"
                    show_button = True
                else:
                    slot_color = "#444444"
                    text_info = "(продолжение записи)"
                    fg_text = "#DDDDDD"
                    show_button = False
            else:
                slot_color = "#2B2B2B"
                text_info = ""
                fg_text = "gray"
                show_button = False

            slot_bar = ctk.CTkFrame(
                timeline_frame,
                height=35,
                fg_color=slot_color,
                corner_radius=6,
                border_width=1,
                border_color="#333333",
            )
            slot_bar.grid(row=row_idx, column=1, sticky="ew", padx=2, pady=2)
            slot_bar.pack_propagate(False)

            if text_info:
                ctk.CTkLabel(
                    slot_bar,
                    text=text_info,
                    font=ctk.CTkFont(size=12),
                    text_color=fg_text,
                ).pack(side="left", padx=15)

            if show_button:
                def _comp(rid=ap["id"]):
                    complete_appointment(app, rid)

                ctk.CTkButton(
                    slot_bar,
                    text="Завершить",
                    width=80,
                    height=22,
                    fg_color="#2ECC71",
                    font=ctk.CTkFont(size=10),
                    command=_comp,
                ).pack(side="right", padx=5)

            row_idx += 1


def complete_appointment(app, record_id):
    """Отметить запись как завершённую: записать доход в Финансы и удалить её из Расписания."""
    import datetime

    cur = app.conn.cursor()

    cur.execute('SELECT * FROM "Записи" WHERE ID = ?', (record_id,))
    rec = cur.fetchone()
    if not rec:
        messagebox.showerror("Ошибка", "Запись не найдена.")
        return

    service_id = rec["ID_Услуги"]
    date_str = rec["Дата"] or datetime.date.today().strftime("%Y-%m-%d")

    prices = []
    names = []

    if service_id:
        cur.execute(
            'SELECT "Цена", "Название" FROM "Услуги" WHERE ID = ?',
            (service_id,),
        )
        s = cur.fetchone()
        if s:
            try:
                prices.append(float(s["Цена"]) if s["Цена"] is not None else 0.0)
            except Exception:
                prices.append(0.0)
            names.append(s["Название"] or "")

    total_amount = sum(prices)
    service_name = " + ".join([n for n in names if n]) if names else ""

    cur.execute(
        'SELECT "ФИО" FROM "Клиенты" WHERE ID = ?',
        (rec["ID_Клиента"],),
    )
    client_row = cur.fetchone()
    client_name = client_row["ФИО"] if client_row else ""

    tipo = "Доход"
    description = f"Прибыль по записи #{record_id}: {service_name} ({client_name})"

    app.conn.execute(
        'INSERT INTO "Финансы" ("Тип", "Сумма", "Дата", "Описание") '
        "VALUES (?, ?, ?, ?)",
        (tipo, total_amount, date_str, description),
    )

    # После фиксации дохода удаляем саму запись из таблицы "Записи"
    app.conn.execute('DELETE FROM "Записи" WHERE ID = ?', (record_id,))
    app.conn.commit()

    try:
        y, m, d = map(int, date_str.split("-"))
        app.finance_date_start = datetime.date(y, m, 1)
        _, last_day = calendar.monthrange(y, m)
        app.finance_date_end = datetime.date(y, m, last_day)
    except Exception:
        pass

    messagebox.showinfo("Готово", f"Доход записан: {total_amount:.2f} руб.")

    app.select_entity("Финансы")


def display_entity_cards(app, entity_name, records, columns):
    """Отображение записей в виде карточек"""
    for widget in app.scrollable_cards_frame.winfo_children():
        widget.destroy()

    app.card_frames = []
    app.scrollable_cards_frame.grid_columnconfigure((0, 1, 2), weight=1)
    column_names = [name for name, _ in columns]
    for index, record in enumerate(records):
        row, col = divmod(index, 3)

        card = ctk.CTkFrame(
            app.scrollable_cards_frame,
            width=300,
            height=200,
            corner_radius=10,
            fg_color=("#2a2d2e", "#212121"),
            border_width=2,
        )
        card.grid(row=row, column=col, padx=10, pady=10, sticky="ew")
        card.record_id = record["ID"]
        card.bind("<Button-1>", lambda event, card=card: app._select_card(card))
        app.card_frames.append(card)
        card.grid_columnconfigure(1, weight=1)


        header_text = f"#{record['ID']}"
        if len(column_names) > 1:
            header_text += f" - {record[column_names[1]]}"

        header_frame = ctk.CTkFrame(card, fg_color="#3A8FCD")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        header_frame.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(
            header_frame,
            text=header_text,
            font=ctk.CTkFont(size=14, weight="bold"),
        ).grid(row=0, column=0, padx=10, pady=5, sticky="w")

        data_rows = 1

        # Мини-превью прикреплённого файла для карточек "Эскизы"
        if entity_name == "Эскизы":
            file_path = (record["Файл"] or "").strip() if "Файл" in record.keys() else ""

            thumb_container = ctk.CTkFrame(card, fg_color="transparent")
            thumb_container.grid(row=1, column=0, columnspan=2, sticky="e", padx=10, pady=(0, 6))

            thumb_w, thumb_h = 90, 70
            if file_path and os.path.exists(file_path) and Image is not None:
                try:
                    pil_img = Image.open(file_path)
                    pil_img.thumbnail((thumb_w, thumb_h))
                    ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=pil_img.size)
                    lbl = ctk.CTkLabel(thumb_container, text="", image=ctk_img)
                    lbl.pack(anchor="e")
                    # Важно: держим ссылку, иначе картинка может пропасть из-за GC
                    card._thumb_img = ctk_img
                except Exception:
                    placeholder = ctk.CTkFrame(
                        thumb_container,
                        width=thumb_w,
                        height=thumb_h,
                        corner_radius=8,
                        fg_color="#2B2B2B",
                        border_width=1,
                        border_color="#333333",
                    )
                    placeholder.pack_propagate(False)
                    placeholder.pack(anchor="e")
                    ctk.CTkLabel(placeholder, text="нет фото", text_color="#AAAAAA").pack(expand=True)
            else:
                placeholder = ctk.CTkFrame(
                    thumb_container,
                    width=thumb_w,
                    height=thumb_h,
                    corner_radius=8,
                    fg_color="#2B2B2B",
                    border_width=1,
                    border_color="#333333",
                )
                placeholder.pack_propagate(False)
                placeholder.pack(anchor="e")
                ctk.CTkLabel(placeholder, text="нет фото", text_color="#AAAAAA").pack(expand=True)

            data_rows = 2

        for name in column_names:
            if name.upper() == "ID":
                continue
            if entity_name == "Эскизы" and name == "Файл":
                continue

            value = str(record[name])
            display_label = name

            if entity_name == "Записи":
                cursor = app.conn.cursor()
                if name == "ID_Клиента":
                    display_label = "Клиент"
                    cursor.execute(
                        'SELECT "ФИО" FROM "Клиенты" WHERE ID = ?',
                        (record[name],),
                    )
                    client_row = cursor.fetchone()
                    value = client_row["ФИО"] if client_row else "Неизвестно"
                elif name == "ID_Услуги":
                    display_label = "Услуга"
                    cursor.execute(
                        'SELECT "Название" FROM "Услуги" WHERE ID = ?',
                        (record[name],),
                    )
                    service_row = cursor.fetchone()
                    value = service_row["Название"] if service_row else "Не указана"
                elif name == "ID_Эскиза":
                    display_label = "Эскиз"
                    if record[name]:
                        cursor.execute(
                            'SELECT "Название" FROM "Эскизы" WHERE ID = ?',
                            (record[name],),
                        )
                        sketch_row = cursor.fetchone()
                        value = sketch_row["Название"] if sketch_row else "Не выбран"
                    else:
                        value = "Не выбран"

            text_color = "white"

            ctk.CTkLabel(
                card,
                text=f"{display_label}:",
                text_color="#aaaaaa",
            ).grid(row=data_rows, column=0, padx=(10, 5), pady=2, sticky="w")

            ctk.CTkLabel(
                card,
                text=value,
                font=ctk.CTkFont(weight="bold"),
                text_color=text_color,
            ).grid(row=data_rows, column=1, padx=(5, 10), pady=2, sticky="w")

            data_rows += 1
            if data_rows >= 6:
                break

        if entity_name == "Записи":
            def _complete(rid=record["ID"]):
                complete_appointment(app, rid)

            ctk.CTkButton(
                card,
                text="✅ Завершить",
                fg_color="#2ECC71",
                command=_complete,
            ).grid(row=data_rows, column=0, columnspan=2, padx=10, pady=(8, 6), sticky="ew")
            data_rows += 1