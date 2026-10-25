"""Versioned engagement observations; cumulative counters are not period activity or customers."""
from datetime import datetime,timezone
from typing import Literal
from pydantic import BaseModel,Field,ConfigDict,field_validator,model_validator
import re,statistics
from urllib.parse import urlsplit

class Comment(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str=Field(min_length=1,max_length=200)
    text:str=Field(max_length=1000)
    published_at:datetime
    @field_validator('text')
    @classmethod
    def redact(cls,value):
        value=re.sub(r'[^\s@]+@[^\s@]+\.[^\s@]+','[email redacted]',value)
        value=re.sub(r'(?<!\w)@[\w.]+','[handle redacted]',value)
        return re.sub(r'(?<!\w)\+?\d(?:[ ().-]*\d){7,14}(?!\w)','[number redacted]',value)
    @field_validator('published_at')
    @classmethod
    def aware(cls,value):
        if value.tzinfo is None:raise ValueError('Timezone-aware timestamps required')
        return value
class Post(BaseModel):
    model_config=ConfigDict(extra='forbid')
    id:str=Field(min_length=1,max_length=200)
    published_at:datetime
    url:str=Field(max_length=2000)
    text:str=Field(default='',max_length=1000)
    likes:int|None=Field(default=None,ge=0,le=10**12,strict=True)
    comments:int|None=Field(default=None,ge=0,le=10**12,strict=True)
    views:int|None=Field(default=None,ge=0,le=10**12,strict=True)
    @field_validator('published_at')
    @classmethod
    def aware(cls,value):return Comment.aware(value)
    @field_validator('url')
    @classmethod
    def valid_url(cls,value):
        p=urlsplit(value)
        if p.scheme!='https' or p.hostname not in ('www.instagram.com','instagram.com','www.youtube.com','youtube.com','www.linkedin.com','linkedin.com') or p.username or p.password or p.fragment or p.port not in (None,443):raise ValueError('Expected a public HTTPS provider post URL')
        return value
    @field_validator('text')
    @classmethod
    def redact(cls,value):return Comment.redact(value)
class Observation(BaseModel):
    model_config=ConfigDict(extra='forbid')
    schema_version:Literal['social-v1']='social-v1'
    provider:Literal['instagram','youtube','linkedin']
    account_id:str=Field(min_length=1,max_length=200,pattern=r'^[A-Za-z0-9:_-]+$')
    account_name:str=Field(max_length=200)
    captured_at:datetime
    followers:int|None=Field(default=None,ge=0,le=10**12,strict=True)
    posts:list[Post]=Field(max_length=25)
    comment_sample:list[Comment]=Field(default_factory=list,max_length=20)
    coverage:str=Field(min_length=10,max_length=1000)
    @field_validator('captured_at')
    @classmethod
    def aware(cls,value):return Comment.aware(value)
    @model_validator(mode='after')
    def unique(self):
        if len({p.id for p in self.posts})!=len(self.posts):raise ValueError('Duplicate post IDs')
        if len({c.id for c in self.comment_sample})!=len(self.comment_sample):raise ValueError('Duplicate comment IDs')
        if any(urlsplit(p.url).hostname not in ({'instagram.com','www.instagram.com'} if self.provider=='instagram' else {'youtube.com','www.youtube.com'} if self.provider=='youtube' else {'linkedin.com','www.linkedin.com'}) for p in self.posts):raise ValueError('Post provider mismatch')
        if any(p.published_at>self.captured_at for p in self.posts) or any(c.published_at>self.captured_at for c in self.comment_sample):raise ValueError('Future publication date')
        return self

def metrics(data):
    posts=data['posts'];result={'posts_observed':len(posts),'followers':data.get('followers')}
    for field in ('likes','comments','views'):
        values=[p.get(field) for p in posts]
        result[field]=sum(values) if values and all(v is not None for v in values) else None
    result['interactions']=result['likes']+result['comments'] if result['likes'] is not None and result['comments'] is not None else None
    result['interactions_per_100_views']=round(100*result['interactions']/result['views'],2) if result['interactions'] is not None and result['views'] else None
    return result

def forecast(history,now=None):
    blocked=lambda reason:{'status':'suppressed','reason':reason}
    if len(history)<29:return blocked('At least 29 comparable daily account snapshots are required to obtain 28 daily interaction observations.')
    rows=sorted(history,key=lambda s:datetime.fromisoformat(s['observation']['captured_at']))[-60:];observations=[r['observation'] for r in rows]
    now=now or datetime.now(timezone.utc)
    if (now-datetime.fromisoformat(observations[-1]['captured_at'])).total_seconds()>36*3600:return blocked('Latest observation is stale; refresh the source before forecasting.')
    identity={(o['provider'],o['account_id'],tuple(sorted(p['id'] for p in o['posts']))) for o in observations}
    if len(identity)!=1:return blocked('The observed post cohort or account changed; cumulative totals are not comparable.')
    values=[]
    for previous,current in zip(rows,rows[1:]):
        a=datetime.fromisoformat(previous['observation']['captured_at']);b=datetime.fromisoformat(current['observation']['captured_at'])
        if abs((b-a).total_seconds()-86400)>900:return blocked('Daily intervals are missing or irregular; no daily forecast inferred.')
        if previous.get('config_binding')!=current.get('config_binding'):return blocked('Connector configuration or metric definitions changed.')
        old={p['id']:p for p in previous['observation']['posts']}
        if any(p.get(k) is None or old[p['id']].get(k) is None or p[k]<old[p['id']][k] for p in current['observation']['posts'] for k in ('likes','comments')):return blocked('Individual post counters are missing or revised downwards.')
        before=previous['metrics']['interactions'];after=current['metrics']['interactions']
        if before is None or after is None or after<before:return blocked('Interaction counters are missing or revised downwards.')
        values.append(after-before)
    if not any(values):return blocked('No nonzero daily interaction baseline exists.')
    errors=[];naive=[]
    for i in range(len(values)-7,len(values)):
        errors.append(abs(values[i]-statistics.mean(values[i-7:i])));naive.append(abs(values[i]-values[i-1]))
    mae=statistics.mean(errors);baseline=statistics.mean(naive)
    if mae>baseline:return blocked('Seven-day mean did not outperform the last-day baseline in the recent backtest.')
    prediction=statistics.mean(values[-7:]);band=max(errors)
    return {'status':'available','metric':'new interactions on the unchanged observed post cohort','model':'rolling-seven-day-mean-v1','horizon_days':7,'sample_size':len(values),'backtest_points':7,'mae':round(mae,2),'naive_mae':round(baseline,2),'daily_estimate':round(prediction,2),'daily_low':round(max(0,prediction-band),2),'daily_high':round(prediction+band,2),'uncertainty':'Range uses maximum recent absolute backtest error; not a calibrated probability interval.','limitations':'Estimate for the same sampled posts, not revenue, unique people, demand or guaranteed growth. Assumes comparable daily collection and stable counters.'}
