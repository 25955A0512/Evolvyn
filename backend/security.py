"""Bounded API entry points and payload-free audit records."""
import os
import time
from collections import defaultdict,deque
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.trustedhost import TrustedHostMiddleware


def install(app,save):
    app.add_middleware(TrustedHostMiddleware,allowed_hosts=os.getenv('ALLOWED_HOSTS','localhost,127.0.0.1,testserver').split(','))
    buckets=defaultdict(deque)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):
        # Validation errors must not reflect passwords or credential-like input values.
        return JSONResponse(status_code=422,content={'detail':[{'loc':error['loc'],'msg':error['msg'],'type':error['type']} for error in exc.errors()]})

    @app.middleware('http')
    async def guard(request:Request,call_next):
        length=request.headers.get('content-length','0')
        if length.isdigit() and int(length)>3_000_000:return JSONResponse(status_code=413,content={'detail':'Request exceeds 3 MB'})
        if request.url.path in ('/api/auth/login','/api/auth/register','/api/demo/session'):
            key=(request.client.host if request.client else 'unknown',request.url.path)
            now=time.monotonic();bucket=buckets[key]
            while bucket and bucket[0]<now-60:bucket.popleft()
            if len(bucket)>=20:return JSONResponse(status_code=429,content={'detail':'Too many authentication attempts; try again in a minute'},headers={'Retry-After':'60'})
            bucket.append(now)
        from backend.policy import REQUEST
        token=REQUEST.set(request)
        try:response=await call_next(request)
        finally:REQUEST.reset(token)
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['Referrer-Policy']='no-referrer'
        identity=getattr(request.state,'identity',None)
        if identity and request.method not in ('GET','HEAD','OPTIONS') and response.status_code<400:
            from datetime import datetime,timezone
            try:save(identity['organization_id'],'audit',{'actor':identity.get('account_id'),'role':identity['role'],'method':request.method,'path':request.url.path,'status':response.status_code,'at':datetime.now(timezone.utc).isoformat()})
            except Exception:pass  # A disconnected database is separately reported by health checks.
        return response
