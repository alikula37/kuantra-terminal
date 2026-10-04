"""Early offline dispatch. No backend or data-directory initialization."""
import json
from app.core.profile_safety import ProfileLease, profile_path, read_operation


def main(argv=None):
    with ProfileLease(profile_path(), timeout=10):
        state = read_operation(profile_path())
        print(json.dumps({'phase': state['phase'] if state else 'NONE'}))
    return 0
