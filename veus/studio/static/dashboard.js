'use strict';
const $ = id => document.getElementById(id);
const fields = ['mass_kg','max_power_kw','max_torque_nm','friction','grade_percent','initial_speed_kmh','duration_s','battery_capacity_kwh','initial_soc','battery_voltage_v','battery_resistance_ohm','discharge_limit_a','charge_limit_a','drive_efficiency','regen_efficiency','target_speed_kmh','lead_speed_kmh','initial_gap_m','time_headway_s','standstill_gap_m','max_acceleration_ms2','comfort_deceleration_ms2','aeb_ttc_s','detection_delay_s','actuation_delay_s','lead_brake_start_s','lead_deceleration_ms2'];
let sensorFaultEvents = [];
let socket, samples = [], appliedConfig = null, connected = false, pendingReset = false;
const controls = () => ({throttle: Number($('throttle').value)/100, brake: Number($('brake').value)/100});
function sensorConfig() {
  const number = id => Number($(id).value);
  return {enabled:$('sensorsEnabled').checked, mode:$('sensorMode').value, seed:number('sensorSeed'),
    speed:{noise_std_ms:number('speedNoise'),bias_ms:number('speedBias'),sampling_hz:number('speedHz'),latency_s:number('speedLatency'),stale_after_s:number('speedStale')},
    radar:{distance_noise_std_m:number('radarNoise'),distance_bias_m:number('radarBias'),relative_speed_noise_std_ms:number('closingNoise'),relative_speed_bias_ms:number('closingBias'),sampling_hz:number('radarHz'),latency_s:number('radarLatency'),stale_after_s:number('radarStale')},
    faults:$('sensorFault').value==='none' ? [] : [{id:'interactive-event',sensor:$('faultSensor').value,fault:$('sensorFault').value,start_time_s:number('faultStart'),duration_s:number('faultDuration'),parameters:{}}]};
}
function config() { return {...Object.fromEntries([...fields.map(k => [k, Number($(k).value)]), ['mode', $('mode').value], ['regen_enabled', $('regen_enabled').checked]]),sensors:sensorConfig()}; }
function send(value) { if (socket?.readyState === WebSocket.OPEN) socket.send(JSON.stringify(value)); }
function buttons(status) {
  $('start').disabled = !connected || status === 'running' || ['completed','collision'].includes(status);
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
  const events=data.sensor_fault_events, resolved=data.resolved_config;delete data.sensor_fault_events;delete data.resolved_config;
  if (pendingReset && data.status === 'ready') {
    samples = []; sensorFaultEvents=[]; pendingReset = false;
    appliedConfig = resolved || config();
    $('message').textContent = '';
  }
  if(resolved && data.status==='ready') appliedConfig=resolved;
  if(events) sensorFaultEvents=events;
  const age = value => value===null ? '—' : value.toFixed(2)+' s';
  $('speedSensorStatus').textContent=data.speed_sensor_status+' / '+age(data.speed_sensor_age_s);
  $('radarSensorStatus').textContent=data.radar_sensor_status+' / '+age(data.radar_sensor_age_s);
  $('measuredValues').textContent=(data.speed_sensor_valid?(data.measured_speed_ms*3.6).toFixed(2)+' km/h':'Unavailable')+' / '+(data.radar_sensor_valid?data.measured_gap_m.toFixed(2)+' m':'Unavailable');
  $('sensorControllerHealth').textContent=data.controller_input_health+' / '+data.applied_input_health;
  $('activeSensorFaults').textContent=data.active_sensor_faults || 'None';
  const event=sensorFaultEvents[sensorFaultEvents.length-1];
  $('latestSensorEvent').textContent=event?`${event.id} ${event.event} at ${event.time_s.toFixed(2)} s`:'None';
  $('adasPanel').hidden = data.target_speed_kmh === null;
  $('controllerState').textContent = data.controller_state.replaceAll('_',' ');
  $('gapValue').textContent = data.gap_m === null ? 'No lead vehicle' : data.gap_m.toFixed(1)+' / '+data.desired_gap_m.toFixed(1)+' m';
  $('ttcValue').textContent = data.ttc_s === null ? 'Undefined · not closing' : data.ttc_s.toFixed(2)+' s';
  $('collisionValue').textContent = data.minimum_gap_m === null ? 'No lead vehicle' : data.minimum_gap_m.toFixed(2)+' m / '+(data.collision?'COLLISION':'No collision');
  $('commandValue').textContent = data.requested_acceleration_ms2.toFixed(2)+' m/s²';
  $('triggerValue').textContent = data.aeb_trigger_time_s === null ? 'Not triggered' : data.aeb_trigger_time_s.toFixed(2)+' s';
  $('leadCar').style.display = data.gap_m === null ? 'none' : 'block';
  $('leadCar').style.left = Math.min(85, Math.max(24, 24+(data.gap_m??0)*0.7))+'%';
  $('gapLabel').textContent = data.gap_m === null ? '' : 'Gap '+data.gap_m.toFixed(1)+' m';
  if (data.collision) $('message').textContent='Collision detected. Run stopped; change gap, friction or delays, then reset.';
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
  if (!samples.length || data.time_s > samples[samples.length-1].time_s) samples.push({...data, soc_percent:data.soc*100, measured_speed_kmh:data.speed_sensor_valid?data.measured_speed_ms*3.6:null, valid_measured_gap_m:data.radar_sensor_valid?data.measured_gap_m:null});
  buttons(data.status); drawCharts();
  document.dispatchEvent(new CustomEvent('veus:telemetry',{detail:{...data}}));
}
function draw(canvasId, key, color, extra = []) {
  const canvas = $(canvasId); if (!canvas || !canvas.getClientRects().length || document.hidden) return;
  const width = canvas.clientWidth, height = canvas.clientHeight;
  const scale = window.devicePixelRatio || 1;
  canvas.width = width*scale; canvas.height = height*scale;
  const ctx = canvas.getContext('2d'); ctx.scale(scale,scale);
  const left=64, right=width-12, top=12, bottom=height-28;
  const values = samples.flatMap(s => [s[key], ...extra.map(e=>s[e.key])]).filter(Number.isFinite);
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
  const series = [{key,color},...extra];
  for (const line of series) {
    ctx.strokeStyle=line.color;ctx.lineWidth=2.5;ctx.setLineDash(line.dashed?[6,4]:[]);ctx.beginPath();
    let started=false;
    for (const s of samples) {
      if (!Number.isFinite(s[line.key])) { started=false;continue; }
      const x=left+s.time_s/duration*(right-left), y=bottom-(s[line.key]-lo)/(hi-lo)*(bottom-top);
      if(started)ctx.lineTo(x,y);else ctx.moveTo(x,y);started=true;
    }
    ctx.stroke();
  }
  ctx.setLineDash([]);
  if (!values.length) ctx.fillText('No defined samples for this experiment',left,top+30);

}
function drawCharts() {draw('driveSpeedChart','velocity_kmh','#b4e5bb');draw('drivePowerChart','battery_power_kw','#d9b28c');draw('speedChart','velocity_kmh','#5ce0ce',[{key:'target_speed_kmh',color:'#a1afc3',dashed:true},{key:'lead_speed_kmh',color:'#ffc273',dashed:true}]);draw('accelChart','acceleration_ms2','#6ea9ff',[{key:'requested_acceleration_ms2',color:'#ffc273',dashed:true}]);draw('powerChart','motor_power_kw','#ffc273');draw('torqueChart','motor_torque_nm','#b6a1ff');draw('socChart','soc_percent','#5ce0ce');draw('batteryChart','battery_power_kw','#ffc273');draw('gapChart','gap_m','#5ce0ce',[{key:'desired_gap_m',color:'#ffc273',dashed:true}]);draw('ttcChart','ttc_s','#6ea9ff');draw('sensorSpeedChart','velocity_kmh','#5ce0ce',[{key:'measured_speed_kmh',color:'#ffc273',dashed:true}]);draw('sensorGapChart','gap_m','#5ce0ce',[{key:'valid_measured_gap_m',color:'#ffc273',dashed:true}]);}
function download(name, text, mime) {const url=URL.createObjectURL(new Blob([text],{type:mime}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('configuration').addEventListener('submit', event => {event.preventDefault();window.VEUS?.release();pendingReset=true;send({action:'reset',config:config()});});
$('mode').addEventListener('change',()=> {if(['braking','coast','acc','aeb'].includes($('mode').value)) $('initial_speed_kmh').value='80';if($('mode').value==='aeb'){$('lead_speed_kmh').value='80';$('initial_gap_m').value='35';}if($('mode').value==='acc'){$('lead_speed_kmh').value='60';$('initial_gap_m').value='50';}$('message').textContent='Apply & reset to use the new experiment.';});
for(const id of ['throttle','brake']) $(id).addEventListener('input',()=> {$(id+'_value').value=$(id).value+'%';if(window.VEUS)window.VEUS.slider(id);else send({action:'controls',controls:controls()});});
$('resetSensors').onclick=()=>{
  $('sensorsEnabled').checked=false;$('sensorMode').value='configured';
  for(const [id,value] of Object.entries({sensorSeed:42,speedNoise:0,speedBias:0,radarNoise:0,radarBias:0,closingNoise:0,closingBias:0,speedHz:100,radarHz:100,speedLatency:0,radarLatency:0,speedStale:.3,radarStale:.3,sensorFault:'none',faultSensor:'radar',faultStart:3,faultDuration:4})) $(id).value=value;
  $('message').textContent='Sensor settings reset. Apply & reset to use them.';
};
$('start').onclick=()=>{send({action:'controls',controls:controls()});send({action:'start'});};
$('pause').onclick=()=>send({action:'pause'});
$('export').onclick=()=>{if(!samples.length)return;const keys=Object.keys(samples[0]).filter(k=>k!=='type');download('veus-telemetry.csv',keys.join(',')+'\n'+samples.map(s=>keys.map(k=>s[k]===null?'':'\"'+String(s[k]).replaceAll('\"','\"\"')+'\"').join(',')).join('\n'),'text/csv');};
$('metadata').onclick=()=>download('veus-run.json',JSON.stringify({schema_version:1,model_version:'veus-sensors-v5',sensor_fault_events:sensorFaultEvents,config:appliedConfig,dt_s:0.01,frames:samples.length,controls:'Manual pedal history is not recorded; CSV contains delivered forces.',limitations:['Constant-OCV battery; no thermal model','Constant drive and regen efficiencies','Educational ADAS; no production safety validation','Uncalibrated parameters','Forward motion only']},null,2),'application/json');
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
  note.textContent = ['sensorSpeedChart','sensorGapChart'].includes(canvas.id) ? 'Solid cyan: ground truth. Dashed amber: valid measured values; stale or missing values are gaps.' : canvas.id==='speedChart' ? 'Solid cyan: ego speed. Dashed grey: target. Dashed amber: lead.' : canvas.id==='accelChart' ? 'Solid blue: achieved acceleration. Dashed amber: controller request (zero when inactive).' : canvas.id==='gapChart' ? 'Solid cyan: actual gap. Dashed amber: desired gap.' : canvas.id==='ttcChart' ? 'TTC shown only when closing on a lead vehicle; missing values are not zero.' : canvas.id==='socChart'
    ? 'Zoomed SOC axis · not zero-based. Read the tick labels; Δ SOC is shown above in percentage points.'
    : 'Horizontal axis: simulation time in seconds. Expand for a larger view.';
  panel.append(note);
}
window.addEventListener('resize',drawCharts);
function connect() {
  socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/ws/simulation`);
  socket.onopen=()=>{connected=true;document.body.classList.add('connected');$('connection').textContent='Connected · local simulation';pendingReset=true;send({action:'reset',config:config()});};
  socket.onmessage=event=>{const data=JSON.parse(event.data);if(data.type==='error'){pendingReset=false;$('message').textContent=data.message;document.dispatchEvent(new CustomEvent('veus:error',{detail:data.message}));return;}render(data);};
  socket.onclose=()=>{connected=false;document.body.classList.remove('connected');document.dispatchEvent(new Event('veus:disconnect'));$('connection').textContent='Disconnected';$('message').textContent='Connection lost. Reload to start a new session; export remains available.';buttons('disconnected');};
  socket.onerror=()=>{$('message').textContent='Cannot reach the simulation server.';};
}
buttons('ready');drawCharts();connect();
