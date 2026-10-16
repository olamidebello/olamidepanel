const $=id=>document.getElementById(id);let marketplaceMenu=[],selectedStore=null;let me,category='Overview',cwd='';
const groups={Marketplace:['Marketplace Dashboard','Hosting Plans','Browse Stores','My Orders','Reseller Catalog','Store Orders','Store Settings','Payment Gateways','Payments'],Files:['File Manager','Images','Directory Privacy','Disk Usage','FTP Accounts','FTP Connections','Anonymous FTP','Web Disk','Git Version Control','Git Deployment','Backups','Backup Wizard','File Restoration'],Domains:['Domains','Redirects','DNS Zone Editor','Dynamic DNS','Site Publisher','Site Builder','SEO','Social Media'],Email:['Email Accounts','Forwarders','Domain Forwarders','Autoresponders','Default Address','Email Routing','Email Filters','Global Filters','Email Deliverability','Email Disk Usage','Address Importer','Archive','Mailing Lists','BoxTrapper','Greylisting','Encryption','Calendars and Contacts','Calendar Sharing','Calendar Delegation','Spam Filters','Track Delivery','Webmail'],Databases:['Database Manager','Database Users','Database Wizard','phpMyAdmin','Remote Database Access','PostgreSQL','PostgreSQL Wizard','phpPgAdmin'],Security:['SSH Access','IP Blocker','SSL/TLS','Private Keys','Certificate Signing Requests','Certificates','SSL Sites','SSL Status','AutoSSL','ModSecurity','Hotlink Protection','Leech Protection','Two-Factor Authentication','API Tokens','Security Policy'],Software:['PHP Manager','PHP-FPM','PHP INI Editor','Application Manager','Environment Variables','Application Dependencies','Optimize Website','Perl Modules','PEAR Packages','RubyGems','Ruby on Rails','Application Installer'],Metrics:['Server Metrics','Visitors','Errors','Bandwidth','Raw Access','AWStats','Analog Stats','Webalizer','FTP Statistics','Metrics Editor','Resource Usage','Site Monitoring'],Advanced:['Terminal','Cron Jobs','Track DNS','Indexes','Error Pages','Apache Handlers','MIME Types','API Shell','Virus Scanner'],Preferences:['Password and Security','Language','Contact Information','Account Preferences','User Manager','Manage Team'],Administration:['Module Readiness','Reseller Access','Hosting Catalog','Access Control','Create Panel User','Audit Log','List Accounts','Suspended Accounts','Account Provisioning','Account Suspension','Account Termination','Shell Access','IP Assignment','Bandwidth Limits','Packages','Feature Manager','Resellers','Server Configuration','Hostname and Resolvers','IP Management','DNS Zones','DNS Templates','DNS Cluster','Configuration Cluster','Backup Configuration','Backup Restoration','Account Transfers','Apache Configuration','PHP Configuration','Mail Configuration','FTP Configuration','Service Manager','Log Rotation','Package Management','Database Services','Mail Queue','Delivery Reports','Brute Force Protection','Host Access Control','Compiler Access','Service Certificates','Process Manager','Task Queue','Service Restarts','System Reboot','Contact Manager','Hooks','Plugins','Branding','Themes and Locales','Support'],Integrations:['WP Toolkit','Softaculous','CloudLinux','LiteSpeed','JetBackup','Comet Backup','Imunify','External DNS/CDN','Billing','External Monitoring','AI Services']};
const implemented=['Redirects','Indexes','Error Pages','Hotlink Protection','IP Blocker','Track DNS','User Manager','List Accounts','Suspended Accounts','Account Suspension','Account Termination','Resellers','Browse Stores','Store Orders','Store Settings','Two-Factor Authentication','Images','Disk Usage','Backups','Backup Wizard','File Restoration','Site Publisher','Payment Gateways','Payments','Module Readiness','Reseller Access','Reseller Catalog','Marketplace Dashboard','Hosting Plans','My Orders','Hosting Catalog','Contact Information','Password and Security','Access Control','File Manager','Domains','Server Metrics','Create Panel User','Audit Log'];
function el(tag,text,cls){const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x}
async function api(path,body){const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-CSRF-Token':me?.csrf||''}:{},body:body?JSON.stringify(body):undefined});if(!r.ok){let d=await r.json();throw Error(d.error)}return r.headers.get('Content-Type')?.includes('json')?r.json():null}
function guard(fn){return async(...args)=>{try{$('message').textContent='';await fn(...args)}catch(e){$('message').textContent=e.message}}}
function form(fields,submit){let f=el('form');for(const [name,type]of fields){let l=el('label',name);let i=el(type==='textarea'?'textarea':'input');i.name=name;if(type!=='textarea')i.type=type;i.required=true;l.append(i);f.append(l)}f.append(el('button','Save'));f.onsubmit=guard(async e=>{e.preventDefault();await submit(Object.fromEntries(new FormData(f)));});return f}
let toolFilter='available';
let favorites;
try { favorites=JSON.parse(localStorage.getItem('olamide-favorites')||'[]'); if(!Array.isArray(favorites))favorites=[]; } catch { favorites=[]; }
const navIcons={Marketplace:'▧',Overview:'◈',Files:'▤',Domains:'◎',Email:'✉',Databases:'▥',Security:'♧',Software:'⌘',Metrics:'▥',Advanced:'⌁',Preferences:'⚙',Administration:'▦',Integrations:'◇'};
function render(){
 let nav=$('nav');nav.replaceChildren();
 for(const name of ['Overview',...Object.keys(groups)].filter(n=>me?.permissions?.includes('users.manage')||n!=='Administration')){
  let b=el('button',undefined,name===category?'active':'');b.append(el('span',navIcons[name]||'◇','nav-icon'),el('span',name));
  b.setAttribute('aria-current',name===category?'page':'false');b.onclick=()=>{category=name;history.pushState(null,'','#category='+encodeURIComponent(name));render()};nav.append(b);
  if(name==='Marketplace'&&category==='Marketplace'){for(const item of marketplaceMenu){const link=el('button',item.name,'marketplace-subnav');link.onclick=guard(()=>open(item.name));nav.append(link)}}
 }
 $('heading').textContent=category==='Overview'?'Hosting overview':category;$('crumb').textContent=category;
 $('sectionTitle').textContent=category==='Overview'?'Your hosting tools':category+' tools';
 $('detail').hidden=true;$('tools').replaceChildren();let count=0;
 let entries=Object.entries(groups).filter(([g])=>(category==='Overview'||g===category)&&(me?.permissions?.includes('users.manage')||g!=='Administration'));
 for(const[g,names]of entries)for(const name of names){
  if(g==='Marketplace'&&!marketplaceMenu.some(item=>item.name===name))continue;
  if(name==='Reseller Catalog'&&me.role!=='reseller')continue;
  if(name==='Payment Gateways'&&!me.permissions.includes('users.manage')&&me.role!=='reseller')continue;
  if(['User Manager','List Accounts','Suspended Accounts','Account Suspension','Account Termination','Resellers'].includes(name)&&!me.permissions.includes('users.manage'))continue;
  const available=implemented.includes(name);
  if(!(name+' '+g).toLowerCase().includes($('search').value.toLowerCase()) || toolFilter==='available'&&!available || toolFilter==='favorites'&&!favorites.includes(name))continue;
  count++;let card=el('article',undefined,'card'),b=el('button',undefined,'tool-open');
  b.append(el('span',navIcons[g]||'◇','icon'),el('h3',name),el('p',g+' / '+(available?'Manage workspace':'Coming to your workspace')),el('span',available?name==='Domains'?'Inventory only':'Available':'Planned',available?'badge':'badge pending'));
  b.onclick=guard(()=>available?open(name):moduleStatusView(name));
  let star=el('button',favorites.includes(name)?'★':'☆','favorite');star.setAttribute('aria-label',(favorites.includes(name)?'Unpin ':'Pin ')+name);star.setAttribute('aria-pressed',String(favorites.includes(name)));
  star.onclick=()=>{favorites=favorites.includes(name)?favorites.filter(n=>n!==name):[...favorites,name];try{localStorage.setItem('olamide-favorites',JSON.stringify(favorites))}catch{}render()};
  card.append(b,star);$('tools').append(card);
 }
 $('resultCount').textContent=count+' tools';
 if(!count)$('tools').append(el('div',toolFilter==='favorites'?'Star a tool to make it a favorite.':'No tools match. Try another search or category.','empty-state'));
 document.querySelectorAll('[data-filter]').forEach(b=>{b.classList.toggle('active',b.dataset.filter===toolFilter);b.setAttribute('aria-pressed',String(b.dataset.filter===toolFilter))});
}
async function openBase(name){let d=$('detail');d.replaceChildren(el('h2',name));d.hidden=false;d.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});d.focus({preventScroll:true});if(!implemented.includes(name)){await moduleStatusView(name);return}
if(name==='Access Control'){
 d.append(el('p','Manage panel roles and suspend or restore lower-level accounts. Panel root controls OlamidePanel permissions; Linux root privileges are not granted.'));
 const [roles,users]=await Promise.all([api('roles'),api('users')]);
 const summary=el('div',undefined,'access-summary');
 for(const [label,value]of [['Accounts',users.length],['Active',users.filter(x=>x.active).length],['Suspended',users.filter(x=>!x.active).length]]){let card=el('div',undefined,'metric');card.append(el('small',label),el('strong',String(value)));summary.append(card)}d.append(summary);
 const list=el('div',undefined,'account-list');d.append(list);
 const search=el('input');search.type='search';search.placeholder='Filter accounts by username or role';search.setAttribute('aria-label','Filter accounts');d.insertBefore(search,list);
 const renderUsers=()=>{list.replaceChildren();for(const user of users.filter(u=>(u.username+' '+u.role).includes(search.value.toLowerCase()))){
  const row=el('div',undefined,'account-row');const info=el('div');info.append(el('strong',user.username),el('p',user.role+' · '+(user.active?'Active':'Suspended')));row.append(info);
  const level=roles.find(r=>r.role===me.role)?.level||0;const targetLevel=roles.find(r=>r.role===user.role)?.level??100;
  if(user.id!==me.id&&targetLevel<level){
   const select=el('select');select.setAttribute('aria-label','Role for '+user.username);for(const role of roles.filter(r=>r.level<level)){const option=el('option',role.role.replaceAll('_',' '));option.value=role.role;option.selected=role.role===user.role;select.append(option)}row.append(select);
   const save=el('button','Save role');save.onclick=guard(async()=>{await api('users/update',{id:user.id,role:select.value,active:Boolean(user.active)});await open(name)});
   const toggle=el('button',user.active?'Suspend':'Restore');toggle.onclick=guard(async()=>{await api('users/update',{id:user.id,role:user.role,active:!user.active});await open(name)});const manage=el('button','Manage');manage.onclick=guard(()=>accountEditor(user));row.append(save,toggle,manage);
  }else row.append(el('span',user.id===me.id?'Your account':'Protected level','badge'));list.append(row);
 }};search.oninput=renderUsers;renderUsers();
 d.append(el('h3','Role permissions'));
 for(const role of roles){const item=el('details');item.append(el('summary',role.role.replaceAll('_',' ')+' · Level '+role.level),el('p',role.permissions.join(' · ')));d.append(item)}
 d.append(el('h3','Register a panel user'));d.append(await userRegistration());
}
if(name==='Domains'){d.append(el('p','Save domain inventory here, then open Site Publisher to request a DNS-verified static website. DNS records must be managed at your DNS provider.'));d.append(form([['name','text']],async b=>{let r=await api('domains',b);$('message').textContent=r.status;await open(name)}));for(const x of await api('domains'))d.append(el('p',x.name))}
if(name==='File Manager'){d.append(el('p','Account files /'+cwd));if(cwd){let back=el('button','Up');back.onclick=guard(async()=>{cwd=cwd.split('/').slice(0,-1).join('/');await open(name)});d.append(back)}const files=await api('files?path='+encodeURIComponent(cwd));for(const x of files){let b=el('button',(x.directory?'▸ ':'')+x.name);b.onclick=guard(async()=>{let path=[cwd,x.name].filter(Boolean).join('/');if(x.directory){cwd=path;return open(name)}let r=await api('files?path='+encodeURIComponent(path));let f=form([['content','textarea']],async val=>{await api('files',{action:'write',path,content:val.content});$('message').textContent='File saved'});f.elements.content.value=r.content;d.append(f)});d.append(b)}d.append(el('h3','Create file'));d.append(form([['path','text'],['content','textarea']],async b=>{await api('files',{...b,path:[cwd,b.path].filter(Boolean).join('/'),action:'write'});await open(name)}));d.append(el('h3','Create folder'));d.append(form([['path','text']],async b=>{await api('files',{action:'mkdir',path:[cwd,b.path].filter(Boolean).join('/')});await open(name)}))}
if(name==='Server Metrics')d.append(el('pre',JSON.stringify(await api('metrics'),null,2)));
if(name==='Audit Log')for(const x of await api('audit'))d.append(el('p',new Date(x.created*1000).toLocaleString()+' · '+x.actor+' · '+x.action));
if(name==='Create Panel User'){d.append(el('p','Register a panel account. This does not create a Linux account.'));d.append(await userRegistration())}}
async function userRegistration(){
 const roles=await api('roles');const f=form([['username','text'],['password','password']],async b=>{await api('users',{...b,role:f.elements.role.value});f.reset();$('message').textContent='Panel account registered'});
 const label=el('label','Access level');const select=el('select');select.name='role';
 for(const role of roles){let option=el('option',role.role.replaceAll('_',' '));option.value=role.role;option.selected=role.role==='user';select.append(option)}label.append(select);f.insertBefore(label,f.lastElementChild);f.elements.password.minLength=14;return f;
}
async function start(){me=await api('me');marketplaceMenu=await api('marketplace/navigation');$('login').hidden=true;$('workspace').hidden=false;$('logout').hidden=false;render();let m=await api('metrics');$('metrics').replaceChildren();for(const[label,value]of [['SERVER',m.hostname],['DISK USED',(m.disk_used/2**30).toFixed(1)+' GB'],['SYSTEM LOAD',m.load[0].toFixed(2)]]){let box=el('div',undefined,'metric');box.append(el('small',label),el('strong',value),el('small','LIVE SERVER DATA'));$('metrics').append(box)}await restoreNavigation()}
$('loginForm').onsubmit=guard(async e=>{e.preventDefault();await api('login',{...Object.fromEntries(new FormData(e.target)),accept_terms:e.target.elements.accept_terms.checked});e.target.reset();await start()});$('logout').onclick=guard(async()=>{await api('logout',{});location.reload()});$('search').oninput=render;start().catch(()=>{});

