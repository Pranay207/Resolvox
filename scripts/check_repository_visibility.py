"""Read-only anonymous GitHub access check; never changes repository visibility."""
from pathlib import Path
import json,datetime,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parents[1]
record={'repository_url':'https://github.com/Pranay207/Resolvox','checked_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'method':'anonymous_github_api','is_public':False}
try:
 request=urllib.request.Request('https://api.github.com/repos/Pranay207/Resolvox',headers={'User-Agent':'Resolvox-submission-check','Accept':'application/vnd.github+json'})
 with urllib.request.urlopen(request,timeout=15) as response:
  value=json.load(response);record.update(http_status=response.status,is_public=value.get('private') is False and value.get('full_name','').casefold()=='pranay207/resolvox')
except urllib.error.HTTPError as error:record.update(http_status=error.code,reason='Repository is not accessible anonymously')
except (OSError,ValueError):record.update(http_status=None,reason='Public-access check could not complete')
(ROOT/'sample_outputs/repository_visibility.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record))
