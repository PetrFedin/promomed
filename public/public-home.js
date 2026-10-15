(() => {
  "use strict";
  const $=id=>document.getElementById(id);
  const el=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};

  function renderAgenda(items){
    const root=$("agenda-list");root.replaceChildren();
    $("agenda-count").textContent=items.length+" опубликовано";
    $("agenda-empty").hidden=items.length>0;
    if(!items.length)return;
    for(const item of items){
      const card=el("article","agendaCard"),time=el("div","time",item.start||"—"),body=el("div","");
      const top=el("div",""),pill=el("span","pill",item.format||"событие"),title=el("h3","",item.title||"Без названия");
      top.append(pill,title);
      const meta=el("p","meta",[(item.end?item.start+"–"+item.end:item.start),item.venue,item.track,item.partner].filter(Boolean).join(" · "));
      body.append(top,meta);card.append(time,body);root.append(card);
    }
  }

  function renderContent(items){
    const root=$("content-list");root.replaceChildren();
    $("content-count").textContent=items.length+" опубликовано";
    $("content-empty").hidden=items.length>0;
    if(!items.length)return;
    for(const item of items){
      const card=el("article","contentCard"),pill=el("span","pill",item.kind||"материал"),title=el("h3","",item.title||"Без названия");
      const dek=el("p","",item.dek||""),meta=el("div","meta",[item.duration,item.author,item.partner].filter(Boolean).join(" · "));
      card.append(pill,title,dek,meta);root.append(card);
    }
  }

  async function load(){
    try{
      const response=await fetch("/api/public-state/v1",{credentials:"omit",cache:"no-store",mode:"same-origin",referrerPolicy:"no-referrer"});
      const data=await response.json();
      if(!response.ok)throw new Error(data.error||"public_state_unavailable");
      if(data.version!=="public-state-v1")throw new Error("unexpected_public_state_version");
      renderAgenda(Array.isArray(data.agenda)?data.agenda:[]);
      renderContent(Array.isArray(data.content)?data.content:[]);
    }catch(_){
      $("agenda-list").replaceChildren();$("content-list").replaceChildren();
      $("agenda-empty").hidden=false;$("content-empty").hidden=false;$("error").hidden=false;
      $("agenda-count").textContent="—";$("content-count").textContent="—";
    }
  }
  load();
})();