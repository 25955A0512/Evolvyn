"""Bounded public discussion ingestion; external comments remain unverified evidence."""
import asyncio
import json
from html.parser import HTMLParser

class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)

def plain(value):
    parser=Text();parser.feed(value or '')
    return ' '.join(parser.parts)[:1800]

async def discussion_excerpt(client,id):
    try:
        chunks=[];size=0
        async with client.stream('GET','https://hn.algolia.com/api/v1/items/'+id,timeout=8) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                size+=len(chunk)
                if size>2_000_000:return []
                chunks.append(chunk)
        data=json.loads(b''.join(chunks))
        texts=[plain(data.get('text',''))]+[plain(comment.get('text','')) for comment in data.get('children',[])[:3]]
        return [text for text in texts if text]
    except Exception:return []

async def enrich(client,hits):
    chosen=[h for h in hits[:2] if str(h.get('objectID','')).isdigit()]
    results=await asyncio.gather(*(discussion_excerpt(client,str(h['objectID'])) for h in chosen))
    return {str(hit['objectID']):result for hit,result in zip(chosen,results)}
