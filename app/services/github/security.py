import hmac
import hashlib


def verify_signature(
    payload_body: bytes, secret_token: str, signature_header: str
) -> bool:
    """
    Verify that the payload was sent from GitHub by validating the SHA256 signature.

    Args:
        payload_body: raw request body bytes
        secret_token: the webhook secret
        signature_header: the X-Hub-Signature-256 header value

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not signature_header:
        # If no signature header is present, we cannot verify authenticity.
        return False

    hash_object = hmac.new(
        secret_token.encode("utf-8"), msg=payload_body, digestmod=hashlib.sha256
    )
    expected_signature = "sha256=" + hash_object.hexdigest()

    if not hmac.compare_digest(expected_signature, signature_header):
        return False

    return True
