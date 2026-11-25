"""
WiFi setup portal with captive portal and QR code display.
"""

import time
import os
import random
import wifi
import socketpool
import displayio
import microcontroller

from .config import BLACK, WHITE, ACCENT, GRAY, AP_SSID, AP_IP

from .fonts import FONT, HAS_DISPLAY_TEXT, label

try:
    import adafruit_miniqr

    HAS_QR = True
except ImportError:
    HAS_QR = False


def generate_password(length=8):
    """Generate a random password using unambiguous characters."""
    charset = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "".join(random.choice(charset) for _ in range(length))


def needs_wifi_setup():
    """Check if WiFi credentials are configured."""
    try:
        ssid = os.getenv("CIRCUITPY_WIFI_SSID")
    except ValueError as e:  # malformed settings.toml: let the portal fix it
        print(f"settings.toml error: {e}")
        return True
    return not ssid or ssid == "YOUR_WIFI_SSID"


def scan_networks():
    """Scan for available WiFi networks, sorted by signal strength."""
    networks = []
    seen = set()
    try:
        for net in wifi.radio.start_scanning_networks():
            if net.ssid and net.ssid not in seen:
                seen.add(net.ssid)
                networks.append((net.ssid, net.rssi))
        networks.sort(key=lambda x: x[1], reverse=True)
    except Exception as e:
        print(f"WiFi scan error: {e}")
    finally:
        # Always stop, or start_ap() can fail with "already scanning"
        try:
            wifi.radio.stop_scanning_networks()
        except Exception:
            pass
    return networks


def make_qr_bitmap(data, scale=2, border=2):
    """Generate a QR code bitmap with a white quiet zone of `border` modules.

    Phone scanners need light space around the code; without it the code
    blends into the black background and often won't scan.
    """
    if not HAS_QR:
        return None, None

    qr = adafruit_miniqr.QRCode(qr_type=3)
    qr.add_data(data.encode("utf-8"))
    qr.make()

    matrix = qr.matrix
    size = matrix.width
    full = (size + 2 * border) * scale
    bitmap = displayio.Bitmap(full, full, 2)  # starts all 0 = white
    palette = displayio.Palette(2)
    palette[0] = WHITE
    palette[1] = BLACK

    off = border * scale
    for y in range(size):
        for x in range(size):
            if matrix[x, y]:
                px, py = off + x * scale, off + y * scale
                for sy in range(scale):
                    for sx in range(scale):
                        bitmap[px + sx, py + sy] = 1

    return bitmap, palette


def url_decode(encoded_string):
    """Decode a URL-encoded (form) string.

    %XX escapes are UTF-8 bytes, so collect bytes and decode once at the end;
    decoding each byte separately turns e.g. "ä" (%C3%A4) into "Ã¤".
    """
    out = bytearray()
    i = 0
    n = len(encoded_string)
    while i < n:
        char = encoded_string[i]
        if char == "%" and i + 3 <= n:
            try:
                out.append(int(encoded_string[i + 1 : i + 3], 16))
                i += 3
                continue
            except ValueError:
                pass
        if char == "+":
            out.append(0x20)
        else:
            out.extend(char.encode("utf-8"))
        i += 1
    try:
        return bytes(out).decode("utf-8")
    except UnicodeError:
        return encoded_string


def parse_form_data(body):
    """Parse URL-encoded form data into a dictionary."""
    params = {}
    for pair in body.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            params[url_decode(key)] = url_decode(value)
    return params


