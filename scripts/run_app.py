"""Launch the local UI, optionally using an explicit Groq answer profile."""
from pathlib import Path
import argparse
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.app_profile import hosted_environment


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--hosted', action='store_true', help='Use Groq for answers from ignored .env.hosted; speech stays Gnani.')
    parser.add_argument('--port', type=int, default=8501)
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        parser.error('Port must be between 1 and 65535.')
    try:
        env = hosted_environment(ROOT, os.environ) if args.hosted else dict(os.environ)
    except ValueError as error:
        parser.error(str(error))
    command = [sys.executable, '-m', 'streamlit', 'run', str(ROOT / 'app.py'),
               '--server.address', '127.0.0.1', '--server.port', str(args.port),
               '--server.headless', 'true']
    return subprocess.call(command, cwd=ROOT, env=env)


if __name__ == '__main__':
    raise SystemExit(main())
