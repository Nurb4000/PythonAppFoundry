import os
import logging

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)

_key = None


def _get_key_path(app):
    return os.path.join(app.instance_path, 'credential.key')


def init_credential_store(app):
    global _key
    key_path = _get_key_path(app)
    os.makedirs(app.instance_path, exist_ok=True)
    if os.path.exists(key_path):
        with open(key_path, 'rb') as f:
            _key = f.read().strip()
    else:
        _key = Fernet.generate_key()
        with open(key_path, 'wb') as f:
            f.write(_key)
        os.chmod(key_path, 0o600)
        logger.info(f'Created credential encryption key at {key_path}')


def _get_cipher():
    if _key is None:
        raise RuntimeError('Credential store not initialized. Call init_credential_store(app) first.')
    return Fernet(_key)


def encrypt_value(plaintext):
    cipher = _get_cipher()
    return cipher.encrypt(plaintext.encode('utf-8')).decode('utf-8')


def decrypt_value(ciphertext):
    cipher = _get_cipher()
    return cipher.decrypt(ciphertext.encode('utf-8')).decode('utf-8')
