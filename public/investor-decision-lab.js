"use strict";
(() => {
  const CASES = ["conservative", "base", "optimistic"];
  const FIELDS = ["clients", "feeAnnual", "events", "eventFee", "variablePct", "fixedCost", "investment"];
  const INTEGER = new Set(["clients", "events"]);
  const LIMITS = {clients:100000,feeAnnual:1e11,events:100000,eventFee:1e11,variablePct:100,fixedCost:1e12,investment:1e12};
  const scenarios = Object.fromEntries(CASES.map(k => [k, Object.fromEntries(FIELDS.map(f => [f, ""]))]));
  const rub = x => Number.isFinite(x) ? new Intl.NumberFormat("ru-RU", {maximumFractionDigits:0}).format(Math.round(x)) + " ₽" : "—";
  const text = (id, value) => { const node = document.getElementById(id); if(node) node.textContent = value; };
  let active = "base";

  function validNumber(field, raw) {
    if(raw.trim() === "") return null;
    const n = Number(raw);
    if(!Number.isFinite(n) || n < 0 || n > LIMITS[field] || (INTEGER.has(field) && !Number.isSafeInteger(n))) return null;
    return n;
  }
  function calculate(input) {
    const values = {};
    for(const key of FIELDS) {
      const n = validNumber(key, String(input[key] ?? ""));
      if(n === null) return null;
      values[key] = n;
    }
    const {clients, feeAnnual, events, eventFee, variablePct, fixedCost, investment} = values;
    const eventRevenue = events * eventFee;
    const revenue = clients * feeAnnual + eventRevenue;
    const contributionRate = 1 - variablePct / 100;
    const operating = revenue * contributionRate - fixedCost;
    if(![revenue, operating, contributionRate].every(Number.isFinite)) return null;
    const margin = revenue > 0 ? (operating / revenue) * 100 : null;
    let breakEven;
    if(contributionRate <= 0 || feeAnnual <= 0) {
      breakEven = operating >= 0 ? 0 : null;
    } else {
      const needed = (fixedCost / contributionRate - eventRevenue) / feeAnnual;
      breakEven = Number.isFinite(needed) ? Math.max(0, Math.ceil(needed - 1e-10)) : null;
    }
    const payback = operating > 0 ? investment / operating * 12 : null;
    return {revenue, operating, margin, breakEven, payback, inputs:values};
  }
  function storeActive() {
    FIELDS.forEach(f => { scenarios[active][f] = document.getElementById(f).value; });
  }
  function render() {
    storeActive();
    const selected = calculate(scenarios[active]);
    text("scenarioMessage", selected ? "Расчёт построен только на введённых параметрах. Он не подтверждает спрос, цены, ROI или контракты." : "Заполните все семь полей числами в допустимых диапазонах. Пустое поле не означает ноль.");
    text("metricRevenue", selected ? rub(selected.revenue) : "—");
    text("metricOperating", selected ? rub(selected.operating) : "—");
    text("metricMargin", selected && selected.margin !== null ? selected.margin.toFixed(1) + " %" : "—");
    text("metricBreakeven", selected ? (selected.breakEven === null ? "Нет решения" : selected.breakEven.toLocaleString("ru-RU")) : "—");
    text("metricPayback", selected ? (selected.payback === null ? "Не окупается в модели" : selected.payback.toFixed(1) + " мес.") : "—");
    FIELDS.forEach(k => {
      const el = document.getElementById(k);
      el.setAttribute("aria-invalid", el.value.trim() !== "" && validNumber(k, el.value) === null ? "true" : "false");
    });
    let hasExport = false;
    CASES.forEach(k => {
      const value = calculate(scenarios[k]);
      hasExport ||= !!value;
      const label = document.querySelector('[data-case-value="'+k+'"]');
      const status = document.querySelector('[data-case-status="'+k+'"]');
      if(label) label.textContent = value ? rub(value.operating) : "—";
      if(status) status.textContent = value ? "Пользовательская гипотеза" : "Нет данных";
    });
    document.getElementById("downloadCsv").disabled = !hasExport;
  }
  function selectScenario(name) {
    if(!CASES.includes(name)) return;
    storeActive();
    active = name;
    FIELDS.forEach(f => document.getElementById(f).value = scenarios[active][f]);
    document.querySelectorAll("[data-scenario]").forEach(btn => {
      const on = btn.dataset.scenario === active;
      btn.classList.toggle("active", on);
      btn.setAttribute("aria-pressed", String(on));
    });
    render();
  }

  const stages = {
    product: {status:"CODE / DEMO · NOT PRODUCTION",title:"Взаимодействие с продуктом",description:"От медиа и тематических маршрутов до программы мероприятия и Studio. Проверяем реальные переходы, не выдавая демонстрационный каталог за аудиторию.",url:"/",label:"Открыть продукт",owner:"Product / Engineering",checks:["Участник проходит ключевой путь без разрыва контекста","UI проверен на телефоне, планшете и компьютере","Версия приложения подтверждается точным Git SHA"]},
    pilot: {status:"PILOT PLANNING · EXTERNAL ACCEPTANCE GATED",title:"Согласовать ограниченный пилот",description:"Buyer Fit → Pilot Proposal → реальные владельцы KPI, сроки, обязанности и согласование данных. Предложение не равно договору.",url:"/institutional-pilot-proposal.html",label:"Открыть Proposal Studio",owner:"Institutional Buyer / Commercial",checks:["Определены юридическое лицо и ответственное лицо","Подписаны scope, privacy и метрики до начала исполнения","Зафиксированы baseline и критерии GO / ITERATE / STOP"]},
    delivery: {status:"DEMO EVIDENCE · REAL DELIVERY GATED",title:"От обещания до доставки ценности",description:"Партнёр получает измеримый deliverable, который связывается с фактом исполнения и подтверждением. Demo-ACK не является внешним принятием.",url:"/institutional-commercial-workspace.html",label:"Открыть Partner Workspace",owner:"Delivery Owner / Partner",checks:["Раздельные consent и tenant scope","Сверены deliverables и фактическая приёмка","Существует независимое подтверждение от партнёра"]},
    finance: {status:"SCENARIO ONLY · NO FINANCE ACCEPTANCE",title:"Сверить деньги, а не просмотры",description:"Модель, себестоимость, подписанные исходные данные, признанная выручка и исключение двойного счёта — разные сущности.",url:"#scenarioLab",label:"Исследовать модель",owner:"Finance / Procurement",checks:["Finance принимает базу сравнения и источники","Перекрывающиеся эффекты исключены","Отдельно учтены реальные затраты и cashflow"]},
    capital: {status:"COMMITTEE DECISION · NOT APPROVED",title:"Разрешать транш только после доказательства",description:"Объём и очередность финансирования зависят от подтверждённых результатов пилота и отдельного решения инвесткомитета.",url:"/institutional-command-center.html",label:"Открыть Command Center",owner:"Investment Committee / Security",checks:["Phase 0 и governance допущены","Внешнее участие и Finance acceptance зафиксированы","GO / ITERATE / STOP оформлено ответственными лицами"]}
  };
  function selectStage(name) {
    const stage = stages[name]; if(!stage) return;
    document.querySelectorAll("[data-stage]").forEach(btn => {
      const on = btn.dataset.stage === name;
      btn.classList.toggle("selected",on); btn.setAttribute("aria-pressed",String(on));
    });
    text("stageStatus",stage.status);
    text("stageTitle",stage.title);
    text("stageDescription",stage.description);
    text("stageOwner","Ответственный: " + stage.owner);
    const link = document.getElementById("stageLink");
    link.href = stage.url;
    link.firstChild.textContent = stage.label + " ";
    const ul = document.getElementById("stageChecklist");
    ul.replaceChildren(...stage.checks.map(t => {const li=document.createElement("li");li.textContent=t;return li;}));
  }
  function csvExport() {
    const rows = [["scenario",...FIELDS,"revenue_rub","operating_rub","margin_pct","break_even_clients","payback_months"]];
    CASES.forEach(k => {
      const v=calculate(scenarios[k]); if(!v)return;
      rows.push([k,...FIELDS.map(x=>v.inputs[x]),v.revenue,v.operating,v.margin??"",v.breakEven??"",v.payback??""]);
    });
    if(rows.length === 1)return;
    const csv="\ufeff"+rows.map(row=>row.map(x => '"'+String(x).replaceAll('"','""')+'"').join(";")).join("\r\n");
    const url=URL.createObjectURL(new Blob([csv],{type:"text/csv;charset=utf-8"}));
    const a=document.createElement("a");a.href=url;a.download="sostoyanie-investor-scenarios.csv";document.body.append(a);a.click();a.remove();URL.revokeObjectURL(url);
  }
  async function loadProof() {
    const timeout=AbortSignal.timeout ? AbortSignal.timeout(7000) : undefined;
    async function get(path) {
      const res=await fetch(path,{cache:"no-store",credentials:"omit",signal:timeout});
      if(!res.ok) throw new Error("status "+res.status);
      return res.json();
    }
    const results=await Promise.allSettled([get("/health"),get("/ready"),get("/api/product-quality-proof")]);
    const health=results[0].status==="fulfilled" ? results[0].value : null;
    const ready=results[1].status==="fulfilled" ? results[1].value : null;
    const catalog=results[2].status==="fulfilled" ? results[2].value : null;
    text("liveProgram",Number.isFinite(catalog?.counts?.program_items) ? String(catalog.counts.program_items) : "—");
    text("liveMedia",Number.isFinite(catalog?.counts?.materials) ? String(catalog.counts.materials) : "—");
    text("livePackages",Number.isFinite(catalog?.counts?.partner_packages) ? String(catalog.counts.partner_packages) : "—");
    const sha=typeof health?.git_commit==="string" ? health.git_commit : "";
    text("liveSha",sha && sha!=="local" ? sha.slice(0,12)+"…" : "Не подтверждён");
    const production=health?.backend==="postgres" && ready?.production_ready===true;
    text("runtimeStatus",production ? "REPORTED PRODUCTION READY · VERIFY EXTERNALLY" : "DEMO / NO PRODUCTION PROOF");
    text("runtimeNote",production ? "Readiness endpoint reports PostgreSQL. Independent restore/admission still required." : "Production readiness не подтверждена; live SHA должен сверяться с GitHub");
  }
  document.querySelectorAll("[data-stage]").forEach(b=>b.addEventListener("click",()=>selectStage(b.dataset.stage)));
  document.querySelectorAll("[data-scenario]").forEach(b=>b.addEventListener("click",()=>selectScenario(b.dataset.scenario)));
  FIELDS.forEach(f=>document.getElementById(f).addEventListener("input",render));
  document.getElementById("scenarioForm").addEventListener("submit",e=>e.preventDefault());
  document.getElementById("downloadCsv").addEventListener("click",csvExport);
  render();
  loadProof();
})();
