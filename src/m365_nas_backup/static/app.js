"use strict";
const $ = id => document.getElementById(id);
let token = "", settings = null, snapshots = [], items = [], offset = 0, total = 0, timer = null, reviewAction = null;
const selected = new Map();
let comparison = null, ignoredComparison = null, pendingCompare = "", compareTimer = null, itemRequest = 0, certificates = [];
const itemKey = item => JSON.stringify([item.folder_id,item.item_id]);
const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
function message(text) {$("message").textContent = text; $("message").hidden = false; clearTimeout(timer); timer = setTimeout(() => $("message").hidden = true, 9000);}
async function api(path, options = {}) {
  const response = await fetch(path, {...options, headers: {Authorization:"Bearer "+token, "Content-Type":"application/json", ...(options.headers||{})}});
  const body = await response.json();
  if (!response.ok) {
    if (response.status === 401) lock();
    throw Error(typeof body.detail === "string" ? body.detail : "Please check the supplied values.");
  }
  return body;
}
function lock() {clearTimeout(compareTimer); pendingCompare=""; comparison=null; itemRequest++; token=""; settings=null; selected.clear(); $("console").hidden=true; $("login").hidden=false;}
function date(value) {return value ? new Date(value).toLocaleString() : "Never";}
async function refresh() {
  if (!token) return;
  const status = await api("/api/status");
  $("health-banner").textContent = status.healthy ? "All selected mailboxes have a recent completed backup." : status.configured ? "Backup coverage needs attention. Check the mailbox results below." : "Set up your Microsoft connection and select mailboxes to start.";
  $("health-banner").classList.toggle("good",status.healthy);
  $("mailbox-count").textContent = status.mailboxes.length;
  $("free-space").textContent = (status.free_bytes/1024**3).toFixed(1)+" GB";
  $("schedule-state").textContent = status.scheduler_enabled ? "Enabled" : "Paused";
  $("version").textContent = status.version;
  $("scope").textContent = status.scope;
  $("backup-now").disabled=status.busy;
  $("compare").disabled=status.busy;
  certificates=status.certificates||[];
  renderCertificates();
  const warnings=certificates.filter(c=>c.active?.warning && (c.purpose==="backup" || settings?.restore_enabled));
  $("certificate-warning").hidden=!warnings.length;
  $("certificate-warning").textContent=warnings.map(c=>c.purpose+" certificate expires "+date(c.active.expires)+". Renew it in Settings.").join(" ");
  if(pendingCompare && status.comparison?.snapshot_id===pendingCompare && status.comparison.id!==ignoredComparison){
    comparison=status.comparison; pendingCompare=""; offset=0; await loadItems();
  } else if(pendingCompare && !status.busy){
    pendingCompare=""; $("comparison-summary").textContent="Comparison did not complete: "+(status.operation?.error||"another operation ran")+". Showing saved backup contents; retry Compare.";
  }
  if(pendingCompare){clearTimeout(compareTimer);compareTimer=setTimeout(()=>refresh().catch(err=>{pendingCompare="";message(err.message);}),1500);}
  $("operation").textContent = status.operation ? JSON.stringify(status.operation,null,2) : "No operation has run in this session.";
  $("mailbox-rows").innerHTML = status.mailboxes.length ? status.mailboxes.map(m=>"<tr><td>"+escapeHtml(m.label)+"</td><td class='state "+(m.healthy?"good":"")+"'>"+escapeHtml(m.running?"Running":m.healthy?"Current":m.issue)+"</td><td>"+escapeHtml(date(m.last_completed))+"</td><td>"+m.item_count.toLocaleString()+"</td></tr>").join("") : "<tr><td colspan='4'>No mailboxes configured yet. Open Settings to add them.</td></tr>";
}
async function loadSettings() {
  settings=await api("/api/settings"); certificates=await api("/api/certificates"); renderCertificates(); const form=$("settings-form");
  for(const name of ["tenant_id","client_id","restore_client_id","interval_minutes","stale_after_minutes","minimum_free_gb"]) form.elements[name].value=settings[name];
  for(const name of ["scheduler_enabled","restore_enabled"]) form.elements[name].checked=settings[name];
  $("mailboxes").value=settings.mailboxes.filter(m=>m.enabled).map(m=>m.user).join("\n");
  $("retention-mode").value=settings.retention.days===null?"forever":"days";
  $("retention-days").value=settings.retention.days??40;
  $("minimum-snapshots").value=settings.retention.minimum_snapshots;
  $("automatic-pruning").checked=settings.retention.automatic_pruning;
  $("retention-days").disabled=settings.retention.days===null;
  $("destination").innerHTML=settings.mailboxes.map(m=>"<option value='"+escapeHtml(m.user)+"'>"+escapeHtml(m.label||m.user)+"</option>").join("");
}
async function loadSnapshots(reset=true) {
  const previous=$("snapshot").value;
  const page=await api("/api/snapshots?limit=1000&offset="+(reset?0:snapshots.length));
  snapshots=reset?page:[...snapshots,...page.filter(s=>!snapshots.some(existing=>existing.id===s.id))];
  $("older-snapshots").disabled=page.length<1000;
  $("snapshot").innerHTML="<option value=''>Choose a backup</option>"+snapshots.map(s=>"<option value='"+s.id+"'>"+escapeHtml(s.mailbox+" · "+date(s.completed)+" · "+s.item_count+" items")+"</option>").join("");
  $("snapshot").value=previous;
}
function comparisonQuery() {return "status="+encodeURIComponent($("difference-filter").value)+"&q="+encodeURIComponent($("search").value);}
async function loadItems() {
  const request=++itemRequest, snapshot=$("snapshot").value;
  if(!snapshot){$("item-rows").innerHTML="";return;}
  const active=comparison?.snapshot_id===snapshot?comparison:null;
  const path=active?"/api/comparisons/"+active.id+"?"+comparisonQuery():"/api/snapshots/"+snapshot+"/items?q="+encodeURIComponent($("search").value);
  const data=await api(path+"&offset="+offset);
  if(request!==itemRequest || snapshot!==$("snapshot").value)return;
  items=data.items;total=data.total;
  $("select-matches").disabled=!active;
  $("difference-filter").disabled=!active;
  if(active){
    const c=data.counts;
    $("comparison-summary").textContent=data.mailbox+" · compared "+date(data.completed)+" · "+["missing","changed","moved","new","unchanged"].map(k=>(c[k]||0)+" "+k).join(" · ");
  }
  $("item-count").textContent=total+" messages · "+selected.size+" selected · showing "+(total?offset+1:0)+"–"+Math.min(offset+100,total);
  $("item-rows").innerHTML=items.map((item,index)=>"<tr><td><input type='checkbox' aria-label='Select "+escapeHtml(item.subject)+"' data-item='"+index+"' "+(item.restorable===false?"disabled ":"")+(selected.has(itemKey(item))?"checked":"")+"></td><td>"+escapeHtml(item.subject)+"</td><td>"+escapeHtml(item.folder||"—")+"</td><td>"+escapeHtml(item.current_folder||"—")+"</td><td>"+escapeHtml(item.status?(item.status==="changed"&&item.moved?"Changed and moved":item.status):"Not compared")+"</td></tr>").join("") || "<tr><td colspan='6'>No messages match this view.</td></tr>";
  $("previous").disabled=offset===0;$("next").disabled=offset+100>=total;
}
async function startCompare() {
  const snapshot=$("snapshot").value;if(!snapshot)throw Error("Choose a backup first.");
  const started=await api("/api/snapshots/"+snapshot+"/compare",{method:"POST",body:"{}"});
  ignoredComparison=started.previous_comparison_id;
  comparison=null;selected.clear();pendingCompare=snapshot;offset=0;
  $("comparison-summary").textContent="Reading the current source mailbox… You can browse the saved backup while the comparison runs.";
  await loadItems();await refresh();
}
function selectRows(rows) {
  const next=new Map(selected);
  rows.filter(r=>r.restorable!==false).forEach(r=>next.set(itemKey(r),{folder_id:r.folder_id,item_id:r.item_id}));
  if(next.size>1000)throw Error("Select at most 1,000 messages per restore. Narrow the filter or clear the existing selection.");
  selected.clear();next.forEach((v,k)=>selected.set(k,v));
}
function renderCertificates(){
  $("certificate-status").textContent=certificates.map(c=>c.purpose+": "+(c.active?"active until "+date(c.active.expires):"not initialized")+(c.pending?"; replacement until "+date(c.pending.expires):"")).join(" | ");
}
async function downloadCertificate(purpose,pending=false){
  const response=await fetch("/api/certificates/"+purpose+(pending?"?pending=true":""),{headers:{Authorization:"Bearer "+token}});
  if(!response.ok)throw Error("Certificate is unavailable. Prepare a replacement first if needed.");
  const url=URL.createObjectURL(await response.blob());const a=document.createElement("a");a.href=url;a.download=purpose+(pending?"-replacement-public.pem":"-public.pem");a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function review(title,body,action) {$("review-title").textContent=title;$("review-body").textContent=body;reviewAction=action;$("review-confirm").disabled=false;$("review").showModal();}
function bind(id,event,action) {$(id).addEventListener(event, e=>{Promise.resolve(action(e)).catch(err=>message(err.message));});}
bind("login-form","submit",async e=>{e.preventDefault();token=$("token").value.trim();await loadSettings();await refresh();$("token").value="";$("login").hidden=true;$("console").hidden=false;});
bind("logout","click",lock);
document.querySelectorAll("[data-tab]").forEach(button=>button.addEventListener("click",async()=>{try{if(button.dataset.tab==="recovery")await loadSnapshots();if(button.dataset.tab==="settings")await loadSettings();document.querySelectorAll(".tab").forEach(s=>s.hidden=s.id!==button.dataset.tab);document.querySelectorAll("[data-tab]").forEach(b=>b.removeAttribute("aria-current"));button.setAttribute("aria-current","page");}catch(err){message(err.message);}}));
bind("backup-now","click",async()=>{await api("/api/backup",{method:"POST",body:"{}"});message("Backup started.");await refresh();});
bind("settings-form","submit",async e=>{
  e.preventDefault(); const f=e.currentTarget; const next={...settings};
  for(const name of ["tenant_id","client_id","restore_client_id"])next[name]=f.elements[name].value.trim();
  for(const name of ["interval_minutes","stale_after_minutes","minimum_free_gb"])next[name]=Number(f.elements[name].value);
  for(const name of ["scheduler_enabled","restore_enabled"])next[name]=f.elements[name].checked;
  const entered=$("mailboxes").value.split(/\r?\n/).map(s=>s.trim()).filter(Boolean);
  next.mailboxes=entered.map(user=>({...settings.mailboxes.find(m=>m.user.toLowerCase()===user.toLowerCase()),user,enabled:true}));
  next.mailboxes.push(...settings.mailboxes.filter(m=>!m.enabled&&!entered.some(user=>user.toLowerCase()===m.user.toLowerCase())));
  next.retention={days:$("retention-mode").value==="forever"?null:Number($("retention-days").value),minimum_snapshots:Number($("minimum-snapshots").value),automatic_pruning:$("automatic-pruning").checked};
  const save=async()=>{settings=await api("/api/settings",{method:"PUT",body:JSON.stringify(next)});message("Settings saved.");await loadSettings();await refresh();};
  if(next.retention.automatic_pruning && (!settings.retention.automatic_pruning || (next.retention.days??Infinity)<(settings.retention.days??Infinity) || next.retention.minimum_snapshots<settings.retention.minimum_snapshots))review("Apply automatic retention?","Expired recovery points can be permanently removed after a successful backup. The configured minimum number of snapshots will remain.",save);else await save();
});
bind("retention-mode","change",()=>{$("retention-days").disabled=$("retention-mode").value==="forever";});
bind("older-snapshots","click",()=>loadSnapshots(false));
bind("snapshot","change",async()=>{selected.clear();comparison=null;pendingCompare="";offset=0;$("difference-filter").value="differences";const snap=snapshots.find(s=>s.id===$("snapshot").value);if(snap)$("destination").value=snap.mailbox;await loadItems();if(snap)await startCompare();});
bind("compare","click",startCompare);
bind("difference-filter","change",async()=>{offset=0;await loadItems();});
bind("select-page","click",async()=>{selectRows(items);await loadItems();});
bind("clear-selection","click",async()=>{selected.clear();await loadItems();});
bind("select-matches","click",async()=>{if(!comparison)throw Error("Compare the mailbox first.");const id=comparison.id,snapshot=$("snapshot").value;const rows=await api("/api/comparisons/"+id+"/selection?"+comparisonQuery());if(id!==comparison?.id||snapshot!==$("snapshot").value)return;selectRows(rows);await loadItems();});
bind("search","change",async()=>{offset=0;await loadItems();});
bind("previous","click",async()=>{offset=Math.max(0,offset-100);await loadItems();});
bind("next","click",async()=>{offset+=100;await loadItems();});
bind("item-rows","change",e=>{if(e.target.dataset.item===undefined)return;const item=items[Number(e.target.dataset.item)];const key=itemKey(item);if(e.target.checked){try{selectRows([item]);}catch(err){e.target.checked=false;throw err;}}else selected.delete(key);$("item-count").textContent=total+" messages · "+selected.size+" selected";});
bind("verify","click",async()=>{if(!$("snapshot").value)throw Error("Choose a backup first.");await api("/api/snapshots/"+$("snapshot").value+"/verify",{method:"POST",body:"{}"});message("Verification started. See Overview for the result.");});
bind("preview-restore","click",async()=>{if(!selected.size)throw Error("Select at least one message.");const plan=await api("/api/restore/preview",{method:"POST",body:JSON.stringify({snapshot_id:$("snapshot").value,destination:$("destination").value,selections:[...selected.values()]})});review("Restore "+plan.count+" messages?","A new recovery folder will be created in "+plan.destination+". Existing messages will remain in place.",async()=>{await api("/api/restore",{method:"POST",body:JSON.stringify({snapshot_id:plan.snapshot_id,destination:plan.destination,selections:plan.selections,confirmation:plan.confirmation})});message("Restore started. See Overview for the result.");});});
bind("preview-prune","click",async()=>{const plan=await api("/api/retention/preview");if(!plan.count){message("No recovery points are eligible for removal.");return;}review("Remove "+plan.count+" expired recovery points?","This cleanup permanently removes the selected older recovery points and unreferenced data. It cannot be undone.",async()=>{await api("/api/retention/apply",{method:"POST",body:JSON.stringify({confirmation:plan.confirmation})});message("Cleanup started.");});});
bind("review-cancel","click",()=>{$("review").close();reviewAction=null;});
bind("review-confirm","click",async()=>{$("review-confirm").disabled=true;try{await reviewAction();$("review").close();}finally{$("review-confirm").disabled=false;}});
document.querySelectorAll("[data-certificate]").forEach(button=>button.addEventListener("click",()=>downloadCertificate(button.dataset.certificate).catch(err=>message(err.message))));
bind("prepare-certificate","click",async()=>{const purpose=$("certificate-purpose").value;await api("/api/certificates/"+purpose+"/prepare",{method:"POST",body:JSON.stringify({days:Number($("certificate-days").value)})});certificates=await api("/api/certificates");renderCertificates();message("Replacement prepared. Download it and upload it to the matching Entra application before activation.");});
bind("download-pending","click",()=>downloadCertificate($("certificate-purpose").value,true));
bind("activate-certificate","click",()=>{const purpose=$("certificate-purpose").value;const pending=certificates.find(c=>c.purpose===purpose)?.pending;if(!pending)throw Error("Prepare and upload a replacement first.");review("Activate the "+purpose+" certificate?","Upload replacement "+pending.thumbprint+" to the matching Entra application first. Authentication will be tested before switching. Keep the existing certificate registered until this succeeds.",async()=>{await api("/api/certificates/"+purpose+"/activate",{method:"POST",body:JSON.stringify({thumbprint:pending.thumbprint})});message("Testing certificate. See Overview for the result.");await refresh();});});
setInterval(()=>{if(token)refresh().catch(err=>message(err.message));},15000);
