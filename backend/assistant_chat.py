"""File-free LLM conversations using the existing durable worker and model boundaries."""
import asyncio,json

class AssistantChat:
    def __init__(self,services):self.s=services
    async def run(self,owner,id):
        s=self.s;run=s['claim_job'](s['conn'],owner,id)
        if not run:return
        from backend.execution_queue import WORKER
        worker=WORKER.set(run['worker']);heartbeat=asyncio.create_task(s['renew_lease'](owner,id))
        events=list(run.get('events',[]))
        try:
            async with asyncio.timeout(150):
                conversation=s['get'](owner,run['conversation'],'conversation')
                events.append({'stage':'respond','detail':'Requesting a real LLM reply; no business-data upload is required for conversation'})
                s['change_execution'](owner,id,{'events':events})
                if run.get('mode')=='evidence':raise ValueError('Chat needs a language model')
                from backend.model_access import model_scope,effective_mode
                with model_scope(owner,'supervisor'):
                    if effective_mode(run.get('mode','default'))=='evidence':raise ValueError('Conversational mode requires a real model')
                history=[{'role':m['role'],'text':m['text'][:1500]} for m in conversation['messages'][:-2] if m.get('channel')=='assistant_chat'][-6:]
                result=await s['AGENTS'].respond(owner,'supervisor',conversation,{'facts':[],'evidence':[]},'You are the Evolvyn conversational assistant. Answer the current message naturally, including greetings and platform questions. Do not demand a sales file for general chat. No business measurements or tool actions are established. User message: '+run['question'],{'conversation':{'text':json.dumps(history)}},run.get('mode','default'),False)
                text=result['text']
                events.append({'stage':'completed','detail':'Model reply received and saved; no business action executed'})
                if s['change_execution'](owner,id,{'state':'COMPLETED','output':text,'events':events,'chat_result':{k:v for k,v in result.items() if k!='text'}}):s['finish_message'](owner,run['conversation'],id,text)
        except asyncio.CancelledError:
            if s['stopping']():s['change_execution'](owner,id,{'state':'CREATED','worker':None,'lease_until':None})
            else:s['change_execution'](owner,id,{'state':'CANCELLED'})
            raise
        except Exception as caught:
            from backend.model_errors import failure
            code,error=failure(caught)
            error+=' Check Key vault. No action executed.'
            if s['change_execution'](owner,id,{'state':'FAILED','error_code':code,'error':error,'events':events+[{'stage':'failed','detail':error}]}):s['finish_message'](owner,run['conversation'],id,error)
        finally:
            heartbeat.cancel();await asyncio.gather(heartbeat,return_exceptions=True);WORKER.reset(worker)
