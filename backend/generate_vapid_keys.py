#!/usr/bin/env python3
"""
VAPID Keys Generator für Family Hub Push Notifications

Dieses Script generiert ein neues VAPID-Schlüsselpaar für Web Push Notifications.
Die Keys müssen in backend/main.py oder .env eingetragen werden.

Usage:
    python generate_vapid_keys.py
"""

try:
    from pywebpush import WebPusher
except ImportError:
    print("Error: pywebpush ist nicht installiert!")
    print("Installiere mit: pip install pywebpush")
    exit(1)

def generate_keys():
    """Generiert neue VAPID Keys"""
    print("\n" + "="*70)
    print("  VAPID Keys Generator für Family Hub")
    print("="*70 + "\n")

    print("Generiere neue VAPID-Schlüssel...\n")

    keys = WebPusher.create_keys()
    private_key = keys['private_key'].decode()
    public_key = keys['public_key'].decode()

    print("✅ Keys erfolgreich generiert!\n")
    print("="*70)
    print("PRIVATE KEY (geheim halten!):")
    print("-"*70)
    print(private_key)
    print()
    print("PUBLIC KEY:")
    print("-"*70)
    print(public_key)
    print("="*70 + "\n")

    print("📝 Nächste Schritte:\n")
    print("1. Öffne backend/main.py")
    print("2. Ersetze diese Zeilen:\n")
    print(f'   VAPID_PRIVATE_KEY = "{private_key}"')
    print(f'   VAPID_PUBLIC_KEY = "{public_key}"\n')
    print("3. Alternativ: Trage Keys in .env ein\n")
    print("4. Starte Backend neu:")
    print("   systemctl restart familyhub.service\n")

    # Save to file (optional)
    save = input("Möchtest du die Keys in einer Datei speichern? (y/n): ")
    if save.lower() == 'y':
        filename = "vapid_keys.txt"
        with open(filename, 'w') as f:
            f.write("FAMILY HUB VAPID KEYS\n")
            f.write("=" * 70 + "\n\n")
            f.write(f"VAPID_PRIVATE_KEY={private_key}\n")
            f.write(f"VAPID_PUBLIC_KEY={public_key}\n")
            f.write("\n" + "=" * 70 + "\n")
            f.write("WICHTIG: Diese Datei enthält geheime Keys!\n")
            f.write("Lösche sie nach dem Eintragen in main.py oder .env\n")
        print(f"\n✅ Keys gespeichert in: {filename}")
        print("⚠️  ACHTUNG: Lösche diese Datei nach dem Konfigurieren!\n")

    print("Fertig! 🎉\n")

if __name__ == "__main__":
    generate_keys()
