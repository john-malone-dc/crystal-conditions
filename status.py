"""Record when each source last fetched successfully. File timestamps don't survive a cloud run."""
import json
from datetime import datetime

import config

FILE = config.DATA / "status.json"


def read():
    return json.loads(FILE.read_text()) if FILE.exists() else {}


def mark(source):
    current = read()
    current[source] = datetime.now().isoformat(timespec="minutes")
    FILE.write_text(json.dumps(current, indent=1))
