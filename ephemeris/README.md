# Swiss Ephemeris data files

`sepl_18.se1` (planets), `semo_18.se1` (Moon) and `seas_18.se1` (asteroids,
which is what Chiron needs) cover 1800-2400.

They are committed rather than downloaded at build time because without them
pyswisseph does not fail - it silently falls back to its built-in Moshier
ephemeris, so the app would keep working while quietly using a different source.
The difference is small (under an arc second for the planets, 3.5" for the true
node) but Chiron is unavailable entirely, and a silent switch of data source is
not something to leave to chance on a deploy.

Source: https://github.com/aloistr/swisseph/tree/master/ephe
The Swiss Ephemeris is © Astrodienst AG, dual-licensed under the AGPL and a
commercial licence; these files are redistributed here under the AGPL.
