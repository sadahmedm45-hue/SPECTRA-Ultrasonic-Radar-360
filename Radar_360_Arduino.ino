#include <stdlib.h>
#include <string.h>

// Hardware wiring (Arduino Uno):
// ULN2003 IN1/N1 -> D12, IN2/N2 -> D11, IN3/N3 -> D10, IN4/N4 -> D9
// HC-SR04 TRIG -> D8, ECHO -> D7; buzzer + -> D13, buzzer - -> GND

const uint8_t MOTOR_PINS[4] = {12, 11, 10, 9};
const uint8_t TRIG_PIN = 8;
const uint8_t ECHO_PIN = 7;
const uint8_t BUZZER_PIN = 13;

const long STEPS_PER_REV = 4096L;       // Nominal 28BYJ-48 half-step revolution
const unsigned long MEASURE_INTERVAL_MS = 65UL;
const unsigned long ECHO_TIMEOUT_US = 25000UL;
const uint8_t CLEAR_READINGS_TO_RESUME = 4;

const uint8_t HALF_STEP_SEQUENCE[8] = {
  0b0001, 0b0011, 0b0010, 0b0110,
  0b0100, 0b1100, 0b1000, 0b1001
};

long positionSteps = 0;
int8_t scanDirection = 1;
int8_t sequenceIndex = 0;
uint8_t speedLevel = 5;                 // UI range: 1 (slow) ... 10 (fast)
uint16_t stopDurationSeconds = 3;       // UI range: 2 ... 30 seconds
float detectionLimitCm = 250.0f;        // UI range: 2 ... 400 cm
float lastDistanceCm = -1.0f;
bool objectDetected = false;
bool userPaused = false;
bool alarmActive = false;
uint8_t clearReadings = 0;
uint8_t stepsSinceMeasurement = 0;
unsigned long detectionStartedMs = 0;
unsigned long lastStepUs = 0;
unsigned long lastMeasureMs = 0;
char commandBuffer[40];
uint8_t commandLength = 0;

unsigned long stepIntervalUs() {
  // Lower interval = faster stepping. The speed level also changes the step
  // budget between ultrasonic readings, so all 10 levels have a useful effect.
  return (unsigned long)map(speedLevel, 1, 10, 9000, 1500);
}

uint8_t maxStepsPerMeasurement() {
  return (uint8_t)map(speedLevel, 1, 10, 3, 16);
}

void applyMotorSequence() {
  const uint8_t pattern = HALF_STEP_SEQUENCE[sequenceIndex];
  for (uint8_t i = 0; i < 4; i++) {
    digitalWrite(MOTOR_PINS[i], (pattern & (1U << i)) ? HIGH : LOW);
  }
}

void setAlarm(bool enabled) {
  if (enabled == alarmActive) return;
  alarmActive = enabled;
  if (alarmActive) tone(BUZZER_PIN, 1600);
  else noTone(BUZZER_PIN);
}

void setDetected(bool detected) {
  if (detected == objectDetected) return;
  objectDetected = detected;
  if (objectDetected) {
    clearReadings = 0;
    detectionStartedMs = millis();
    setAlarm(true);
    Serial.print(F("EVENT,OBJECT_DETECTED,"));
    Serial.print((positionSteps * 360.0f) / STEPS_PER_REV, 1);
    Serial.print(',');
    Serial.println(lastDistanceCm, 1);
  } else {
    clearReadings = 0;
    setAlarm(false);
    Serial.print(F("EVENT,OBJECT_CLEARED,"));
    Serial.print((positionSteps * 360.0f) / STEPS_PER_REV, 1);
    Serial.print(',');
    Serial.println(lastDistanceCm, 1);
  }
}

float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(3);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);

  const unsigned long duration = pulseIn(ECHO_PIN, HIGH, ECHO_TIMEOUT_US);
  if (duration == 0) return -1.0f;

  const float distance = (duration * 0.0343f) / 2.0f;
  if (distance < 2.0f || distance > 400.0f) return -1.0f;
  return distance;
}

void moveOneStep() {
  // Keep the actual step direction before changing direction at an endpoint.
  const int8_t directionUsed = scanDirection;
  sequenceIndex = (sequenceIndex + (directionUsed > 0 ? 1 : 7)) & 7;
  applyMotorSequence();
  positionSteps += directionUsed;

  if (positionSteps >= STEPS_PER_REV) {
    positionSteps = STEPS_PER_REV;
    scanDirection = -1;
  } else if (positionSteps <= 0) {
    positionSteps = 0;
    scanDirection = 1;
  }
}

unsigned long holdRemainingMs() {
  if (!objectDetected) return 0;
  const unsigned long elapsed = millis() - detectionStartedMs;
  const unsigned long required = (unsigned long)stopDurationSeconds * 1000UL;
  return elapsed >= required ? 0 : required - elapsed;
}

