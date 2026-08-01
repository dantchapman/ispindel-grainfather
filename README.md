# iSpindel → Grainfather

[![hacs][hacs-badge]][hacs-url]

A Home Assistant integration that receives readings from an [iSpindel][ispindel]
DIY hydrometer, records them locally, and relays them to a Grainfather brew
session on a schedule you choose.

Home Assistant sits between the device and the cloud, which buys you three
things the device cannot do on its own:

- **A fast local log and a slow remote one.** Let the iSpindel report every
  minute for a detailed local graph while Grainfather still receives the
  15-minute cadence it expects.
- **Plato ↔ SG conversion.** Many iSpindels are calibrated to emit degrees
  Plato. If yours does, this converts on the way out so Grainfather gets the
  unit it is configured for.
- **A gap instead of a lie.** If the device goes quiet, uploads stop rather
  than repeating the last reading, so a dead battery shows up as a gap in your
  brew session rather than a convincing flat line.

## Installation

### HACS

1. HACS → Integrations → ⋮ → **Custom repositories**
2. Add this repository, category **Integration**
3. Install, then restart Home Assistant

### Manual

Copy `custom_components/ispindel_grainfather/` into your Home Assistant
`config/custom_components/` directory and restart.

## Setup

**Settings → Devices & Services → Add Integration → iSpindel → Grainfather**

| Setting | Notes |
|---|---|
| Grainfather server URL | From the Grainfather app: Equipment → your iSpindel → *View instructions*. Looks like `https://community.grainfather.com/iot/your-slug/ispindel` |
| Gravity unit the iSpindel reports | See [Which unit is my device using?](#which-unit-is-my-device-using) |
| Gravity unit to send to Grainfather | Match your Grainfather session. Usually SG |
| Forward every | Default 15 minutes |
| Skip forwarding if older than | Default 30 minutes. Must exceed the forward interval |

The final step shows the webhook URL. Enter it in the iSpindel's configuration
portal:

| iSpindel field | Value |
|---|---|
| Service Type | HTTP |
| Server Address | your Home Assistant host |
| Server Port | `8123` |
| Server URL | `/api/webhook/…` as shown |
| Update interval | `60` for a detailed local graph, `900` to conserve battery |

The webhook is **local-only** — it rejects requests from outside your network.

## Which unit is my device using?

Float the iSpindel in plain water and look at the reported gravity.

| Water reads | Your device emits |
|---|---|
| ~`1.000` | Specific gravity |
| ~`0.0` (including small negatives like `-0.44`) | Degrees Plato |

A negative reading in water is **not** a fault — water is 0 °P, so a Plato
calibration lands on roughly zero, and a small negative is just the calibration
error. `-0.44 °P` is about `0.9983 SG`, i.e. 0.0017 out.

If the numbers look like neither, the device is probably not floating (lying
flat reads near 90° of tilt) or the calibration polynomial was never entered.

## Entities

| Entity | Notes |
|---|---|
| `sensor.…_gravity` | Specific gravity, 4 dp |
| `sensor.…_gravity_plato` | The same reading in °P |
| `sensor.…_temperature` | Normalised to °C from the device's own C/F/K |
| `sensor.…_angle` | Tilt |
| `sensor.…_battery` | Volts (diagnostic) |
| `sensor.…_signal` | dBm (diagnostic) |
| `sensor.…_last_report` | Timestamp; raw device fields as attributes |
| `sensor.…_last_upload` | Timestamp; HTTP `status`, `ok` and `detail` as attributes |
| `sensor.…_webhook_url` | Diagnostic, disabled by default |
| `binary_sensor.…_online` | Off after three missed reports (minimum 5 minutes) |
| `switch.…_grainfather_forwarding` | Master switch for uploads |
| `button.…_upload_now` | Send immediately, ignoring the switch and timer |

The gravity sensors go **unavailable** rather than reporting nonsense when the
figure is outside a plausible fermentation range — typically because the device
is out of the liquid.

### The forwarding switch defaults to off

Deliberately. Bench-testing an uncalibrated device should not write junk into a
live brew session. Home Assistant records everything locally regardless; only
the outbound leg is gated. Turn it on when you pitch.

## Charting it

An [apexcharts-card][apexcharts] example with gravity and temperature is in
[`examples/fermentation-card.yaml`](examples/fermentation-card.yaml).

## Troubleshooting

**Nothing arrives.** Check `sensor.…_webhook_url` matches what the device is
configured with, and that the device is on the same network — the webhook is
local-only. `binary_sensor.…_online` tells you whether readings are landing.

**Grainfather is stale.** Check `sensor.…_last_upload`. Its `status` attribute
is the HTTP status; Grainfather returns **201** on success. `ok: false` with no
status means the request never completed. Also check the forwarding switch is
on and that readings are arriving at all.

**Gravity looks wrong by a factor.** You have the input unit set incorrectly.
See [above](#which-unit-is-my-device-using).

## Licence

MIT — see [LICENSE](LICENSE).

[ispindel]: https://www.ispindel.de/
[apexcharts]: https://github.com/RomRider/apexcharts-card
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://github.com/hacs/integration
