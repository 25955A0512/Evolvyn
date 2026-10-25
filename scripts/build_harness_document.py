"""Render the repository-backed harness report; requires reportlab and local DejaVu fonts."""
from pathlib import Path
import re
from html import escape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle, Flowable, KeepTogether
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT=Path(__file__).resolve().parents[1]
REPORT=ROOT/'docs/reports/EVOLVYN_HARNESS_ENGINEERING.md'
PDF=REPORT.with_suffix('.pdf')
REV='bb82c1bcf85e225095e4822d57e681b57492aeb2'
BASE=f'https://github.com/25955A0512/Evolvyn/blob/{REV}/'
FONT=Path('/usr/share/fonts/truetype/dejavu')
for name,file in [('Body','DejaVuSans.ttf'),('Bold','DejaVuSans-Bold.ttf'),('Italic','DejaVuSans-Oblique.ttf'),('Mono','DejaVuSansMono.ttf')]:
 pdfmetrics.registerFont(TTFont(name,str(FONT/file)))
pdfmetrics.registerFontFamily('Body',normal='Body',bold='Bold',italic='Italic',boldItalic='Bold')
INK=colors.HexColor('#20332D'); GREEN=colors.HexColor('#28684E'); MUTED=colors.HexColor('#65766E'); PALE=colors.HexColor('#EFF4EF'); LINE=colors.HexColor('#D9E3DD'); GOLD=colors.HexColor('#C6A261')
W,H=595.276,841.89
WIDTH=W-104
styles={
 'body':ParagraphStyle('body',fontName='Body',fontSize=9.3,leading=13.5,textColor=INK,spaceAfter=8),
 'h1':ParagraphStyle('h1',fontName='Bold',fontSize=10,leading=14,textColor=GREEN,spaceAfter=13),
 'h2':ParagraphStyle('h2',fontName='Bold',fontSize=24,leading=29,textColor=INK,spaceAfter=18),
 'h3':ParagraphStyle('h3',fontName='Bold',fontSize=11,leading=15,textColor=INK,spaceBefore=7,spaceAfter=6),
 'bullet':ParagraphStyle('bullet',fontName='Body',fontSize=9.1,leading=13.3,textColor=INK,leftIndent=12,firstLineIndent=-10,spaceAfter=6),
 'source':ParagraphStyle('source',fontName='Body',fontSize=7.8,leading=11,textColor=MUTED,spaceBefore=7,spaceAfter=4),
 'cell':ParagraphStyle('cell',fontName='Body',fontSize=8.2,leading=11.8,textColor=INK),
 'th':ParagraphStyle('th',fontName='Bold',fontSize=8,leading=11,textColor=colors.white),
}
refs={
 'S01':('Graph definitions, execution and approvals','backend/graph_harness.py'),
 'S02':('Worker claims, capacity and leases','backend/execution_queue.py'),
 'S03':('State fencing, lease renewal and live events','backend/app.py'),
 'S04':('Deterministic resource, risk and data policy','backend/policy.py'),
 'S05':('Persistent adapters and approval digests','backend/tool_plugins.py'),
 'S06':('Typed built-in tool invocation','backend/registry.py'),
 'S07':('LangGraph discussion and revision loop','backend/discussion.py'),
 'S08':('Encrypted credentials and shared routes','backend/vault.py'),
 'S09':('Catalog and JSON compatibility checks','backend/cloud_models.py'),
 'S10':('Reviewed, scoped lexical memory','backend/agent_memory.py'),
 'S11':('Product specialist graph and revisions','backend/product_agents.py'),
 'S12':('MCP registration, sessions and discovery','backend/mcp_registry.py'),
 'S13':('Bundled MCP client validation','backend/mcp_gateway.py'),
 'S14':('Request-local model/credential scope','backend/model_access.py'),
 'S15':('Authenticated standalone MCP starter','backend/custom_mcp.py'),
 'S16':('Manifest and file-by-file source builder','backend/model_source.py'),
 'S17':('Private compiler request and receipts','backend/source_compiler.py'),
 'S18':('Social source binding and snapshot graph','backend/social_growth.py'),
 'S19':('Social observation and forecast contracts','backend/social_contract.py'),
 'S20':('Evidence-led growth analysis','backend/growth.py'),
 'S21':('Persisted upload-event automations','backend/automations.py'),
 'T01':('Graph branches, joins, budgets and retries','tests/test_graph_harness.py'),
 'T02':('Recovery and stale-worker fencing','tests/test_recovery.py'),
 'T03':('Registry, approval and remote boundaries','tests/test_registry_governance.py'),
 'T04':('Restricted project resource isolation','tests/test_project_policy.py'),
 'T05':('Manifest recovery and retained source','tests/test_model_source.py'),
}
def markup(text):
 text=escape(text)
 text=re.sub(r'`([^`]+)`',r'<font name="Mono" size="8">\1</font>',text)
 text=re.sub(r'\*\*(.*?)\*\*',r'<b>\1</b>',text)
 for key,(_,path) in refs.items():
  text=text.replace('['+key+']',f'<link href="{BASE+path}" color="#28684E">[{key}]</link>')
 return text

