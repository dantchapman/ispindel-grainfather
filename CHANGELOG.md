# Changelog

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
