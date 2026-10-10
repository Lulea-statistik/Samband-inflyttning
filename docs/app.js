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
let panel=[], rootModel={}, model={}, predictions=[], diagnostics=[], qq=[];
let selectedWindow=5;
let selectedModelVariant='forecast';
let selectedGeography='sweden';

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
  lag1_sysselsatta_arbetsstalle_forandring_pct:'Förändring sysselsatta efter arbetsställets belägenhet, föregående år (%)',
  lag1_sysselsatta_bostad_forandring_pct:'Förändring sysselsatta efter bostadens belägenhet, föregående år (%)',
  lag1_sysselsatta_arbetsstalle_sasongsvariation_pct:'Månadsvariation sysselsatta efter arbetsställets belägenhet, föregående år (%)',
  lag1_sysselsatta_bostad_sasongsvariation_pct:'Månadsvariation sysselsatta efter bostadens belägenhet, föregående år (%)',
  lag1_andel_eftergymnasial:'Andel eftergymnasialt utbildade 25–64 år, föregående år (%)',
  lag1_andel_studerande:'Andel studerande 20–64 år, föregående år (%)',
  lag1_kolada_lok_foreningar_per_10000:'Idrottsföreningar med LOK-stöd, föregående år (antal/10 000 inv)',
  lag1_kolada_flickdominerade_idrottsforeningar_andel:'Idrottsföreningar med flickdominerad verksamhet, föregående år (%)',
  lag1_kolada_utbetalt_lok_stod_kr_per_inv:'Utbetalt LOK-stöd till idrottsföreningar, föregående år (kr/inv)',
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
    rootModel=JSON.parse(mText);
    model=rootModel;
    panel=d3.csvParse(pText,d3.autoType);
    predictions=d3.csvParse(prText,d3.autoType);
    diagnostics=d3.csvParse(dText,d3.autoType);
    qq=d3.csvParse(qText,d3.autoType);
    selectedWindow=Number(model.default_window||5);
    initGeographySelector();
    initModelVariantSelector();
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

function initGeographySelector(){
  const s=document.getElementById('geographySelect');
  if(!s) return;
  s.value=selectedGeography;
  s.addEventListener('change',()=>{
    selectedGeography=s.value;
    renderAll();
    renderScatter();
  });
}

