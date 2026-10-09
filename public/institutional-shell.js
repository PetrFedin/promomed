(function(){
  const pages=[
    {path:'/institutional-commercial-workspace.html',label:'Workspace',stage:'01 · Route'},
    {path:'/institutional-buyer-fit.html',label:'Buyer Fit',stage:'02 · Fit'},
    {path:'/institutional-pilot-proposal.html',label:'Proposal',stage:'03 · Proposal'},
    {path:'/institutional-outreach-pack.html',label:'Outreach',stage:'04 · Meeting'},
    {path:'/institutional-evidence-export.html',label:'Export',stage:'05 · Pack'},
    {path:'/institutional-command-center.html',label:'Command Center',stage:'06 · Diligence'}
  ];
  const main=document.querySelector('main');
  if(main){
    main.id=main.id||'main-content';
    if(!main.hasAttribute('tabindex')) main.setAttribute('tabindex','-1');
    for(const region of main.querySelectorAll('section.panel, section.grid2, section.summary')) region.classList.add('institutionalPerfRegion');
  }
  const skip=document.createElement('a');
  skip.className='institutionalSkipLink';
  skip.href='#main-content';
  skip.textContent='Перейти к основному содержанию';
  skip.addEventListener('click',()=>{setTimeout(()=>main&&main.focus({preventScroll:true}),0)});
  document.body.prepend(skip);
  const current=location.pathname;
  const active=pages.find(x=>x.path===current);
  const nav=document.createElement('nav');
  nav.className='institutionalShellNav';
  nav.setAttribute('aria-label','Institutional commercial navigation');
  nav.innerHTML='<div class="institutionalShellNav__inner">'+
    '<a class="institutionalShellNav__brand" href="/institutional-commercial-workspace.html"><span class="institutionalShellNav__mark">С</span><span>СОСТОЯНИЕ · Institutional</span></a>'+
    '<div class="institutionalShellNav__links">'+pages.map(x=>'<a class="institutionalShellNav__link" href="'+x.path+'"'+(x.path===current?' aria-current="page"':'')+'>'+x.label+'</a>').join('')+'</div>'+
    '</div>';
  const trail=document.createElement('div');
  trail.className='institutionalShellTrail';
  trail.innerHTML='<b>Institutional commercial route</b><span class="institutionalShellCue">'+(active?active.stage:'Planning surface')+'</span><span class="institutionalShellCue">Planning ≠ customer truth</span>';
  document.body.prepend(trail);
  document.body.prepend(nav);
})();