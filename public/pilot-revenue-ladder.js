"use strict";
(() => {
  const STAGES = [
    {id:"pilot_acceptance",title:"01 · Accepted pilot",owner:"Institutional signatory + Governance",state:"GATED",whyBlocked:"Необходимо независимое подтверждение подписи, масштаба и полномочий. Регистрация организации не равна соглашению.",requiredEvidence:["Подтверждённая организация и подписант","Подписанные scope и обязанности","External Participation Acceptance"],target:"/institutional-command-center.html"},
    {id:"contract",title:"02 · Contracted obligations",owner:"Legal + Commercial",state:"GATED",whyBlocked:"Коммерческое предложение и demo Deal Room не являются подписанным договором.",requiredEvidence:["Подписанный договор и существенные условия","Стоимость и валюта договора","Перечень deliverables и приёмочных критериев"],target:"/institutional-pilot-proposal.html"},
    {id:"delivery",title:"03 · Delivered and accepted",owner:"Delivery Owner + External Buyer",state:"GATED",whyBlocked:"Технический ACK поставки контента не подтверждает коммерческую приёмку.",requiredEvidence:["Реестр выполненных обязательств","Независимая приёмка заказчиком","Сверка отказов, кредит-нот и споров"],target:"/institutional-commercial-workspace.html"},
    {id:"invoice",title:"04 · Invoice issued",owner:"Accounts Receivable",state:"GATED",whyBlocked:"Заявка на оплату и инвестиционный транш не являются коммерческим счётом.",requiredEvidence:["Уникальный идентификатор счёта","Привязка к договору и исполнению","Дата, сумма, налоги и корректировки"],target:"/institutional-command-center.html"},
    {id:"cash",title:"05 · Cash received",owner:"Treasury + Finance",state:"GATED",whyBlocked:"Сумма выставленного счёта не равна поступившим деньгам.",requiredEvidence:["Банковская выписка или PSP settlement","Распределение платежа по счёту","Возвраты и chargeback"],target:"/institutional-command-center.html"},
    {id:"finance",title:"06 · Finance acceptance",owner:"Finance Controller",state:"GATED",whyBlocked:"Результат должен быть признан согласно учётной политике, отдельно от поступления денег.",requiredEvidence:["Реестр признания выручки","Фактическая себестоимость deliverables","Сверка скидок, возвратов и двойного учёта","Подтверждение финансового контролёра"],target:"/institutional-evidence-export.html"},
    {id:"renewal",title:"07 · Repeatable contract",owner:"Account Owner + Finance",state:"GATED",whyBlocked:"Повторное посещение или намерение — не продление контракта.",requiredEvidence:["Следующий подписанный период","Ссылка на исходный договор","Фактически признанная выручка от продления"],target:"/institutional-commercial-workspace.html"}
  ];
  const BY_ID = Object.fromEntries(STAGES.map(s => [s.id,s]));
  const IDS = new Set(STAGES.map(s => s.id));
  const allowedTargets = new Set(STAGES.map(s => s.target));
  const metricIds=["metricContract","metricInvoice","metricCash","metricRevenue","metricCost","metricContribution","metricRenewal"];
  let activeStage="pilot_acceptance";
  let token="";
  let proof=null;

  const el=id=>document.getElementById(id);
  const showText=(id,value)=>{const node=el(id);if(node)node.textContent=String(value ?? "—");};
  const setStatus=(value)=>showText("proofStatus",value);
  const validOrg = x => /^[A-Za-z0-9][A-Za-z0-9:_-]{0,99}$/.test(x);

  function selectStage(id) {
    if(!IDS.has(id))return;
    activeStage=id;
    const source=proof?.stages?.find(s => s.id === id);
    // Only local curated content is used for links and labels before
    // authority admission; the response may set status to GATED only.
    const model=BY_ID[id];
    document.querySelectorAll(".stage-control").forEach(button=>{
      const selected=button.dataset.step===id;
      button.classList.toggle("active",selected);
      button.setAttribute("aria-pressed",String(selected));
      button.lastElementChild.textContent="GATED";
    });
    showText("stageTitle",model.title);
    showText("stageBadge","GATED");
    showText("stageOwner",model.owner);
    showText("stageWhy",source?.whyBlocked||model.whyBlocked);
    const ul=el("requiredList");
    const reqs=Array.isArray(source?.requiredEvidence) ? source.requiredEvidence : model.requiredEvidence;
    ul.replaceChildren(...reqs.map(item=>{
      const li=document.createElement("li");
      li.textContent=String(item).slice(0,300);
      return li;
    }));
    const link=el("stageLink");
    link.href=allowedTargets.has(model.target) ? model.target : "/institutional-commercial-workspace.html";
  }

  function clearEvidence() {
    proof=null;
    el("scopedProof").hidden=true;
    metricIds.forEach(id=>showText(id,"—"));
    showText("orgName","—");showText("orgId","—");
    showText("packHash","Evidence-request SHA: —");
    showText("techSignals","—");
    showText("acceptanceStatus","7 / 7 GATED");
    selectStage(activeStage);
  }

  async function request(url, options={}) {
    const response=await fetch(url,{
      ...options,
      credentials:"omit",
      cache:"no-store",
      signal: typeof AbortSignal.timeout === "function" ? AbortSignal.timeout(10000) : undefined,
      headers:{"Accept":"application/json",...(options.headers||{})}
    });
    if(!response.ok) {
      const err=new Error(response.status === 403 ? "FORBIDDEN" :
        response.status === 404 ? "NOT_FOUND" :
        response.status === 401 ? "UNAUTHORIZED" : "UNAVAILABLE");
      throw err;
    }
    return response.json();
  }

  function renderProof(data) {
    if(!data || data.version!=="promomed-pilot-to-revenue-evidence-ladder-v1"
       || data.acceptanceSummary?.capitalReleaseAuthorized!==false
       || data.acceptanceSummary?.financeAccepted!==false
       || data.truthBoundary?.readOnly!==true
       || !Array.isArray(data.stages) || data.stages.length!==STAGES.length
       || new Set(data.stages.map(s => s.id)).size!==STAGES.length
       || data.stages.some(s => !IDS.has(s.id) || s.state!=="GATED")) {
      throw new Error("INVALID_PROOF_BOUNDARY");
    }
    proof=data;
    showText("orgName",data.organization?.name||"—");
    showText("orgId",data.organization?.id||"—");
    showText("orgMode",data.organization?.demoOnly ? "DEMO ORGANIZATION" : "NON-DEMO METADATA ONLY");
    // Zero financial evidence is NOT the same as a confirmed value of 0.
    // Never render money until a separate finance authority is implemented.
    metricIds.forEach(id=>showText(id,"—"));
    const signal=data.sourceSignals||{};
    showText("techSignals","Атрибутируемая non-demo identity metadata: "+
      (signal.nonDemoIdentityMetadata ? "есть (не контракт)" : "не подтверждена")+
      " · Технических acknowledgement: "+(Number.isSafeInteger(signal.technicalEvidenceAcknowledgements)
          ? signal.technicalEvidenceAcknowledgements : "—")+
      " (не коммерческие приёмки)");
    showText("acceptanceStatus",String(data.acceptanceSummary.acceptedStages)+
      " / "+String(data.acceptanceSummary.totalStages)+" ACCEPTED · CAPITAL: HOLD");
    showText("packHash","Evidence-request SHA-256: "+String(data.evidenceRequestPack?.sha256||"—"));
    el("scopedProof").hidden=false;
    selectStage(activeStage);
  }

  async function loginAndLoad(event){
    event.preventDefault();
    clearEvidence();
    const email=el("loginEmail").value.trim();
    const password=el("loginPassword").value;
    const org=el("organizationId").value.trim();
    if(!validOrg(org)){setStatus("Используйте точный Organization ID: латиница, цифры, _, - или двоеточие.");return}
    if(!email || !password){setStatus("Нужен служебный email и пароль организатора.");return}
    const button=el("proofForm").querySelector('button[type="submit"]');
    button.disabled=true;
    try{
      setStatus("Проверка полномочий…");
      const auth=await request("/api/login",{
        method:"POST",headers:{"Content-Type":"application/json"},
        body:JSON.stringify({email,password})
      });
      if(auth.role!=="organizer" || typeof auth.token!=="string" || auth.token.length<16){
        throw new Error("FORBIDDEN");
      }
      token=auth.token;
      el("loginPassword").value="";
      setStatus("Загрузка ограниченного read-only proof…");
      const data=await request("/api/pilot-revenue-ladder/"+encodeURIComponent(org),{
        headers:{"Authorization":"Bearer "+token}
      });
      if(data.organization?.id!==org)throw new Error("INVALID_SCOPE");
      renderProof(data);
      setStatus("Протокол доказательств загружен. Все финансовые этапы остаются GATED.");
    }catch(e){
      token="";
      el("loginPassword").value="";
      clearEvidence();
      setStatus(e.message==="FORBIDDEN"?"Доступ запрещён. Нужна роль organizer.":
        e.message==="NOT_FOUND"?"Организация не найдена в разрешённой области.":
        "Не удалось подтвердить доступ или доказательства. Финансовая приёмка не выполнялась.");
    }finally{button.disabled=false}
  }
  function logout(){
    token="";clearEvidence();el("loginPassword").value="";el("loginEmail").value="";
    el("organizationId").value="";
    setStatus("Доступ очищен. В браузере ничего не сохраняется.");
  }
  function exportRequest(){
    if(!token || !proof?.evidenceRequestPack?.document)return;
    const json=JSON.stringify(proof.evidenceRequestPack,null,2);
    const address=URL.createObjectURL(new Blob([json],{type:"application/json"}));
    const a=document.createElement("a");
    a.href=address;a.download="promomed-pilot-revenue-evidence-request.json";
    document.body.append(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(address),1000);
  }
  document.querySelectorAll(".stage-control").forEach(button=>button.addEventListener("click",()=>selectStage(button.dataset.step)));
  el("proofForm").addEventListener("submit",loginAndLoad);
  el("logoutButton").addEventListener("click",logout);
  el("exportEvidence").addEventListener("click",exportRequest);
  el("printProof").addEventListener("click",()=>window.print());
  selectStage(activeStage);
})();
