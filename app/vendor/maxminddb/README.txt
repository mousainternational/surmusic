MaxMind DB reader (pure Python), copied from https://github.com/maxmind/MaxMind-DB-Reader-python
(commit a3888b2c182e8f3a9a4c3cbc5cddf055da0d5031, 26 Oct 2026). Licence: Apache License 2.0 (LICENSE).
Changes made for Sur Music: absolute imports `from maxminddb.x` changed to relative `from .x`; the package
version is no longer read from installed metadata. The optional C extension is not included.
Used by app/geo.py to read the free DB-IP "IP to City Lite" database (.mmdb).
