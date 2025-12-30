# Python Weather Dashboard

A sleek, full-screen weather station dashboard built with Python and Tkinter. This application provides real-time weather updates, a 5-day forecast, and scrolling emergency alerts, designed specifically for dedicated displays or Raspberry Pi setups.

## 🌟 Features

*   **Real-time Weather:** Displays current temperature, "feels like" conditions, and weather descriptions.
*   **Dynamic Backgrounds:** Automatically changes the background image based on current weather conditions (e.g., clear, rainy, cloudy).
*   **5-Day Forecast:** Detailed daily forecast including high/low temperatures, humidity, and sunrise/sunset times.
*   **Scrolling Alerts:** A dedicated ticker at the bottom for official weather alerts or sync status.
*   **Interactive Tooltips:** Hover over forecast boxes to see detailed condition summaries.
*   **Easy Configuration:** Built-in setup dialog to configure your OpenWeather API key and Location (via Zip Code).
*   **Persistent Settings:** Uses an SQLite backend to remember your configuration between restarts.

## 🛠️ Tech Stack

*   **Language:** Python 3.12+
*   **GUI Framework:** Tkinter
*   **Imaging:** Pillow (PIL) for advanced rendering and image compositing.
*   **Data Sources:** 
    *   [OpenWeather One Call API 3.0](https://openweathermap.org/api/one-call-3) for weather data.
    *   [Zippopotam.us](https://api.zippopotam.us/) for free Zip-to-Lat/Lon geocoding.

## 📋 Prerequisites

Before running the application, ensure you have:
1.  An **OpenWeather API Key** (One Call 3.0 subscription).
2.  A folder named `images` in the project root containing weather-specific icons and backgrounds (e.g., `01d_bg.png`, `01d_t@4x.png`).

## 🚀 Installation & Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd <project-directory>
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # macOS/Linux
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install pillow requests
    ```

4.  **Run the application:**
    ```bash
    python main.py
    ```

## ⚙️ Configuration

On the first launch, the application will automatically open the **API CONFIG** dialog.
*   **API Key:** Enter your OpenWeather API 3.0 key.
*   **Zip Code:** Enter your US Zip Code to automatically fetch coordinates and city names.
*   Click **SAVE & SYNC** to initialize the dashboard.

## 📂 Project Structure

*   `main.py`: The core application logic and UI rendering.
*   `settings/`: Contains the SQLite database (`settings.db`) for saved configurations.
*   `images/`: (User Provided) Directory for weather icons and background overlays.
*   `weather_debug.log`: Automatically generated log file for troubleshooting.

## 📝 License

This project is open-source and available under the [MIT License](LICENSE).