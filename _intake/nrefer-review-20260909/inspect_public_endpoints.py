"""Read public JS bundles only; no API requests, cookies or authentication."""
import concurrent.futures
import re
import urllib.request
import sys

BASE = 'https://nrefer.moph.go.th/beta/'
TERMS = ('user-status', 'user-by-key', 'thaid/authenticated', 'evaluate-choice', 'modified-rankin-scale')
if len(sys.argv) > 1:
    TERMS = tuple(sys.argv[1:])

def read(name):
    with urllib.request.urlopen(BASE + name, timeout=30) as response:
        return name, response.read().decode('utf-8')

if __name__ == '__main__':
    pending = {'main-CLHAXOP7.js'}
    seen = set()
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        while pending:
            batch = sorted(pending - seen)
            if not batch:
                break
            pending = set()
            for name, source in pool.map(read, batch):
                seen.add(name)
                pending.update(re.findall(r'chunk-[A-Z0-9]+\.js', source))
                for term in TERMS:
                    for match in re.finditer(re.escape(term), source):
                        print(name, term, source[max(0, match.start()-400):match.end()+650], flush=True)
    print('Public JS bundles inspected:', len(seen))
