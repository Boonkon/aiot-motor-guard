// ขั้นที่ 2: Cucumber RIS -> MQTT
// ทุก ๆ 1 วินาที บอร์ดจะ
//   1) เก็บค่าความเร่งจาก MPU-6050 จำนวน 200 ตัวอย่าง (200 Hz)
//   2) สรุปเป็น "ฟีเจอร์" ไม่กี่ตัว (RMS, peak-to-peak, crest factor, ความถี่เด่น)
//   3) อ่านอุณหภูมิ/ความชื้นจาก HTS221
//   4) ส่งเป็น JSON ไปที่ topic  aiot/<DEVICE_ID>/telemetry
// การย่อข้อมูลบนบอร์ด (edge processing) ทำให้ส่งข้อมูลน้อยลงจาก 600 ค่า/วินาที เหลือ ~8 ค่า/วินาที

#include <Arduino.h>
#include <Wire.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Adafruit_HTS221.h>
#include <Adafruit_MPU6050.h>
#include "secrets.h"   // คัดลอกจาก secrets_example.h

#define I2C_SDA 41
#define I2C_SCL 40

const int   N_SAMPLES = 200;        // จำนวนตัวอย่างต่อหน้าต่าง
const float FS_HZ     = 200.0f;     // อัตราสุ่มตัวอย่าง
const uint32_t PERIOD_US = (uint32_t)(1e6 / FS_HZ);

float bx[N_SAMPLES], by[N_SAMPLES], bz[N_SAMPLES], bm[N_SAMPLES];

Adafruit_HTS221 hts;
Adafruit_MPU6050 mpu;
WiFiClient net;
PubSubClient mqtt(net);

String topicTelemetry = String("aiot/") + DEVICE_ID + "/telemetry";
String topicStatus    = String("aiot/") + DEVICE_ID + "/status";
uint32_t seq = 0;

void connectWiFi() {
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  Serial.print("WiFi");
  while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
  Serial.printf("\nWiFi OK, IP = %s\n", WiFi.localIP().toString().c_str());
}

void connectMQTT() {
  while (!mqtt.connected()) {
    String cid = String("cucumber-") + DEVICE_ID + "-" + String(random(0xffff), HEX);
    // Last Will: ถ้าบอร์ดหลุด broker จะประกาศ "offline" ให้อัตโนมัติ
    if (mqtt.connect(cid.c_str(), topicStatus.c_str(), 1, true, "offline")) {
      mqtt.publish(topicStatus.c_str(), "online", true);
      Serial.println("MQTT connected");
    } else {
      Serial.printf("MQTT failed rc=%d, retry in 3 s\n", mqtt.state());
      delay(3000);
    }
  }
}

// ค่า RMS ของสัญญาณหลังลบค่าเฉลี่ย (ตัดผลของแรงโน้มถ่วงออก)
float rmsNoMean(const float *x, int n) {
  float mean = 0;
  for (int i = 0; i < n; i++) mean += x[i];
  mean /= n;
  float s = 0;
  for (int i = 0; i < n; i++) { float d = x[i] - mean; s += d * d; }
  return sqrtf(s / n);
}

// หาความถี่เด่นด้วยอัลกอริทึม Goertzel (เบากว่า FFT เต็มรูปแบบ เหมาะกับ ESP32-S2 ที่ไม่มี FPU)
float dominantHz(const float *x, int n, float fs) {
  float mean = 0;
  for (int i = 0; i < n; i++) mean += x[i];
  mean /= n;
  int bestK = 1;
  float bestP = 0;
  for (int k = 1; k < n / 2; k++) {
    float coeff = 2.0f * cosf(2.0f * PI * k / n);
    float s1 = 0, s2 = 0;
    for (int i = 0; i < n; i++) {
      float s0 = (x[i] - mean) + coeff * s1 - s2;
      s2 = s1; s1 = s0;
    }
    float p = s1 * s1 + s2 * s2 - coeff * s1 * s2;
    if (p > bestP) { bestP = p; bestK = k; }
  }
  return bestK * fs / n;
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Wire.begin(I2C_SDA, I2C_SCL);
  Wire.setClock(400000);  // I2C เร็ว เพื่อให้อ่านได้ทัน 200 Hz

  if (!hts.begin_I2C()) Serial.println("HTS221 not found");
  if (!mpu.begin()) {
    Serial.println("MPU-6050 not found — ตรวจสาย/บอร์ด");
    while (true) delay(100);
  }
  mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
  mpu.setFilterBandwidth(MPU6050_BAND_94_HZ);

  connectWiFi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  mqtt.setBufferSize(512);
  connectMQTT();
}

void loop() {
  if (WiFi.status() != WL_CONNECTED) connectWiFi();
  if (!mqtt.connected()) connectMQTT();

  // 1) เก็บตัวอย่างความเร่ง
  uint32_t t0 = micros();
  for (int i = 0; i < N_SAMPLES; i++) {
    while (micros() - t0 < (uint32_t)i * PERIOD_US) { /* รอให้ถึงเวลาสุ่มครั้งถัดไป */ }
    sensors_event_t a, g, t;
    mpu.getEvent(&a, &g, &t);
    bx[i] = a.acceleration.x / 9.80665f;
    by[i] = a.acceleration.y / 9.80665f;
    bz[i] = a.acceleration.z / 9.80665f;
    bm[i] = sqrtf(bx[i] * bx[i] + by[i] * by[i] + bz[i] * bz[i]);
  }
  mqtt.loop();

  // 2) คำนวณฟีเจอร์
  float rx = rmsNoMean(bx, N_SAMPLES);
  float ry = rmsNoMean(by, N_SAMPLES);
  float rz = rmsNoMean(bz, N_SAMPLES);
  float rm = rmsNoMean(bm, N_SAMPLES);
  float mn = bm[0], mx = bm[0], mean = 0;
  for (int i = 0; i < N_SAMPLES; i++) {
    mn = min(mn, bm[i]); mx = max(mx, bm[i]); mean += bm[i];
  }
  mean /= N_SAMPLES;
  float peak = max(mx - mean, mean - mn);
  float crest = rm > 1e-4f ? peak / rm : 0;
  float fdom = dominantHz(bm, N_SAMPLES, FS_HZ);

  // 3) อุณหภูมิ/ความชื้น
  sensors_event_t hum, temp;
  hts.getEvent(&hum, &temp);

  // 4) สร้าง JSON และส่ง
  JsonDocument doc;
  doc["device"] = DEVICE_ID;
  doc["seq"]    = seq++;
  doc["rms_x"]  = rx;
  doc["rms_y"]  = ry;
  doc["rms_z"]  = rz;
  doc["rms"]    = rm;
  doc["p2p"]    = mx - mn;
  doc["crest"]  = crest;
  doc["f_dom"]  = fdom;
  doc["temp"]   = temp.temperature;
  doc["hum"]    = hum.relative_humidity;

  char buf[384];
  size_t len = serializeJson(doc, buf);
  // ต้อง cast เป็น uint8_t* เพื่อเลือก overload (topic, payload, length, retained)
  // ถ้าส่ง (char*, len) ตรง ๆ คอมไพเลอร์จะตีความ len เป็น retained=true โดยไม่เตือน
  mqtt.publish(topicTelemetry.c_str(), (const uint8_t *)buf, len, false);
  Serial.println(buf);
}
