"""Gateway: ตัวกลางระหว่างบอร์ดกับผู้ใช้
    MQTT (telemetry) -> AI ทำนาย -> SQLite -> MQTT (prediction / alert)

    python gateway.py
"""
import json
import time
from collections import defaultdict

import joblib
import pandas as pd

from common import (LABEL_TH, TOPIC_ALERT, TOPIC_PREDICTION, TOPIC_TELEMETRY,
                    config, db_connect, mqtt_client, path)


class Predictor:
    def __init__(self, model_path: str):
        m = joblib.load(model_path)
        self.clf, self.iso, self.thr, self.features = m["clf"], m["iso"], m["iso_threshold"], m["features"]
        print(f"โหลดโมเดล (ฝึกจาก {m.get('trained_on')}) ฟีเจอร์ = {self.features}")

    def predict(self, d: dict) -> tuple[str, float, float]:
        x = pd.DataFrame([[d[f] for f in self.features]], columns=self.features)
        proba = self.clf.predict_proba(x)[0]
        i = proba.argmax()
        label, conf = self.clf.classes_[i], float(proba[i])
        score = float(self.iso.score_samples(x)[0])
        if score < self.thr:          # ไม่เหมือนข้อมูลที่เคยฝึกเลย
            label = "unknown"
        return label, conf, score


class AlertLogic:
    """แจ้งเตือนเมื่อสถานะเปลี่ยนและคงอยู่ติดกัน N หน้าต่าง (กันการแจ้งเตือนรัว ๆ จากค่ากระโดด)"""

    def __init__(self, n: int, temp_limit: float):
        self.n, self.temp_limit = n, temp_limit
        self.reported = defaultdict(lambda: "normal")
        self.streak = defaultdict(lambda: ("", 0))
        self.hot = defaultdict(bool)

    def update(self, device: str, label: str, temp: float) -> list[tuple[str, str]]:
        out = []
        # กฎความปลอดภัย (ไม่ใช้ AI): อุณหภูมิสูงเกินกำหนด
        if temp >= self.temp_limit and not self.hot[device]:
            out.append(("temperature", f"🌡️ {device}: อุณหภูมิ {temp:.1f}°C เกิน {self.temp_limit}°C"))
        self.hot[device] = temp >= self.temp_limit

        prev, k = self.streak[device]
        self.streak[device] = (label, k + 1 if label == prev else 1)
        label, k = self.streak[device]
        if k == self.n and label != self.reported[device]:
            icon = "✅" if label == "normal" else "⚠️"
            out.append(("state", f"{icon} {device}: สถานะเปลี่ยนเป็น '{LABEL_TH.get(label, label)}' "
                                 f"(ต่อเนื่อง {self.n} วินาที)"))
            self.reported[device] = label
        return out


def main():
    predictor = Predictor(path(config.MODEL_PATH))
    alerts = AlertLogic(config.ALERT_CONSECUTIVE, config.TEMP_LIMIT_C)
    db = db_connect()

    def on_connect(cli, userdata, flags, rc, props):
        print("เชื่อมต่อ broker แล้ว รอข้อมูลที่", TOPIC_TELEMETRY.format(device="+"))
        cli.subscribe(TOPIC_TELEMETRY.format(device="+"))

    def on_message(cli, userdata, msg):
        try:
            d = json.loads(msg.payload)
            device = msg.topic.split("/")[1]
            label, conf, score = predictor.predict(d)
        except (ValueError, KeyError) as e:
            print("ข้ามข้อความที่ไม่ถูกต้อง:", e)
            return
        now = time.time()
        db.execute(
            "INSERT INTO telemetry (ts, device, rms_x, rms_y, rms_z, rms, p2p, crest, f_dom, temp, hum,"
            " label, confidence, anomaly) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (now, device, d["rms_x"], d["rms_y"], d["rms_z"], d["rms"], d["p2p"], d["crest"],
             d["f_dom"], d.get("temp"), d.get("hum"), label, conf, score))
        for kind, text in alerts.update(device, label, d.get("temp") or 0.0):
            db.execute("INSERT INTO alerts (ts, device, kind, message) VALUES (?,?,?,?)",
                       (now, device, kind, text))
            cli.publish(TOPIC_ALERT.format(device=device), json.dumps({"kind": kind, "message": text}))
            print("ALERT:", text)
        db.commit()
        cli.publish(TOPIC_PREDICTION.format(device=device),
                    json.dumps({"label": label, "confidence": round(conf, 3), "anomaly": round(score, 3)}))
        print(f"{device}: {label:10s} ({conf:.0%})  rms={d['rms']:.3f}  T={d.get('temp')}")

    cli = mqtt_client("gateway")
    cli.on_connect = on_connect
    cli.on_message = on_message
    cli.connect(config.MQTT_HOST, config.MQTT_PORT, 30)
    cli.loop_forever()


if __name__ == "__main__":
    main()
