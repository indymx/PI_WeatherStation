import logging
import sys
import os
import tkinter as tk
from tkinter import messagebox
import sqlite3
import requests
import json
from PIL import Image, ImageTk

try:
    import PIL._tkinter_finder
except ImportError:
    pass
from datetime import datetime
import subprocess

# --- Display & Path Configuration ---
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":0"

if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

# --- Logging Setup ---
log_path = os.path.join(application_path, "weather_debug.log")
logging.basicConfig(
    filename=log_path,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)


class LoggerWriter:
    def __init__(self, level):
        self.level = level

    def write(self, message):
        if message.strip(): self.level(message.strip())

    def flush(self): pass


sys.stdout = LoggerWriter(logging.info)
sys.stderr = LoggerWriter(logging.error)


def disable_screen_blanking():
    try:
        logging.info("Requesting screen to stay awake (xset)...")
        subprocess.run(["xset", "s", "off"], check=False)
        subprocess.run(["xset", "s", "noblank"], check=False)
        subprocess.run(["xset", "-dpms"], check=False)
    except Exception as e:
        logging.warning(f"Screen blanking control failed: {e}")


# --- Database Management ---
SETTINGS_DIR = os.path.join(application_path, "settings")
DB_PATH = os.path.join(SETTINGS_DIR, "settings.db")

if not os.path.exists(SETTINGS_DIR):
    os.makedirs(SETTINGS_DIR)


