const fmt0 = new Intl.NumberFormat('sv-SE',{maximumFractionDigits:0});
const fmt1 = new Intl.NumberFormat('sv-SE',{maximumFractionDigits:1});
const fmt2 = new Intl.NumberFormat('sv-SE',{maximumFractionDigits:2});
let panel=[], model={}, predictions=[], diagnostics=[], qq=[];
let selectedWindow=5;

const labels={
  lag1_inflyttning_per_1000:'Inflyttning föregående år per 1 000',
  lag1_log_folkmangd:'Folkmängd (log), föregående år',
  lag1_befolkningstillvaxt_pct:'Befolkningstillväxt, föregående år (%)',
  lag1_andel_20_34:'Andel 20–34 år, föregående år (%)',
  lag1_inflyttare_medelalder:'Inflyttarnas medelålder föregående år',
  lag1_inkomst_tkr:'Genomsnittlig förvärvsinkomst 20–64 år, föregående år (tkr)',
  lag1_andel_smahus:'Andel småhus föregående år (%)',
  lag1_sysselsattningsgrad:'Sysselsättningsgrad 20–64 år, föregående år (%)',
  lag1_arbetsloshet:'Arbetslöshet 20–64 år, föregående år (%)',
  lag1_andel_eftergymnasial:'Andel eftergymnasialt utbildade 25–64 år, föregående år (%)',
  lag1_andel_studerande:'Andel studerande 20–64 år, föregående år (%)'
};

async function load(){
  initTabs();
  try{
    const responses=await Promise.all([
      fetch('data/model.json',{cache:'no-store'}),
      fetch('data/panel.csv',{cache:'no-store'}),
      fetch('data/predictions.csv',{cache:'no-store'}),
      fetch('data/diagnostics.csv',{cache:'no-store'}),
      fetch('data/qq.csv',{cache:'no-store'})
    ]);
    for(const r of responses){
      if(!r.ok) throw new Error('Analysdata saknas ännu ('+r.status+' '+r.url.split('/').pop()+'). GitHub Actions måste slutföras först.');
    }
    const [mText,pText,prText,dText,qText]=await Promise.all(responses.map(r=>r.text()));
    model=JSON.parse(mText);
    panel=d3.csvParse(pText,d3.autoType);
    predictions=d3.csvParse(prText,d3.autoType);
    diagnostics=d3.csvParse(dText,d3.autoType);
    qq=d3.csvParse(qText,d3.autoType);
    selectedWindow=Number(model.default_window||5);
    initWindowSelector();
    const mm=document.getElementById('matrixMetric');
    if(mm) mm.addEventListener('change',renderVariableMatrix);
    initRelationships();
    initMunicipality();
    renderAll();
  }catch(err){
    showLoadError(err);
    console.error(err);
  }
}

function showLoadError(err){
  const cards=document.getElementById('cards');
  if(cards) cards.innerHTML='<div class="card"><div class="label">Status</div><div class="value" style="font-size:18px">Data byggs eller behöver repareras</div><div class="note" style="margin-top:8px">'+String(err.message||err)+'</div></div>';
  const chart=document.getElementById('modelCompare');
  if(chart) chart.innerHTML='<p class="note">Navigationen fungerar, men diagrammen fylls först när analysdata har skapats av GitHub Actions.</p>';
}

function initTabs(){
  document.querySelectorAll('.tab').forEach(b=>b.addEventListener('click',()=>{
    document.querySelectorAll('.tab,.page').forEach(x=>x.classList.remove('active'));
    b.classList.add('active');
    document.getElementById(b.dataset.page).classList.add('active');
    setTimeout(()=>window.dispatchEvent(new Event('resize')),20);
  }));
}

function initWindowSelector(){
  const s=document.getElementById('windowSelect');
  s.value=String(selectedWindow);
  s.addEventListener('change',()=>{
    selectedWindow=Number(s.value);
    renderAll();
  });
}

function wdata(){
  return model.windows?.[String(selectedWindow)];
}

function renderAll(){
  const w=wdata();
  if(!w) return showLoadError(new Error('Modellresultat saknas för '+selectedWindow+' års analysperiod.'));
  const e=w.explanation, v=w.validation;
  document.getElementById('windowDescription').textContent=
    'Förklaringsmodell: '+e.start_year+'–'+e.end_year+
    ' · validering: '+v.train_start_year+'–'+v.train_end_year+' → test '+v.test_year;
  renderOverview();
  renderModel();
  renderVariableMatrix();
  renderValidation();
  renderMunicipality();
}

function metricCard(label,value,sub=''){
  return '<div class="card"><div class="label">'+label+'</div><div class="value">'+value+'</div>'+(sub?'<div class="note">'+sub+'</div>':'')+'</div>';
}