function setTheme(theme){document.documentElement.dataset.theme=theme;$('theme').setAttribute('aria-label',theme==='dark'?'Use light theme':'Use dark theme');$('theme').setAttribute('aria-pressed',String(theme==='dark'));try{localStorage.setItem('olamide-theme',theme)}catch{}}
let savedTheme;try{savedTheme=localStorage.getItem('olamide-theme')}catch{}
setTheme(savedTheme||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'));
$('theme').onclick=()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark');
$('help').onclick=()=>$('guide').showModal();$('closeGuide').onclick=()=>$('guide').close();
$('quickFiles').onclick=guard(()=>open('File Manager'));$('quickDomain').onclick=guard(()=>open('Domains'));$('guideMetrics').onclick=guard(()=>open('Server Metrics'));
$('showAvailable').onclick=()=>{category='Overview';toolFilter='av…5410 tokens truncated…('span',row.mode.toUpperCase()+' · '+row.state,'badge'),el('p',row.provider+' · '+money(row.amount_cents,row.currency)+' · Store '+row.seller_id));const verify=el('button','Verify with provider');verify.onclick=guard(async()=>{const result=await api('payments/verify',{id:row.id});$('message').textContent=result.paid?'Provider confirmed payment ('+row.mode+' mode). Hosting setup is separate.':'Provider has not confirmed payment';await open(name)});card.append(verify);
   if(row.state!=='paid'&&(me.permissions.includes('users.manage')||(me.role==='reseller'&&row.seller_id===me.id))){card.append(el('p','Reconciliation token: '+row.token));const f=form([['reference','text']],async b=>{await api('payments/reconcile',{id:row.id,reference:b.reference});await open(name)});f.elements.reference.value=row.provider_reference||'';f.lastElementChild.textContent='Verify and reconcile reference';card.append(f)}d.append(card)}return;
 }
 const data=await api('payments/gateways');const add=el('button','Add gateway');add.onclick=guard(()=>gatewayEditor());d.append(add,el('p','Credentials are encrypted on the server and never returned to this screen. Use a new gateway when changing merchant accounts. Preserve the server encryption key with your backups.'));
 for(const row of data){const card=el('article',undefined,'order-card');card.append(el('h3',row.label),el('p',row.provider+' · '+row.mode+' · Store '+row.owner_id+' · '+(row.enabled?'Enabled':'Disabled')),el('p','Webhook URL: '+location.origin+row.webhook_path));const edit=el('button','Manage');edit.onclick=guard(()=>gatewayEditor(row));card.append(edit);d.append(card)}
 d.append(el('h3','Provider catalog'));for(const provider of await api('payments/providers'))d.append(el('p',provider.provider+' — '+provider.status));
}
async function gatewayEditor(gateway={provider:'stripe',mode:'test',label:'',owner_id:me.permissions.includes('users.manage')?0:me.id,enabled:false}){
 const dialog=el('dialog');dialog.className='account-dialog';let close=el('button','×','dialog-close');close.setAttribute('aria-label','Close gateway editor');close.onclick=()=>dialog.close();dialog.append(close,el('h2',gateway.id?'Manage gateway':'Add payment gateway'),el('p','Store 0 is the operator. Super admins may select an enabled reseller user ID. Live mode can collect real money; use test credentials first.'));
 const fields=[['label','text'],['owner_id','number'],['secret','password'],['webhook_secret','password']];const f=form(fields,async b=>{
  try{await api('payments/gateways/save',{...b,owner_id:Number(b.owner_id),provider:f.elements.provider.value,mode:f.elements.mode.value,enabled:f.elements.enabled.checked,confirmed_live:f.elements.confirmed_live.checked,...(gateway.id?{id:gateway.id}:{})});f.elements.secret.value='';f.elements.webhook_secret.value='';dialog.close();await open('Payment Gateways')}catch(e){status.textContent=e.message}
 });f.elements.label.value=gateway.label;f.elements.owner_id.value=gateway.owner_id;f.elements.owner_id.readOnly=!me.permissions.includes('users.manage')||Boolean(gateway.id);f.elements.secret.required=!gateway.id;f.elements.webhook_secret.required=false;
 for(const[key,values]of [['provider',['stripe','paystack']],['mode',['test','live']]]){let l=el('label',key),select=el('select');select.name=key;for(const value of values){let option=el('option',value);option.value=value;option.selected=value===gateway[key];select.append(option)}l.append(select);f.insertBefore(l,f.firstChild)}
 for(const[key,text]of [['enabled','Enable this gateway'],['confirmed_live','I authorize enabling live payments for this merchant account']]){let l=el('label',undefined,'terms-confirm');let input=el('input');input.type='checkbox';input.name=key;input.checked=key==='enabled'&&Boolean(gateway.enabled);l.append(input,el('span',text));f.insertBefore(l,f.lastElementChild)}
 dialog.append(el('p','Stripe requires a whsec_ webhook signing secret. Paystack signs webhooks using its secret key. Leave stored secrets blank to preserve them when editing.'));let status=el('p');status.setAttribute('role','status');dialog.append(f,status);dialog.onclose=()=>dialog.remove();document.body.append(dialog);dialog.showModal();
}
async function paymentCheckout(order){
 const options=await api('payments/options/'+order.id);const dialog=el('dialog');dialog.className='account-dialog';const close=el('button','×','dialog-close');close.setAttribute('aria-label','Close checkout');close.onclick=()=>dialog.close();dialog.append(close,el('h2','Pay for order #'+order.id),el('p',money(order.price_cents,order.currency)+' for one month. This is a one-time payment, without automatic renewal. Hosting activation requires operator follow-up.'));
 const f=el('form'),select=el('select');select.setAttribute('aria-label','Choose gateway');for(const option of options){const opt=el('option',option.label+' · '+option.provider+' · '+option.mode.toUpperCase());opt.value=option.id;select.append(opt)}f.append(select);const l=el('label',undefined,'terms-confirm');const check=el('input');check.type='checkbox';check.required=true;l.append(check,el('span','I confirm the amount and the selected TEST/LIVE mode and authorize this one-time checkout.'));f.append(l);const button=el('button','Continue to hosted checkout');button.disabled=!options.length;f.append(button);const status=el('p');status.setAttribute('role','status');f.onsubmit=async e=>{e.preventDefault();button.disabled=true;try{const result=await api('payments/checkout',{order_id:order.id,gateway_id:Number(select.value),confirmed:check.checked});location.assign(result.url)}catch(error){status.textContent=error.message;button.disabled=false}};
 if(!options.length)dialog.append(el('p','No gateway is enabled for this seller. Contact the operator.'));dialog.append(f,status);dialog.onclose=()=>dialog.remove();document.body.append(dialog);dialog.showModal();
}

