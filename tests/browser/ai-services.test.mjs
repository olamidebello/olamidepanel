import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {JSDOM} from 'jsdom';
const html=await readFile(new URL('../../panel/static/index.html',import.meta.url),'utf8');
const source=await readFile(new URL('../../panel/static/app.js',import.meta.url),'utf8');
test('AI request confirms 30 percent markup and sends pricing version without exposing key',async()=>{
 const dom=new JSDOM(html,{url:'https://panel.example.com',runScripts:'outside-only'}),w=dom.window;
 try{
 w.matchMedia=()=>({matches:false});w.HTMLElement.prototype.scrollIntoView=()=>{};let post;
 w.fetch=async(path,options={})=>{
  if(path==='/api/me')return {ok:false,json:async()=>({error:'Sign in'})};
  if(options.method==='POST')post=JSON.parse(options.body);
  return {ok:true,headers:{get:()=> 'application/json'},json:async()=>options.method==='POST'?{id:1,answer:'Done',state:'completed',buy_cost:'0.01',user_charge:'0.013'}:{pricing_version:'version',balance:'1',requests:[],config:{enabled:true,model:'test-snapshot',domains:['example.com'],max_output_tokens:100,input_rate:'1',cached_rate:'0.25',output_rate:'2'}}};
 };
 w.eval(source+'\nwindow.testing={open,setUser:u=>me=u};');await new Promise(r=>setTimeout(r,0));w.testing.setUser({id:2,role:'user',csrf:'token',permissions:[]});await w.testing.open('AI Services');
 const d=w.document.getElementById('detail');assert.ok(d.textContent.includes('30%'));const form=d.querySelector('form');form.elements.prompt.value='Hello';form.querySelector('input[type=checkbox]').checked=true;form.dispatchEvent(new w.Event('submit',{cancelable:true}));await new Promise(r=>setTimeout(r,10));
 assert.equal(post.action,'chat');assert.equal(post.pricing_version,'version');assert.equal(post.confirmed,true);assert.equal(post.domain,'example.com');assert.equal('secret' in post,false);assert.ok(d.querySelector('pre').textContent.includes('Done'));
 }finally{dom.window.close()}
});
