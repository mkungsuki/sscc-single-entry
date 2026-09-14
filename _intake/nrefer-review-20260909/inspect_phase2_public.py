"""Fetch public nRefer assets only; no cookies, tokens, or patient API calls."""
import concurrent.futures
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE = 'https://nrefer.moph.go.th/beta/'
OUT = Path(__file__).parent / 'public-phase2-20260911'
TERMS = ('save-dmis-evaluate', 'save-hospcare', 'save-imc-evaluate',
         'save-visit', 'evaluate-choice', 'service-status', 'disc_healthrisk',
         'dmis-disc-evaluate', 'checkHN()', 'checkAN()', 'getPerson()',
         'savePatient()', 'addHospcare()', 'patient_ref', 'caregiver')

def read(name):
    with urllib.request.urlopen(BASE + name, timeout=30) as response:
        return name, response.read()

if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    _, html = read('')
    (OUT / 'index.html').write_bytes(html)
    pending = set(re.findall(r'(?:main|chunk)-[A-Z0-9]+\.js', html.decode()))
    seen, manifest, excerpts = set(), [], []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        while pending:
            batch = sorted(pending - seen)
            if not batch:
                break
            pending = set()
            for name, raw in pool.map(read, batch):
                seen.add(name)
                source = raw.decode('utf-8')
                pending.update(re.findall(r'chunk-[A-Z0-9]+\.js', source))
                (OUT / name).write_bytes(raw)
                manifest.append({'url': BASE + name, 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
                found = [term for term in TERMS if term in source]
                if found:
                    print(name, ', '.join(found), flush=True)
                for term in found:
                    for match in re.finditer(re.escape(term), source):
                        excerpts.append({'file': name, 'term': term, 'offset': match.start(),
                                         'context': source[max(0, match.start()-220):match.end()+950]})
    (OUT / 'manifest.json').write_text(json.dumps({'fetched_utc': datetime.now(timezone.utc).isoformat(), 'files': manifest}, indent=2), encoding='utf-8')
    (OUT / 'excerpts.json').write_text(json.dumps(excerpts, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Public bundles:', len(seen), flush=True)
