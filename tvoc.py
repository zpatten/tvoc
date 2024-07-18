#!/usr/bin/env python3

import busio
import board
import os
import sys
import time
import json

import adafruit_sgp30
import adafruit_sht4x

import paho.mqtt.client as mqtt

from humanize.time import precisedelta

STARTED_AT = time.time()

def next_interval(interval):
  t = time.time()
  return (t + (interval - (t % interval)))

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=os.getenv("MQTT_CLIENT_ID"))
client.username_pw_set(os.getenv("MQTT_USERNAME"), os.getenv("MQTT_PASSWORD"))
client.connect(os.getenv("MQTT_HOSTNAME"), int(os.getenv("MQTT_PORT")))
client.loop_start()

MQTT_INTERVAL = 60
mqtt_at = next_interval(MQTT_INTERVAL)

def mqtt_publish(topic, data):
  payload = json.dumps(data)
  print("MQTT Publish: %s: %s" % (topic, data))
  client.publish(topic, payload, retain=True)

BASELINE_FILENAME = os.path.expanduser("/opt/tvoc/baseline.dat")
BASELINE_INTERVAL = 10
CALIBRATION_INTERVAL = (12 * 60 * 60) # 12 Hours

i2c = busio.I2C(board.SCL, board.SDA, frequency=100000)
sgp30 = adafruit_sgp30.Adafruit_SGP30(i2c)

sht = adafruit_sht4x.SHT4x(i2c)
print("Found SHT4x with serial number", hex(sht.serial_number))

sht.mode = adafruit_sht4x.Mode.NOHEAT_HIGHPRECISION
# Can also set the mode to enable heater
# sht.mode = adafruit_sht4x.Mode.LOWHEAT_100MS
print("Current mode is: ", adafruit_sht4x.Mode.string[sht.mode])

last_eCO2 = 0
last_TVOC = 0
baseline_at = time.time()
sgp30_calibrated = False
sgp30_init = True

try:
  f = open(BASELINE_FILENAME, 'r')
  baseline_eCO2, baseline_TVOC = f.read().split(",")
  f.close()
  print("Loading baseline data; SGP30 calibrated")
  sgp30.set_iaq_baseline(int(baseline_eCO2), int(baseline_TVOC))
  sgp30_calibrated = True
  sgp30_init = False
except (FileNotFoundError, ValueError):
  print("No baseline data available; SGP30 not calibrated!")

while True:
  temp_c, relative_humidity = sht.measurements
  temp_f = (temp_c * 9 / 5) + 32

  sgp30.set_iaq_relative_humidity(celsius=temp_c, relative_humidity=relative_humidity)
  eCO2, TVOC = sgp30.iaq_measure()
  baseline_TVOC = sgp30.baseline_TVOC
  baseline_eCO2 = sgp30.baseline_eCO2

  if time.time() - mqtt_at >= MQTT_INTERVAL:
    print(f"TVOC: {TVOC} ppb | eCO2: {eCO2} ppm | T: {temp_c:0.2f} C ({temp_f:0.2f} F) | H: {relative_humidity:0.2f} % | Baseline TVOC:{baseline_TVOC} | Baseline eCO2:{baseline_eCO2}")

    mqtt_at = next_interval(MQTT_INTERVAL)

    data = { "TVOC": TVOC, "eCO2": eCO2, "baseline_TVOC": baseline_TVOC, "baseline_eCO2": baseline_eCO2, "temp_c": temp_c, "relative_humidity": relative_humidity, "started_at": STARTED_AT, "timestamp": time.time() }
    mqtt_publish(os.getenv('MQTT_TOPIC'), data)

  if time.time() - baseline_at >= BASELINE_INTERVAL:
    baseline_at = next_interval(BASELINE_INTERVAL)

    if not sgp30_calibrated and time.time() - STARTED_AT > CALIBRATION_INTERVAL:
      sgp30_calibrated = True
	
    if sgp30_calibrated:
      print("SGP30 Calibrated; saving baseline data")
      f = open(BASELINE_FILENAME, "w")
      baseline_data = "%d,%d" % (baseline_eCO2, baseline_TVOC)
      f.write(baseline_data)
      f.close()
      if sgp30_init:
        sys.exit(0)
    else:
      remaining_calibration_seconds = int(CALIBRATION_INTERVAL - (time.time() - STARTED_AT))
      humanized_remaining_calibration_time = precisedelta(remaining_calibration_seconds, minimum_unit='seconds')
      print(f"SGP30 not calibrated; {humanized_remaining_calibration_time} remaining until calibration complete")

    print(f">>> Baseline Values: TVOC = 0x{baseline_TVOC:x} ({baseline_TVOC}), eCO2 = 0x{baseline_eCO2:x} ({baseline_eCO2})")

  time.sleep(1)

