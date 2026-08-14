$env:PYTHONPATH=Join-Path $PSScriptRoot 'src';Set-Location $PSScriptRoot
@'
from pathlib import Path
from scenebrain.repair_four_transcripts import run
r=run(Path(r'E:\Movies'),Path('runtime/bb_discovery_router_v4/audio_repairs'),{(1,2),(1,4),(1,6),(1,7)})
Path('runtime/bb_discovery_router_v4/S1_REPAIR_COMPLETE.json').write_text(str(len(r)))
'@|python -