function renderOverview(){
  const w=wdata(), e=w.explanation, v=w.validation;
  const best=Object.entries(v.models).sort((a,b)=>(b[1].r2??-Infinity)-(a[1].r2??-Infinity))[0];
  document.getElementById('cards').innerHTML=[
    metricCard('Förklaringsperiod',e.start_year+'–'+e.end_year),
    metricCard('Kommun-år',fmt0.format(e.n_obs)),
    metricCard('Kommuner',fmt0.format(e.n_municipalities)),
    metricCard('R²',fmt2.format(e.r2)),
    metricCard('Justerat R²',fmt2.format(e.adjusted_r2)),
    metricCard('Bästa test-R²',fmt2.format(best[1].r2),best[0].toUpperCase()+' · test '+v.test_year)
  ].join('');

  Plotly.react('modelCompare',[{
    x:['Naiv','OLS','Ridge'],
    y:[v.models.naive.r2,v.models.ols.r2,v.models.ridge.r2],
    type:'bar',
    name:'Out-of-sample R²',
    hovertemplate:'%{x}<br>R²=%{y:.3f}<extra></extra>'
  }],{
    margin:{t:20},
    yaxis:{title:'Out-of-sample R²'},
    xaxis:{title:'Modell'}
  },{responsive:true,displaylogo:false});
}

function initRelationships(){
  const x=document.getElementById('xvar');
  if(!x.options.length) Object.entries(labels).forEach(([k,v])=>x.add(new Option(v,k)));
  const years=[...new Set(panel.map(d=>d.year))].filter(Number.isFinite).sort((a,b)=>a-b);
  const y=document.getElementById('yearFilter');
  if(!y.options.length){
    y.add(new Option('Alla år','all'));
    years.forEach(v=>y.add(new Option(v,v)));
  }
  x.value='lag1_inflyttning_per_1000';
  y.value=String(model.test_year);
  x.addEventListener('change',renderScatter);
  y.addEventListener('change',renderScatter);
  renderScatter();
}

function renderScatter(){
  const key=document.getElementById('xvar').value;
  const yf=document.getElementById('yearFilter').value;
  const rows=panel.filter(d=>Number.isFinite(d[key])&&Number.isFinite(d.inflyttning_per_1000)&&(yf==='all'||d.year===+yf));
  Plotly.react('scatter',[{
    x:rows.map(d=>d[key]),
    y:rows.map(d=>d.inflyttning_per_1000),
    text:rows.map(d=>d.kommun+' · '+d.year),
    mode:'markers',type:'scatter',
    hovertemplate:'%{text}<br>x=%{x:.2f}<br>Inflyttning=%{y:.2f} per 1 000<extra></extra>'
  }],{
    margin:{t:20},
    xaxis:{title:labels[key]},
    yaxis:{title:'Inflyttade per 1 000'}
  },{responsive:true,displaylogo:false});
}

function renderVariableMatrix(){
  const e=wdata().explanation;
  const pm=e.pairwise_matrix;
  if(!pm||!pm.rows||!pm.features) return;

  const mode=document.getElementById('matrixMetric')?.value||'correlation';
  const keys=pm.features;
  const short=k=>(labels[k]||k)
    .replace(', föregående år','')
    .replace(' föregående år','')
    .replace('Genomsnittlig ','')
    .replace('20–64 år','')
    .replace('25–64 år','')
    .replace(/\s+/g,' ').trim();

  const lookup=new Map(pm.rows.map(r=>[r.x+'|'+r.y,r]));
  const z=keys.map(y=>keys.map(x=>{
    const r=lookup.get(x+'|'+y)||lookup.get(y+'|'+x);
    return r?Number(r[mode]):null;
  }));
  const text=z.map(row=>row.map(v=>Number.isFinite(v)?(mode==='correlation'?v.toFixed(2):v.toFixed(3)):''));

  let title='Pearsons korrelation r';
  let zmin=-1,zmax=1,colorscale='RdBu';
  if(mode==='joint_adjusted_r2'){
    title='Gemensamt justerat R²';
    zmin=0; zmax=Math.max(.01,...z.flat().filter(Number.isFinite)); colorscale='Blues';
  } else if(mode==='incremental_adjusted_r2'){
    title='Extra justerat R² jämfört med starkaste ensam';
    const vals=z.flat().filter(Number.isFinite);
    const lim=Math.max(.005,...vals.map(v=>Math.abs(v)));
    zmin=-lim; zmax=lim; colorscale='RdBu';
  }

  Plotly.react('variableMatrix',[{
    z,
    x:keys.map(short),
    y:keys.map(short),
    type:'heatmap',
    zmin,zmax,colorscale,
    reversescale:mode==='correlation',
    text,
    texttemplate:'%{text}',
    hovertemplate:'%{y}<br>× %{x}<br>'+title+': %{z:.3f}<extra></extra>',
    colorbar:{title:title}
  }],{
    margin:{t:25,l:190,b:150},
    xaxis:{tickangle:-45,automargin:true},
    yaxis:{automargin:true,autorange:'reversed'}
  },{responsive:true,displaylogo:false});
}

