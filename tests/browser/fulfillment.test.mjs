import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM} from 'jsdom';
const html=await readFile(new URL('../../panel/static/index.html',import.meta.url),'utf8');
const source=await readFile(new URL('../../panel/static/app.js',import.meta.url),'utf8');
async function fixture(role,state){
 const dom=new JSDOM(html,{url:'https://hosting.example.com',runScripts:'outside-only'}),w=dom.window,calls=[];
 w.matchMedia=()=>({matches:false});w.HTMLElement.prototype.scrollIntoView=()=>{};
 w.fetch=async(path,options={})=>{calls.push({path,options});let status=200,body={};
  if(path==='/api/me'){status=401;body={error:'Not signed in'};}
  if(path==='/api/marketplace/capabilities')body={manage_all:role==='root',manage_own:false};
  if(path.startsWith('/api/marketplace/orders?'))body=[{id:1,owner:7,seller_id:0,status:'approved',price_cents:1500,currency:'USD',created:1,username:'buyer',plan_snapshot:JSON.stringify({name:'Business'}),provisioning:{state,message:'Account activation status',attempts:1},service:state==='active'?{state:'active',disk_bytes:2*1024**3,websites:3,expires_at:2000000000}:null}];
  return {ok:status<400,status,headers:{get:()=> 'application/json'},json:async()=>body};
 };
 w.eval(source+'\nwindow.testing={marketplaceView,setUser:u=>me=u};');await new Promise(r=>setTimeout(r,0));w.testing.setUser({id:7,role,csrf:'test-csrf',permissions:role==='root'?['users.manage']:[]});
 return {w,calls,dom};
}
test('paid active order shows resources and hides repeat checkout',async()=>{
 const {w,dom}=await fixture('user','active');try{const panel=w.document.getElementById('detail');await w.testing.marketplaceView('My Orders',panel);assert.match(panel.textContent,/Provisioning: active/);assert.match(panel.textContent,/2 GiB panel storage/);assert.ok(![...panel.querySelectorAll('button')].some(b=>b.textContent==='Payment options'));}finally{dom.window.close();}
});
test('only operator sees retry and retry uses scoped CSRF API',async()=>{
 for(const role of ['user','root']){const {w,calls,dom}=await fixture(role,'needs_attention');try{const panel=w.document.getElementById('detail');await w.testing.marketplaceView('My Orders',panel);const retry=[...panel.querySelectorAll('button')].find(b=>b.textContent==='Retry account activation');assert.equal(Boolean(retry),role==='root');if(retry){retry.click();await new Promise(r=>setTimeout(r,25));const post=calls.find(c=>c.path==='/api/marketplace/orders/retry');assert.ok(post);assert.equal(post.options.headers['X-CSRF-Token'],'test-csrf');assert.equal(JSON.parse(post.options.body).id,1);}}finally{dom.window.close();}}
});
