"""Reassemble the approved signed APK and deterministic installation ZIP."""
import hashlib
import json
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '5.3.23'
APK = 'SoatiGuyo-' + VERSION + '-Android10plus.apk'
INSTALL = 'SoatiGuyo-' + VERSION + '-Install.zip'
DOCS = ['Readme-RU.txt', 'Updates-RU.txt', 'Testing-' + VERSION + '.txt',
        'PublicationStatus-RU.txt', 'verification.json', 'Strings-' + VERSION + '.json']


def checked(data, item):
    if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
        raise ValueError('Payload size/hash mismatch')
    return data


def assemble():
    payload = ROOT / 'release-payload'
    index = json.loads((payload / 'index.json').read_text())
    if index['schema'] != 1 or index['version'] != VERSION:
        raise ValueError('Unexpected payload version')
    if len(index['files']) != 1 or index['files'][0]['name'] != APK:
        raise ValueError('Unexpected signed artifact')
    item = index['files'][0]
    if not 1 <= len(item['parts']) <= 1000:
        raise ValueError('Unexpected part count')
    result = bytearray()
    for number, part in enumerate(item['parts']):
        expected = APK + '.parts/' + f'{number:03d}.bin'
        if part['path'] != expected:
            raise ValueError('Invalid part path/order')
        data = checked((payload / part['path']).read_bytes(), part)
        if not 1 <= len(data) <= 262144:
            raise ValueError('Invalid part length')
        result.extend(data)
        if len(result) > 128 * 1024 * 1024:
            raise ValueError('Artifact too large')
    checked(result, item)
    (ROOT / 'public' / APK).write_bytes(result)
    if [d['name'] for d in index['docs']] != DOCS:
        raise ValueError('Unexpected installation documents')
    entries = [(APK, result)]
    for doc in index['docs']:
        data = (payload / 'docs' / doc['name']).read_bytes()
        if len(data) > 65536:
            raise ValueError('Document too large')
        entries.append((doc['name'], checked(data, doc)))
    destination = ROOT / 'public' / INSTALL
    with zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, data in entries:
            info = zipfile.ZipInfo(name, (2026, 11, 9, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    if index['install']['name'] != INSTALL:
        raise ValueError('Unexpected installation archive')
    checked(destination.read_bytes(), index['install'])
    print('Verified signed APK and installation ZIP:', VERSION)


if __name__ == '__main__':
    assemble()

