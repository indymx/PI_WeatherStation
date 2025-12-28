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

# --- Display & Environment Configuration ---
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":0"

# Determine path for assets (works for script and PyInstaller)
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
    """Request the system to keep the screen on."""
    try:
        logging.info("Disabling screen blanking...")
        subprocess.run(["xset", "s", "off"], check=False)
        subprocess.run(["xset", "s", "noblank"], check=False)
        subprocess.run(["xset", "-dpms"], check=False)
    except Exception as e:
        logging.warning(f"xset failed (common on Wayland): {e}")

# --- Database Management ---
SETTINGS_DIR = os.path.join(application_path, "settings")
DB_PATH = os.path.join(SETTINGS_DIR, "settings.db")

if not os.path.exists(SETTINGS_DIR):
    os.makedirs(SETTINGS_DIR)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key=?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None

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
        logging.info("Initializing WeatherApp UI...")
        self.title("Pi Weather Station")
        
        # Robust Fullscreen/Kiosk Mode
        self.geometry("800x480+0+0")
        self.attributes("-fullscreen", True)
        self.overrideredirect(True) 
        self.configure(bg="black")
        
        # Load settings and LOG them
        self.api_key = get_setting("api_key")
        self.zipcode = get_setting("zipcode")
        logging.info(f"Loaded Settings: API_KEY={'SET' if self.api_key else 'MISSING'}, ZIP={self.zipcode}")
        
        self.icon_cache = {}
        self.setup_ui()
        
        # Validation: check for non-empty values
        if not self.api_key or not self.zipcode or self.api_key == "" or self.zipcode == "":
            logging.info("Settings missing or empty. Prompting for configuration.")
            self.after(1000, self.show_setup_dialog)
        else:
            logging.info("Settings found. Starting weather update cycle.")
            self.update_weather()
            
        self.scroll_alerts()

    def update_weather(self):
        logging.info("update_weather() called.") # Add this to track execution
        if not self.api_key or not self.zipcode: 
            logging.warning("update_weather aborted: No API Key or Zipcode.")
            return

    def setup_ui(self):
        # 1. Top Bar
        self.top_bar = tk.Frame(self, bg="#111", height=40)
        self.top_bar.pack(side="top", fill="x")
        self.top_bar.pack_propagate(False)

        tk.Button(self.top_bar, text="⚙ SETTINGS", font=("Arial", 9, "bold"), 
                  fg="white", bg="#333", bd=0, padx=15, command=self.show_setup_dialog).pack(side="right", fill="y")

        # 2. Main Container (Using expand=True to ensure it pushes the scroller to bottom)
        self.content_container = tk.Frame(self, bg="black")
        self.content_container.pack(side="top", fill="both", expand=True)

        # Current Conditions Frame
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
        self.big_icon_label.pack(side="left", padx=10)
        
        self.desc_label = tk.Label(self.curr_left, text="Check settings...", font=("Arial", 14), fg="gray", bg="black")
        self.desc_label.pack(anchor="w")

        self.curr_right = tk.Frame(self.main_frame, bg="black")
        self.curr_right.pack(side="right", fill="both", expand=True)
        self.details_label = tk.Label(self.curr_right, text="", font=("Courier New", 12), justify="left", fg="#4CAF50", bg="black")
        self.details_label.pack(anchor="e", pady=5)

        # 3. 5-Day Forecast (Reduced padding to save vertical space)
        self.forecast_strip = tk.Frame(self.content_container, bg="black")
        self.forecast_strip.pack(side="top", fill="x", padx=10, pady=5)
        
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
            self.forecast_items.append({'day': day, 'icon': icon, 'temp_feel': t_f, 'min_max': m_m, 'humidity': hum})

        # 4. Scroller (Bottom)
        self.alert_canvas = tk.Canvas(self, height=30, bg="darkred", highlightthickness=0)
        self.alert_canvas.pack(side="bottom", fill="x")
        self.alert_text = self.alert_canvas.create_text(800, 15, text="Ready.", fill="white", font=("Arial", 11, "bold"), anchor="w")

    def show_setup_dialog(self):
        setup = tk.Toplevel(self)
        setup.title("Settings")
        setup.geometry("500x380+150+50")
        setup.configure(bg="#222")
        setup.grab_set()
        
        tk.Label(setup, text="Weather Setup", font=("Arial", 16, "bold"), fg="#4CAF50", bg="#222").pack(pady=15)
        tk.Label(setup, text="API Key:", fg="white", bg="#222").pack()
        ent_key = tk.Entry(setup, width=40, font=("Arial", 12), bg="#333", fg="white", insertbackground="white")
        ent_key.insert(0, self.api_key or ""); ent_key.pack(pady=5)
        tk.Label(setup, text="Zipcode:", fg="white", bg="#222").pack()
        ent_zip = tk.Entry(setup, width=15, font=("Arial", 12), bg="#333", fg="white", insertbackground="white")
        ent_zip.insert(0, self.zipcode or ""); ent_zip.pack(pady=5)
        
        def save():
            k, z = ent_key.get().strip(), ent_zip.get().strip()
            if k and z:
                changed = (k != self.api_key or z != self.zipcode)
                save_setting("api_key", k); save_setting("zipcode", z)
                self.api_key, self.zipcode = k, z
                setup.destroy()
                if changed: self.update_weather()
            else: messagebox.showwarning("Error", "Required fields.")

        def shutdown():
            logging.info("System shutdown triggered from UI.")
            self.quit()
            self.destroy()
            sys.exit(0)

        tk.Button(setup, text="SAVE & REFRESH", command=save, bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), width=20, height=2).pack(pady=10)
        tk.Button(setup, text="QUIT APP", command=shutdown, bg="#f44336", fg="white", font=("Arial", 10, "bold"), width=20, height=2).pack(pady=5)

    def update_weather(self):
        if not self.api_key or not self.zipcode: return
        try:
            url = f"http://api.openweathermap.org/data/2.5/forecast?zip={self.zipcode},us&appid={self.api_key}&units=imperial"
            res = requests.get(url).json()
            logging.info("Weather Data Fetched.")

            if str(res.get("cod")) == "200":
                curr = res["list"][0]
                icon = curr['weather'][0]['icon']
                self.city_label.config(text=res["city"]["name"])
                self.temp_label.config(text=f"{int(curr['main']['temp'])}°")
                self.desc_label.config(text=curr['weather'][0]['description'].capitalize())
                
                # Big @4x Icon
                big_img = self.get_weather_icon(icon, size="@4x")
                if big_img: self.big_icon_label.config(image=big_img)

                det = (f"Feels Like: {int(curr['main']['feels_like'])}°\n"
                       f"Humidity:   {curr['main']['humidity']}%\n"
                       f"Wind:       {curr['wind']['speed']} mph\n"
                       f"Pressure:   {curr['main']['pressure']} hPa\n"
                       f"Visibility: {curr.get('visibility',0)/1000:.1f} km")
                self.details_label.config(text=det)
                
                # Forecast @2x Icons
                daily = res["list"][::8] 
                for i, data in enumerate(daily[:5]):
                    m = data['main']
                    self.forecast_items[i]['day'].config(text=datetime.fromtimestamp(data['dt']).strftime("%a").upper())
                    self.forecast_items[i]['temp_feel'].config(text=f"{int(m['temp'])}°/{int(m['feels_like'])}°")
                    self.forecast_items[i]['min_max'].config(text=f"L:{int(m['temp_min'])} H:{int(m['temp_max'])}")
                    self.forecast_items[i]['humidity'].config(text=f"H:{m['humidity']}%")
                    f_img = self.get_weather_icon(data['weather'][0]['icon'], size="@2x")
                    if f_img: self.forecast_items[i]['icon'].config(image=f_img)
                
                self.alert_canvas.itemconfig(self.alert_text, text=f"Last sync: {datetime.now().strftime('%H:%M')}. No severe alerts.")
            else:
                self.desc_label.config(text=f"API: {res.get('message')}")
        except Exception as e:
            logging.error(f"Sync fail: {e}", exc_info=True)
        
        self.after(600000, self.update_weather) # 10min

    def scroll_alerts(self):
        self.alert_canvas.move(self.alert_text, -2, 0)
        if self.alert_canvas.coords(self.alert_text)[0] < -700:
            self.alert_canvas.coords(self.alert_text, 800, 17)
        self.after(35, self.scroll_alerts)

if __name__ == "__main__":
    init_db()
    disable_screen_blanking()
    WeatherApp().mainloop()
