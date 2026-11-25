# SpotPrice Display

A real-time Finnish electricity spot price monitor built with CircuitPython for the Adafruit ESP32-S3 TFT Feather. Displays current electricity prices with color-coded backgrounds and 8-hour/24-hour forecast graphs.

![CI](https://github.com/McShoothy/spotprice/actions/workflows/ci.yml/badge.svg) ![License: CC BY-NC 4.0](https://img.shields.io/badge/License-CC%20BY--NC%204.0-blue) ![CircuitPython](https://img.shields.io/badge/CircuitPython-10.x-purple)

![Device Photo](images/device.jpeg)
(This image was taken before adding the new font)

## Quickstart

Get up and running in a couple of minutes.

1) Flash CircuitPython 10.x for the ESP32-S3 TFT Feather

> Download the `.uf2` file from [adafruit_feather_esp32s3_tft](https://circuitpython.org/board/adafruit_feather_esp32s3_reverse_tft/)

> Double press the Reset button

> copy the `.uf2` file to FTHRS3BOOT

2) Connect the board via USB and run the installer from this project directory
```bash
chmod +x install.sh
./install.sh
```

3) Configure WiFi (first boot)
  > The device shows a QR code; scan it to join the temporary WiFi and open the setup page
  ![Device Photo](images/connect-to-wifi.jpeg)
> Select your home WiFi and enter the password; the device reboots and connects
  ![Device Photo](images/my_wifi.jpeg)

  After this the device will reboot automatically and start working.

1) Use the device
- Press `D0` to cycle: Price → 8H Graph → 24H Graph
- Hold `D0` during boot to keep the USB drive writable for development

## Features

- **Real-time price display** with color-coded background (green = cheap, red = expensive)
- **8-hour and 24-hour forecast graphs** with smooth curves and 15-minute resolution
- **15-minute price resolution** - tracks Finnish Fingrid's quarter-hourly pricing
- **Smart fetching** gets tomorrow's prices once a day, right after they're published (~14:05 Finnish time), retrying if Nord Pool is late
- **Power optimized** - WiFi disabled between fetches, adjustable display brightness
- **WiFi captive portal** for easy setup without editing config files
- **QR code setup** - scan to connect and configure
- **Automatic NTP sync** for accurate time-based pricing
- **Button controls** for switching views and entering setup mode
- **Graceful degradation** if optional libraries are missing

## Hardware

### Required