async function publisherView(d){
 d.append(el('p','Publish a simple static page with HTTPS after DNS ownership verification. The server website worker must be installed. This does not create DNS zones or run PHP/Node applications.'));
 const refresh=el('button','Refresh publishing status');refresh.onclick=guard(()=>open('Site Publisher'));d.append(refresh);
 const sites=await api('websites');if(!sites.length)d.append(el('p','Add a domain under Domains first.'));
 for(const site of sites){const card=el('article',undefined,'order-card');card.append(el('h3',site.name),el('span',site.state||'Not requested','badge'),el('p',site.message||'Configure the page below to generate your ownership verification token.'));
  if(site.token){card.append(el('p','At your DNS provider, add this TXT record:'),el('pre','Name: _olamidepanel.'+site.name+'\nValue: '+site.token),el('p','Point the domain A record to your panel server IP. Provisioning starts automatically once DNS is public; no resubmission is needed. Keep the TXT record for subsequent page updates.'))}
  if(site.state==='published'){const a=el('a','Open published website ↗');a.href='https://'+site.name;a.target='_blank';a.rel='noopener';card.append(a)}
  if(me.role!=='readonly'){const f=form([['title','text'],['tagline','text']],async b=>{await api('websites',{domain_id:site.id,...b});await open('Site Publisher')});f.elements.title.value=site.title||site.name;f.elements.title.maxLength=100;f.elements.tagline.required=false;f.elements.tagline.maxLength=500;f.elements.tagline.value=site.tagline||'';f.lastElementChild.textContent=site.state==='published'?'Update published page':'Enable automatic provisioning / retry';card.append(f)}d.append(card);
 }
}