function renderModel(){
  const e=wdata().explanation;
  const sel=e.variable_selection||{};
  document.getElementById('regressionCards').innerHTML=[
    metricCard('R²',fmt2.format(e.r2)),
    metricCard('Justerat R²',fmt2.format(e.adjusted_r2)),
    metricCard('AIC',fmt1.format(e.aic)),
    metricCard('BIC',fmt1.format(e.bic)),
    metricCard('Observationer',fmt0.format(e.n_obs)),
    metricCard('Standardfel','Klustrade','per kommun')
  ].join('');

  const selected=(sel.selected||[]).map(f=>labels[f]||f);
  const excluded=(sel.excluded||[]).map(f=>labels[f]||f);
  const elastic=(sel.elastic_net_selected||[]).map(f=>labels[f]||f);
  const backward=(sel.backward_aic_selected||[]).map(f=>labels[f]||f);
  const thematic=(sel.thematic_selected||[]).map(f=>labels[f]||f);
  const temporal=(sel.temporal_cv_selected||[]).map(f=>labels[f]||f);
  const cv=sel.temporal_cv||{};
  const themeMeta=sel.thematic_selection||{};
  document.getElementById('selectionSummary').innerHTML=
    '<p><strong>Behållna variabler:</strong> '+(selected.length?selected.join(', '):'–')+'</p>'+
    '<p><strong>Bortsållade variabler:</strong> '+(excluded.length?excluded.join(', '):'inga')+'</p>'+
    '<p class="note"><strong>Elastic Net valde:</strong> '+(elastic.length?elastic.join(', '):'–')+
    '<br><strong>Backward-AIC valde:</strong> '+(backward.length?backward.join(', '):'–')+
    '<br><strong>Tematiskt urval:</strong> '+(thematic.length?thematic.join(', '):'–')+
    (themeMeta.n_themes!=null?'<br><strong>Antal kvalitativa teman:</strong> '+themeMeta.n_themes:'')+
    '<br><strong>Tidsbaserad korsvalidering:</strong> '+(temporal.length?temporal.join(', '):'–')+
    (cv.mean_rmse!=null?'<br><strong>Rolling-origin RMSE:</strong> '+fmt(cv.mean_rmse,2):'')+
    (cv.reason?'<br><strong>CV-status:</strong> '+cv.reason:'')+
    '</p>';

  const c=e.coefficients;
  Plotly.react('coefficients',[{
    y:c.map(d=>labels[d.feature]||d.feature),
    x:c.map(d=>d.standardized_coefficient),
    type:'bar',orientation:'h',
    customdata:c.map(d=>[d.coefficient,d.p_value]),
    hovertemplate:'%{y}<br>Standardiserad β=%{x:.3f}<br>Koefficient=%{customdata[0]:.3f}<br>p=%{customdata[1]:.3g}<extra></extra>'
  }],{
    margin:{t:20,l:245},
    xaxis:{title:'Standardiserad koefficient β',zeroline:true}
  },{responsive:true,displaylogo:false});

  Plotly.react('coefficientCI',[{
    y:c.map(d=>labels[d.feature]||d.feature),
    x:c.map(d=>d.coefficient),
    type:'scatter',mode:'markers',
    error_x:{
      type:'data',
      symmetric:false,
      array:c.map(d=>d.ci_high-d.coefficient),
      arrayminus:c.map(d=>d.coefficient-d.ci_low),
      visible:true
    },
    customdata:c.map(d=>d.p_value),
    hovertemplate:'%{y}<br>β=%{x:.3f}<br>p=%{customdata:.3g}<extra></extra>'
  }],{
    margin:{t:20,l:245},
    xaxis:{title:'Koefficient med 95 % konfidensintervall',zeroline:true}
  },{responsive:true,displaylogo:false});

  const vif=e.vif;
  Plotly.react('vifChart',[{
    y:vif.map(d=>labels[d.feature]||d.feature),
    x:vif.map(d=>d.vif),
    type:'bar',orientation:'h',
    hovertemplate:'%{y}<br>VIF=%{x:.2f}<extra></extra>'
  }],{
    margin:{t:20,l:245},
    xaxis:{title:'VIF'},
    shapes:[
      {type:'line',x0:5,x1:5,y0:-.5,y1:vif.length-.5,line:{dash:'dash'}},
      {type:'line',x0:10,x1:10,y0:-.5,y1:vif.length-.5,line:{dash:'dot'}}
    ]
  },{responsive:true,displaylogo:false});

  const d=diagnostics.filter(x=>x.window===selectedWindow);
  Plotly.react('residualChart',[{
    x:d.map(x=>x.fitted),
    y:d.map(x=>x.std_residual),
    text:d.map(x=>x.kommun+' · '+x.year),
    mode:'markers',type:'scatter',
    hovertemplate:'%{text}<br>Skattat=%{x:.2f}<br>Standardiserad residual=%{y:.2f}<extra></extra>'
  }],{
    margin:{t:20},
    xaxis:{title:'Skattade värden'},
    yaxis:{title:'Standardiserade residualer',zeroline:true}
  },{responsive:true,displaylogo:false});

  const q=qq.filter(x=>x.window===selectedWindow);
  const vals=q.flatMap(x=>[x.theoretical,x.sample]).filter(Number.isFinite);
  const lo=Math.min(...vals), hi=Math.max(...vals);
  Plotly.react('qqChart',[{
    x:q.map(x=>x.theoretical),
    y:q.map(x=>x.sample),
    mode:'markers',type:'scatter',
    hovertemplate:'Teoretisk=%{x:.2f}<br>Residual=%{y:.2f}<extra></extra>'
  }],{
    margin:{t:20},
    xaxis:{title:'Teoretiska normal-kvantiler'},
    yaxis:{title:'Standardiserade residualer'},
    shapes:[{type:'line',x0:lo,x1:hi,y0:lo,y1:hi,line:{dash:'dash'}}]
  },{responsive:true,displaylogo:false});
}

