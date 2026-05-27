from types import SimpleNamespace

from app.security import (
    SECRET_PREFIX,
    decrypt_secret,
    encrypt_secret,
    is_encrypted_secret,
    needs_secret_migration,
)


TEST_SETTINGS = SimpleNamespace(
    model_config_encryption_key="MDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWY="
)


def test_encrypt_secret_prefixes_ciphertext():
    encrypted = encrypt_secret("secret-key", TEST_SETTINGS)

    assert encrypted.startswith(SECRET_PREFIX)
    assert encrypted != "secret-key"
    assert is_encrypted_secret(encrypted) is True


def test_encrypt_secret_round_trips_with_decrypt_secret():
    encrypted = encrypt_secret("secret-key", TEST_SETTINGS)

    assert decrypt_secret(encrypted, TEST_SETTINGS) == "secret-key"


def test_empty_secret_round_trips_to_empty_string():
    encrypted = encrypt_secret("", TEST_SETTINGS)

    assert encrypted == ""
    assert decrypt_secret(encrypted, TEST_SETTINGS) == ""


def test_plaintext_secret_is_marked_for_migration():
    assert needs_secret_migration("legacy-secret") is True
    assert needs_secret_migration("") is False