async function uploadControls(d){
 d.append(el('h3','Upload a file'),el('p','Up to 8 MiB per file. Account storage limit: 250 MiB; backups have a separate five-snapshot limit.'));
 const f=el('form'),input=el('input');input.type='file';input.required=true;input.setAttribute('aria-label','Choose file to upload');const overwrite=el('input');overwrite.type='checkbox';const label=el('label',undefined,'terms-confirm');label.append(overwrite,el('span','Allow replacing a file with the same name'));const button=el('button','Upload');const status=el('p');status.setAttribute('role','status');f.append(input,label,button,status);
 f.onsubmit=async e=>{e.preventDefault();button.disabled=true;try{const file=input.files[0];if(file.size>8*1024*1024)throw Error('File limit is 8 MiB');const buffer=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<buffer.length;i+=32768)binary+=String.fromCharCode(...buffer.subarray(i,i+32768));await api('storage/files',{action:'upload',path:[cwd,file.name].filter(Boolean).join('/'),content_base64:btoa(binary),overwrite:overwrite.checked});await open('File Manager')}catch(error){status.textContent=error.message;button.disabled=false}};d.append(f);
}
async function storageView(name,d){
 if(name==='Disk Usage'){const usage=await api('storage/usage');for(const[label,value]of [['Used',moneyBytes(usage.used_bytes)],['Quota',moneyBytes(usage.quota_bytes)],['File count',usage.files+' / '+usage.file_limit]]){let row=el('div',undefined,'account-row');row.append(el('strong',label),el('span',value));d.append(row)}return;}
 if(name==='Images'){
  d.append(el('p','Create a resized PNG, JPEG or WebP from an existing account image. Aspect ratio is preserved; the source is not overwritten.'));
  const f=form([['path','text'],['destination','text'],['width','number'],['height','number']],async b=>{await api('storage/files',{...b,action:'image',width:Number(b.width),height:Number(b.height),format:f.elements.format.value});$('message').textContent='Image created'});f.elements.width.value=800;f.elements.height.value=800;for(const key of ['width','height']){f.elements[key].min=1;f.elements[key].max=4000}const select=el('select');select.name='format';select.setAttribute('aria-label','Output image format');for(const value of ['PNG','JPEG','WEBP']){let option=el('option',value);option.value=value;select.append(option)}f.insertBefore(select,f.lastElementChild);if(me.role!=='readonly')d.append(f);return;
 }
 d.append(el('p','Back up your account files into a ZIP snapshot. This does not include MySQL databases, mail, domain settings or system configuration. Restoration adds a new folder; existing files remain intact. Max five snapshots and 64 MiB expanded content per snapshot.'));
 if(me.role!=='readonly'){const create=el('button','Create account-files backup');create.onclick=guard(async()=>{create.disabled=true;try{await api('storage/backups',{action:'create'});await open(name)}finally{create.disabled=false}});d.append(create)}
 const rows=await api('storage/backups');if(!rows.length)d.append(el('p','No snapshots yet.'));
 for(const backup of rows){const row=el('article',undefined,'order-card');row.append(el('h3',new Date(backup.created*1000).toLocaleString()),el('p',backup.id+' · '+moneyBytes(backup.size)));let download=el('a','Download backup ZIP');download.href='/api/storage/download?backup='+encodeURIComponent(backup.id);download.download=backup.id+'.zip';row.append(download);
  if(me.role!=='readonly'){const f=el('form');const label=el('label',undefined,'terms-confirm');const check=el('input');check.type='checkbox';check.required=true;label.append(check,el('span','I confirm restoration into a new folder or permanent deletion of this snapshot.'));const action=el('select');action.setAttribute('aria-label','Backup operation');for(const value of ['restore','delete']){const option=el('option',value);option.value=value;action.append(option)}f.append(label,action,el('button','Apply'));f.onsubmit=guard(async e=>{e.preventDefault();const result=await api('storage/backups',{id:backup.id,action:action.value,confirmed:check.checked});await open(name);$('message').textContent=result.folder?'Restored to '+result.folder:'Snapshot deleted'});row.append(f)}d.append(row);
 }
}
const moneyBytes=value=>(value/1024/1024).toFixed(2)+' MiB';

