# 🚀 Installation and Setup Guide

## 1. Required Hardware

- Arduino Uno and a data-capable USB cable.
- 28BYJ-48 stepper motor and ULN2003 driver board.
- HC-SR04 ultrasonic sensor.
- Buzzer.
- Motor power supply matching the motor rating.
- Jumper wires and a stable mechanical mount.

Follow [the wiring guide](../hardware/wiring/pin-connections.md) before applying power.

## 2. Required Software

- Arduino IDE (to compile and upload the firmware).
- Python 3.10 or newer recommended.
- Visual Studio Code or another Python editor (optional).
- USB serial driver for the Arduino board, if required by the installed Uno variant.

Tkinter is part of most standard Windows Python installations. It is not a PyPI dependency in `requirements.txt`.

## 3. Clone or Download the Repository

### Option A — Git clone

```bash
git clone https://github.com/<YOUR-GITHUB-USERNAME>/SPECTRA-Ultrasonic-Radar-360.git
cd SPECTRA-Ultrasonic-Radar-360
```

Replace `<YOUR-GITHUB-USERNAME>` with the actual GitHub account name.

### Option B — Download ZIP

On GitHub, use **Code → Download ZIP**, extract the folder, and open the extracted repository root.

## 4. Install Python Dependencies

Open a terminal in the repository root and run:

```bash
python -m pip install -r requirements.txt
```

The requirements file contains:

- `pyserial` — serial-port access.
- `Pillow` — loading profile and project images.

Verify installation:

```bash
python -c "import serial; import PIL; print('Dependencies OK')"
```

## 5. Assemble the Hardware

1. Wire the Arduino, driver, stepper, HC-SR04, and buzzer according to the wiring diagram.
2. Verify the exact motor voltage rating before connecting its supply.
3. If using an external motor supply, connect its ground to Arduino GND.
4. Keep the rotating assembly mechanically clear and secure the sensor.

## 6. Upload Arduino Firmware

1. Open `firmware/arduino/SPECTRA_Radar_Arduino.ino` in Arduino IDE.
2. Select **Arduino Uno** under Tools → Board.
3. Select the correct USB port under Tools → Port.
4. Click **Upload**.
5. Open Serial Monitor at 115200 baud only for a brief diagnostic check, then close it before using Python.

At startup the controller should emit a `READY` line and an `INFO` line.

## 7. Run the Python GUI

From the repository root:

```bash
python software/python/radar_gui.py
```

The program will open in demo mode until connected. Click **REFRESH PORTS**, select the Arduino COM port, and click **CONNECT**. The interface should then report incoming telemetry and reflect the actual angle and distance packets.

## 8. First Bench Test

- Set the detection threshold to a conservative value, such as 100 cm.
- Set speed to 2–4 for initial mechanical checks.
- Set minimum hold time to 3 seconds.
- Keep hands clear of the rotating mechanism.
- Place a flat target at a known distance within the sensor's line of sight.
- Confirm the red alert, distance display, motor hold, and buzzer behavior.
- Remove the target and confirm four clear readings plus the hold interval allow scanning to resume.

## 9. Troubleshooting

| Symptom | Checks |
|---|---|
| No COM port appears | USB data cable, device driver, Device Manager, refresh ports |
| Port cannot be opened | Close Arduino Serial Monitor and other serial applications |
| GUI starts in demo mode | Select the correct COM port and click Connect |
| GUI reports missing `serial` | Install requirements in the active Python environment |
| Profile image is missing | Keep `assets/images/` at the repository root |
| Sensor always shows no distance | Check VCC/GND, TRIG D8, ECHO D7, target angle, and sensor timeout |
| False or unstable distance | Improve mounting, avoid angled/soft targets, reduce nearby reflections |
| Motor vibrates but does not rotate | Verify IN1–IN4 order, motor connector, driver supply, and shared ground |
| Motor angle is inaccurate | Calibrate `STEPS_PER_REV` for the actual motor and mechanical assembly |

## 10. Shutdown

Disconnect the Python GUI, close the application, and switch off the motor supply before changing wiring. Do not disconnect motor leads while the driver is energized.
