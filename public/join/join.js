'use strict';
const state=document.getElementById('inviteState');
const form=document.getElementById('joinForm');
const tokenInput=document.getElementById('inviteToken');
const password=document.getElementById('password');
const confirmInput=document.getElementById('confirm');
const submit=document.getElementById('submit');
const success=document.getElementById('success');
let inviteToken='';
function setState(text,error=false){state.textContent=text;state.classList.toggle('error',error)}
function readFragment(){
  const raw=location.hash.startsWith('#')?location.hash.slice(1):'';
  const p=new URLSearchParams(raw);
  const token=p.get('token')||'';
  history.replaceState(null,'',location.pathname);
  if(/^[A-Za-z0-9_-]{40,128}$/.test(token)){
    inviteToken=token;tokenInput.value=token;setState('Приглашение получено. Задайте новый пароль.');
  }else{
    setState('Введите код из приглашения организатора.',true);
  }
}
function strongEnough(v){
  const classes=[/[a-zа-яё]/.test(v),/[A-ZА-ЯЁ]/.test(v),/[0-9]/.test(v),/[^A-Za-zА-Яа-яЁё0-9]/.test(v)];
  return v.length>=14&&v.length<=256&&classes.filter(Boolean).length>=3;
}
form.addEventListener('submit',async e=>{
  e.preventDefault();
  const token=(tokenInput.value||'').trim();
  if(!/^[A-Za-z0-9_-]{40,128}$/.test(token)){setState('Код приглашения имеет неверный формат.',true);return}
  if(!strongEnough(password.value)){setState('Пароль не соответствует требованиям.',true);return}
  if(password.value!==confirmInput.value){setState('Пароли не совпадают.',true);return}
  submit.disabled=true;setState('Активируем приглашение…');
  try{
    const r=await fetch('/api/participant-invite/accept',{
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body:JSON.stringify({token,password:password.value}),
      cache:'no-store',
      credentials:'same-origin'
    });
    let data={};try{data=await r.json()}catch{}
    if(!r.ok)throw Object.assign(new Error(data.error||('HTTP '+r.status)),{status:r.status});
    inviteToken='';tokenInput.value='';password.value='';confirmInput.value='';
    form.hidden=true;state.hidden=true;success.hidden=false;
  }catch(err){
    const text=err.status===404?'Приглашение недействительно, истекло или уже использовано.':
      err.status===409?'Аккаунт для этого приглашения уже существует.':
      err.status===422?'Проверьте код и требования к паролю.':
      'Не удалось активировать приглашение. Повторите попытку.';
    setState(text,true);submit.disabled=false;
  }
});
window.addEventListener('pagehide',()=>{inviteToken='';tokenInput.value='';password.value='';confirmInput.value=''});
readFragment();
