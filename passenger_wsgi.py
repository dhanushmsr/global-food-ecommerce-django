import sys
import io
import os

# 1. 🛡️ SAFE STREAM HANDLING: Only wrap encoding streams if cPanel hasn't closed the TTY file descriptor
if sys.stdout and hasattr(sys.stdout, 'buffer') and not sys.stdout.closed:
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    except Exception:
        pass

if sys.stderr and hasattr(sys.stderr, 'buffer') and not sys.stderr.closed:
    try:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
    except Exception:
        pass

# 2. 🎯 PATH MATCH INTEGRITY: Only append paths if they aren't already registered in the system environment
PROJECT_ROOT = '/home/ganesham/core'
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

os.environ['DJANGO_SETTINGS_MODULE'] = 'core.settings'

# 3. Hand off the request execution safely to the Django WSGI engine
from core.wsgi import application