"""เก็บข้อมูลจริงจากบอร์ดพร้อม "ติดป้าย" (label) เพื่อนำไปฝึก AI

ตัวอย่าง:
    python collect.py --label normal --seconds 120
    (ติดเหรียญ/เทปที่ใบพัด 1 ข้าง)  python collect.py --label unbalanced --seconds 120
    (ปิดพัดลม)                     python collect.py --label off --seconds 60

ผลลัพธ์จะถูกต่อท้ายใน data/<label>.csv
"""
import argparse
import csv
import json
import os
import time

from common import FEATURES, LABELS, TOPIC_TELEMETRY, config, mqtt_client, path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--label", required=True, choices=LABELS)
    ap.add_argument("--seconds", type=int, default=120)
    ap.add_argument("--device", default="+", help="ชื่อบอร์ด หรือ + เพื่อรับทุกบอร์ด")
    ap.add_argument("--host", default=config.MQTT_HOST)
    a = ap.parse_args()

    os.makedirs(path("data"), exist_ok=True)
    fn = path(f"data/{a.label}.csv")
    new_file = not os.path.exists(fn)
    f = open(fn, "a", newline="")
    w = csv.DictWriter(f, fieldnames=FEATURES + ["hum", "label"])
    if new_file:
        w.writeheader()
    count = 0

    def on_message(cli, userdata, msg):
        nonlocal count
        try:
            d = json.loads(msg.payload)
            w.writerow({k: d[k] for k in FEATURES + ["hum"]} | {"label": a.label})
            count += 1
            print(f"\r[{a.label}] เก็บแล้ว {count} แถว   rms={d['rms']:.3f}", end="")
        except (ValueError, KeyError) as e:
            print("ข้ามข้อความที่รูปแบบไม่ถูกต้อง:", e)

    cli = mqtt_client("collector")
    cli.on_message = on_message
    cli.on_connect = lambda c, u, fl, rc, pr: c.subscribe(TOPIC_TELEMETRY.format(device=a.device))
    cli.connect(a.host, config.MQTT_PORT, 30)
    cli.loop_start()
    time.sleep(a.seconds)
    cli.loop_stop()
    f.close()
    print(f"\nบันทึก {count} แถวลง {fn}")


if __name__ == "__main__":
    main()
