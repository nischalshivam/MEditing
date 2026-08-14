$env:PYTHONPATH = Join-Path $PSScriptRoot 'src'
Set-Location $PSScriptRoot
@'
from pathlib import Path
from scenebrain.repair_four_transcripts import run
r=run(Path(r'E:\Movies'),Path('runtime/bb_transcript_repair_v2'))
Path('runtime/bb_transcript_repair_v2/COMPLETE.json').write_text(str([(x[2]['episode'],x[2]['segments'],x[2]['runtime_seconds']) for x in r]))
'@ | python -
