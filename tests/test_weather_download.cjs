const fs=require('fs'),vm=require('vm'),assert=require('assert');
async function scenario(fail=false){
 const nodes={};for(const id of ['preferred-country','preferred-link','preference-status','apk-download','apk-checksum','build-status'])nodes[id]={hidden:true,children:[],append(n){this.children.push(n)}};
 const storage=new Map([['africaweather-preferred-country','nigeria']]),events=[];
 const list=[{slug:'nigeria',name:'Nigeria',domain:'weathernigeria.africandroid.world'},{slug:'algeria',name:'Algeria',domain:'weatheralgeria.africandroid.world'}];
 const context={document:{getElementById:id=>nodes[id],createElement:()=>({})},window:{addEventListener(){},dispatchEvent:event=>events.push(event)},localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},CustomEvent:class{constructor(type,o){this.type=type;this.detail=o.detail}},URL,fetch:async url=>({ok:!fail,json:async()=>url.includes('countries.json')?list:[{name:'Weather build',assets:[{name:'AfricaWeather.apk',browser_download_url:'https://github.com/olamidebello/olamidepanel/releases/download/test/AfricaWeather.apk'}]}]})};
 vm.runInNewContext(fs.readFileSync('olamidepanel/deploy/africaweather/download.js','utf8'),context);
 await new Promise(r=>setImmediate(r));
 if(fail){assert.equal(nodes['apk-download'].hidden,true);assert.match(nodes['build-status'].textContent,/not available/);return}
 assert.equal(nodes['preferred-country'].value,'nigeria');assert.equal(nodes['preferred-link'].href,'https://weathernigeria.africandroid.world');assert.equal(nodes['apk-download'].hidden,false);
 nodes['preferred-country'].value='algeria';nodes['preferred-country'].onchange();assert.equal(storage.get('africaweather-preferred-country'),'algeria');assert.equal(nodes['preferred-link'].href,'https://weatheralgeria.africandroid.world');
 nodes['preferred-country'].value='';nodes['preferred-country'].onchange();assert.equal(storage.has('africaweather-preferred-country'),false);assert.equal(nodes['preferred-link'].hidden,true);
}
(async()=>{await scenario();await scenario(true);console.log('Download and preferred-country checks passed')})().catch(e=>{console.error(e);process.exit(1)});
