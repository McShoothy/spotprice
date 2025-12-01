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

# Optional dependencies
try:
    from adafruit_display_text import label
    import terminalio
    try:
        from adafruit_bitmap_font import bitmap_font
        FONT = bitmap_font.load_font("/font.bdf")
    except Exception:
        FONT = terminalio.FONT
    HAS_DISPLAY_TEXT = True
except ImportError:
    HAS_DISPLAY_TEXT = False
    FONT = None

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
    ssid = os.getenv("CIRCUITPY_WIFI_SSID")
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
        wifi.radio.stop_scanning_networks()
        networks.sort(key=lambda x: x[1], reverse=True)
    except Exception as e:
        print(f"WiFi scan error: {e}")
    return networks


def make_qr_bitmap(data, scale=2):
    """Generate a QR code bitmap from the given data string."""
    if not HAS_QR:
        return None, None
    
    qr = adafruit_miniqr.QRCode(qr_type=3)
    qr.add_data(data.encode("utf-8"))
    qr.make()
    
    matrix = qr.matrix
    size = matrix.width
    bitmap = displayio.Bitmap(size * scale, size * scale, 2)
    palette = displayio.Palette(2)
    palette[0] = WHITE
    palette[1] = BLACK
    
    for y in range(size):
        for x in range(size):
            color = 1 if matrix[x, y] else 0
            for sy in range(scale):
                for sx in range(scale):
                    bitmap[x * scale + sx, y * scale + sy] = color
    
    return bitmap, palette


def url_decode(encoded_string):
    """Decode a URL-encoded string."""
    result = []
    i = 0
    while i < len(encoded_string):
        char = encoded_string[i]
        if char == "%" and i + 2 < len(encoded_string):
            try:
                result.append(chr(int(encoded_string[i + 1:i + 3], 16)))
                i += 3
                continue
            except ValueError:
                pass
        elif char == "+":
            result.append(" ")
            i += 1
            continue
        result.append(char)
        i += 1
    return "".join(result)


def parse_form_data(body):
    """Parse URL-encoded form data into a dictionary."""
    params = {}
    for pair in body.split("&"):
        if "=" in pair:
            key, value = pair.split("=", 1)
            params[url_decode(key)] = url_decode(value)
    return params


def build_setup_html(networks=None):
    """Generate the WiFi setup page HTML."""
    network_options = ""
    if networks:
        for ssid, rssi in networks:
            network_options += f'<option value="{ssid}">{ssid}</option>\n'
    
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
        <input type="password" name="password" placeholder="WiFi Password" required>
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
    "/generate_204", "/gen_204",
    "/hotspot-detect.html",
    "/library/test/success.html",
    "/ncsi.txt", "/connecttest.txt",
    "/redirect", "/success.txt",
    "/canonical.html",
}


def save_credentials(ssid, password):
    """Write WiFi creds to settings.toml. Returns True on success."""
    import storage
    
    content = f'CIRCUITPY_WIFI_SSID = "{ssid}"\nCIRCUITPY_WIFI_PASSWORD = "{password}"\n'
    print(f"Saving: {ssid}")
    
    try:
        with open("/settings.toml", "w") as f:
            f.write(content)
        print("Saved!")
        return True
    except Exception as e:
        print(f"Save failed: {e}")
        return False


