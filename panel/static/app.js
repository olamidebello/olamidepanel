const $=id=>document.getElementById(id);let marketplaceMenu=[],selectedStore=null;let me,category='Overview',cwd='';
const groups={Marketplace:['Marketplace Dashboard','Hosting Plans','Browse Stores','My Orders','Reseller Catalog','Store Orders','Store Settings','Payment Gateways','Payments'],Files:['File Manager','Images','Directory Privacy','Disk Usage','FTP Accounts','FTP Connections','Anonymous FTP','Web Disk','Git Version Control','Git Deployment','Backups','Backup Wizard','File Restoration'],Domains:['Domains','Redirects','DNS Zone Editor','Dynamic DNS','Site Publisher','Site Builder','SEO','Social Media'],Email:['Email Accounts','Forwarders','Domain Forwarders','Autoresponders','Default Address','Email Routing','Email Filters','Global Filters','Email Deliverability','Email Disk Usage','Address Importer','Archive','Mailing Lists','BoxTrapper','Greylisting','Encryption','Calendars and Contacts','Calendar Sharing','Calendar Delegation','Spam Filters','Track Delivery','Webmail'],Databases:['Database Manager','Database Users','Database Wizard','phpMyAdmin','Remote Database Access','PostgreSQL','PostgreSQL Wizard','phpPgAdmin'],Security:['SSH Access','IP Blocker','SSL/TLS','Private Keys','Certificate Signing Requests','Certificates','SSL Sites','SSL Status','AutoSSL','ModSecurity','Hotlink Protection','Leech Protection','Two-Factor Authentication','API Tokens','Security Policy'],Software:['PHP Manager','PHP-FPM','PHP INI Editor','Application Manager','Environment Variables','Application Dependencies','Optimize Website','Perl Modules','PEAR Packages','RubyGems','Ruby on Rails','Application Installer'],Metrics:['Server Metrics','Visitors','Errors','Bandwidth','Raw Access','AWStats','Analog Stats','Webalizer','FTP Statistics','Metrics Editor','Resource Usage','Site Monitoring'],Advanced:['Terminal','Cron Jobs','Track DNS','Indexes','Error Pages','Apache Handlers','MIME Types','API Shell','Virus Scanner'],Preferences:['Password and Security','Language','Contact Information','Account Preferences','User Manager','Manage Team'],Administration:['Module Manager','Watchdog Events & Reports','Hosting Domains','Module Readiness','Reseller Access','Hosting Catalog','Access Control','Create Panel User','Audit Log','List Accounts','Suspended Accounts','Account Provisioning','Account Suspension','Account Termination','Shell Access','IP Assignment','Bandwidth Limits','Packages','Feature Manager','Resellers','Server Configuration','Hostname and Resolvers','IP Management','DNS Zones','DNS Templates','DNS Cluster','Configuration Cluster','Backup Configuration','Backup Restoration','Account Transfers','Apache Configuration','PHP Configuration','Mail Configuration','FTP Configuration','Service Manager','Log Rotation','Package Management','Database Services','Mail Queue','Delivery Reports','Brute Force Protection','Host Access Control','Compiler Access','Service Certificates','Process Manager','Task Queue','Service Restarts','System Reboot','Contact Manager','Hooks','Plugins','Branding','Themes and Locales','Support'],Integrations:['WP Toolkit','Softaculous','CloudLinux','LiteSpeed','JetBackup','Comet Backup','Imunify','External DNS/CDN','Billing','External Monitoring','AI Services']};
const implemented=['Module Manager','Watchdog Events & Reports','Hosting Domains','Redirects','Indexes','Error Pages','Hotlink Protection','IP Blocker','Track DNS','User Manager','List Accounts','Suspended Accounts','Account Suspension','Account Termination','Resellers','Browse Stores','Store Orders','Store Settings','Two-Factor Authentication','Images','Disk Usage','Backups','Backup Wizard','File Restoration','Site Publisher','Payment Gateways','Payments','Module Readiness','Reseller Access','Reseller Catalog','Marketplace Dashboard','Hosting Plans','My Orders','Hosting Catalog','Contact Information','Password and Security','Access Control','File Manager','Domains','Server Metrics','Create Panel User','Audit Log'];
function el(tag,text,cls){const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x}
async function api(path,body){const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-CSRF-Token':me?.csrf||''}:{},body:body?JSON.stringify(body):undefined});if(!r.ok){let d=await r.json();throw Error(d.error)}return r.headers.get('Content-Type')?.includes('json')?r.json():null}
function guard(fn){return async(...args)=>{try{$('message').textContent='';await fn(...args)}catch(e){$('message').textContent=e.message}}}
function form(fields,submit){let f=el('form');for(const [name,type]of fields){let l=el('label',name);let i=el(type==='textarea'?'textarea':'input');i.name=name;if(type!=='textarea')i.type=type;i.required=true;l.append(i);f.append(l)}f.append(el('button','Save'));f.onsubmit=guard(async e=>{e.preventDefault();await submit(Object.fromEntries(new FormData(f)));});return f}
let toolFilter='available';
let favorites;
try { favorites=JSON.parse(localStorage.getItem('olamide-favorites')||'[]'); if(!Array.isArray(favorites))favorites=[]; } catch { favorites=[]; }
const navIcons={Marketplace:'▧',Overview:'◈',Files:'▤',Domains:'◎',Email:'✉',Databases:'▥',Security:'♧',Software:'⌘',Metrics:'▥',Advanced:'⌁',Preferences:'⚙',Administration:'▦',Integrations:'◇'};
// Each navigation owns a separate node, so late API responses cannot alter another screen.
function resetDetail(){const previous=$('detail'),next=previous.cloneNode(false);previous.replaceWith(next);return next}
function render(){
 let nav=$('nav');nav.replaceChildren();
 for(const name of ['Overview',...Object.keys(groups)].filter(n=>me?.permissions?.includes('users.manage')||n!=='Administration')){
  let b=el('button',undefined,name===category?'active':'');b.append(el('span',navIcons[name]||'◇','nav-icon'),el('span',name));
  b.setAttribute('aria-current',name===category?'page':'false');b.onclick=()=>{category=name;history.pushState(null,'','#category='+encodeURIComponent(name));render()};nav.append(b);
  if(name==='Marketplace'&&category==='Marketplace'){for(const item of marketplaceMenu){const link=el('button',item.name,'marketplace-subnav');link.onclick=guard(()=>open(item.name));nav.append(link)}}
 }
 $('heading').textContent=category==='Overview'?'Hosting overview':category;$('crumb').textContent=category;
 $('sectionTitle').textContent=category==='Overview'?'Your hosting tools':category+' tools';
 resetDetail().hidden=true;$('tools').replaceChildren();let count=0;
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
  b.onclick=guard(()=>open(name));
  let star=el('button',favorites.includes(name)?'★':'☆','favorite');star.setAttribute('aria-label',(favorites.includes(name)?'Unpin ':'Pin ')+name);star.setAttribute('aria-pressed',String(favorites.includes(name)));
  star.onclick=()=>{favorites=favorites.includes(name)?favorites.filter(n=>n!==name):[...favorites,name];try{localStorage.setItem('olamide-favorites',JSON.stringify(favorites))}catch{}render()};
  card.append(b,star);$('tools').append(card);
 }
 $('resultCount').textContent=count+' tools';
 if(!count)$('tools').append(el('div',toolFilter==='favorites'?'Star a tool to make it a favorite.':'No tools match. Try another search or category.','empty-state'));
 document.querySelectorAll('[data-filter]').forEach(b=>{b.classList.toggle('active',b.dataset.filter===toolFilter);b.setAttribute('aria-pressed',String(b.dataset.filter===toolFilter))});
}
async function openBase(name,d=$('detail')){d.replaceChildren(el('h2',name));d.hidden=false;d.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});d.focus({preventScroll:true});if(!implemented.includes(name)){await moduleStatusView(name);return}
if(name==='Access Control'){
 d.append(el('p','Manage panel roles and suspend or restore lower-level accounts. Panel root controls OlamidePanel permissions; Linux root privileges are not granted.'));
 const [roles,users]=await Promise.all([api('roles'),api('users')]);
 const summary=el('div',undefined,'access-summary');
 for(const [label,value]of [['Accounts',users.length],['Active',users.filter(x=>x.active).length],['Suspended',users.filter(x=>!x.active).length]]){let card=el('div',undefined,'metric');card.append(el('small',label),el('strong',String(value)));summary.append(card)}d.append(summary);
 const list=el('div',undefined,'account-list');d.append(list);
 const search=el('input');search.type='search';search.placeholder='Filter accounts by username or role';search.setAttribute('aria-label','Filter accounts');d.insertBefore(search,list);
 const renderUsers=()=>{list.replaceChildren();for(const user of users.filter(u=>(u.username+' '+u.role).toLowerCase().includes(search.value.toLowerCase()))){
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
async function start(){me=await api('me');marketplaceMenu=await api('marketplace/navigation');$('login').hidden=true;$('workspace').hidden=false;$('logout').hidden=false;render();let m=await api('metrics');$('metrics').replaceChildren();for(const[label,value]of [['SERVER',m.hostname],['DISK USED',(m.disk_used/2**30).toFixed(1)+' GB'],['SYSTEM LOAD',m.load[0].toFixed(2)]]){let box=el('div',undefined,'metric');box.append(el('small',label),el('strong',value),el('small','LIVE SERVER DATA'));$('metrics').append(box)}if(me.permissions.includes('users.manage')){const card=el('div',undefined,'metric'),b=el('button','View all hosting domains');b.onclick=guard(()=>open('Hosting Domains'));card.append(el('small','SERVER DOMAINS'),b);$('metrics').append(card)}await restoreNavigation()}
$('loginForm').onsubmit=guard(async e=>{e.preventDefault();await api('login',{...Object.fromEntries(new FormData(e.target)),accept_terms:e.target.elements.accept_terms.checked});e.target.reset();await start()});$('logout').onclick=guard(async()=>{await api('logout',{});location.reload()});$('search').oninput=render;start().catch(()=>{});

function setTheme(theme){document.documentElement.dataset.theme=theme;$('theme').setAttribute('aria-label',theme==='dark'?'Use light theme':'Use dark theme');$('theme').setAttribute('aria-pressed',String(theme==='dark'));try{localStorage.setItem('olamide-theme',theme)}catch{}}
let savedTheme;try{savedTheme=localStorage.getItem('olamide-theme')}catch{}
setTheme(savedTheme||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'));
$('theme').onclick=()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark');
$('help').onclick=()=>$('guide').showModal();$('closeGuide').onclick=()=>$('guide').close();
$('quickFiles').onclick=guard(()=>open('File Manager'));$('quickDomain').onclick=guard(()=>open('Domains'));$('guideMetrics').onclick=guard(()=>open('Server Metrics'));
$('showAvailable').onclick=()=>{category='Overview';toolFilter='available';$('search').value='';render();$('sectionTitle').scrollIntoView({block:'start'})};
document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{toolFilter=b.dataset.filter;render()});
document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&!$('workspace').hidden&&!$('guide').open){e.preventDefault();$('search').focus()}});

