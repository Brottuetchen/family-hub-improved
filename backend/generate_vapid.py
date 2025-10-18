#!/usr/bin/env python3
"""Generate VAPID keys for Web Push notifications."""

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import base64
import json

# Generate private key
private_key = ec.generate_private_key(ec.SECP256R1(), default_backend())

# Get private key bytes
private_value = private_key.private_numbers().private_value
private_key_bytes = private_value.to_bytes(32, byteorder='big')

# Get public key bytes (uncompressed format)
public_numbers = private_key.public_key().public_numbers()
x_bytes = public_numbers.x.to_bytes(32, byteorder='big')
y_bytes = public_numbers.y.to_bytes(32, byteorder='big')
public_key_bytes = b'\x04' + x_bytes + y_bytes

# Convert to base64 URL-safe encoding (without padding)
private_key_b64 = base64.urlsafe_b64encode(private_key_bytes).decode('utf-8').rstrip('=')
public_key_b64 = base64.urlsafe_b64encode(public_key_bytes).decode('utf-8').rstrip('=')

# Create the JSON structure
vapid_keys = {
    "private_key": private_key_b64,
    "public_key": public_key_b64
}

# Print the keys
print("Generated VAPID Keys:")
print("=" * 80)
print(json.dumps(vapid_keys, indent=2))
print("=" * 80)
print("\nPrivate Key:", private_key_b64)
print("Public Key:", public_key_b64)
print("\nSave these to backend/vapid_keys.json")
