"""Validate public update assets; use Android apksigner before publishing."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import zipfile

REPO = 'baqha0717-netizen/Talking-clock.'
PACKAGE = 'com.example.talkingclock'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def lp(data, offset=0):
    size = struct.unpack_from('<I', data, offset)[0]
    end = offset + 4 + size
    require(end <= len(data), 'Truncated signing field')
    return data[offset + 4:end], end


def certificate_hash(data):
    eocd = data.rfind(b'PK\x05\x06', max(0, len(data) - 65557))
    require(eocd >= 0, 'No ZIP footer')
    require(eocd + 22 + struct.unpack_from('<H', data, eocd + 20)[0] == len(data), 'Invalid ZIP footer')
    central = struct.unpack_from('<I', data, eocd + 16)[0]
    require(data[central - 16:central] == b'APK Sig Block 42', 'No APK signing block')
    size = struct.unpack_from('<Q', data, central - 24)[0]
    start = central - size - 8
    require(start >= 0 and struct.unpack_from('<Q', data, start)[0] == size, 'Invalid signing block')
    offset = start + 8
    while offset < central - 24:
        size = struct.unpack_from('<Q', data, offset)[0]
        require(size >= 4 and offset + 8 + size <= central - 24, 'Invalid signing entry')
        kind = struct.unpack_from('<I', data, offset + 8)[0]
        if kind == 0xf05368c0:
            signers, _ = lp(data[offset + 12:offset + 8 + size])
            signer, end = lp(signers)
            require(end == len(signers), 'Expected one signer')
            signed, _ = lp(signer)
            _, offset2 = lp(signed)
            certs, _ = lp(signed, offset2)
            cert, end = lp(certs)
            require(end == len(certs), 'Expected one signing certificate')
            return hashlib.sha256(cert).hexdigest()
        offset += 8 + size
    raise ValueError('No v3 signature')


def manifest_attributes(data):
    """Read the root/uses-sdk attributes from an Android binary XML file."""
    require(struct.unpack_from('<H', data)[0] == 3, 'Not Android binary XML')
    strings = []
    result = {}
    offset = struct.unpack_from('<H', data, 2)[0]
    while offset < len(data):
        kind, header, size = struct.unpack_from('<HHI', data, offset)
        require(size >= header >= 8 and offset + size <= len(data), 'Invalid XML chunk')
        if kind == 1:
            count, _, flags, begin = struct.unpack_from('<IIII', data, offset + 8)
            def length(pos, unit):
                value = int.from_bytes(data[pos:pos + unit], 'little')
                pos += unit
                mask = 1 << (unit * 8 - 1)
                if value & mask:
                    value = ((value & (mask - 1)) << (unit * 8)) | int.from_bytes(data[pos:pos + unit], 'little')
                    pos += unit
                return value, pos
            for i in range(count):
                pos = offset + begin + struct.unpack_from('<I', data, offset + header + i * 4)[0]
                if flags & 0x100:
                    _, pos = length(pos, 1)
                    n, pos = length(pos, 1)
                    strings.append(data[pos:pos + n].decode('utf-8'))
                else:
                    n, pos = length(pos, 2)
                    strings.append(data[pos:pos + n * 2].decode('utf-16le'))
        elif kind == 0x102:
            ext = offset + header
            element = strings[struct.unpack_from('<I', data, ext + 4)[0]]
            attr_start, attr_size, count = struct.unpack_from('<HHH', data, ext + 8)
            if element in ('manifest', 'uses-sdk'):
                for i in range(count):
                    pos = ext + attr_start + i * attr_size
                    name, raw = struct.unpack_from('<II', data, pos + 4)
                    value_type = data[pos + 15]
                    value = struct.unpack_from('<I', data, pos + 16)[0]
                    result[strings[name]] = strings[raw] if raw != 0xffffffff else strings[value] if value_type == 3 else value
        offset += size
    return result


def validate(root, apksigner=None):
    public = root / 'public'
    raw = (public / 'latest.json').read_bytes()
    require(len(raw) <= 65536, 'Metadata exceeds app limit')
    meta = json.loads(raw)
    require(meta.get('schema') == 1 and meta.get('package') == PACKAGE, 'Schema/package mismatch')
    for field, lower, upper in [('versionCode', 1, 2147483647), ('minSdk', 1, 1000), ('bytes', 1, 128 * 1024 * 1024)]:
        require(type(meta[field]) is int and lower <= meta[field] <= upper, 'Invalid ' + field)
    require(re.fullmatch(r'[0-9a-f]{64}', meta['sha256']), 'Invalid hash')
    require(isinstance(meta['versionName'], str) and 0 < len(meta['versionName']) <= 48, 'Invalid version name')
    match = re.fullmatch(r'https://github\.com/' + re.escape(REPO) + r'/releases/download/([A-Za-z0-9._-]{1,64})/([A-Za-z0-9._-]{1,100}\.apk)', meta['apkUrl'])
    require(match is not None and match[1] not in ('.', '..'), 'Invalid APK URL')
    require(match[1] == 'v' + meta['versionName'], 'Tag/version mismatch')
    for field in ('notes_ru', 'notes_tg'):
        require(isinstance(meta[field], str) and 0 < len(meta[field]) <= 8000, 'Invalid release notes')
    apk = public / match[2]
    data = apk.read_bytes()
    require(len(data) == meta['bytes'], 'APK size mismatch')
    require(hashlib.sha256(data).hexdigest() == meta['sha256'], 'APK hash mismatch')
    with zipfile.ZipFile(apk) as archive:
        require(archive.testzip() is None, 'ZIP CRC mismatch')
        attrs = manifest_attributes(archive.read('AndroidManifest.xml'))
    for field, attr in [('package', 'package'), ('versionCode', 'versionCode'), ('versionName', 'versionName'), ('minSdk', 'minSdkVersion')]:
        require(meta[field] == attrs.get(attr), 'APK manifest mismatch: ' + field)
    expected = (public / 'signing-cert.sha256').read_text().strip()
    require(re.fullmatch(r'[0-9a-f]{64}', expected), 'Invalid certificate fingerprint')
    require(certificate_hash(data) == expected, 'APK certificate mismatch')
    allowed = {match[2], 'SoatiGuyo-' + meta['versionName'] + '-Install.zip', 'latest.json', 'signing-cert.sha256', 'notes-ru.txt', 'notes-tg.txt'}
    require({p.name for p in public.iterdir()} == allowed, 'Unexpected public file')
    install = public / ('SoatiGuyo-' + meta['versionName'] + '-Install.zip')
    with zipfile.ZipFile(install) as archive:
        require(archive.testzip() is None, 'Install ZIP CRC mismatch')
        require(set(archive.namelist()) == {match[2], 'Readme-RU.txt', 'Updates-RU.txt', 'Testing-5.3.18.txt', 'PublicationStatus-RU.txt', 'verification.json', 'Strings-5.3.18.json'}, 'Unexpected install ZIP entry')
        require(archive.read(match[2]) == data, 'Install ZIP APK mismatch')
    if apksigner:
        completed = subprocess.run([str(apksigner), 'verify', '--verbose', '--print-certs', str(apk)], check=True, capture_output=True, text=True)
        fingerprints = re.findall(r'Signer #\d+ certificate SHA-256 digest: ([0-9a-fA-F]+)', completed.stdout)
        require([value.lower() for value in fingerprints] == [expected], 'Verified signer mismatch')
    return meta, apk, match[1]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--apksigner', type=Path)
    args = parser.parse_args()
    meta, apk, tag = validate(args.root, args.apksigner)
    print(json.dumps({'version': meta['versionName'], 'tag': tag, 'apk': str(apk), 'sha256': meta['sha256'], 'signature_verified': bool(args.apksigner)}, ensure_ascii=False))
