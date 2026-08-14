$env:PYTHONPATH = Join-Path $PSScriptRoot 'src'
Set-Location $PSScriptRoot
python -m scenebrain.production_editor
