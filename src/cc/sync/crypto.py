"""
Sync payload encryption — AES-256-GCM.

Key is derived from the API key via SHA-256. Both client and server
know the API key, so no extra config is needed.

Wire format: {"e": "<base64 ciphertext>", "n": "<base64 nonce>", "t": "<base64 tag>"}
"""
import base64
import hashlib
import json

from Cryptodome.Cipher import AES


def _derive_key(api_key: str) -> bytes:
    return hashlib.sha256(api_key.encode()).digest()


def encrypt(payload: dict, api_key: str) -> dict:
    key = _derive_key(api_key)
    plaintext = json.dumps(payload).encode()
    cipher = AES.new(key, AES.MODE_GCM)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    return {
        "e": base64.b64encode(ciphertext).decode(),
        "n": base64.b64encode(cipher.nonce).decode(),
        "t": base64.b64encode(tag).decode(),
    }


def decrypt(envelope: dict, api_key: str) -> dict:
    key = _derive_key(api_key)
    ciphertext = base64.b64decode(envelope["e"])
    nonce = base64.b64decode(envelope["n"])
    tag = base64.b64decode(envelope["t"])
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    return json.loads(plaintext)


def is_encrypted(data: dict) -> bool:
    return "e" in data and "n" in data and "t" in data
