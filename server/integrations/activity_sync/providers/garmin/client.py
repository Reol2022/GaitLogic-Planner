"""Garmin client boundary.

The concrete garminconnect client is still created by the legacy provider during
the v0.9.4 migration. Keeping this module gives future provider work a stable
place to move network-only Garmin code without changing the facade contract.
"""
