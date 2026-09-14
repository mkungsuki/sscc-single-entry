"""Read two known reference endpoints without authentication or patient data."""
import json
import urllib.error
import urllib.request
from pathlib import Path

out = Path(__file__).parent / 'public-phase2-20260911'
results = []
for name in ('evaluate-choice', 'service-status'):
    url = 'https://nrefer.moph.go.th/api/beta/dmis/imc/' + name
    try:
        with urllib.request.urlopen(url, timeout=25) as response:
            data = json.load(response)
            rows = data.get('rows', [])
            if name == 'evaluate-choice':
                rows = [r for r in rows if r.get('group_type') == 'BI']
            record = {'url': url, 'http_status': response.status,
                      'statusCode': data.get('statusCode'), 'rows': rows}
    except urllib.error.HTTPError as exc:
        record = {'url': url, 'http_status': exc.code, 'rows': []}
    results.append(record)
    print(name, 'HTTP', record['http_status'], 'rows', len(record['rows']))
(out / 'reference-probe.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
