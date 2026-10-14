"""Local-only PostgreSQL in a private Unix socket directory; never a production server."""
from pathlib import Path
import os
import pgserver
ROOT=Path(__file__).resolve().parent.parent
runtime=ROOT/'.runtime'; runtime.mkdir(mode=0o700,exist_ok=True)
server=pgserver.get_server(runtime/'postgres',cleanup_mode=None)
uri=server.get_uri()
path=runtime/'database-url'
path.write_text(uri); path.chmod(0o600)
print('Local PostgreSQL ready; connection details stored privately in .runtime/database-url')
