"""auth 규칙. 노션 'API 명세서' API-001~005."""

import hashlib
import hmac
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import jwt
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import ACCESS_TOKEN_TTL_SECONDS, REFRESH_TOKEN_TTL_SECONDS, jwt_secret
from app.core.errors import AppError
from app.modules.auth.models import RefreshToken, User
from app.modules.auth.schemas import LoginRequest, SignupRequest

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


def _email_taken(db: Session, email: str) -> bool:
    return db.scalar(select(User.id).where(User.email == email)) is not None


def signup(db: Session, req: SignupRequest, today: date | None = None) -> User:
    today = today or datetime.now(KST).date()
    if _age_on(req.birth_date, today) < MIN_SIGNUP_AGE:
        raise _validation_failed("UNDER_MIN_AGE")

    email = req.email.strip().lower()
    if _email_taken(db, email):
        raise _validation_failed("EMAIL_ALREADY_USED")

    user = User(
        provider=req.provider,
        email=email,
        password_hash=hash_password(req.password),
        nickname=req.nickname,
        birth_date=req.birth_date,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # 같은 이메일 가입이 동시에 와서 위 검사를 둘 다 통과한 경우. email 유니크 제약이 하나만 남긴다
        db.rollback()
        raise _validation_failed("EMAIL_ALREADY_USED") from None
    return user


# ---- 토큰 ----

JWT_ALGORITHM = "HS256"


@dataclass
class IssuedTokens:
    access_token: str
    access_token_expires_in: int
    refresh_token: str


def _now() -> datetime:
    return datetime.now(UTC)


def _hash_refresh(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_access_token(user_id: uuid.UUID, now: datetime | None = None) -> str:
    now = now or _now()
    claims = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(seconds=ACCESS_TOKEN_TTL_SECONDS),
    }
    return jwt.encode(claims, jwt_secret(), algorithm=JWT_ALGORITHM)


def _issue_tokens(db: Session, user_id: uuid.UUID) -> IssuedTokens:
    """access 토큰과 refresh 토큰을 만든다. refresh 토큰은 해시만 저장하고 커밋은 호출한 쪽이 한다."""
    now = _now()
    refresh = secrets.token_urlsafe(48)
    db.add(
        RefreshToken(
            user_id=user_id,
            token_hash=_hash_refresh(refresh),
            expires_at=now + timedelta(seconds=REFRESH_TOKEN_TTL_SECONDS),
        )
    )
    return IssuedTokens(
        access_token=create_access_token(user_id, now),
        access_token_expires_in=ACCESS_TOKEN_TTL_SECONDS,
        refresh_token=refresh,
    )


# 없는 이메일에도 해시 계산을 한 번 해서, 응답 시간으로 가입 여부를 알기 어렵게 한다
_DUMMY_HASH = hash_password(secrets.token_hex(16))


def login(db: Session, req: LoginRequest) -> tuple[User, IssuedTokens]:
    email = req.email.strip().lower()
    user = db.scalar(select(User).where(User.email == email, User.provider == req.provider))
    if user is None:
        verify_password(req.password, _DUMMY_HASH)
        raise AppError(401, "UNAUTHENTICATED", "이메일 또는 비밀번호가 일치하지 않습니다.")
    if not verify_password(req.password, user.password_hash):
        raise AppError(401, "UNAUTHENTICATED", "이메일 또는 비밀번호가 일치하지 않습니다.")

    tokens = _issue_tokens(db, user.id)
    db.commit()
    return user, tokens


def _revoke_refresh(db: Session, refresh_token: str) -> uuid.UUID | None:
    """유효한(만료·폐기 전) refresh 토큰을 폐기하고 user_id를 돌려준다. 없으면 None.

    조건부 UPDATE 한 번으로 처리해, 같은 토큰이 동시에 두 번 와도 하나만 성공한다.
    """
    now = _now()
    return db.scalar(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == _hash_refresh(refresh_token),
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .values(revoked_at=now)
        .returning(RefreshToken.user_id)
    )


def logout(db: Session, user_id: uuid.UUID, refresh_token: str) -> None:
    """본인의 refresh 토큰을 폐기한다 (노션 API-004).

    남의 토큰·이미 폐기된 토큰·없는 토큰이면 아무것도 바꾸지 않는다. 명세의 에러는 Bearer 401뿐이라
    이 경우도 204로 끝낸다 (같은 로그아웃 요청을 다시 보내도 결과가 같음).
    """
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == _hash_refresh(refresh_token),
            RefreshToken.user_id == user_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=_now())
    )
    db.commit()


def refresh(db: Session, refresh_token: str) -> IssuedTokens:
    """refresh 토큰 rotation: 이전 토큰을 폐기하고 새 access·refresh 토큰을 발급한다 (노션 API-003)."""
    user_id = _revoke_refresh(db, refresh_token)
    if user_id is None:
        db.rollback()
        raise AppError(401, "UNAUTHENTICATED", "refresh 토큰이 만료되었거나 폐기되었습니다.")
    tokens = _issue_tokens(db, user_id)
    db.commit()
    return tokens
