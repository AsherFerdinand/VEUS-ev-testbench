# VEUS — Vehicle Electric Unit Simulation ⚡🚗

VEUS is a modular electric vehicle powertrain simulation framework written in Python. It models battery cell chemistry, motor torque curves, transmission gear ratios, and longitudinal vehicle dynamics, with real-time telemetry streaming to a web dashboard. 📊

---

## 🧩 Core Models & Solver

### 🔋 1. Battery Pack & Cell (`veus/model/cell.py`, `pack.py`)
Uses an **Equivalent Circuit Model (ECM)** that tracks Open Circuit Voltage ($V_{oc}$) as a function of State of Charge (SOC) and models voltage sag caused by internal resistance ($R_{internal}$) under heavy discharge currents:
$$V_{terminal} = V_{oc}(SOC) - I_{pack} \cdot R_{internal}$$

### ⚙️ 2. Motor & Inverter (`veus/model/motor.py`, `inverter.py`)
Models a Permanent Magnet Synchronous Motor (PMSM) with dual-region dynamics: **Constant Torque** at low speeds and **Field Weakening (Constant Power)** at high RPMs, including inverter switching loss efficiency maps.

### ⚙️ 3. Transmission & Vehicle Dynamics (`veus/model/transmission.py`, `vehicle.py`)
Calculates wheel torque through multi-speed gear reductions and solves aerodynamic drag ($\frac{1}{2} \rho C_d A v^2$), rolling resistance, and mass acceleration against road traction forces.

### ⏱️ 4. Fixed-Step Numerical Solver (`veus/sim/solver.py`)
Uses a **Fixed-Step Explicit Euler Integration** scheme ($\Delta t = 0.01\text{ s} - 0.1\text{ s}$) to advance vehicle speed, motor RPM, current draw, and battery SOC forward in time while maintaining deterministic execution for real-time HIL (Hardware-in-the-Loop) streaming.

---

## 📁 Project Structure

```text
veus_project/
├── veus/
│   ├── model/         # 🔋 Battery, ⚙️ motor, inverter, and vehicle dynamics
│   ├── sim/           # ⏱️ Numerical solver and drive cycle execution
│   └── studio/        # 🌐 FastAPI web dashboard & WebSocket streaming server
├── test_run.py        # 🚀 Powertrain test runner script
└── README.md          # 📄 Project documentation
