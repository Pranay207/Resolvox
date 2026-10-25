$ErrorActionPreference='Stop'
Set-Location -LiteralPath 'C:\Users\Shiva\Downloads\ESD'
$env:PYTHONIOENCODING='utf-8'
$env:PYTHONUTF8='1'
& '.\.venv\Scripts\python.exe' -u -X utf8 'tmp\run_source_first_pilots.py' *> 'tmp\source_first_pilot.log'
$pilotExit=$LASTEXITCODE
[PSCustomObject]@{exit_code=$pilotExit;finished_at_utc=[DateTime]::UtcNow.ToString('o')} | ConvertTo-Json | Set-Content -LiteralPath 'tmp\source_first_pilot_done.json' -Encoding UTF8