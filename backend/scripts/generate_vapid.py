"""Generiert VAPID-Schlüssel für Web Push.

Nutzung (aus ``backend/``): python -m scripts.generate_vapid
Gib die Ausgabe in deine .env unter VAPID_PRIVATE_KEY / VAPID_PUBLIC_KEY ein.

Es werden die für pywebpush und den Browser (applicationServerKey) benötigten
rohen (base64url) Schlüssel erzeugt – KEIN PEM.
"""

from __future__ import annotations

import base64


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def main() -> int:
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
    except ImportError:
        print("Die 'cryptography'-Bibliothek wird benötigt (in requirements.txt enthalten).")
        return 1

    key = ec.generate_private_key(ec.SECP256R1())
    private_value = key.private_numbers().private_value.to_bytes(32, "big")
    public_point = key.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )

    print("# In die .env eintragen:")
    print("VAPID_PRIVATE_KEY=" + _b64(private_value))
    print("VAPID_PUBLIC_KEY=" + _b64(public_point))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
