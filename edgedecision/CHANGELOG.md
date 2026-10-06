# Changelog

## 1.0.1

- The integration now finds the EdgeDecision add-on by itself. In 1.0.0 it proposed `http://local-edgedecision:8765`,
  which only works for a local copy of the add-on: when installed from this repository the address is
  `http://a974f757-edgedecision:8765`. An integration already configured with a wrong address fixes itself at the
  next start of Home Assistant.
- EdgeDecision and EdgeSTT add-ons are now version 1.0.1, aligned with the integration. Home Assistant can
  offer the add-on updates through the add-on store. This is a version alignment: the decision model,
  recognition model and add-on behavior are unchanged. The automatic address correction is provided by
  the HACS integration 1.0.1; updating only the add-ons does not update the integration.

## 1.0.0

First public release: EdgeDecision model 7c (6 layers, INT8, 9 languages), EdgeSTT with NVIDIA Nemotron 3.5 ASR
Streaming, EdgeDecision integration for Assist.
