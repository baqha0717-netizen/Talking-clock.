"""Publish verified APK/ZIP assets atomically through a draft GitHub release."""
import json
import os
from pathlib import Path
import subprocess
import hashlib
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
REPO = 'baqha0717-netizen/Talking-clock.'


def gh(*args, check=True):
    return subprocess.run(['gh', *args], check=check, capture_output=True, text=True)


def publish():
    if os.environ.get('GH_REPO') != REPO:
        raise ValueError('Unexpected repository')
    meta = json.loads((ROOT / 'public/latest.json').read_text())
    tag = 'v' + meta['versionName']
    apk = urlsplit(meta['apkUrl']).path.rsplit('/', 1)[1]
    assets = [apk, 'SoatiGuyo-' + meta['versionName'] + '-Install.zip',
              'latest.json', 'notes-ru.txt', 'notes-tg.txt', 'signing-cert.sha256']
    # An already published version is immutable. Re-runs only verify live bytes.
    found = gh('api', f'repos/{REPO}/releases/tags/{tag}', check=False)
    if found.returncode == 0:
        release = json.loads(found.stdout)
        if not release.get('draft'):
            subprocess.run(['python3', str(ROOT / 'scripts/verify_live.py')], check=True)
            print('Release already published and verified:', tag)
            return
        if release.get('target_commitish') != os.environ['GITHUB_SHA']:
            raise ValueError('Existing draft belongs to a different commit')
        if release.get('assets'):
            raise ValueError('Existing draft has assets; inspect before retrying')
    else:
        # --draft prevents latest.json from advertising an incomplete release.
        gh('release', 'create', tag, '--draft', '--target', os.environ['GITHUB_SHA'],
           '--title', 'Соати гӯё ' + meta['versionName'],
           '--notes-file', str(ROOT / 'public/notes-ru.txt'))
    gh('release', 'upload', tag, *[str(ROOT / 'public' / name) for name in assets])
    release = json.loads(gh('api', f'repos/{REPO}/releases/tags/{tag}').stdout)
    actual = {a['name']: a for a in release['assets']}
    if set(actual) != set(assets):
        raise ValueError('Uploaded release assets mismatch')
    for name in assets:
        if actual[name]['size'] != (ROOT / 'public' / name).stat().st_size:
            raise ValueError('Uploaded asset size mismatch: ' + name)
    with tempfile.TemporaryDirectory() as directory:
        gh('release', 'download', tag, '--dir', directory)
        for name in assets:
            remote = hashlib.sha256((Path(directory) / name).read_bytes()).digest()
            local = hashlib.sha256((ROOT / 'public' / name).read_bytes()).digest()
            if remote != local:
                raise ValueError('Uploaded asset hash mismatch: ' + name)
    gh('release', 'edit', tag, '--draft=false', '--latest')
    subprocess.run(['python3', str(ROOT / 'scripts/verify_live.py')], check=True)
    print('Published and verified:', tag)


if __name__ == '__main__':
    publish()
