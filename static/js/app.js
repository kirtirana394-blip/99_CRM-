async function postJSON(url, body={}, form=false){
  const opts={method:"POST",headers:{}};
  if(form){opts.body=body}else{opts.headers["Content-Type"]="application/json";opts.body=JSON.stringify(body)}
  const r=await fetch(url,opts); if(!r.ok) throw new Error(await r.text()); return r.json();
}
document.addEventListener("DOMContentLoaded",()=>{
 const all=document.getElementById("checkAll"); if(all) all.addEventListener("change",()=>document.querySelectorAll(".lead-check").forEach(x=>x.checked=all.checked));
});
async function completeFollowup(id){await postJSON(`/followups/${id}/complete`);location.reload()}
async function taskStatus(id,status){await postJSON(`/tasks/${id}/status`,new URLSearchParams({status}),true)}
async function toggleUser(id){await postJSON(`/users/${id}/toggle`);location.reload()}
async function deleteLead(id){if(!confirm("Delete this lead and its related CRM records?"))return;const r=await postJSON(`/leads/${id}/delete`);if(r.ok)location.href="/leads"}
