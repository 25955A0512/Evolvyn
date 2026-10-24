"""Bounded API entry points and payload-free audit records."""
import os
import time
import json,logging
from collections import defaultdict,deque
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware


def install(app,save):
    logger=logging.getLogger('evolvyn.requests')
    logger.setLevel(logging.INFO);logger.propagate=False
    if not logger.handlers:
        handler=logging.StreamHandler();handler.setFormatter(logging.Formatter('%(message)s'));logger.addHandler(handler)
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=os.getenv('ALLOWED_HOSTS','localhost,127.0.0.1,testserver').split(','))
    buckets=defaultdict(deque)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        # Validation errors must not reflect passwords or credential-like input values.
        return JSONResponse(status_code=422,content={'detail':[{'loc':error['loc'],'msg':error['msg'],'type':error['type']} for error in exc.errors()]})

    @app.middleware('http')
    async def guard(request:Request,call_next):
        from uuid import uuid4
        request.state.request_id=uuid4().hex
        # Backwards-compatible v1 entry point; the same authenticated handlers,
        # policies and audit middleware serve both paths.
        if request.scope['path'].startswith('/api/v1/'):
            request.scope['path']='/api/'+request.scope['path'][8:]
            request.scope['raw_path']=request.scope['path'].encode()
        length=request.headers.get('content-length','0')
        if length.isdigit() and int(length)>3_000_000:return JSONResponse(status_code=413,content={'detail':'Request exceeds 3 MB'})
        if request.url.path in ('/api/auth/login','/api/auth/register','/api/demo/session','/api/auth/password','/api/help/ask') or request.url.path.startswith('/api/auth/oauth/'):
            key=(request.client.host if request.client else 'unknown',request.url.path)
            now=time.monotonic();bucket=buckets[key]
            while bucket and bucket[0]<now-60:bucket.popleft()
            if len(bucket)>=20:return JSONResponse(status_code=429,content={'detail':'Too many authentication attempts; try again in a minute'},headers={'Retry-After':'60'})
            bucket.append(now)
        started=time.monotonic()
        from backend.policy import REQUEST
        token=REQUEST.set(request)
        try:response=await call_next(request)
        finally:REQUEST.reset(token)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        response.headers['X-Request-ID']=request.state.request_id
        logger.info(json.dumps({'request_id':request.state.request_id,'method':request.method,'route':getattr(request.scope.get('route'),'path','unmatched'),'status':response.status_code,'duration_ms':round((time.monotonic()-started)*1000,2)}))
        identity=getattr(request.state,'identity',None)
        if identity and request.method not in ('GET','HEAD','OPTIONS') and response.status_code<400:
            from datetime import datetime,timezone
            try:save(identity['organization_id'],'audit',{'request_id':request.state.request_id,'actor':identity.get('account_id'),'role':identity['role'],'method':request.method,'path':request.url.path,'status':response.status_code,'at':datetime.now(timezone.utc).isoformat()})
            except Exception:pass  # A disconnected database is separately reported by health checks.
        return response
