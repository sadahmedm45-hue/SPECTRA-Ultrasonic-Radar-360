# ✅ Test Plan and Results

## Test Status

**Status at documentation time:** hardware tests are not independently verified in this repository package. The procedures below define how to perform and record the tests. Do not mark a case as PASS until it has been run on the assembled circuit.

## Test Matrix

| ID | Test | Procedure | Expected result | Status |
|---|---|---|---|---|
| T-01 | Arduino startup | Upload firmware and open Serial Monitor at 115200 baud | `READY` and `INFO` lines appear | NOT RUN |
| T-02 | Python dependencies | Install `requirements.txt` and launch GUI | GUI opens without missing-module errors | NOT RUN |
| T-03 | Serial connection | Close Serial Monitor, select COM port, connect | GUI receives `RADAR` telemetry | NOT RUN |
| T-04 | Motor scan | Run with no target in range | Motor scans to the endpoint and reverses | NOT RUN |
| T-05 | Distance reading | Place a flat target at a known distance | Displayed value is plausible and stable | NOT RUN |
| T-06 | Detection threshold | Place a target inside configured limit | Red alert, buzzer, motor hold, event log | NOT RUN |
| T-07 | Minimum hold | Remove target before the hold interval ends | Motor does not resume before minimum hold expires | NOT RUN |
| T-08 | Persistent target | Keep target inside range after hold expires | Motor stays stopped and buzzer remains active | NOT RUN |
| T-09 | Clear confirmation | Remove target and keep area clear | Four clear readings plus hold completion resume scan | NOT RUN |
| T-10 | Live settings | Change speed, limit, and hold from GUI | Arduino returns matching `CONFIG` acknowledgements | NOT RUN |
| T-11 | Manual pause | Click Pause Scan / Resume Scan | Arduino confirms `STATE` messages | NOT RUN |
| T-12 | Range edge cases | Test near 2 cm and at increasing distances | Invalid/out-of-range readings are handled without GUI crash | NOT RUN |

## Test Record Template

Copy this block for each physical session:

```text
Test date:
Hardware version / motor voltage:
Arduino board / port:
Python version:
Speed level:
Detection threshold (cm):
Minimum hold time (s):
Target type / surface:
Measured target distance (cm):
Observed scan angle (deg):
Expected behavior:
Actual behavior:
Result: PASS / FAIL / NEEDS REVIEW
Notes / photo path:
```

## Acceptance Criteria

- Firmware starts and responds at 115200 baud.
- The sensor returns valid distance readings for a suitable target.
- The stepper sweeps in both directions without mechanical interference.
- In-range measurements stop the motor at its current commanded step position and activate the buzzer.
- The GUI displays the same reported distance and estimated angle as Arduino telemetry.
- Scanning resumes only after the configured minimum hold and four consecutive clear readings.
- Serial connection loss or malformed packets do not cause the GUI to freeze.

## Engineering Notes

The angle is open-loop: it is calculated from commanded step counts rather than measured by an encoder. Any missed steps, mechanical slip, or motor/gearbox variance can cause angle error. The HC-SR04's beam width and target reflections can also cause uncertainty in the target marker position. Record these limitations when reporting results.