| Component | Description | Purchase Link |
|-----------|-------------|---------------|
| Adafruit ESP32-S3 TFT Feather | Main board with built-in 1.14" TFT display | [Adafruit](https://www.adafruit.com/product/5345) |
| USB-C Cable | For power and programming (Any USB-C cable capable of datatransfer will do) | [Adafruit](https://www.adafruit.com/product/4473) |

### Optional

| Component | Description | Purchase Link |
|-----------|-------------|---------------|
| LiPo Battery | 3.7V battery for portable use | [Adafruit](https://www.adafruit.com/product/328) |

## Photos

| Main Display | Forecast View | Setup Screen |
|--------------|---------------|--------------|
| ![Price Display](images/price_display.jpeg) ![Price Display](images/price_display1.jpeg) | ![Forecast](images/forecast.jpeg)![Forecast](images/forecast8.jpeg) | ![Setup](images/connect-to-wifi1.jpeg) ![Setup](images/setup.jpeg) |

## Screenshots

Captured pixel-for-pixel from the display itself (shown at 2×).

**Price view**: the background colour shows the price level.

| Negative | Cheap | Mid | Expensive |
|:---:|:---:|:---:|:---:|
| ![Negative price on blue](images/screen-price-negative.png) | ![Cheap price on green](images/screen-price-green.png) | ![Mid price on yellow](images/screen-price-yellow.png) | ![Expensive price on red](images/screen-price-red.png) |
| −1.2 c/kWh | 0.60 c/kWh | 7.5 c/kWh | 15.4 c/kWh |

**Forecast graphs**: real prices from 5 March 2026, a day that starts green overnight, climbs to red morning and evening peaks, and drops back to green.

| 24H | 8H |
|:---:|:---:|
| ![24-hour forecast graph](images/screen-graph-24h.png) | ![8-hour forecast graph](images/screen-graph-8h.png) |
| 02:00 → 02:00 the next day | The morning climb, 04:00 → 12:00 |

**WiFi setup**: shown on first boot (or when WiFi fails). Scan the first code to join the device's own network, then the second to open the setup page.

| 1. Join the setup network | 2. Open the setup page |
|:---:|:---:|
| ![QR code to join the SpotPrice network](images/screen-setup-join-wifi.png) | ![QR code to open the setup page](images/screen-setup-open-page.png) |
| The password is random on every boot | Appears once your phone has connected |

## Installation

### 1. Install CircuitPython

Download and install CircuitPython 10.x for the ESP32-S3 TFT Feather from:
https://circuitpython.org/board/adafruit_feather_esp32s3_tft/

### 2. Quick Install (Recommended)

Connect your device via USB and run:

```bash
./install.sh
```

This script will:
- Create a Python virtual environment
- Install `circup` (CircuitPython library manager)
- Copy all project files to your device
- Install required CircuitPython libraries automatically

### 3. Manual Installation (Alternative)

If you prefer to install manually:

**Install libraries with circup:**

```bash
python3 -m venv venv
source venv/bin/activate
pip install circup
circup install adafruit_requests adafruit_connection_manager adafruit_ntp adafruit_ticks adafruit_display_text adafruit_bitmap_font adafruit_miniqr
```

**Or manually copy these libraries** from the [Adafruit CircuitPython Bundle](https://circuitpython.org/libraries) to the `/lib` folder:

- `adafruit_requests.mpy`
- `adafruit_ntp.mpy`
- `adafruit_connection_manager.mpy`
- `adafruit_ticks.mpy`
- `adafruit_display_text/` (folder)
- `adafruit_miniqr.mpy`
- `adafruit_bitmap_font/` (folder)

**Copy project files** to your CIRCUITPY drive:

```
CIRCUITPY/
    boot.py
    main.py
    spotprice/        (folder)
    font.pcf          (UI font)
    price.pcf         (large price digits)
    settings.toml     (created automatically during setup)
    lib/
        (libraries listed above)
```

### 4. Configure WiFi

There are two ways to configure WiFi credentials:

**Option A: Captive Portal (Recommended for first-time setup)**

1. Power on the device
2. If no WiFi is configured, the device automatically enters setup mode
3. The device creates a WiFi network named "SpotPrice"
4. Scan the QR code on screen or connect manually (password shown on display)
5. A setup page will open automatically in your browser (if not scan the new QR code on the screen)
6. Select your home WiFi network and enter the password
7. The device saves credentials and reboots to connect

**Option B: Edit settings.toml**

Edit `settings.toml` on the CIRCUITPY drive directly:

```toml
CIRCUITPY_WIFI_SSID = "YourNetworkName"
CIRCUITPY_WIFI_PASSWORD = "YourPassword"
```

This method is useful when:
- You have USB access to the device
- You want to pre-configure before deployment
- You need to change networks without the captive portal

You can also start from the provided example:

```bash
cp settings.toml.example settings.toml
```

## Usage

### Button Controls

| Button | Action |
|--------|--------|
| D0 | Cycle through views: Price → 8H Graph → 24H Graph |
| D0 (held during boot) | Enable USB drive for development |

### Display Modes

**Price View (Mode 1)**

Shows the current electricity price in cents per kWh. The background color indicates the price level:

| Color | Price Range |
|-------|-------------|
| Blue | Negative (you get paid!) |
| Green | Below 1 c/kWh |
| Light Green | 1-3 c/kWh |
| Light green → Yellow | 3-8 c/kWh (gradient) |
| Yellow → Red | 8-13 c/kWh (gradient) |
| Red | Above 13 c/kWh |

**8-Hour Forecast (Mode 2)**

Shows a smooth curve graph of the next 8 hours of prices using 15-minute data points (32 slots). Ideal for planning immediate electricity usage.

**24-Hour Forecast (Mode 3)**

Shows a smooth curve graph of the next 24 hours of prices (96 slots). Great for seeing the full day's pricing pattern.

Both graph views are color-coded:
- Green: Below 3 c/kWh
- Yellow: 3-8 c/kWh  
- Red: Above 8 c/kWh

The filled area under the curve uses darker shades of the same colors. A white marker shows the current price position.

## Configuration

Edit the constants in `spotprice/config.py` to customize behavior:

```python
# Fetch schedule, (hour, minute) in Finnish local time (DST handled)
PUBLISH_LOCAL = (14, 5)      # Daily fetch, plus a random 0-10 min per device
FAST_UNTIL_LOCAL = (15, 30)  # If tomorrow is missing, retry every 15 min until here...
GIVE_UP_LOCAL = (22, 0)      # ...then every 45 min until here
RETRY_INTERVAL = 30          # Failed request: retry after 30 s, doubling...
RETRY_MAX = 15 * 60          # ...up to 15 minutes

# Power saving
DISPLAY_BRIGHTNESS = 0.5  # 0.0-1.0 (lower = less power, 0.3 recommended for battery)

# Forecast settings
GRAPH_SLOTS_8H = 32       # Number of 15-min slots for 8-hour view
GRAPH_SLOTS_24H = 96      # Number of 15-min slots for 24-hour view
GRAPH_PAST_8H = 2         # Slots shown before "now" on each graph
GRAPH_PAST_24H = 4

# Price thresholds (cents/kWh)
PRICE_LOW = 1.0           # Below this = bright green
PRICE_MED = 3.0           # Below this = light green
PRICE_HIGH = 8.0          # Above this = yellow in graph
PRICE_MAX = 13.0          # Above this = red background
```

### Power Saving

The device implements several power-saving strategies for battery operation:

1. **WiFi disabled between fetches** - Radio is only enabled during API calls (a few seconds, usually once a day)
2. **Reduced display brightness** - Default 50%, lower for longer battery life
3. **Minimal redraws** - The screen only redraws when a new 15-minute slot starts or a button is pressed

For maximum battery life, set `DISPLAY_BRIGHTNESS = 0.3`.

## API

This project uses the [Porssisahko API](https://porssisahko.net/) for Finnish electricity spot prices. The API is free and does not require authentication.

**Endpoint:** `https://api.porssisahko.net/v2/latest-prices.json`

**Caching Strategy:**
- The API returns 48 hours of 15-minute price slots (~192 entries)
- Nord Pool publishes tomorrow's prices around 14:00 Finnish time, and porssisahko.net has them "from 14:00"
- The device fetches at boot, then once a day at about 14:05-14:15 (a random offset per device avoids everyone hitting the API at the same second); the clock is re-synced via NTP on each fetch
- If tomorrow's prices aren't there yet (Nord Pool delays happen), it retries every 15 min until 15:30, then every 45 min until 22:00. Today's prices last until 01:00, after which it retries every 15 min
- WiFi is disabled between fetches to save power
- Prices are cached in memory and used for display updates
- The display updates at each 15-minute slot boundary; graph hour labels are shown in Finnish local time

## Project Structure

```
esp32-s3/
    boot.py           # Filesystem config (hold D0 during boot for USB access)
    main.py           # Main application entry point
    settings.toml     # WiFi credentials (auto-generated)
    font.pcf          # UI font
    price.pcf         # Large price font
    spotprice/        # Application modules
        __init__.py   # Package exports
        config.py     # Configuration constants
        display.py    # Display rendering (price view, graph)
        fonts.py      # Shared font loading
        prices.py     # Price parsing and Finnish local time
        wifi_portal.py # Captive portal for WiFi setup
    lib/              # CircuitPython libraries
    images/           # Documentation images
    tools/
        make_font.py  # Render TTF/OTF to crisp bitmap fonts at exact sizes
        strip_font.py # Shrink a BDF font to ASCII and convert to PCF
        fonts/        # League Spartan source font + license
```

### Fonts

The display uses fonts rendered from [League Spartan](https://github.com/theleagueof/league-spartan) (SIL Open Font License, source in `tools/fonts/`):

| File | Size | Used for |
|------|------|----------|
| `font.pcf` | 22 px, ASCII | Titles, labels, graph axes |
| `price.aa` | 96 px, digits only, anti-aliased | The big current price |
| `price.pcf` | 96 px, digits only | Fallback for the price if `price.aa` is missing |

Bitmap fonts can only be enlarged by whole-pixel multiples, which makes scaled-up text blocky, so the price gets its own natively rendered font. CircuitPython bitmap fonts are also 1-bit (no smooth edges), so the price digits additionally ship as `price.aa`: greyscale glyphs with 4 shades, drawn by `spotprice/aatext.py` with the edge shades blended into the current background colour.

To regenerate or try another typeface (needs `pip install freetype-py` and `bdftopcf`):

```bash
python3 tools/make_font.py "tools/fonts/LeagueSpartan[wght].ttf" 22 font.pcf
python3 tools/make_font.py "tools/fonts/LeagueSpartan[wght].ttf" 96 price.pcf --chars "0123456789.-"
python3 tools/make_font.py "tools/fonts/LeagueSpartan[wght].ttf" 96 price.aa --chars "0123456789.-"
```

`--levels` sets the number of shades in `price.aa` (default 4; higher is smoother). If neither price font is present, the price falls back to the small font scaled up.

## Troubleshooting

### "Filesystem may be read-only" during setup

The `boot.py` file configures the filesystem to be writable by CircuitPython. Make sure you have copied `boot.py` to the device and rebooted.

### USB drive not writable

By default, the device filesystem is writable by CircuitPython code (for saving WiFi credentials), which means USB is read-only. To edit files from your computer:

**Option 1: Hold D0 during boot**
Hold the D0 button while pressing reset or plugging in. This keeps USB drive writable for development.

**Option 2: Via REPL**
1. Open a serial console
2. Press Ctrl+C to enter REPL
3. Run: `import os; os.rename("boot.py", "boot.py.bak")`
4. Reset the device --> USB drive will be writable

### WiFi connection fails

1. Verify your SSID and password are correct
2. Ensure your router is using 2.4GHz (ESP32 does not support 5GHz)
3. Try moving closer to your router
4. Delete credentials from `settings.toml` to re-enter setup mode

### Display shows "Time error"

NTP sync failed. Check your internet connection. The device will retry on the next fetch cycle.

### Prices not updating

The API may be temporarily unavailable. The device retries after 30 seconds, backing off up to every 15 minutes, and keeps showing cached prices meanwhile.

## Development

### Serial Console

Connect via USB and open a serial terminal at 115200 baud to see debug output.

On macOS/Linux:
```bash
screen /dev/tty.usbmodem* 115200
```

### Development Mode

Hold D0 during boot to enable USB drive write access (development mode). In this mode, CircuitPython cannot save WiFi credentials, but you can edit all files from your computer.

## License

This project is licensed under **CC BY-NC 4.0** (Creative Commons Attribution-NonCommercial 4.0 International).

You are free to share and adapt this work for non-commercial purposes with attribution. Commercial use is prohibited.

See [LICENSE](LICENSE) file for details.

## Author

Sam Z.

## Acknowledgments

- [Adafruit](https://www.adafruit.com/) for CircuitPython and the ESP32-S3 TFT Feather
- [Porssisahko](https://porssisahko.net/) for the electricity price API
