import time
import logging
from typing import Any

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt

from app.core.config import settings

# Dev bypass: Clerk user IDs that always receive role="admin" without Clerk metadata.
# Populate via ADMIN_USER_IDS env var (comma-separated).
# Find your user ID at: https://dashboard.clerk.com/users or via GET /api/v1/me
_ADMIN_USER_IDS: frozenset[str] = frozenset(
    uid.strip()
    for uid in (settings.admin_user_ids or "").split(",")
    if uid.strip()
)

logger = logging.getLogger(__name__)

security = HTTPBearer()

# In-memory JWKS cache: avoids fetching Clerk on every request.
_jwks_cache: dict[str, Any] = {"keys": [], "fetched_at": 0.0}
_JWKS_TTL = 3600.0  # 1 hour


def _jwks_url() -> str:
    if settings.clerk_jwt_issuer:
        return f"{settings.clerk_jwt_issuer.rstrip('/')}/.well-known/jwks.json"
    raise RuntimeError(
        "CLERK_JWT_ISSUER não configurado. "
        "Defina-o via variável de ambiente ou Vault (path: secret/estudohub)."
    )


async def _get_jwks() -> list[dict]:
    now = time.monotonic()
    if _jwks_cache["keys"] and (now - _jwks_cache["fetched_at"]) < _JWKS_TTL:
        return _jwks_cache["keys"]

    url = _jwks_url()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    keys: list[dict] = resp.json().get("keys", [])
    _jwks_cache["keys"] = keys
    _jwks_cache["fetched_at"] = now
    logger.debug("JWKS atualizado de %s (%d chaves)", url, len(keys))
    return keys


async def verify_clerk_token(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    FastAPI dependency. Valida o JWT do Clerk via JWKS (RS256).
    Retorna o payload decodificado; 'sub' contém o Clerk user ID.
    """
    token = credentials.credentials

    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        keys = await _get_jwks()
        matching = [k for k in keys if k.get("kid") == kid]

        if not matching:
            # Chave não encontrada — pode ser rotação. Invalida cache e tenta de novo.
            _jwks_cache["fetched_at"] = 0.0
            keys = await _get_jwks()
            matching = [k for k in keys if k.get("kid") == kid]

        if not matching:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Chave de assinatura do token não encontrada.",
            )

        payload: dict = jwt.decode(
            token,
            matching[0],
            algorithms=["RS256"],
            issuer=settings.clerk_jwt_issuer or None,
            options={
                "verify_aud": False,   # Clerk usa 'azp', não 'aud'
                "verify_exp": True,
                "verify_iss": bool(settings.clerk_jwt_issuer),
            },
        )

        # Dev bypass: inject admin role for configured user IDs
        if payload.get("sub") in _ADMIN_USER_IDS:
            payload["role"] = "admin"

        return payload

    except ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado.",
        )
    except JWTError as exc:
        logger.warning("Falha na validação JWT: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido.",
        )
    except RuntimeError as exc:
        logger.error("Configuração de auth ausente: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        )
