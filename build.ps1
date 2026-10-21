# Build dist/KeyOverlay.exe (single file, no console window).
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install --disable-pip-version-check -q -r requirements-dev.txt
python -m PyInstaller --noconfirm --clean --onefile --noconsole `
    --name KeyOverlay `
    KeyOverlay.pyw
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed" }

Get-Item dist/KeyOverlay.exe | Select-Object Name, @{n = "MB"; e = { [math]::Round($_.Length / 1MB, 1) } }
