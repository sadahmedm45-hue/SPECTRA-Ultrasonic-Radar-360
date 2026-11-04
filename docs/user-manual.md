# 🧭 User Manual

## 1. Launching the Application

Run the GUI from the repository root:

```bash
python software/python/radar_gui.py
```

Until the Arduino is connected, the interface shows a demo sweep. Demo animation is only a visual preview; it is not a physical sensor measurement.

## 2. Serial Connection

1. Connect Arduino Uno to the computer over USB.
2. Close Arduino IDE Serial Monitor.
3. Click **REFRESH PORTS**.
4. Select the Arduino COM port.
5. Click **CONNECT**.
6. Wait for the link status and incoming `RADAR` telemetry.

Click **DISCONNECT** before closing the application or reconnecting to another board.

## 3. Radar Display

The main radar panel shows:

- A 360° circular grid and bearing labels.
- The current scan ray and a short sweep trail.
- Recent target markers positioned using angle and measured range.
- A detection marker when an object is inside the selected distance threshold.
- Range rings scaled to the current detection limit.

The displayed angle is estimated from the stepper step counter. It is not a direct measurement from an encoder.

## 4. Live Controls

| Control | Range | Description |
|---|---:|---|
| Stepper Speed | 1–10 | 1 is slowest; 10 is fastest |
| Detection Distance | 2–400 cm | A valid measured distance at or below this value enters alert state |
| Minimum Stop Time | 2–30 seconds | Minimum duration the motor must remain stopped after detection |
| Apply | — | Sends current settings to Arduino |
| Pause Scan | — | Sends a manual pause command |
| Resume Scan | — | Sends a manual resume command |

The GUI also schedules settings updates after slider adjustments. If the board is not connected, the settings remain local until connection and application.

## 5. Understanding the Alert

When the distance is valid and within the threshold:

- The radar theme changes from green to red.
- The alert panel reports the measured distance and scan angle.
- The Arduino stops issuing new step commands and keeps the stepper coils energized to hold position.
- The buzzer is activated at the Arduino.
- Python logs the event and may play a host-side alert sound on supported Windows systems.

The motor resumes only when the minimum hold time has elapsed and the firmware has received four consecutive clear readings. If a target remains in range, the motor stays stopped even after the timer reaches zero.

## 6. Serial Output Panel

The log shows connection events, controller acknowledgements, detection events, cleared events, configuration acknowledgements, and parsing errors. The **LATEST RX** area shows the most recently received line.

For packet definitions, see [Communication Protocol](communication-protocol.md).

## 7. Author Information

Click the author portrait / project-information link in the right-side profile panel to open the project information window.

## 8. Safe Operation

- Keep fingers, loose clothing, and cables away from the rotating platform.
- Do not move the sensor mount by hand while the stepper is energized.
- Use a stable power source matching the motor's rating.
- The sensor is not suitable as a life-safety or collision-prevention device.
- Do not rely on this prototype for security, navigation, or protection of people or property.
