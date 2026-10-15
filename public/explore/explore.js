(() => {
  "use strict";
  const $=id=>document.getElementById(id);
  const escText=value=>value==null?"":String(value);

  function clear(node){node.replaceChildren();}
  function node(tag,cls,text){
    const n=document.createElement(tag);
    if(cls)n.className=cls;
    if(text!==undefined)n.textContent=escText(text);
    return n;
  }
  function publicationBadge(publication){
    const p=node("span","pub","Допущено к публикации");
    if(publication?.sourceRef)p.title="Источник допуска: "+publication.sourceRef;
    return p;
  }
  function renderAgenda(items){
    const root=$("agenda");clear(root);
    $("agenda-count").textContent=String(items.length);
    $("agenda-empty").hidden=items.length>0;
    for(const item of items){
      const card=node("article","eventCard");
      const time=node("div");
      time.append(node("div","eventTime",item.start||"—"),node("div","eventMeta",(item.end||"")+" · "+(item.venue||"")));
      const body=node("div");
      body.append(node("h3","",item.title||"Событие"));
      const tags=node("div","tags");
      for(const value of [item.track,item.format,item.audience].filter(Boolean))tags.append(node("span","tag",value));
      body.append(tags);
      card.append(time,body,publicationBadge(item.publication));
      root.append(card);
    }
  }
  function renderContent(items){
    const root=$("content");clear(root);
    $("content-count").textContent=String(items.length);
    $("content-empty").hidden=items.length>0;
    for(const item of items){
      const card=node("article","story");
      card.append(node("p","eyebrow",item.theme||item.kind||"МАТЕРИАЛ"));
      card.append(node("h3","",item.title||"Материал"));
      if(item.dek)card.append(node("p","",item.dek));
      const meta=[item.duration,item.author,item.partner].filter(Boolean).join(" · ");
      if(meta)card.append(node("p","",meta));
      card.append(publicationBadge(item.publication));
      root.append(card);
    }
  }
  async function load(){
    const status=$("status");
    status.classList.remove("error");
    status.textContent="Загружаем открытую программу…";
    try{
      const response=await fetch("/api/public-state/v1",{
        method:"GET",credentials:"omit",cache:"no-store",mode:"same-origin",referrerPolicy:"no-referrer"
      });
      const data=await response.json().catch(()=>({}));
      if(!response.ok)throw new Error(data.error||"public_state_unavailable");
      renderAgenda(Array.isArray(data.agenda)?data.agenda:[]);
      renderContent(Array.isArray(data.content)?data.content:[]);
      status.textContent=(data.counts?.agenda||0)+(data.counts?.content||0)>0
        ?"Показаны только версии, допущенные public-state v1."
        :"Публичная выдача пока пуста — неподтверждённые записи не показываются.";
    }catch(_){
      renderAgenda([]);renderContent([]);
      status.classList.add("error");
      status.textContent="Не удалось подтвердить публичную выдачу. Непроверенные локальные данные не подставлены.";
    }
  }
  $("agenda-jump").addEventListener("click",()=>$("agenda-section").scrollIntoView({behavior:"smooth",block:"start"}));
  load();
})();