function initModelVariantSelector(){
  const s=document.getElementById('modelVariantSelect');
  if(!s) return;
  s.value=selectedModelVariant;
  s.addEventListener('change',()=>{
    selectedModelVariant=s.value;
    model = selectedModelVariant==='demographic_blind'
      ? (rootModel.model_variants?.demographic_blind || rootModel)
      : rootModel;
    selectedWindow=Number(model.default_window||5);
    const ws=document.getElementById('windowSelect');
    if(ws) ws.value=String(selectedWindow);
    renderAll();
  });
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

function observedModelYears(){
  const w=wdata();
  const e=w?.explanation;
  if(!e) return [];
  const sampleFeatures=model.features||e.selected_features||[];
  return [...new Set(panel
    .filter(r=>Number(r.year)>=Number(e.start_year)&&Number(r.year)<=Number(e.end_year)
      && Number.isFinite(Number(r[model.target||'inflyttning_per_1000']))
      && sampleFeatures.every(f=>Number.isFinite(Number(r[f]))))
    .map(r=>Number(r.year)))]
    .sort((a,b)=>a-b);
}

function renderAll(){
  const w=wdata();
  if(!w) return showLoadError(new Error('Modellresultat saknas för '+selectedWindow+' års analysperiod.'));
  const e=w.explanation, v=w.validation;
  const variantMeta = rootModel.model_variant_metadata?.[selectedModelVariant] || {};
  const variantTitle=document.getElementById('variantPurposeTitle');
  const variantText=document.getElementById('variantPurposeText');
  if(variantTitle) variantTitle.textContent=variantMeta.label || model.model_label || 'Modell';
  if(variantText){
    let txt=variantMeta.purpose || '';
    if(selectedModelVariant==='demographic_blind'){
      txt += ' Kommunstorlek är tillåten som strukturell kontroll. Bostads- och arbetsmarknadsförändringar får ingå men ska tolkas som samband, inte säkra orsakseffekter.';
    }
    variantText.textContent=txt;
  }
  const observedYears=observedModelYears();
  const observedRange=observedYears.length
    ? observedYears[0]+'–'+observedYears[observedYears.length-1]
    : e.start_year+'–'+e.end_year;
  document.getElementById('windowDescription').textContent=
    (variantMeta.label || model.model_label || 'Modell')+': '+observedRange+
    ' · validering: '+v.train_start_year+'–'+v.train_end_year+' → test '+v.test_year;
  renderGeographyContext();
  renderOverview();
  renderVariantComparison();
  renderR2ContributionProfile();
  renderLuleaView();
  renderPublicPage();
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
    metricCard('Modell',selectedModelVariant==='demographic_blind'?'Demografiskt blind':'Prognos'),
    metricCard('Förklaringsperiod',(()=>{
      const ys=observedModelYears();
      return ys.length?ys[0]+'–'+ys[ys.length-1]:e.start_year+'–'+e.end_year;
    })()),
    metricCard('Kommun-år',fmt0.format(e.n_obs)),
    metricCard('Kommuner',fmt0.format(e.n_municipalities)),
    metricCard('R²',fmt2.format(e.r2)),
    metricCard('Justerat R²',fmt2.format(e.adjusted_r2)),
    metricCard('Bästa test-R²',fmt2.format(best[1].r2),best[0].toUpperCase()+' · test '+v.test_year)
  ].join('');

  const naiveLabel = selectedModelVariant==='demographic_blind'
    ? 'Naiv historik (extern referens)'
    : 'Naiv';
  Plotly.react('modelCompare',[{
    x:[naiveLabel,'OLS','Ridge'],
    y:[v.models.naive.r2,v.models.ols.r2,v.models.ridge.r2],
    type:'bar',
    name:'Out-of-sample R²',
    hovertemplate:'%{x}<br>R²=%{y:.3f}<extra></extra>'
  }],{
    margin:{t:20},
    yaxis:{title:'Out-of-sample R²'},
    xaxis:{title:'Modell'},
    annotations:selectedModelVariant==='demographic_blind' ? [{
      text:'Naiv historik använder föregående års inflyttning och är endast benchmark – den ingår inte i den demografiskt blinda modellen.',
      xref:'paper',yref:'paper',x:0,y:1.14,showarrow:false,align:'left',font:{size:12}
    }] : []
  },{responsive:true,displaylogo:false});
}

function renderVariantComparison(){
  const root=document.getElementById('variantComparison');
  if(!root) return;
  const forecast=rootModel.windows?.[String(selectedWindow)];
  const blind=rootModel.model_variants?.demographic_blind?.windows?.[String(selectedWindow)];
  if(!forecast||!blind){
    root.innerHTML='<p class="note">Jämförelsedata saknas för valt analysfönster.</p>';
    return;
  }
  const rows=[
    {
      label:'Prognosmodell',
      adj:forecast.explanation?.adjusted_r2,
      test:forecast.validation?.models?.ridge?.r2,
      rmse:forecast.validation?.models?.ridge?.rmse
    },
    {
      label:'Demografiskt blind strukturmodell',
      adj:blind.explanation?.adjusted_r2,
      test:blind.validation?.models?.ridge?.r2,
      rmse:blind.validation?.models?.ridge?.rmse
    }
  ];
  Plotly.react(root,[{
    x:rows.map(d=>d.label),
    y:rows.map(d=>d.test),
    customdata:rows.map(d=>[d.adj,d.rmse]),
    type:'bar',
    name:'Ridge test-R²',
    hovertemplate:'%{x}<br>Test-R²=%{y:.3f}<br>Justerat R² i förklaringsmodellen=%{customdata[0]:.3f}<br>Test-RMSE=%{customdata[1]:.2f}<extra></extra>'
  }],{
    margin:{t:20,b:100},
    yaxis:{title:'Out-of-sample R²'},
    xaxis:{title:''}
  },{responsive:true,displaylogo:false});
}


