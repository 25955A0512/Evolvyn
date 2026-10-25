"""Build the standalone extensible-architecture PDF without changing the original report.

Run: python scripts/build_extensible_architecture_document.py
Uses the shared ReportLab styles/renderer and locally installed DejaVu fonts.
"""
from reportlab.platypus import Flowable, Spacer
from reportlab.lib import colors
import build_harness_document as base

base.REPORT=base.ROOT/'docs/reports/EVOLVYN_EXTENSIBLE_PLATFORM_ARCHITECTURE.md'
base.PDF=base.REPORT.with_suffix('.pdf')
base.REV='8ac1e567a81319cdec6e929c5061d753ed594755'
base.BASE=f'https://github.com/25955A0512/Evolvyn/blob/{base.REV}/'
base.refs={
 'S01':('Bounded graphs, approvals and checkpoints','backend/graph_harness.py'),
 'S02':('Queue admission and worker leases','backend/execution_queue.py'),
 'S03':('Resource, risk and data-processing policy','backend/policy.py'),
 'S04':('MCP registration, discovery and remote sessions','backend/mcp_registry.py'),
 'S05':('Tool mappings, invocation and approval binding','backend/tool_plugins.py'),
 'S06':('Typed built-in implementation contract','backend/registry.py'),
 'S07':('Agent definitions and bounded model access','backend/agent_gateway.py'),
 'S08':('Scoped model routing and credential resolution','backend/model_access.py'),
 'S09':('Provider catalog and JSON compatibility checks','backend/cloud_models.py'),
 'S10':('Bundled MCP client execution','backend/mcp_gateway.py'),
 'S11':('Authenticated standalone MCP server','backend/custom_mcp.py'),
 'S12':('Validated policy configuration interfaces','backend/policy_api.py'),
 'S13':('Source-bound social observation workflow','backend/social_growth.py'),
 'T01':('Graph branches, approval and budget tests','tests/test_graph_harness.py'),
 'T02':('Recovery, fencing and attempt-limit tests','tests/test_recovery.py'),
 'T03':('Registry, approval and transport-boundary tests','tests/test_registry_governance.py'),
 'T04':('Restricted project isolation test','tests/test_project_policy.py'),
 'T05':('Source-contract and artifact persistence tests','tests/test_model_source.py'),
}
W,H=base.W,base.H
class Cover(Flowable):
 def __init__(self):super().__init__();self.width=base.WIDTH;self.height=700
 def draw(self):
  c=self.canv
  c.setFillColor(base.GREEN);c.roundRect(0,651,40,40,10,fill=1,stroke=0)
  c.setFillColor(colors.white);c.setFont('Bold',30);c.drawString(10,660,'e')
  c.setFillColor(base.INK);c.setFont('Bold',25);c.drawString(54,660,'evolvyn')
  c.setFillColor(base.GREEN);c.setFont('Bold',10);c.drawString(0,593,'PLATFORM ARCHITECTURE / EXTENSIBILITY')
  c.setFillColor(base.INK);c.setFont('Bold',39);c.drawString(0,529,'Extensible');c.drawString(0,478,'agent platform')
  c.setFillColor(base.MUTED);c.setFont('Body',15);c.drawString(0,438,'Registries, guardrails and gateways')
  c.setStrokeColor(base.GOLD);c.setLineWidth(3);c.line(0,408,63,408)
  p=base.para('How Evolvyn adds connections and capabilities through defined contracts while preserving authorization, bounded execution and human decisions.');p.wrap(base.WIDTH-25,85);p.drawOn(c,0,347)
  for x,y,title,detail in [(0,249,'MCP REGISTRY','Extend connections and discovery'),(253,249,'TOOL REGISTRY','Extend callable business capabilities'),(0,157,'GOVERNANCE / GUARDRAILS','Extend validated policy and checks'),(253,157,'GATEWAYS','Extend model and tool adapters')]:
   c.setFillColor(base.PALE);c.roundRect(x,y,238,76,8,fill=1,stroke=0)
   c.setFillColor(base.GREEN);c.setFont('Bold',9);c.drawString(x+13,y+50,title)
   c.setFillColor(base.INK);c.setFont('Body',8.4);c.drawString(x+13,y+25,detail)
  p=base.para('Standalone engineering brief · 25 October 2026<br/>'.replace('<br/>',' / ')+'Source **8ac1e56**. Supported registration and configuration are distinguished from engineering extensions. Live provider readiness requires separate acceptance.');p.wrap(base.WIDTH,75);p.drawOn(c,0,79)
  c.setFillColor(base.MUTED);c.setFont('Body',8);c.drawString(0,33,'10 pages · Dedicated component sections · Extensibility matrix · Source references')