async function accountEditor(user){
 const dialog=el('dialog');dialog.className='account-dialog';let close=el('button','×','dialog-close');close.setAttribute('aria-label','Close account editor');close.onclick=()=>dialog.close();dialog.append(close,el('h2','Manage '+user.username),el('p','Changes apply to this panel account. Account files are retained after deletion.'));
 const status=el('p');status.setAttribute('role','status');const run=async body=>{try{await api('users/action',{id:user.id,...body});status.textContent='Account updated';}catch(e){status.textContent=e.message}};
 dialog.append(el('h3','Account details'));
 const profile=form([['display_name','text'],['email','email']],async b=>run({...b,action:'profile'}));profile.elements.display_name.required=false;profile.elements.email.required=false;profile.elements.display_name.value=user.display_name||'';profile.elements.email.value=user.email||'';dialog.append(profile);
 dialog.append(el('h3','Set a new password'));const pw=form([['password','password']],async b=>{await run({...b,action:'password'});pw.reset()});pw.elements.password.minLength=14;dialog.append(pw);
 const revoke=el('button','Revoke all sessions');revoke.onclick=()=>run({action:'revoke_sessions'});dialog.append(revoke);
 if(!user.active){dialog.append(el('h3','Delete suspended account'),el('p','Type the exact username. Domain inventory is removed; files are retained for operator recovery.'));dialog.append(form([['confirmation','text']],async b=>{await run({...b,action:'delete'})}))}
 dialog.append(status);dialog.addEventListener('close',()=>{dialog.remove();guard(()=>open('Access Control'))()});document.body.append(dialog);dialog.showModal();
}
async function open(name){
 const accountTools=['User Manager','List Accounts','Suspended Accounts','Account Suspension','Account Termination','Resellers'];
 if(accountTools.includes(name)){if(!me.permissions.includes('users.manage'))throw Error('Super-admin access required');await accountToolsView(name);return;}
 if(!implemented.includes(name)){await moduleStatusView(name);return;}
 if(groups.Marketplace.includes(name)&&!marketplaceMenu.some(item=>item.name===name))throw Error('This marketplace menu is unavailable for your account');
 if(location.hash!=='#tool='+encodeURIComponent(name))history.pushState(null,'','#tool='+encodeURIComponent(name));
 if(groups.Marketplace.includes(name)){category='Marketplace';render()}
 const d=resetDetail();await openBase(name,d);if(!d.isConnected)return;
 if(['Redirects','Indexes','Error Pages','Hotlink Protection','IP Blocker'].includes(name)){await siteControlsView(name,d);return;}
 if(name==='Track DNS'){await dnsView(d);return;}
 if(name==='Two-Factor Authentication'){await mfaView(d);return;}
 if(['Images','Disk Usage','Backups','Backup Wizard','File Restoration'].includes(name)){await storageView(name,d);return;}
 if(name==='Module Manager'){await moduleManagerView(d);return;}
 if(name==='Watchdog Events & Reports'){await watchdogView(d);return;}
 if(name==='Hosting Domains'){await hostingDomainsView(d);return;}
 if(name==='Site Publisher'){await publisherView(d);return;}
 if(name==='Payment Gateways'||name==='Payments'){await paymentView(name,d);return;}
 if(name==='Module Readiness'){const data=await api('modules');d.append(el('p',data.notice));for(const module of data.modules){const row=el('div',undefined,'account-row');row.append(el('strong',module.name),el('span',module.status,'badge'),el('p',module.detail));d.append(row)}d.append(el('h3','Individual tools'));for(const tool of data.tools){const row=el('details');row.append(el('summary',tool.category+' / '+tool.name+' · '+tool.status),el('p',tool.detail));d.append(row)}return;}
 if(['Marketplace Dashboard','Hosting Plans','Browse Stores','Store Settings','Store Orders','My Orders','Hosting Catalog','Reseller Catalog','Reseller Access'].includes(name)){await marketplaceView(name,d);return;}
 if(name==='Contact Information'||name==='Password and Security'){
  d.replaceChildren(el('h2',name));const profile=await api('profile');
  if(name==='Contact Information'){const f=form([['display_name','text'],['email','email']],async b=>{await api('profile',b);$('message').textContent='Contact information saved'});for(const field of ['display_name','email']){f.elements[field].required=false;f.elements[field].value=profile[field]||''}d.append(f)}
  else{d.append(el('p','Use a password with at least 14 characters. Changing it signs out all sessions.'));const f=form([['current_password','password'],['password','password']],async b=>{await api('profile',{...b,email:profile.email,display_name:profile.display_name});location.reload()});f.elements.password.minLength=14;d.append(f)}
 }
 if(name==='Domains'&&me.permissions.includes('domains.write')){
  d.append(el('h3','Remove domain inventory'));const list=await api('domains');for(const domain of list){let row=el('div',undefined,'account-row');row.append(el('strong',domain.name));const remove=el('button','Remove record');remove.onclick=guard(async()=>{await api('domains/delete',{id:domain.id});await open(name)});row.append(remove);d.append(row)}
 }
 if(name==='File Manager'&&me.permissions.includes('files.write')){
  const files=await api('files?path='+encodeURIComponent(cwd));await uploadControls(d);d.append(el('h3','File actions'),el('p','Rename, copy or remove files. Folder deletion requires an empty folder.'));
  for(const file of files){let path=[cwd,file.name].filter(Boolean).join('/');let row=el('details');row.append(el('summary',file.name));let download=el('a','Download');download.href='/api/storage/download?path='+encodeURIComponent(path);download.download=file.name;if(!file.directory)row.append(download);if(!file.directory){
   const f=form([['destination','text']],async b=>{await api('files',{action:f.elements.operation.value,path,destination:b.destination});await open(name)});const select=el('select');select.name='operation';select.setAttribute('aria-label','File operation');for(const action of ['rename','copy']){let option=el('option',action);option.value=action;select.append(option)}f.insertBefore(select,f.firstChild);f.elements.destination.value=path;row.append(f);
  }
  const archiveForm=form([['destination','text']],async b=>{await api('storage/files',{action:archiveForm.elements.archive_action.value,path,destination:b.destination});await open(name)});const archiveAction=el('select');archiveAction.name='archive_action';archiveAction.setAttribute('aria-label','Archive operation');for(const action of ['compress','extract']){let option=el('option',action);option.value=action;archiveAction.append(option)}archiveForm.insertBefore(archiveAction,archiveForm.firstChild);archiveForm.elements.destination.value=path+'.zip';row.append(archiveForm);
  const deleteForm=form([['confirmation','text']],async b=>{if(b.confirmation!==file.name)throw Error('Type the exact file name to confirm');await api('files',{action:'delete',path});await open(name)});deleteForm.firstElementChild.firstChild.textContent='Type '+file.name+' to delete';deleteForm.lastElementChild.textContent='Delete';row.append(deleteForm);d.append(row);
  }
 }
}

