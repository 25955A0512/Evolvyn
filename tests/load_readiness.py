"""Small HTTP readiness benchmark, explicitly not an agent throughput/capacity test."""
import asyncio,json,os,statistics,time
import httpx
async def main():
    count=100;concurrency=4;gate=asyncio.Semaphore(concurrency);latencies=[];errors=0
    async with httpx.AsyncClient(timeout=10,trust_env=False) as client:
        async def request():
            nonlocal errors
            async with gate:
                start=time.perf_counter()
                try:
                    result=await client.get(os.getenv('EVOLVYN_TEST_URL','http://localhost:3000')+'/api/v1/health')
                    if result.status_code!=200 or len(result.headers.get('X-Request-ID',''))!=32:errors+=1
                except httpx.HTTPError:errors+=1
                latencies.append((time.perf_counter()-start)*1000)
        start=time.perf_counter();await asyncio.gather(*(request() for _ in range(count)));elapsed=time.perf_counter()-start
    ordered=sorted(latencies)
    print(json.dumps({'scope':'Local nginx/API/PostgreSQL health only; excludes authentication, models, tools and user-capacity claims','requests':count,'concurrency':concurrency,'errors':errors,'elapsed_seconds':round(elapsed,3),'mean_ms':round(statistics.mean(ordered),2),'p50_ms':round(ordered[len(ordered)//2],2),'p95_ms':round(ordered[int(len(ordered)*.95)-1],2)}))
    assert errors==0
asyncio.run(main())
