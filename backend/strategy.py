"""Evidence-linked, explicitly heuristic strategy plans; no invented outcomes."""
from uuid import uuid4

def recommendations(report):
    facts=report['facts']; evidence=report['evidence']
    sources=[f['source'] for f in facts[-2:]]+[e.get('citation',e['source']) for e in evidence[:2]]
    themes=report.get('themes',[])
    top_theme=themes[0] if themes else None
    if top_theme:sources+=top_theme['sources'][:2]
    decline=len(facts)>1 and facts[-1]['conversion']<facts[0]['conversion']
    proposals=[('Validate the conversion measurement' if facts else 'Validate the customer feedback themes',
       'Verify definitions, sample coverage and the baseline before changing the product.',5,.9,1,
       ['Check source definitions and document limitations','Record an agreed baseline and observation window']),
       (('Investigate reported '+top_theme['label'].lower()) if top_theme else ('Investigate conversion friction' if decline else 'Interview customers about the strongest evidence'),
       ('The uploaded text contains '+str(top_theme['keyword_mentions'])+' keyword references to '+top_theme['label'].lower()+'. Validate these reports with interviews and instrumentation; mentions do not establish a trend or cause.' if top_theme else 'Use interviews and event instrumentation to test explanations; the evidence does not establish a cause.'),4,.55,2,
       ['Review the cited evidence with the product owner','Interview affected customers and record supporting and contradictory evidence']),
       ('Design a controlled onboarding experiment' if decline else 'Design a measurable improvement experiment',
       'Test a reversible change only after validation; estimated impact remains unknown.',4,.4,3,
       ['Define a control and a treatment with a rollback condition','Review experiment results after the agreed measurement period'])]
    return [{'id':str(uuid4()),'title':title,'rationale':why,'evidence':sources,'impact':impact,'confidence':confidence,'effort':effort,'cost_estimate':None,'expected_benefit':'Unknown until an adequately designed experiment is measured','assumptions':['Source definitions are consistent','Uploaded data represents the business question'],'risks':['Selection bias','Confounding changes','Insufficient sample size'],'success_metric':report['success_metric'],'measurement_period_days':14,'rollback':'Stop the experiment and return to the documented baseline if guardrails worsen.','tasks':tasks,'status':'proposed','classification':'Heuristic proposal requiring review'} for title,why,impact,confidence,effort,tasks in proposals]
