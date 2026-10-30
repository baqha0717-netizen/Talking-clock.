"""Require Android's apksigner before allowing any release upload."""
import json
import os
from pathlib import Path
import re
from check_release import validate

root = Path(__file__).resolve().parents[1]
home = os.environ.get('ANDROID_HOME') or os.environ.get('ANDROID_SDK_ROOT')
if not home:
    raise RuntimeError('Android SDK not available')
versions = sorted((Path(home) / 'build-tools').glob('*/apksigner'),
                  key=lambda p: tuple(int(n) for n in re.findall(r'\d+', p.parent.name)))
if not versions:
    raise RuntimeError('apksigner not available')
meta, apk, tag = validate(root, versions[-1])
print(json.dumps({'version': meta['versionName'], 'tag': tag, 'apk': str(apk),
                  'sha256': meta['sha256'], 'signature_verified': True}))
