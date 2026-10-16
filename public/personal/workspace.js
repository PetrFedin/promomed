(() => {
  "use strict";
  const API="/api/my-state/v1";
  const EVENT_API="/api/event-registration/v1";
  const PARTNER_APPT="/api/partner-appointments/v1";
  const PARTNER_LEAD="/api/partner-commercial/v1";
  const REG_REQUEST="/api/participant-registration/v1/request";
  const REG_VERIFY="/api/participant-registration/v1/verify";
  const $=id=>document.getElementById(id);
  const state={token:null,account:null,generation:0,controllers:new Set(),notes:[],next:null,pending:null,busy:false,authBusy:false,eventBusy:false,partnerBusy:false,registration:null,eventEditions:[]};

  function message(text="",error=false){
    const n=$("notice");n.hidden=!text;n.textContent=text;n.classList.toggle("error",!!error);
  }
  function abortAll(){for(const c of state.controllers)c.abort();state.controllers.clear();}
  function showAuthMode(mode){
    const login=mode==="login",verify=mode==="verify";
    $("login-form").hidden=!login;
    $("signup-form").hidden=login||verify;
    $("verify-form").hidden=!verify;
    $("mode-login").classList.toggle("active",login);
    $("mode-signup").classList.toggle("active",!login);
    $("mode-login").setAttribute("aria-selected",String(login));
    $("mode-signup").setAttribute("aria-selected",String(!login));
    if(!verify){$("demo-code").hidden=true;$("demo-code").textContent="";}
  }
  function changeAuthMode(mode){
    state.generation++;abortAll();state.registration=null;state.authBusy=false;
    $("verify-code").value="";$("signup-password").value="";
    showAuthMode(mode);message("");
  }
  function clearSession(){
    state.generation++;abortAll();state.token=null;state.account=null;state.notes=[];state.next=null;state.pending=null;state.busy=false;state.authBusy=false;state.eventBusy=false;state.partnerBusy=false;state.registration=null;state.eventEditions=[];
    $("workspace").hidden=true;$("signed-out").hidden=false;$("logout").hidden=true;
    $("login-button").disabled=false;$("signup-button").disabled=false;$("verify-button").disabled=false;$("save-note").disabled=true;$("logout-all").disabled=false;
    $("password").value="";$("signup-name").value="";$("signup-email").value="";$("signup-password").value="";$("verify-code").value="";$("verify-email").textContent="";$("note-text").value="";$("notes").replaceChildren();$("bookings").replaceChildren();$("event-registration-list").replaceChildren();$("partner-appointments").replaceChildren();$("partner-leads").replaceChildren();
    showAuthMode("login");updateCount();
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
    const bookings=$("bookings");bookings.replaceChildren();
    for(const b of data.bookings||[]){
      const row=el("div","booking");row.append(el("strong","",b.item_id),el("span","",b.status||"recorded"));bookings.append(row);
    }
    if(!(data.bookings||[]).length)bookings.append(el("p","fine","Активных записей нет."));
    if(data.bookingsTruncated)bookings.append(el("p","fine","Показаны последние 50 записей."));
    $("signed-out").hidden=true;$("workspace").hidden=false;$("logout").hidden=false;renderNotes();updateCount();
  }
  function renderEventRegistrations(data){
    const root=$("event-registration-list");root.replaceChildren();
    state.eventEditions=data.events||[];
    if(!state.eventEditions.length){
      root.append(el("p","fine","Открытых событий пока нет."));
      return;
    }
    const labels={confirmed:"Место подтверждено",waitlist:"Лист ожидания",cancelled:"Регистрация отменена"};
    for(const event of state.eventEditions){
      const card=el("article","eventRegistration"),head=el("div","eventRegistrationHead");
      const info=el("div",""),title=el("strong","",event.eventTitle||event.eventId);
      const date=event.startsAt?new Date(event.startsAt*1000).toLocaleString("ru-RU",{day:"numeric",month:"long",hour:"2-digit",minute:"2-digit"}):"Дата уточняется";
      info.append(title,el("span","fine",date));
      const status=el("span","eventStatus "+(event.myStatus||"none"),labels[event.myStatus]||"Не зарегистрирован");
      head.append(info,status);card.append(head);
      const action=el("button","outline eventAction");
      action.type="button";action.dataset.eventId=event.eventId;
      if(event.myStatus==="confirmed"||event.myStatus==="waitlist"){
        action.textContent="Отменить регистрацию";action.dataset.action="cancel";
      }else if(event.registrationStatus==="open"){
        action.textContent="Зарегистрироваться";action.dataset.action="register";
      }else if(event.registrationStatus==="waitlist_only"){
        action.textContent="Встать в лист ожидания";action.dataset.action="register";
      }else{
        action.textContent="Регистрация закрыта";action.disabled=true;
      }
      if(state.eventBusy)action.disabled=true;
      action.addEventListener("click",()=>changeEventRegistration(event,action));
      card.append(action);root.append(card);
    }
  }
  async function changeEventRegistration(event,button){
    if(state.eventBusy||!state.token)return;
    const g=state.generation,action=button.dataset.action;
    state.eventBusy=true;button.disabled=true;
    try{
      const result=await request(EVENT_API,{method:"POST",body:{event_id:event.eventId,action}});
      if(g!==state.generation)return;
      const status=result.registration?.status;
      message(action==="cancel"?"Регистрация отменена.":status==="confirmed"?"Место подтверждено.":"Вы добавлены в лист ожидания.");
      state.eventBusy=false;
      await refresh();
    }catch(err){
      fail(err,g,err.status===409?"Регистрация на это событие закрыта.":"Не удалось изменить регистрацию.");
    }finally{
      if(g===state.generation)state.eventBusy=false;
    }
  }
  function renderPartnerRows(target,items,kind){
    const root=$(target);root.replaceChildren();
    if(!items.length){root.append(el("p","fine",kind==="appointment"?"Встреч пока нет.":"Заявок пока нет."));return;}
    for(const item of items){
      const card=el("div","partnerRecord");
      const status=item.status||"";
      if(kind==="appointment"){
        const name=item.organization_name||item.organization_id||"Партнёр";
        const stamp=item.starts_at?new Date(item.starts_at*1000).toLocaleString("ru-RU"):"";
        card.append(el("strong","",name),el("span","fine",stamp),el("span","",status==="booked"?"Место подтверждено":status==="waitlist"?"Лист ожидания":"Отменено"));
      }else{
        card.append(el("strong","",item.kind||"Заявка"),el("span","fine","Организация: "+(item.organization_id||"")),el("span","",status==="submitted"?"Контакт передан":"Согласие отозвано"));
      }
      if((kind==="appointment"&&["booked","waitlist"].includes(status))||(kind==="lead"&&status==="submitted")){
        const button=el("button","outline",kind==="appointment"?"Отменить встречу":"Отозвать заявку");
        button.type="button";button.disabled=state.partnerBusy;
        button.addEventListener("click",()=>changePartnerRecord(kind,item,button));
        card.append(button);
      }
      root.append(card);
    }
  }
  async function changePartnerRecord(kind,item,button){
    if(state.partnerBusy||!state.token)return;
    const generation=state.generation;state.partnerBusy=true;button.disabled=true;
    const appointment=kind==="appointment";
    try{
      await request(appointment?PARTNER_APPT:PARTNER_LEAD,{method:"POST",body:appointment
        ?{action:"cancel",slot_id:item.slot_id}:{action:"lead_withdraw",lead_id:item.id}});
      if(generation!==state.generation)return;
      message(appointment?"Встреча отменена.":"Заявка отозвана.");
      await refresh();
    }catch(e){fail(e,generation,"Изменение не подтверждено. Обновите данные и проверьте статус.");}
    finally{if(generation===state.generation){state.partnerBusy=false;button.disabled=false;}}
  }
  async function refreshPartner(){
    const generation=state.generation;
    const responses=await Promise.allSettled([request(PARTNER_APPT),request(PARTNER_LEAD)]);
    if(generation!==state.generation||!state.token)return;
    const targets=[["partner-appointments","myAppointments","appointment"],["partner-leads","myLeads","lead"]];
    for(let i=0;i<targets.length;i++){
      const [id,key,kind]=targets[i],result=responses[i];
      if(result.status==="fulfilled"){renderPartnerRows(id,result.value[key]||[],kind);}
      else if(!result.reason?.stale){
        if(result.reason?.status===401||result.reason?.status===403){fail(result.reason,generation);return;}
        const root=$(id);root.replaceChildren(el("p","fine","Данные временно недоступны. Повторите обновление."));
      }
    }
  }
  async function refresh(){
    if(!state.token)return;
    const g=state.generation;
    const [data,eventData]=await Promise.all([request(API),request(EVENT_API)]);
    if(g!==state.generation)return;render(data);renderEventRegistrations(eventData);
    await refreshPartner();
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
  $("mode-login").addEventListener("click",()=>changeAuthMode("login"));
  $("mode-signup").addEventListener("click",()=>changeAuthMode("signup"));
  $("change-registration-email").addEventListener("click",()=>changeAuthMode("signup"));

  $("signup-form").addEventListener("submit",async e=>{
    e.preventDefault();if(state.authBusy)return;
    const name=$("signup-name").value.trim(),email=$("signup-email").value.trim(),password=$("signup-password").value;
    const g=state.generation;state.authBusy=true;$("signup-button").disabled=true;message("Отправляем код подтверждения…");
    try{
      const data=await request(REG_REQUEST,{method:"POST",body:{email,name,password},anonymous:true});
      if(g!==state.generation)return;
      state.registration={requestId:data.requestId,email};
      $("verify-email").textContent="Код отправлен на "+email;
      $("signup-password").value="";$("verify-code").value="";
      showAuthMode("verify");
      if(data.demoOnly&&data.demoVerificationCode){
        $("demo-code").textContent="DEMO ONLY · код: "+data.demoVerificationCode;
        $("demo-code").hidden=false;
      }
      message("Проверьте почту и введите шестизначный код.");
      $("verify-code").focus();
    }catch(err){
      if(g!==state.generation||err?.stale)return;
      const text=err.status===503
        ?"Регистрация пока недоступна: канал подтверждения email не настроен или временно не отвечает."
        :"Проверьте имя, email и требования к паролю.";
      message(text,true);
    }finally{
      if(g===state.generation){state.authBusy=false;$("signup-button").disabled=false;$("signup-password").value="";}
    }
  });

  $("verify-form").addEventListener("submit",async e=>{
    e.preventDefault();if(state.authBusy||!state.registration)return;
    const code=$("verify-code").value.trim();
    if(!/^[0-9]{6}$/.test(code)){message("Введите шестизначный код из письма.",true);return;}
    const g=state.generation;state.authBusy=true;$("verify-button").disabled=true;message("Подтверждаем email…");
    try{
      const data=await request(REG_VERIFY,{method:"POST",body:{request_id:state.registration.requestId,code},anonymous:true});
      if(g!==state.generation)return;
      if(data.role!=="participant"||!data.token){throw Object.assign(new Error("invalid_registration_session"),{status:403});}
      state.token=data.token;state.account={name:data.name||"",email:state.registration.email};state.registration=null;
      $("verify-code").value="";$("signup-name").value="";$("signup-email").value="";
      await refresh();
      if(g===state.generation)message(data.eventRegistration?"Аккаунт создан.":"Аккаунт создан. Регистрация на мероприятие выполняется отдельно.");
    }catch(err){
      if(g!==state.generation||err?.stale)return;
      message(err.status===422?"Код неверен, истёк или число попыток исчерпано.":"Не удалось подтвердить регистрацию.",true);
    }finally{
      if(g===state.generation){state.authBusy=false;$("verify-button").disabled=false;}
    }
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
  showAuthMode("login");updateCount();
})();
