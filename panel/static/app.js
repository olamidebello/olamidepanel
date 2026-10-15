const $=id=>document.getElementById(id);let me,category='Overview',cwd='';
const groups={Files:['File Manager','Images','Directory Privacy','Disk Usage','FTP Accounts','FTP Connections','Anonymous FTP','Web Disk','Git Version Control','Git Deployment','Backups','Backup Wizard','File Restoration'],Domains:['Domains','Redirects','DNS Zone Editor','Dynamic DNS','Site Publisher','Site Builder','SEO','Social Media'],Email:['Email Accounts','Forwarders','Domain Forwarders','Autoresponders','Default Address','Email Routing','Email Filters','Global Filters','Email Deliverability','Email Disk Usage','Address Importer','Archive','Mailing Lists','BoxTrapper','Greylisting','Encryption','Calendars and Contacts','Calendar Sharing','Calendar Delegation','Spam Filters','Track Delivery','Webmail'],Databases:['Database Manager','Database Users','Database Wizard','phpMyAdmin','Remote Database Access','PostgreSQL','PostgreSQL Wizard','phpPgAdmin'],Security:['SSH Access','IP Blocker','SSL/TLS','Private Keys','Certificate Signing Requests','Certificates','SSL Sites','SSL Status','AutoSSL','ModSecurity','Hotlink Protection','Leech Protection','Two-Factor Authentication','API Tokens','Security Policy'],Software:['PHP Manager','PHP-FPM','PHP INI Editor','Application Manager','Environment Variables','Application Dependencies','Optimize Website','Perl Modules','PEAR Packages','RubyGems','Ruby on Rails','Application Installer'],Metrics:['Server Metrics','Visitors','Errors','Bandwidth','Raw Access','AWStats','Analog Stats','Webalizer','FTP Statistics','Metrics Editor','Resource Usage','Site Monitoring'],Advanced:['Terminal','Cron Jobs','Track DNS','Indexes','Error Pages','Apache Handlers','MIME Types','API Shell','Virus Scanner'],Preferences:['Password and Security','Language','Contact Information','Account Preferences','User Manager','Manage Team'],Administration:['Access Control','Create Panel User','Audit Log','List Accounts','Suspended Accounts','Account Provisioning','Account Suspension','Account Termination','Shell Access','IP Assignment','Bandwidth Limits','Packages','Feature Manager','Resellers','Server Configuration','Hostname and Resolvers','IP Management','DNS Zones','DNS Templates','DNS Cluster','Configuration Cluster','Backup Configuration','Backup Restoration','Account Transfers','Apache Configuration','PHP Configuration','Mail Configuration','FTP Configuration','Service Manager','Log Rotation','Package Management','Database Services','Mail Queue','Delivery Reports','Brute Force Protection','Host Access Control','Compiler Access','Service Certificates','Process Manager','Task Queue','Service Restarts','System Reboot','Contact Manager','Hooks','Plugins','Branding','Themes and Locales','Support'],Integrations:['WP Toolkit','Softaculous','CloudLinux','LiteSpeed','JetBackup','Comet Backup','Imunify','External DNS/CDN','Billing','External Monitoring','AI Services']};
const implemented=['Access Control','File Manager','Domains','Server Metrics','Create Panel User','Audit Log'];
function el(tag,text,cls){const x=document.createElement(tag);if(text!==undefined)x.textContent=text;if(cls)x.className=cls;return x}
async function api(path,body){const r=await fetch('/api/'+path,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json','X-CSRF-Token':me?.csrf||''}:{},body:body?JSON.stringify(body):undefined});if(!r.ok){let d=await r.json();throw Error(d.error)}return r.status===200&&r.headers.get('Content-Type')?.includes('json')?r.json():null}
function guard(fn){return async(...args)=>{try{$('message').textContent='';await fn(...args)}catch(e){$('message').textContent=e.message}}}
function form(fields,submit){let f=el('form');for(const [name,type]of fields){let l=el('label',name);let i=el(type==='textarea'?'textarea':'input');i.name=name;if(type!=='textarea')i.type=type;i.required=true;l.append(i);f.append(l)}f.append(el('button','Save'));f.onsubmit=guard(async e=>{e.preventDefault();await submit(Object.fromEntries(new FormData(f)));});return f}
let toolFilter='all';
let favorites;
try { favorites=JSON.parse(localStorage.getItem('olamide-favorites')||'[]'); if(!Array.isArray(favorites))favorites=[]; } catch { favorites=[]; }
const navIcons={Overview:'◈',Files:'▤',Domains:'◎',Email:'✉',Databases:'▥',Security:'♧',Software:'⌘',Metrics:'▥',Advanced:'⌁',Preferences:'⚙',Administration:'▦',Integrations:'◇'};
function render(){
 let nav=$('nav');nav.replaceChildren();
 for(const name of ['Overview',...Object.keys(groups)].filter(n=>me?.permissions?.includes('users.manage')||n!=='Administration')){
  let b=el('button',undefined,name===category?'active':'');b.append(el('span',navIcons[name]||'◇','nav-icon'),el('span',name));
  b.setAttribute('aria-current',name===category?'page':'false');b.onclick=()=>{category=name;render()};nav.append(b);
 }
 $('heading').textContent=category==='Overview'?'Hosting overview':category;$('crumb').textContent=category;
 $('sectionTitle').textContent=category==='Overview'?'Your hosting tools':category+' tools';
 $('detail').hidden=true;$('tools').replaceChildren();let count=0;
 let entries=Object.entries(groups).filter(([g])=>(category==='Overview'||g===category)&&(me?.permissions?.includes('users.manage')||g!=='Administration'));
 for(const[g,names]of entries)for(const name of names){
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
async function open(name){let d=$('detail');d.replaceChildren(el('h2',name));d.hidden=false;d.scrollIntoView({behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});d.focus({preventScroll:true});if(!implemented.includes(name)){d.append(el('p','This module is not implemented. No server changes are made. It requires a tested service adapter or an external licensed integration.'));return}
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
   const toggle=el('button',user.active?'Suspend':'Restore');toggle.onclick=guard(async()=>{await api('users/update',{id:user.id,role:user.role,active:!user.active});await open(name)});row.append(save,toggle);
  }else row.append(el('span',user.id===me.id?'Your account':'Protected level','badge'));list.append(row);
 }};search.oninput=renderUsers;renderUsers();
 d.append(el('h3','Role permissions'));
 for(const role of roles){const item=el('details');item.append(el('summary',role.role.replaceAll('_',' ')+' · Level '+role.level),el('p',role.permissions.join(' · ')));d.append(item)}
 d.append(el('h3','Register a panel user'));d.append(await userRegistration());
}
if(name==='Domains'){d.append(el('p','Manage domain inventory. Live DNS, virtual hosts and TLS provisioning are not implemented.'));d.append(form([['name','text']],async b=>{let r=await api('domains',b);$('message').textContent=r.status;await open(name)}));for(const x of await api('domains'))d.append(el('p',x.name))}
if(name==='File Manager'){d.append(el('p','Account files /'+cwd));if(cwd){let back=el('button','Up');back.onclick=guard(async()=>{cwd=cwd.split('/').slice(0,-1).join('/');await open(name)});d.append(back)}const files=await api('files?path='+encodeURIComponent(cwd));for(const x of files){let b=el('button',(x.directory?'▸ ':'')+x.name);b.onclick=guard(async()=>{let path=[cwd,x.name].filter(Boolean).join('/');if(x.directory){cwd=path;return open(name)}let r=await api('files?path='+encodeURIComponent(path));let f=form([['content','textarea']],async val=>{await api('files',{action:'write',path,content:val.content});$('message').textContent='File saved'});f.elements.content.value=r.content;d.append(f)});d.append(b)}d.append(el('h3','Create file'));d.append(form([['path','text'],['content','textarea']],async b=>{await api('files',{...b,path:[cwd,b.path].filter(Boolean).join('/'),action:'write'});await open(name)}));d.append(el('h3','Create folder'));d.append(form([['path','text']],async b=>{await api('files',{action:'mkdir',path:[cwd,b.path].filter(Boolean).join('/')});await open(name)}))}
if(name==='Server Metrics')d.append(el('pre',JSON.stringify(await api('metrics'),null,2)));
if(name==='Audit Log')for(const x of await api('audit'))d.append(el('p',new Date(x.created*1000).toLocaleString()+' · '+x.actor+' · '+x.action));
if(name==='Create Panel User'){d.append(el('p','Register a panel account. This does not create a Linux account.'));d.append(await userRegistration())}}
async function userRegistration(){
 const roles=await api('roles');const f=form([['username','text'],['password','password']],async b=>{await api('users',{...b,role:f.elements.role.value});f.reset();$('message').textContent='Panel account registered'});
 const label=el('label','Access level');const select=el('select');select.name='role';
 for(const role of roles){let option=el('option',role.role.replaceAll('_',' '));option.value=role.role;option.selected=role.role==='user';select.append(option)}label.append(select);f.insertBefore(label,f.lastElementChild);f.elements.password.minLength=14;return f;
}
async function start(){me=await api('me');$('login').hidden=true;$('workspace').hidden=false;$('logout').hidden=false;render();let m=await api('metrics');$('metrics').replaceChildren();for(const[label,value]of [['SERVER',m.hostname],['DISK USED',(m.disk_used/2**30).toFixed(1)+' GB'],['SYSTEM LOAD',m.load[0].toFixed(2)]]){let box=el('div',undefined,'metric');box.append(el('small',label),el('strong',value),el('small','LIVE SERVER DATA'));$('metrics').append(box)}}
$('loginForm').onsubmit=guard(async e=>{e.preventDefault();await api('login',Object.fromEntries(new FormData(e.target)));e.target.reset();await start()});$('logout').onclick=guard(async()=>{await api('logout',{});location.reload()});$('search').oninput=render;start().catch(()=>{});

