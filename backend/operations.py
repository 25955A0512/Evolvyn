"""Five bounded operational agent interfaces over explicitly uploaded logs/runbooks."""
import re
from collections import Counter
from backend.retrieval import retrieve
from backend.strategy import recommendations


def investigate(documents,query):
    entries=[];changes=[]
    for document in documents:
        for number,line in enumerate(document['content'][:200_000].splitlines()[:5000],1):
            level=re.search(r'\b(CRITICAL|FATAL|ERROR|WARN(?:ING)?|INFO)\b',line,re.I)
            citation=f"{document['name']}:line {number}"
            if level:entries.append({'level':level.group(1).upper().replace('WARNING','WARN'),'text':line[:500],'source':citation})
            if re.search(r'\b(deploy(?:ed|ment)?|release|commit|rollback)\b',line,re.I):changes.append({'text':line[:500],'source':citation})
    counts=dict(Counter(e['level'] for e in entries));errors=[e for e in entries if e['level'] in ('ERROR','FATAL','CRITICAL')]
    priority='high' if len(errors)>=10 or counts.get('CRITICAL',0) or counts.get('FATAL',0) else ('medium' if errors else 'low')
    runbooks=[d for d in documents if re.search(r'runbook|playbook|procedure',d['name'],re.I)]
    evidence=retrieve(documents,query)
    return {'facts':[],'evidence':evidence,'hypothesis':'Uploaded logs alone do not establish root cause. Validate timestamps, source completeness and recent changes before proposing a fix.','plan':'Create an internal incident investigation plan; no production system will be modified.','success_metric':'Define a baseline error rate and service-level indicator, then collect authorized follow-up evidence.','market_research':'This is uploaded-log investigation, not live production monitoring.','operations':{
        'alert_triage':{'priority':priority,'classification':'Heuristic triage of uploaded evidence','error_lines':len(errors)},
        'log_analysis':{'severity_counts':counts,'sample_errors':errors[:5],'parsed_lines':len(entries),'classification':'Counts of matching uploaded log lines, not production error rates'},
        'change_analysis':{'change_markers':changes[:5],'conclusion':'Change mentions are investigation leads; temporal proximity and causality have not been established.'},
        'runbook_retrieval':{'matches':retrieve(runbooks,query,3) if runbooks else [],'status':'Uploaded runbook passages retrieved' if runbooks else 'No runbook document is connected'},
        'verification':{'status':'not_evaluated','reason':'No executed production fix and authorized follow-up monitoring evidence are available.'}}}


def proposals(report):
    result=recommendations(report)
    sources=[e['source'] for e in report['operations']['log_analysis']['sample_errors']]
    for record,(title,rationale,tasks) in zip(result,[
        ('Validate the incident evidence','Check log coverage, severity definitions and timestamps before treating an uploaded excerpt as a production incident.',['Confirm the affected service and observation window','Check log completeness and document the baseline']),
        ('Investigate errors and recent change markers','Review cited error lines against authorized changes and runbooks; no root cause has been established.',['Review the cited errors and available change markers','Retrieve and review the appropriate runbook with the service owner']),
        ('Prepare a reversible response and verification plan','Define a permitted response, approval owner, rollback condition and follow-up measurement before making changes.',['Draft a response and rollback plan for approval','Collect follow-up service indicators and verify the result'])]):
        record.update(title=title,rationale=rationale,tasks=tasks,evidence=sources or [e.get('citation',e['source']) for e in report['evidence'][:2]],success_metric=report['success_metric'])
    return result
