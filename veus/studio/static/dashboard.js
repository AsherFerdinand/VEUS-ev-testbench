'use strict';
const $ = id => document.getElementById(id);
const fields = ['mass_kg','max_power_kw','max_torque_nm','friction','grade_percent','initial_speed_kmh','duration_s'];
let socket, samples = [], appliedConfig = null, connected = false, pendingReset = false;
const controls = () => ({throttle: Number($('throttle').value)/100, brake: Number($('brake').value)/100});
function config() { return Object.fromEntries([...fields.map(k => [k, Number($(k).value)]), ['mode', $('mode').value]]); }
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
  $('time').textContent = data.time_s.toFixed(1)+' s';
  $('rpm').textContent = Math.round(data.motor_rpm)+' rpm / '+data.current_gear;
  $('forces').textContent = [data.drive_force_n,data.brake_force_n,data.resistance_force_n].map(Math.round).join(' / ')+' N';
  $('limits').textContent = [data.traction_limited ? 'Tyre traction' : '', data.torque_limited ? 'Motor torque / power / RPM' : ''].filter(Boolean).join(', ') || 'None';
  $('lane').style.transform = `translateX(-${data.position_m % 40}px)`;
  if (!samples.length || data.time_s > samples[samples.length-1].time_s) samples.push(data);
  buttons(data.status); drawCharts();
}
function draw(canvasId, key, color) {
  const canvas = $(canvasId), width = canvas.clientWidth, height = canvas.clientHeight;
  const scale = window.devicePixelRatio || 1;
  canvas.width = width*scale; canvas.height = height*scale;
  const ctx = canvas.getContext('2d'); ctx.scale(scale,scale);
  const left=48, right=width-12, top=12, bottom=height-28;
  const values = samples.map(s => s[key]);
  let lo = Math.min(0,...values), hi = Math.max(1,...values); hi += (hi-lo)*0.1;
  const duration = Math.max(1, samples[samples.length-1]?.time_s || 0);
  ctx.font='11px system-ui'; ctx.fillStyle='#a1afc3';
  for(let i=0;i<=4;i++) { const y=top+(bottom-top)*i/4;
    ctx.strokeStyle='#2b3a50'; ctx.beginPath(); ctx.moveTo(left,y);ctx.lineTo(right,y);ctx.stroke();
    ctx.fillText((hi-(hi-lo)*i/4).toFixed(1),2,y+4);
  }
  ctx.fillText('0 s',left,bottom+20);ctx.fillText(duration.toFixed(1)+' s',Math.max(left,right-45),bottom+20);
  ctx.strokeStyle=color;ctx.lineWidth=2;ctx.beginPath();
  samples.forEach((s,i)=> {const x=left+s.time_s/duration*(right-left), y=bottom-(s[key]-lo)/(hi-lo)*(bottom-top);if(i)ctx.lineTo(x,y);else ctx.moveTo(x,y);});ctx.stroke();
}
function drawCharts() {draw('speedChart','velocity_kmh','#5ce0ce');draw('accelChart','acceleration_ms2','#6ea9ff');draw('powerChart','motor_power_kw','#ffc273');draw('torqueChart','motor_torque_nm','#b6a1ff');}
function download(name, text, mime) {const url=URL.createObjectURL(new Blob([text],{type:mime}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('configuration').addEventListener('submit', event => {event.preventDefault();pendingReset=true;send({action:'reset',config:config()});});
$('mode').addEventListener('change',()=> {if($('mode').value==='braking' || $('mode').value==='coast') $('initial_speed_kmh').value='80';$('message').textContent='Apply & reset to use the new experiment.';});
for(const id of ['throttle','brake']) $(id).addEventListener('input',()=> {$(id+'_value').value=$(id).value+'%';send({action:'controls',controls:controls()});});
$('start').onclick=()=>{send({action:'controls',controls:controls()});send({action:'start'});};
$('pause').onclick=()=>send({action:'pause'});
$('export').onclick=()=>{if(!samples.length)return;const keys=Object.keys(samples[0]).filter(k=>k!=='type');download('veus-telemetry.csv',keys.join(',')+'\n'+samples.map(s=>keys.map(k=>s[k]).join(',')).join('\n'),'text/csv');};
$('metadata').onclick=()=>download('veus-run.json',JSON.stringify({schema_version:1,model_version:'veus-mechanical-v1',config:appliedConfig,dt_s:0.01,frames:samples.length,controls:'Manual pedal history is not recorded; CSV contains delivered forces.',limitations:['No battery or regenerative braking','Uncalibrated parameters','Forward motion only']},null,2),'application/json');
window.addEventListener('resize',drawCharts);
function connect() {
  socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/simulation`);
  socket.onopen=()=>{connected=true;$('connection').textContent='Connected · local simulation';pendingReset=true;send({action:'reset',config:config()});};
  socket.onmessage=event=>{const data=JSON.parse(event.data);if(data.type==='error'){pendingReset=false;$('message').textContent=data.message;return;}render(data);};
  socket.onclose=()=>{connected=false;$('connection').textContent='Disconnected';$('message').textContent='Connection lost. Reload to start a new session; export remains available.';buttons('disconnected');};
  socket.onerror=()=>{$('message').textContent='Cannot reach the simulation server.';};
}
buttons('ready');drawCharts();connect();
