"""Offline high-confidence pattern candidates; never print matched values."""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PATTERNS = {
    'private_key_block': re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'provider_key_shape': re.compile(r'\bsk-[A-Za-z0-9_-]{24,}'),
    'aws_access_key_shape': re.compile(r'\bAKIA[0-9A-Z]{16}\b'),
    'literal_credential_url': re.compile(r'(?:mysql(?:\+pymysql)?|postgresql|redis)://[^\s/:{}$]+:[^\s/@{}$]+@'),
}


def main():
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode('utf-8').split('\0')
    found, scanned = [], 0
    for name in files:
        path = ROOT / name
        if not name or path.suffix.lower() not in {'.py','.ts','.vue','.md','.yaml','.yml','.toml','.json','.example','.sql','.ps1','.sh'} or not path.is_file() or path.stat().st_size > 2_000_000:
            continue
        scanned += 1
        for number, line in enumerate(path.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            for label, pattern in PATTERNS.items():
                if pattern.search(line):
                    found.append(dict(path=name, line=number, pattern=label))
    target = ROOT / '.audit-private/tracked-secret-candidates.json'
    target.write_text(json.dumps(dict(scanned_files=scanned, candidates=found), indent=2), encoding='utf-8')
    print('Tracked source files scanned:', scanned, '; candidate locations:', len(found), '; no matched values emitted')


if __name__ == '__main__':
    main()
