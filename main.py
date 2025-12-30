import logging
import os
import sqlite3
import sys
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

import requests
from PIL import Image, ImageTk, ImageDraw, ImageFont

# --- 1. Path & Display Configuration ---
if "DISPLAY" not in os.environ:
    os.environ["DISPLAY"] = ":0"

if getattr(sys, 'frozen', False):
    application_path = os.path.dirname(sys.executable)
else:
    application_path = os.path.dirname(os.path.abspath(__file__))

# --- 2. Logging Setup ---
log_path = os.path.join(application_path, "weather_debug.log")
logging.basicConfig(
    filename=log_path,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filemode='w'
)

# --- 3. Database Management ---
DB_DIR = os.path.join(application_path, "settings")
DB_PATH = os.path.join(DB_DIR, "settings.db")


def init_db():
    try:
        os.makedirs(DB_DIR, exist_ok=True)
        conn = sqlite3.connect(DB_PATH)
        conn.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        conn.commit()
        conn.close()
        logging.info("Database initialized successfully.")
    except Exception as e:
        logging.error(f"DB Init Error: {e}")


def get_setting(key):
    try:
        conn = sqlite3.connect(DB_PATH)
        res = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        conn.close()
        return res[0] if res else None
    except Exception as e:
        logging.error(f"DB Read Error: {e}")
        return None


def save_setting(key, value):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        conn.close()
        logging.info(f"Setting saved: {key}")
    except Exception as e:
        logging.error(f"DB Write Error: {e}")


