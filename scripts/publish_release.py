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
    result = subprocess.run(['gh', *args], check=False, capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError('GitHub command failed: ' + result.stderr[:4000])
    return result


def find_release(tag):
    # A draft's tag may not exist yet; /releases/tags/:tag can return404.
    releases = json.loads(gh('api', f'repos/{REPO}/releases?per_page=100').stdout)
    matches = [release for release in releases if release['tag_name'] == tag]
    if len(matches) > 1:
        raise ValueError('Ambiguous release tag')
    return matches[0] if matches else None


def publish():
    if os.environ.get('GH_REPO') != REPO:
        raise ValueError('Unexpected repository')
    meta = json.loads((ROOT / 'public/latest.json').read_text())
    tag = 'v' + meta['versionName']
    apk = urlsplit(meta['apkUrl']).path.rsplit('/', 1)[1]
    assets = [apk, 'SoatiGuyo-' + meta['versionName'] + '-Install.zip',
              'latest.json', 'notes-ru.txt', 'notes-tg.txt', 'signing-cert.sha256']
    # An already published version is immutable. Re-runs only verify live bytes.
    release = find_release(tag)
    if release is not None:
        if not release.get('draft'):
            subprocess.run(['python3', str(ROOT / 'scripts/verify_live.py')], check=True)
            print('Release already published and verified:', tag)
            return
        if release.get('target_commitish') != os.environ['GITHUB_SHA']:
            # Resume only this known draft from our interrupted5.3.22 run.
            if not (tag == 'v5.3.22' and release['id'] == 439106549
                    and release['target_commitish'] == 'b749c0c96e991d1fb542bf3468202d2a09689a2d'):
                raise ValueError('Existing draft belongs to a different commit')
    else:
        # --draft prevents latest.json from advertising an incomplete release.
        gh('release', 'create', tag, '--draft', '--target', os.environ['GITHUB_SHA'],
           '--title', 'Соати гӯё ' + meta['versionName'],
           '--notes-file', str(ROOT / 'public/notes-ru.txt'))
        release = find_release(tag)
    if release is None or not release.get('draft'):
        raise ValueError('Expected a draft release')
    if not release.get('assets'):
        gh('release', 'upload', tag, *[str(ROOT / 'public' / name) for name in assets])
    release = json.loads(gh('api', f'repos/{REPO}/releases/{release["id"]}').stdout)
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
    gh('api', '--method', 'PATCH', f'repos/{REPO}/releases/{release["id"]}',
       '-F', 'draft=false', '-f', 'make_latest=true', '-f',
       'target_commitish=' + os.environ['GITHUB_SHA'])
    subprocess.run(['python3', str(ROOT / 'scripts/verify_live.py')], check=True)
    print('Published and verified:', tag)


if __name__ == '__main__':
    publish()