function variantWindow(variantId){
  if(variantId==='demographic_blind'){
    return rootModel.model_variants?.demographic_blind?.windows?.[String(selectedWindow)];
  }
  return rootModel.windows?.[String(selectedWindow)];
}

function marginalThemeMap(w){
  const rows=w?.explanation?.theme_marginal_analysis?.rows||[];
  return new Map(rows.map(d=>[d.theme,d]));
}

function renderR2ContributionProfile(){
  const root=document.getElementById('r2ContributionProfile');
  if(!root) return;
  const fw=variantWindow('forecast');
  const bw=variantWindow('demographic_blind');
  if(!fw||!bw){
    root.innerHTML='<p class="note">Bidragsdata saknas för valt analysfönster.</p>';
    return;
  }
  const fm=marginalThemeMap(fw), bm=marginalThemeMap(bw);
  const themes=[...new Set([...fm.keys(),...bm.keys()])];
  themes.sort((a,b)=>{
    const aa=Math.max(fm.get(a)?.delta_adjusted_r2??0,bm.get(a)?.delta_adjusted_r2??0);
    const bb=Math.max(fm.get(b)?.delta_adjusted_r2??0,bm.get(b)?.delta_adjusted_r2??0);
    return aa-bb;
  });
  Plotly.react(root,[
    {
      y:themes,
      x:themes.map(t=>fm.get(t)?.delta_adjusted_r2??0),
      type:'bar',orientation:'h',name:'Prognosmodell',
      customdata:themes.map(t=>[(fm.get(t)?.features||[]).map(f=>labels[f]||f).join(', ')]),
      hovertemplate:'%{y}<br>Prognosmodell: Δ justerat R²=%{x:.4f}<br>%{customdata[0]}<extra></extra>'
    },
    {
      y:themes,
      x:themes.map(t=>bm.get(t)?.delta_adjusted_r2??0),
      type:'bar',orientation:'h',name:'Demografiskt blind',
      customdata:themes.map(t=>[(bm.get(t)?.features||[]).map(f=>labels[f]||f).join(', ')]),
      hovertemplate:'%{y}<br>Blind modell: Δ justerat R²=%{x:.4f}<br>%{customdata[0]}<extra></extra>'
    }
  ],{
    barmode:'group',
    margin:{t:35,l:220,b:55},
    xaxis:{title:'Förlust i justerat R² när temat tas bort',zeroline:true},
    yaxis:{automargin:true},
    legend:{orientation:'h',y:1.08}
  },{responsive:true,displaylogo:false});
}


function renderGeographyContext(){
  const sw=document.getElementById('swedenOverview');
  const lu=document.getElementById('luleaOverview');
  if(sw) sw.hidden=selectedGeography!=='sweden';
  if(lu) lu.hidden=selectedGeography!=='lulea';

  const lead=document.querySelector('#overview > .lead');
  if(lead){
    lead.innerHTML=selectedGeography==='lulea'
      ? 'Luleå-vyn använder <strong>Sverigemodellen som referens</strong> och bryter ned varför Luleå avviker från genomsnittet bland svenska kommuner, samt hur den modellberäknade avvikelsen förändras över tid.'
      : 'Rapporten skiljer nu på två modeller. <strong>Prognosmodellen</strong> får använda historisk demografi om det förbättrar träffsäkerheten. <strong>Den demografiskt blinda strukturmodellen</strong> förbjuder historisk migration, befolkningstillväxt, åldersstruktur och inflyttarprofil som förklaringsvariabler, men tillåter kommunstorlek samt strukturella bostads-, arbetsmarknads-, ekonomiska och geografiska variabler.';
  }

  const technicalNote=document.getElementById('windowDescription');
  const methodNote=document.getElementById('geographyMethodNote');
  if(technicalNote && selectedGeography==='lulea'){
    technicalNote.textContent+=' · Luleå-vyn använder denna nationella modell som referens';
  }
  if(methodNote){
    methodNote.textContent=selectedGeography==='lulea'
      ? 'Tekniska regressions-, ålders- och valideringsflikar visar Sverigemodellen som används för att tolka Luleå.'
      : '';
  }
}

