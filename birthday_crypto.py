import base64
import json
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


def _key(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=2**17, r=8, p=1)
    return base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))


def encrypt(data, passphrase: str) -> bytes:
    salt = os.urandom(16)
    token = Fernet(_key(passphrase, salt)).encrypt(json.dumps(data).encode())
    return salt + token


def decrypt(blob: bytes, passphrase: str):
    salt, token = blob[:16], blob[16:]
    return json.loads(Fernet(_key(passphrase, salt)).decrypt(token))
