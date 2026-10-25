"""Pure configuration validation shared by the API and private setup CLI."""
from urllib.parse import urlsplit
import hashlib,json

def public_origin(value,secure=False):
    origin=value.split(',')[0].strip().rstrip('/')
    try:
        parsed=urlsplit(origin);port=parsed.port
    except ValueError:raise ValueError('PUBLIC_ORIGIN must be a valid origin URL')
    if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.path or parsed.query or parsed.fragment:
        raise ValueError('PUBLIC_ORIGIN must contain only a scheme, hostname and optional port')
    if any(c.isspace() for c in origin) or '*' in origin:raise ValueError('PUBLIC_ORIGIN cannot contain whitespace or wildcards')
    loopback=parsed.hostname in ('localhost','127.0.0.1','::1')
    if parsed.scheme=='http' and not loopback:raise ValueError('OAuth requires HTTPS outside localhost')
    if parsed.scheme=='https' and not secure:raise ValueError('HTTPS OAuth requires COOKIE_SECURE=1')
    if parsed.scheme=='http' and secure:raise ValueError('Use COOKIE_SECURE=0 for local HTTP, or configure HTTPS')
    return origin

def fingerprint(settings):
    return hashlib.sha256(json.dumps({k:settings[k] for k in ('client_id','client_secret','redirect_uri')},sort_keys=True).encode()).hexdigest()