async function mfaView(d){
 d.replaceChildren(el('h2','Two-Factor Authentication'));
 const state=await api('mfa');d.append(el('p',state.enabled?'Authenticator protection is enabled.':'Add an authenticator app to protect sign-in.'));
 d.append(el('p','Keep recovery codes offline. They appear once and each works once. Enabling or disabling this protection signs out existing sessions.'));
 if(state.enabled){d.append(form([['current_password','password'],['code','text']],async v=>{await api('mfa',{...v,action:'disable'});location.reload()}));return;}
 d.append(form([['current_password','password']],async v=>{
  const enrollment=await api('mfa',{...v,action:'setup'});d.replaceChildren(el('h2','Connect your authenticator'));
  d.append(el('p','Enter this secret in your authenticator app as a time-based, six-digit code. Keep it private.'),el('pre',enrollment.secret));
  d.append(form([['current_password','password'],['code','text']],async answer=>{
   const result=await api('mfa',{...answer,action:'enable'});d.replaceChildren(el('h2','Save your recovery codes'),el('p',result.notice),el('pre',result.recovery_codes.join('\n')));
   const b=el('button','I saved my codes — sign in again');b.onclick=()=>location.reload();d.append(b);
  }));
 }));
}

function marketplaceNavigation(current){
 const nav=el('nav',undefined,'marketplace-tabs');nav.setAttribute('aria-label','Marketplace navigation');
 for(const item of marketplaceMenu){const b=el('button',item.name,item.name===current?'active':'');b.setAttribute('aria-current',item.name===current?'page':'false');b.onclick=guard(()=>open(item.name));nav.append(b)}
 const refresh=el('button','Refresh');refresh.onclick=guard(async()=>{marketplaceMenu=await api('marketplace/navigation');await open(current)});nav.append(refresh);return nav;
}
async function storeSettingsView(d,admin){
 d.append(el('p','Store name, description and contact email are visible to signed-in shoppers. Super admins control reseller publishing access.'));
 const select=el('select');select.setAttribute('aria-label','Choose store');let option=el('option',admin?'Operator store':'Your store');option.value=admin?'0':String(me.id);select.append(option);
 if(admin){for(const vendor of await api('marketplace/vendors')){option=el('option',vendor.username+' · Store #'+vendor.id);option.value=vendor.id;select.append(option)}}
 const area=el('div');d.append(select,area);
 const load=async()=>{const store=await api('marketplace/store?owner_id='+select.value);area.replaceChildren();const f=form([['name','text'],['description','textarea'],['contact_email','email']],async b=>{await api('marketplace/store/save',{...b,owner_id:Number(select.value)});$('message').textContent='Store settings saved'});for(const key of ['name','description','contact_email'])f.elements[key].value=store[key]||'';f.elements.name.maxLength=80;f.elements.description.maxLength=1000;f.elements.description.required=false;f.elements.contact_email.required=false;area.append(f)};select.onchange=guard(load);await load();
}
async function restoreNavigation(){
 const query=new URLSearchParams(location.hash.slice(1));const tool=query.get('tool'),section=query.get('category');
 if(tool&&Object.values(groups).flat().includes(tool)){await open(tool);return;}
 if(section&&(section==='Overview'||groups[section])&&(section!=='Administration'||me.permissions.includes('users.manage')))category=section;
 render();
}
window.addEventListener('popstate',()=>{if(me)guard(restoreNavigation)()});

