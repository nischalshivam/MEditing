$env:PYTHONPATH=Join-Path $PSScriptRoot 'src';Set-Location $PSScriptRoot
@'
from pathlib import Path
from scenebrain.router_v4 import align_all
r=align_all(Path(r'E:\Movies'),Path('runtime/bb_discovery_router_v4'))
Path('runtime/bb_discovery_router_v4/ALIGNMENT_COMPLETE.json').write_text(str(len(r)))
'@|python -