class Gateways(Flowable):
 def __init__(self):super().__init__();self.width=base.WIDTH;self.height=127
 def draw(self):
  c=self.canv
  for y,title,detail,target in [(67,'MODEL GATEWAY','Context + vault + provider contract','Gemini / Groq'),(5,'TOOL EXECUTION GATEWAY','Schema + policy + approval + credential','Built-in / MCP')]:
   c.setFillColor(base.PALE);c.setStrokeColor(base.LINE);c.roundRect(0,y,321,52,8,fill=1,stroke=1)
   c.setFillColor(base.GREEN);c.setFont('Bold',9);c.drawString(12,y+33,title)
   c.setFillColor(base.MUTED);c.setFont('Body',8);c.drawString(12,y+16,detail)
   c.setStrokeColor(base.GREEN);c.line(321,y+26,347,y+26);c.line(347,y+26,342,y+29);c.line(347,y+26,342,y+23)
   c.setFillColor(base.PALE);c.setStrokeColor(base.LINE);c.roundRect(351,y,140,52,8,fill=1,stroke=1)
   c.setFillColor(base.INK);c.setFont('Bold',9);c.drawCentredString(421,y+24,target)

old_placeholder=base.placeholder
EXTENSIONS=[
 ('MCP registry','Register approved HTTPS endpoints; probe and discover.','Add a reviewed profile, transport or provider authorization flow.','Host safety, credential scope, schema and timeout checks.'),
 ('Tool registry','Map existing built-in/discovered tools; label capabilities and entities.','Implement typed handlers or new adapter dispatch.','Current permissions, declared risk, validation and approval.'),
 ('Governance / guardrails','Configure allowed tools, ceilings, external processing and project access.','Add deterministic domain checks and coordinated schemas/tests.','Model output cannot grant authority or change policy.'),
 ('Gateways','Use verified Gemini/Groq workspace keys and supported adapters.','Implement provider contracts, error/usage handling or new protocols.','Fixed destinations, scoped secrets, policy and output limits.'),
 ('Harness / agents','Compose validated graphs and registered role/tool definitions.','Introduce new node semantics or recovery behavior through code.','Budgeted execution, checkpoints, state and stale-worker controls.'),
]
def placeholder(key):
 if key=='gateways':return [Gateways(),Spacer(1,12)]
 if key=='extensions':return [base.table(['COMPONENT','RUNTIME EXTENSION','ENGINEERING EXTENSION','BOUNDARY TO PRESERVE'],EXTENSIONS,[76,138,138,base.WIDTH-352]),Spacer(1,14)]
 return old_placeholder(key)

def frame(c,doc):
 c.saveState()
 if doc.page>1:
  c.setStrokeColor(base.LINE);c.setLineWidth(.6);c.line(52,H-44,W-52,H-44)
  c.setFont('Bold',8);c.setFillColor(base.GREEN);c.drawString(52,H-33,'EVOLVYN / EXTENSIBLE ARCHITECTURE')
  c.setFont('Body',7.5);c.setFillColor(base.MUTED);c.drawRightString(W-52,H-33,'REGISTRIES · GUARDRAILS · GATEWAYS')
 c.setStrokeColor(base.LINE);c.line(52,43,W-52,43)
 c.setFont('Body',7.5);c.setFillColor(base.MUTED);c.drawString(52,29,'25 OCT 2026  ·  SOURCE 8ac1e56')
 c.setFont('Bold',8);c.drawRightString(W-52,29,f'{doc.page:02d} / 10')
 c.restoreState()

OriginalDoc=base.ReportDoc
class ExtensibleDoc(OriginalDoc):
 def __init__(self,*args,**kwargs):
  kwargs.update(title='Evolvyn — Extensible Platform Architecture',subject='MCP registry, tool registry, governance, guardrails and application-level gateways')
  super().__init__(*args,**kwargs)

base.Cover=Cover
base.placeholder=placeholder
base.page_frame=frame
base.ReportDoc=ExtensibleDoc
if __name__=='__main__':base.build()
