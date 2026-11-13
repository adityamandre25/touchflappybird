/*
 * Flappy Bird - Arduino Touch Controller
 * 
 * Hardware:
 *   - Arduino Uno (or compatible AVR board)
 *   - TTP223 Capacitive Touch Sensor Module
 * 
 * Wiring:
 *   - TTP223 VCC  -> Arduino 5V
 *   - TTP223 GND  -> Arduino GND
 *   - TTP223 OUT  -> Arduino Digital Pin 2
 * 
 * Behavior:
 *   - Monitors touch sensor on pin 2.
 *   - Uses rising edge detection to detect a tap/touch.
 *   - Sends "JUMP\n" via Serial (9600 baud) once per touch.
 *   - Includes debouncing (50ms) to prevent double/false triggers.
 *   - Toggles built-in LED (Pin 13) for instant visual feedback.
 */

const int TOUCH_PIN = 2;        // TTP223 OUT connected to Digital Pin 2
const int LED_PIN = 13;         // Onboard LED indicator
const unsigned long DEBOUNCE_MS = 40; // Debounce threshold in milliseconds

int lastReading = LOW;
int stableState = LOW;
unsigned long lastDebounceTime = 0;

void setup() {
  Serial.begin(9600);
  pinMode(TOUCH_PIN, INPUT);
  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Allow serial port and sensor to stabilize
  delay(200);
  Serial.println("FLAPPY_CONTROLLER_READY");
}

void loop() {
  int currentReading = digitalRead(TOUCH_PIN);

  // If signal transitioned, reset debounce timer
  if (currentReading != lastReading) {
    lastDebounceTime = millis();
  }

  // Check if reading has stayed stable past debounce threshold
  if ((millis() - lastDebounceTime) > DEBOUNCE_MS) {
    if (currentReading != stableState) {
      stableState = currentReading;

      // On rising edge (finger touched the pad)
      if (stableState == HIGH) {
        Serial.println("JUMP");
        digitalWrite(LED_PIN, HIGH);
      } else {
        digitalWrite(LED_PIN, LOW);
      }
    }
  }

  lastReading = currentReading;
}
