"""Validated line-item imports and SQL-derived e-commerce observations, without currency inference."""
import csv
import hashlib
import io
import json
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from fastapi import HTTPException

ALIASES={'sku':'product_id','product_sku':'product_id','order_number':'order_id','product':'product_name','name':'product_name','price':'unit_price','qty':'quantity','stock':'inventory','date':'order_date','created_at':'order_date','discount_amount':'discount','refund_amount':'refund'}
CENT=Decimal('.01')
MAX_ROWS=5000

def initialize(c):
    c.execute('CREATE TABLE IF NOT EXISTS commerce_datasets (document_id text PRIMARY KEY REFERENCES records(id) ON DELETE CASCADE,owner text NOT NULL,kind text NOT NULL,currency text,content_sha256 text NOT NULL)')
    c.execute("ALTER TABLE commerce_datasets ADD COLUMN IF NOT EXISTS metadata jsonb NOT NULL DEFAULT '{}'::jsonb")
    c.execute('CREATE INDEX IF NOT EXISTS commerce_dataset_owner ON commerce_datasets(owner)')
    c.execute('CREATE TABLE IF NOT EXISTS commerce_sales (document_id text REFERENCES commerce_datasets(document_id) ON DELETE CASCADE,row_number integer,order_id text NOT NULL,line_id text NOT NULL,product_id text NOT NULL,product_name text NOT NULL,quantity integer NOT NULL,unit_price numeric(24,2) NOT NULL,discount numeric(24,2) NOT NULL,refund numeric(24,2) NOT NULL,order_date date,status text NOT NULL,PRIMARY KEY(document_id,row_number))')
    c.execute('ALTER TABLE commerce_sales ALTER COLUMN discount DROP NOT NULL')
    c.execute('ALTER TABLE commerce_sales ALTER COLUMN refund DROP NOT NULL')
    c.execute('CREATE TABLE IF NOT EXISTS commerce_catalog (document_id text REFERENCES commerce_datasets(document_id) ON DELETE CASCADE,row_number integer,product_id text NOT NULL,product_name text NOT NULL,unit_price numeric(24,2) NOT NULL,inventory integer,PRIMARY KEY(document_id,product_id))')

def error(row,message):raise HTTPException(422,f'E-commerce CSV row {row}: {message}')
def money(value,row,field):
    try:
        number=Decimal(str(value or '').strip())
        if not number.is_finite() or number<0 or number>Decimal('1000000000000') or number.quantize(CENT)!=number:raise ValueError()
        return number
    except (ValueError,InvalidOperation):error(row,field+' must be a nonnegative decimal amount with at most two decimal places')
def integer(value,row,field,minimum=0):
    if not re.fullmatch(r'\d{1,9}',str(value or '').strip()) or int(value)<minimum:error(row,field+' must be an integer >= '+str(minimum))
    return int(value)
def identifier(value,row,field):
    value=str(value or '').strip()
    if not value or len(value)>200:error(row,field+' is required (maximum 200 characters)')
    return value
