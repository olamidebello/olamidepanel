import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM} from 'jsdom';
const html=await readFile(new URL('../../panel/static/index.html',import.meta.url),'utf8');
const source=await readFile(new URL('../../panel/static/app.js',import.meta.url),'utf8');
test('bulk selection sends only selected domains and shared gateway IDs with CSRF',async()=>{
 const dom=new JSDOM(html,{url:'https://panel.example.com',runScripts:'outside-only'}),w=dom.window;
 try{
 w.matchMedia=()=>({matches:false});w.HTMLElement.prototype.scrollIntoView=()=>{};w.confirm=()=>true;const calls=[];
 w.fetch=async(path,options={})=>{calls.push({path,options});if(path==='/api/me')return {ok:false,json:async()=>({error:'Sign in'})};return {ok:true,headers:{get:()=> 'application/json'},json:async()=>({domains:[{name:'one.example.com'},{name:'two.example.com'}],gateways:[{id:5,label:'Shared',provider:'stripe',mode:'test',enabled:true}],jobs:[]})}};
 w.eval(source+'\nwindow.testing={open,setUser:u=>me=u};');await new Promise(r=>setTimeout(r,0));w.testing.setUser({id:1,role:'root',csrf:'csrf',permissions:['users.manage']});await w.testing.open('Domain Marketplace Deployment');
 const d=w.document.getElementById('detail'),filter=d.querySelector('input[type=search]');filter.value='one.';filter.dispatchEvent(new w.Event('input'));
 const all=d.querySelector('input[type=checkbox]');all.checked=true;all.dispatchEvent(new w.Event('change'));Array.from(d.querySelectorAll('input[type=checkbox]')).find(x=>x.value==='5').checked=true;
 d.querySelector('form').dispatchEvent(new w.Event('submit',{cancelable:true}));await new Promise(r=>setTimeout(r,10));const post=calls.find(c=>c.options.method==='POST');assert.ok(post);const body=JSON.parse(post.options.body);assert.deepEqual(body.domains,['one.example.com']);assert.deepEqual(body.gateway_ids,[5]);assert.equal(body.confirmed,true);assert.equal(post.options.headers['X-CSRF-Token'],'csrf');
 }finally{dom.window.close()}
});
