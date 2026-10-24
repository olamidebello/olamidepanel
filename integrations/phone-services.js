// The host application supplies its own authenticated status endpoint.
// No SIP/app bearer tokens, passwords or sessions are accepted by this widget.
export function phoneServices(host,{loadStatus}){
 const status=document.createElement('p'),refresh=document.createElement('button'),link=document.createElement('a');
 status.setAttribute('role','status');refresh.type='button';refresh.textContent='Refresh phone services';
 link.textContent='Open phone and PBX workspace';link.href='https://sip.dobhrap.com/';link.target='_blank';link.rel='noopener noreferrer';
 host.replaceChildren(status,refresh,link);let disposed=false;
 async function load(){refresh.disabled=true;try{const data=await loadStatus();if(disposed)return;status.textContent='Phone account: '+data.state+(data.phone?' · SIP: '+data.phone.sipStatus+(data.phone.pbxWorkspace?' · PBX workspace created':''):'');}catch{if(!disposed)status.textContent='Phone services status unavailable';}finally{if(!disposed)refresh.disabled=false;}}
 refresh.onclick=load;void load();return ()=>{disposed=true;host.replaceChildren();};
}