def run_setup_portal(disp):
    """Run the WiFi captive portal for configuration."""
    ap_password = generate_password()
    
    # Set up display
    group = displayio.Group()
    disp.root_group = group
    
    # Black background
    bg = displayio.Bitmap(disp.width, disp.height, 1)
    bg_pal = displayio.Palette(1)
    bg_pal[0] = BLACK
    group.append(displayio.TileGrid(bg, pixel_shader=bg_pal))
    
    # Show QR code for WiFi connection
    wifi_qr = f"WIFI:T:WPA;S:{AP_SSID};P:{ap_password};;"
    qr_bmp, qr_pal = make_qr_bitmap(wifi_qr, scale=4)
    
    if qr_bmp and HAS_DISPLAY_TEXT:
        qr_y = (disp.height - qr_bmp.height) // 2
        group.append(displayio.TileGrid(qr_bmp, pixel_shader=qr_pal, x=10, y=qr_y))
        
        rx = disp.width - 60
        def add_lbl(txt, y, color, scale=1):
            lbl = label.Label(FONT, text=txt, color=color, scale=scale)
            lbl.anchor_point = (0.5, 0.0)
            lbl.anchored_position = (rx, y)
            group.append(lbl)
        
        add_lbl("WiFi Setup", 5, ACCENT, 1)
        add_lbl("Scan QR", 28, WHITE)
        add_lbl("to connect", 46, WHITE)
        add_lbl("or", 68, GRAY)
        add_lbl(AP_SSID, 88, ACCENT)
        add_lbl(ap_password, 106, WHITE)

    # Scan networks and start access point
    networks = scan_networks()
    setup_html = build_setup_html(networks)
    
    wifi.radio.stop_station()
    wifi.radio.start_ap(ssid=AP_SSID, password=ap_password)
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
        """Switch display to show portal URL QR after client connects."""
        nonlocal client_seen
        if client_seen:
            return
        client_seen = True
        
        while len(group) > 1:
            group.pop()
        
        url_qr = f"http://{AP_IP}/setup"
        qr2, pal2 = make_qr_bitmap(url_qr, scale=4)
        if qr2 and HAS_DISPLAY_TEXT:
            qr_y = (disp.height - qr2.height) // 2
            group.append(displayio.TileGrid(qr2, pixel_shader=pal2, x=10, y=qr_y))
            
            rx = disp.width - 60
            def add_lbl(txt, y, color, scale=1):
                lbl = label.Label(FONT, text=txt, color=color, scale=scale)
                lbl.anchor_point = (0.5, 0.0)
                lbl.anchored_position = (rx, y)
                group.append(lbl)
            
            add_lbl("Connected!", 5, ACCENT, 1)
            add_lbl("Scan QR", 28, WHITE)
            add_lbl("to open", 46, WHITE)
            add_lbl("setup page", 64, WHITE)
            add_lbl("-- or --", 86, GRAY)
            add_lbl(AP_IP, 106, ACCENT)
    
    # Server loop
    while True:
        if not client_seen:
            try:
                if wifi.radio.stations_ap:
                    show_portal_qr()
            except:
                pass
        
        try:
            client, addr = sock.accept()
            client.setblocking(True)
            client.settimeout(5.0)
            show_portal_qr()
            
            buf = bytearray(4096)
            try:
                n = client.recv_into(buf)
                req = buf[:n].decode('utf-8')
                
                first_line = req.split('\r\n')[0]
                parts = first_line.split(' ')
                if len(parts) >= 2:
                    method, path = parts[0], parts[1]
                    
                    if path in CAPTIVE_PORTAL_PATHS or path == "/":
                        resp = f"HTTP/1.1 302 Found\r\nLocation: http://{AP_IP}/setup\r\nContent-Length: 0\r\n\r\n"
                        client.send(resp.encode())
                    
                    elif path == "/setup":
                        resp = f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(setup_html)}\r\n\r\n{setup_html}"
                        client.sendall(resp.encode())
                    
                    elif method == "POST" and path == "/save":
                        body_start = req.find('\r\n\r\n')
                        if body_start > 0:
                            body = req[body_start + 4:]
                            params = parse_form_data(body)
                            ssid = params.get('ssid', '')
                            pw = params.get('password', '')
                            
                            if ssid:
                                ok = save_credentials(ssid, pw)
                                html = SUCCESS_HTML if ok else ERROR_HTML
                                resp = f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(html)}\r\n\r\n{html}"
                                client.sendall(resp.encode())
                                client.close()
                                if ok:
                                    time.sleep(1)
                                    microcontroller.reset()
                                continue
                    else:
                        resp = f"HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nContent-Length: {len(setup_html)}\r\n\r\n{setup_html}"
                        client.sendall(resp.encode())
                        
            except Exception as e:
                print(f"Request error: {e}")
            finally:
                client.close()
                
        except OSError as e:
            if e.errno != 11:
                print(f"Server error: {e}")
        
        time.sleep(0.1)