def html_escape(text):
    """Escape text for safe inclusion in HTML (SSIDs are attacker-controlled)."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def toml_escape(text):
    """Escape a value for a TOML basic (double-quoted) string."""
    out = []
    for ch in text:
        if ch == "\x00":
            continue  # NUL can't appear in settings.toml
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ord(ch) < 0x20 or ch == "\x7f":
            out.append("\\u%04x" % ord(ch))
        else:
            out.append(ch)
    return "".join(out)


def build_setup_html(networks=None):
    """Generate the WiFi setup page HTML."""
    network_options = ""
    if networks:
        for ssid, rssi in networks:
            safe = html_escape(ssid)
            network_options += f'<option value="{safe}">{safe}</option>\n'

    network_select = ""
    if network_options:
        network_select = f"""
        <select id="network-select" onchange="document.getElementById('ssid').value=this.value">
            <option value="">-- Select a network --</option>
            {network_options}
        </select>"""

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>SpotPrice WiFi Setup</title>
    <style>
        body {{ font-family: -apple-system, sans-serif; max-width: 400px; margin: 40px auto; padding: 20px; background: #1a1a2e; color: #eee; }}
        h1 {{ color: #00ff88; text-align: center; }}
        input, button, select {{ width: 100%; padding: 15px; margin: 10px 0; border: none; border-radius: 8px; font-size: 16px; box-sizing: border-box; }}
        input, select {{ background: #16213e; color: #fff; border: 1px solid #0f3460; }}
        button {{ background: #00ff88; color: #1a1a2e; font-weight: bold; cursor: pointer; }}
        button:hover {{ background: #00cc6a; }}
        .info {{ background: #16213e; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .divider {{ text-align: center; color: #888; margin: 5px 0; }}
    </style>
</head>
<body>
    <h1>SpotPrice Setup</h1>
    <div class="info">
        <p>Connect this device to your WiFi network to display real-time electricity prices.</p>
    </div>
    <form method="POST" action="/save">
        {network_select}
        <p class="divider">or enter manually:</p>
        <input type="text" id="ssid" name="ssid" placeholder="WiFi Network Name (SSID)" required>
        <input type="password" name="password" placeholder="WiFi Password (blank for open network)">
        <button type="submit">Save and Connect</button>
    </form>
</body>
</html>"""


