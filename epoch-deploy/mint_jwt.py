#!/usr/bin/env python3
"""
mint_jwt.py — issue a bearer token the deployed epoch-gateway will accept.

The gateway's epoch_auth.verify_jwt() requires HS256 with claims
sub / role / hospital_id, issuer https://idp.epoch.internal, audience
epoch-gateway.internal, signed with JWT_SECRET. That secret is supplied to
Cloud Run from Secret Manager (secret: jwt-secret) and its value matches the
DEFAULT below, which is the same demo secret used by Week 16.2's tests/fakes.py.

Auth issuance is a separate concern from the gateway (Session 15.2's
epoch_auth.py is the real IdP) — this is just the demo minter.

    python mint_jwt.py --role=admin --tenant=tenant_A
    python mint_jwt.py --role=viewer --tenant=tenant_B --sub=intern.42
"""
import argparse
import os
import time
import uuid

import jwt  # PyJWT

# Same default as epoch_gateway/epoch_auth.py and the deployed `jwt-secret`
# Secret Manager value. Override with JWT_SECRET to match a rotated secret.
JWT_SECRET   = os.environ.get("JWT_SECRET", "epoch-demo-secret-rotate-via-kms-in-prod")
JWT_ALG      = "HS256"
JWT_ISSUER   = "https://idp.epoch.internal"
JWT_AUDIENCE = "epoch-gateway.internal"


def main() -> None:
    p = argparse.ArgumentParser(description="Mint an EPOCH gateway bearer token.")
    p.add_argument("--role", default="admin", help="role claim (e.g. admin, viewer)")
    p.add_argument("--tenant", default="tenant_A",
                   help="hospital_id claim — the tenant the token is bound to")
    p.add_argument("--sub", default="dr.sarah.chen", help="subject claim (user id)")
    p.add_argument("--ttl", type=int, default=3600, help="lifetime in seconds")
    a = p.parse_args()

    now = int(time.time())
    payload = {
        "sub": a.sub,
        "role": a.role,
        "hospital_id": a.tenant,
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "iat": now,
        "exp": now + a.ttl,
        "jti": str(uuid.uuid4()),
    }
    print(jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG))


if __name__ == "__main__":
    main()
