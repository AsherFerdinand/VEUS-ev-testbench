'use strict';
const $ = id => document.getElementById(id);
const fields = ['mass_kg','max_power_kw','max_torque_nm','friction','grade_percent','initial_speed_kmh','duration_s','battery_capacity_kwh','initial_soc','battery_voltage_v','battery_resistance_ohm','discharge_limit_a','charge_limit_a','drive_efficiency','regen_efficiency'];
let socket, samples = [], appliedConfig = null, connected = false, pendingReset = false;
const controls = () => ({throttle: Number($('throttle').value)/100, brake: Number($('brake').value)/100});
function config() { return Object.fromEntries([...fields.map(k => [k, Number($(k).value)]), ['mode', $('mode').value], ['regen_enabled', $('regen_enabled').checked]]); }
function send(value) { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(value)); }
function buttons(status) {
  $('start').disabled = !connected || status === 'running' || status === 'completed';
  $('pause').disabled = !connected || status !== 'running';
  $('reset').disabled = !connected;
  $('export').disabled = samples.length === 0;
  $('metadata').disabled = samples.length === 0;
  const manual = appliedConfig?.mode === 'manual';
  $('throttle').disabled = !connected || !manual;
  $('brake').disabled = !connected || !manual;
  $('start').textContent = status === 'paused' ? 'Resume' : 'Run';
}
function render(data) {
  if (pendingReset && data.status === 'ready') {
    samples = []; pendingReset = false;
    appliedConfig = config();
    $('message').textContent = '';
  }
  $('status').textContent = data.status.toUpperCase();
  const values = {speed: [data.velocity_kmh,1], accel: [data.acceleration_ms2,2], power: [data.motor_power_kw,1], distance: [data.position_m,1]};
  for (const [id, [value, digits]] of Object.entries(values)) $(id).textContent = value.toFixed(digits);
  $('soc').textContent = (data.soc*100).toFixed(3);
  const initialSoc = samples.length ? samples[0].soc : data.soc;
  const change = (data.soc-initialSoc)*100;
  $('socChange').textContent = `Δ ${change>=0?'+':''}${change.toFixed(3)} percentage points`;
  $('batteryPower').textContent = data.battery_power_kw.toFixed(1);
  $('consumed').textContent = data.energy_consumed_kwh.toFixed(3);
  $('recovered').textContent = data.energy_recovered_kwh.toFixed(3);
  $('electrical').textContent = data.battery_voltage_v.toFixed(1)+' V / '+data.battery_current_a.toFixed(1)+' A';
  $('brakeSplit').textContent = Math.round(data.regen_force_n)+' / '+Math.round(data.friction_brake_force_n)+' N';
  $('balance').textContent = data.energy_balance_error_j.toFixed(3)+' J';
  $('time').textContent = data.time_s.toFixed(1)+' s';
  $('rpm').textContent = Math.round(data.motor_rpm)+' rpm / '+data.current_gear;
  $('forces').textContent = [data.drive_force_n,data.brake_force_n,data.resistance_force_n].map(Math.round).join(' / ')+' N';
  $('limits').textContent = [data.battery_limited ? 'Battery discharge' : '', data.traction_limited ? 'Tyre traction' : '', data.torque_limited ? 'Motor torque / power / RPM' : ''].filter(Boolean).join(', ') || 'None';
  $('lane').style.transform = `translateX(-${data.position_m % 40}px)`;
  if (!samples.length || data.time_s > samples[samples.length-1].time_s) samples.push({...data, soc_percent:data.soc*100});
  buttons(data.status); drawCharts();
}
function draw(canvasId, key, color) {
  const canvas = $(canvasId), width = canvas.clientWidth, height = canvas.clientHeight;
  const scale = window.devicePixelRatio || 1;
  canvas.width = width*scale; canvas.height = height*scale;
  const ctx = canvas.getContext('2d'); ctx.scale(scale,scale);
  const left=64, right=width-12, top=12, bottom=height-28;
  const values = samples.map(s => s[key]);
  const zoomSoc = key === 'soc_percent';
  let lo, hi;
  if (zoomSoc) {
    const initial = (appliedConfig?.initial_soc ?? 0.8)*100;
    const min = values.length ? Math.min(...values) : initial;
    const max = values.length ? Math.max(...values) : initial;
    const padding = Math.max(0.005, (max-min)*0.15);
    lo = Math.max(0,min-padding); hi = Math.min(100,max+padding);
  } else {
    lo = Math.min(0,...values); hi = Math.max(1,...values); hi += (hi-lo)*0.1;
  }
  canvas.dataset.axisMin = String(lo); canvas.dataset.axisMax = String(hi);
  const duration = Math.max(1, samples[samples.length-1]?.time_s || 0);
  ctx.font='13px system-ui'; ctx.fillStyle='#a1afc3';
  for(let i=0;i<=4;i++) { const y=top+(bottom-top)*i/4;
    ctx.strokeStyle='#2b3a50'; ctx.beginPath(); ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();
    ctx.fillText((hi-(hi-lo)*i/4).toFixed(zoomSoc ? 3 : 1),2,y+4);
  }
  ctx.fillText('0 s',left,bottom+20);ctx.fillText(duration.toFixed(1)+' s',Math.max(left,right-45),bottom+20);
  ctx.strokeStyle=color;ctx.lineWidth=2.5;ctx.beginPath();
  samples.forEach((s,i)=> {const x=left+s.time_s/duration*(right-left), y=bottom-(s[key]-lo)/(hi-lo)*(bottom-top);if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);});ctx.stroke();
}
function drawCharts() {draw('speedChart','velocity_kmh','#5ce0ce');draw('accelChart','acceleration_ms2','#6ea9ff');draw('powerChart','motor_power_kw','#ffc273');draw('torqueChart','motor_torque_nm','#b6a1ff');draw('socChart','soc_percent','#5ce0ce');draw('batteryChart','battery_power_kw','#ffc273');}
function download(name, text, mime) {const url=URL.createObjectURL(new Blob([text],{type:mime}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('configuration').addEventListener('submit', event => {event.preventDefault();pendingReset=true;send({action:'reset',config:config()});});
$('mode').addEventListener('change',()=> {if($('mode').value==='braking' || $('mode').value==='coast') $('initial_speed_kmh').value='80';$('message').textContent='Apply & reset to use the new experiment.';});
for(const id of ['throttle','brake']) $(id).addEventListener('input',()=> {$(id+'_value').value=$(id).value+'%';send({action:'controls',controls:controls()});});
$('start').onclick=()=>{send({action:'controls',controls:controls()});send({action:'start'});};
$('pause').onclick=()=>send({action:'pause'});
$('export').onclick=()=>{if(!samples.length)return;const keys=Object.keys(samples[0]).filter(k=>k!=='type');download('veus-telemetry.csv',keys.join(',')+'\n'+samples.map(s=>keys.map(k=>s[k]).join(',')).join('\n'),'text/csv');};
$('metadata').onclick=()=>download('veus-run.json',JSON.stringify({schema_version:1,model_version:'veus-energy-v2',config:appliedConfig,dt_s:0.01,frames:samples.length,controls:'Manual pedal history is not recorded; CSV contains delivered forces.',limitations:['Constant-OCV battery; no thermal model','Constant drive and regen efficiencies','No ADAS','Uncalibrated parameters','Forward motion only']},null,2),'application/json');
// Native dialog supplies focus containment, Escape handling and backdrop.
let expandedPanel = null, chartMarker = null, expandedButton = null;
const chartDialog = $('chartDialog');
chartDialog.addEventListener('close', () => {
  if (!expandedPanel) return;
  chartMarker.replaceWith(expandedPanel);
  expandedButton.textContent = 'Expand';
  expandedButton.setAttribute('aria-expanded','false');
  expandedButton.setAttribute('aria-label','Expand '+expandedPanel.querySelector('h2').textContent);
  expandedButton.focus();
  expandedPanel = null; chartMarker = null; expandedButton = null;
  drawCharts();
});
for (const canvas of document.querySelectorAll('.charts canvas')) {
  const panel = canvas.closest('.panel'), title = panel.querySelector('h2');
  title.id = canvas.id+'Title';
  const head = document.createElement('div'); head.className = 'chart-head';
  title.before(head); head.append(title);
  const button = document.createElement('button'); button.type = 'button';
  button.textContent = 'Expand';button.setAttribute('aria-expanded','false');
  button.setAttribute('aria-label','Expand '+title.textContent);
  button.onclick = () => {
    if (chartDialog.open) { chartDialog.close(); return; }
    expandedPanel=panel;expandedButton=button;chartMarker=document.createComment('chart position');
    panel.before(chartMarker);chartDialog.append(panel);
    chartDialog.setAttribute('aria-labelledby',title.id);chartDialog.showModal();
    button.textContent='Close graph';button.setAttribute('aria-expanded','true');
    button.setAttribute('aria-label','Close expanded '+title.textContent);drawCharts();button.focus();
  };
  head.append(button);
  const note=document.createElement('small');note.className='chart-note';
  note.textContent = canvas.id==='socChart'
    ? 'Zoomed SOC axis · not zero-based. Read the tick labels; Δ SOC is shown above in percentage points.'
    : 'Horizontal axis: simulation time in seconds. Expand for a larger view.';
  panel.append(note);
}
window.addEventListener('resize',drawCharts);
function connect() {
  socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/simulation`);
  socket.onopen=()=>{connected=true;$('connection').textContent='Connected · local simulation';pendingReset=true;send({action:'reset',config:config()});};
  socket.onmessage=event=>{const data=JSON.parse(event.data);if(data.type==='error'){pendingReset=false;$('message').textContent=data.message;return;}render(data);};
  socket.onclose=()=>{connected=false;$('connection').textContent='Disconnected';$('message').textContent='Connection lost. Reload to start a new session; export remains available.';buttons('disconnected');};
  socket.onerror=()=>{$('message').textContent='Cannot reach the simulation server.';};
}
buttons('ready');drawCharts();connect();
