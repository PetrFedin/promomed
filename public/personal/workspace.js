(() => {
  "use strict";
  const API="/api/my-state/v1";
  const $=id=>document.getElementById(id);
  const state={token:null,account:null,generation:0,controllers:new Set(),notes:[],next:null,pending:null,busy:false};

  function message(text="",error=false){
    const n=$("notice");n.hidden=!text;n.textContent=text;n.classList.toggle("error",!!error);
  }
  function abortAll(){for(const c of state.controllers)c.abort();state.controllers.clear();}
  function clearSession(){
    state.generation++;abortAll();state.token=null;state.account=null;state.notes=[];state.next=null;state.pending=null;state.busy=false;
    $("workspace").hidden=true;$("signed-out").hidden=false;$("logout").hidden=true;
    $("login-button").disabled=false;$("save-note").disabled=true;$("logout-all").disabled=false;
    $("password").value="";$("note-text").value="";$("notes").replaceChildren();$("bookings").replaceChildren();
    updateCount();
  }
  function stale(g,token){return g!==state.generation||token!==state.token;}
  async function request(url,{method="GET",body=null,anonymous=false}={}){
    const g=state.generation,token=state.token,controller=new AbortController();state.controllers.add(controller);
    const timer=setTimeout(()=>controller.abort(),8000);
    try{
      const headers={};
      if(!anonymous&&token)headers.Authorization="Bearer "+token;
      if(body!==null)headers["Content-Type"]="application/json";
      const response=await fetch(url,{method,headers,body:body===null?undefined:JSON.stringify(body),signal:controller.signal,
        credentials:"omit",cache:"no-store",mode:"same-origin",referrerPolicy:"no-referrer"});
      let data={};try{data=await response.json();}catch(_){}
      if(stale(g,token)){const e=new Error("stale");e.stale=true;throw e;}
      if(!response.ok){const e=new Error(data.error||"request_failed");e.status=response.status;e.code=data.error;throw e;}
      return data;
    } finally {clearTimeout(timer);state.controllers.delete(controller);}
  }
  function fail(e,g,text="Кабинет временно недоступен. Повторите попытку."){
    if(e?.stale||g!==state.generation)return;
    if(e?.status===401){clearSession();message("Сессия завершена или отозвана. Войдите снова.",true);return;}
    if(e?.status===403){clearSession();message("Этот кабинет доступен только активному участнику.",true);return;}
    message(text,true);
  }
  function updateCount(){
    const value=$("note-text").value||"",count=Array.from(value).length;
    $("char-count").textContent=count.toLocaleString("ru-RU")+" / 2 000";
    $("save-note").disabled=!state.token||!value.trim()||count>2000||state.busy;
  }
  function el(tag,cls,text){
    const node=document.createElement(tag);if(cls)node.className=cls;if(text!==undefined)node.textContent=text;return node;
  }
  function renderNotes(){
    const root=$("notes");root.replaceChildren();
    for(const note of state.notes){
      const card=el("article","note"),meta=el("div","noteMeta");
      const date=new Date(note.created_at*1000).toLocaleDateString("ru-RU",{day:"numeric",month:"long",year:"numeric"});
      meta.append(el("time","",date),el("span","","Личная запись"));
      const body=el("p","noteBody",note.body),actions=el("div","noteActions");
      const remove=el("button","quiet danger","Удалить");remove.type="button";
      actions.append(remove);card.append(meta,body,actions);root.append(card);
      remove.addEventListener("click",()=>{
        if(state.busy)return;
        if(remove.dataset.confirm!=="yes"){remove.dataset.confirm="yes";remove.textContent="Подтвердить удаление";return;}
        deleteNote(note,remove);
      });
    }
    $("empty-notes").hidden=state.notes.length>0;
    $("shown-count").textContent=state.notes.length?"· "+state.notes.length:"";
    $("load-more").hidden=!state.next;
  }
  function render(data){
    state.account=data.account;state.notes=data.notes?.items||[];state.next=data.notes?.nextBefore||null;
    $("account-name").textContent=data.account.name||"Участник";$("account-email").textContent=data.account.email||"";
    $("editing-account").textContent="Сохраняется только для "+(data.account.email||"текущего аккаунта");
    $("avatar").textContent=(data.account.name||"У").trim().slice(0,2).toLocaleUpperCase("ru-RU");
    $("registration").textContent=data.registration?.status==="confirmed"?"Подтверждена":data.registration?"Запись существует":"Нет подтверждённой регистрации";
    const bookings=$("bookings");bookings.replaceChildren();
    for(const b of data.bookings||[]){
      const row=el("div","booking");row.append(el("strong","",b.item_id),el("span","",b.status||"recorded"));bookings.append(row);
    }
    if(!(data.bookings||[]).length)bookings.append(el("p","fine","Активных записей нет."));
    if(data.bookingsTruncated)bookings.append(el("p","fine","Показаны последние 50 записей."));
    $("signed-out").hidden=true;$("workspace").hidden=false;$("logout").hidden=false;renderNotes();updateCount();
  }
  async function refresh(){
    if(!state.token)return;
    const g=state.generation,data=await request(API);
    if(g!==state.generation)return;render(data);
  }
  $("login-form").addEventListener("submit",async e=>{
    e.preventDefault();
    const email=$("email").value.trim(),password=$("password").value;
    clearSession();
    const g=state.generation;
    $("login-button").disabled=true;message("Проверяем аккаунт…");
    try{
      const data=await request("/api/login",{method:"POST",body:{email,password},anonymous:true});
      if(g!==state.generation)return;
      if(data.role!=="participant"){const err=new Error("forbidden_role");err.status=403;throw err;}
      state.token=data.token;state.account={name:data.name||"",email};
      await refresh();if(g===state.generation)message("");
    }catch(err){if(g===state.generation){clearSession();message(err.status===401?"Проверьте почту и пароль участника.":"Вход не выполнен.",true);}}
    finally{if(g===state.generation)$("login-button").disabled=false;$("password").value="";}
  });
  $("note-text").addEventListener("input",updateCount);
  $("save-note").addEventListener("click",async()=>{
    if(state.busy||!state.token)return;
    const text=$("note-text").value.trim();if(!text||Array.from(text).length>2000)return;
    const g=state.generation;
    if(!state.pending||state.pending.text!==text)state.pending={text,request_id:crypto.randomUUID().replaceAll("-","")};
    state.busy=true;updateCount();$("note-text").readOnly=true;
    try{
      const data=await request(API+"/notes",{method:"POST",body:state.pending});
      if(g!==state.generation)return;
      state.pending=null;$("note-text").value="";
      if(!state.notes.some(n=>n.id===data.note.id))state.notes.unshift(data.note);
      renderNotes();message(data.replayed?"Повтор запроса подтверждён без дубликата.":"Заметка сохранена.");
    }catch(err){fail(err,g,err.status===409?"Этот запрос уже использован с другим содержанием.":"Не удалось подтвердить сохранение. Текст и ключ повторной отправки сохранены в этой вкладке.");}
    finally{if(g===state.generation){state.busy=false;$("note-text").readOnly=false;updateCount();}}
  });
  async function deleteNote(note,button){
    const g=state.generation;state.busy=true;button.disabled=true;updateCount();
    try{
      await request(API+"/notes/delete",{method:"POST",body:{id:note.id}});
      if(g!==state.generation)return;
      state.notes=state.notes.filter(n=>n.id!==note.id);renderNotes();
      message("Текст удалён из текущей базы. Удаление из резервных копий не подтверждено.");
    }catch(err){fail(err,g,"Удаление не подтверждено.");}
    finally{if(g===state.generation){state.busy=false;updateCount();}}
  }
  $("refresh").addEventListener("click",async()=>{
    if(state.busy||!state.token)return;const g=state.generation;
    try{await refresh();if(g===state.generation)message("");}catch(err){fail(err,g);}
  });
  $("load-more").addEventListener("click",async()=>{
    if(!state.next||state.busy)return;const g=state.generation,cursor=state.next;
    try{
      const data=await request(API+"/notes/before/"+encodeURIComponent(cursor));
      if(g!==state.generation)return;
      const ids=new Set(state.notes.map(n=>n.id));state.notes.push(...(data.items||[]).filter(n=>!ids.has(n.id)));
      state.next=data.nextBefore||null;renderNotes();
    }catch(err){fail(err,g);}
  });
  $("logout").addEventListener("click",()=>{clearSession();message("Локальная сессия этой вкладки очищена.");});
  $("logout-all").addEventListener("click",async()=>{
    if(!state.token||state.busy)return;const g=state.generation;state.busy=true;
    try{await request(API+"/logout-all",{method:"POST",body:{}});if(g!==state.generation)return;clearSession();message("Все серверные сессии аккаунта отозваны.");}
    catch(err){if(g===state.generation){state.busy=false;fail(err,g,"Не удалось подтвердить отзыв всех сессий.");}}
  });
  window.addEventListener("pagehide",clearSession);
  document.addEventListener("visibilitychange",()=>{if(document.visibilityState==="visible"&&state.token&&!state.busy){const g=state.generation;refresh().catch(e=>fail(e,g));}});
  setInterval(()=>{if(state.token&&!state.busy){const g=state.generation;refresh().catch(e=>fail(e,g));}},30000);
  updateCount();
})();
