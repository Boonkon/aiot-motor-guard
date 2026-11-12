"""บอร์ดจำลอง — ใช้แทน Cucumber เมื่อยังไม่มีบอร์ด หรือใช้ทดสอบระบบ

ส่ง JSON รูปแบบเดียวกับ devices/02_mqtt_features ทุก 1 วินาที

ตัวอย่าง:
    python simulator.py --state normal
    python simulator.py --scenario demo        # ปกติ 40 วิ -> ไม่สมดุล 20 วิ -> หยุด 15 วิ วนไป
    python simulator.py --dump data_demo 300   # สร้างชุดข้อมูลสังเคราะห์ (ไม่ต้องมี broker)
"""
import argparse
import csv
import json
import math
import os
import random
import time

from common import FEATURES, LABELS, TOPIC_TELEMETRY, config, mqtt_client

# ค่ากลาง (mean, sd) ของแต่ละสถานะ — ประมาณจากพัดลมตั้งโต๊ะความเร็ว ~1200 rpm (~20 Hz)
PROFILES = {
    "normal":     {"rms": (0.032, 0.010), "crest": (2.6, 0.35), "f_dom": (20.0, 0.8)},
    "unbalanced": {"rms": (0.075, 0.022), "crest": (1.9, 0.35), "f_dom": (20.0, 0.8)},
    "off":        {"rms": (0.004, 0.001), "crest": (3.2, 0.4), "f_dom": None},
}


def make_sample(state: str, t_motor: float, device: str = "fan01", seq: int = 0) -> dict:
    p = PROFILES[state]
    rms = max(1e-4, random.gauss(*p["rms"]))
    crest = max(1.1, random.gauss(*p["crest"]))
    # แรงไม่สมดุลหมุนในระนาบใบพัด จึงเด่นในแกน x, y มากกว่า z
    wx, wy, wz = (1.0, 1.0, 0.4) if state == "unbalanced" else (0.8, 0.8, 0.7)
    norm = math.sqrt((wx**2 + wy**2 + wz**2) / 3)
    jitter = lambda: random.uniform(0.85, 1.15)
    f_dom = random.uniform(1, 99) if p["f_dom"] is None else random.gauss(*p["f_dom"])
    return {
        "device": device,
        "seq": seq,
        "rms_x": rms * wx / norm * jitter(),
        "rms_y": rms * wy / norm * jitter(),
        "rms_z": rms * wz / norm * jitter(),
        "rms": rms,
        "p2p": rms * crest * 2 * random.uniform(0.9, 1.1),
        "crest": crest,
        "f_dom": round(f_dom / 1.0) * 1.0,   # ความละเอียดความถี่ของบอร์ด = 1 Hz
        "temp": round(t_motor + random.gauss(0, 0.1), 2),
        "hum": round(random.gauss(60, 1.5), 1),
    }


def motor_temp(prev: float, state: str) -> float:
    """อุณหภูมิค่อย ๆ เข้าหาค่าคงตัวของแต่ละสถานะ"""
    target = {"normal": 33.0, "unbalanced": 36.0, "off": 29.0}[state]
    return prev + (target - prev) * 0.02


def scenario_state(t: float) -> str:
    cycle = t % 75
    return "normal" if cycle < 40 else "unbalanced" if cycle < 60 else "off"


def dump(folder: str, n: int):
    os.makedirs(folder, exist_ok=True)
    for state in LABELS:
        temp = 30.0
        fn = os.path.join(folder, f"{state}.csv")
        with open(fn, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FEATURES + ["hum", "label"])
            w.writeheader()
            for i in range(n):
                temp = motor_temp(temp, state)
                s = make_sample(state, temp, seq=i)
                w.writerow({k: s[k] for k in FEATURES + ["hum"]} | {"label": state})
        print(f"เขียน {fn} ({n} แถว)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--state", choices=LABELS, default="normal")
    ap.add_argument("--scenario", choices=["demo"])
    ap.add_argument("--device", default="fan01")
    ap.add_argument("--host", default=config.MQTT_HOST)
    ap.add_argument("--port", type=int, default=config.MQTT_PORT)
    ap.add_argument("--rate", type=float, default=1.0, help="จำนวนข้อความต่อวินาที")
    ap.add_argument("--count", type=int, default=0, help="ส่งกี่ข้อความแล้วหยุด (0 = ไม่หยุด)")
    ap.add_argument("--dump", nargs=2, metavar=("FOLDER", "N"))
    a = ap.parse_args()

    if a.dump:
        dump(a.dump[0], int(a.dump[1]))
        return

    cli = mqtt_client("simulator")
    cli.connect(a.host, a.port, 30)
    cli.loop_start()
    topic = TOPIC_TELEMETRY.format(device=a.device)
    temp, seq, t0 = 30.0, 0, time.time()
    print(f"ส่งข้อมูลจำลองไปที่ {topic}  (Ctrl+C เพื่อหยุด)")
    try:
        while a.count == 0 or seq < a.count:
            state = scenario_state(time.time() - t0) if a.scenario else a.state
            temp = motor_temp(temp, state)
            msg = make_sample(state, temp, a.device, seq)
            cli.publish(topic, json.dumps(msg)).wait_for_publish()
            print(f"[{state:10s}] rms={msg['rms']:.3f} g  f={msg['f_dom']:.0f} Hz  T={msg['temp']:.1f} C")
            seq += 1
            time.sleep(1 / a.rate)
    except KeyboardInterrupt:
        pass
    cli.loop_stop()
    cli.disconnect()


if __name__ == "__main__":
    main()
