# 📡 Project Overview — SPECTRA RADAR 360°

## 1. Abstract

SPECTRA RADAR 360° is an educational mechatronics prototype that demonstrates the integration of distance sensing, stepper-motor motion, embedded control, serial communication, and graphical visualization. An HC-SR04 ultrasonic module is mounted on a rotating platform driven by a 28BYJ-48 stepper motor through a ULN2003 driver. An Arduino Uno controls the motion, measures distance, applies an object-detection threshold, and reports status to a Python desktop application.

When a valid measured distance is less than or equal to the configured threshold, the firmware stops the stepper at its current commanded position and activates a buzzer. The Python GUI changes to an alert theme and displays the approximate scan angle and measured distance. After the configured minimum hold time has elapsed and four consecutive readings are outside the detection zone, the controller clears the alert and resumes scanning.

## 2. Problem Statement

A basic ultrasonic module can measure distance in a single direction. To inspect a wider surrounding area, the sensor must be repositioned and each measurement must be associated with the sensor's scan direction. SPECTRA combines a low-cost stepper mechanism with an ultrasonic sensor and a desktop visualization so that distance readings can be interpreted in relation to scan angle.

## 3. Objectives

- Integrate Arduino Uno with a stepper motor driver and ultrasonic sensor.
- Produce a bidirectional full-revolution scanning motion.
- Estimate scan angle from the number of commanded half-steps.
- Detect objects inside a user-configurable distance threshold.
- Hold the motor and activate an audible alert while a detected object remains in range.
- Provide a desktop interface for configuration, telemetry, and event history.
- Demonstrate a simple, documented Serial protocol between embedded and desktop software.

## 4. Operating Principle

1. The Arduino advances the stepper through an eight-state half-step sequence.
2. The sensor is triggered at regular intervals and the Echo pulse duration is measured.
3. The firmware converts the pulse duration to a distance estimate in centimeters.
4. The current step count is converted to an estimated angle from 0° to 360°.
5. If the distance is valid and inside the selected limit, the controller sets the detected state, stops issuing new motor steps, and activates the buzzer.
6. The controller continues measuring while stopped.
7. After the minimum hold time and four consecutive clear readings, the alert is cleared and scanning resumes.
8. The Arduino streams telemetry to Python, which updates the radar display and event log.

## 5. Project Scope

**Included:** ultrasonic distance reading, stepper motor control, a buzzer alert, serial settings, Python GUI, angle/distance display, manual pause/resume, and technical documentation.

**Not included:** object classification, vertical/elevation tracking, precision encoder feedback, certified obstacle avoidance, weatherproof construction, or autonomous navigation.

## 6. Intended Learning Outcomes

- Embedded C/C++ programming on Arduino.
- Stepper-motor sequencing and open-loop position estimation.
- Ultrasonic time-of-flight measurement.
- Serial communication and simple protocol design.
- Python GUI programming and background serial reading.
- Integration testing across hardware and desktop software.

## 7. Performance and Limitations

The HC-SR04 is commonly specified for a nominal range of approximately 2–400 cm, but that value is not a guarantee for all targets. Soft, small, angled, or irregular surfaces may return weak or inconsistent echoes. The system's angle is calculated from step commands and can drift from the true mechanical orientation if steps are missed or the gearbox differs from nominal. The prototype should therefore be calibrated and tested in its intended environment.

## 8. Project Identity

**Project:** SPECTRA RADAR 360°  
**Author:** SAAD AHMED ALBOHAN  
**Discipline:** Mechatronics Engineering  
**Institution:** Faculty of Engineering, Dhamar University
