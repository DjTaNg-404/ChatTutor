"""密码哈希与 JWT 单元测试（不依赖数据库）。"""

from app.core.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


def test_bcrypt_hash_and_verify_roundtrip():
    raw = "my-secure-password-123"
    h = hash_password(raw)
    assert h != raw
    assert verify_password(raw, h) is True
    assert verify_password("wrong", h) is False


def test_jwt_create_and_decode():
    token = create_access_token(user_id="user-uuid-1", username="alice")
    payload = decode_access_token(token)
    assert payload is not None
    assert payload.get("sub") == "user-uuid-1"
    assert payload.get("username") == "alice"


def test_jwt_invalid_returns_none():
    assert decode_access_token("not.a.valid.jwt") is None