def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings
                 (
                     key
                     TEXT
                     PRIMARY
                     KEY,
                     value
                     TEXT
                 )''')
    conn.commit()
    conn.close()


def get_setting(key):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key=?", (key,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        logging.error(f"DB Read Error: {e}")
        return None


def save_setting(key, value):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


# --- Main Application ---
class WeatherApp(tk.Tk):
    def __init__(self):
        super().__init__()
        logging.info("Starting WeatherApp UI Initialization...")

        self.geometry("800x480+0+0")
        self.attributes("-fullscreen", True)
        self.overrideredirect(True)
        self.configure(bg="black")

        self.api_key = get_setting("api_key")
        self.zipcode = get_setting("zipcode")
        self.icon_cache = {}

        self.setup_ui()

        if not self.api_key or not self.zipcode:
            self.after(1000, self.show_setup_dialog)
        else:
            self.after(500, self.update_weather)

        self.after(2000, self.scroll_alerts)

    def get_weather_icon(self, icon_code, size="@2x"):
        cache_key = f"{icon_code}{size}"
        if cache_key in self.icon_cache:
            return self.icon_cache[cache_key]

        icon_path = os.path.join(application_path, "images", f"{icon_code}_t{size}.png")
        try:
            if not os.path.exists(icon_path):
                logging.error(f"Icon file not found: {icon_path}")
                return None
            img = Image.open(icon_path).convert("RGBA")
            photo = ImageTk.PhotoImage(img)
            self.icon_cache[cache_key] = photo
            return photo
        except Exception as e:
            logging.error(f"Pillow Error loading icon: {e}")
            return None

    def setup_ui(self):
        # 1. Top Bar
        self.top_bar = tk.Frame(self, bg="#111", height=45)
        self.top_bar.pack(side="top", fill="x")
        self.top_bar.pack_propagate(False)

        self.settings_btn = tk.Button(self.top_bar, text=" ⚙ CONFIGURATION ", font=("Arial", 10, "bold"),
                                      fg="white", bg="#444", bd=1, relief="raised",
                                      activebackground="#666", activeforeground="white",
                                      command=self.show_setup_dialog)
        self.settings_btn.pack(side="right", padx=10, pady=5)

        # 2. Alert Scroller (Reserved space at bottom)
        self.alert_canvas = tk.Canvas(self, height=35, bg="darkred", highlightthickness=0)
        self.alert_canvas.pack(side="bottom", fill="x")
        self.alert_text = self.alert_canvas.create_text(800, 17, text="Connecting to weather service...",
                                                        fill="white", font=("Arial", 11, "bold"), anchor="w")

        # 3. Main Body
        self.content_container = tk.Frame(self, bg="black")
        self.content_container.pack(side="top", fill="both", expand=True)

        self.main_frame = tk.Frame(self.content_container, bg="black")
        self.main_frame.pack(side="top", fill="both", expand=True, padx=20, pady=5)

        self.curr_left = tk.Frame(self.main_frame, bg="black")
        self.curr_left.pack(side="left", fill="both", expand=True)

        self.city_label = tk.Label(self.curr_left, text="---", font=("Arial", 24), fg="white", bg="black")
        self.city_label.pack(anchor="w")

        self.temp_row = tk.Frame(self.curr_left, bg="black")
        self.temp_row.pack(anchor="w")

        self.temp_label = tk.Label(self.temp_row, text="--°", font=("Arial", 80, "bold"), fg="white", bg="black")
        self.temp_label.pack(side="left")

        self.big_icon_label = tk.Label(self.temp_row, bg="black")
        self.big_icon_label.pack(side="left", padx=15)

        self.desc_label = tk.Label(self.curr_left, text="Ready.", font=("Arial", 14), fg="gray", bg="black")
        self.desc_label.pack(anchor="w")

        self.curr_right = tk.Frame(self.main_frame, bg="black")
        self.curr_right.pack(side="right", fill="both", expand=True)
        self.details_label = tk.Label(self.curr_right, text="", font=("Courier New", 12), justify="left", fg="#4CAF50",
                                      bg="black")
        self.details_label.pack(anchor="e", pady=5)

        # 4. 5-Day Strip
        self.forecast_strip = tk.Frame(self.content_container, bg="black")
        self.forecast_strip.pack(side="top", fill="x", padx=10, pady=5)

        # Tooltip Overlay
        self.tooltip = tk.Label(self, text="", font=("Arial", 10), bg="#222", fg="white", relief="solid", bd=1, padx=8,
                                pady=5)
        self.tooltip.place_forget()

        self.forecast_items = []
        for i in range(5):
            box = tk.Frame(self.forecast_strip, bg="#111", highlightbackground="#222", highlightthickness=1)
            box.pack(side="left", expand=True, fill="both", padx=2)

            day = tk.Label(box, text="---", font=("Arial", 9, "bold"), fg="gray", bg="#111")
            day.pack(pady=2)
            icon = tk.Label(box, bg="#111")
            icon.pack()
            t_f = tk.Label(box, text="--°/--°", font=("Arial", 10, "bold"), fg="white", bg="#111")
            t_f.pack()
            m_m = tk.Label(box, text="L:-- H:--", font=("Arial", 8), fg="gray", bg="#111")
            m_m.pack()
            hum = tk.Label(box, text="H:--%", font=("Arial", 8), fg="#00BCD4", bg="#111")
            hum.pack(pady=2)

            item_data = {'frame': box, 'day': day, 'icon': icon, 'temp_feel': t_f, 'min_max': m_m, 'humidity': hum,
                         'details': ""}
            self.forecast_items.append(item_data)

            # Bind Hover Events
            def on_enter(event, idx=i):
                details = self.forecast_items[idx]['details']
                if details:
                    self.tooltip.config(text=details)
                    self.tooltip.place(x=event.widget.winfo_rootx(), y=280)
                    self.forecast_items[idx]['frame'].config(highlightbackground="#4CAF50")

            def on_leave(event, idx=i):
                self.tooltip.place_forget()
                self.forecast_items[idx]['frame'].config(highlightbackground="#222")

            box.bind("<Enter>", on_enter)
            box.bind("<Leave>", on_leave)
            for widget in box.winfo_children():
                widget.bind("<Enter>", lambda e, idx=i: on_enter(e, idx))
                widget.bind("<Leave>", lambda e, idx=i: on_leave(e, idx))

    def show_setup_dialog(self):
        logging.info("Opening Settings Dialog...")
        setup = tk.Toplevel(self)
        setup.title("Configuration")

        # OverrideRedirect ensures the popup layers correctly over the kiosk main window
        setup.geometry("500x380+150+50")
        setup.overrideredirect(True)
        setup.configure(bg="#222", highlightbackground="#4CAF50", highlightthickness=2)

        setup.transient(self)
        setup.lift()
        setup.attributes("-topmost", True)
        setup.grab_set()

        tk.Label(setup, text="API SETTINGS", font=("Arial", 16, "bold"), fg="#4CAF50", bg="#222").pack(pady=15)
        tk.Label(setup, text="OpenWeather Key:", fg="white", bg="#222").pack()
        ent_key = tk.Entry(setup, width=40, font=("Arial", 12), bg="#333", fg="white", insertbackground="white")
        ent_key.insert(0, self.api_key or "");
        ent_key.pack(pady=5)
        tk.Label(setup, text="Zipcode:", fg="white", bg="#222").pack()
        ent_zip = tk.Entry(setup, width=15, font=("Arial", 12), bg="#333", fg="white", insertbackground="white")
        ent_zip.insert(0, self.zipcode or "");
        ent_zip.pack(pady=5)

        def save():
            k, z = ent_key.get().strip(), ent_zip.get().strip()
            if k and z:
                changed = (k != self.api_key or z != self.zipcode)
                save_setting("api_key", k);
                save_setting("zipcode", z)
                self.api_key, self.zipcode = k, z
                setup.destroy()
                if changed: self.update_weather()
            else:
                messagebox.showwarning("Error", "All fields required.")

        def force_exit():
            logging.info("Shutting down app.")
            self.quit()
            self.destroy()
            sys.exit(0)

        tk.Button(setup, text="SAVE & REFRESH", command=save, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"),
                  width=20, height=2).pack(pady=10)
        tk.Button(setup, text="QUIT APP", command=force_exit, bg="#f44336", fg="white", font=("Arial", 10, "bold"),
                  width=20, height=2).pack(pady=5)
        tk.Button(setup, text="CANCEL", command=setup.destroy, bg="#222", fg="gray", bd=0).pack(side="bottom", pady=5)

    def update_weather(self):
        if not self.api_key or not self.zipcode: return
        logging.info("Fetching weather data...")
        try:
            url = f"http://api.openweathermap.org/data/2.5/forecast?zip={self.zipcode},us&appid={self.api_key}&units=imperial"
            res = requests.get(url).json()

            if str(res.get("cod")) == "200":
                curr = res["list"][0]
                icon_code = curr['weather'][0]['icon']

                self.city_label.config(text=res["city"]["name"])
                self.temp_label.config(text=f"{int(curr['main']['temp'])}°")
                self.desc_label.config(text=curr['weather'][0]['description'].capitalize())

                img_big = self.get_weather_icon(icon_code, size="@4x")
                if img_big: self.big_icon_label.config(image=img_big)

                det = (f"Feels: {int(curr['main']['feels_like'])}°\n"
                       f"Humid: {curr['main']['humidity']}%\n"
                       f"Wind:  {curr['wind']['speed']} mph\n"
                       f"Pres:  {curr['main']['pressure']} hPa\n"
                       f"Vis:   {curr.get('visibility', 0) / 1000:.1f} km")
                self.details_label.config(text=det)

                daily = res["list"][::8]
                for i, data in enumerate(daily[:5]):
                    m = data['main']
                    w = data['weather'][0]
                    self.forecast_items[i]['day'].config(text=datetime.fromtimestamp(data['dt']).strftime("%a").upper())
                    self.forecast_items[i]['temp_feel'].config(text=f"{int(m['temp'])}°/{int(m['feels_like'])}°")
                    self.forecast_items[i]['min_max'].config(text=f"L:{int(m['temp_min'])} H:{int(m['temp_max'])}")
                    self.forecast_items[i]['humidity'].config(text=f"H:{m['humidity']}%")

                    self.forecast_items[i]['details'] = (
                        f"{w['description'].capitalize()}\n"
                        f"Wind: {data['wind']['speed']} mph\n"
                        f"Clouds: {data['clouds']['all']}%"
                    )

                    img_f = self.get_weather_icon(w['icon'], size="@2x")
                    if img_f: self.forecast_items[i]['icon'].config(image=img_f)

                self.alert_canvas.itemconfig(self.alert_text,
                                             text=f"Last Sync: {datetime.now().strftime('%H:%M')}. All conditions normal.")
            else:
                self.desc_label.config(text=f"API: {res.get('message')}")
        except Exception as e:
            logging.error(f"Update error: {e}", exc_info=True)

        self.after(600000, self.update_weather)

    def scroll_alerts(self):
        try:
            coords = self.alert_canvas.coords(self.alert_text)
            if not coords:
                self.after(500, self.scroll_alerts)
                return
            self.alert_canvas.move(self.alert_text, -2, 0)
            if coords[0] < -750:
                self.alert_canvas.coords(self.alert_text, 800, 17)
            self.after(35, self.scroll_alerts)
        except Exception:
            self.after(1000, self.scroll_alerts)


if __name__ == "__main__":
    init_db()
    disable_screen_blanking()
    WeatherApp().mainloop()