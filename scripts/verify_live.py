"""Compare the published metadata and APK with the checked local release."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]


def allowed(url):
    parsed = urlparse(url)
    return (parsed.scheme == 'https' and parsed.port in (None, 443)
            and parsed.username is None and parsed.password is None
            and (parsed.hostname == 'github.com' or (parsed.hostname or '').endswith('.githubusercontent.com')))


class Redirects(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, url):
        if not allowed(url):
            raise ValueError('Unexpected download origin')
        return super().redirect_request(request, fp, code, msg, headers, url)


def download(url, limit):
    if not allowed(url):
        raise ValueError('Unexpected download origin')
    with build_opener(Redirects()).open(Request(url, headers={'User-Agent': 'SoatiGuyo-release-check'}), timeout=60) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Download exceeds expected limit')
    return data


if __name__ == '__main__':
    expected = (ROOT / 'public/latest.json').read_bytes()
    actual = download('https://github.com/baqha0717-netizen/Talking-clock./releases/latest/download/latest.json', 65536)
    if actual != expected:
        raise ValueError('Published metadata mismatch')
    metadata = json.loads(actual)
    apk = download(metadata['apkUrl'], metadata['bytes'])
    if len(apk) != metadata['bytes'] or hashlib.sha256(apk).hexdigest() != metadata['sha256']:
        raise ValueError('Published APK mismatch')
    name = 'SoatiGuyo-' + metadata['versionName'] + '-Install.zip'
    url = metadata['apkUrl'].rsplit('/', 1)[0] + '/' + name
    expected_zip = (ROOT / 'public' / name).read_bytes()
    actual_zip = download(url, len(expected_zip))
    if actual_zip != expected_zip:
        raise ValueError('Published install ZIP mismatch')
    print('Public metadata, APK and install ZIP verified:', metadata['versionName'])
