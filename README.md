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
| Unit received FROM the iSpindel | See [Which unit is my device using?](#which-unit-is-my-device-using) |
| Unit sent TO Grainfather | Leave as **Plato**. See [What unit does Grainfather want?](#what-unit-does-grainfather-want) |
| Forward every | Default 15 minutes |
| Skip forwarding if older than | Default 30 minutes. Must exceed the forward interval |
| Webhook ID (optional) | Leave blank to generate one. Set it to reuse a URL an existing iSpindel is already configured with |

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

Note that a device resting against the side of the vessel gives readings just as
steady as one floating freely — steadiness is not evidence of a good reading. If
a water test is off by more than a few thousandths, check the angle: for a given
calibration, water corresponds to one specific tilt, and a device that is caught
on something sits several degrees away from it.

## What unit does Grainfather want?

**Plato**, despite brew sessions displaying SG.

Grainfather's ingest endpoint treats the iSpindel `gravity` field as degrees
Plato and converts it for display. Send SG and it converts a second time: a real
`1.0591 SG` arrives as `1.0591 °P` and shows in the session as `1.0041`. If your
session reads a little over `1.00` while Home Assistant shows a healthy wort
gravity, that is this bug, and the fix is to set the output unit to Plato.

Note that a wrong unit still returns HTTP `201` — the endpoint accepts the
payload happily and misreads it. `sensor.…_last_upload` showing `201` confirms
delivery, not correctness. Check an actual figure in the app against
`sensor.…_gravity` once, at the start of a brew.

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

Two ready-made cards are in [`examples/`](examples):

- [`fermentation-card.yaml`](examples/fermentation-card.yaml) —
  [apexcharts-card][apexcharts], gravity and temperature on twin axes.
- [`fermentation-card-plotly.yaml`](examples/fermentation-card-plotly.yaml) —
  [plotly-graph-card][plotly], the same two series, a draggable range slider,
  and a window that follows whichever brew session is selected.

Prefer the Plotly one if you want to pick a time range. Apexcharts rebuilds its
chart on every redraw and discards any selection with it, so a device reporting
every minute resets your zoom every minute; its `brush` feature has the same
problem. Plotly's `uirevision` tells it to preserve zoom and pan across redraws,
which is why the Plotly card keeps your range and the Apex one cannot.

Both examples use aggregation rather than raw history — a fortnight of
minute-resolution readings is tens of thousands of points and will crawl on a
phone. The Plotly card uses `statistic: mean` with `period: 5minute`, which needs
long-term statistics -- Home Assistant records these automatically for these
entities.

Avoid `period: auto` on a chart you want to watch live. It picks the period
from the zoom level, so a multi-day view resolves to hourly statistics, and an
hourly bucket is not written until the hour ends -- leaving the right-hand edge
of the chart up to an hour stale, which reads as a chart that has stopped
updating. `5minute` is at most ~6 minutes behind and still only ~8,000 points
across a fortnight.

Set `extend_to_present: true` on statistics traces. It defaults to `true` for
state history but **`false` for statistics**, so without it the line stops at the
last completed bucket instead of reaching the present -- and a chart with only
one bucket so far draws nothing at all, because a line trace needs two points to
render a segment. That combination reads as "the chart is broken" when the data
is in fact arriving normally.

**Do not assign `yaxis:` on the entities, and do not put `overlaying`, `side`
or `anchor` in `layout.yaxis*`.** The Plotly card works out axis assignment and
placement itself from each trace's unit -- with SG and °C it creates `y` and
`y2` and wires up the overlay correctly. Setting either by hand conflicts with
that and the gravity trace silently stops drawing: it still appears in the
legend and the rangeslider, and the left axis still auto-ranges to its values,
but nothing is plotted. Restrict `layout.yaxis*` to cosmetics -- title,
`tickformat`, `tickfont`.

The session-scoped window comes from `hours_to_show` (fetch from the pitch of
the selected session) plus `layout.xaxis.range` (clamp the view to its start
and end). `time_offset` cannot do the job: no duration parser in the bundle
accepts a negative value, so a finished session's window cannot be shifted
backwards that way. Give `xaxis.range` LOCAL time strings, since the card plots
in local time.

Do **not** set `layout.uirevision` on the Plotly card. It manages that value
itself -- randomising it on each fetch so the chart re-ranges onto new data, and
holding it steady only while you are zoomed in, at which point a reset button
appears on the card to resume following. Your config is merged last, so a
hardcoded `uirevision` overrides that and the chart stops updating entirely.

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
[plotly]: https://github.com/dbuezas/lovelace-plotly-graph-card
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[hacs-url]: https://github.com/hacs/integration
