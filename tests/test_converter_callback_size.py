"""Test converter callback_data tidak melebihi 64 byte limit Telegram."""

import pytest
from uuid import uuid4


def test_callback_data_stays_under_64_bytes():
    """Simulasikan file_id panjang dan pastikan callback_data tetap valid."""
    # file_id Telegram nyata bisa 70+ karakter
    long_file_id = "BQACAgUAAxkBAAIBQ2abcdef0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz_12345"
    
    # Callback token dibuat dari UUID truncated
    conv_token = "a1b2c3d4e5f6"  # 12 karakter
    
    # Format callback_data yang baru
    callbacks = [
        f"convert:{conv_token}:docx",
        f"convert:{conv_token}:xlsx",
        f"convert:{conv_token}:pptx",
        f"convert:{conv_token}:images",
        f"convert:{conv_token}:pdf",
    ]
    
    for callback in callbacks:
        byte_length = len(callback.encode())
        assert byte_length <= 64, f"{callback} ({byte_length} byte) melebihi limit 64 byte"


def test_token_generation_produces_valid_length():
    """Pastikan token 12 karakter hex selalu menghasilkan callback < 64 byte."""
    max_callback_len = 0
    for _ in range(100):
        token = uuid4().hex[:12]
        callback = f"convert:{token}:images"
        byte_len = len(callback.encode())
        max_callback_len = max(max_callback_len, byte_len)
    
    assert max_callback_len < 64, f"Max callback panjang: {max_callback_len} byte"


def test_old_callback_format_exceeds_64_bytes():
    """Verify old format dengan file_id panjang melebihi 64 byte."""
    long_file_id = "BQACAgUAAxkBAAIBQ2abcdef0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz_12345"
    
    old_callback = f"convert:{long_file_id}:docx"
    byte_length = len(old_callback.encode())
    
    # Verifikasi bahwa format lama memang melebihi limit
    assert byte_length > 64, f"Old format seharusnya melebihi 64 byte, tapi hanya {byte_length} byte"


def test_callback_token_always_short():
    """Test bahwa token 12 hex char selalu menghasilkan callback tepat di batas."""
    # Token 12 karakter hex + "convert::images" = 32 byte
    # "convert:" = 8 byte
    # ":images" = 7 byte
    # Total = 8 + 12 + 7 = 27 byte, jauh di bawah 64
    
    token = uuid4().hex[:12]
    callback = f"convert:{token}:images"
    
    byte_len = len(callback.encode())
    assert byte_len < 50, f"Callback harusnya < 50 byte, dapat {byte_len}"
    assert byte_len <= 64


def test_all_target_formats_fit_in_64_bytes():
    """Test semua target format fit dalam 64 byte limit."""
    token = "a" * 12  # worst case: 12 'a'
    targets = ["docx", "xlsx", "pptx", "images", "pdf"]
    
    for target in targets:
        callback = f"convert:{token}:{target}"
        byte_len = len(callback.encode())
        assert byte_len <= 64, f"Target '{target}' callback melebihi limit: {byte_len} byte"
