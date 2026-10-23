(()=>{
  'use strict';
  const $=id=>document.getElementById(id),APPT='/api/partner-appointments/v1',COMM='/api/partner-commercial/v1';
  const state={token:null,role:null,generation:0,read:0,busy:false,organizations:[],appointments:[]};
  const labels={planned:'Планируется',enabled:'Включено',paused:'Приостановлено',ended:'Завершено',open:'Открыта',closed:'Запись закрыта',cancelled:'Отменена'};
  function el(tag,text){const node=document.createElement(tag);if(text!==undefined)node.textContent=text;return node;}
  function notice(text='',error=false){$('notice').textContent=text;$('notice').hidden=!text;$('notice').classList.toggle('error',error);}
  function clear(){state.generation++;state.read++;state.token=null;state.role=null;state.busy=false;state.organizations=[];state.appointments=[];$('workspace').hidden=true;$('logout').hidden=true;$('login-form').hidden=false;$('password').value='';$('organization').replaceChildren();$('owner-metrics').replaceChildren();$('slots').replaceChildren();$('leads').replaceChildren();$('owner-data').hidden=true;$('partner-data').hidden=true;}
  async function request(url,body){
    const g=state.generation,controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
    try{const response=await fetch(url,{method:body?'POST':'GET',headers:{...(state.token?{Authorization:'Bearer '+state.token}:{}),...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,credentials:'omit',cache:'no-store',signal:controller.signal});
      const data=await response.json();if(g!==state.generation)throw Object.assign(new Error('stale'),{stale:true});
      if(!response.ok)throw Object.assign(new Error(data.error),{status:response.status});return data;
    }finally{clearTimeout(timer);}
  }
  function fail(e){if(e.stale)return;if(e.status===401||e.status===403){clear();notice('Доступ завершён или отозван. Войдите заново.',true);}else notice(e.status===409?'Данные изменились. Обновите кабинет перед повторной попыткой.':'Операция не подтверждена. Обновите данные и проверьте результат.',true);}
  function controls(){for(const button of $('workspace').querySelectorAll('button'))button.disabled=state.busy||button.dataset.locked==='yes';}
  async function mutate(url,body){if(state.busy)return;const g=state.generation;state.busy=true;controls();try{await request(url,body);if(g!==state.generation)return;try{await refresh();notice('Изменения сохранены.');}catch(e){if(!e.stale)notice('Сервер сохранил изменение, но обновить кабинет не удалось. Проверьте данные перед повторной отправкой.',true);}}catch(e){fail(e);}finally{if(g===state.generation){state.busy=false;controls();}}}
  function selected(){return state.organizations.find(x=>x.organizationId===$('organization').value);}
  function render(){
    const org=selected();$('partner-data').hidden=!org;$('slots').replaceChildren();$('leads').replaceChildren();
    if(!org)return;
    $('placement-state').textContent=labels[org.placement?.status]||'Размещение ещё не создано';$('placement-status').value=org.placement?.status||'planned';
    $('invitation-code').textContent=org.organizationId;$('invitation-link').href='/personal/?partner='+encodeURIComponent(org.organizationId);
    const data=state.appointments.find(x=>x.organizationId===org.organizationId);
    if(data?.slotsTruncated)$('slots').append(el('p','Показаны первые 200 встреч; сводка организатора считает все записи.'));
    if(!data?.slots.length)$('slots').append(el('p','Встреч пока нет.'));
    for(const slot of data?.slots||[]){
      const card=el('article');card.className='partnerSlot';card.dataset.slot=slot.id;
      card.append(el('h3',new Date(slot.starts_at*1000).toLocaleString('ru-RU')+' — '+new Date(slot.ends_at*1000).toLocaleString('ru-RU')),el('p',labels[slot.status]));
      const count=el('p','Подтверждено: '+slot.counts.booked+' · Ожидают: '+slot.counts.waitlist+' · Свободно: '+slot.counts.available);count.className='slotCounts';card.append(count);
      if(slot.counts.overCapacity)card.append(el('p','Превышение вместимости: '+slot.counts.overCapacity));
      const form=el('form');form.className='slotControls';const label=el('label','Мест'),capacity=el('input');capacity.type='number';capacity.min='1';capacity.max='1000';capacity.step='1';capacity.required=true;capacity.value=slot.capacity;label.append(capacity);
      const save=el('button','Сохранить места');save.className='outline';form.append(label,save);card.append(form);
      function change(status){if(status==='cancelled'&&!window.confirm('Отменить встречу для всех записанных участников?'))return;mutate(APPT,{action:'slot_update',slot_id:slot.id,expected_version:slot.version,starts_at:slot.starts_at,ends_at:slot.ends_at,capacity:Number(capacity.value),status});}
      form.addEventListener('submit',e=>{e.preventDefault();change(slot.status);});
      if(slot.status!=='cancelled')for(const [status,text] of [[slot.status==='open'?'closed':'open',slot.status==='open'?'Закрыть запись':'Открыть запись'],['cancelled','Отменить встречу']]){const button=el('button',text);button.type='button';button.className='outline';button.addEventListener('click',()=>change(status));card.append(button);}
      else {save.disabled=true;save.dataset.locked='yes';}
      for(const booking of slot.bookings){const row=el('p',booking.email+' · '+(booking.status==='booked'?'Место подтверждено':'Лист ожидания'));row.className='contactRow';card.append(row);}
      if(slot.bookingsTruncated)card.append(el('p','Показаны первые 500 контактов. Счётчики рассчитаны по всем записям.'));
      $('slots').append(card);
    }
    $('lead-count').textContent='Активных заявок: '+org.activeLeadCount;
    for(const lead of org.leads){const row=el('p',lead.email+' · '+lead.kind);row.className='contactRow';$('leads').append(row);}
    if(org.leadsTruncated)$('leads').append(el('p','Показаны первые 200 заявок; счётчик учитывает все активные.'));
  }
  async function refresh(){
    if(!state.token)return;const sequence=++state.read;
    if(state.role==='organizer'){
      const org=$('owner-organization').value.trim();if(!org)return;
      $('owner-data').hidden=true;$('owner-metrics').replaceChildren();
      const data=await request('/api/organization-operations/v1?organization_id='+encodeURIComponent(org));
      if(sequence!==state.read||org!==$('owner-organization').value.trim())return;
      $('owner-title').textContent=data.organization.name;$('owner-data').hidden=false;
      const names={upcomingSlots:'Текущие и будущие встречи',capacity:'Вместимость',booked:'Подтверждённые записи',unavailableBookings:'Записи недоступного размещения',waitlist:'Очередь',activeLeads:'Активные заявки',occupancyPercent:'Заполненность, %'};
      for(const [key,label] of Object.entries(names)){const metric=el('div');metric.append(el('span',label),el('strong',data.metrics[key]===null?'Не рассчитано':String(data.metrics[key])));$('owner-metrics').append(metric);}
      $('as-of').textContent='На '+new Date(data.asOf*1000).toLocaleString('ru-RU')+' · Размещение: '+(labels[data.placementStatus]||'Не создано');return;
    }
    const [commercial,appointments]=await Promise.all([request(COMM),request(APPT)]);if(sequence!==state.read)return;
    const previous=$('organization').value;state.appointments=appointments.organizations;
    state.organizations=commercial.organizations.filter(x=>state.appointments.some(y=>x.organizationId===y.organizationId));
    $('organization').replaceChildren();for(const org of state.organizations){const option=el('option',org.organizationName);option.value=org.organizationId;$('organization').append(option);}
    if(state.organizations.some(x=>x.organizationId===previous))$('organization').value=previous;
    render();$('as-of').textContent='Обновлено '+new Date().toLocaleString('ru-RU');
    if(!state.organizations.length)notice('Нет организаций с действующими подтверждёнными полномочиями.');
  }
  $('login-form').addEventListener('submit',async e=>{e.preventDefault();const email=$('email').value.trim(),password=$('password').value;clear();const g=state.generation;$('login').disabled=true;try{const data=await request('/api/login',{email,password});if(!['partner','organizer'].includes(data.role))throw Object.assign(new Error('forbidden'),{status:403});state.token=data.token;state.role=data.role;$('login-form').hidden=true;$('workspace').hidden=false;$('logout').hidden=false;$('partner-selector').hidden=data.role!=='partner';$('owner-form').hidden=data.role!=='organizer';await refresh();}catch(e){fail(e);}finally{if(g===state.generation)$('login').disabled=false;$('password').value='';}});
  $('organization').addEventListener('change',render);
  $('refresh').addEventListener('click',()=>refresh().catch(fail));
  $('owner-form').addEventListener('submit',e=>{e.preventDefault();refresh().catch(fail);});
  $('placement-form').addEventListener('submit',e=>{e.preventDefault();const org=selected();if(!org)return;const status=$('placement-status').value;if(status==='ended'&&!window.confirm('Завершить размещение? Оно станет недоступно участникам.'))return;mutate(COMM,{action:'placement_update',organization_id:org.organizationId,status,expected_version:org.placement?.version||0});});
  $('slot-form').addEventListener('submit',e=>{e.preventDefault();const org=selected();if(!org)return;const starts=Math.floor(new Date($('starts').value).getTime()/1000),ends=Math.floor(new Date($('ends').value).getTime()/1000);if(!Number.isFinite(starts)||ends<=starts){notice('Проверьте начало и окончание встречи.',true);return;}mutate(APPT,{action:'slot_create',organization_id:org.organizationId,starts_at:starts,ends_at:ends,capacity:Number($('capacity').value)});});
  $('timezone').textContent='Часовой пояс устройства: '+Intl.DateTimeFormat().resolvedOptions().timeZone;
  $('logout').addEventListener('click',()=>{clear();notice('Вы вышли из кабинета.');});window.addEventListener('pagehide',clear);
})();
