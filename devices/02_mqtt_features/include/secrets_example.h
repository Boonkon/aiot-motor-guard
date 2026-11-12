// คัดลอกไฟล์นี้เป็น secrets.h แล้วแก้ค่าให้ตรงกับเครือข่ายของคุณ
// secrets.h อยู่ใน .gitignore จะไม่ถูกส่งขึ้น GitHub — ห้ามใส่รหัสผ่านจริงในไฟล์นี้
#pragma once

#define WIFI_SSID     "your-2.4GHz-wifi"
#define WIFI_PASSWORD "your-wifi-password"

// IP ของคอมพิวเตอร์ที่รัน Mosquitto (ดูด้วย ipconfig / ifconfig)
#define MQTT_HOST     "192.168.1.100"
#define MQTT_PORT     1883

// ชื่อเครื่องจักร — ใช้เป็นส่วนหนึ่งของ topic: aiot/<DEVICE_ID>/telemetry
#define DEVICE_ID     "fan01"
