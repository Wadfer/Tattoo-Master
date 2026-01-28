import customtkinter as ctk
from tkinter import messagebox
import datetime
import calendar

import config
import database
import dialogs
import views

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class DBApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Менеджер БД тату-мастера")
        self.geometry("1100x800")

        self.conn = database.get_db_connection()
        self.current_entity = None
        self.selected_card = None
        self.card_frames = []
        self.sidebar_buttons = {}

        database.initialize_database(self.conn)

        self.calendar_date = datetime.date.today()
        self.schedule_date = datetime.date.today()
        self.finance_date = datetime.date.today()

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self.sidebar_frame = ctk.CTkFrame(self, width=280, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="nsew")

        ctk.CTkLabel(
            self.sidebar_frame,
            text="РАЗДЕЛЫ СИСТЕМЫ",
            font=ctk.CTkFont(size=16, weight="bold")
        ).grid(row=0, column=0, padx=20, pady=(20, 10))

        row_counter = 1
        for entity_name in config.FIXED_ENTITIES:
            btn = ctk.CTkButton(self.sidebar_frame, text=entity_name,
                                command=lambda name=entity_name: self.select_entity(name))
            btn.grid(row=row_counter, column=0, padx=20, pady=5, sticky="ew")
            self.sidebar_buttons[entity_name] = btn
            row_counter += 1

        self.sidebar_frame.grid_rowconfigure(row_counter, weight=1)

        self.content_frame = ctk.CTkFrame(self)
        self.content_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.content_frame.grid_rowconfigure(1, weight=1)
        self.content_frame.grid_columnconfigure(0, weight=1)

        self.top_controls = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.top_controls.grid(row=0, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.top_controls.grid_columnconfigure((0, 1, 2), weight=1)

        self.scrollable_cards_frame = ctk.CTkScrollableFrame(self.content_frame, label_text="Данные:", label_anchor="w",
                                                             corner_radius=10)
        self.scrollable_cards_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.scrollable_cards_frame.grid_columnconfigure(0, weight=1)

        if config.FIXED_ENTITIES:
            self.select_entity(config.FIXED_ENTITIES[0])

    def _get_table_columns(self, entity_name):
        cursor = self.conn.cursor()
        cursor.execute(f'PRAGMA table_info("{entity_name}")')
        return [(col[1], col[2]) for col in cursor.fetchall()]

    def select_entity(self, entity_name):
        self.current_entity = entity_name
        self.selected_card = None
        self._update_sidebar_buttons()
        self._display_entity_data(entity_name)

    def _update_sidebar_buttons(self):
        for entity_name, button in self.sidebar_buttons.items():
            if entity_name == self.current_entity:
                button.configure(fg_color="#3A8FCD", hover_color="#2A7FBD", 
                               border_color="#5BB3F0", border_width=2)
            else:
                button.configure(fg_color=["#3B8ED0", "#1F6AA5"], hover_color=["#36719F", "#144870"],
                               border_width=0)

    def _display_entity_data(self, entity_name):
        for widget in self.top_controls.winfo_children():
            widget.destroy()

        self.top_controls.grid_columnconfigure((0, 1, 2, 3, 4), weight=0)

        if entity_name == "Финансы":
            views.display_finance_report_view(self)
            return

        elif entity_name == "Расписание":
            records = views.get_appointment_data(self.conn, self.schedule_date)
            date_label_text = self.schedule_date.strftime("%d %B %Y").capitalize()
            self.scrollable_cards_frame.configure(
                label_text=f"Расписание на {date_label_text} ({len(records)} записей)")
            views.display_schedule_view(self, records, self.schedule_date)
            return

        else:
            self.top_controls.grid_columnconfigure((0, 1, 2), weight=1)
            cursor = self.conn.cursor()
            cursor.execute(f'SELECT * FROM "{entity_name}"')
            records = cursor.fetchall()
            columns = self._get_table_columns(entity_name)

            self._setup_card_controls() 

            self.scrollable_cards_frame.configure(label_text=f"Данные: {entity_name} ({len(records)} записей)")
            views.display_entity_cards(self, entity_name, records, columns)

        self.title(f"Менеджер БД тату-мастера - {entity_name}")

    def _setup_card_controls(self):

        ctk.CTkButton(self.top_controls, text="➕ Добавить", command=self.open_add_record_dialog).grid(row=0, column=0,
                                                                                                      padx=5, pady=10,
                                                                                                      sticky="ew")
        ctk.CTkButton(self.top_controls, text="✏️ Изменить", command=self.open_edit_record_dialog,
                      fg_color="#E67E22").grid(row=0, column=1, padx=5, pady=10, sticky="ew")
        ctk.CTkButton(self.top_controls, text="➖ Удалить", command=self.delete_record, fg_color="red").grid(row=0,
                                                                                                            column=2,
                                                                                                            padx=5,
                                                                                                            pady=10,
                                                                                                            sticky="ew")

    def delete_record(self):
        if self.selected_card is None:
            messagebox.showwarning("Предупреждение", "Выберите карточку.")
            return
        if self.current_entity in ["Расписание", "Финансы"]:
            messagebox.showwarning("Предупреждение", "Удаление здесь не поддерживается.")
            return
        if messagebox.askyesno("Подтверждение", "Удалить запись?"):
            record_id = self.selected_card.record_id
            if self.current_entity == "Услуги":
                try:
                    self.conn.execute('DELETE FROM "Запись_Услуги" WHERE "ID_Услуги" = ?', (record_id,))
                except Exception:
                    pass
            self.conn.execute(f'DELETE FROM "{self.current_entity}" WHERE ID = ?', (record_id,))
            self.conn.commit()
            self._display_entity_data(self.current_entity)

    def open_edit_record_dialog(self):
        dialogs.open_edit_record_dialog(self)

    def open_add_record_dialog(self):
        dialogs.open_add_record_dialog(self)

    def change_calendar_month(self, d):
        m = (self.calendar_date.month - 1 + d) % 12 + 1
        y = self.calendar_date.year + (self.calendar_date.month - 1 + d) // 12
        self.calendar_date = datetime.date(y, m, 1)
        self.calendar_date = datetime.date.today().replace(day=1)

    def change_schedule_date(self, delta):
        self.schedule_date += datetime.timedelta(days=delta)
        self._display_entity_data("Расписание")

    def change_finance_month(self, delta):
        current_year = self.finance_date.year
        current_month = self.finance_date.month
        new_month = (current_month - 1 + delta) % 12 + 1
        new_year = current_year + (current_month - 1 + delta) // 12
        self.finance_date = datetime.date(new_year, new_month, 1)
        self._display_entity_data("Финансы")

    def _select_card(self, card):
        for c in self.card_frames:
            c.configure(border_color=('#2a2d2e', '#212121'))
        card.configure(border_color=('#3A8FCD', '#3A8FCD'))
        self.selected_card = card


if __name__ == "__main__":
    app = DBApp()
    app.mainloop()
