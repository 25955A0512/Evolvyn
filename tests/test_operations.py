from pathlib import Path
from backend.operations import investigate,proposals

def test_operational_agents_report_uploaded_observations_without_invented_verification():
    document={'id':'logs','name':'service-logs.txt','content':Path('sample-data/service-logs.txt').read_text()}
    report=investigate([document],'activation timeout')
    assert report['operations']['log_analysis']['severity_counts']['ERROR']==2
    assert report['operations']['alert_triage']['priority']=='medium'
    assert report['operations']['change_analysis']['change_markers']
    assert report['operations']['verification']['status']=='not_evaluated'
    assert report['operations']['runbook_retrieval']['matches']==[]
    actions=proposals(report)
    assert all('production' not in r['tasks'][0].lower() or 'approval' in r['rationale'].lower() for r in actions)
    assert actions[1]['evidence'][0].startswith('service-logs.txt:line')
