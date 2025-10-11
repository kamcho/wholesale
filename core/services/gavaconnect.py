import base64
from typing import Tuple, Dict, Any
from django.conf import settings
import requests, os


class GavaConnectError(Exception):
    pass


def _build_basic_auth_header(client_key: str, client_secret: str) -> str:
    token = f"{client_key}:{client_secret}".encode("utf-8")
    b64 = base64.b64encode(token).decode("ascii")
    return f"Basic {b64}"


def get_access_token() -> Tuple[str, int]:
    """Generate access token using client credentials.

    Returns (access_token, expires_in_seconds)
    """
    base_url = os.getenv("GAVA_BASE_URL", "https://sbx.kra.go.ke")
    client_key = os.getenv("GAVA_CLIENT_KEY")
    client_secret = os.getenv("GAVA_CLIENT_SECRET")

    if not client_key or not client_secret:
        raise GavaConnectError("Missing GavaConnect client credentials")

    url = f"{base_url}/v1/token/generate"
    params = {"grant_type": "client_credentials"}
    headers = {
        "Authorization": _build_basic_auth_header(client_key, client_secret),
        "Accept": "application/json",
    }
    try:
        r = requests.get(url, params=params, headers=headers, timeout=15)
        r.raise_for_status()
        data = r.json()
        access_token = data.get("access_token")
        expires_in = int(data.get("expires_in") or 0)
        if not access_token:
            raise GavaConnectError("Token response missing access_token")
        # Debug: log access token and expiry
        print(f"[Gava TOKEN] access_token={access_token!r} expires_in={expires_in}")
        return access_token, expires_in
    except requests.RequestException as e:
        # Try to surface server message
        msg = getattr(e.response, 'text', str(e)) if hasattr(e, 'response') and e.response is not None else str(e)
        raise GavaConnectError(f"Token request failed: {msg}")


def _pin_check_request(access_token: str, taxpayer_type: str, taxpayer_id: str) -> Dict[str, Any]:
    base_url = getattr(settings, "GAVA_BASE_URL", "https://sbx.kra.go.ke")
    url = f"{base_url}/checker/v1/pin"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    # Defensive normalization
    ttype = (taxpayer_type or "").strip().upper()
    tid = (taxpayer_id or "").strip()
    json_body = {
        "TaxpayerType": ttype,
        "TaxpayerID": tid,
    }
    try:
        # Debug: log request payload
        print(f"[Gava PIN REQ] url={url} json_body={json_body}")
        r = requests.post(url, json=json_body, headers=headers, timeout=20)
        # Debug: log upstream response
        try:
            print(f"[Gava PIN RESP] status={r.status_code} body={r.text!r}")
        except Exception:
            pass
        # If the API returns an error body with 4xx, return JSON for caller to handle
        if r.status_code >= 400:
            try:
                return r.json()
            except ValueError:
                raise GavaConnectError(f"PIN check failed {r.status_code}: {r.text}")
        return r.json()
    except requests.RequestException as e:
        msg = getattr(e.response, 'text', str(e)) if hasattr(e, 'response') and e.response is not None else str(e)
        raise GavaConnectError(f"PIN check error: {msg}")


def check_pin(taxpayer_type: str, taxpayer_id: str) -> Dict[str, Any]:
    """Full flow: generate token then check PIN; returns response JSON."""
    access_token, _ = get_access_token()
    return _pin_check_request(access_token, taxpayer_type, taxpayer_id)


def pin_check_by_id(taxpayer_type: str, taxpayer_id: str) -> Dict[str, Any]:
    """Backward-compatible alias that performs the full flow."""
    return check_pin(taxpayer_type, taxpayer_id)


# ==============================
# Pending Returns (by PIN & obligation)
# ==============================
def _pending_returns_request(access_token: str, tax_payer_pin: str, obligation_id: str) -> Dict[str, Any]:
    base_url = getattr(settings, "GAVA_BASE_URL", "https://sbx.kra.go.ke")
    url = f"{base_url}/checker/v1/pendingreturn"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    json_body = {
        "taxPayerPin": (tax_payer_pin or "").strip().upper(),
        "obligationId": str(obligation_id).strip(),
    }
    try:
        print(f"[Gava PENDING REQ] url={url} json_body={json_body}")
        r = requests.post(url, json=json_body, headers=headers, timeout=20)
        try:
            print(f"[Gava PENDING RESP] status={r.status_code} body={r.text!r}")
        except Exception:
            pass
        if r.status_code >= 400:
            try:
                return r.json()
            except ValueError:
                raise GavaConnectError(f"Pending returns failed {r.status_code}: {r.text}")
        return r.json()
    except requests.RequestException as e:
        msg = getattr(e.response, 'text', str(e)) if hasattr(e, 'response') and e.response is not None else str(e)
        raise GavaConnectError(f"Pending returns error: {msg}")


def pending_returns(tax_payer_pin: str, obligation_id: str) -> Dict[str, Any]:
    """Full flow: token then Pending Returns API."""
    access_token, _ = get_access_token()
    return _pending_returns_request(access_token, tax_payer_pin, obligation_id)
