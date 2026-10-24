"""Versioned PRD drafts and real Office Open XML exports; no executable document content."""
import io,json,re,zipfile
from datetime import datetime,timezone
from xml.sax.saxutils import escape
from fastapi import Depends,HTTPException
from fastapi.responses import Response
from pydantic import BaseModel,ConfigDict,Field
from backend.agent_memory import reject_secrets

class Draft(BaseModel):
    model_config=ConfigDict(extra='forbid')
    revision:int=Field(ge=0)
    text:str=Field(min_length=1,max_length=16000)

def docx(text,title):
    text=re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]','',text)
    paragraphs=[]
    for line in [title,'',*text.splitlines()]:
        match=re.match(r'^(#{1,3})\s+(.*)',line)
        value=match[2] if match else line
        style='<w:pPr><w:pStyle w:val="Heading'+str(len(match[1]))+'"/></w:pPr>' if match else ''
        paragraphs.append('<w:p>'+style+'<w:r><w:t xml:space="preserve">'+escape(value)+'</w:t></w:r></w:p>')
    output=io.BytesIO()
    with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml','<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/><Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/></Types>')
        archive.writestr('_rels/.rels','<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        archive.writestr('word/_rels/document.xml.rels','<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        archive.writestr('word/document.xml','<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'+''.join(paragraphs)+'<w:sectPr/></w:body></w:document>')
        archive.writestr('word/styles.xml','<?xml version="1.0" encoding="UTF-8"?><w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'+''.join('<w:style w:type="paragraph" w:styleId="Heading'+str(n)+'"><w:name w:val="heading '+str(n)+'"/><w:rPr><w:b/><w:sz w:val="'+str(36-4*n)+'"/></w:rPr></w:style>' for n in (1,2,3))+'</w:styles>')
    return output.getvalue()

def install(app,auth,get,conn,policy):
    def read(owner,id):
        spec=get(owner,id,'product_spec')
        with conn() as c:
            draft=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='product_document'",(owner,'prd:'+id)).fetchone()
            if draft:return draft['body']
            run=c.execute("SELECT body->'graph_checkpoint'->'nodes'->'prd'->'output'->>'text' AS text FROM records WHERE owner=%s AND kind='execution' AND body->'definition'->'nodes' @> %s::jsonb AND body->'graph_checkpoint'->'nodes'->'prd'->'output'->>'text' IS NOT NULL ORDER BY created DESC LIMIT 1",(owner,json.dumps([{'id':'requirements','arguments':{'spec_id':id}}]))).fetchone()
        return {'spec_id':id,'revision':0,'text':run['text'] if run else '', 'source':'agent output' if run else 'not generated','project_id':spec.get('project_id')}
    @app.get('/api/studio/products/{id}/prd')
    def document(id:str,owner=Depends(auth)):return read(owner,id)
    @app.put('/api/studio/products/{id}/prd')
    def save(id:str,body:Draft,owner=Depends(auth)):
        spec=get(owner,id,'product_spec');principal=policy.require(owner,'write');reject_secrets(body.text)
        with conn() as c:
            c.execute('SELECT pg_advisory_xact_lock(hashtext(%s))',('prd:'+id,))
            row=c.execute("SELECT body FROM records WHERE owner=%s AND id=%s AND kind='product_document'",(owner,'prd:'+id)).fetchone()
            revision=row['body']['revision'] if row else 0
            if revision!=body.revision:raise HTTPException(409,'PRD draft changed; reload before saving')
            data={'spec_id':id,'project_id':spec.get('project_id'),'revision':revision+1,'text':body.text,'source':'user-reviewed draft','actor':principal.account,'updated_at':datetime.now(timezone.utc).isoformat()}
            c.execute("INSERT INTO records(id,owner,kind,body) VALUES (%s,%s,'product_document',%s) ON CONFLICT(id) DO UPDATE SET body=EXCLUDED.body WHERE records.owner=EXCLUDED.owner",('prd:'+id,owner,json.dumps(data)))
        return data
    @app.get('/api/studio/products/{id}/prd.docx')
    def download(id:str,owner=Depends(auth)):
        document=read(owner,id);spec=get(owner,id,'product_spec')
        if not document['text']:raise HTTPException(409,'Generate or save a PRD before exporting')
        return Response(docx(document['text'],spec['name']+' · Product requirements'),media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',headers={'Content-Disposition':'attachment; filename="evolvyn-prd.docx"','Cache-Control':'no-store'})