def parse(content):
    reader=csv.DictReader(io.StringIO(content),strict=True)
    original=reader.fieldnames or []
    headers=[ALIASES.get(re.sub(r'[^a-z0-9]+','_',str(h).strip().lower()).strip('_'),re.sub(r'[^a-z0-9]+','_',str(h).strip().lower()).strip('_')) for h in original]
    commerce='order_id' in headers or ('product_id' in headers and any(k in headers for k in ('unit_price','inventory')))
    if not commerce:return None
    if len(set(headers))!=len(headers):raise HTTPException(422,'E-commerce CSV has duplicate or ambiguous column names')
    kind='sales' if 'order_id' in headers else 'catalog'
    required={'product_id','quantity','unit_price'} if kind=='sales' else {'product_id','product_name','unit_price'}
    if not required<=set(headers):raise HTTPException(422,'E-commerce '+kind+' CSV requires columns: '+', '.join(sorted(required|({'order_id'} if kind=='sales' else set()))))
    rows=[];currencies=set();keys=set();order_dates={};warnings=[];line_ids=[]
    for number,raw in enumerate(reader,2):
        if number>MAX_ROWS+1:raise HTTPException(422,f'E-commerce imports are limited to {MAX_ROWS} rows; split the export into explicit snapshots')
        if None in raw or any(value is None for value in raw.values()):error(number,'column count does not match the header')
        row={header:str(raw[key]).strip() for key,header in zip(original,headers)}
        currency=row.get('currency','').upper()
        if currency and not re.fullmatch(r'[A-Z]{3}',currency):error(number,'currency must be a three-letter code')
        currencies.add(currency)
        item={'row_number':number,'product_id':identifier(row.get('product_id'),number,'product_id'),'product_name':row.get('product_name','')[:200],'unit_price':money(row.get('unit_price'),number,'unit_price')}
        if kind=='sales':
            item.update(order_id=identifier(row.get('order_id'),number,'order_id'),quantity=integer(row.get('quantity'),number,'quantity',1),discount=money(row['discount'],number,'discount') if 'discount' in row else None,refund=money(row['refund'],number,'refund') if 'refund' in row else None,line_id=row.get('line_id',''),status=row.get('status','paid').lower(),order_date=None)
            if item['status'] not in ('paid','completed','fulfilled','refunded','cancelled','pending','failed','void'):error(number,'unsupported order status; use paid/completed/fulfilled/refunded/cancelled/pending/failed/void')
            if (item['discount'] or Decimal(0))+(item['refund'] or Decimal(0))>item['unit_price']*item['quantity']:error(number,'discount plus refund exceeds the line gross sales')
            if item['status']=='refunded' and not item['refund']:error(number,'refunded status requires an explicit positive refund amount')
            if row.get('order_date'):
                try:item['order_date']=date.fromisoformat(row['order_date']) if len(row['order_date'])==10 else datetime.fromisoformat(row['order_date'].replace('Z','+00:00')).date()
                except ValueError:error(number,'order_date must be ISO YYYY-MM-DD or an ISO timestamp')
            if item['order_id'] in order_dates and order_dates[item['order_id']]!=item['order_date']:error(number,'all lines in an order must have the same date')
            order_dates[item['order_id']]=item['order_date']
            key=(item['order_id'],item['line_id'] or item['product_id']);line_ids.append(bool(item['line_id']))
        else:
            item['inventory']=integer(row['inventory'],number,'inventory') if row.get('inventory') else None
            key=item['product_id']
        if key in keys:error(number,'duplicate product/order line; supply unique line_id values when an order repeats the same SKU')
        keys.add(key);rows.append(item)
    if not rows:raise HTTPException(422,'E-commerce CSV contains no data rows')
    if len(currencies)>1:raise HTTPException(422,'One currency per e-commerce snapshot is required; missing and explicit currencies cannot be mixed')
    if line_ids and any(line_ids) and not all(line_ids):raise HTTPException(422,'Supply line_id on every sales row or omit it consistently')
    ignored=sorted(set(headers)-{'order_id','line_id','order_date','product_id','product_name','quantity','unit_price','discount','refund','inventory','currency','status'})
    if ignored:warnings.append('Unused columns (not included in metrics): '+', '.join(ignored))
    if kind=='sales' and not {'discount','refund'}<=set(headers):warnings.append('Missing discount/refund columns: net revenue and net AOV are unavailable. Gross sales and gross AOV are calculated separately.')
    if not next(iter(currencies)):warnings.append('Currency was not supplied; no currency has been inferred.')
    return {'kind':kind,'currency':next(iter(currencies)) or None,'rows':rows,'content_sha256':hashlib.sha256(content.encode()).hexdigest(),'warnings':warnings}

def persist(c,owner,id,parsed):
    c.execute('INSERT INTO commerce_datasets(document_id,owner,kind,currency,content_sha256,metadata) VALUES (%s,%s,%s,%s,%s,%s)',(id,owner,parsed['kind'],parsed['currency'],parsed['content_sha256'],json.dumps({'warnings':parsed['warnings']})))
    with c.cursor() as cursor:
        if parsed['kind']=='sales':
            cursor.executemany('INSERT INTO commerce_sales VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)',[(id,*[row[k] for k in ('row_number','order_id','line_id','product_id','product_name','quantity','unit_price','discount','refund','order_date','status')]) for row in parsed['rows']])
        else:
            cursor.executemany('INSERT INTO commerce_catalog VALUES (%s,%s,%s,%s,%s,%s)',[(id,*[row[k] for k in ('row_number','product_id','product_name','unit_price','inventory')]) for row in parsed['rows']])
    return metrics(c,owner,id)

