const fmt0 = new Intl.NumberFormat('sv-SE',{maximumFractionDigits:0});
const fmt1 = new Intl.NumberFormat('sv-SE',{maximumFractionDigits:1});
const fmt2 = new Intl.NumberFormat('sv-SE',{maximumFractionDigits:2});
function fmt(value,digits=2){
  const n=Number(value);
  if(!Number.isFinite(n)) return '–';
  return new Intl.NumberFormat('sv-SE',{
    minimumFractionDigits:digits,
    maximumFractionDigits:digits
  }).format(n);
}
let panel=[], model={}, predictions=[], diagnostics=[], qq=[];
let selectedWindow=5;

const labels={
  lag1_inflyttning_per_1000:'Inflyttning föregående år per 1 000',
  lag1_utflyttning_per_1000:'Utflyttning föregående år per 1 000',
  lag1_inflyttning_18_23_per_1000:'Inflyttning 18–23 år föregående år per 1 000 i samma ålder',
  lag1_inflyttning_24_34_per_1000:'Inflyttning 24–34 år föregående år per 1 000 i samma ålder',
  lag1_inflyttning_35_49_per_1000:'Inflyttning 35–49 år föregående år per 1 000 i samma ålder',
  lag1_inflyttning_63_68_per_1000:'Inflyttning 63–68 år föregående år per 1 000 i samma ålder',
  lag1_inflyttning_70_79_per_1000:'Inflyttning 70–79 år föregående år per 1 000 i samma ålder',
  lag1_log_folkmangd:'Folkmängd (log), föregående år',
  lag1_befolkningstillvaxt_pct:'Befolkningstillväxt, föregående år (%)',
  lag1_andel_20_34:'Andel 20–34 år, föregående år (%)',
  lag1_inflyttare_medelalder:'Inflyttarnas medelålder föregående år',
  lag1_inkomst_tkr:'Genomsnittlig förvärvsinkomst 20–64 år, föregående år (tkr)',
  lag1_valdeltagande_pct:'Valdeltagande i riksdagsval, linjärt interpolerat, föregående år (%)',
  lag1_valdeltagande_gap_pp:'Riksdagsvaldeltagandeklyfta mellan valdistrikt, föregående år (procentenheter)',
  lag1_ekonomisk_standard_gap_pp:'Socioekonomisk klyfta mellan DeSO, föregående år (procentenheter)',
  lag1_bostader_per_1000:'Bostadsbestånd föregående år per 1 000 invånare',
  lag1_bostadsbestandsforandring_pct:'Förändring i bostadsbestånd föregående år (%)',
  lag1_fardigstallda_bostader_per_1000:'Färdigställda bostäder föregående år per 1 000 invånare',
  lag1_andel_hyresratt:'Andel hyresrätt föregående år (%)',
  lag1_andel_bostadsratt:'Andel bostadsrätt föregående år (%)',
  lag1_andel_smahus:'Andel småhus föregående år (%)',
  lag1_fritidshusandel_bland_smahus:'Fritidshusandel bland småhusliknande bostäder, föregående år (%)',
  lag1_brott_per_100000:'Anmälda brott per 100 000 invånare, föregående år',
  lag1_sysselsattningsgrad:'Sysselsättningsgrad 20–64 år, föregående år (%)',
  lag1_arbetsloshet:'Arbetslöshet 20–64 år, föregående år (%)',
  lag1_andel_eftergymnasial:'Andel eftergymnasialt utbildade 25–64 år, föregående år (%)',
  lag1_andel_studerande:'Andel studerande 20–64 år, föregående år (%)',
  lag1_kolada_idrott_deltagartillfallen:'Idrottsföreningsaktivitet 7–20 år, föregående år (deltagartillfällen/inv)',
  lag1_kolada_bibliotek_aktivitetstillfallen:'Biblioteksaktiviteter barn/unga, föregående år (per 1 000 inv 0–18 år)',
  lag1_kolada_kulturskola_andel:'Kulturskoledeltagande 6–15 år, föregående år (%)',
  lag1_andel_industri_bc:'Andel sysselsatta i B+C industri/gruvor, föregående år (%)',
  lag1_andel_hotell_restaurang_i:'Andel sysselsatta i I hotell/restaurang, föregående år (%)',
  lag1_andel_kultur_service_rstu:'Andel sysselsatta i R+S+T+U kultur/nöje/service, föregående år (%)',
  lag1_log_externa_fa_jobb_per_1000:'Regional arbetsmarknadsaccess (FA15), föregående år',
  lag1_andel_fa_arbetsplatser_i_egen_kommun:'Regional arbetsmotor: egen andel av FA-regionens arbetsplatser, föregående år (%)'
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
  renderAgeModels();
  renderRegressionEquations();
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

  const tm=e.theme_marginal_analysis||{};
  const trows=(tm.rows||[]).slice();
  if(trows.length){
    Plotly.react('themeMarginalChart',[{
      y:trows.map(d=>d.theme),
      x:trows.map(d=>d.delta_adjusted_r2),
      type:'bar',orientation:'h',
      customdata:trows.map(d=>[d.delta_aic,d.delta_rmse,(d.features||[]).map(f=>labels[f]||f).join(', ')]),
      hovertemplate:'%{y}<br>Δ justerat R²=%{x:.4f}<br>Δ AIC=%{customdata[0]:.1f}<br>Δ RMSE=%{customdata[1]:.3f}<br>%{customdata[2]}<extra></extra>'
    }],{
      margin:{t:20,l:220},
      xaxis:{title:'Förlust i justerat R² när temat tas bort',zeroline:true},
      yaxis:{autorange:'reversed'}
    },{responsive:true,displaylogo:false});

    document.getElementById('themeMarginalTable').innerHTML=
      '<table class="metric-table"><thead><tr><th>Tema</th><th>Variabel</th><th>Δ just. R²</th><th>Δ AIC</th><th>Δ RMSE</th></tr></thead><tbody>'+
      trows.map(d=>'<tr><td>'+d.theme+'</td><td>'+(d.features||[]).map(f=>labels[f]||f).join(', ')+'</td><td>'+fmt(d.delta_adjusted_r2,4)+'</td><td>'+fmt(d.delta_aic,1)+'</td><td>'+fmt(d.delta_rmse,3)+'</td></tr>').join('')+
      '</tbody></table>';
  } else {
    Plotly.purge('themeMarginalChart');
    document.getElementById('themeMarginalTable').innerHTML='<p class="note">Marginalanalys saknas för valt fönster.</p>';
  }

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

function renderLifeStageWinners(){
  const root=document.getElementById('lifeStageWinnerTable');
  if(!root) return;
  const models=model.age_group_models||{};
  const keys=['18_23','24_34','35_49','63_68','70_79'];
  const ageLabels=keys.map(k=>(models[k]&&models[k].label)||k.replace('_','–')+' år');

  const winnerMaps={};
  const themeSet=new Set();
  keys.forEach(k=>{
    const sel=(((models[k]||{}).explanation||{}).variable_selection||{}).thematic_selection||{};
    const themes=sel.themes||{};
    winnerMaps[k]=themes;
    Object.keys(themes).forEach(t=>{ if(t!=='Historisk flyttdynamik') themeSet.add(t); });
  });

  const themes=Array.from(themeSet).sort((a,b)=>a.localeCompare(b,'sv'));
  const shortLabel=f=>(labels[f]||f)
    .replace(', föregående år','')
    .replace(' föregående år','')
    .replace('Genomsnittlig ','')
    .replace(/\s+/g,' ')
    .trim();

  root.innerHTML=
    '<table class="metric-table winner-table"><thead><tr><th>Tema</th>'+
    ageLabels.map(x=>'<th>'+x+'</th>').join('')+
    '</tr></thead><tbody>'+
    themes.map(theme=>'<tr><td><strong>'+theme+'</strong></td>'+
      keys.map(k=>{
        const f=winnerMaps[k]?.[theme];
        return '<td>'+(f?shortLabel(f):'<span class="muted">–</span>')+'</td>';
      }).join('')+
    '</tr>').join('')+
    '</tbody></table>';
}


function renderLifeStageHeatmap(){
  const models=model.age_group_models||{};
  const keys=['18_23','24_34','35_49','63_68','70_79'];
  const labelsAge=keys.map(k=>(models[k]&&models[k].label)||k.replace('_','–')+' år');
  const mode=(document.getElementById('lifeStageMetric')||{}).value||'structural';

  const maps={};
  const themeSet=new Set();
  keys.forEach(k=>{
    const rows=(((models[k]||{}).explanation||{}).theme_marginal_analysis||{}).rows||[];
    maps[k]=new Map(rows.map(r=>[r.theme,r]));
    rows.forEach(r=>themeSet.add(r.theme));
  });

  let themes=Array.from(themeSet);
  if(mode==='structural') themes=themes.filter(t=>t!=='Historisk flyttdynamik');

  // Order themes by their strongest observed marginal contribution across life stages.
  themes.sort((a,b)=>{
    const ma=Math.max(...keys.map(k=>maps[k].get(a)?.delta_adjusted_r2??-Infinity));
    const mb=Math.max(...keys.map(k=>maps[k].get(b)?.delta_adjusted_r2??-Infinity));
    return mb-ma;
  });

  const rawZ=themes.map(t=>keys.map(k=>{
    const r=maps[k].get(t);
    return r ? r.delta_adjusted_r2 : null;
  }));
  // Compress the colour scale so structural differences remain visible even
  // when historical persistence is shown. Hover/text always use raw delta R².
  const colorZ=rawZ.map(row=>row.map(v=>v==null?null:Math.sign(v)*Math.sqrt(Math.abs(v))));
  const custom=themes.map(t=>keys.map(k=>{
    const r=maps[k].get(t);
    const sel=(((models[k]||{}).explanation||{}).variable_selection||{}).thematic_selection||{};
    const winner=(sel.themes||{})[t];
    return r ? [r.delta_adjusted_r2,r.delta_aic,r.delta_rmse,winner?(labels[winner]||winner):'–'] : [null,null,null,'–'];
  }));
  const text=rawZ.map(row=>row.map(v=>v==null?'':(v>=0?'+':'')+v.toFixed(4)));

  Plotly.react('lifeStageHeatmap',[{
    x:labelsAge,
    y:themes,
    z:colorZ,
    customdata:custom,
    text:text,
    texttemplate:'%{text}',
    type:'heatmap',
    hoverongaps:false,
    colorbar:{title:'√|Δ just. R²|'},
    hovertemplate:'%{y}<br>%{x}<br>Vald variabel: %{customdata[3]}<br>Δ justerat R²=%{customdata[0]:.4f}<br>Δ AIC=%{customdata[1]:.1f}<br>Δ RMSE=%{customdata[2]:.3f}<extra></extra>'
  }],{
    margin:{t:20,l:210,b:70},
    xaxis:{side:'bottom'},
    yaxis:{autorange:'reversed'},
    annotations:[],
    height:Math.max(420,90+themes.length*34)
  },{responsive:true,displaylogo:false});
}

function renderAgeModels(){
  const root=document.getElementById('ageModels');
  if(!root) return;
  const models=model.age_group_models||{};
  const keys=['18_23','24_34','35_49','63_68','70_79'];
  const html=keys.map(key=>{
    const m=models[key];
    if(!m) return '<div class="panel"><h3>'+key.replace('_','–')+' år</h3><p class="note">Data saknas.</p></div>';
    if(m.error) return '<div class="panel"><h3>'+m.label+'</h3><p class="note">'+m.error+'</p></div>';
    const e=m.explanation||{};
    const marg=(e.theme_marginal_analysis&&e.theme_marginal_analysis.rows)||[];
    const top=marg.slice(0,6);
    const v=m.validation&&m.validation.models;
    return '<div class="panel">'+
      '<h3>'+m.label+' – '+m.interpretation+'</h3>'+
      '<p class="note">'+m.rate_definition+'</p>'+
      '<div class="cards">'+
        metricCard('Justerat R²',fmt2.format(e.adjusted_r2))+
        metricCard('Observationer',fmt0.format(e.n_obs))+
        metricCard('Valda variabler',fmt0.format((e.selected_features||[]).length))+
        (v?metricCard('Ridge R²',fmt2.format(v.ridge.r2)):'')+
        (v&&Number.isFinite(v.ridge?.r2)&&Number.isFinite(v.naive?.r2)
          ? metricCard('Ridge − naiv',fmt(v.ridge.r2-v.naive.r2,3),'skillnad i test-R²')
          : '')+
      '</div>'+
      '<table class="metric-table"><thead><tr><th>Tema</th><th>Δ just. R²</th><th>Δ AIC</th><th>Δ RMSE</th></tr></thead><tbody>'+
      top.map(d=>'<tr><td>'+d.theme+'</td><td>'+fmt(d.delta_adjusted_r2,4)+'</td><td>'+fmt(d.delta_aic,1)+'</td><td>'+fmt(d.delta_rmse,3)+'</td></tr>').join('')+
      '</tbody></table>'+
      '</div>';
  }).join('');
  root.innerHTML=html;
  renderLifeStageHeatmap();
  renderLifeStageWinners();
}


function renderRegressionEquations(){
  const root=document.getElementById('regressionEquations');
  if(!root) return;
  const models=model.age_group_models||{};
  const keys=['18_23','24_34','35_49','63_68','70_79'];

  const targetLabels={
    '18_23':'Inflyttning 18–23 år per 1 000 invånare 18–23 år',
    '24_34':'Inflyttning 24–34 år per 1 000 invånare 24–34 år',
    '35_49':'Inflyttning 35–49 år per 1 000 invånare 35–49 år',
    '63_68':'Inflyttning 63–68 år per 1 000 invånare 63–68 år',
    '70_79':'Inflyttning 70–79 år per 1 000 invånare 70–79 år'
  };

  root.innerHTML=keys.map(key=>{
    const m=models[key];
    if(!m||m.error) return '<div class="panel"><h3>'+key.replace('_','–')+' år</h3><p class="note">Ekvationen saknas tills modellen är byggd.</p></div>';
    const e=m.explanation||{};
    const intercept=Number(e.intercept);
    const terms=(e.coefficients||[]).map(c=>{
      const coef=Number(c.coefficient);
      const sign=coef>=0?' + ':' − ';
      return '<div class="eq-term"><span class="eq-sign">'+sign+'</span><span class="eq-coef">'+fmt(Math.abs(coef),4)+'</span> × <span class="eq-var">'+(labels[c.feature]||c.feature)+'</span></div>';
    }).join('');
    const years=(e.year_effect_coefficients||[]);
    const yearText=years.length
      ? years.map(d=>d.year+': '+(Number(d.coefficient)>=0?'+':'')+fmt(d.coefficient,4)).join(' · ')
      : 'inga separata årsdummies';

    return '<div class="panel equation-panel">'+
      '<h3>'+m.label+' – '+m.interpretation+'</h3>'+
      '<div class="equation-grid">'+
        '<div class="equation-box">'+
          '<div class="equation-target">'+targetLabels[key]+' =</div>'+
          '<div class="eq-term"><span class="eq-coef">'+fmt(intercept,4)+'</span> <span class="eq-var">intercept</span></div>'+
          terms+
          '<div class="eq-term"><span class="eq-sign"> + </span><span class="eq-var">årseffekter</span></div>'+
          '<div class="note equation-years"><strong>Årseffekter:</strong> '+yearText+'</div>'+
        '</div>'+
        '<div class="equation-stats">'+
          metricCard('R²',fmt(e.r2,3))+
          metricCard('Justerat R²',fmt(e.adjusted_r2,3))+
          metricCard('Observationer',fmt0.format(e.n_obs))+
        '</div>'+
      '</div>'+
      '</div>';
  }).join('');
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

document.getElementById('lifeStageMetric')?.addEventListener('change',renderLifeStageHeatmap);
