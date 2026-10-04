"""Early offline dispatch. No backend or data-directory initialization."""
import json
import argparse
from app.core.profile_safety import ProfileLease, profile_path, read_operation


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--restore-maintenance', action='store_true', required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--restore-status', action='store_true')
    action.add_argument('--restore-prepare', metavar='OPERATION_ID')
    args = parser.parse_args(argv)
    with ProfileLease(profile_path(), timeout=10) as lease:
        if args.restore_prepare:
            from app.services.desktop_restore import RestorePreparation
            # Already owns the lifetime lease. This branch never starts GUI,
            # backend lifespan, gateway, plugins, quotes or automatic tracking.
            state = RestorePreparation(profile_path(), lease).prepare(args.restore_prepare)
            print(json.dumps({'phase': state['phase'], 'operation_id': state['operation_id']}))
        else:
            state = read_operation(profile_path())
            print(json.dumps({'phase': state['phase'] if state else 'NONE'}))
    return 0