def amount(value):return str(Decimal(value).quantize(CENT,rounding=ROUND_HALF_UP)) if value is not None else None
def metrics(c,owner,id):
    dataset=c.execute('SELECT * FROM commerce_datasets WHERE owner=%s AND document_id=%s',(owner,id)).fetchone()
    if not dataset:raise HTTPException(404,'Structured dataset not found')
    base={'dataset_id':id,'kind':dataset['kind'],'currency':dataset['currency'],'content_sha256':dataset['content_sha256'],'calculation_engine':'PostgreSQL exact numeric aggregates','citation':'commerce:'+id,'classification':'Calculated from user-uploaded data; source completeness and accounting definitions require validation','warnings':dataset['metadata'].get('warnings',[])}
    if dataset['kind']=='catalog':
        total=c.execute('SELECT count(*) AS products,count(inventory) AS stock_known,coalesce(sum(inventory),0) AS inventory_units,count(*) FILTER(WHERE inventory=0) AS out_of_stock FROM commerce_catalog WHERE document_id=%s',(id,)).fetchone()
        rows=c.execute('SELECT product_id,product_name,unit_price,inventory,row_number FROM commerce_catalog WHERE document_id=%s ORDER BY product_id LIMIT 50',(id,)).fetchall()
        return {**base,**total,'inventory_units':int(total['inventory_units']) if total['stock_known']==total['products'] else None,'items':[{**r,'unit_price':amount(r['unit_price'])} for r in rows],'net_revenue':None,'orders':None,'average_order_value':None,'definitions':{'products':'Unique product IDs in this catalog','revenue':'Unavailable: catalog prices and inventory are not sales'},'unavailable_metrics':['Revenue, orders and average order value require a sales-line export','Profit and margin require costs; acquisition metrics require spend and attribution']}
    included="status IN ('paid','completed','fulfilled','refunded')"
    total=c.execute(f'''SELECT count(DISTINCT order_id) AS orders,count(*) AS included_lines,coalesce(sum(quantity),0) AS units_sold,coalesce(sum(quantity*unit_price),0) AS gross_sales,coalesce(sum(discount),0) AS discounts,coalesce(sum(refund),0) AS refunds,coalesce(sum(quantity*unit_price-discount-refund),0) AS net_revenue,min(order_date) AS start,max(order_date) AS end,count(order_date) AS dated_lines,count(discount) AS discounts_known,count(refund) AS refunds_known FROM commerce_sales WHERE document_id=%s AND {included}''',(id,)).fetchone()
    excluded=c.execute(f'SELECT count(*) AS count FROM commerce_sales WHERE document_id=%s AND NOT ({included})',(id,)).fetchone()['count']
    net_known=total['discounts_known']==total['included_lines'] and total['refunds_known']==total['included_lines']
    if total['discounts_known']!=total['included_lines']:total['discounts']=None
    if total['refunds_known']!=total['included_lines']:total['refunds']=None
    if not net_known:total['net_revenue']=None
    products=c.execute(f'''SELECT product_id,max(product_name) AS product_name,sum(quantity) AS units_sold,count(DISTINCT order_id) AS orders,sum(quantity*unit_price) AS gross_sales,sum(quantity*unit_price-discount-refund) AS net_revenue FROM commerce_sales WHERE document_id=%s AND {included} GROUP BY product_id ORDER BY coalesce(sum(quantity*unit_price-discount-refund),sum(quantity*unit_price)) DESC,product_id LIMIT 50''',(id,)).fetchall()
    definition={'gross_sales':'SUM(quantity × unit_price) on paid/completed/fulfilled/refunded lines','net_revenue':'Gross sales minus line discounts and explicit line refunds; excludes tax/shipping; no FX conversion','orders':'COUNT(DISTINCT order_id) in included lines, including fully refunded orders','average_order_value':'Net revenue / distinct included orders (null when zero orders or discount/refund data is missing)','gross_average_order_value':'Gross sales / distinct included orders, before discounts/refunds; not net AOV','units_sold':'Sum of ordered units; refunds do not imply a known count of returned units','coverage':'Start/end are observed order dates, not proof of full-period coverage; timestamp dates use their supplied calendar date'}
    return {**base,**{k:(amount(total[k]) if k in ('gross_sales','discounts','refunds','net_revenue') else int(total[k])) for k in ('orders','included_lines','units_sold','gross_sales','discounts','refunds','net_revenue','dated_lines')},'average_order_value':amount(total['net_revenue']/total['orders']) if total['orders'] and net_known else None,'gross_average_order_value':amount(total['gross_sales']/total['orders']) if total['orders'] else None,'period':{'start':total['start'].isoformat() if total['start'] else None,'end':total['end'].isoformat() if total['end'] else None},'excluded_lines':excluded,'products':[{**p,'units_sold':int(p['units_sold']),'gross_sales':amount(p['gross_sales']),'net_revenue':amount(p['net_revenue']) if net_known else None} for p in products],'definitions':definition,'unavailable_metrics':['Profit/margin: cost data missing','Conversion: visitor/session data missing','CAC/attribution: spend and attribution data missing','Repeat purchase/LTV: customer identity and longitudinal coverage not established']}

