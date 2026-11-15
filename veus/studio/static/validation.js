'use strict';
(() => {
  const el=id=>document.getElementById(id);
  let csv=null, calibration=null, report=null;
  const status=text=>{el('validationStatus').textContent=text;};
  const describe=experiment=>{el('validationDataset').textContent=`${experiment.source.kind.toUpperCase()} · ${experiment.source.dataset} · run ${experiment.source.run_id} · role ${experiment.source.role} · ${experiment.kind} · licence ${experiment.source.licence}`;};
  const readFile=(file)=>new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=reject;reader.readAsDataURL(file);});
  function exportFile(name,text){const url=URL.createObjectURL(new Blob([text],{type:name.endsWith('.html')?'text/html':'application/json'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  async function load(){
    const response=await fetch('/api/validation/examples/'+el('validationExample').value);if(!response.ok)throw Error('Cannot load example');
    const data=await response.json();csv=data.csv_base64;
    el('validationConfig').value=JSON.stringify(data.experiment,null,2);el('validationSettings').value=JSON.stringify(data.calibration_settings,null,2);
    describe(data.experiment);status('Example loaded. Existing fitted model is retained until cleared.');
  }
  el('loadValidationExample').onclick=()=>load().catch(e=>status(e.message));
  el('validationCsv').onchange=async event=>{
    const file=event.target.files[0];if(!file)return;if(file.size>10000000){status('Select a CSV of at most 10 MB.');return;}
    csv=await readFile(file);const hash=await crypto.subtle.digest('SHA-256',await file.arrayBuffer());
    const sha=[...new Uint8Array(hash)].map(b=>b.toString(16).padStart(2,'0')).join('');
    status('CSV loaded, SHA-256 '+sha+'. Match this explicitly in the experiment; provenance is not inferred.');
  };
  el('validationJson').onchange=async event=>{try{const file=event.target.files[0];if(!file)return;const data=JSON.parse(await file.text());el('validationConfig').value=JSON.stringify(data,null,2);describe(data);status('Experiment loaded; select its matching CSV.');}catch(e){status(e.message);}};
  el('validationCalibration').onchange=async event=>{try{const file=event.target.files[0];if(!file)return;calibration=JSON.parse(await file.text());status('Calibration loaded; its training identity will be checked against the evaluation data.');}catch(e){status(e.message);}};
  el('clearValidationCalibration').onclick=()=>{calibration=null;el('exportCalibration').disabled=true;status('Fitted model cleared. Next evaluation uses only the original parameters.');};
  el('runValidation').onclick=async()=>{
    el('runValidation').disabled=true;status('Running experiment…');
    try{
      if(!csv)throw Error('Load a CSV first.');
      const experiment=JSON.parse(el('validationConfig').value),settings=JSON.parse(el('validationSettings').value||'{}');
      const request={experiment,csv_base64:csv,action:el('validationAction').value,calibration};
      if(request.action==='calibrate')request.calibration_settings=settings;
      if(el('validationSensitivity').checked){request.sensitivity_parameters=settings.parameters;request.sensitivity_signal=settings.objective_signal;}
      const response=await fetch('/api/validation/analyse',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(request)});
      const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
      report=data.report_html;if(data.calibration)calibration=data.calibration;
      const summary=data.summary;status(`${summary.label} · ${summary.status} · numerical criteria ${summary.numerical_status} · evidence ${summary.evidence_status}`);
      describe(experiment);el('validationFrame').hidden=false;el('validationFrame').srcdoc=report;
      const host=el('validationMetrics');host.replaceChildren();
      const table=document.createElement('table');table.style.width='100%';
      for(const [signal,metric] of Object.entries(summary.original.metrics)){
        const row=document.createElement('tr');const after=summary.calibrated?.metrics[signal];
        for(const value of [signal,'Original RMSE: '+(metric.rmse?.toPrecision(5)??'Unavailable'),'Calibrated RMSE: '+(after?.rmse?.toPrecision(5)??'Not fitted'),(after||metric).status]){const cell=document.createElement('td');cell.textContent=value;cell.style.padding='8px';row.append(cell);}table.append(row);
      }
      host.append(table);el('exportValidation').disabled=false;el('exportCalibration').disabled=!calibration;
    }catch(error){status('Experiment rejected: '+error.message);}finally{el('runValidation').disabled=false;}
  };
  el('exportValidation').onclick=()=>{if(report)exportFile('veus-model-validation.html',report);};
  el('exportCalibration').onclick=()=>{if(calibration)exportFile('veus-calibration.json',JSON.stringify(calibration,null,2));};
  fetch('/api/validation/examples').then(r=>r.json()).then(examples=>{for(const item of examples){const option=document.createElement('option');option.value=item.id;option.textContent=item.id+' · '+item.kind;el('validationExample').append(option);}}).catch(e=>status(e.message));
})();
