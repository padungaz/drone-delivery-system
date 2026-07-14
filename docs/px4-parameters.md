# PX4 Parameter Configuration
# Pixhawk 6C — Drone Delivery Autonomous System

Apply these parameters via QGroundControl or `param set` over MAVLink.
Reboot after changing parameters.

---

## MAVLink

| Parameter | Value | Description |
|-----------|-------|-------------|
| `MAV_0_CONFIG` | `101` | TELEM1 serial port |
| `MAV_0_MODE` | `2` | Onboard companion computer |
| `MAV_0_RATE` | `1200` | MAVLink stream rate (bytes/s) |
| `SER_TEL1_BAUD` | `57600` | Telemetry 1 baud rate |

```bash
param set MAV_0_CONFIG 101
param set MAV_0_MODE 2
param set MAV_0_RATE 1200
param set SER_TEL1_BAUD 57600
```

---

## EKF2 — State Estimator

| Parameter | Value | Description |
|-----------|-------|-------------|
| `EKF2_EN` | `1` | Enable EKF2 |
| `EKF2_AID_MASK` | `24` | GPS (1) + Vision Position (16) = 17; use 24 for GPS+EV+flow |
| `EKF2_HGT_MODE` | `2` | Range sensor (for landing) |
| `EKF2_REQ_NSATS` | `6` | Minimum GPS satellites |

```bash
param set EKF2_EN 1
param set EKF2_AID_MASK 24
param set EKF2_HGT_MODE 2
param set EKF2_REQ_NSATS 6
```

> **Vision Position Fusion**: Enable bit 4 (value 16) in `EKF2_AID_MASK` for external vision aiding via `LANDING_TARGET` and `VISION_POSITION_ESTIMATE`.

---

## GPS

| Parameter | Value | Description |
|-----------|-------|-------------|
| `EKF2_GPS_CTRL` | `7` | Enable GPS lon/lat/alt/vel fusion |

```bash
param set EKF2_GPS_CTRL 7
```

---

## Optical Flow / Range Finder

| Parameter | Value | Description |
|-----------|-------|-------------|
| `EKF2_RNG_CTRL` | `1` | Enable range finder for height aiding |

```bash
param set EKF2_RNG_CTRL 1
```

---

## Precision Landing

| Parameter | Value | Description |
|-----------|-------|-------------|
| `PLD_HACC_RAD` | `0.2` | Horizontal acceptance radius (m) |
| `PLD_MAX_SRCH` | `3` | Max search attempts |
| `PLD_SRCH_ALT` | `10` | Search altitude (m) |
| `PLD_SRCH_TOUT` | `10` | Search timeout (s) |

```bash
param set PLD_HACC_RAD 0.2
param set PLD_MAX_SRCH 3
param set PLD_SRCH_ALT 10
param set PLD_SRCH_TOUT 10
```

---

## Landing Mode Constraints

| Parameter | Value | Description |
|-----------|-------|-------------|
| `LNDMC_ALT_GND` | `2` | Ground effect altitude (m) |
| `LNDMC_XY_VEL_MAX` | `1.5` | Max horizontal velocity during landing (m/s) |
| `LNDMC_Z_VEL_MAX` | `0.25` | Max descent rate during landing (m/s) |

```bash
param set LNDMC_ALT_GND 2
param set LNDMC_XY_VEL_MAX 1.5
param set LNDMC_Z_VEL_MAX 0.25
```

---

## Mission / Navigation

| Parameter | Value | Description |
|-----------|-------|-------------|
| `MIS_TAKEOFF_ALT` | `10` | Default takeoff altitude (m) |
| `NAV_ACC_RAD` | `2` | Waypoint acceptance radius (m) |

```bash
param set MIS_TAKEOFF_ALT 10
param set NAV_ACC_RAD 2
```

---

## Return to Launch

| Parameter | Value | Description |
|-----------|-------|-------------|
| `RTL_RETURN_ALT` | `30` | RTL cruise altitude (m) |
| `RTL_DESCEND_ALT` | `10` | RTL descend altitude (m) |

```bash
param set RTL_RETURN_ALT 30
param set RTL_DESCEND_ALT 10
```

---

## Safety / Failsafe

| Parameter | Value | Description |
|-----------|-------|-------------|
| `COM_DISARM_LAND` | `2` | Auto-disarm after landing (s) |
| `COM_DL_LOSS_T` | `10` | Data link loss timeout (s) |
| `COM_OBC_LOSS_T` | `5` | Onboard computer loss timeout (s) |

```bash
param set COM_DISARM_LAND 2
param set COM_DL_LOSS_T 10
param set COM_OBC_LOSS_T 5
```

> `COM_OBC_LOSS_T = 5` ensures PX4 triggers failsafe if Raspberry Pi companion stops responding within 5 seconds.

---

## Battery

| Parameter | Value | Description |
|-----------|-------|-------------|
| `BAT_LOW_THR` | `0.15` | Low battery threshold (15%) |
| `BAT_CRIT_THR` | `0.07` | Critical battery threshold (7%) |

```bash
param set BAT_LOW_THR 0.15
param set BAT_CRIT_THR 0.07
```

---

## MAVLink Messages

### Raspberry Pi reads (subscribed at 20Hz)

| Message | Fields |
|---------|--------|
| `GLOBAL_POSITION_INT` | lat, lon, relative_alt |
| `VFR_HUD` | groundspeed, heading |
| `SYS_STATUS` | battery_remaining |
| `ATTITUDE` | roll, pitch, yaw |
| `GPS_RAW_INT` | satellites_visible, fix_type |

### Raspberry Pi sends

| Message | Purpose |
|---------|---------|
| `LANDING_TARGET` | ArUco precision landing guidance |
| `COMMAND_LONG` | arm, takeoff, goto, land, RTL |
| `SET_POSITION_TARGET_GLOBAL_INT` | waypoint navigation |

---

## Apply All Script

Save as `apply_params.sh` and run via QGroundControl MAVLink console or companion:

```bash
#!/bin/bash
PARAMS=(
  "MAV_0_CONFIG 101"
  "MAV_0_MODE 2"
  "MAV_0_RATE 1200"
  "SER_TEL1_BAUD 57600"
  "EKF2_EN 1"
  "EKF2_AID_MASK 24"
  "EKF2_HGT_MODE 2"
  "EKF2_REQ_NSATS 6"
  "EKF2_GPS_CTRL 7"
  "EKF2_RNG_CTRL 1"
  "PLD_HACC_RAD 0.2"
  "PLD_MAX_SRCH 3"
  "PLD_SRCH_ALT 10"
  "PLD_SRCH_TOUT 10"
  "LNDMC_ALT_GND 2"
  "LNDMC_XY_VEL_MAX 1.5"
  "LNDMC_Z_VEL_MAX 0.25"
  "MIS_TAKEOFF_ALT 10"
  "NAV_ACC_RAD 2"
  "RTL_RETURN_ALT 30"
  "RTL_DESCEND_ALT 10"
  "COM_DISARM_LAND 2"
  "COM_DL_LOSS_T 10"
  "COM_OBC_LOSS_T 5"
  "BAT_LOW_THR 0.15"
  "BAT_CRIT_THR 0.07"
)

for p in "${PARAMS[@]}"; do
  echo "param set $p"
done
echo "param save"
echo "reboot"
```