function setTheme(theme){document.documentElement.dataset.theme=theme;$('theme').setAttribute('aria-label',theme==='dark'?'Use light theme':'Use dark theme');$('theme').setAttribute('aria-pressed',String(theme==='dark'));try{localStorage.setItem('olamide-theme',theme)}catch{}}
let savedTheme;try{savedTheme=localStorage.getItem('olamide-theme')}catch{}
setTheme(savedTheme||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'));
$('theme').onclick=()=>setTheme(document.documentElement.dataset.theme==='dark'?'light':'dark');
$('help').onclick=()=>$('guide').showModal();$('closeGuide').onclick=()=>$('guide').close();
$('quickFiles').onclick=guard(()=>open('File Manager'));$('quickDomain').onclick=guard(()=>open('Domains'));$('guideMetrics').onclick=guard(()=>open('Server Metrics'));
$('showAvailable').onclick=()=>{category='Overview';toolFilter='available';$('search').value='';render();$('sectionTitle').scrollIntoView({block:'start'})};
document.querySelectorAll('[data-filter]').forEach(b=>b.onclick=()=>{toolFilter=b.dataset.filter;render()});
document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(document.activeElement.tagName)&&!$('workspace').hidden&&!$('guide').open){e.preventDefault();$('search').focus()}});
