"""ฝึกโมเดล AI จากไฟล์ CSV ที่เก็บด้วย collect.py

    python train.py                 # ใช้ data/ (ถ้าไม่มีจะใช้ data_demo/ ซึ่งเป็นข้อมูลสังเคราะห์)
    python train.py --data data_demo

ได้ไฟล์:
    models/motor_model.joblib     โมเดลที่ gateway.py ใช้
    models/confusion_matrix.png   ภาพสรุปว่าโมเดลทายถูก/ผิดอย่างไร
"""
import argparse
import glob
import os

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import ConfusionMatrixDisplay, classification_report
from sklearn.model_selection import train_test_split

from common import MODEL_FEATURES, config, path


def load(folder: str) -> pd.DataFrame:
    files = sorted(glob.glob(os.path.join(folder, "*.csv")))
    if not files:
        raise SystemExit(f"ไม่พบไฟล์ CSV ใน {folder}")
    df = pd.concat([pd.read_csv(f) for f in files], ignore_index=True)
    print(f"โหลด {len(df)} แถวจาก {len(files)} ไฟล์")
    print(df["label"].value_counts().to_string(), "\n")
    return df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=None)
    a = ap.parse_args()
    folder = a.data or (path("data") if glob.glob(path("data/*.csv")) else path("data_demo"))
    df = load(folder)

    X, y = df[MODEL_FEATURES], df["label"]
    X_tr, X_te, y_tr, y_te = train_test_split(X, y, test_size=0.25, stratify=y, random_state=0)

    # 1) ตัวจำแนก: ทายว่าเป็น ปกติ / ไม่สมดุล / หยุด
    clf = RandomForestClassifier(n_estimators=100, max_depth=6, random_state=0)
    clf.fit(X_tr, y_tr)
    print("ผลทดสอบกับข้อมูลที่โมเดลไม่เคยเห็น (25%):")
    print(classification_report(y_te, clf.predict(X_te), digits=3))

    print("ความสำคัญของแต่ละฟีเจอร์:")
    for name, imp in sorted(zip(MODEL_FEATURES, clf.feature_importances_), key=lambda t: -t[1]):
        print(f"  {name:6s} {imp:.3f} " + "#" * int(imp * 50))

    # 2) ตัวตรวจ "ของแปลก": รูปแบบที่ไม่เหมือนข้อมูลฝึกเลย -> unknown
    iso = IsolationForest(n_estimators=100, contamination="auto", random_state=0).fit(X_tr)
    threshold = float(pd.Series(iso.score_samples(X_tr)).quantile(0.01))

    os.makedirs(os.path.dirname(path(config.MODEL_PATH)), exist_ok=True)
    joblib.dump({"clf": clf, "iso": iso, "iso_threshold": threshold,
                 "features": MODEL_FEATURES, "trained_on": os.path.basename(folder)},
                path(config.MODEL_PATH))

    fig, ax = plt.subplots(figsize=(5, 4.2))
    ConfusionMatrixDisplay.from_estimator(clf, X_te, y_te, ax=ax, cmap="Blues", colorbar=False)
    ax.set_title("Confusion matrix (test set)")
    fig.tight_layout()
    fig.savefig(path("models/confusion_matrix.png"), dpi=120)
    print(f"\nบันทึกโมเดลที่ {config.MODEL_PATH} และภาพ models/confusion_matrix.png")


if __name__ == "__main__":
    main()
