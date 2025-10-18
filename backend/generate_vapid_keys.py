#!/usr/bin/env python3
"""
VAPID Keys Generator fuer Family Hub Push Notifications

Generiert ein neues VAPID-Schluesselpaar und gibt die Base64URL-codierten Werte
aus, die in `backend/main.py` oder einer `.env` hinterlegt werden koennen.
"""

import base64

try:
    from py_vapid import Vapid
    from cryptography.hazmat.primitives import serialization
except ImportError as exc:
    print("Error: Benoetigte Pakete fehlen!")
    print("Installiere mit: pip install pywebpush py-vapid cryptography")
    raise SystemExit(1) from exc


def generate_keys() -> tuple[str, str]:
    """Erzeugt ein VAPID-Schluesselpaar und liefert (private, public)."""
    vapid = Vapid()
    vapid.generate_keys()

    private_value = vapid.private_key.private_numbers().private_value
    private_key_bytes = private_value.to_bytes(32, byteorder="big")
    public_key_bytes = vapid.public_key.public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.UncompressedPoint,
    )

    private_key = base64.urlsafe_b64encode(private_key_bytes).decode("utf-8").rstrip("=")
    public_key = base64.urlsafe_b64encode(public_key_bytes).decode("utf-8").rstrip("=")
    return private_key, public_key


def main() -> None:
    print("\n" + "=" * 70)
    print("  VAPID Keys Generator fuer Family Hub")
    print("=" * 70 + "\n")

    print("Generiere neue VAPID-Schluessel...\n")
    private_key, public_key = generate_keys()

    print("[OK] Keys erfolgreich generiert!\n")
    print("=" * 70)
    print("PRIVATE KEY (geheim halten!):")
    print("-" * 70)
    print(private_key)
    print()
    print("PUBLIC KEY:")
    print("-" * 70)
    print(public_key)
    print("=" * 70 + "\n")

    print("[INFO]  Naechste Schritte:\n")
    print("1. Öffne backend/main.py")
    print("2. Ersetze dort die Platzhalter z.B. so:\n")
    print(f'   VAPID_PRIVATE_KEY = "{private_key}"')
    print(f'   VAPID_PUBLIC_KEY = "{public_key}"\n')
    print("3. Alternativ: Trage die Werte in eine .env-Datei ein")
    print("4. Backend neu starten (z. B. systemctl restart familyhub.service)\n")

    choice = input("Soll eine temporaere Datei 'vapid_keys.txt' erstellt werden? (y/N): ")
    if choice.strip().lower() == "y":
        filename = "vapid_keys.txt"
        with open(filename, "w", encoding="utf-8") as fh:
            fh.write("FAMILY HUB VAPID KEYS\n")
            fh.write("=" * 70 + "\n")
            fh.write(f"VAPID_PRIVATE_KEY={private_key}\n")
            fh.write(f"VAPID_PUBLIC_KEY={public_key}\n")
        print(f"\n[SAVE] Keys gespeichert in: {filename}")
        print("[WARN]  Bitte nach dem Eintragen wieder loeschen!\n")

    print("Fertig [OK]\n")


if __name__ == "__main__":
    main()
