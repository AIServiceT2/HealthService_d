"""auth 규칙. 노션 'API 명세서' API-001~005."""

import hashlib
import hmac
import secrets
from datetime import date, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.modules.auth.models import User
from app.modules.auth.schemas import SignupRequest

KST = ZoneInfo("Asia/Seoul")
MIN_SIGNUP_AGE = 14  # 14세 미만 가입 불가 (PRD 1절, 03 R16 [가정])

# 비밀번호 해시: 표준 라이브러리 scrypt (추가 패키지 없음)
_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode(), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P
    )
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt_hex, digest_hex = stored.split("$")
        digest = hashlib.scrypt(
            password.encode(), salt=bytes.fromhex(salt_hex), n=int(n), r=int(r), p=int(p)
        )
    except ValueError:
        return False
    return hmac.compare_digest(digest.hex(), digest_hex)


def _age_on(birth_date: date, today: date) -> int:
    had_birthday = (today.month, today.day) >= (birth_date.month, birth_date.day)
    return today.year - birth_date.year - (0 if had_birthday else 1)


def _validation_failed(reason: str) -> AppError:
    return AppError(400, "VALIDATION_FAILED", "입력값이 올바르지 않습니다.", {"reason": reason})


def signup(db: Session, req: SignupRequest, today: date | None = None) -> User:
    today = today or datetime.now(KST).date()
    if _age_on(req.birth_date, today) < MIN_SIGNUP_AGE:
        raise _validation_failed("UNDER_MIN_AGE")

    email = req.email.strip().lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise _validation_failed("EMAIL_ALREADY_USED")

    user = User(
        provider=req.provider,
        email=email,
        password_hash=hash_password(req.password),
        nickname=req.nickname,
        birth_date=req.birth_date,
    )
    db.add(user)
    db.commit()
    return user
