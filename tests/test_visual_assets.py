"""Exported consoles must retain icon files, license and unchanged uploaded logos."""
import base64,hashlib,json,re
from pathlib import Path
from backend.runtime_export import bundle

ROOT=Path(__file__).resolve().parents[1]

def test_runtime_export_preserves_the_self_contained_visual_assets():
    files=bundle(ROOT)
    icons=json.loads(files['evolvyn/frontend/public/assets/tabler/manifest.json'])
    assert 'MIT License' in files['evolvyn/frontend/public/assets/tabler/LICENSE.txt']
    assert len(icons['assets'])>=30
    for icon in icons['assets']:
        content=files['evolvyn/frontend/public/assets/tabler/'+icon['file']]
        assert hashlib.sha256(content.encode()).hexdigest()==icon['sha256']
        assert '<svg' in content and '<script' not in content and 'href=' not in content
    assert 'evolvyn/frontend/src/workspace-refresh.css' in files
    assert 'evolvyn/frontend/src/components/ComposerActions.tsx' in files
    assert 'evolvyn/frontend/src/dashboard-refresh.css' in files
    for component in ['WorkspaceDialog', 'KeyVaultPanel', 'ConnectionsDashboard']:
        assert f'evolvyn/frontend/src/components/{component}.tsx' in files

def test_uploaded_logo_bytes_survive_embedding_and_runtime_export():
    files=bundle(ROOT)
    source=files['evolvyn/frontend/src/assets/connector-logos.ts']
    logos=json.loads(source.split('= ',1)[1].rsplit(';',1)[0])
    provenance=json.loads((ROOT/'docs/CONNECTOR_ASSETS.json').read_text())
    assert len(logos)==7
    for item in provenance['assets']:
        name=Path(item['file']).stem
        assert re.match(r'^data:image/(png|jpeg);base64,',logos[name])
        content=base64.b64decode(logos[name].split(',',1)[1],validate=True)
        assert hashlib.sha256(content).hexdigest()==item['sha256']
    # Only repository-owned public icon assets are newly allowlisted, not uploads.
    assert not any('/.local/' in key or '/attachments/' in key for key in files)
