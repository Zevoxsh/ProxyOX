"""
Helpers for creating SSLContext for server-side TLS (with optional mTLS).
"""
import ssl
from typing import Optional




def create_server_ssl_context(
    certfile: str, keyfile: str, cafile: Optional[str] = None, require_client_cert: bool = False
) -> ssl.SSLContext:
    """Create a secure SSLContext for server sockets.


    - `certfile` / `keyfile`: server cert and private key path.
    - `cafile`: optional CA bundle to verify client certificates.
    - `require_client_cert`: if True, enforce mTLS (client cert required).
    """
    ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    # Harden: disable TLS1.0/1.1
    ctx.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1
    # Prefer server cipher order
    try:
        ctx.options |= ssl.OP_CIPHER_SERVER_PREFERENCE
    except Exception:
        pass


    ctx.load_cert_chain(certfile=certfile, keyfile=keyfile)


    if require_client_cert:
        ctx.verify_mode = ssl.CERT_REQUIRED
        if cafile:
            ctx.load_verify_locations(cafile=cafile)
        else:
    # if no cafile provided, we'll rely on system default CAs (less strict)
            pass


    # Set reasonable ciphers (platform dependent)
    try:
        ctx.set_ciphers(
            'ECDHE+AESGCM:ECDHE+CHACHA20:ECDHE+AES256:!aNULL:!eNULL:!MD5:!RC4:!DSS'
        )
    except Exception:
    # conservative fallback
        pass


    return ctx