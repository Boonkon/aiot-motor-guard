# AIoT Motor Guard 🔧📡🤖

สื่อการสอน AIoT: บอร์ด **Cucumber RIS** วัดการสั่นของพัดลม → **MQTT** → **AI** (scikit-learn) ทายว่า ปกติ / ไม่สมดุล / หยุด → แจ้งเตือนผ่าน **Telegram**

📖 **เว็บบทเรียน:** https://Boonkon.github.io/aiot-motor-guard/

## เริ่มเร็ว (ไม่ต้องมีบอร์ด)

```bash
docker compose up -d                 # MQTT broker
cd python
pip install -r requirements.txt
cp config_example.py config.py       # ใส่ TELEGRAM_TOKEN
python train.py                      # ฝึกจาก data_demo/
python gateway.py                    # หน้าต่างที่ 1
python simulator.py --scenario demo  # หน้าต่างที่ 2
python bot.py                        # หน้าต่างที่ 3 แล้วพิมพ์ /start ใน Telegram
```

## โครงสร้าง

| โฟลเดอร์ | เนื้อหา |
|---|---|
| `devices/` | เฟิร์มแวร์ PlatformIO สำหรับ Cucumber (ESP32-S2) |
| `python/` | simulator, collect, train, gateway, Telegram bot |
| `notebooks/` | ฝึกโมเดลบน Google Colab |
| `content/`, `index.qmd` | เว็บบทเรียน (Quarto) — deploy อัตโนมัติด้วย GitHub Actions |

โค้ด: MIT · เนื้อหา: CC BY 4.0
