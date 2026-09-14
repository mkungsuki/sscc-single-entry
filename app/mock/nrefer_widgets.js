// DOM contract fixture based on the observed UI. This is not the Angular component.
const dx = document.querySelector('select[name="editRow.dx"]');
Array.from(dx.options).filter(o=>o.value==='G45').forEach(o=>o.remove());
const group = document.querySelector('select[name="editRow.dmis"]');
group.disabled=true;
dx.onchange=()=>{
 document.querySelector('input[name="editRow.dx"]').value=dx.value;
 group.value=['I60','I61','I62'].includes(dx.value)?'1':'2';
};
document.querySelector('input[name="editRow.gcs"]').readOnly=true;
// Model observed keyboard-sensitive recalculation, not the Angular implementation.
const gcsParts=['gcs_eye','gcs_verbal','gcs_motor'].map(k=>document.querySelector('input[name="editRow.'+k+'"]'));
gcsParts.forEach(el=>el.addEventListener('keyup',event=>{
 if(!/^[0-9]$/.test(event.key)&&!['Backspace','Delete'].includes(event.key))return;
 document.querySelector('input[name="editRow.gcs"]').value=String(gcsParts.reduce((sum,p)=>sum+Number(p.value||0),0));
}));
if(new URLSearchParams(location.search).has('slow_his')){
 document.querySelector('input[name="editRow.hn"]').addEventListener('change',async()=>{
  const data=await (await fetch('/test/his')).json();
  document.querySelector('input[name="editRow.fname"]').value=data.fname;
  document.querySelector('input[name="editRow.tel"]').value=data.tel;
 });
}
const start=document.querySelector('input[name="editRow.surgery_start_time"]').parentElement;
const end=start.cloneNode(true);
end.querySelector('label').textContent='เวลาสิ้นสุดผ่าตัด:';
end.querySelector('input[type="time"]').name='editRow.surgery_end_time';
start.after(end);
document.querySelectorAll('pk-datepicker').forEach(host=>{
 const inp=host.querySelector('input');
 inp.onclick=()=>{
  document.querySelectorAll('.datepicker-dropdown').forEach(e=>e.remove());
  const initial=(inp.dataset.iso||'2026-09-09').split('-').map(Number);
  let y=initial[0],m=initial[1]-1;
  const popup=document.createElement('div');popup.className='datepicker-dropdown';host.appendChild(popup);
  const render=()=>{
   popup.replaceChildren();
   const header=document.createElement('div');header.className='calendar-header';
   const month=document.createElement('select'),year=document.createElement('select');
   for(let i=0;i<12;i++)month.add(new Option(String(i+1),String(i)));
   // The actual widget has a fixed range, not a moving +/- year range.
   for(let i=2006;i<=2036;i++)year.add(new Option(String(i+543),String(i+543)));
   month.value=String(m);year.value=String(y+543);
   month.onchange=()=>{m=Number(month.value);render();};year.onchange=()=>{y=Number(year.value)-543;render();};
   header.append(month,year);popup.appendChild(header);
   const heading=document.createElement('div');heading.className='month-year-display';heading.textContent=`เดือน ${m+1} ${y+543}`;popup.appendChild(heading);
   const days=document.createElement('div');days.className='days';popup.appendChild(days);
   for(let d=1;d<=new Date(y,m+1,0).getDate();d++){
    const iso=`${y}-${String(m+1).padStart(2,'0')}-${String(d).padStart(2,'0')}`;
    const b=document.createElement('button');b.textContent=String(d);
    if(inp.dataset.iso===iso)b.className='selected';
    b.onclick=()=>{inp.dataset.iso=iso;inp.value=`${String(d).padStart(2,'0')}/${String(m+1).padStart(2,'0')}/${y+543}`;popup.remove();};
    days.appendChild(b);
   }
   const clear=document.createElement('button');clear.textContent='ลบ';clear.onclick=()=>{delete inp.dataset.iso;inp.value='';popup.remove();};popup.appendChild(clear);
  };render();
 };
});
document.addEventListener('click',e=>{if(!e.target.closest('pk-datepicker'))document.querySelectorAll('.datepicker-dropdown').forEach(d=>d.remove());});
for(const [field,times] of Object.entries({rtpa:['rtpa'],ctscan:['ctscan'],stroke_unit:['stroke_unit'],surgery:['surgery_start','surgery_end']})){
 const update=()=>{const enabled=document.getElementById('editRow.'+field+'1').checked;for(const t of times){const el=document.querySelector('input[name="editRow.'+t+'_time"]');el.disabled=!enabled;el.previousElementSibling.querySelector('input').disabled=!enabled;}};
 document.querySelectorAll('input[name="editRow.'+field+'"]').forEach(r=>r.addEventListener('change',update));update();
}
