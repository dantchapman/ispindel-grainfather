# Changelog

## 1.7.0

- ABV now uses the Balling-derived formula rather than (OG-FG)*131.25, which
  under-reads by 0.2% at 6.5% and 0.8% at 10%

## 1.6.0

- OG and FG can be typed in, overriding the iSpindel snapshot: a floating
  hydrometer accumulates yeast and drifts, so the hydrometer sample at bottling
  is usually the figure worth keeping
- Editable fields now act on the session in view, matching the sensors

## 1.5.0

- Brew sessions: named fermentations with a recipe link, pitch/end times, OG and
  FG, stored in HA and selectable so charts and figures can be scoped to one brew
- New "Brew Session" device with select, text, button and sensor entities
- Services: start_session, end_session, delete_session

## 1.4.0

- Default the outbound unit to Plato: Grainfather reads the gravity field as
  Plato, so sending SG was converted a second time and understated gravity

## 1.3.0

- Signal strength is now enabled by default; a fermenter in a fridge is exactly
  where RSSI matters, and it is the first thing to check when reports stop

## 1.2.0

- Widen the lower plausibility bound from -5 °P to -20 °P; the old floor would
  have hidden legitimate high-ABV dry ferments finishing below 0.981 SG

## 1.1.0

- Webhook ID can be chosen at setup or changed later, so an existing iSpindel
  can keep the URL it is already configured with
- Clearer unit labels ("Unit received FROM the iSpindel" / "Unit sent TO
  Grainfather") after both were easy to set backwards

## 1.0.0

Initial release.

- Local-push webhook receiver for iSpindel HTTP reports
- Gravity, temperature, angle, battery, signal, last-report and last-upload entities
- Automatic Plato ↔ SG conversion, configurable in both directions
- Scheduled forwarding to a Grainfather brew session, with a staleness guard
- Forwarding switch (defaults to off) and an "Upload now" button
- UI configuration with an options flow