def para(text,style='body'):return Paragraph(markup(text),styles[style])

def table(headers,rows,widths):
 data=[[Paragraph(escape(v),styles['th']) for v in headers]]
 data.extend([[Paragraph(markup(str(v)),styles['cell']) for v in row] for row in rows])
 t=Table(data,colWidths=widths,hAlign='LEFT',repeatRows=1)
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),GREEN),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('ROWBACKGROUNDS',(0,1),(-1,-1),[PALE,colors.white]),('LINEBELOW',(0,-1),(-1,-1),.6,LINE)]))
 return t

class Diagram(Flowable):
 def __init__(self,kind):super().__init__();self.kind=kind;self.width=WIDTH;self.height={'architecture':210,'lifecycle':135,'toolpath':100}[kind]
 def draw(self):
  c=self.canv
  def box(x,y,w,h,title,detail='',fill=PALE):
   c.setFillColor(fill);c.setStrokeColor(LINE);c.roundRect(x,y,w,h,8,fill=1,stroke=1)
   c.setFillColor(INK);c.setFont('Bold',9);c.drawCentredString(x+w/2,y+h-18,title)
   if detail:
    c.setFillColor(MUTED);c.setFont('Body',7.6)
    for i,line in enumerate(detail.split('|')):c.drawCentredString(x+w/2,y+h-32-i*11,line)
  def arrow(x,y,x2,y2):
   import math
   c.setStrokeColor(GREEN);c.setFillColor(GREEN);c.setLineWidth(1);c.line(x,y,x2,y2)
   a=math.atan2(y2-y,x2-x);p=c.beginPath();p.moveTo(x2,y2);p.lineTo(x2-5*math.cos(a-.5),y2-5*math.sin(a-.5));p.lineTo(x2-5*math.cos(a+.5),y2-5*math.sin(a+.5));p.close();c.drawPath(p,fill=1,stroke=0)
  if self.kind=='architecture':
   box(0,153,142,49,'React workspace','Intent · evidence · decisions')
   box(175,153,141,49,'FastAPI + policy','Identity · scope · admission')
   box(349,153,142,49,'PostgreSQL','State · grants · artifacts')
   arrow(142,178,175,178);arrow(316,178,349,178)
   box(111,73,269,57,'Execution harness','Typed GraphHarness + LangGraph discussions|Leases · checkpoints · bounded execution')
   arrow(245,153,245,130)
   box(0,0,221,50,'Gemini / Groq gateway','Shared vault route · bounded inference')
   box(270,0,221,50,'Tool registry + MCP','Schema · permissions · risk · receipts')
   arrow(196,73,111,50);arrow(295,73,380,50)
   c.setFont('Italic',7);c.setFillColor(MUTED);c.drawRightString(WIDTH,62,'Execution state persists in PostgreSQL')
  elif self.kind=='lifecycle':
   for x,title,detail in [(0,'CREATED','Saved intent'),(175,'RUNNING','Claimed lease'),(350,'COMPLETED','Saved result')]:box(x,80,141,47,title,detail)
   arrow(141,103,175,103);arrow(316,103,350,103)
   box(175,0,141,49,'WAITING FOR APPROVAL','Exact action binding')
   arrow(226,80,226,49);arrow(267,49,267,80)
   c.setFont('Body',7.5);c.setFillColor(MUTED);c.drawString(0,50,'Failure → FAILED');c.drawString(0,36,'User stop → CANCELLED');c.drawString(350,46,'Expired RUNNING lease');c.drawString(350,33,'→ bounded reclaim')
  else:
   for x,title,detail in [(0,'REGISTER','Endpoint + secret ref'),(175,'DISCOVER','Healthy MCP + schema'),(350,'INVOKE','Policy + result checks')]:box(x,40,141,51,title,detail)
   arrow(141,65,175,65);arrow(316,65,350,65)
   c.setFont('Italic',8);c.setFillColor(MUTED);c.drawCentredString(WIDTH/2,16,'Non-read tool → exact-argument approval before execution')