# --- 4. Main Application ---
class WeatherApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        logging.info("Initializing WeatherApp...")

        self.api_key = get_setting("api_key")
        self.lat = get_setting("lat")
        self.lon = get_setting("lon")
        self.city = get_setting("city_name"),
        self.state = get_setting("state_abbr"),
        self.bg_image_ref = None
        self.forecast_details = []

        self.geometry("800x480+0+0")
        self.attributes("-fullscreen", True)
        self.overrideredirect(True)
        self.configure(bg="black")

        self.setup_ui()

        if not all([self.api_key, self.lat, self.lon]):
            self.after(1000, self.show_setup_dialog)
        else:
            self.after(500, self.update_weather)

        self.after(2000, self.scroll_alerts)

    def setup_ui(self):
        logging.debug("Configuring UI layers...")
        self.bg_label = tk.Label(self, bg="black")
        self.bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        self.tooltip = tk.Label(self, text="", font=("Arial", 10), bg="#222", fg="white",
                                relief="solid", bd=1, padx=8, pady=5)
        self.tooltip.place_forget()
        self.bg_label.bind("<Motion>", self.check_hover)

        self.top_bar = tk.Frame(self, bg="#111", height=35)
        self.top_bar.place(x=0, y=0, width=800)
        tk.Button(self.top_bar, text=" CONFIG ", font=("Arial", 8, "bold"), fg="white", bg="#333",
                  command=self.show_setup_dialog).pack(side="right", padx=10, pady=4)

        self.alert_canvas = tk.Canvas(self, height=30, bg="darkred", highlightthickness=0)
        self.alert_canvas.place(x=0, y=450, width=800)
        self.alert_text = self.alert_canvas.create_text(800, 15, text="Ready...", fill="white",
                                                        font=("Arial", 10, "bold"), anchor="w")

    def check_hover(self, event):
        if 305 <= event.y <= 442 and self.forecast_details:
            idx = (event.x - 10) // 158
            if 0 <= idx < len(self.forecast_details):
                self.tooltip.config(text=self.forecast_details[idx])
                self.tooltip.place(x=event.x, y=event.y - 80)
                return
        self.tooltip.place_forget()

    def update_weather(self):
        logging.info("Triggering weather update cycle.")
        if not self.api_key: return

        try:
            url = f"https://api.openweathermap.org/data/3.0/onecall?lat={self.lat}&lon={self.lon}&appid={self.api_key}&units=imperial"
            res = requests.get(url, timeout=10).json()

            if "current" in res:
                curr = res["current"]
                icon_code = curr['weather'][0]['icon']

                # 1. Background Composite
                bg_file = os.path.join(application_path, "images", f"{icon_code}_bg.png")
                if not os.path.exists(bg_file): bg_file = os.path.join(application_path, "images", "01d_bg.png")

                canvas = Image.open(bg_file).convert("RGBA").resize((800, 480), Image.Resampling.LANCZOS)
                overlay = Image.new("RGBA", (800, 480), (0, 0, 0, 0))
                draw_ov = ImageDraw.Draw(overlay)
                glass_color = (0, 0, 0, 60)

                draw_ov.rectangle([10, 45, 485, 290], fill=glass_color, outline=(255, 255, 255, 30), width=1)
                draw_ov.rectangle([520, 45, 790, 275], fill=glass_color, outline=(255, 255, 255, 30), width=1)
                for i in range(5):
                    x_box = 10 + (i * 158)
                    draw_ov.rectangle([x_box, 305, x_box + 152, 442], fill=glass_color, outline=(255, 255, 255, 40),
                                      width=1)
                    # Darker sub-box for the detailed text area
                    draw_ov.rectangle([x_box + 3, 355, x_box + 149, 435], fill=(0, 0, 0, 175),
                                      outline=(255, 255, 255, 20), width=1)

                canvas = Image.alpha_composite(canvas, overlay)

                # 2. Text Rendering
                draw = ImageDraw.Draw(canvas)
                try:
                    f_city = ImageFont.truetype("arial.ttf", 32)
                    f_temp = ImageFont.truetype("arialbd.ttf", 100)
                    f_desc = ImageFont.truetype("arial.ttf", 18)
                    f_det = ImageFont.truetype("arialbd.ttf", 18)
                    f_day = ImageFont.truetype("arialbd.ttf", 12)
                    f_f_t = ImageFont.truetype("arialbd.ttf", 14)
                    f_f_mm = ImageFont.truetype("arial.ttf", 10)
                    f_hum = ImageFont.truetype("arial.ttf", 10)
                except Exception as fe:
                    logging.error(f"Font error: {fe}")
                    f_city = f_temp = f_desc = f_det = f_day = f_f_t = f_f_mm = f_hum = ImageFont.load_default()

                # Current
                display_city = get_setting("city_name")
                display_state = get_setting("state_abbr")

                if display_city and display_state:
                    location_text = f"{display_city}, {display_state}"
                else:
                    location_text = res.get("timezone", "Local").split('/')[-1].replace('_', ' ')

                draw.text((30, 60), location_text, font=f_city, fill="#FFFFFF")
                draw.text((25, 95), f"{int(curr['temp'])}°", font=f_temp, fill="#FFFFFF")
                draw.text((30, 215), curr['weather'][0]['description'].capitalize(), font=f_desc, fill="#FFFFFF")
                draw.text((30, 240), datetime.now().strftime("%m/%d"), font=f_det, fill="#FFFFFF")

                ic_path = os.path.join(application_path, "images", f"{icon_code}_t@4x.png")
                if os.path.exists(ic_path):
                    bi = Image.open(ic_path).convert("RGBA")
                    canvas.alpha_composite(bi, (180, 100))

                # Details (Top Right)
                det = (f"Feels: {int(curr['feels_like'])}°\n"
                       f"Humid: {curr['humidity']}%\n"
                       f"Wind:  {int(curr['wind_speed'])} mph\n"
                       f"UV:    {curr.get('uvi', 0)}\n"
                       f"Vis:   {curr.get('visibility', 0) / 1609.34:.1f} mi\n"
                       f"Sunrise: {datetime.fromtimestamp(curr['sunrise']).strftime('%H:%M')}\n"
                       f"Sunset:  {datetime.fromtimestamp(curr['sunset']).strftime('%H:%M')}\n"
                       f"Dew Point: {int(curr['dew_point'])}°\n"
                       )
                draw.multiline_text((545, 65), det, font=f_det, fill="white", spacing=8)

                # Forecast
                self.forecast_details = []
                for i, d_data in enumerate(res.get("daily", [])[1:6]):
                    x = 25 + (i * 158)
                    w = d_data['weather'][0]
                    t, fl = d_data['temp'], d_data['feels_like']

                    self.forecast_details.append(
                        f"{w['description'].capitalize()}\n"
                        f"Day: {int(t['day'])}° (Feels: {int(fl['day'])}°)\n"
                        f"Night: {int(t['night'])}°\n"
                        f"Clouds: {d_data.get('clouds', 0)}%"
                    )

                    day_str = datetime.fromtimestamp(d_data['dt']).strftime("%a").upper()
                    date_str = datetime.fromtimestamp(d_data['dt']).strftime("%m/%d")
                    draw.text((x + 5, 312), f"{day_str} {date_str}", font=f_day, fill="#FFFFFF")

                    fi_path = os.path.join(application_path, "images", f"{w['icon']}_t@2x.png")
                    if os.path.exists(fi_path):
                        fi = Image.open(fi_path).convert("RGBA")
                        canvas.alpha_composite(fi, (x + 45, 280))

                    draw.text((x + 5, 360), f"{int(t['day'])}°/{int(fl['day'])}°", font=f_f_t, fill="#FFFFFF")
                    draw.text((x + 5, 375), f"L:{int(t['min'])} H:{int(t['max'])}", font=f_f_mm, fill="#FFFFFF")
                    draw.text((x + 5, 390), f"H:{d_data['humidity']}%", font=f_hum, fill="#48ff00")
                    draw.text((x + 5, 405), f"Sunrise: {datetime.fromtimestamp(d_data['sunrise']).strftime('%H:%M')}",
                              font=f_f_mm, fill="#FFFFFF")
                    draw.text((x + 5, 420), f"Sunset:  {datetime.fromtimestamp(d_data['sunset']).strftime('%H:%M')}",
                              font=f_f_mm, fill="#FFFFFF")

                # --- MOVE REFRESH LOGIC OUT OF THE FOR LOOP ---
                photo = ImageTk.PhotoImage(canvas)
                self.bg_label.config(image=photo)
                self.bg_image_ref = photo
                logging.info("Render complete.")

                # 3. Handle Alerts in Scroller
                alert_msgs = []
                if "alerts" in res:
                    for alert in res["alerts"]:
                        event = alert.get("event", "Alert")
                        desc = alert.get("description", "").replace("\n", " ")
                        alert_msgs.append(f"*** {event.upper()}: {desc} ***")

                if alert_msgs:
                    full_alert_text = "     ".join(alert_msgs)
                else:
                    full_alert_text = f"Last Sync: {datetime.now().strftime('%H:%M')}"

                self.alert_canvas.itemconfig(self.alert_text, text=full_alert_text, fill="white")

        except Exception as e:
            logging.error(f"Weather update fail: {e}")
        self.after(600000, self.update_weather)

    def scroll_alerts(self):
        try:
            coords = self.alert_canvas.coords(self.alert_text)
            if coords[0] < -1000:
                self.alert_canvas.coords(self.alert_text, 800, 15)
            else:
                self.alert_canvas.move(self.alert_text, -2, 0)
        except:
            pass
        self.after(35, self.scroll_alerts)

    def show_setup_dialog(self):
        logging.info("Opening setup.")
        setup = tk.Toplevel(self)
        setup.geometry("400x320+200+80")
        setup.overrideredirect(True)
        setup.configure(bg="#222", highlightthickness=2, highlightbackground="#4CAF50")
        setup.grab_set()
        tk.Label(setup, text="API CONFIG", fg="#4CAF50", bg="#222", font=("Arial", 12, "bold")).pack(pady=15)

        tk.Label(setup, text="OpenWeather API Key", fg="white", bg="#222", font=("Arial", 9)).pack()
        e_key = tk.Entry(setup, width=35)
        e_key.insert(0, self.api_key or "")
        e_key.pack(pady=5)

        tk.Label(setup, text="Zip Code", fg="white", bg="#222", font=("Arial", 9)).pack()
        e_zip = tk.Entry(setup, width=15, justify='center')
        # Try to load existing zip, or leave blank
        current_zip = get_setting("zip_code") or ""
        e_zip.insert(0, current_zip)
        e_zip.pack(pady=5)

        def save():
            api_key = e_key.get()
            zip_code = e_zip.get()

            try:
                # Use Zippopotam.us for free zip-to-lat-lon conversion (No API Key required)
                geo_url = f"https://api.zippopotam.us/us/{zip_code}"
                response = requests.get(geo_url, timeout=10)

                if response.status_code == 200:
                    geo_data = response.json()
                    place = geo_data["places"][0]
                    new_lat, new_lon = place["latitude"], place["longitude"]
                    city_name = place["place name"]
                    state_abbr = place["state abbreviation"]

                    save_setting("api_key", api_key)
                    save_setting("zip_code", zip_code)
                    save_setting("lat", new_lat)
                    save_setting("lon", new_lon)
                    save_setting("city_name", city_name)
                    save_setting("state_abbr", state_abbr)

                    self.api_key, self.lat, self.lon = api_key, new_lat, new_lon
                    setup.destroy()
                    self.update_weather()
                else:

                    messagebox.showerror("Error", f"Could not find Zip Code: {zip_code}")
            except Exception as e:
                logging.error(f"Geocoding error: {e}")
                messagebox.showerror("Error", "Failed to connect to geocoding service")

        tk.Button(setup, text=" SAVE & SYNC ", bg="#4CAF50", fg="white", font=("Arial", 10, "bold"), width=15,
                  command=save).pack(pady=15)
        tk.Button(setup, text=" CANCEL ", bg="#444", fg="white", width=15,
                  command=setup.destroy).pack(pady=5)
        tk.Button(setup, text=" EXIT APP ", bg="#333", fg="red", command=lambda: sys.exit(0)).pack()


if __name__ == "__main__":
    init_db()
    WeatherApp().mainloop()
