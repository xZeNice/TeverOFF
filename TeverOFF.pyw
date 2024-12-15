import customtkinter as ctk
from pystray import Icon as icon, Menu as menu, MenuItem as item
from PIL import Image
import tkinter as tk
import json
import datetime
import os
import time
import threading

APP_TITLE = "TeverOFF"
APP_GEOMETRY = "225x250"
BASE_DIR = os.path.dirname(__file__)
ICON_PATH = os.path.join(BASE_DIR, "icon.png")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")


ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title(APP_TITLE)
        self.geometry(APP_GEOMETRY)
        self.resizable(False, False)
        self.tray_icon = None
        self.config = self.load_config()
        self.shutdown_scheduled = False
        self.shutdown_event = threading.Event()  # Используем threading.Event
        self.shutdown_thread = None
        self.create_widgets()
        self.create_tray_icon()
        self.schedule_shutdown()
        self.minimize_to_tray()

    def create_widgets(self):
        self.date_label = ctk.CTkLabel(self, text="Дата [ГГГГ-ММ-ДД]")
        self.date_label.pack(pady=5)
        self.date_entry = ctk.CTkEntry(self, placeholder_text="ГГГГ-ММ-ДД")
        self.date_entry.pack(pady=5)
        self.date_entry.insert(0, self.config.get("date", ""))

        self.time_label = ctk.CTkLabel(self, text="Время [ЧЧ:ММ]")
        self.time_label.pack(pady=5)
        self.time_entry = ctk.CTkEntry(self, placeholder_text="ЧЧ:ММ")
        self.time_entry.pack(pady=5)
        self.time_entry.insert(0, self.config.get("time", ""))

        self.daily_repeat = ctk.CTkCheckBox(self, text="Повторять ежедневно", command=self.toggle_date_entry)
        self.daily_repeat.pack(pady=5)
        self.daily_repeat.select() if self.config.get("daily_repeat", True) else self.daily_repeat.deselect()
        self.toggle_date_entry()

        self.save_button = ctk.CTkButton(self, text="Сохранить", command=self.save_config)
        self.save_button.pack(pady=10)

    def toggle_date_entry(self):
        is_enabled = not self.daily_repeat.get()
        self.date_entry.configure(state="normal" if is_enabled else "disabled")
        if not is_enabled:
            self.date_entry.delete(0, tk.END)

    def create_tray_icon(self):
        try:
            image = Image.open(ICON_PATH).convert("RGBA")
            image = image.resize((32, 32))
            self.tray_icon = icon(
                APP_TITLE,
                image,
                menu=self.create_tray_menu(),
            )
        except FileNotFoundError:
            print(f"Ошибка: Файл {ICON_PATH} не найден")
            return

    def create_tray_menu(self):
        return menu(
            item("Открыть меню", self.show_window),
            item("Выход", self.exit_app),
        )

    def show_window(self):
        if self.tray_icon:
            self.tray_icon.stop()
            self.deiconify()
            self.tray_icon = None
            self.create_tray_icon()
            self.update_tray_menu()

    def exit_app(self):
        self.cancel_shutdown()
        self.destroy()
        if self.tray_icon:
            self.tray_icon.stop()

    def minimize_to_tray(self):
        self.withdraw()
        if self.tray_icon:
            self.tray_icon.run()

    def on_closing(self):
        self.minimize_to_tray()
        return True

    def save_config(self):
        date_str = self.date_entry.get()
        time_str = self.time_entry.get()
        daily_repeat = self.daily_repeat.get()

        try:
            datetime.datetime.strptime(date_str, "%Y-%m-%d")
            datetime.datetime.strptime(time_str, "%H:%M")
        except ValueError:
            print("Неверный формат даты или времени.")
            return

        self.config = {
            "date": date_str,
            "time": time_str,
            "daily_repeat": daily_repeat,
        }
        self.save_json_config(self.config)
        print("Конфигурация сохранена!")
        self.schedule_shutdown()

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_json_config(self, data):
        with open(CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=4)

    def schedule_shutdown(self):
        self.cancel_shutdown()

        try:
            time_str = self.config.get("time", "")
            daily_repeat = self.config.get("daily_repeat", False)

            if not time_str:
                print("Время не задано.")
                self.shutdown_scheduled = False
                self.update_tray_menu()
                return

            now = datetime.datetime.now()
            shutdown_time = datetime.datetime.strptime(time_str, "%H:%M").time()

            if daily_repeat:
                shutdown_datetime = now.replace(hour=shutdown_time.hour, minute=shutdown_time.minute, second=0,
                                               microsecond=0)
                if shutdown_datetime < now:
                    shutdown_datetime += datetime.timedelta(days=1)
            else:
                date_str = self.config.get("date", "")
                if not date_str:
                    print("Дата не задана для одноразового выключения.")
                    self.shutdown_scheduled = False
                    self.update_tray_menu()
                    return

                shutdown_date = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                shutdown_datetime = datetime.datetime.combine(shutdown_date, shutdown_time)
                if shutdown_datetime < now:
                    print("Ошибка: Время завершения работы истекло.")
                    self.shutdown_scheduled = False
                    self.update_tray_menu()
                    return

            time_diff = shutdown_datetime - now
            seconds_to_shutdown = time_diff.total_seconds()

            if seconds_to_shutdown > 0:
                print(f"Планируется выключение через {time_diff}")
                self.shutdown_scheduled = True
                self.shutdown_event.clear()  # Сбрасываем событие
                self.shutdown_thread = threading.Thread(target=self.shutdown_timer_thread, args=(seconds_to_shutdown,))
                self.shutdown_thread.start()
                self.update_tray_menu()
            else:
                print("Ошибка: Время завершения работы истекло.")
                self.shutdown_scheduled = False
                self.update_tray_menu()

        except (KeyError, ValueError, TypeError) as e:
            print(f"Ошибка планирования выключения: {e}")
            self.shutdown_scheduled = False
            self.update_tray_menu()
        except Exception as e:
            print(f"Непредвиденная ошибка в schedule_shutdown: {e}")

    def shutdown_timer_thread(self, seconds):
        self.shutdown_event.wait(seconds)  # Ждем секунды или пока не сбросим событие
        if not self.shutdown_event.is_set(): # Проверка, что время не отменили
             self.perform_shutdown()

    def perform_shutdown(self):
        os.system("shutdown /s /t 0")

    def cancel_shutdown(self):
        if self.shutdown_thread and self.shutdown_thread.is_alive():
            self.shutdown_event.set()  # Устанавливаем событие, чтобы поток завершился
            self.shutdown_thread.join()  # Ждем завершения потока
            self.shutdown_thread = None
            self.shutdown_scheduled = False
            print("Запланированное выключение отменено.")


    def update_tray_menu(self):
        if self.tray_icon:
            if self.shutdown_scheduled:
                if self.config.get("daily_repeat", False):
                    time_str = self.config.get("time", "??:??")
                    shutdown_info = f"Выключение ежедневно | {time_str}"
                else:
                    date_str = self.config.get("date", "??-??-???")
                    time_str = self.config.get("time", "??:??")
                    shutdown_info = f"Выключение {date_str} | {time_str}"
            else:
                shutdown_info = "Выключение не запланировано"

            self.tray_icon.menu = menu(
                item(shutdown_info, lambda: None),
                item("Открыть меню", self.show_window),
                item("Выход", self.exit_app),
            )


if __name__ == "__main__":
    try:
        app = App()
        app.protocol("WM_DELETE_WINDOW", app.on_closing)
        tk.mainloop()
    except Exception as e:
        print(f"Произошла ошибка: {e}")