class Cover(Flowable):
 def __init__(self):
  super().__init__();self.width=WIDTH;self.height=700
 def draw(self):
  c=self.canv;c.setFillColor(GREEN);c.roundRect(0,651,40,40,10,fill=1,stroke=0);c.setFont('Bold',30);c.setFillColor(colors.white);c.drawString(10,660,'e')
  c.setFillColor(INK);c.setFont('Bold',25);c.drawString(54,660,'evolvyn')
  c.setFont('Bold',10);c.setFillColor(GREEN);c.drawString(0,593,'ENGINEERING ARCHITECTURE / 2026')
  c.setFillColor(INK);c.setFont('Bold',43);c.drawString(0,523,'Harness');c.drawString(0,469,'engineering')
  c.setFillColor(MUTED);c.setFont('Body',16);c.drawString(0,428,'Architecture, execution controls and evidence')
  c.setStrokeColor(GOLD);c.setLineWidth(3);c.line(0,400,63,400)
  p=para('How Evolvyn coordinates agents, tools, business evidence and human decisions. A repository-backed technical review prepared for engineering and product evaluation.');p.wrap(WIDTH-55,100);p.drawOn(c,0,328)
  labels=[('EVIDENCE','Source-bound context'),('CONTROL','Typed, bounded execution'),('REVIEW','Argument-bound approval')]
  for i,(title,detail) in enumerate(labels):
   x=i*167;c.setFillColor(PALE);c.roundRect(x,218,157,75,8,fill=1,stroke=0);c.setFont('Bold',9);c.setFillColor(GREEN);c.drawString(x+12,269,title);c.setFont('Body',8);c.setFillColor(INK);c.drawString(x+12,244,detail)
  p=para('Prepared 25 October 2026 · Source baseline **bb82c1b**. Code-level assessment with fresh focused tests. Live provider authorization and production readiness require separate acceptance.');p.wrap(WIDTH,90);p.drawOn(c,0,113)
  c.setFillColor(MUTED);c.setFont('Body',9);c.drawString(0,48,'13 pages · Architecture diagrams · Implementation references')

def page_frame(c,doc):
 c.saveState()
 if doc.page>1:
  c.setStrokeColor(LINE);c.setLineWidth(.6);c.line(52,H-44,W-52,H-44)
  c.setFont('Bold',8);c.setFillColor(GREEN);c.drawString(52,H-33,'EVOLVYN / HARNESS ENGINEERING')
  c.setFont('Body',7.5);c.setFillColor(MUTED);c.drawRightString(W-52,H-33,'SOURCE-BASED TECHNICAL REVIEW')
 c.setStrokeColor(LINE);c.line(52,43,W-52,43)
 c.setFont('Body',7.5);c.setFillColor(MUTED);c.drawString(52,29,'25 OCT 2026  ·  SOURCE bb82c1b')
 c.setFont('Bold',8);c.drawRightString(W-52,29,f'{doc.page:02d} / 13')
 c.restoreState()