function renderValidation(){
  const rows=predictions.filter(d=>d.window===selectedWindow);
  if(!rows.length)return;
  const observed=rows.map(d=>d.inflyttning_per_1000);
  const predvals=rows.flatMap(d=>[d.pred_naiv,d.pred_ols,d.pred_ridge]);
  const vals=observed.concat(predvals).filter(Number.isFinite);
  const lo=Math.min(...vals), hi=Math.max(...vals);
  Plotly.react('validationChart',[
    {x:observed,y:rows.map(d=>d.pred_naiv),text:rows.map(d=>d.kommun),mode:'markers',name:'Naiv'},
    {x:observed,y:rows.map(d=>d.pred_ols),text:rows.map(d=>d.kommun),mode:'markers',name:'OLS'},
    {x:observed,y:rows.map(d=>d.pred_ridge),text:rows.map(d=>d.kommun),mode:'markers',name:'Ridge'}
  ],{
    margin:{t:20},
    xaxis:{title:'Observerat per 1 000'},
    yaxis:{title:'Predikterat per 1 000'},
    shapes:[{type:'line',x0:lo,x1:hi,y0:lo,y1:hi,line:{dash:'dash'}}]
  },{responsive:true,displaylogo:false});
}

function initMunicipality(){
  const s=document.getElementById('municipalitySelect');
  if(!s.options.length){
    const mun=[...new Map(panel.map(d=>[d.kommun_kod,d.kommun])).entries()].sort((a,b)=>a[1].localeCompare(b[1],'sv'));
    mun.forEach(([k,v])=>s.add(new Option(v,k)));
    const lulea=mun.find(x=>x[1]==='Luleå');
    if(lulea)s.value=lulea[0];
    s.addEventListener('change',renderMunicipality);
  }
}

function renderMunicipality(){
  const select=document.getElementById('municipalitySelect');
  if(!select||!select.value)return;
  const code=select.value;
  const rows=panel.filter(d=>d.kommun_kod===code).sort((a,b)=>a.year-b.year);
  const testPred=predictions.find(d=>d.window===selectedWindow&&d.kommun_kod===code);
  const traces=[{
    x:rows.map(d=>d.year),
    y:rows.map(d=>d.inflyttning_per_1000),
    mode:'lines+markers',
    name:'Observerad inflyttning'
  }];
  if(testPred){
    traces.push({
      x:[testPred.year],y:[testPred.pred_ols],
      mode:'markers',name:'OLS-prediktion',
      marker:{size:11,symbol:'diamond'}
    });
  }
  Plotly.react('municipalityChart',traces,{
    margin:{t:20},
    xaxis:{title:'År'},
    yaxis:{title:'Inflyttade per 1 000'}
  },{responsive:true,displaylogo:false});
}

load();