async function accountToolsView(name){
 category='Administration';render();if(location.hash!=='#tool='+encodeURIComponent(name))history.pushState(null,'','#tool='+encodeURIComponent(name));
 const d=$('detail');d.replaceChildren(el('h2',name),el('p','Manage OlamidePanel accounts. Linux hosting accounts and their resources require separate provisioning.'));d.hidden=false;
 const roles=await api('roles'),users=await api('users');const level=roles.find(r=>r.role===me.role)?.level||0;
 const search=el('input');search.type='search';search.placeholder='Search panel accounts';search.setAttribute('aria-label','Search panel accounts');const list=el('div');d.append(search,list);
 const draw=()=>{list.replaceChildren();for(const user of users.filter(u=>(name!=='Suspended Accounts'||!u.active)&&(name!=='Account Termination'||!u.active)&&(name!=='Resellers'||u.role==='reseller')&&(u.username+' '+u.role).toLowerCase().includes(search.value.toLowerCase()))){const row=el('article',undefined,'account-row');row.append(el('strong',user.username),el('p',user.role+' · '+(user.active?'Active':'Suspended')));const target=roles.find(r=>r.role===user.role)?.level??100;
 if(user.id!==me.id&&target<level){const manage=el('button','Manage account');manage.onclick=guard(()=>accountEditor(user));const suspend=el('button',user.active?'Suspend':'Restore');suspend.onclick=guard(async()=>{await api('users/update',{id:user.id,role:user.role,active:!user.active});await accountToolsView(name)});row.append(manage,suspend)}else row.append(el('span','Protected account','badge'));list.append(row)}if(!list.children.length)list.append(el('p','No matching accounts.'))};search.oninput=draw;draw();const add=el('button','Create panel user');add.onclick=guard(()=>open('Create Panel User'));d.append(add);d.scrollIntoView({behavior:'smooth'});d.focus();
}
async function dnsView(d){
 d.append(el('p','Look up public DNS records. This tool reads DNS; it does not create or edit zones.'));
 const result=el('pre');result.setAttribute('aria-live','polite');const f=form([['name','text']],async b=>{result.textContent='Looking up DNS…';try{result.textContent=JSON.stringify(await api('dns/lookup',{...b,type:f.elements.record_type.value}),null,2)}catch(e){result.textContent=e.message}});const select=el('select');select.name='record_type';select.setAttribute('aria-label','DNS record type');for(const type of ['A','AAAA','CNAME','MX','NS','TXT','SOA','CAA']){const option=el('option',type);option.value=type;select.append(option)}f.insertBefore(select,f.lastElementChild);f.lastElementChild.textContent='Look up records';d.append(f,result);
}
async function moduleStatusView(name){
 const d=$('detail');d.replaceChildren(el('h2',name));d.hidden=false;
 d.append(el('p','This tool is not available yet. It requires additional backend implementation; installing packages alone will not enable it.'));
 if(me.permissions.includes('users.manage')){const report=await api('modules');const tool=report.tools.find(t=>t.name===name);if(tool)d.append(el('p',tool.detail));const readiness=el('button','View module readiness');readiness.onclick=guard(()=>open('Module Readiness'));d.append(readiness)}
 const available=el('button','Browse working tools');available.onclick=()=>{toolFilter='available';category='Overview';render()};d.append(available);d.scrollIntoView({behavior:'smooth'});
}

