"""Reassemble only the two approved signed distribution artifacts."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def assemble():
    index = json.loads((ROOT / 'release-payload/index.json').read_text())
    if index['schema'] != 1 or index['version'] != '5.3.18':
        raise ValueError('Unexpected payload version')
    allowed = {'SoatiGuyo-5.3.18-Android10plus.apk', 'SoatiGuyo-5.3.18-Install.zip'}
    if {f['name'] for f in index['files']} != allowed or len(index['files']) != 2:
        raise ValueError('Unexpected payload artifacts')
    for item in index['files']:
        result = bytearray()
        if not 1 <= len(item['parts']) <= 100:
            raise ValueError('Unexpected part count')
        for number, part in enumerate(item['parts']):
            expected = item['name'] + '.parts/' + f'{number:03d}.bin'
            if part['path'] != expected:
                raise ValueError('Invalid part path/order')
            data = (ROOT / 'release-payload' / part['path']).read_bytes()
            if len(data) != part['bytes'] or hashlib.sha256(data).hexdigest() != part['sha256']:
                raise ValueError('Transport part mismatch')
            result.extend(data)
            if len(result) > 128 * 1024 * 1024:
                raise ValueError('Artifact too large')
        if len(result) != item['bytes'] or hashlib.sha256(result).hexdigest() != item['sha256']:
            raise ValueError('Reassembled artifact mismatch')
        destination = ROOT / 'public' / item['name']
        destination.write_bytes(result)
        print('Verified artifact:', item['name'], len(result), item['sha256'])


if __name__ == '__main__':
    assemble()
