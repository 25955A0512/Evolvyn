"""Auditable keyword signals for the no-provider fallback; not LLM sentiment analysis."""
import re

THEMES=[('onboarding','Onboarding friction',r'\bonboard\w*|\bactivat\w*|\bsign.?up\b'),('reliability','Product reliability',r'\bcrash\w*|\bbug\w*|\berror\w*|\bfreez\w*'),('performance','Product performance',r'\bslow\w*|\blatency\b|\bload(?:ing)? time\b'),('pricing','Pricing concerns',r'\bexpensive\b|\bpricing\b|\bprice\b|\bcost\b'),('support','Customer support',r'\bsupport\b|\bticket\w*|\bresponse time\b'),('retention','Retention concerns',r'\bchurn\w*|\bcancel\w*|\brefund\w*')]

def signals(documents):
    results=[]
    for id,label,pattern in THEMES:
        count=0;citations=[];excerpts=[]
        for doc in documents:
            if doc['name'].lower().endswith('.csv'):continue
            text=doc['content'][:200_000]
            matches=list(re.finditer(pattern,text,re.I))
            count+=len(matches)
            if matches:
                match=matches[0];start=max(0,match.start()-100);end=min(len(text),match.end()+200)
                citations.append(f"{doc['name']}:characters {start+1}–{end}")
                excerpts.append(text[start:end])
        if count:results.append({'id':id,'label':label,'keyword_mentions':count,'sources':citations,'excerpts':excerpts[:2],'classification':'Keyword signal in user-provided text; not a verified customer trend or causal finding'})
    return sorted(results,key=lambda r:r['keyword_mentions'],reverse=True)