SUCCESS_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Setup Complete</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 400px; margin: 40px auto; padding: 20px; background: #1a1a2e; color: #eee; }
        .success { background: #00ff88; color: #1a1a2e; padding: 30px; border-radius: 8px; text-align: center; }
        h1 { margin: 0 0 10px 0; }
    </style>
</head>
<body>
    <div class="success">
        <h1>Setup Complete</h1>
        <p>Device is rebooting and will connect to your WiFi network.</p>
        <p>You can close this page.</p>
    </div>
</body>
</html>"""


ERROR_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Setup Error</title>
    <style>
        body { font-family: -apple-system, sans-serif; max-width: 400px; margin: 40px auto; padding: 20px; background: #1a1a2e; color: #eee; }
        .error { background: #ff4444; color: #fff; padding: 30px; border-radius: 8px; text-align: center; }
        h1 { margin: 0 0 10px 0; }
    </style>
</head>
<body>
    <div class="error">
        <h1>Setup Error</h1>
        <p>Could not save WiFi credentials. The filesystem may be read-only.</p>
        <p>Hold D0 button during boot to enable USB drive, then edit settings.toml manually.</p>
    </div>
</body>
</html>"""


# Captive portal detection paths
CAPTIVE_PORTAL_PATHS = {
    "/generate_204",
    "/gen_204",
    "/hotspot-detect.html",
    "/library/test/success.html",
    "/ncsi.txt",
    "/connecttest.txt",
    "/redirect",
    "/success.txt",
    "/canonical.html",
}


def _settings_key(line):
    """Return the key of a `KEY = value` line in settings.toml, else None."""
    stripped = line.strip()
    if not stripped or stripped[0] in "#[":
        return None
    key, sep, _ = stripped.partition("=")
    return key.strip() if sep else None


def update_settings(text, values):
    """Return settings.toml `text` with `values` (key -> str) set.

    Existing top-level keys are replaced in place (duplicates dropped);
    missing keys are added at the top. CircuitPython's os.getenv() stops
    reading at the first [table] header, so keys after one are invisible and
    left alone. All other lines and comments are kept.
    """
    out = []
    done = set()
    in_table = False
    for line in text.splitlines():
        if line.strip().startswith("["):
            in_table = True
        key = None if in_table else _settings_key(line)
        if key in values:
            if key not in done:
                out.append(f'{key} = "{toml_escape(values[key])}"')
                done.add(key)
            continue
        out.append(line)
    missing = [f'{k} = "{toml_escape(v)}"' for k, v in values.items() if k not in done]
    return "\n".join(missing + out).rstrip("\n") + "\n"


SETTINGS_PATH = "/settings.toml"


def save_credentials(ssid, password):
    """Save WiFi creds to settings.toml, keeping any other settings.

    Writes a temp file and renames it over settings.toml, so a power cut
    mid-write can't leave a truncated file. If a previous save was cut off
    after the temp file was written, its contents are recovered (boot.py
    also restores it). Returns True on success.
    """
    print(f"Saving: {ssid}")
    tmp = SETTINGS_PATH + ".tmp"
    try:
        text = ""
        for path in (SETTINGS_PATH, tmp):
            try:
                with open(path) as f:
                    text = f.read()
                break
            except OSError:
                pass
        text = update_settings(
            text,
            {"CIRCUITPY_WIFI_SSID": ssid, "CIRCUITPY_WIFI_PASSWORD": password},
        )
        with open(tmp, "w") as f:
            f.write(text)
        os.rename(tmp, SETTINGS_PATH)  # FAT VFS replaces an existing target
        print("Saved!")
        return True
    except Exception as e:
        print(f"Save failed: {e}")
        return False


def _show_qr_screen(group, disp, qr_data, lines):
    """Replace everything but the background with a QR code and text lines."""
    while len(group) > 1:
        group.pop()

    # 3 px modules: (29 + 2*2 border) * 3 = 99 px, leaving 141 px for text.
    # At scale 4 (132 px) the 8-char password ran into the QR code.
    qr_bmp, qr_pal = make_qr_bitmap(qr_data, scale=3)
    if not qr_bmp or not HAS_DISPLAY_TEXT:
        return

    qr_y = max(0, (disp.height - qr_bmp.height) // 2)
    group.append(displayio.TileGrid(qr_bmp, pixel_shader=qr_pal, x=0, y=qr_y))

    rx = (qr_bmp.width + disp.width) // 2  # center text in the space right of the QR
    for text, y, color in lines:
        lbl = label.Label(FONT, text=text, color=color, scale=1)
        lbl.anchor_point = (0.5, 0.0)
        lbl.anchored_position = (rx, y)
        group.append(lbl)


def _read_request(client):
    """Read an HTTP request, including the full body per Content-Length.

    Phones often send headers and the POST body in separate TCP segments,
    so a single recv() can miss the form data.
    """
    buf = bytearray(1024)
    data = b""
    while b"\r\n\r\n" not in data and len(data) < 4096:
        n = client.recv_into(buf)
        if not n:
            break
        data += bytes(buf[:n])

    head, _, body = data.partition(b"\r\n\r\n")
    length = 0
    for line in head.split(b"\r\n")[1:]:
        if line.lower().startswith(b"content-length:"):
            try:
                length = int(line.split(b":", 1)[1].strip())
            except ValueError:
                pass
    length = min(length, 4096)
    while len(body) < length:
        n = client.recv_into(buf)
        if not n:
            break
        body += bytes(buf[:n])

    return head.decode("utf-8"), body.decode("utf-8")


def _send_html(client, html, status="200 OK"):
    payload = html.encode("utf-8")
    client.sendall(
        f"HTTP/1.1 {status}\r\nContent-Type: text/html; charset=utf-8\r\n"
        f"Content-Length: {len(payload)}\r\nConnection: close\r\n\r\n".encode()
    )
    client.sendall(payload)


def run_setup_portal(disp, timeout=None):
    """Run the WiFi captive portal for configuration.

    If `timeout` (seconds) is given and nobody connects to the access point
    in that time, reboot to retry the saved credentials. Used when WiFi
    failed at boot, e.g. because the router was still starting up.
    """
    started = time.monotonic()
    ap_password = generate_password()

    # Set up display
    group = displayio.Group()
    disp.root_group = group

    # Black background
    bg = displayio.Bitmap(disp.width, disp.height, 1)
    bg_pal = displayio.Palette(1)
    bg_pal[0] = BLACK
    group.append(displayio.TileGrid(bg, pixel_shader=bg_pal))

    # Show QR code for joining the setup access point
    _show_qr_screen(
        group,
        disp,
        f"WIFI:T:WPA;S:{AP_SSID};P:{ap_password};;",
        (
            ("WiFi Setup", 5, ACCENT),
            ("Scan QR", 28, WHITE),
            ("to connect", 46, WHITE),
            ("or", 68, GRAY),
            (AP_SSID, 88, ACCENT),
            (ap_password, 106, WHITE),
        ),
    )

    # Scan networks and start access point
    networks = scan_networks()
    setup_html = build_setup_html(networks)

    try:
        wifi.radio.stop_station()
        wifi.radio.start_ap(ssid=AP_SSID, password=ap_password)
    except Exception as e:
        print(f"Could not start access point: {e}")
        time.sleep(5)
        microcontroller.reset()
    print(f"AP: {AP_SSID} @ {wifi.radio.ipv4_address_ap}")

    # Start HTTP server
    pool = socketpool.SocketPool(wifi.radio)
    sock = pool.socket(pool.AF_INET, pool.SOCK_STREAM)
    sock.setsockopt(pool.SOL_SOCKET, pool.SO_REUSEADDR, 1)
    sock.bind(("0.0.0.0", 80))
    sock.listen(1)
    sock.setblocking(False)

    client_seen = False

    def show_portal_qr():
        """Switch display to show portal URL QR after a client connects."""
        nonlocal client_seen
        if client_seen:
            return
        client_seen = True
        _show_qr_screen(
            group,
            disp,
            f"http://{AP_IP}/setup",
            (
                ("Connected!", 5, ACCENT),
                ("Scan QR", 28, WHITE),
                ("to open", 46, WHITE),
                ("setup page", 64, WHITE),
                ("-- or --", 86, GRAY),
                (AP_IP, 106, ACCENT),
            ),
        )

    # Server loop
    while True:
        if timeout and not client_seen and time.monotonic() - started > timeout:
            print("Setup portal timed out, rebooting to retry WiFi")
            microcontroller.reset()

        if not client_seen:
            try:
                if wifi.radio.stations_ap:
                    show_portal_qr()
            except Exception:
                pass

        try:
            client, _ = sock.accept()
        except OSError as e:
            if e.errno != 11:  # EAGAIN: no pending connection
                print(f"Server error: {e}")
            time.sleep(0.1)
            continue

        reboot = False
        try:
            client.setblocking(True)
            client.settimeout(5.0)
            show_portal_qr()

            head, body = _read_request(client)
            parts = head.split("\r\n", 1)[0].split(" ")
            method = parts[0] if parts else ""
            path = parts[1].split("?", 1)[0] if len(parts) > 1 else "/"

            if path in CAPTIVE_PORTAL_PATHS or path == "/":
                client.sendall(
                    f"HTTP/1.1 302 Found\r\nLocation: http://{AP_IP}/setup\r\n"
                    "Content-Length: 0\r\nConnection: close\r\n\r\n".encode()
                )
            elif method == "POST" and path == "/save":
                params = parse_form_data(body)
                ssid = params.get("ssid", "").strip()
                if ssid:
                    ok = save_credentials(ssid, params.get("password", ""))
                    _send_html(client, SUCCESS_HTML if ok else ERROR_HTML)
                    reboot = ok
                else:
                    _send_html(client, setup_html)
            else:
                _send_html(client, setup_html)
        except Exception as e:
            print(f"Request error: {e}")
        finally:
            client.close()

        if reboot:
            time.sleep(1)
            microcontroller.reset()