LIMITS=[('Graph structure','32 nodes; 64 edges','Validated definition ceiling'),('Run budgets','32 steps; 16 tools; 2,048 tokens; 180 s','Defaults; maxima 100 / 64 / 8,192 / 600 s'),('Node controls','10 visits; 30 s timeout; 1 attempt','Defaults; max 100 visits / 120 s / 4 attempts'),('Checkpoint','600,000 serialized characters','Last 200 harness events retained'),('Policy interaction','Minimum of graph/policy where applied','Default policy: 16 tool calls; 300 s')]
VERIFY=[('Graph harness','7 tests','Approval, branches/joins, loops, retries and budgets'),('Worker recovery','4 tests','Expired leases, stale fencing, attempt cap, data policy'),('Registry + governance','9 tests','Discovery, schemas, approvals, tenant and network limits'),('Project isolation','1 test','Restricted linked-resource visibility'),('Source generation','20 tests','Persistence, cancellation, unsafe paths and manifest repair')]

def placeholder(key):
 if key in ('architecture','lifecycle','toolpath'):return [Diagram(key),Spacer(1,12)]
 if key=='limits':return [table(['CONTROL','BOUND','INTERPRETATION'],LIMITS,[92,193,WIDTH-285]),Spacer(1,12)]
 if key=='verification':return [table(['SUITE','RESULT','WHAT IT EXERCISES'],VERIFY,[106,64,WIDTH-170]),Spacer(1,13)]
 if key=='testresult':return [para('**41 passed** in 37.47 seconds. One Starlette/AnyIO dependency deprecation warning. No live provider acceptance is inferred.')]
 if key=='sources':
  rows=[]
  for key,(label,path) in refs.items():
   rows.append([f'<link href="{BASE+path}" color="#28684E"><b>{key}</b></link>',label,path])
  data=[[Paragraph(x,styles['th']) for x in ['REF','IMPLEMENTATION / EVIDENCE','REPOSITORY FILE']]]
  st=ParagraphStyle('smallcell',parent=styles['cell'],fontSize=6.8,leading=9)
  data.extend([[Paragraph(v,st) for v in row] for row in rows])
  t=Table(data,colWidths=[37,204,WIDTH-241],repeatRows=1)
  t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),GREEN),('ROWBACKGROUNDS',(0,1),(-1,-1),[PALE,colors.white]),('VALIGN',(0,0),(-1,-1),'TOP'),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3)]))
  return [t,Spacer(1,9)]
 raise ValueError(key)

class ReportDoc(SimpleDocTemplate):
 def afterFlowable(self,flowable):
  if isinstance(flowable,Paragraph) and flowable.style.name=='h1':
   label=flowable.getPlainText();key='section-'+str(self.page)
   self.canv.bookmarkPage(key)
   self.canv.addOutlineEntry(label,key,level=0,closed=False)

def build():
 pages=REPORT.read_text().split('<!-- page -->')
 story=[Cover()]
 for section in pages[1:]:
  story.append(PageBreak());lines=section.strip().splitlines();buffer=[]
  def flush():
   if buffer:
    text=' '.join(buffer);story.append(para(text,'source' if text.startswith('Sources:') else 'body'));buffer.clear()
  for line in lines:
   line=line.strip()
   if not line:flush();continue
   if line.startswith('[['):flush();story.extend(placeholder(line[2:-2]));continue
   if line.startswith('# '):flush();story.append(para(line[2:].upper(),'h1'));continue
   if line.startswith('## '):flush();story.append(para(line[3:],'h2'));continue
   if line.startswith('### '):flush();story.append(para(line[4:],'h3'));continue
   if line.startswith('- '):flush();story.append(para('• '+line[2:],'bullet'));continue
   if re.match(r'^\d+\. ',line):flush();story.append(para(line,'bullet'));continue
   buffer.append(line)
  flush()
 doc=ReportDoc(str(PDF),pagesize=(W,H),rightMargin=52,leftMargin=52,topMargin=67,bottomMargin=57,title='Evolvyn — Harness Engineering',author='Evolvyn',subject='Architecture, durable execution, policy, MCP tools and verified implementation',pageCompression=1)
 doc.build(story,onFirstPage=page_frame,onLaterPages=page_frame)
 print(PDF)

if __name__=='__main__':build()
