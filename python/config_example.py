"""คัดลอกไฟล์นี้เป็น config.py แล้วแก้ค่า
config.py อยู่ใน .gitignore — โทเคน Telegram จะไม่หลุดขึ้น GitHub
"""

MQTT_HOST = "127.0.0.1"     # broker รันบนเครื่องเดียวกัน
MQTT_PORT = 1883

DB_PATH = "data/aiot.db"            # ฐานข้อมูล SQLite ที่ gateway เขียน และ bot อ่าน
MODEL_PATH = "models/motor_model.joblib"

# ขอโทเคนจาก @BotFather ใน Telegram
TELEGRAM_TOKEN = "123456789:PASTE-YOUR-TOKEN-HERE"

# กฎความปลอดภัย (ไม่ใช้ AI) — ตรวจสอบได้ตรงไปตรงมา
TEMP_LIMIT_C = 45.0         # อุณหภูมิเกินนี้แจ้งเตือนทันที
ALERT_CONSECUTIVE = 5       # ต้องผิดปกติติดกันกี่หน้าต่าง (วินาที) จึงแจ้งเตือน
