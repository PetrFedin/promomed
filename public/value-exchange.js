"use strict";
(function(){
  const routes={
    participant:{
      kicker:"PARTICIPANT JOURNEY",title:"От интереса к полезному действию",
      description:"Маршрут человека: материал, событие, участие и продолжение. Без диагноза и скрытой передачи данных.",
      status:"DEMO JOURNEY",
      guardrail:"Открытые материалы доступны гостю. Персональные действия и записи требуют отдельной авторизации.",
      steps:[
        {title:"Найти важную тему",description:"Изучить материалы, связанные с интересами, и перейти к научному контексту без индивидуальных медицинских рекомендаций.",state:"Открытый контент",cta:"Открыть материалы",href:"/?screen=media"},
        {title:"Принять участие",description:"Посмотреть программу, выбрать мероприятие, проверить пересечения по времени и доступность записи.",state:"Зависит от авторизации и мест",cta:"Посмотреть программу",href:"/?screen=events"},
        {title:"Вернуться с пользой",description:"Продолжить изучать материалы и свой 1 / 7 / 30-дневный маршрут. Партнёрская коммуникация — только с согласием.",state:"Проверяемый demo-функционал",cta:"Личный маршрут",href:"/?screen=me"}
      ]
    },
    partner:{
      kicker:"PARTNER COLLABORATION",title:"Из спонсорства — в полезный совместный формат",
      description:"Партнёр выбирает аудиторию, контент и форму участия. Отдельные согласия и аналитика помогают оценить результат без доступа к чужим данным.",
      status:"PARTNER PILOT CONCEPT",
      guardrail:"Партнёрские пакеты и пилотные документы демонстрационные. Реальные цены, эксклюзивность, контракты и передачи данных не подтверждены.",
      steps:[
        {title:"Выбрать модель участия",description:"Событие, Studio, образовательный контент или партнёрский опыт. Оценить deliverables и ограничения медицинского обзора.",state:"Пакеты в demo-каталоге",cta:"Форматы сотрудничества",href:"/?screen=commercial"},
        {title:"Спроектировать пилот",description:"Сравнить тип институции, собрать границы пилота, вопросы для первой встречи и перечень свидетельств.",state:"Planning, не контракт",cta:"Commercial Workspace",href:"/institutional-commercial-workspace.html"},
        {title:"Управлять взаимодействием",description:"Проверять записи, добровольные контакты, согласие и операционные события в партнёрском кабинете.",state:"Требует роли и авторизации",cta:"Открыть кабинет",href:"/?screen=partnerDash"}
      ]
    },
    investor:{
      kicker:"INVESTOR VALUE PATH",title:"Не количество экранов. Механика устойчивого бизнеса",
      description:"Проследить продуктовый цикл, проверить сценарную экономику и увидеть критерии следующего инвестиционного решения.",
      status:"EVIDENCE-FIRST",
      guardrail:"Отсутствуют подтверждённые ARR, реальный pipeline и производственная PostgreSQL readiness. Модели допускают только собственные входные данные.",
      steps:[
        {title:"Понять продуктовый цикл",description:"Контент → участник → событие → согласованное взаимодействие → возвращение. Это предполагаемая цепочка создания ценности.",state:"Проверять с реальными когортами",cta:"Investor Proof",href:"/?presentation=investor"},
        {title:"Проверить финансовые допущения",description:"Сценарии доходов, издержек и финансирования: формулы отделены от подтверждённых платежей.",state:"Что-если, не прогноз",cta:"Executive / CVC Room",href:"/?presentation=executive"},
        {title:"Запросить доказательства",description:"Архитектурная готовность, ограничения, safety, evidence export и основания для отдельного институционального пилота.",state:"Готовность ≠ внешнее одобрение",cta:"Evidence Export",href:"/institutional-evidence-export.html"}
      ]
    }
  };
  const root=document.getElementById("role-content");
  if(!root)return;
  const els={kicker:document.getElementById("route-kicker"),title:document.getElementById("route-title"),description:document.getElementById("route-description"),status:document.getElementById("route-status"),steps:document.getElementById("route-steps"),guardrail:document.getElementById("route-guardrail"),copy:document.getElementById("copy-route"),message:document.getElementById("copy-status")};
  const tabs=[...document.querySelectorAll('[role="tab"][data-audience]')];
  let active="participant";
  function render(role,focus){
    if(!Object.prototype.hasOwnProperty.call(routes,role))role="participant";
    active=role;
    const data=routes[role];
    for(const tab of tabs){const selected=tab.dataset.audience===role;tab.setAttribute("aria-selected",String(selected));tab.tabIndex=selected?0:-1;if(selected&&focus)tab.focus()}
    root.setAttribute("aria-labelledby","role-"+role);
    els.kicker.textContent=data.kicker;els.title.textContent=data.title;els.description.textContent=data.description;els.status.textContent=data.status;els.guardrail.textContent=data.guardrail;els.message.textContent="";
    els.steps.replaceChildren();
    for(const [i,step] of data.steps.entries()){
      const article=document.createElement("article");article.className="stepCard";
      const num=document.createElement("span");num.className="stepNumber";num.textContent="ШАГ "+String(i+1).padStart(2,"0");
      const title=document.createElement("h3");title.textContent=step.title;
      const description=document.createElement("p");description.textContent=step.description;
      const state=document.createElement("div");state.className="stepState";state.textContent=step.state;
      const link=document.createElement("a");link.className="stepLink";link.href=step.href;link.textContent=step.cta+" ↗";
      article.append(num,title,description,state,link);els.steps.append(article);
    }
    const url=new URL(location.href);url.searchParams.set("audience",role);history.replaceState(null,"",url.pathname+url.search+url.hash);
  }
  tabs.forEach((tab,index)=>{
    tab.addEventListener("click",()=>render(tab.dataset.audience,false));
    tab.addEventListener("keydown",event=>{
      let next;if(event.key==="ArrowRight")next=(index+1)%tabs.length;else if(event.key==="ArrowLeft")next=(index+tabs.length-1)%tabs.length;else if(event.key==="Home")next=0;else if(event.key==="End")next=tabs.length-1;else return;
      event.preventDefault();render(tabs[next].dataset.audience,true);
    });
  });
  render(new URLSearchParams(location.search).get("audience")||"participant",false);
  els.copy.addEventListener("click",async ()=>{
    const data=routes[active];
    const text=[data.title,data.description,...data.steps.map((x,i)=>(i+1)+". "+x.title+" — "+x.description+" ("+new URL(x.href,location.origin).href+")"),"Ограничения: "+data.guardrail].join("\n");
    try{if(!navigator.clipboard||!navigator.clipboard.writeText)throw new Error("Clipboard unavailable");await navigator.clipboard.writeText(text);els.message.textContent="Маршрут скопирован.";}
    catch(_){const fallback=document.getElementById("copy-fallback");fallback.hidden=false;fallback.value=text;fallback.focus();fallback.select();els.message.textContent="Выделен текст для ручного копирования.";}
  });
  const setText=(id,value)=>{const node=document.getElementById(id);if(node)node.textContent=value};
  async function readJson(path){const c=new AbortController();const timeout=setTimeout(()=>c.abort(),6000);try{const response=await fetch(path,{signal:c.signal,credentials:"omit",cache:"no-store"});if(!response.ok)throw new Error("HTTP "+response.status);return await response.json()}finally{clearTimeout(timeout)}}
  Promise.allSettled([readJson("/health"),readJson("/ready"),readJson("/api/product-quality-proof")]).then(results=>{
    const [health,ready,proof]=results;
    if(health.status==="fulfilled"&&ready.status==="fulfilled"){
      const h=health.value,r=ready.value;
      const prod=r.production_ready===true&&h.backend==="postgres"&&r.backend==="postgres"&&r.durable===true&&r.demo_accounts===0;
      setText("runtime-state",prod?"POSTGRES ADMITTED":h.backend==="sqlite"?"DEMO / SQLITE":"ОГРАНИЧЕН");
      setText("runtime-detail","Backend: "+(h.backend||"неизвестен")+" · production_ready="+String(r.production_ready===true)+" · SHA: "+String(h.git_commit||"unknown").slice(0,12));
    }else{setText("runtime-state","НЕТ ПОДТВЕРЖДЕНИЯ");setText("runtime-detail","Текущий runtime недоступен для проверки. Не делаем вывода о готовности.");}
    if(proof.status==="fulfilled"&&proof.value&&proof.value.counts){
      const counts=proof.value.counts;
      setText("program-count",Number.isInteger(counts.program_items)?counts.program_items.toLocaleString("ru-RU"):"—");
      setText("package-count",Number.isInteger(counts.partner_packages)?counts.partner_packages.toLocaleString("ru-RU"):"—");
      setText("api-proof-message","Каталожные показатели: /api/product-quality-proof. Только demo-структура, не использование.");
    }else setText("api-proof-message","Каталожные данные сейчас не подтверждены. Числовые показатели скрыты.");
  });
  const form=document.getElementById("funnel-form"),fields=["audience","reach","optin","return"],fmt=new Intl.NumberFormat("ru-RU",{maximumFractionDigits:0});
  function update(){
    const values={};let valid=true;
    for(const name of fields){
      const input=document.getElementById(name),raw=input.value.trim(),number=Number(raw),upper=name==="audience"?1e8:100;
      const ok=raw!==""&&Number.isFinite(number)&&number>=0&&number<=upper&&(name!=="audience"||Number.isInteger(number));
      input.setAttribute("aria-invalid",String(!ok&&raw!==""));
      if(!ok)valid=false;values[name]=number;
    }
    const nodes=document.getElementById("funnel-numbers"),message=document.getElementById("funnel-message");
    if(!valid){nodes.hidden=true;message.hidden=false;message.textContent="Для расчёта заполните все четыре поля допустимыми значениями. Пустые поля — не ноль.";return}
    const seen=values.audience*values.reach/100,consent=seen*values.optin/100,repeat=consent*values.return/100;
    for(const [id,value] of [["result-reach",seen],["result-optin",consent],["result-return",repeat]])setText(id,fmt.format(value));
    message.hidden=true;nodes.hidden=false;
  }
  form.addEventListener("input",update);update();
})();
