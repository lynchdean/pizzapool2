import secrets
import string

_ALPHABET = string.ascii_letters + string.digits


def generate_public_id(length=10):
    return ''.join(secrets.choice(_ALPHABET) for _ in range(length))