async function siteControlsView(name,d){
 d.append(el('p','Controls apply to your DNS-verified static sites after the provisioning worker succeeds. Panel login and other domains are unaffected.'));
 const sites=await api('site-controls');if(!sites.length){d.append(el('p','Add a domain under Domains, then request Site Publisher first.'));const go=el('button','Open Site Publisher');go.onclick=guard(()=>open('Site Publisher'));d.append(go);return;}
 const select=el('select');select.setAttribute('aria-label','Static website domain');for(const site of sites){const option=el('option',site.name);option.value=site.id;select.append(option)}
 const area=el('div');d.append(select,area);
 const draw=()=>{const site=sites.find(s=>String(s.id)===select.value);area.replaceChildren(el('p',`State: ${site.state||'Not published'} · saved revision ${site.revision} · applied revision ${site.applied_revision}. ${site.message||''}`));const settings=structuredClone(site.settings),status=el('p');status.setAttribute('role','status');
  if(me.role==='readonly'){area.append(el('p','Read-only access: configuration changes are disabled.'));return;}
  const save=async()=>{const result=await api('site-controls',{domain_id:Number(site.id),revision:site.revision,settings});status.textContent=result.message;const latest=await api('site-controls');sites.splice(0,sites.length,...latest);draw();$('message').textContent=result.message;};
  if(name==='Indexes'){
   const f=form([],save),label=el('label','Allow directory listings when no index file exists'),check=el('input');check.type='checkbox';check.checked=settings.indexes;check.onchange=()=>settings.indexes=check.checked;label.append(check);f.prepend(label);area.append(f);
  }
  if(name==='Redirects'){
   area.append(el('p','Exact-path HTTPS redirects only. Reserved paths, configuration syntax and redirect loops are rejected.'));
   const list=el('div');for(const [i,r] of settings.redirects.entries()){const row=el('div',`${r.path} → ${r.target} (${r.status})`),remove=el('button','Remove redirect');remove.onclick=guard(async()=>{settings.redirects.splice(i,1);await save()});row.append(remove);list.append(row)}area.append(list);
   const f=form([['path','text'],['target','url']],async b=>{settings.redirects.push({...b,status:Number(statusSelect.value)});await save()});const statusSelect=el('select');statusSelect.setAttribute('aria-label','HTTP redirect status');for(const code of [302,301,307,308]){const o=el('option',String(code));o.value=code;statusSelect.append(o)}f.insertBefore(statusSelect,f.lastElementChild);area.append(f);
  }
  if(name==='Error Pages'){
   const list=el('div');for(const [code,message] of Object.entries(settings.errors)){const row=el('div',`HTTP ${code}: ${message}`),remove=el('button','Use default page');remove.onclick=guard(async()=>{delete settings.errors[code];await save()});row.append(remove);list.append(row)}area.append(list);
   const f=form([['message','textarea']],async b=>{settings.errors[codeSelect.value]=b.message;await save()});f.elements.message.maxLength=1000;const codeSelect=el('select');codeSelect.setAttribute('aria-label','HTTP error code');for(const code of [400,401,403,404,500,502,503]){const o=el('option',String(code));o.value=code;codeSelect.append(o)}f.insertBefore(codeSelect,f.lastElementChild);area.append(f);
  }
  if(name==='Hotlink Protection'){
   area.append(el('p','Protect image requests from other sites. Direct requests and your own hostname remain allowed.'));
   const f=form([['allowed_domains','textarea']],async b=>{settings.referers=b.allowed_domains.split(/\s+/).filter(Boolean);settings.hotlink=enabled.checked;await save()});f.elements.allowed_domains.required=false;f.elements.allowed_domains.value=settings.referers.join('\n');const label=el('label','Enable image hotlink protection'),enabled=el('input');enabled.type='checkbox';enabled.checked=settings.hotlink;label.append(enabled);f.prepend(label);area.append(f);
  }
  if(name==='IP Blocker'){
   area.append(el('p','Deny addresses or CIDR networks for this static site. One per line, up to 20 entries.'));
   const f=form([['networks','textarea']],async b=>{settings.blocked_ips=b.networks.split(/\s+/).filter(Boolean);await save()});f.elements.networks.required=false;f.elements.networks.value=settings.blocked_ips.join('\n');area.append(f);
  }
  area.append(status);
 };
 select.onchange=draw;draw();const refresh=el('button','Reload saved and applied status');refresh.onclick=guard(async()=>{const latest=await api('site-controls');sites.splice(0,sites.length,...latest);draw()});d.append(refresh);
}