void sendTelemetry() {
  const float angle = (positionSteps * 360.0f) / STEPS_PER_REV;
  Serial.print(F("RADAR,"));
  Serial.print(angle, 1);
  Serial.print(',');
  Serial.print(lastDistanceCm, 1);
  Serial.print(',');
  Serial.print(objectDetected ? 1 : 0);
  Serial.print(',');
  Serial.print(scanDirection);
  Serial.print(',');
  Serial.print(userPaused ? 1 : 0);
  Serial.print(',');
  Serial.print(speedLevel);
  Serial.print(',');
  Serial.print(holdRemainingMs());
  Serial.print(',');
  Serial.print(detectionLimitCm, 1);
  Serial.print(',');
  Serial.println(stopDurationSeconds);
}

void processCommand(char *cmd) {
  if (strncmp(cmd, "LIMIT,", 6) == 0) {
    const float value = atof(cmd + 6);
    if (value >= 2.0f && value <= 400.0f) {
      detectionLimitCm = value;
      Serial.print(F("CONFIG,LIMIT,"));
      Serial.println(detectionLimitCm, 1);
    } else {
      Serial.println(F("ERROR,LIMIT_MUST_BE_2_TO_400_CM"));
    }
  } else if (strncmp(cmd, "SPEED,", 6) == 0) {
    const int value = atoi(cmd + 6);
    if (value >= 1 && value <= 10) {
      speedLevel = (uint8_t)value;
      stepsSinceMeasurement = 0;
      Serial.print(F("CONFIG,SPEED,"));
      Serial.println(speedLevel);
    } else {
      Serial.println(F("ERROR,SPEED_MUST_BE_1_TO_10"));
    }
  } else if (strncmp(cmd, "HOLD,", 5) == 0) {
    const int value = atoi(cmd + 5);
    if (value >= 2 && value <= 30) {
      stopDurationSeconds = (uint16_t)value;
      Serial.print(F("CONFIG,HOLD,"));
      Serial.println(stopDurationSeconds);
    } else {
      Serial.println(F("ERROR,HOLD_MUST_BE_2_TO_30_SECONDS"));
    }
  } else if (strcmp(cmd, "PAUSE") == 0) {
    userPaused = true;
    Serial.println(F("STATE,PAUSED"));
  } else if (strcmp(cmd, "RESUME") == 0) {
    userPaused = false;
    Serial.println(F("STATE,SCANNING"));
  } else if (strcmp(cmd, "PING") == 0) {
    Serial.println(F("READY,SPECTRA_RADAR_360"));
  } else if (cmd[0] != '\0') {
    Serial.println(F("ERROR,UNKNOWN_COMMAND"));
  }
}

void readSerialCommands() {
  while (Serial.available() > 0) {
    const char ch = (char)Serial.read();
    if (ch == '\r') continue;
    if (ch == '\n') {
      commandBuffer[commandLength] = '\0';
      if (commandLength > 0) processCommand(commandBuffer);
      commandLength = 0;
    } else if (commandLength < sizeof(commandBuffer) - 1) {
      commandBuffer[commandLength++] = ch;
    } else {
      commandLength = 0;
      Serial.println(F("ERROR,COMMAND_TOO_LONG"));
    }
  }
}

void setup() {
  for (uint8_t i = 0; i < 4; i++) pinMode(MOTOR_PINS[i], OUTPUT);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(TRIG_PIN, LOW);

  Serial.begin(115200);
  applyMotorSequence();
  lastStepUs = micros();
  lastMeasureMs = millis();
  Serial.println(F("READY,SPECTRA_RADAR_360"));
  Serial.println(F("INFO,Send LIMIT,2..400; SPEED,1..10; HOLD,2..30; PAUSE; RESUME"));
}

void loop() {
  readSerialCommands();
  const unsigned long nowMs = millis();

  if ((unsigned long)(nowMs - lastMeasureMs) >= MEASURE_INTERVAL_MS) {
    lastMeasureMs = nowMs;
    lastDistanceCm = readDistanceCm();
    stepsSinceMeasurement = 0;

    const bool inDetectionZone =
      lastDistanceCm >= 2.0f && lastDistanceCm <= detectionLimitCm;

    if (inDetectionZone) {
      clearReadings = 0;
      // First in-range reading locks the stepper at the current scan angle.
      if (!objectDetected) setDetected(true);
    } else if (objectDetected) {
      if (clearReadings < CLEAR_READINGS_TO_RESUME) clearReadings++;
      const bool minimumHoldPassed = holdRemainingMs() == 0;
      // Resume only after the requested hold time AND multiple clear readings.
      // If the object remains within range, the motor stays stopped indefinitely.
      if (minimumHoldPassed && clearReadings >= CLEAR_READINGS_TO_RESUME) {
        setDetected(false);
      }
    }
    sendTelemetry();
  }

  // The stepper stays energized and holds its position while detected/paused.
  if (!objectDetected && !userPaused &&
      stepsSinceMeasurement < maxStepsPerMeasurement()) {
    const unsigned long nowUs = micros();
    if ((unsigned long)(nowUs - lastStepUs) >= stepIntervalUs()) {
      lastStepUs = nowUs;
      moveOneStep();
      stepsSinceMeasurement++;
    }
  }
}
