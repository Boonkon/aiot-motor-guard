// ขั้นที่ 1: อ่านค่าเซนเซอร์ทั้ง 3 ตัวบนบอร์ด Cucumber RIS แล้วพิมพ์ออก Serial Monitor
//   - HTS221  : อุณหภูมิ + ความชื้น
//   - MPU-6050: ความเร่ง 3 แกน (ใช้วัดการสั่นของมอเตอร์)
//   - BMP280  : ความดันอากาศ
// เซนเซอร์ทั้งหมดต่ออยู่บนบัส I2C เดียวกัน: SDA = GPIO41, SCL = GPIO40

#include <Arduino.h>
#include <Wire.h>
#include <Adafruit_HTS221.h>
#include <Adafruit_MPU6050.h>
#include <Adafruit_BMP280.h>

#define I2C_SDA 41
#define I2C_SCL 40

Adafruit_HTS221 hts;
Adafruit_MPU6050 mpu;
Adafruit_BMP280 bmp;
bool hasBmp = false;

// สแกนหาอุปกรณ์บนบัส I2C — ช่วยตรวจว่าเซนเซอร์ตอบสนองหรือไม่
void scanI2C() {
  Serial.println("I2C scan:");
  for (uint8_t addr = 1; addr < 127; addr++) {
    Wire.beginTransmission(addr);
    if (Wire.endTransmission() == 0) {
      Serial.printf("  found device at 0x%02X\n", addr);
    }
  }
}

void setup() {
  Serial.begin(115200);
  delay(1500);
  Wire.begin(I2C_SDA, I2C_SCL);
  scanI2C();

  if (!hts.begin_I2C()) {
    Serial.println("ไม่พบ HTS221");
  }
  if (!mpu.begin()) {
    Serial.println("ไม่พบ MPU-6050");
  } else {
    mpu.setAccelerometerRange(MPU6050_RANGE_4_G);
    mpu.setFilterBandwidth(MPU6050_BAND_94_HZ);
  }
  // BMP280 อาจอยู่ที่ 0x76 หรือ 0x77 ขึ้นกับรุ่นบอร์ด
  hasBmp = bmp.begin(0x76) || bmp.begin(0x77);
  if (!hasBmp) Serial.println("ไม่พบ BMP280 (ข้ามได้ ไม่ได้ใช้ในโปรเจกต์หลัก)");
}

void loop() {
  sensors_event_t hum, temp;
  hts.getEvent(&hum, &temp);

  sensors_event_t a, g, t;
  mpu.getEvent(&a, &g, &t);

  // แปลงหน่วย m/s^2 เป็น g (1 g = 9.80665 m/s^2) เพื่อให้อ่านง่าย
  float ax = a.acceleration.x / 9.80665f;
  float ay = a.acceleration.y / 9.80665f;
  float az = a.acceleration.z / 9.80665f;

  Serial.printf("T=%.2f C  RH=%.1f %%  acc[g]: x=%+.3f y=%+.3f z=%+.3f",
                temp.temperature, hum.relative_humidity, ax, ay, az);
  if (hasBmp) Serial.printf("  P=%.1f hPa", bmp.readPressure() / 100.0f);
  Serial.println();
  delay(500);
}