function meanFinite(rows,key){
  const vals=rows.map(r=>Number(r[key])).filter(Number.isFinite);
  return vals.length ? vals.reduce((a,b)=>a+b,0)/vals.length : NaN;
}

function luleaAnalysis(){
  const w=wdata();
  const e=w?.explanation;
  if(!e) return null;
  const features=e.selected_features||[];
  const sampleFeatures=model.features||features;
  const coeffMap=new Map((e.coefficients||[]).map(d=>[d.feature,Number(d.coefficient)]));
  const themeMap=new Map();
  (e.theme_marginal_analysis?.rows||[]).forEach(row=>{
    (row.features||[]).forEach(f=>themeMap.set(f,row.theme));
  });
  features.forEach(f=>{ if(!themeMap.has(f)) themeMap.set(f,labels[f]||f); });
  const yearEffects=new Map((e.year_effect_coefficients||[]).map(d=>[Number(d.year),Number(d.coefficient)]));
  const intercept=Number(e.intercept)||0;

  const out=[];
  const years=observedModelYears();
  for(const year of years){
    const yearRows=panel.filter(r=>
      Number(r.year)===Number(year) &&
      Number.isFinite(Number(r.inflyttning_per_1000)) &&
      sampleFeatures.every(f=>Number.isFinite(Number(r[f])))
    );
    const lu=yearRows.find(r=>String(r.kommun_kod)==='2580');
    if(!lu||!yearRows.length) continue;

    const means={};
    features.forEach(f=>means[f]=meanFinite(yearRows,f));
    const nationalMean=meanFinite(yearRows,'inflyttning_per_1000');
    let predictedLulea=intercept+(yearEffects.get(Number(year))||0);
    let predictedMean=intercept+(yearEffects.get(Number(year))||0);
    const byTheme={};

    features.forEach(f=>{
      const beta=coeffMap.get(f)||0;
      const xv=Number(lu[f]);
      const xm=Number(means[f]);
      predictedLulea+=beta*xv;
      predictedMean+=beta*xm;
      const contribution=beta*(xv-xm);
      const theme=themeMap.get(f)||f;
      byTheme[theme]=(byTheme[theme]||0)+contribution;
    });

    out.push({
      year:Number(year),
      actual:Number(lu.inflyttning_per_1000),
      nationalMean,
      actualGap:Number(lu.inflyttning_per_1000)-nationalMean,
      predictedLulea,
      predictedMean,
      predictedGap:predictedLulea-predictedMean,
      byTheme
    });
  }
  return {rows:out,features,explanation:e};
}