def report(documents):
    datasets=[{**d['commerce'],'source':d['name']} for d in documents if d.get('commerce')]
    if not datasets:return None
    sales=[d for d in datasets if d['kind']=='sales'];primary=(sales or datasets)[-1]
    return {'primary':primary,'datasets':[{'dataset_id':d['dataset_id'],'source':d['source'],'kind':d['kind'],'citation':d['citation']} for d in datasets],'selection':'Latest attached sales snapshot (or latest catalog when no sales exist). Snapshots are never added together; overlapping exports could double-count orders.'}

def proposals(report):
    from uuid import uuid4
    primary=report['commerce']['primary'];citation=primary['citation'];market=[s['url'] for s in report.get('market_sources',[])[:2]]+[e['citation'] for e in report.get('evidence',[]) if e.get('citation','').startswith('registered-tool:')][:2]
    if primary['kind']=='sales' and primary['products']:
        top=primary['products'][0]
        title='Create a tracked product-page investigation for '+(top['product_name'] or top['product_id'])
        metric='net_revenue' if primary['net_revenue'] is not None else 'gross_sales'
        metric_label='net sales' if metric=='net_revenue' else 'gross sales (net revenue unavailable)'
        rationale=f"{top['product_id']} contributes {top[metric]} {primary['currency'] or '(currency unspecified)'} {metric_label} in this snapshot. This identifies observed product contribution, not demand or a cause. Review product clarity and customer feedback before a controlled content test."
        tasks=['Review the cited sales lines and confirm period/currency coverage','Review '+top['product_id']+' product-page content and consented customer feedback','Design a controlled content test; record baseline, owner and rollback before publishing']
    elif primary['kind']=='catalog':
        title='Create a tracked catalog-quality review'
        rationale=f"The catalog contains {primary.get('products',0)} products and {primary.get('out_of_stock',0)} reported stockouts. Sales and revenue cannot be inferred from catalog prices."
        tasks=['Validate product identifiers, prices and inventory with the store owner','Collect a dated sales-line export before deciding promotion spend','Review product content changes before any external publication']
    else:
        title='Create a tracked paid-order data review'
        rationale='No posted paid/refunded sales lines are present. Pending/cancelled lines do not establish realized sales or demand.'
        tasks=['Verify order statuses and export coverage','Collect posted sales lines with dates and currency','Do not infer a promotion opportunity from pending orders alone']
    return [{'id':str(uuid4()),'title':title,'rationale':rationale,'evidence':[citation]+market,'impact':3,'confidence':.5,'effort':2,'cost_estimate':None,'expected_benefit':'A verified investigation task and baseline. Sales lift is unknown and requires follow-up data and an appropriate control.','assumptions':['The uploaded snapshot is complete for the intended period','Net sales excludes shipping/tax; line amounts are not order totals'],'risks':['Incomplete exports','Seasonality and changing product mix','Public research may not represent this store’s customers'],'success_metric':report['success_metric'],'measurement_period_days':14,'rollback':'Do not publish changes from this internal task. Revert any later approved test if predefined guardrails worsen.','tasks':tasks,'status':'proposed','classification':'Evidence-linked experiment hypothesis; not a claimed market effect'}]

