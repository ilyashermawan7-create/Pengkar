import test from 'node:test';
import assert from 'node:assert/strict';
import {requestData} from '../frontend/requestData.mjs';
test('request preserves parsed data and authentication options',async()=>{
 const original=globalThis.fetch;
 try{
  globalThis.fetch=async(url,options)=>{assert.equal(url,'/api/dashboard');assert.equal(options.headers.Authorization,'Bearer test');return new Response(JSON.stringify({activities:[]}),{headers:{'content-type':'application/json'}});};
  const {data}=await requestData('/api/dashboard',{headers:{Authorization:'Bearer test'}});
  assert.deepEqual(data,{activities:[]});
 }finally{globalThis.fetch=original;}
});
test('stalled login requests time out rather than keep the button busy forever',async()=>{
 const original=globalThis.fetch;
 try{
  globalThis.fetch=async(_,options)=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError'))));
  await assert.rejects(requestData('/api/login',{},10),/Server belum merespons/);
 }finally{globalThis.fetch=original;}
});
test('timeout covers stalled response body as well as initial connection',async()=>{
 const original=globalThis.fetch;
 try{
  globalThis.fetch=async(_,options)=>({headers:new Headers({'content-type':'application/json'}),json:()=>new Promise((resolve,reject)=>options.signal.addEventListener('abort',()=>reject(new DOMException('Aborted','AbortError'))))});
  await assert.rejects(requestData('/api/dashboard',{},10),/Server belum merespons/);
 }finally{globalThis.fetch=original;}
});
test('invalid JSON reports a recoverable loading error',async()=>{
 const original=globalThis.fetch;
 try{globalThis.fetch=async()=>new Response('{',{headers:{'content-type':'application/json'}});await assert.rejects(requestData('/api/dashboard'),/belum termuat lengkap/);}
 finally{globalThis.fetch=original;}
});
