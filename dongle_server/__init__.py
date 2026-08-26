"""autobrain-dongle-server — firmware release & distribution service (AUT-1673).

Owns: firmware manifests, MinIO signed blob URLs, serial-number whitelist,
paid-account gate (delegated to the AutoBrain backend), and the ops web GUI.
The AutoBrain backend is a thin paid-gate facade (require_premium) that proxies
manifest operations here via the internal API; manifest truth lives ONLY here.
"""
