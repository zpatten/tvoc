Simple Python Daemon for sending TVOC sensors readings for a 3D printer to MQTT (Home Assistant in my case).

BOM:
- Adafruit SGP30 (https://www.adafruit.com/product/3709)
- Adafruit SHT45 (https://www.adafruit.com/product/5665)

Install into `/opt/tvoc`.
Copy sample systemd service to `/etc/systemd/system/`.
Copy ENV variable template and modify as appropriate.
