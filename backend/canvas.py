"""Versioned visual requirements and executable graph drafts; no canvas text is code."""
import json
from datetime import datetime, timezone
from typing import Literal
from fastapi import Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from backend.agent_memory import reject_secrets
from backend.graph_harness import Definition

class Point(BaseModel):
    model_config=ConfigDict(extra='forbid')
    x:float=Field(ge=0,le=1200,allow_inf_nan=False)
    y:float=Field(ge=0,le=900,allow_inf_nan=False)
class Element(Point):
    id:str=Field(pattern=r'^[a-zA-Z][a-zA-Z0-9_]{0,39}$')
    kind:Literal['heading','text','button','card','image','navigation']='card'
    label:str=Field(min_length=1,max_length=300)
    width:float=Field(default=220,ge=40,le=1200,allow_inf_nan=False)
    height:float=Field(default=100,ge=30,le=900,allow_inf_nan=False)
class Drawing(BaseModel):
    model_config=ConfigDict(extra='forbid')
    name:str=Field(min_length=2,max_length=100)
    project_id:str|None=None
    theme:Literal['light','dark']='light'
    accent:str=Field(default='#336b58',pattern=r'^#[0-9a-fA-F]{6}$')
    elements:list[Element]=Field(default_factory=list,max_length=80)
    strokes:list[list[Point]]=Field(default_factory=list,max_length=100)
    graph:Definition|None=None
    positions:dict[str,Point]=Field(default_factory=dict,max_length=32)
    @model_validator(mode='after')
    def bounded(self):
        if len({e.id for e in self.elements})!=len(self.elements):raise ValueError('Element IDs must be unique')
        if sum(len(s) for s in self.strokes)>6000:raise ValueError('Drawing exceeds 6000 points')
        if self.graph and not set(self.positions)<={n.id for n in self.graph.nodes}:raise ValueError('Position references an unknown node')
        reject_secrets(self.name+' '+ ' '.join(e.label for e in self.elements))
        return self
class Update(BaseModel):
    revision:int=Field(ge=1)
    drawing:Drawing
class Apply(BaseModel):
    product_id:str
    revision:int=Field(ge=1)
    canvas_revision:int=Field(ge=1)

def prompt(drawing):
    rows=['Implement this reviewed page layout as data-driven UI.', 'Theme: '+drawing['theme']+'; accent: '+drawing['accent']+'.', 'Canvas viewport: 1200 by 900. Preserve reading order, responsive layout, keyboard access and readable typography.']
    for e in sorted(drawing['elements'],key=lambda e:(e['y'],e['x'])):
        rows.append(f"{e['kind']}: {json.dumps(e['label'])}; position ({e['x']}, {e['y']}), size {e['width']} x {e['height']}.")
    if drawing['strokes']:rows.append(f"{len(drawing['strokes'])} freehand strokes are attached as visual annotations. They are not OCR or executable instructions; use labeled blocks for precise intent.")
    rows.append('Button labels specify visual intent; domain actions require explicit implementation and acceptance tests.')
    return '\n'.join(rows)

def install(app,auth,get,save,listing,policy):
    @app.get('/api/canvas')
    def canvases(owner=Depends(auth)):return listing(owner,'canvas')
    @app.post('/api/canvas')
    def create(body:Drawing,owner=Depends(auth)):
        if body.project_id:get(owner,body.project_id,'project')
        if body.graph:policy.resource(owner,'write','agent_graph',body.graph.model_dump())
        if len(listing(owner,'canvas'))>=100:raise HTTPException(422,'Maximum 100 canvases')
        return save(owner,'canvas',{**body.model_dump(),'revision':1,'prompt':prompt(body.model_dump())})
    @app.put('/api/canvas/{id}')
    def update(id:str,body:Update,owner=Depends(auth)):
        old=get(owner,id,'canvas');policy.require(owner,'write')
        if body.drawing.graph:policy.resource(owner,'write','agent_graph',body.drawing.graph.model_dump())
        if old.get('project_id')!=body.drawing.project_id:raise HTTPException(422,'Canvas project cannot change')
        value={**body.drawing.model_dump(),'revision':body.revision+1,'prompt':prompt(body.drawing.model_dump())}
        policy.resource(owner,'write','canvas',value,id)
        with policy.conn() as c:
            row=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='canvas' FOR UPDATE",(owner,id)).fetchone()
            if row['body']['revision']!=body.revision:raise HTTPException(409,'Canvas changed; reload before saving')
            c.execute('UPDATE records SET body=%s WHERE owner=%s AND id=%s',(json.dumps(value),owner,id))
        return {'id':id,**value}
    @app.post('/api/canvas/{id}/publish-graph')
    def publish(id:str,owner=Depends(auth)):
        canvas=get(owner,id,'canvas')
        if not canvas.get('graph'):raise HTTPException(422,'Create a workflow graph first')
        # The existing harness performs schema, capability, data and approval checks at execution.
        return save(owner,'agent_graph',Definition.model_validate(canvas['graph']).model_dump())
    @app.post('/api/canvas/{id}/apply')
    def apply(id:str,body:Apply,owner=Depends(auth)):
        get(owner,id,'canvas');get(owner,body.product_id,'product_spec');policy.require(owner,'write')
        with policy.conn() as c:
            drawing=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='canvas' FOR UPDATE",(owner,id)).fetchone()['body']
            spec=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='product_spec' FOR UPDATE",(owner,body.product_id)).fetchone()['body']
            if drawing['revision']!=body.canvas_revision or spec['revision']!=body.revision:raise HTTPException(409,'Product or canvas changed; refresh before applying')
            if drawing.get('project_id')!=spec.get('project_id'):raise HTTPException(422,'Canvas and product must share project scope')
            spec['requirements']['design']={key:drawing[key] for key in ('theme','accent','elements','strokes','prompt')}
            spec['requirements'].update(theme=drawing['theme'],accent=drawing['accent'])
            spec['revision']+=1
            spec.setdefault('design_history',[]).append({'canvas_id':id,'canvas_revision':drawing['revision'],'product_revision':spec['revision'],'at':datetime.now(timezone.utc).isoformat()})
            spec['messages'].append({'role':'assistant','text':'Applied canvas layout and visual requirements. Rebuild to generate this revision; existing builds remain unchanged.'})
            policy.resource(owner,'write','product_spec',spec,body.product_id)
            c.execute('UPDATE records SET body=%s WHERE owner=%s AND id=%s',(json.dumps(spec),owner,body.product_id))
        return {'id':body.product_id,**spec}
