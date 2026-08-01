# Changelog

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
