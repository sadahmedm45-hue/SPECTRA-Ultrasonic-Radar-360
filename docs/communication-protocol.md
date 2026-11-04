# 🔗 Serial Communication Protocol

## 1. Link Configuration

| Parameter | Value |
|---|---|
| Interface | USB Serial (Arduino Uno virtual COM port) |
| Baud rate | 115200 bits/s |
| Data bits | 8 |
| Parity | None |
| Stop bits | 1 |
| Encoding | ASCII |
| Framing | One message per line, terminated by LF (`\n`) |

The Python application and Arduino firmware must use the same baud rate. Close Arduino IDE Serial Monitor before opening the same COM port from Python.

## 2. Host-to-Arduino Commands

| Command | Valid range / format | Description | Example reply |
|---|---|---|---|
| `SPEED,n` | Integer 1–10 | Sets stepper speed level; 1 is slowest, 10 is fastest | `CONFIG,SPEED,7` |
| `LIMIT,n` | Number 2–400 | Sets detection threshold in centimeters | `CONFIG,LIMIT,180.0` |
| `HOLD,n` | Integer 2–30 | Sets minimum motor hold time in seconds | `CONFIG,HOLD,5` |
| `PAUSE` | No parameter | Pauses scanning | `STATE,PAUSED` |
| `RESUME` | No parameter | Resumes scanning unless the detection state still prevents motion | `STATE,SCANNING` |
| `PING` | No parameter | Requests a ready response | `READY,SPECTRA_RADAR_360` |

Invalid values produce an `ERROR` message. Commands must end with a newline. The Python GUI appends `\n` automatically.

## 3. Arduino-to-Host Telemetry

### RADAR packet

Format:

```text
RADAR,angle,distance,detected,direction,paused,speed,holdRemainingMs,limit,holdSeconds
```

| Index | Field | Type | Meaning |
|---:|---|---|---|
| 0 | `RADAR` | Text | Packet identifier |
| 1 | `angle` | Float | Estimated scan angle in degrees, 0–360 |
| 2 | `distance` | Float | Latest distance in cm; `-1.0` means no valid echo |
| 3 | `detected` | 0 / 1 | Object currently inside the configured detection zone |
| 4 | `direction` | -1 / +1 | Current scan direction |
| 5 | `paused` | 0 / 1 | Manual pause state |
| 6 | `speed` | Integer | Speed level, 1–10 |
| 7 | `holdRemainingMs` | Integer | Remaining minimum hold time in milliseconds |
| 8 | `limit` | Float | Active detection threshold in cm |
| 9 | `holdSeconds` | Integer | Configured minimum stop time in seconds |

Example:

```text
RADAR,126.0,42.5,1,-1,0,6,1800,250.0,3
```

This example indicates a detected object at an estimated scan angle of 126.0° and a measured distance of 42.5 cm. The motor is moving in the negative scan direction as a state value, but object detection holds its position; the configured minimum hold time has about 1.8 seconds remaining.

### Event messages

```text
EVENT,OBJECT_DETECTED,angle,distance
EVENT,OBJECT_CLEARED,angle,distance
```

The first event is emitted when the detection state changes from clear to detected. The second is emitted when the target-clear and minimum-hold conditions allow scanning to resume.

### Other message types

| Prefix | Purpose | Example |
|---|---|---|
| `READY` | Controller startup / ping response | `READY,SPECTRA_RADAR_360` |
| `INFO` | Startup instruction message | `INFO,Send LIMIT,2..400; SPEED,1..10; HOLD,2..30; PAUSE; RESUME` |
| `CONFIG` | Accepted setting acknowledgement | `CONFIG,SPEED,5` |
| `STATE` | Manual pause / resume acknowledgement | `STATE,PAUSED` |
| `ERROR` | Invalid command or parameter | `ERROR,HOLD_MUST_BE_2_TO_30_SECONDS` |

## 4. Measurement Semantics

The firmware sends a telemetry packet after each scheduled distance measurement (nominally every 65 ms). A zero echo timeout or a result outside the sensor's nominal 2–400 cm envelope is represented internally as `-1.0`; the Python GUI displays this as unavailable (`---.- cm`). A valid detection requires a valid reading of at least 2 cm and no greater than the active threshold.

## 5. Detection and Resume Rule

The stepper stops on the first valid in-range reading. The buzzer remains active while detected. Resume requires both:

1. The configured minimum hold time has elapsed since detection began.
2. Four consecutive subsequent readings are outside the detection zone.

A target that remains in range keeps the system stopped; the hold timer does not override a persistent detection.

## 6. Protocol Extension Guidance

If the message format changes, update both the Arduino firmware parser and the Python `handle_line()` implementation. Keep field order stable or introduce a version identifier before changing the packet structure.
