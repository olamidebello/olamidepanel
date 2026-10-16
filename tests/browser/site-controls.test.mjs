import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM} from 'jsdom';
const html=await readFile(new URL('../../panel/static/index.html',import.meta.url),'utf8');
const source=await readFile(new URL('../../panel/static/app.js',import.meta.url),'utf8');
const settings={redirects:[],indexes:false,errors:{},hotlink:false,referers:[],blocked_ips:[]};
async function fixture(){
 const dom=new JSDOM(html,{url:'https://hosting.example.com',runScripts:'outside-only'}),w=dom.window,calls=[];
 w.matchMedia=()=>({matches:false});w.HTMLElement.prototype.scrollIntoView=()=>{};w.structuredClone=structuredClone;
 w.fetch=async(path,options={})=>{calls.push({path,options});let status=200,body;
  if(path==='/api/me'){status=401;body={error:'Not signed in'};}
  else if(path==='/api/site-controls'&&options.method==='POST'){status=202;body={queued:true,message:'Saved and queued'};}
  else if(path==='/api/site-controls')body=[{id:1,name:'example.com',state:'published',revision:2,applied_revision:2,settings}];
  else body={};
  return {ok:status<400,status,headers:{get:()=> 'application/json'},json:async()=>body};
 };
 w.eval(source+'\nwindow.testing={siteControlsView,setUser:u=>me=u};');await new Promise(r=>setTimeout(r,0));w.testing.setUser({id:7,role:'user',csrf:'csrf',permissions:[]});
 return {w,calls,dom};
}
test('all five hosting controls render forms and save via the scoped API with CSRF and revision',async()=>{
 for(const name of ['Redirects','Indexes','Error Pages','Hotlink Protection','IP Blocker']){
  const {w,calls,dom}=await fixture();try{
   const panel=w.document.getElementById('detail');await w.testing.siteControlsView(name,panel);const form=panel.querySelector('form');assert.ok(form,name);
   if(name==='Redirects'){form.elements.path.value='/old';form.elements.target.value='https://example.net/new';}
   if(name==='Error Pages')form.elements.message.value='Custom error';
   if(name==='IP Blocker')form.elements.networks.value='192.0.2.1';
   form.dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await new Promise(r=>setTimeout(r,20));
   const saved=calls.find(c=>c.options.method==='POST');assert.ok(saved,name);assert.equal(saved.path,'/api/site-controls');assert.equal(saved.options.headers['X-CSRF-Token'],'csrf');const body=JSON.parse(saved.options.body);assert.equal(body.domain_id,1);assert.equal(body.revision,2);assert.equal(w.document.getElementById('message').textContent,'Saved and queued');
  }finally{dom.window.close();}
 }
});
test('read-only accounts see status without editable forms',async()=>{
 const {w,dom}=await fixture();try{w.testing.setUser({id:7,role:'readonly'});await w.testing.siteControlsView('Indexes',w.document.getElementById('detail'));assert.equal(w.document.getElementById('detail').querySelector('form'),null);}finally{dom.window.close();}
});