const money=(cents,currency='USD')=>new Intl.NumberFormat(undefined,{style:'currency',currency}).format(cents/100);
const hostingTemplates=[
 {name:'Starter',description:'Suggested for a small personal site or portfolio.',price_cents:500,disk_gb:10,bandwidth_gb:100,websites:1,enabled:false,featured:false},
 {name:'Business',description:'Suggested for a small business with several websites.',price_cents:1500,disk_gb:30,bandwidth_gb:500,websites:5,enabled:false,featured:true},
 {name:'Growth',description:'Suggested for a larger group of business websites.',price_cents:3000,disk_gb:75,bandwidth_gb:1500,websites:15,enabled:false,featured:false}
];
async function marketplaceView(name,d){
 const admin=me.permissions.includes('users.manage');
 const capabilities=await api('marketplace/capabilities');
 d.append(marketplaceNavigation(name));
 if(name==='Store Settings'){await storeSettingsView(d,admin);return;}
 if(name==='Browse Stores'){for(const store of await api('marketplace/stores')){const card=el('article',undefined,'order-card');card.append(el('h3',store.name),el('p',store.description||'Hosting storefront'));if(store.contact_email){const email=el('a',store.contact_email);email.href='mailto:'+store.contact_email;card.append(email)}const browse=el('button','View store plans');browse.onclick=guard(async()=>{selectedStore=store.owner_id;await open('Hosting Plans')});card.append(browse);d.append(card)}return;}
 d.append(el('p','Paid plans activate panel account resources automatically after verified live payment. Stripe and Paystack require merchant setup. Services last 30 days; no automatic renewal.'));
 if(name==='Reseller Access'){
  if(!admin)throw Error('Super-admin access required');
  d.append(el('p','Create or assign reseller users in Access Control, then enable publishing here. Disabling a storefront hides its published plans and prevents reseller edits/review; super admins retain control.'));
  let usersButton=el('button','Manage users and roles');usersButton.onclick=guard(()=>open('Access Control'));d.append(usersButton);
  const vendors=await api('marketplace/vendors');if(!vendors.length)d.append(el('p','No reseller accounts yet. Assign the reseller role in Access Control.'));
  for(const vendor of vendors){let row=el('div',undefined,'account-row');row.append(el('strong',vendor.username),el('span',vendor.enabled?'Publishing enabled':'Publishing disabled','badge'),el('p',vendor.active?'Account active':'Account suspended'));
   let b=el('button',vendor.enabled?'Disable storefront':'Enable storefront');b.onclick=guard(async()=>{await api('marketplace/vendors/save',{id:vendor.id,enabled:!vendor.enabled});await open(name)});row.append(b);d.append(row)}return;
 }
 if(name==='Marketplace Dashboard'){
  const data=await api('marketplace/summary');d.append(el('small',data.scope==='all_accounts'?'ALL ACCOUNTS':data.scope==='reseller_store'?'YOUR PURCHASES AND STOREFRONT ORDERS':'YOUR ACCOUNT'));
  const grid=el('div',undefined,'access-summary');for(const[label,value]of [['Available plans',data.enabled_plans],['Pending requests',data.counts.pending||0],['Approved requests',data.counts.approved||0],['Rejected',data.counts.rejected||0],['Cancelled',data.counts.cancelled||0]]){let card=el('div',undefined,'metric');card.append(el('small',label),el('strong',String(value)));grid.append(card)}d.append(grid);
  for(const target of ['Hosting Plans','My Orders',...(admin?['Hosting Catalog','Reseller Access','Access Control']:me.role==='reseller'?['Reseller Catalog']:[])]){let b=el('button',target);b.onclick=guard(()=>open(target));d.append(b)}return;
 }
 if(name==='Hosting Plans'||name==='Hosting Catalog'||name==='Reseller Catalog'){
  if(name==='Hosting Catalog'&&!admin)throw Error('Super-admin access required');
  const all=await api('marketplace/plans');const plans=name==='Hosting Plans'?all.filter(p=>p.enabled&&(selectedStore===null||p.seller_id===selectedStore)):name==='Reseller Catalog'?all.filter(p=>p.seller_id===me.id):all;
  if(name==='Hosting Plans'&&selectedStore!==null){const clear=el('button','Show all stores');clear.onclick=guard(async()=>{selectedStore=null;await open(name)});d.append(el('p','Viewing store #'+selectedStore),clear)}
  if((admin&&name==='Hosting Catalog')||(me.role==='reseller'&&name==='Reseller Catalog'&&capabilities.manage_own)){
   const add=el('button','Create plan');add.onclick=guard(()=>hostingPlanEditor());d.append(add,el('h3','Suggested starting templates'),el('p','Illustrative monthly USD prices. Storage and website limits apply in the panel; bandwidth is not metered. Review server capacity and costs before publishing.'));
   for(const template of [...hostingTemplates,...resellerTemplates]){let b=el('button','Customize '+template.name+' · '+money(template.price_cents)+'/month');b.onclick=guard(()=>hostingPlanEditor(template));d.append(b)}
  }
  if(name==='Reseller Catalog'&&!capabilities.manage_own)d.append(el('p','Publishing is disabled. Ask super admin to enable your storefront.'));
  const filter=el('input');filter.type='search';filter.placeholder='Search plans';filter.setAttribute('aria-label','Search hosting plans');d.append(filter);let grid=el('div',undefined,'plan-grid');d.append(grid);
  const render=()=>{grid.replaceChildren();for(const plan of plans.filter(p=>(p.name+' '+p.description).toLowerCase().includes(filter.value.toLowerCase()))){
   let card=el('article',undefined,'hosting-plan');if(plan.featured)card.append(el('span','Operator featured','badge'));card.append(el('small',(plan.plan_kind==='reseller'?'RESELLER PLAN':'HOSTING PLAN')+' · Seller: '+(plan.seller_id?(plan.seller_name||plan.seller_username||'Reseller #'+plan.seller_id):'OlamidePanel operator')),el('h3',plan.name),el('strong',money(plan.price_cents,plan.currency)+'/month','plan-price'),el('p',plan.description));
   let ul=el('ul');for(const text of [plan.disk_gb+' GB storage target',plan.bandwidth_gb+' GB monthly transfer target',plan.websites+' website(s)'])ul.append(el('li',text));card.append(ul,el('p','Panel storage and website allocations activate after verified live payment. Transfer is a recorded allocation; bandwidth metering is not available. DNS/HTTPS requires ownership verification.'));
   if(name==='Hosting Catalog'||(name==='Reseller Catalog'&&capabilities.manage_own)){card.append(el('span',plan.enabled?'Published':'Disabled','badge'));let edit=el('button','Edit plan');edit.onclick=guard(()=>hostingPlanEditor(plan));card.append(edit)}
   else if(name==='Hosting Plans'&&me.role!=='readonly'&&plan.seller_id!==me.id){let order=el('button','Request this plan');order.onclick=guard(()=>hostingOrderDialog(plan));card.append(order)}
   grid.append(card);
  }if(!grid.children.length)grid.append(el('p',name==='Hosting Catalog'?'No plans yet. Create a plan or customize a template.':'No plans are currently published.'))};filter.oninput=render;render();return;
 }
 if(name==='My Orders'||name==='Store Orders'){
  d.append(el('small',name==='Store Orders'?(admin?'LATEST 200 ORDERS ACROSS ALL STORES':'YOUR LATEST 200 STORE ORDERS'):'YOUR LATEST 200 PURCHASES'));
  const orders=await api('marketplace/orders?scope='+(name==='Store Orders'?'store':'purchases'));const filter=el('select');filter.setAttribute('aria-label','Filter order status');for(const value of ['all','pending','approved','rejected','cancelled']){let o=el('option',value);o.value=value;filter.append(o)}d.append(filter);let list=el('div');d.append(list);
  const render=()=>{list.replaceChildren();for(const order of orders.filter(o=>filter.value==='all'||o.status===filter.value)){
   const plan=JSON.parse(order.plan_snapshot);const canReview=admin||(capabilities.manage_own&&order.seller_id===me.id);const card=el('article',undefined,'order-card');card.append(el('h3','#'+order.id+' · '+plan.name),el('span',order.status,'badge'),el('p',money(order.price_cents,order.currency)+'/month · '+order.username+' · '+new Date(order.created*1000).toLocaleString()),el('p','Customer note: '+(order.note||'—')),el('p','Operator note: '+(order.operator_note||'—')));
   if(order.status==='approved'){
    card.append(el('p',order.provisioning?'Payment verified. Account activation status is shown below.':'Ready for payment. Verified live payment queues automatic account activation.'));
    if(!order.provisioning&&order.owner===me.id&&me.role!=='readonly'){let pay=el('button','Payment options');pay.onclick=guard(()=>paymentCheckout(order));card.append(pay)}
   }
   if(order.provisioning){card.append(el('span','Provisioning: '+order.provisioning.state,'badge'),el('p',order.provisioning.message));if(order.provisioning.state==='needs_attention'&&canReview){const retry=el('button','Retry account activation');retry.onclick=guard(async()=>{await api('marketplace/orders/retry',{id:order.id});await open(name)});card.append(retry)}}
   if(order.service){card.append(el('p','Service: '+order.service.state+' · '+order.service.disk_bytes/1024**3+' GiB panel storage · '+order.service.websites+' websites · Ends '+new Date(order.service.expires_at*1000).toLocaleString()));const manage=el('button','Manage account resources');manage.onclick=guard(()=>open('File Manager'));card.append(manage)}
   if(order.status==='pending'&&me.role!=='readonly'){
    if(canReview){const note=el('textarea');note.maxLength=1000;note.placeholder='Operator note (visible to customer)';note.setAttribute('aria-label','Operator note for order '+order.id);card.append(note);
     for(const action of ['approve','reject']){const b=el('button',action==='approve'?'Approve for follow-up':'Reject');b.onclick=guard(async()=>{await api('marketplace/orders/action',{id:order.id,action,operator_note:note.value});await open(name)});card.append(b)}}
    const cancel=el('button','Cancel request');cancel.hidden=!admin&&order.owner!==me.id;cancel.onclick=guard(async()=>{await api('marketplace/orders/action',{id:order.id,action:'cancel'});await open(name)});card.append(cancel);
   }list.append(card);
  }if(!list.children.length)list.append(el('p','No orders match this status.'))};filter.onchange=render;render();
 }
}
const resellerTemplates=[
 {name:'Reseller Launch',plan_kind:'reseller',description:'Illustrative entry reseller allocation for a small client portfolio; automatic panel activation after verified live payment.',price_cents:2500,disk_gb:50,bandwidth_gb:500,websites:20,enabled:false,featured:false},
 {name:'Reseller Business',plan_kind:'reseller',description:'Illustrative allocation for a growing reseller portfolio; review server capacity first.',price_cents:5000,disk_gb:100,bandwidth_gb:1500,websites:50,enabled:false,featured:true},
 {name:'Reseller Scale',plan_kind:'reseller',description:'Illustrative larger portfolio allocation; automatic panel storage and website allocation.',price_cents:10000,disk_gb:250,bandwidth_gb:4000,websites:100,enabled:false,featured:false}
];
async function hostingPlanEditor(plan={name:'',description:'',price_cents:0,disk_gb:10,bandwidth_gb:100,websites:1,enabled:false,featured:false}){
 const dialog=el('dialog');dialog.className='account-dialog';let close=el('button','×','dialog-close');close.setAttribute('aria-label','Close plan editor');close.onclick=()=>dialog.close();dialog.append(close,el('h2',plan.id?'Edit hosting plan':'Create hosting plan'),el('p','Monthly USD price. Enter price in cents: 1500 = $15.00. Plans stay disabled until you publish them.'));
 const f=form([['name','text'],['description','textarea'],['price_cents','number'],['disk_gb','number'],['bandwidth_gb','number'],['websites','number']],async b=>{
  const payload={...b,plan_kind:f.elements.plan_kind.value,enabled:f.elements.enabled.checked,featured:f.elements.featured.checked};for(const key of ['price_cents','disk_gb','bandwidth_gb','websites'])payload[key]=Number(payload[key]);if(plan.id)payload.id=plan.id;
  try{await api('marketplace/plans/save',payload);dialog.close();await open(me.role==='reseller'?'Reseller Catalog':'Hosting Catalog')}catch(e){status.textContent=e.message}
 });for(const field of ['name','description','price_cents','disk_gb','bandwidth_gb','websites'])f.elements[field].value=plan[field];f.elements.description.required=false;
 for(const key of ['price_cents','disk_gb','bandwidth_gb','websites']){f.elements[key].min=key==='price_cents'?0:1;f.elements[key].step=1}
 const kindLabel=el('label','Plan category');const kind=el('select');kind.name='plan_kind';for(const value of ['hosting','reseller']){let option=el('option',value);option.value=value;option.selected=(plan.plan_kind||'hosting')===value;kind.append(option)}kindLabel.append(kind);f.insertBefore(kindLabel,f.lastElementChild);
 for(const[key,label]of [['enabled','Publish / allow requests'],['featured','Feature this plan']]){const l=el('label',undefined,'terms-confirm');let input=el('input');input.type='checkbox';input.name=key;input.checked=Boolean(plan[key]);l.append(input,el('span',label));f.insertBefore(l,f.lastElementChild)}
 let status=el('p');status.setAttribute('role','status');dialog.append(f,status);dialog.onclose=()=>dialog.remove();document.body.append(dialog);dialog.showModal();
}
async function hostingOrderDialog(plan){
 const dialog=el('dialog');dialog.className='account-dialog';let close=el('button','×','dialog-close');close.setAttribute('aria-label','Close order request');close.onclick=()=>dialog.close();dialog.append(close,el('h2','Request '+plan.name),el('p',money(plan.price_cents,plan.currency)+'/month · Complete hosted checkout after ordering to activate your panel resources automatically.'));
 let key=crypto.randomUUID();const f=form([['note','textarea']],async b=>{try{await api('marketplace/orders/create',{plan_id:plan.id,expected_price_cents:plan.price_cents,request_key:key,note:b.note,confirmed:f.elements.confirmed.checked});dialog.close();await open('My Orders')}catch(e){status.textContent=e.message}});f.elements.note.required=false;f.elements.note.maxLength=1000;
 const label=el('label',undefined,'terms-confirm');let check=el('input');check.type='checkbox';check.name='confirmed';check.required=true;label.append(check,el('span','I confirm this order. Payment is completed separately; verified live payment activates my purchased resources for 30 days.'));f.insertBefore(label,f.lastElementChild);f.lastElementChild.textContent='Submit request';const status=el('p');status.setAttribute('role','status');dialog.append(f,status);dialog.onclose=()=>dialog.remove();document.body.append(dialog);dialog.showModal();
}