def compare(baseline,followup):
    if baseline['kind']!='sales' or followup['kind']!='sales':raise HTTPException(422,'Outcome measurement requires two sales snapshots; catalog prices are not revenue')
    if baseline['dataset_id']==followup['dataset_id'] or baseline['content_sha256']==followup['content_sha256']:raise HTTPException(422,'Follow-up must be new evidence, not the baseline or a renamed copy')
    if not baseline['currency'] or not followup['currency']:raise HTTPException(422,'Explicit currency is required for a financial outcome comparison')
    if baseline['currency']!=followup['currency']:raise HTTPException(422,'Baseline and follow-up must use the same currency')
    if not baseline['included_lines'] or not followup['included_lines'] or any(d['dated_lines']!=d['included_lines'] for d in (baseline,followup)):raise HTTPException(422,'All included sales lines need dates for outcome comparison')
    a,b=baseline['period'],followup['period']
    if b['start']<=a['end']:raise HTTPException(422,'Follow-up dates must be strictly later and nonoverlapping')
    before_days=(date.fromisoformat(a['end'])-date.fromisoformat(a['start'])).days+1
    after_days=(date.fromisoformat(b['end'])-date.fromisoformat(b['start'])).days+1
    changes={}
    for key in ('gross_sales','net_revenue','orders','average_order_value','gross_average_order_value','units_sold'):
        first,last=baseline[key],followup[key]
        changes[key]={'before':first,'after':last,'absolute_change':amount(Decimal(str(last))-Decimal(str(first))) if first is not None and last is not None else None,'percent_change':amount(100*(Decimal(str(last))-Decimal(str(first)))/Decimal(str(first))) if first is not None and last is not None and Decimal(str(first)) else None}
    return {'kind':'commerce','baseline':baseline,'followup':followup,'changes':changes,'observed_calendar_days':{'baseline':before_days,'followup':after_days},'comparable_duration':before_days==after_days,'classification':'Observed pre/post snapshot comparison, not causal attribution. Date spans do not prove complete coverage; unequal duration, traffic, seasonality and product mix can confound results.'}

def model_context(report):
    primary=report['commerce']['primary']
    return {**{k:v for k,v in primary.items() if k not in ('products','items','definitions')},'products':primary.get('products',[])[:5] if primary['kind']=='sales' else primary.get('products'),'catalog_items':primary.get('items',[])[:5],'definitions':primary['definitions'],'selection':report['commerce']['selection']}

def summary_lines(report):
    primary=report['commerce']['primary'];currency=primary['currency'] or 'currency unspecified'
    lines=['**Calculated business facts** ['+primary['citation']+']']
    if primary['kind']=='sales':
        lines.append(f"Net revenue: {primary['net_revenue'] if primary['net_revenue'] is not None else 'unavailable'} {currency}; distinct orders: {primary['orders']}; net average order value: {primary['average_order_value'] or 'unavailable'}; units sold: {primary['units_sold']}.")
        lines.append(f"Gross sales {primary['gross_sales']} minus discounts {primary['discounts'] if primary['discounts'] is not None else 'unavailable'} and refunds {primary['refunds'] if primary['refunds'] is not None else 'unavailable'}; tax and shipping excluded. {primary['excluded_lines']} non-posted lines excluded.")
        lines+=['Product '+p['product_id']+': '+str(p['net_revenue'] if p['net_revenue'] is not None else p['gross_sales'])+' '+currency+(' net sales, ' if p['net_revenue'] is not None else ' gross sales (net unavailable), ')+str(p['units_sold'])+' units.' for p in primary['products'][:3]]
    else:lines.append(f"Catalog: {primary['products']} products; {primary['out_of_stock']} reported stockouts. Revenue, orders and AOV are unavailable without sales data.")
    lines+=primary.get('warnings',[])
    lines.append(report['commerce']['selection'])
    if report.get('market_sources'):
        lines.append('**External discussion leads, not verified market demand**\n'+'\n'.join(s['title']+' ['+s['url']+'] — published '+str(s.get('publication_date') or 'unknown')+'; retrieved '+s['retrieved_at'] for s in report['market_sources'][:3]))
    for s in report.get('connector_status',[]):lines.append('Connector '+s['tool']+': '+s['status']+' '+str(s.get('retrieved_at') or s.get('detail','')))
    if report.get('research_status',{}).get('status')=='unavailable':lines.append(report['research_status']['detail'])
    lines.append('**Hypothesis:** product clarity, offer fit or availability may warrant investigation; these metrics alone establish no cause. Expected sales lift is unknown. The supported approved action creates internal tasks; it does not publish or change store prices.')
    return lines