function renderLuleaView(){
  if(selectedGeography!=='lulea') return;
  const a=luleaAnalysis();
  if(!a||!a.rows.length) return;
  const rows=a.rows;
  const first=rows[0], last=rows[rows.length-1];

  const cards=document.getElementById('luleaCards');
  if(cards){
    cards.innerHTML=[
      metricCard('Luleå '+last.year,fmt(last.actual,1),'inflyttade per 1 000'),
      metricCard('Sverigemedel '+last.year,fmt(last.nationalMean,1),'kommunmedel per 1 000'),
      metricCard('Faktiskt gap',((last.actualGap>=0?'+':'')+fmt(last.actualGap,1)),'Luleå minus kommunmedel'),
      metricCard('Modellberäknat gap',((last.predictedGap>=0?'+':'')+fmt(last.predictedGap,1)),'utifrån vald modell')
    ].join('');
  }

  Plotly.react('luleaDevelopmentChart',[
    {
      x:rows.map(d=>d.year),y:rows.map(d=>d.actual),
      mode:'lines+markers',type:'scatter',name:'Luleå – faktisk',
      hovertemplate:'%{x}<br>Luleå faktisk=%{y:.1f}<extra></extra>'
    },
    {
      x:rows.map(d=>d.year),y:rows.map(d=>d.nationalMean),
      mode:'lines+markers',type:'scatter',name:'Sverige – kommunmedel',
      hovertemplate:'%{x}<br>Kommunmedel=%{y:.1f}<extra></extra>'
    },
    {
      x:rows.map(d=>d.year),y:rows.map(d=>d.predictedLulea),
      mode:'lines+markers',type:'scatter',name:'Luleå – modellskattad',
      line:{dash:'dash'},
      hovertemplate:'%{x}<br>Modellskattad Luleå=%{y:.1f}<extra></extra>'
    }
  ],{
    margin:{t:25,b:55,l:70,r:30},
    xaxis:{title:'År',dtick:1},
    yaxis:{title:'Inflyttade per 1 000'},
    legend:{orientation:'h',y:1.12}
  },{responsive:true,displaylogo:false});

  const latestContrib=Object.entries(last.byTheme)
    .map(([theme,value])=>({theme,value}))
    .filter(d=>Math.abs(d.value)>1e-9)
    .sort((a,b)=>a.value-b.value);
  Plotly.react('luleaLatestContributions',[{
    y:latestContrib.map(d=>d.theme),
    x:latestContrib.map(d=>d.value),
    type:'bar',orientation:'h',
    text:latestContrib.map(d=>(d.value>=0?'+':'')+fmt(d.value,2)),
    textposition:'outside',
    hovertemplate:'%{y}<br>Bidrag till Luleå–Sverige-gapet=%{x:.2f} per 1 000<extra></extra>'
  }],{
    margin:{t:25,l:210,r:75,b:55},
    xaxis:{title:'Bidrag till modellberäknat gap, inflyttade per 1 000',zeroline:true},
    yaxis:{automargin:true},
    showlegend:false
  },{responsive:true,displaylogo:false});

  const themes=[...new Set([...Object.keys(first.byTheme),...Object.keys(last.byTheme)])];
  const changes=themes.map(theme=>({
    theme,
    value:(last.byTheme[theme]||0)-(first.byTheme[theme]||0)
  })).sort((a,b)=>a.value-b.value);
  const changeRoot=document.getElementById('luleaContributionChange');
  if(rows.length<2){
    changeRoot.innerHTML='<p class="note">Välj minst två års analysperiod för att visa förändringen över tid.</p>';
  }else{
    Plotly.react(changeRoot,[{
      y:changes.map(d=>d.theme),
      x:changes.map(d=>d.value),
      type:'bar',orientation:'h',
      text:changes.map(d=>(d.value>=0?'+':'')+fmt(d.value,2)),
      textposition:'outside',
      hovertemplate:'%{y}<br>Förändrat modellbidrag=%{x:.2f} per 1 000<extra></extra>'
    }],{
      margin:{t:25,l:210,r:75,b:55},
      xaxis:{title:'Förändring i bidrag från '+first.year+' till '+last.year,zeroline:true},
      yaxis:{automargin:true},
      showlegend:false
    },{responsive:true,displaylogo:false});
  }
}

