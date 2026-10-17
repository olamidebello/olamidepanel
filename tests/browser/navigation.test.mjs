import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM} from 'jsdom';
const html=await readFile(new URL('../../panel/static/index.html',import.meta.url),'utf8');
const source=await readFile(new URL('../../panel/static/app.js',import.meta.url),'utf8');
async function fixture(){
 const dom=new JSDOM(html,{url:'https://panel.example.com',runScripts:'outside-only'}),w=dom.window;
 w.matchMedia=()=>({matches:false});w.HTMLElement.prototype.scrollIntoView=()=>{};
 const pending=[];
 w.fetch=async path=>{
  if(path==='/api/me')return {ok:false,json:async()=>({error:'Not signed in'})};
  return new Promise(resolve=>pending.push({path,resolve:body=>resolve({ok:true,headers:{get:()=> 'application/json'},json:async()=>body})}));
 };
 w.eval(source+'\nwindow.testing={open,render,setUser:u=>me=u};');
 await new Promise(r=>setTimeout(r,0));
 w.testing.setUser({id:1,role:'root',permissions:['users.manage','domains.write']});
 return {dom,w,pending};
}
test('late module response cannot overwrite or append to newer screen',async()=>{
 const {dom,w,pending}=await fixture();try{
  const first=w.testing.open('Domains');
  assert.equal(pending[0].path,'/api/domains');
  await w.testing.open('Track DNS');
  pending[0].resolve([{name:'late.example.com'}]);await first;
  const detail=w.document.getElementById('detail');
  assert.equal(detail.querySelector('h2').textContent,'Track DNS');
  assert.equal(detail.textContent.includes('late.example.com'),false);
  assert.equal(pending.length,1,'stale view must not start its next request');
 }finally{dom.window.close();}
});
test('category render invalidates pending module and keeps detail hidden',async()=>{
 const {dom,w,pending}=await fixture();try{
  const first=w.testing.open('Server Metrics');w.testing.render();
  pending[0].resolve({hostname:'old-server'});await first;
  const detail=w.document.getElementById('detail');
  assert.equal(detail.hidden,true);assert.equal(detail.textContent.includes('old-server'),false);
 }finally{dom.window.close();}
});
test('late planned-module response stays detached after another tool opens',async()=>{
 const {dom,w,pending}=await fixture();try{
  const first=w.testing.open('Email Accounts');await w.testing.open('Track DNS');
  pending[0].resolve({tools:[{name:'Email Accounts',detail:'old unavailable module'}]});await first;
  const detail=w.document.getElementById('detail');
  assert.equal(detail.querySelector('h2').textContent,'Track DNS');
  assert.equal(detail.textContent.includes('old unavailable module'),false);
 }finally{dom.window.close();}
});
