"""Authentication helpers for the Kalshi REST API.

Kalshi's v2 API uses RSA-PSS request signing.  The private key is stored as a
PEM-encoded PKCS#8 file whose path (or raw content) is supplied via environment
variables.  Every outgoing request must include three headers:

    KALSHI-ACCESS-KEY      – the API key ID
    KALSHI-ACCESS-TIMESTAMP – milliseconds since epoch (UTC)
    KALSHI-ACCESS-SIGNATURE – base-64 encoded RSA-PSS-SHA256 signature of
                              "<timestamp><method><path>"
"""

import base64
import time
from typing import Optional

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class KalshiAuth:
    """Signs outgoing Kalshi API requests with an RSA private key."""

    def __init__(self, api_key_id: str, private_key_pem: str) -> None:
        """
        Parameters
        ----------
        api_key_id:
            The key ID shown in the Kalshi dashboard.
        private_key_pem:
            The PEM-encoded RSA private key (PKCS#8 format).
        """
        self._key_id = api_key_id
        self._private_key = serialization.load_pem_private_key(
            private_key_pem.encode() if isinstance(private_key_pem, str) else private_key_pem,
            password=None,
        )

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    def build_headers(self, method: str, path: str) -> dict:
        """Return the three authentication headers for a request.

        Parameters
        ----------
        method:
            HTTP verb in upper-case, e.g. ``"GET"``.
        path:
            Request path including query string, e.g. ``"/trade-api/v2/markets"``.
        """
        timestamp_ms = str(int(time.time() * 1000))
        message = f"{timestamp_ms}{method.upper()}{path}"
        signature = self._sign(message)
        return {
            "KALSHI-ACCESS-KEY": self._key_id,
            "KALSHI-ACCESS-TIMESTAMP": timestamp_ms,
            "KALSHI-ACCESS-SIGNATURE": signature,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _sign(self, message: str) -> str:
        """Return a base-64 encoded RSA-PSS-SHA256 signature."""
        raw_sig = self._private_key.sign(
            message.encode(),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        return base64.b64encode(raw_sig).decode()
