const fmt1 = new Intl.NumberFormat('sv-SE',{maximumFractionDigits:1});
const fmt2 = new Intl.NumberFormat('sv-SE',{maximumFractionDigits:2});
let panel=[], model={}, predictions=[];

const labels={
  lag1_inflyttning_per_1000:'Inflyttning föregående år per 1 000',
  log_folkmangd:'Log folkmängd',
  befolkningstillvaxt_pct:'Befolkningstillväxt (%)',
  andel_20_34:'Andel 20–34 år (%)',
  lag1_inflyttare_medelalder:'Inflyttarnas medelålder föregående år'
};

async function load(){
  initTabs();
  try{
    const responses=await Promise.all([
      fetch('data/model.json',{cache:'no-store'}),
      fetch('data/panel.csv',{cache:'no-store'}),
      fetch('data/predictions.csv',{cache:'no-store'})
    ]);
    for(const r of responses){
      if(!r.ok) throw new Error('Analysdata saknas ännu ('+r.status+' '+r.url.split('/').pop()+'). GitHub Actions måste slutföras först.');
    }
    const [mText,pText,prText]=await Promise.all(responses.map(r=>r.text()));
    model=JSON.parse(mText);
    panel=d3.csvParse(pText,d3.autoType);
    predictions=d3.csvParse(prText,d3.autoType);
    renderOverview();
    initRelationships();
    renderModel();
    renderValidation();
    initMunicipality();
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
    b.classList.add('active'); document.getElementById(b.dataset.page).classList.add('active');
  }));
}

function metricCard(label,value){return '<div class="card"><div class="label">'+label+'</div><div class="value">'+value+'</div></div>'}

function renderOverview(){
  const best=Object.entries(model.models).sort((a,b)=>b[1].r2-a[1].r2)[0];
  document.getElementById('cards').innerHTML=[
    metricCard('Testår',model.test_year),
    metricCard('Kommun-år i träning',model.n_train.toLocaleString('sv-SE')),
    metricCard('Kommuner i test',model.n_test.toLocaleString('sv-SE')),
    metricCard('Bästa test-R²',fmt2.format(best[1].r2)),
    metricCard('Bästa modell',best[0].toUpperCase())
  ].join('');
  const names=['Naiv','OLS','Ridge'];
  Plotly.newPlot('modelCompare',[
    {x:names,y:[model.models.naive.r2,model.models.ols.r2,model.models.ridge.r2],type:'bar',name:'R²'}
  ],{margin:{t:20},yaxis:{title:'Out-of-sample R²'},xaxis:{title:'Modell'}},{responsive:true,displaylogo:false});
}

function initRelationships(){
  const x=document.getElementById('xvar');
  Object.entries(labels).forEach(([k,v])=>x.add(new Option(v,k)));
  const years=[...new Set(panel.map(d=>d.year))].sort((a,b)=>a-b);
  const y=document.getElementById('yearFilter'); y.add(new Option('Alla år','all'));
  years.forEach(v=>y.add(new Option(v,v)));
  x.value='lag1_inflyttning_per_1000'; y.value=model.test_year;
  x.addEventListener('change',renderScatter); y.addEventListener('change',renderScatter); renderScatter();
}

function renderScatter(){
  const key=document.getElementById('xvar').value, yf=document.getElementById('yearFilter').value;
  const rows=panel.filter(d=>Number.isFinite(d[key])&&Number.isFinite(d.inflyttning_per_1000)&&(yf==='all'||d.year===+yf));
  Plotly.newPlot('scatter',[{x:rows.map(d=>d[key]),y:rows.map(d=>d.inflyttning_per_1000),text:rows.map(d=>d.kommun+' · '+d.year),mode:'markers',type:'scatter',hovertemplate:'%{text}<br>x=%{x:.2f}<br>Inflyttning=%{y:.2f}<extra></extra>'}],
    {margin:{t:20},xaxis:{title:labels[key]},yaxis:{title:'Inflyttade per 1 000'}},{responsive:true,displaylogo:false});
}

function renderModel(){
  const c=model.ols_coefficients;
  Plotly.newPlot('coefficients',[{y:c.map(d=>labels[d.feature]||d.feature),x:c.map(d=>d.coefficient),type:'bar',orientation:'h'}],
    {margin:{t:20,l:230},xaxis:{title:'OLS-koefficient'}},{responsive:true,displaylogo:false});
}

function renderValidation(){
  Plotly.newPlot('validation',[
    {x:predictions.map(d=>d.inflyttning_per_1000),y:predictions.map(d=>d.pred_naiv),text:predictions.map(d=>d.kommun),mode:'markers',name:'Naiv'},
    {x:predictions.map(d=>d.inflyttning_per_1000),y:predictions.map(d=>d.pred_ols),text:predictions.map(d=>d.kommun),mode:'markers',name:'OLS'},
    {x:predictions.map(d=>d.inflyttning_per_1000),y:predictions.map(d=>d.pred_ridge),text:predictions.map(d=>d.kommun),mode:'markers',name:'Ridge'}
  ],{margin:{t:20},xaxis:{title:'Observerat per 1 000'},yaxis:{title:'Predikterat per 1 000'}},{responsive:true,displaylogo:false});
}

function initMunicipality(){
  const s=document.getElementById('municipalitySelect');
  const mun=[...new Map(panel.map(d=>[d.kommun_kod,d.kommun])).entries()].sort((a,b)=>a[1].localeCompare(b[1],'sv'));
  mun.forEach(([k,v])=>s.add(new Option(v,k)));
  const lulea=mun.find(x=>x[1]==='Luleå'); if(lulea)s.value=lulea[0];
  s.addEventListener('change',renderMunicipality); renderMunicipality();
}
function renderMunicipality(){
  const code=document.getElementById('municipalitySelect').value;
  const rows=panel.filter(d=>d.kommun_kod===code).sort((a,b)=>a.year-b.year);
  Plotly.newPlot('municipalityChart',[{x:rows.map(d=>d.year),y:rows.map(d=>d.inflyttning_per_1000),mode:'lines+markers',name:'Observerad inflyttning'}],
    {margin:{t:20},xaxis:{title:'År'},yaxis:{title:'Inflyttade per 1 000'}},{responsive:true,displaylogo:false});
}
load();
