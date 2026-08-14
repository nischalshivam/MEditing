from pathlib import Path
from .portable_library import scan
from .library_dashboard import build
def main():
 root=Path(r'E:\Movies');r=scan(root);build(root,Path(__file__).resolve().parents[2]/'runtime/library_foundation');print(r['incremental'])
if __name__=='__main__':main()
