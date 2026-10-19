"""Bounded provider HTTP and paid task journaling. No credentials on disk."""
import json
import re
import time
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlparse
from .schema import digest
from .storage import atomic_json, read_json
from .process import check_cancel


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def https_handler():
    import ssl
    import truststore
    return urllib.request.HTTPSHandler(context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT))


def request(url, authorization, payload=None):
    req = urllib.request.Request(url, data=json.dumps(payload).encode() if payload is not None else None,
        headers={'Authorization':authorization, 'Content-Type':'application/json', 'Accept':'application/json'})
    try:
        with urllib.request.build_opener(NoRedirect, https_handler()).open(req, timeout=60) as response:
            result = json.loads(response.read(4*1024*1024))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'Provider API returned HTTP {exc.code}. Check API scope, credits and selected model/avatar. Paid submissions are not retried automatically.') from None
    except (OSError, ValueError):
        raise RuntimeError('Provider connection or JSON decoding failed. Check the saved submission before retrying.') from None
    if not isinstance(result, dict):
        raise RuntimeError('Provider returned an unexpected response.')
    return result


def trusted_media(url, domains):
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or '').lower()
        return parsed.scheme == 'https' and not parsed.username and not parsed.password and parsed.port in (None,443) and any(host == d or host.endswith('.'+d) for d in domains)
    except (ValueError, TypeError):
        return False


def download(url, output, domains, cancel_file=None):
    if not trusted_media(url, domains):
        raise ValueError('Provider returned an unsupported media host; use the provider dashboard to inspect the result.')
    class Redirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            if not trusted_media(newurl, domains):
                raise ValueError('Unsupported provider media redirect.')
            return super().redirect_request(req, fp, code, msg, headers, newurl)
    temporary = output.with_suffix('.partial')
    try:
        with urllib.request.build_opener(Redirect, https_handler()).open(url, timeout=120) as response, temporary.open('wb') as target:
            size = 0
            while True:
                check_cancel(cancel_file)
                chunk = response.read(1024*1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > 500*1024*1024:
                    raise ValueError('Provider media exceeds 500 MB.')
                target.write(chunk)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)


def task(root, provider, payload, submit, poll, identifier, status, completed, failed, media_url, domains, cancel_file=None):
    folder = Path(root)/'cache'/provider/digest(payload)
    folder.mkdir(parents=True, exist_ok=True)
    output, journal = folder/'video.mp4', folder/'submission.json'
    check_cancel(cancel_file)
    if journal.exists():
        saved = read_json(journal)
        task_id = saved.get('task_id')
        if not task_id:
            raise RuntimeError('Previous '+provider+' submission has an unknown outcome. Check the dashboard before retrying. Journal: '+str(journal))
    else:
        try:
            with journal.open('x', encoding='utf-8') as stream:
                json.dump({'state':'submitting','payload_hash':digest(payload)}, stream)
        except FileExistsError:
            raise RuntimeError('A matching cloud submission is already starting; resume it after the task ID is recorded.') from None
        response = submit(payload)
        task_id = identifier(response)
        if not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,200}', task_id):
            raise RuntimeError('Provider returned no valid task ID. Check the dashboard before retrying.')
        saved = {'task_id':task_id, 'state':'submitted','payload_hash':digest(payload)}
        atomic_json(journal, saved)
    deadline = time.monotonic()+1800
    while time.monotonic() < deadline:
        check_cancel(cancel_file)
        response = poll(task_id)
        state = status(response)
        if state in failed:
            raise RuntimeError(provider+' task '+state+'. Inspect the provider dashboard; no replacement was submitted.')
        if state in completed:
            if not output.exists():
                download(media_url(response), output, domains, cancel_file)
            return output, {'provider':provider, 'task_id':task_id, 'payload_sha256':digest(payload)}
        for _ in range(30):
            check_cancel(cancel_file)
            time.sleep(1)
    raise RuntimeError(provider+' is still processing. Resume to reuse the saved task ID.')
