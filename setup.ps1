$ErrorActionPreference='Stop'
Set-Location -LiteralPath $PSScriptRoot
$taskPythonCandidates=@()
$taskPythonCommand=Get-Command python -ErrorAction SilentlyContinue
if ($taskPythonCommand) { $taskPythonCandidates+=$taskPythonCommand.Source }
$taskPythonCandidates+=@("$env:LOCALAPPDATA\Programs\Python\Python311\python.exe","$env:LOCALAPPDATA\Programs\Python\Python312\python.exe","$env:LOCALAPPDATA\Programs\Python\Python313\python.exe")
$taskPython=$taskPythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $taskPython) { throw 'Install Python 3.11+ and rerun setup.ps1.' }
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) { & $taskPython -m venv .venv; if ($LASTEXITCODE) { throw 'Virtual environment creation failed' } }
$taskPipVersion=(& '.\.venv\Scripts\python.exe' -m pip --version)
if ($taskPipVersion -match '^pip 24\.[01](?:\D|$)') {
    & '.\.venv\Scripts\python.exe' -m pip --use-feature=truststore install --upgrade pip
} else {
    & '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
}
if ($LASTEXITCODE) { throw 'pip upgrade failed' }
& '.\.venv\Scripts\python.exe' -X utf8 setup.py --models
if ($LASTEXITCODE) { throw 'Setup failed; inspect the error above' }
if (-not (Test-Path -LiteralPath '.env')) { Copy-Item -LiteralPath '.env.example' -Destination '.env' }
Write-Output 'Setup complete. Add GNANI_API_KEY to .env, start Ollama, then run .\.venv\Scripts\python.exe -m streamlit run app.py'