async function paymentView(name,d){
 d.append(marketplaceNavigation(name));
 d.append(el('p','Hosted one-time payments for approved orders. No card details are collected here. Verified live payment automatically queues account activation. Test gateway transactions do not represent money received.'));
 if(name==='Payments'){
  const rows=await api('payments/transactions');if(!rows.length)d.append(el('p','No payment attempts yet. Open My Orders → Payment options after approval.'));
  for(const row of rows){const card=el('article',undefined,'order-card');card.append(el('h3','Payment #'+row.id+' · Order #'+row.order_id),el('span',row.mode.toUpperCase()+' · '+row.state,'badge'),el('p',row.provider+' · '+money(row.amount_cents,row.currency)+' · Store '+row.seller_id));const verify=el('button','Verify with provider');verify.onclick=guard(async()=>{const result=await api('payments/verify',{id:row.id});$('message').textContent=result.paid?'Provider confirmed payment ('+row.mode+' mode). '+(row.mode==='live'?'Account activation is queued; see My Orders.':'Test payments do not activate services.'):'Provider has not confirmed payment';await open(name)});card.append(verify);
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
 const options=await api('payments/options/'+order.id);const dialog=el('dialog');dialog.className='account-dialog';const close=el('button','×','dialog-close');close.setAttribute('aria-label','Close checkout');close.onclick=()=>dialog.close();dialog.append(close,el('h2','Pay for order #'+order.id),el('p',money(order.price_cents,order.currency)+' for one month. This is a one-time payment, without automatic renewal. Verified live payment activates your purchased panel resources automatically.'));
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
 const d=resetDetail();d.replaceChildren(el('h2',name),el('p','Manage OlamidePanel accounts. Linux hosting accounts and their resources require separate provisioning.'));d.hidden=false;
 const roles=await api('roles'),users=await api('users');const level=roles.find(r=>r.role===me.role)?.level||0;
 const search=el('input');search.type='search';search.placeholder='Search panel accounts';search.setAttribute('aria-label','Search panel accounts');const list=el('div');d.append(search,list);
 const draw=()=>{list.replaceChildren();for(const user of users.filter(u=>(name!=='Suspended Accounts'||!u.active)&&(name!=='Account Termination'||!u.active)&&(name!=='Resellers'||u.role==='reseller')&&(u.username+' '+u.role).toLowerCase().includes(search.value.toLowerCase()))){const row=el('article',undefined,'account-row');row.append(el('strong',user.username),el('p',user.role+' · '+(user.active?'Active':'Suspended')));const target=roles.find(r=>r.role===user.role)?.level??100;
 if(user.id!==me.id&&target<level){const manage=el('button','Manage account');manage.onclick=guard(()=>accountEditor(user));const suspend=el('button',user.active?'Suspend':'Restore');suspend.onclick=guard(async()=>{await api('users/update',{id:user.id,role:user.role,active:!user.active});await accountToolsView(name)});row.append(manage,suspend)}else row.append(el('span','Protected account','badge'));list.append(row)}if(!list.children.length)list.append(el('p','No matching accounts.'))};search.oninput=draw;draw();const add=el('button','Create panel user');add.onclick=guard(()=>open('Create Panel User'));d.append(add);if(d.isConnected){d.scrollIntoView({behavior:'smooth'});d.focus();}
}
async function dnsView(d){
 d.append(el('p','Look up public DNS records. This tool reads DNS; it does not create or edit zones.'));
 const result=el('pre');result.setAttribute('aria-live','polite');const f=form([['name','text']],async b=>{result.textContent='Looking up DNS…';try{result.textContent=JSON.stringify(await api('dns/lookup',{...b,type:f.elements.record_type.value}),null,2)}catch(e){result.textContent=e.message}});const select=el('select');select.name='record_type';select.setAttribute('aria-label','DNS record type');for(const type of ['A','AAAA','CNAME','MX','NS','TXT','SOA','CAA']){const option=el('option',type);option.value=type;select.append(option)}f.insertBefore(select,f.lastElementChild);f.lastElementChild.textContent='Look up records';d.append(f,result);
}
async function moduleStatusView(name){
 const d=resetDetail();d.replaceChildren(el('h2',name));d.hidden=false;
 d.append(el('p','This tool is not available yet. It requires additional backend implementation; installing packages alone will not enable it.'));
 if(me.permissions.includes('users.manage')){const report=await api('modules');const tool=report.tools.find(t=>t.name===name);if(tool)d.append(el('p',tool.detail));const readiness=el('button','View module readiness');readiness.onclick=guard(()=>open('Module Readiness'));d.append(readiness)}
 const available=el('button','Browse working tools');available.onclick=()=>{toolFilter='available';category='Overview';render()};d.append(available);if(d.isConnected)d.scrollIntoView({behavior:'smooth'});
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



async function hostingDomainsView(d){
 if(!me.permissions.includes('users.manage'))throw Error('Super-admin access required');
 d.append(el('p','All panel domain records and operator-managed hosting domains. Viewing a domain does not transfer ownership or enable editing.'));
 const controls=el('div',undefined,'banner-actions'),search=el('input'),refresh=el('button','Refresh status');
 search.type='search';search.placeholder='Search domains, countries or owners';search.setAttribute('aria-label','Search hosting domains');
 const category=el('select');category.setAttribute('aria-label','Filter hosting domains');for(const[value,label]of [['all','All domains'],['country_weather','Country weather']]){const option=el('option',label);option.value=value;category.append(option)}
 controls.append(search,category,refresh);d.append(controls);
 const checkedDate=value=>{const date=new Date(typeof value==='number'?value*1000:value);return Number.isNaN(date.getTime())?'Unavailable':date.toLocaleString()};
 const summary=el('p'),notice=el('p'),list=el('div',undefined,'account-list');summary.setAttribute('role','status');d.append(summary,notice,list);
 const labels={verification_pending:'Configured domain · hosting verification pending',https_ready:'HTTPS configured',waiting_dns:'Waiting for DNS',waiting_tls_retry:'Certificate retry scheduled',needs_attention:'Needs attention',existing_site_preserved:'Existing website preserved',inventory_only:'Inventory only',deployed_waiting_dns:'Application deployed · waiting for DNS',deployed_tls_needs_attention:'Application deployed · HTTPS needs attention',waiting_repository:'Waiting for repository'};
 let domains=[];
 const draw=()=>{
  list.replaceChildren();const q=search.value.trim().toLowerCase();const shown=domains.filter(x=>(category.value==='all'||x.category===category.value)&&(x.name+' '+(x.country||'')+' '+x.owner+' '+x.status).toLowerCase().includes(q));
  summary.textContent=shown.length+' of '+domains.length+' hosting domains';
  if(!shown.length)list.append(el('p','No domains match.'));
  for(const x of shown){
   const row=el('article',undefined,'account-row'),info=el('div');
   info.append(el('strong',x.name),el('p','Owner: '+x.owner+' · '+x.source),el('span',labels[x.status]||x.status,'badge'));
   if(x.country)info.append(el('p','Country weather: '+x.country));
   if(x.www)info.append(el('p','www: '+(x.www==='ready'?(x.status==='https_ready'?'HTTPS configured':'DNS ready'):'Waiting for DNS')));
   if(x.deployment_status)info.append(el('p','Deployment: '+(x.deployment_status==='running'?'Application ready':labels[x.deployment_status]||x.deployment_status)));
   if(x.backend)info.append(el('p','Backend: '+x.backend));
   if(x.repo)info.append(el('p','Repository: '+x.repo+(x.commit?' · '+x.commit.slice(0,7):'')));
   if(x.error)info.append(el('p',x.error));
   if(x.deployment_checked_at)info.append(el('p','Deployment checked: '+checkedDate(x.deployment_checked_at)));
   if(x.document_root)info.append(el('p','Document root: '+x.document_root));
   if(x.configuration)info.append(el('p','Existing configuration: '+x.configuration));
   if(x.checked_at)info.append(el('p','Last checked: '+checkedDate(x.checked_at)));
   row.append(info);
   {const visit=el('a',x.status==='https_ready'?'Open website ↗':'Check website ↗');visit.href='https://'+x.name+'/';visit.target='_blank';visit.rel='noopener noreferrer';row.append(visit)}
   list.append(row);
  }
 };
 const load=async()=>{refresh.disabled=true;try{const data=await api('hosting-domains');domains=data.domains;notice.textContent=data.notice||(data.updated_at?'Hosting snapshot: '+new Date(data.updated_at*1000).toLocaleString():'');draw()}finally{refresh.disabled=false}};
 search.oninput=draw;category.onchange=draw;refresh.onclick=guard(load);await load();
}


async function watchdogView(d){
 if(!me.permissions.includes('users.manage'))throw Error('Super-admin access required');
 const controls=el('div'),refresh=el('button','Refresh reports'),download=el('button','Download displayed report'),search=el('input');search.placeholder='Filter by domain or action';search.setAttribute('aria-label','Filter watchdog reports');controls.append(search,refresh,download);d.append(controls);
 const status=el('p'),totals=el('p'),domains=el('div'),events=el('div');status.setAttribute('role','status');d.append(status,totals,el('h3','Domain health'),domains,el('h3','Recent events'),events);let data;
 const draw=()=>{const q=search.value.trim().toLowerCase();domains.replaceChildren();events.replaceChildren();for(const row of data.domains.filter(x=>JSON.stringify([x.domain,x.action]).toLowerCase().includes(q))){const box=el('article',undefined,'account-row');box.append(el('strong',row.domain),el('p',(row.stale?'STALE · ':'')+(row.healthy?'Healthy':'Needs attention')+' · '+row.action+' · '+new Date(row.checked_at*1000).toLocaleString()),el('p',Object.entries(row.checks).map(([k,v])=>k+': '+(v?'passed':'failed')).join(' · ')));domains.append(box)}for(const row of data.events.filter(x=>JSON.stringify([x.domain,x.action]).toLowerCase().includes(q)))events.append(el('p',new Date(row.checked_at*1000).toLocaleString()+' · '+row.domain+' · '+row.action));};
 const load=async()=>{refresh.disabled=true;try{data=await api('watchdog');if(!d.isConnected)return;status.textContent=data.domains.length+' domains reported. Checks run every minute; 90-day retention, latest 500 events shown.';totals.textContent='Last 24 hours: '+data.totals.map(x=>x.action+': '+x.count).join(' · ');draw()}finally{refresh.disabled=false}};
 refresh.onclick=guard(load);search.oninput=()=>data&&draw();download.onclick=()=>{if(!data)return;const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));const a=el('a');a.href=url;a.download='olamidepanel-watchdog-report.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
 await load();const timer=setInterval(()=>{if(!d.isConnected){clearInterval(timer);return}load().catch(e=>{status.textContent=e.message})},60000);
}

async function moduleManagerView(d){
 if(!me.permissions.includes('users.manage'))throw Error('Super-admin access required');
 const status=el('p'),controls=el('div'),adapters=el('div'),coverage=el('div'),history=el('div'),search=el('input');search.placeholder='Filter module coverage';search.setAttribute('aria-label','Filter module coverage');d.append(status,controls,el('h3','Installable adapters'),adapters,el('h3','Complete tool implementation inventory'),search,coverage,el('h3','Installation and repair jobs'),history);let data;
 const queue=async(adapter,operation)=>{const r=await api('module-manager',{adapter,operation});$('message').textContent=r.queued+' module jobs queued. Repairs may briefly restart the panel.';await load()};
 for(const [label,operation] of [['Check all modules','audit'],['Install / repair all supported adapters','repair']]){const b=el('button',label);b.onclick=guard(()=>queue('all',operation));controls.append(b)}const cancel=el('button','Cancel queued operations');cancel.onclick=guard(()=>queue('all','cancel'));controls.append(cancel);const refresh=el('button','Refresh');refresh.onclick=guard(()=>load());controls.append(refresh);
 const drawTools=()=>{coverage.replaceChildren();const q=search.value.toLowerCase();for(const row of data.tools.filter(x=>(x.category+' '+x.name+' '+x.status).toLowerCase().includes(q))){const box=el('details');box.append(el('summary',row.category+' / '+row.name+' · '+row.status),el('p',row.detail));coverage.append(box)}};search.oninput=()=>data&&drawTools();
 const load=async()=>{data=await api('module-manager');if(!d.isConnected)return;status.textContent=data.notice;adapters.replaceChildren();history.replaceChildren();const busy=data.jobs.some(j=>['queued','running'].includes(j.state));for(const button of controls.querySelectorAll('button'))if(button!==refresh&&button!==cancel)button.disabled=busy;for(const row of data.adapters){const box=el('article',undefined,'account-row');box.append(el('strong',row.id),el('p',row.status?row.status.state+' · '+new Date(row.status.checked_at*1000).toLocaleString():'Not checked'),el('p','Prerequisites: '+(row.prerequisites.join(', ')||'Python standard library')));if(row.status)box.append(el('p',Object.entries(row.status.checks).map(([k,v])=>k+': '+(v?'passed':'failed')).join(' · ')));for(const [label,operation] of [['Check','audit'],['Install / repair','repair']]){const b=el('button',label);b.disabled=busy;b.onclick=guard(()=>queue(row.id,operation));box.append(b)}adapters.append(box)}for(const row of data.jobs)history.append(el('p','#'+row.id+' · '+row.adapter+' · '+row.operation+' · '+row.state+' · '+row.summary));drawTools()};
 await load();const timer=setInterval(()=>{if(!d.isConnected){clearInterval(timer);return}load().catch(e=>{status.textContent=e.message})},15000);
}
