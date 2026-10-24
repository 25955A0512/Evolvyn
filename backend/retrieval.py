"""Bounded lexical retrieval with stable document offsets, not semantic embeddings."""
import math
import re
from collections import Counter

STOP = {'the','and','for','with','this','that','from','what','which','would','could','should','have','about','into','your','please'}

def tokens(text):
    return [w for w in re.findall(r'[a-z0-9]+', text.lower()) if len(w)>2 and w not in STOP]

def chunks(document, width=1000, overlap=150):
    text=document['content']
    # A 2 MB document cannot make an unbounded retrieval index.
    for start in range(0,min(len(text),200_000),width-overlap):
        excerpt=text[start:start+width]
        if excerpt.strip():
            yield {'document_id':document['id'],'source':document['name'], 'start':start,'end':start+len(excerpt),'excerpt':excerpt,'classification':'user-provided, unverified'}

def retrieve(documents, query, limit=5):
    passages=[c for d in documents if not d['name'].lower().endswith('.csv') for c in chunks(d)]
    if not passages:return []
    terms=set(tokens(query)); bags=[Counter(tokens(p['excerpt'])) for p in passages]
    average=sum(sum(b.values()) for b in bags)/len(bags) or 1
    frequencies={t:sum(t in b for b in bags) for t in terms}
    for passage,bag in zip(passages,bags):
        score=0.0
        for term in terms:
            tf=bag[term]
            if tf:
                idf=math.log(1+(len(bags)-frequencies[term]+.5)/(frequencies[term]+.5))
                score+=idf*tf*2.2/(tf+1.2*(.25+.75*sum(bag.values())/average))
        passage['score']=round(score,5)
        passage['citation']=f"{passage['source']}:characters {passage['start']+1}–{passage['end']}"
    return sorted(passages,key=lambda p:p['score'],reverse=True)[:limit]
