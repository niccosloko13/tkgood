"""Small shared Companion wire contract, independent from session/safety state."""
import json
import re
from pathlib import Path

def contract():return json.loads((Path(__file__).resolve().parents[1]/'config/companion_api.json').read_text(encoding='utf-8'))

def compatibility(bridge):
    expected=contract();version=bridge.get('companion_version') or bridge.get('extension_version') or ''
    def parsed(value):return tuple(map(int,value.split('.'))) if re.fullmatch(r'\d+\.\d+\.\d+',value) else None
    current=parsed(version);minimum=parsed(expected['companion_min_version'])
    reason='COMPANION_DESATUALIZADO' if current and current<minimum else 'COMPANION_VERSION_UNCONFIRMED' if not current else 'API_VERSION_MISMATCH' if bridge.get('api_version')!=expected['api_version'] else 'COMPATIBLE'
    return {**expected,'reported_companion_version':version,'reported_api_version':bridge.get('api_version'),
            'companion_compatible':reason=='COMPATIBLE','compatibility_status':reason}
