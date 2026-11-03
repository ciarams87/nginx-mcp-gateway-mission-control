#!/usr/bin/env python3
"""Populate real NGINX metrics through MCP JSON-RPC. Python stdlib only."""
import argparse, json, time, urllib.request, urllib.error, concurrent.futures
p=argparse.ArgumentParser()
p.add_argument('--url',default='http://localhost:8080/mcp')
p.add_argument('--rounds',type=int,default=12)
p.add_argument('--burst',type=int,default=30)
a=p.parse_args()
seq=0

def call(method,params=None):
 global seq
 seq+=1
 body=json.dumps({'jsonrpc':'2.0','id':seq,'method':method,'params':params or {}}).encode()
 req=urllib.request.Request(a.url,data=body,headers={'Content-Type':'application/json','Accept':'application/json, text/event-stream'},method='POST')
 try:
  with urllib.request.urlopen(req,timeout=12) as r:
   status=r.status; content_type=r.headers.get('Content-Type',''); payload=r.read(100000).decode(errors='replace')
 except urllib.error.HTTPError as e:
  status=e.code;content_type=e.headers.get('Content-Type','');payload=e.read(100000).decode(errors='replace')
 except Exception as e:
  return f'network_error: {e}'
 try:
  data=json.loads(payload)
  outcome='rpc_error '+str(data['error']['code']) if 'error' in data else 'tool_error' if data.get('result',{}).get('isError') else 'success'
 except Exception:outcome='non_json_response'
 return f'{status} {outcome} ({content_type})'

def tool(name,arguments=None):return call('tools/call',{'name':name,'arguments':arguments or {}})
print('Gateway:',a.url)
for i in range(a.rounds):
 for name,args in [('list_pods',{}),('get_pod',{'name':'api-7d9c'}),('list_records',{}),('echo',{'message':'demo'}),('fail_operation',{}),('get_pod',{'name':'does-not-exist'}),('delete_pod',{'name':'api-7d9c'}),('delete_record',{'id':'customer-101'})]:
  print(f'{name:20} {tool(name,args)}')
 print('rpc unknown method: ',call('demo/method_does_not_exist'))
 print('rpc unknown tool:   ',tool('not_a_real_tool'))
 if i%3==0:
  print('slow_operation:    ',tool('slow_operation'))
 time.sleep(0.25)
print('Rate-limit burst:')
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
 results=list(pool.map(lambda _:tool('list_pods'),range(a.burst)))
from collections import Counter
print(Counter(results))
print('Wait 10-20 seconds for collector flush and Prometheus scrape, then refresh Grafana.')
