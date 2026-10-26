"use strict";
const $ = id => document.getElementById(id);
let token = "", settings = null, snapshots = [], items = [], offset = 0, total = 0, timer = null, reviewAction = null;
const selected = new Map();
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
function lock() {token=""; settings=null; selected.clear(); $("console").hidden=true; $("login").hidden=false;}
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
  $("operation").textContent = status.operation ? JSON.stringify(status.operation,null,2) : "No operation has run in this session.";
  $("mailbox-rows").innerHTML = status.mailboxes.length ? status.mailboxes.map(m=>"<tr><td>"+escapeHtml(m.label)+"</td><td class='state "+(m.healthy?"good":"")+"'>"+escapeHtml(m.running?"Running":m.healthy?"Current":m.issue)+"</td><td>"+escapeHtml(date(m.last_completed))+"</td><td>"+m.item_count.toLocaleString()+"</td></tr>").join("") : "<tr><td colspan='4'>No mailboxes configured yet. Open Settings to add them.</td></tr>";
}
async function loadSettings() {
  settings=await api("/api/settings"); const form=$("settings-form");
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
async function loadItems() {
  const snapshot=$("snapshot").value; if(!snapshot){$("item-rows").innerHTML="";return;}
  const data=await api("/api/snapshots/"+snapshot+"/items?offset="+offset+"&q="+encodeURIComponent($("search").value));
  items=data.items;total=data.total;
  $("item-count").textContent=total+" messages · "+selected.size+" selected · showing "+(total?offset+1:0)+"–"+Math.min(offset+100,total);
  $("item-rows").innerHTML=items.map((item,index)=>"<tr><td><input type='checkbox' aria-label='Select "+escapeHtml(item.subject)+"' data-item='"+index+"' "+(selected.has(item.folder_id+"|"+item.item_id)?"checked":"")+"></td><td>"+escapeHtml(item.subject)+"</td><td>"+escapeHtml(item.folder)+"</td><td>"+escapeHtml(date(item.modified))+"</td></tr>").join("") || "<tr><td colspan='4'>No messages match this view.</td></tr>";
  $("previous").disabled=offset===0;$("next").disabled=offset+100>=total;
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
bind("snapshot","change",async()=>{selected.clear();offset=0;await loadItems();});
bind("search","change",async()=>{offset=0;await loadItems();});
bind("previous","click",async()=>{offset=Math.max(0,offset-100);await loadItems();});
bind("next","click",async()=>{offset+=100;await loadItems();});
bind("item-rows","change",e=>{if(e.target.dataset.item===undefined)return;const item=items[Number(e.target.dataset.item)];const key=item.folder_id+"|"+item.item_id;if(e.target.checked)selected.set(key,{folder_id:item.folder_id,item_id:item.item_id});else selected.delete(key);$("item-count").textContent=total+" messages · "+selected.size+" selected";});
bind("verify","click",async()=>{if(!$("snapshot").value)throw Error("Choose a backup first.");await api("/api/snapshots/"+$("snapshot").value+"/verify",{method:"POST",body:"{}"});message("Verification started. See Overview for the result.");});
bind("preview-restore","click",async()=>{if(!selected.size)throw Error("Select at least one message.");const plan=await api("/api/restore/preview",{method:"POST",body:JSON.stringify({snapshot_id:$("snapshot").value,destination:$("destination").value,selections:[...selected.values()]})});review("Restore "+plan.count+" messages?","A new recovery folder will be created in "+plan.destination+". Existing messages will remain in place.",async()=>{await api("/api/restore",{method:"POST",body:JSON.stringify({snapshot_id:plan.snapshot_id,destination:plan.destination,selections:plan.selections,confirmation:plan.confirmation})});message("Restore started. See Overview for the result.");});});
bind("preview-prune","click",async()=>{const plan=await api("/api/retention/preview");if(!plan.count){message("No recovery points are eligible for removal.");return;}review("Remove "+plan.count+" expired recovery points?","This cleanup permanently removes the selected older recovery points and unreferenced data. It cannot be undone.",async()=>{await api("/api/retention/apply",{method:"POST",body:JSON.stringify({confirmation:plan.confirmation})});message("Cleanup started.");});});
bind("review-cancel","click",()=>{$("review").close();reviewAction=null;});
bind("review-confirm","click",async()=>{$("review-confirm").disabled=true;try{await reviewAction();$("review").close();}finally{$("review-confirm").disabled=false;}});
document.querySelectorAll("[data-certificate]").forEach(button=>button.addEventListener("click",async()=>{try{const response=await fetch("/api/certificates/"+button.dataset.certificate,{headers:{Authorization:"Bearer "+token}});if(!response.ok)throw Error("Certificate is unavailable.");const url=URL.createObjectURL(await response.blob());const a=document.createElement("a");a.href=url;a.download=button.dataset.certificate+"-public.pem";a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(err){message(err.message);}}));
setInterval(()=>{if(token)refresh().catch(err=>message(err.message));},15000);