function renderPublicPage(){
  if(selectedGeography==='lulea'){
    const a=luleaAnalysis();
    if(!a||!a.rows.length) return;
    const rows=a.rows, first=rows[0], last=rows[rows.length-1];
    const eyebrow=document.getElementById('publicEyebrow');
    const title=document.getElementById('publicHeroTitle');
    const txt=document.getElementById('publicHeroText');
    if(eyebrow) eyebrow.textContent='Luleås inflyttning i ett Sverigeperspektiv';
    if(title) title.textContent='Varför utvecklas Luleås inflyttning som den gör?';
    if(txt) txt.innerHTML='Samma modell som används för Sveriges kommuner används här som <strong>referensram för Luleå</strong>. Vi jämför Luleås egenskaper med genomsnittskommunen och ser vilka teman som drar den modellberäknade skillnaden uppåt eller nedåt.';
    const e1=document.getElementById('publicChart1Eyebrow'), t1=document.getElementById('publicChart1Title'), p1=document.getElementById('publicChart1Text');
    const e2=document.getElementById('publicChart2Eyebrow'), t2=document.getElementById('publicChart2Title'), p2=document.getElementById('publicChart2Text');
    const e3=document.getElementById('publicChart3Eyebrow'), t3=document.getElementById('publicChart3Title'), p3=document.getElementById('publicChart3Text');
    if(e1) e1.textContent='Luleå jämfört med genomsnittskommunen';
    if(t1) t1.textContent='Utvecklingen kan följas år för år';
    if(p1) p1.textContent='Den faktiska inflyttningen i Luleå jämförs med kommunmedlet och den nivå som Sverigemodellen skattar för Luleå.';
    if(e2) e2.textContent='Vad gör Luleå annorlunda?';
    if(t2) t2.textContent='Teman som drar Luleå uppåt eller nedåt';
    if(p2) p2.textContent='Bidragen visar hur Luleås egenskaper, relativt genomsnittskommunen samma år, påverkar den modellberäknade skillnaden i inflyttning.';
    if(e3) e3.textContent='Förändring över tid';
    if(t3) t3.textContent='Vilka drivkrafter har stärkts eller försvagats?';
    if(p3) p3.textContent='Här jämförs varje temas bidrag i början och slutet av analysperioden. Det visar vad som har förändrats i Luleås modellprofil.';

    const kpis=document.getElementById('publicKpis');
    if(kpis) kpis.innerHTML=[
      '<article><span>Luleå '+last.year+'</span><strong>'+fmt(last.actual,1)+'</strong><small>inflyttade per 1 000</small></article>',
      '<article><span>Kommunmedel '+last.year+'</span><strong>'+fmt(last.nationalMean,1)+'</strong><small>inflyttade per 1 000</small></article>',
      '<article><span>Modellberäknat gap</span><strong>'+(last.predictedGap>=0?'+':'')+fmt(last.predictedGap,1)+'</strong><small>Luleå minus kommunmedel</small></article>'
    ].join('');

    Plotly.react('publicModelR2',[
      {x:rows.map(d=>d.year),y:rows.map(d=>d.actual),mode:'lines+markers',type:'scatter',name:'Luleå'},
      {x:rows.map(d=>d.year),y:rows.map(d=>d.nationalMean),mode:'lines+markers',type:'scatter',name:'Kommunmedel'},
      {x:rows.map(d=>d.year),y:rows.map(d=>d.predictedLulea),mode:'lines+markers',type:'scatter',name:'Modellskattad Luleå',line:{dash:'dash'}}
    ],{
      margin:{t:20,b:55,l:65,r:30},
      yaxis:{title:'Inflyttade per 1 000'},
      xaxis:{title:'År',dtick:1},
      legend:{orientation:'h',y:1.12}
    },{responsive:true,displaylogo:false});

    const contrib=Object.entries(last.byTheme)
      .map(([theme,value])=>({theme,value}))
      .sort((a,b)=>a.value-b.value);
    Plotly.react('publicBlindDrivers',[{
      y:contrib.map(d=>d.theme),x:contrib.map(d=>d.value),
      type:'bar',orientation:'h',
      text:contrib.map(d=>(d.value>=0?'+':'')+fmt(d.value,2)),
      textposition:'outside',
      hovertemplate:'%{y}<br>Bidrag=%{x:.2f} per 1 000<extra></extra>'
    }],{
      margin:{t:20,l:190,r:70,b:55},
      xaxis:{title:'Bidrag till Luleå–Sverige-gapet',zeroline:true},
      yaxis:{automargin:true},showlegend:false
    },{responsive:true,displaylogo:false});

    const themes=[...new Set([...Object.keys(first.byTheme),...Object.keys(last.byTheme)])];
    const changes=themes.map(theme=>({theme,value:(last.byTheme[theme]||0)-(first.byTheme[theme]||0)})).sort((a,b)=>a.value-b.value);
    Plotly.react('publicAgeComparison',[{
      y:changes.map(d=>d.theme),x:changes.map(d=>d.value),
      type:'bar',orientation:'h',
      text:changes.map(d=>(d.value>=0?'+':'')+fmt(d.value,2)),
      textposition:'outside',
      hovertemplate:'%{y}<br>Förändrat bidrag=%{x:.2f} per 1 000<extra></extra>'
    }],{
      margin:{t:20,l:190,r:70,b:55},
      xaxis:{title:'Förändrat bidrag '+first.year+'–'+last.year,zeroline:true},
      yaxis:{automargin:true},showlegend:false
    },{responsive:true,displaylogo:false});
    return;
  }

  const eyebrow=document.getElementById('publicEyebrow');
  const title=document.getElementById('publicHeroTitle');
  const txt=document.getElementById('publicHeroText');
  if(eyebrow) eyebrow.textContent='Inflyttning till svenska kommuner';
  if(title) title.textContent='Två frågor kräver två olika modeller';
  if(txt) txt.innerHTML='En modell försöker <strong>förutsäga nästa års inflyttning så träffsäkert som möjligt</strong>. Den andra försöker förstå <strong>vilka strukturella egenskaper som hänger ihop med inflyttning</strong> utan att använda tidigare migration eller befolkningstillväxt som genväg.';
  const e1=document.getElementById('publicChart1Eyebrow'), t1=document.getElementById('publicChart1Title'), p1=document.getElementById('publicChart1Text');
  const e2=document.getElementById('publicChart2Eyebrow'), t2=document.getElementById('publicChart2Title'), p2=document.getElementById('publicChart2Text');
  const e3=document.getElementById('publicChart3Eyebrow'), t3=document.getElementById('publicChart3Title'), p3=document.getElementById('publicChart3Text');
  if(e1) e1.textContent='Hur mycket variation fångas?';
  if(t1) t1.textContent='Historisk demografi ger en stor prognosfördel';
  if(p1) p1.textContent='Test-R² visar hur väl modellerna fångar variationen i ett år som inte användes när modellen skattades. Det är inte samma sak som “procent rätt”.';
  if(e2) e2.textContent='Vad träder fram utan demografisk historik?';
  if(t2) t2.textContent='Bostäder, kommunstorlek och humankapital blir tydligare';
  if(p2) p2.textContent='Här visas de teman där strukturmodellen tappar mest justerat R² när temat tas bort. Ett större tapp betyder mer självständigt förklaringsvärde inom modellen.';
  if(e3) e3.textContent='Olika livsfaser';
  if(t3) t3.textContent='Historik betyder mest för yngre – struktur relativt mer för äldre';
  if(p3) p3.textContent='Åldersdiagrammet jämför modellerna i samma testår. För de äldre grupperna står den strukturella modellen relativt starkare än för yngre inflyttare.';

  const fw=rootModel.windows?.['5'];
  const bw=rootModel.model_variants?.demographic_blind?.windows?.['5'];
  if(!fw||!bw) return;

  const fr=fw.validation?.models?.ridge||{};
  const br=bw.validation?.models?.ridge||{};
  const diff=(fr.r2??0)-(br.r2??0);
  const kpis=document.getElementById('publicKpis');
  if(kpis){
    kpis.innerHTML=[
      '<article><span>Prognosmodell</span><strong>'+fmt(fr.r2,3)+'</strong><small>test-R² 2024</small></article>',
      '<article><span>Demografiskt blind</span><strong>'+fmt(br.r2,3)+'</strong><small>test-R² 2024</small></article>',
      '<article><span>Historikens prognosfördel</span><strong>+'+fmt(diff,3)+'</strong><small>skillnad i test-R²</small></article>'
    ].join('');
  }

  Plotly.react('publicModelR2',[
    {
      x:['Prognosmodell','Demografiskt blind strukturmodell'],
      y:[fr.r2,br.r2],
      type:'bar',
      text:[fr.r2,br.r2].map(v=>fmt(v,3)),
      textposition:'outside',
      hovertemplate:'%{x}<br>Test-R²=%{y:.3f}<extra></extra>'
    }
  ],{
    margin:{t:20,b:90,l:65,r:30},
    yaxis:{title:'Test-R²',range:[0,1]},
    xaxis:{title:''},
    showlegend:false
  },{responsive:true,displaylogo:false});

  const blindRows=(bw.explanation?.theme_marginal_analysis?.rows||[])
    .filter(d=>(d.delta_adjusted_r2??0)>0)
    .sort((a,b)=>(a.delta_adjusted_r2??0)-(b.delta_adjusted_r2??0))
    .slice(-8);
  Plotly.react('publicBlindDrivers',[{
    y:blindRows.map(d=>d.theme),
    x:blindRows.map(d=>d.delta_adjusted_r2),
    type:'bar',orientation:'h',
    text:blindRows.map(d=>fmt(d.delta_adjusted_r2,3)),
    textposition:'outside',
    customdata:blindRows.map(d=>[(d.features||[]).map(f=>labels[f]||f).join(', ')]),
    hovertemplate:'%{y}<br>Δ justerat R²=%{x:.4f}<br>%{customdata[0]}<extra></extra>'
  }],{
    margin:{t:20,l:190,r:70,b:55},
    xaxis:{title:'Självständigt förklaringsvärde: tapp i justerat R²'},
    yaxis:{automargin:true},
    showlegend:false
  },{responsive:true,displaylogo:false});

  const keys=['18_23','24_34','35_49','63_68','70_79'];
  const fa=rootModel.age_group_models||{};
  const ba=rootModel.model_variants?.demographic_blind?.age_group_models||{};
  const ageLabels=keys.map(k=>(fa[k]?.label||k.replace('_','–')));
  Plotly.react('publicAgeComparison',[
    {
      x:ageLabels,
      y:keys.map(k=>fa[k]?.validation?.models?.ridge?.r2),
      type:'bar',name:'Prognosmodell',
      hovertemplate:'%{x}<br>Prognosmodell R²=%{y:.3f}<extra></extra>'
    },
    {
      x:ageLabels,
      y:keys.map(k=>ba[k]?.validation?.models?.ridge?.r2),
      type:'bar',name:'Demografiskt blind',
      hovertemplate:'%{x}<br>Blind modell R²=%{y:.3f}<extra></extra>'
    }
  ],{
    barmode:'group',
    margin:{t:25,b:65,l:65,r:30},
    yaxis:{title:'Test-R²',range:[0,1]},
    xaxis:{title:'Åldersgrupp'},
    legend:{orientation:'h',y:1.12}
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
  let rows=panel.filter(d=>Number.isFinite(d[key])&&Number.isFinite(d.inflyttning_per_1000)&&(yf==='all'||d.year===+yf));
  if(selectedGeography==='lulea'){
    rows=panel.filter(d=>String(d.kommun_kod)==='2580'&&Number.isFinite(d[key])&&Number.isFinite(d.inflyttning_per_1000));
  }
  Plotly.react('scatter',[{
    x:rows.map(d=>d[key]),
    y:rows.map(d=>d.inflyttning_per_1000),
    text:rows.map(d=>d.kommun+' · '+d.year),
    mode:'markers',type:'scatter',
    hovertemplate:'%{text}<br>x=%{x:.2f}<br>Inflyttning=%{y:.2f} per 1 000<extra></extra>'
  }],{
    margin:{t:20},
    xaxis:{title:labels[key]},
    yaxis:{title:'Inflyttade per 1 000'},
    title:selectedGeography==='lulea'?'Luleå över tid':'Sveriges kommuner'
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
