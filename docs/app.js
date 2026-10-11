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
  lag1_smahusforsaljningar_per_1000_smahus:'Försålda permanenta småhus per 1 000 småhus, föregående år',
  lag1_smahusforsaljningar_per_1000_inv:'Försålda permanenta småhus per 1 000 invånare, föregående år',
  lag1_fritidshusandel_bland_smahus:'Fritidshusandel bland småhusliknande bostäder, föregående år (%)',
  lag1_fritidshus_per_1000_inv:'Fritidshus per 1 000 invånare, föregående år',
  lag1_log_fritidshus_per_1000_inv:'Fritidshus per 1 000 invånare (log), föregående år',
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
  lag1_andel_fa_arbetsplatser_i_egen_kommun:'Regional arbetsmotor: egen andel av FA-regionens arbetsplatser, föregående år (%)',
  lag1_regional_centre_distance_km:'Avstånd till regionalt centrum-proxy, föregående år (km)',
  lag1_log_regional_centre_distance_km:'Avstånd till regionalt centrum-proxy (log), föregående år',
  lag1_kvinnors_lonesumma_dagbef_pct:'Kvinnors andel av männens lönesumma, dagbefolkning, föregående år (%)',
  lag1_kvinnors_mediannettoinkomst_andel_pct:'Kvinnors mediannettoinkomst som andel av mäns, föregående år (%)',
  lag1_inkomst_median_tkr:'Median förvärvsinkomst, föregående år (tkr)',
  lag1_lediga_allmannytta_pct:'Lediga lägenheter i allmännyttan, föregående år (%)',
  lag1_lediga_allmannytta_av_total_bostadsbestand_pct:'Lediga allmännyttiga lägenheter som andel av hela bostadsbeståndet, föregående år (%)',
  lag1_smahuspris_medel_tkr:'Genomsnittligt småhuspris, föregående år (tkr)',
  lag1_log_smahuspris_medel:'Genomsnittligt småhuspris (log), föregående år',
  lag1_smahuspris_forandring_pct:'Förändring i genomsnittligt småhuspris, föregående år (%)',
  lag1_smahuspris_inkomstkvot_medel:'Småhuspris i relation till genomsnittlig inkomst, föregående år',
  lag1_smahuspris_inkomstkvot_median:'Småhuspris i relation till medianinkomst, föregående år',
  lag1_andel_bostader_70_max:'Andel bostäder under 70 m², föregående år (%)',
  lag1_andel_flerbostad_70_max:'Andel bostäder under 70 m² i flerbostadshus, föregående år (%)',
  lag1_andel_bostader_111_plus:'Andel bostäder minst 111 m², föregående år (%)',
  lag1_andel_bostader_141_plus:'Andel bostäder minst 141 m², föregående år (%)',
  lag1_andel_bostader_151_plus:'Andel bostäder minst 151 m², föregående år (%)',
  lag1_andel_smahus_111_plus:'Andel småhus minst 111 m², föregående år (%)',
  lag1_andel_smahus_151_plus:'Andel småhus minst 151 m², föregående år (%)',
  lag1_tatortsgrad_pct:'Andel av befolkningen i statistisk tätort, föregående år (%)',
  lag1_log_befolkningstathet_land:'Befolkningstäthet på landareal (log), föregående år',
  lag1_bebyggd_anlagd_andel_land_pct:'Bebyggd och anlagd mark som andel av landareal, föregående år (%)',
  lag1_skogsmark_andel_land_pct:'Skogsmark som andel av landareal, föregående år (%)',
  lag1_naturpraglad_mark_andel_land_pct:'Naturpräglad mark som andel av landareal, föregående år (%)',
  lag1_snoskoterandel_alla_fordon_pct:'Snöskotrar som andel av alla publicerade fordonsslag, föregående år (%)',
  lag1_snoskoterandel_exkl_dragfordon_pct:'Snöskoterandel exklusive dragfordon i nämnaren, föregående år (%)',
  lag1_strand_hav_bostader_per_1000:'Bostadsbyggnader inom 100 m från hav per 1 000 invånare, föregående år',
  lag1_strand_inland_bostader_per_1000:'Bostadsbyggnader inom 100 m från inlandsvatten per 1 000 invånare, föregående år',
  lag1_strand_hav_bostader_tatort_per_1000:'Strandnära bostadsbyggnader vid hav i tätort per 1 000 invånare, föregående år',
  lag1_strand_hav_bostader_tatort_andel_pct:'Andel havsnära bostadsbyggnader som ligger i tätort, föregående år (%)',
  lag1_strand_hav_bostader_skyddad_natur_per_1000:'Havsnära bostadsbyggnader i skyddad natur per 1 000 invånare, föregående år',
  kommun_centroid_northing_km:'Kommunens areaviktade centroid – nordkoordinat i SWEREF 99 TM (km)',
  kommun_centroid_easting_km:'Kommunens areaviktade centroid – östkoordinat i SWEREF 99 TM (km)',
  havsandel_pct:'Havsvatten som andel av kommunens totalareal (%)',
  kustkommun_hav:'Indikator: kommunen har havsvatten',
  geo_northing_100km:'Nordlighet: avstånd från rikets mediancentroid i 100 km',
  geo_havsandel_10pp:'Havsandel uttryckt i 10 procentenheters steg',
  geo_kust_x_northing:'Interaktion: kustkommun × nordlighet',
  geo_havsandel_x_northing:'Interaktion: havsandel × nordlighet',
  geo_havsandel_10pp_x_lag1_tatortsgrad_pct:'Interaktion: havsandel × tätortsgrad',
  geo_havsandel_10pp_x_lag1_log_folkmangd:'Interaktion: havsandel × kommunstorlek',
  geo_havsandel_10pp_x_lag1_log_befolkningstathet_land:'Interaktion: havsandel × befolkningstäthet',
  geo_havsandel_10pp_x_lag1_bebyggd_anlagd_andel_land_pct:'Interaktion: havsandel × bebyggd/anlagd mark'
};

const variableNotes={
  lag1_inflyttning_per_1000:'Antal inflyttade till kommunen dividerat med folkmängden och multiplicerat med 1 000. Här används föregående års nivå.',
  lag1_utflyttning_per_1000:'Antal utflyttade från kommunen per 1 000 invånare föregående år.',
  lag1_log_folkmangd:'Naturlig logaritm av folkmängden. Transformationen gör skillnaden mellan mycket stora och små kommuner mindre extrem.',
  lag1_befolkningstillvaxt_pct:'Årlig procentuell förändring i kommunens folkmängd.',
  lag1_inflyttare_medelalder:'Genomsnittlig ålder bland personer som flyttade in till kommunen under föregående år.',
  lag1_valdeltagande_pct:'Riksdagsvaldeltagande. Mellan valåren används linjär interpolation; därför används måttet inte i strikt prognosvalidering när framtida valdata skulle krävas.',
  lag1_valdeltagande_gap_pp:'Skillnaden i procentenheter mellan kommunens valdistrikt med högst respektive lägst valdeltagande.',
  lag1_ekonomisk_standard_gap_pp:'Skillnaden i procentenheter mellan DeSO med högst respektive lägst andel personer med låg ekonomisk standard.',
  lag1_bostader_per_1000:'Antal bostadslägenheter i kommunens bostadsbestånd per 1 000 invånare.',
  lag1_bostadsbestandsforandring_pct:'Procentuell förändring i bostadsbeståndets storlek jämfört med året före.',
  lag1_fardigstallda_bostader_per_1000:'Antal färdigställda bostäder under året per 1 000 invånare.',
  lag1_fritidshusandel_bland_smahus:'Fritidshus dividerat med fritidshus plus bostäder i småhus. Måttet är en proxy eftersom statistikens enheter inte är helt identiska.',
  lag1_fritidshus_per_1000_inv:'Antal fritidshus dividerat med folkmängden och multiplicerat med 1 000.',
  lag1_log_fritidshus_per_1000_inv:'Log-transformerad fritidshusintensitet. Transformationen dämpar påverkan från kommuner med mycket höga nivåer.',
  lag1_smahusforsaljningar_per_1000_smahus:'Antal sålda permanenta småhus under året i relation till småhusbeståndet.',
  lag1_smahusforsaljningar_per_1000_inv:'Antal sålda permanenta småhus under året i relation till kommunens folkmängd.',
  lag1_smahuspris_inkomstkvot_medel:'Genomsnittligt småhuspris dividerat med genomsnittlig förvärvsinkomst. Används som enkel boendeekonomisk tillgänglighetsproxy.',
  lag1_smahuspris_inkomstkvot_median:'Genomsnittligt småhuspris dividerat med median förvärvsinkomst.',
  lag1_lediga_allmannytta_pct:'Lediga lägenheter i allmännyttan som andel av allmännyttans lägenheter.',
  lag1_lediga_allmannytta_av_total_bostadsbestand_pct:'Lediga lägenheter i allmännyttan dividerat med hela kommunens bostadsbestånd.',
  lag1_sysselsatta_arbetsstalle_sasongsvariation_pct:'Månadsvariation beräknad som (högsta månad − lägsta månad) / årsmedel för sysselsatta efter arbetsställets belägenhet.',
  lag1_sysselsatta_bostad_sasongsvariation_pct:'Månadsvariation beräknad som (högsta månad − lägsta månad) / årsmedel för sysselsatta efter bostadens belägenhet.',
  lag1_log_externa_fa_jobb_per_1000:'Antal jobb i övriga kommuner inom samma FA15-region per 1 000 invånare i den egna kommunen, log-transformerat.',
  lag1_andel_fa_arbetsplatser_i_egen_kommun:'Den egna kommunens arbetsplatser som andel av samtliga arbetsplatser i samma FA15-region.',
  lag1_regional_centre_distance_km:'Raklinjeavstånd mellan kommunens centroid och den kommun som har flest arbetsplatser i samma FA15-region det året. Första versionen är en avståndsproxy, inte faktisk restid.',
  lag1_log_regional_centre_distance_km:'Log-transformerad version av avståndsproxyn till regionalt centrum.',
  lag1_kvinnors_lonesumma_dagbef_pct:'Kvinnors totala lönesumma dividerat med männens totala lönesumma för den arbetsställebaserade dagbefolkningen.',
  lag1_kvinnors_mediannettoinkomst_andel_pct:'Kvinnors disponibla mediannettoinkomst som andel av mäns. Måttet omfattar även kapitalinkomster och transfereringar och är därför inte ett rent lönegap.',
  lag1_naturpraglad_mark_andel_land_pct:'Bred naturproxy baserad på skogsmark, öppen myrmark och övrig mark som andel av landarealen.',
  lag1_bebyggd_anlagd_andel_land_pct:'Bebyggd och anlagd mark dividerat med kommunens landareal.',
  lag1_log_befolkningstathet_land:'Log-transformerad folkmängd per kvadratkilometer landareal.',
  lag1_snoskoterandel_alla_fordon_pct:'Snöskotrar dividerat med summan av alla publicerade fordonsslag. Används som beteendebaserad klimat-/nordlighetsproxy.',
  lag1_snoskoterandel_exkl_dragfordon_pct:'Robusthetsvariant där dragfordon tas bort ur nämnaren eftersom dragfordon är en därav-post i fordonsstatistiken.',
  lag1_strand_hav_bostader_per_1000:'Antal bostadsbyggnader inom 100 meter från hav enligt SCB:s strandnära bebyggelsestatistik, skalat per 1 000 invånare.',
  lag1_strand_inland_bostader_per_1000:'Motsvarande strandmått för inlandsvatten.',
  lag1_strand_hav_bostader_tatort_per_1000:'Havsnära bostadsbyggnader som samtidigt ligger i tätort, per 1 000 invånare.',
  lag1_strand_hav_bostader_tatort_andel_pct:'Andel av de havsnära bostadsbyggnaderna som ligger i tätort.',
  lag1_strand_hav_bostader_skyddad_natur_per_1000:'Havsnära bostadsbyggnader inom formellt skyddad natur, per 1 000 invånare.',
  kommun_centroid_northing_km:'Areaviktad centroid för hela kommunpolygonen, reprojicerad till SWEREF 99 TM. Används som grov nord–syd-position.',
  kommun_centroid_easting_km:'Areaviktad centroidens östkoordinat i SWEREF 99 TM. Används bland annat för avståndsberäkningar.',
  havsandel_pct:'SCB:s havsvattenarea ut till territorialgränsen dividerat med kommunens totalareal.',
  kustkommun_hav:'Binär indikator som är 1 när kommunen har positiv havsvattenarea och 0 annars.',
  geo_northing_100km:'Centroidens northing centrerad kring rikets median och skalad så en enhet motsvarar 100 km.',
  geo_havsandel_10pp:'Havsandel omskalad så en enhet motsvarar 10 procentenheter.',
  geo_kust_x_northing:'Interaktion som testar om kustkommuners samband skiljer sig beroende på nordlighet.',
  geo_havsandel_x_northing:'Interaktion som testar om sambandet för havsandel varierar med nordlighet.',
  geo_havsandel_10pp_x_lag1_tatortsgrad_pct:'Interaktion som testar om sambandet för havsandel varierar med tätortsgrad.',
  geo_havsandel_10pp_x_lag1_log_folkmangd:'Interaktion som testar om sambandet för havsandel varierar med kommunstorlek.',
  geo_havsandel_10pp_x_lag1_log_befolkningstathet_land:'Interaktion som testar om sambandet för havsandel varierar med befolkningstäthet.',
  geo_havsandel_10pp_x_lag1_bebyggd_anlagd_andel_land_pct:'Interaktion som testar om sambandet för havsandel varierar med graden av bebyggd/anlagd mark.'
};

function variableGroup(key){
  if(/inflytt|utflytt|folkmangd|befolkningstillvaxt|andel_20_34|inflyttare_medelalder/.test(key)) return 'Demografi och migration';
  if(/inkomst|ekonomisk_standard|kvinnors_/.test(key)) return 'Inkomst och ekonomisk jämlikhet';
  if(/valdeltagande/.test(key)) return 'Demokrati';
  if(/bostad|smahus|fritidshus|hyresratt|bostadsratt|lediga_allmannytta/.test(key)) return 'Bostäder och bostadsmarknad';
  if(/brott/.test(key)) return 'Trygghet';
  if(/syssels|arbetslos|eftergymnasial|studerande|industri|hotell|kultur|fa_|regional_centre/.test(key)) return 'Arbetsmarknad, utbildning och näringsliv';
  if(/kolada_/.test(key)) return 'Föreningsliv';
  if(/strand|havsandel|kust|centroid|northing|tatort|befolkningstathet|bebyggd|skogsmark|naturpraglad|snoskoter|^geo_/.test(key)) return 'Geografi, mark och miljö';
  return 'Övriga variabler';
}

function variableSource(key){
  if(/brott/.test(key)) return 'Brå';
  if(/valdeltagande/.test(key)) return 'Valmyndigheten';
  if(/kolada_|kvinnors_/.test(key)) return 'Kolada / SCB';
  if(/fa_|regional_centre/.test(key)) return 'SCB + Tillväxtverket FA15';
  if(/centroid|^geo_/.test(key)) return 'SCB-kommungränser via swemaps + härledd beräkning';
  return 'SCB / härledd beräkning';
}

function genericVariableExplanation(key){
  const label=labels[key]||key;
  const lag=key.startsWith('lag1_')
    ? ' Värdet avser föregående år (lag 1), så samma års utfall används inte som förklaringsinformation.'
    : '';
  const transform=/log/.test(key)
    ? ' Variabeln är log-transformerad för att dämpa mycket stora skillnader.'
    : '';
  const interaction=key.startsWith('geo_')&&key.includes('_x_')
    ? ' Detta är en interaktionsterm och ska tolkas tillsammans med sina huvudtermer.'
    : '';
  return label+'.'+lag+transform+interaction;
}

function collectReportVariableKeys(){
  const keys=new Set(Object.keys(labels));
  function walk(x){
    if(Array.isArray(x)){ x.forEach(walk); return; }
    if(x&&typeof x==='object'){ Object.values(x).forEach(walk); return; }
    if(typeof x==='string' && (
      x.startsWith('lag1_') || x.startsWith('geo_') ||
      ['kommun_centroid_northing_km','kommun_centroid_easting_km','havsandel_pct','kustkommun_hav'].includes(x)
    )) keys.add(x);
  }
  walk(rootModel);
  return [...keys].filter(k=>labels[k]||variableNotes[k]).sort((a,b)=>{
    const ga=variableGroup(a), gb=variableGroup(b);
    return ga.localeCompare(gb,'sv') || (labels[a]||a).localeCompare(labels[b]||b,'sv');
  });
}

function renderMethodVariableDictionary(){
  const body=document.getElementById('variableDictionaryBody');
  const count=document.getElementById('variableDictionaryCount');
  const search=document.getElementById('variableDictionarySearch');
  if(!body) return;
  const all=collectReportVariableKeys();

  function draw(){
    const q=(search?.value||'').trim().toLocaleLowerCase('sv-SE');
    const rows=all.filter(k=>{
      const hay=[k,labels[k],variableGroup(k),variableSource(k),variableNotes[k]]
        .filter(Boolean).join(' ').toLocaleLowerCase('sv-SE');
      return !q||hay.includes(q);
    });
    if(count) count.textContent=rows.length+' av '+all.length+' variabler';
    body.innerHTML=rows.map(k=>{
      const label=labels[k]||k;
      const explanation=variableNotes[k]||genericVariableExplanation(k);
      return '<tr>'+
        '<td><strong>'+label+'</strong><div class="variable-code">'+k+'</div></td>'+
        '<td>'+variableGroup(k)+'</td>'+
        '<td>'+explanation+'</td>'+
        '<td>'+variableSource(k)+'</td>'+
      '</tr>';
    }).join('');
  }

  if(search && !search.dataset.bound){
    search.addEventListener('input',draw);
    search.dataset.bound='1';
  }
  draw();
}


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
      && Number.isFinite(r[model.target||'inflyttning_per_1000'])
      && sampleFeatures.every(f=>Number.isFinite(r[f])))
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
  renderThreeModelComparison();
  renderGeographicRobustness();
  renderShorelineRobustness();
  renderHousingTurnoverCandidate();
  renderLeisureIntensityCandidate();
  renderQueuedStructuralTests();
  renderR2ContributionProfile();
  renderLuleaView();
  renderPublicPage();
  renderModel();
  renderVariableMatrix();
  renderAgeModels();
  renderRegressionEquations();
  renderValidation();
  renderMunicipality();
  renderMethodVariableDictionary();
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

  const shareRoot=document.getElementById('r2ContributionShare');
  if(shareRoot){
    const fTotal=Number(fw.explanation?.adjusted_r2);
    const bTotal=Number(bw.explanation?.adjusted_r2);
    const fShare=t=>Number.isFinite(fTotal)&&Math.abs(fTotal)>1e-12
      ? 100*(fm.get(t)?.delta_adjusted_r2??0)/fTotal
      : null;
    const bShare=t=>Number.isFinite(bTotal)&&Math.abs(bTotal)>1e-12
      ? 100*(bm.get(t)?.delta_adjusted_r2??0)/bTotal
      : null;

    Plotly.react(shareRoot,[
      {
        y:themes,
        x:themes.map(fShare),
        type:'bar',orientation:'h',name:'Prognosmodell',
        customdata:themes.map(t=>[
          fm.get(t)?.delta_adjusted_r2??0,
          fTotal,
          (fm.get(t)?.features||[]).map(f=>labels[f]||f).join(', ')
        ]),
        hovertemplate:'%{y}<br>Andel av totalt justerat R²=%{x:.1f}%<br>Δ justerat R²=%{customdata[0]:.4f}<br>Totalt justerat R²=%{customdata[1]:.3f}<br>%{customdata[2]}<extra></extra>'
      },
      {
        y:themes,
        x:themes.map(bShare),
        type:'bar',orientation:'h',name:'Demografiskt blind',
        customdata:themes.map(t=>[
          bm.get(t)?.delta_adjusted_r2??0,
          bTotal,
          (bm.get(t)?.features||[]).map(f=>labels[f]||f).join(', ')
        ]),
        hovertemplate:'%{y}<br>Andel av totalt justerat R²=%{x:.1f}%<br>Δ justerat R²=%{customdata[0]:.4f}<br>Totalt justerat R²=%{customdata[1]:.3f}<br>%{customdata[2]}<extra></extra>'
      }
    ],{
      barmode:'group',
      margin:{t:35,l:220,b:55},
      xaxis:{title:'Andel av modellens totala justerade R² (%)',ticksuffix:' %',zeroline:true},
      yaxis:{automargin:true},
      legend:{orientation:'h',y:1.08}
    },{responsive:true,displaylogo:false});
  }
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
      : 'Rapporten skiljer nu på tre modellspår. <strong>Prognosmodellen</strong> maximerar träffsäkerheten, <strong>den demografiskt blinda strukturmodellen</strong> söker strukturella samband utan historisk demografi som genväg och <strong>den geografiskt robusta prognosmodellen</strong> försöker minska stora prognosfel som koncentreras till vissa kommuner.';
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
      Number.isFinite(r.inflyttning_per_1000) &&
      sampleFeatures.every(f=>Number.isFinite(r[f]))
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

  const themeVariables=new Map(
    (a.explanation?.theme_marginal_analysis?.rows||[]).map(r=>[
      r.theme,
      (r.features||[]).map(f=>labels[f]||f).join('; ')
    ])
  );
  const latestContrib=Object.entries(last.byTheme)
    .map(([theme,value])=>({
      theme,
      value,
      variableDescription:themeVariables.get(theme)||theme
    }))
    .filter(d=>Math.abs(d.value)>1e-9)
    .sort((a,b)=>a.value-b.value);
  Plotly.react('luleaLatestContributions',[{
    y:latestContrib.map(d=>d.theme),
    x:latestContrib.map(d=>d.value),
    customdata:latestContrib.map(d=>d.variableDescription),
    type:'bar',orientation:'h',
    text:latestContrib.map(d=>(d.value>=0?'+':'')+fmt(d.value,2)),
    textposition:'outside',
    hovertemplate:'%{y}<br>Bidrag till Luleå–Sverige-gapet=%{x:.2f} per 1 000<br>Variabel i modellen: %{customdata}<extra></extra>'
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
  if(title) title.textContent='Tre frågor kräver tre olika modeller';
  if(txt) txt.innerHTML='En modell försöker <strong>förutsäga nästa års inflyttning så träffsäkert som möjligt</strong>. En andra försöker förstå <strong>vilka strukturella egenskaper som hänger ihop med inflyttning</strong>. Modell 3 frågar om prognosen fungerar <strong>jämnt mellan olika kommuner</strong> och försöker minska svansen av stora geografiska prognosfel.';
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



function geographicRobustModel(){
  return rootModel.geographic_robust_model || null;
}

function renderThreeModelComparison(){
  const root=document.getElementById('threeModelComparison');
  if(!root) return;
  const fw=rootModel.windows?.['5'];
  const bw=rootModel.model_variants?.demographic_blind?.windows?.['5'];
  const gw=geographicRobustModel();
  if(!fw||!bw||!gw||gw.status!=='tested'){
    root.innerHTML='<p class="note">Modell 3 byggs i den senaste analyskörningen. Diagrammet visas när resultatet finns i model.json.</p>';
    return;
  }
  const fr=fw.validation?.models?.ridge||{};
  const br=bw.validation?.models?.ridge||{};
  const gr=gw.robust_metrics||{};
  Plotly.react(root,[
    {
      x:['Prognosmodell','Demografiskt blind','Geografiskt robust'],
      y:[fr.r2,br.r2,gr.r2],
      type:'bar',
      text:[fr.r2,br.r2,gr.r2].map(v=>fmt(v,3)),
      textposition:'outside',
      hovertemplate:'%{x}<br>Test-R²=%{y:.3f}<extra></extra>'
    }
  ],{
    margin:{t:25,b:80,l:65,r:30},
    yaxis:{title:'Test-R²'},
    xaxis:{title:''},
    showlegend:false
  },{responsive:true,displaylogo:false});
}

function renderGeographicRobustness(){
  const g=geographicRobustModel();
  const cards=document.getElementById('geoRobustCards');
  const chart=document.getElementById('geoRobustComparison');
  const tail=document.getElementById('geoRobustTail');
  const table=document.getElementById('geoRobustWorstTable');
  const selection=document.getElementById('geoRobustSelection');
  if(!cards||!chart||!tail||!table||!selection) return;

  if(!g||g.status!=='tested'){
    cards.innerHTML=metricCard('Status','Byggs','Modell 3 finns efter nästa slutförda analyskörning');
    chart.innerHTML='<p class="note">Resultat saknas ännu.</p>';
    tail.innerHTML='';
    table.innerHTML='';
    selection.innerHTML='';
    return;
  }

  const b=g.baseline_metrics||{}, r=g.robust_metrics||{}, d=g.delta||{};
  const signed=v=>Number.isFinite(Number(v)) ? ((Number(v)>=0?'+':'')+fmt(v,2)) : '–';
  cards.innerHTML=[
    metricCard('Testår',String(g.test_year||'–'),'samma holdoutår som prognosmodellen'),
    metricCard('RMSE',fmt(r.rmse,2),signed(d.rmse)+' förändring mot baslinjen'),
    metricCard('P90 absolutfel',fmt(r.p90_abs_error,2),signed(d.p90_abs_error)+' förändring mot baslinjen'),
    metricCard('P90–P10',fmt(r.p90_p10_abs_error_gap,2),signed(d.p90_p10_abs_error_gap)+' förändring mot baslinjen'),
    metricCard('Sämsta decilens MAE',fmt(r.worst_decile_mae,2),signed(d.worst_decile_mae)+' förändring mot baslinjen')
  ].join('');

  const verdict=document.getElementById('geoRobustVerdict');
  if(verdict){
    const core=[d.rmse,d.p90_abs_error,d.p90_p10_abs_error_gap,d.worst_decile_mae].map(Number);
    const pass=core.every(v=>Number.isFinite(v)&&v>0);
    const improved=(g.municipality_errors||[]).filter(x=>Number(x.delta_abs_error)>0).length;
    const worsened=(g.municipality_errors||[]).filter(x=>Number(x.delta_abs_error)<0).length;
    verdict.classList.toggle('geo-verdict-pass',pass);
    verdict.classList.toggle('geo-verdict-fail',!pass);
    verdict.innerHTML=pass
      ? '<h3>Resultat: Modell 3 klarar holdout-testet</h3><p>Den geografiska felprofilen förbättras på samtliga huvudmått utan att baslinjen tappar oproportionerligt mycket.</p>'
      : '<h3>Resultat: Modell 3 underkänns i 2024-holdout</h3><p>Den interna kommunblockerade korsvalideringen såg lovande ut, men det separata teståret blev sämre. '+improved+' kommuner förbättrades och '+worsened+' försämrades. Modellen behålls därför som diagnostiskt metodspår, inte som produktionsmodell.</p>';
  }

  const metrics=[
    {label:'RMSE',b:b.rmse,r:r.rmse},
    {label:'Median absolutfel',b:b.median_abs_error,r:r.median_abs_error},
    {label:'P90 absolutfel',b:b.p90_abs_error,r:r.p90_abs_error},
    {label:'P90–P10',b:b.p90_p10_abs_error_gap,r:r.p90_p10_abs_error_gap},
    {label:'Sämsta decilens MAE',b:b.worst_decile_mae,r:r.worst_decile_mae}
  ];
  Plotly.react(chart,[
    {x:metrics.map(x=>x.label),y:metrics.map(x=>x.b),type:'bar',name:'Vanlig prognosmodell',
      hovertemplate:'%{x}<br>%{y:.2f}<extra>Vanlig prognosmodell</extra>'},
    {x:metrics.map(x=>x.label),y:metrics.map(x=>x.r),type:'bar',name:'Modell 3',
      hovertemplate:'%{x}<br>%{y:.2f}<extra>Modell 3</extra>'}
  ],{
    barmode:'group',margin:{t:30,b:80,l:65,r:30},
    yaxis:{title:'Fel, inflyttade per 1 000'},
    legend:{orientation:'h',y:1.13}
  },{responsive:true,displaylogo:false});

  const rows=(g.municipality_errors||[]).slice().sort((a,b)=>
    Number(a.robust_abs_error)-Number(b.robust_abs_error)
  );
  Plotly.react(tail,[
    {x:rows.map((_,i)=>i+1),y:rows.map(x=>x.baseline_abs_error),
      mode:'lines',name:'Vanlig prognosmodell',
      customdata:rows.map(x=>x.kommun),
      hovertemplate:'%{customdata}<br>Rang %{x}<br>Absolutfel=%{y:.2f}<extra></extra>'},
    {x:rows.map((_,i)=>i+1),y:rows.map(x=>x.robust_abs_error),
      mode:'lines',name:'Modell 3',
      customdata:rows.map(x=>x.kommun),
      hovertemplate:'%{customdata}<br>Rang %{x}<br>Absolutfel=%{y:.2f}<extra></extra>'}
  ],{
    margin:{t:30,b:60,l:65,r:30},
    xaxis:{title:'Kommuner sorterade från lägst till högst fel i Modell 3'},
    yaxis:{title:'Absolut prognosfel per 1 000'},
    legend:{orientation:'h',y:1.12}
  },{responsive:true,displaylogo:false});

  const worst=(g.municipality_errors||[]).slice(0,20);
  table.innerHTML='<table class="metric-table"><thead><tr>'+
    '<th>Kommun</th><th>Observerat</th><th>Vanlig prognos</th><th>Modell 3</th>'+
    '<th>Absolutfel bas</th><th>Absolutfel Modell 3</th><th>Förbättring</th>'+
    '</tr></thead><tbody>'+
    worst.map(x=>'<tr>'+
      '<td>'+x.kommun+'</td>'+
      '<td>'+fmt(x.observed,1)+'</td>'+
      '<td>'+fmt(x.baseline_prediction,1)+'</td>'+
      '<td>'+fmt(x.robust_prediction,1)+'</td>'+
      '<td>'+fmt(x.baseline_abs_error,2)+'</td>'+
      '<td>'+fmt(x.robust_abs_error,2)+'</td>'+
      '<td>'+signed(x.delta_abs_error)+'</td>'+
    '</tr>').join('')+'</tbody></table>';

  const added=g.added_features_vs_forecast_selection||[];
  const removed=g.removed_features_vs_forecast_selection||[];
  const fs=g.selected_feature_set||[];
  const cfg=g.selection?.selected||{};
  selection.innerHTML=
    '<p><strong>Valt feature-set:</strong> '+(cfg.feature_set||'–')+
    ' · <strong>ridge α:</strong> '+fmt(g.selected_alpha,3)+
    ' · <strong>CV-metod:</strong> '+(cfg.cv_method==='municipality_group_kfold'?'kommunblockerad 5-fold':(cfg.cv_method||'–'))+
    ' · <strong>foldar:</strong> '+(cfg.folds??'–')+'</p>'+
    '<p><strong>Valda variabler:</strong> '+(fs.length?fs.map(x=>labels[x]||x).join('; '):'–')+'</p>'+
    '<p><strong>Tillkom jämfört med vanlig prognosmodell:</strong> '+(added.length?added.map(x=>labels[x]||x).join('; '):'inga')+'</p>'+
    '<p><strong>Togs bort:</strong> '+(removed.length?removed.map(x=>labels[x]||x).join('; '):'inga')+'</p>'+
    '<p class="note">Urvalsmål: '+(g.objective?.formula||'–')+'. '+(g.objective?.rmse_guardrail||'')+'</p>';
}

function shorelineRobustRows(){
  const blind=rootModel.model_variants?.demographic_blind;
  const age=blind?.shoreline_protected_robustness_tests?.age_groups?.['35_49'];
  return age?.rows||[];
}

function renderShorelineRobustness(){
  const rows=shorelineRobustRows().filter(r=>r.status==='tested');
  const summary=document.getElementById('shorelineRobustnessSummary');
  const chart=document.getElementById('shorelineRobustnessChart');
  const table=document.getElementById('shorelineRobustnessTable');
  const logText=document.getElementById('shorelineRun114Text');
  const logDecision=document.getElementById('shorelineRun114Decision');
  if(!summary||!chart||!table) return;

  if(!rows.length){
    summary.textContent='Robusthetsresultatet från #114 saknas i den laddade modellfilen.';
    chart.innerHTML='';
    table.innerHTML='';
    return;
  }

  const labelsMap={
    raw_all:'Råvärde – alla',
    log1p_all:'Log-transformerad – alla',
    winsor99_all:'Winsor 99 % – alla',
    exclude_top3_all:'Exkl. tre högsta',
    coastal_only_raw:'Endast kust – rå',
    coastal_only_log1p:'Endast kust – log'
  };
  const positive=rows.filter(r=>Number(r.holdout?.delta_r2)>0);
  const stable=positive.length>=Math.ceil(rows.length/2);
  const raw=rows.find(r=>r.variant==='raw_all');
  const excl=rows.find(r=>r.variant==='exclude_top3_all');
  const coast=rows.find(r=>r.variant==='coastal_only_raw');

  const pieces=[];
  if(raw?.holdout?.delta_r2!=null) pieces.push('råvärdet ΔR² '+(Number(raw.holdout.delta_r2)>=0?'+':'')+fmt(raw.holdout.delta_r2,4));
  if(excl?.holdout?.delta_r2!=null) pieces.push('utan de tre högsta '+(Number(excl.holdout.delta_r2)>=0?'+':'')+fmt(excl.holdout.delta_r2,4));
  if(coast?.holdout?.delta_r2!=null) pieces.push('endast kust '+(Number(coast.holdout.delta_r2)>=0?'+':'')+fmt(coast.holdout.delta_r2,4));
  summary.innerHTML='<strong>35–49 år:</strong> '+pieces.join(' · ')+'. '+
    (stable
      ? 'Signalen är positiv i en majoritet av de testade holdout-varianterna, vilket talar emot att den enbart orsakas av de allra högsta kommunerna.'
      : 'Signalen är inte positiv i en majoritet av robusthetsvarianterna. Den bör därför fortsatt behandlas som lokal/åldersspecifik diagnostik snarare än generell produktionssignal.');

  Plotly.react(chart,[{
    x:rows.map(r=>labelsMap[r.variant]||r.variant),
    y:rows.map(r=>r.holdout?.delta_r2),
    type:'bar',
    customdata:rows.map(r=>[r.p_value,r.delta_adjusted_r2,r.n_municipalities]),
    hovertemplate:'%{x}<br>Holdout ΔR²=%{y:.4f}<br>p=%{customdata[0]:.4f}<br>Δ justerat R²=%{customdata[1]:.4f}<br>Kommuner=%{customdata[2]}<extra></extra>'
  }],{
    margin:{t:25,b:100,l:70,r:30},
    yaxis:{title:'Förändring i holdout-R²'},
    xaxis:{title:''},
    shapes:[{type:'line',x0:-.5,x1:rows.length-.5,y0:0,y1:0,line:{dash:'dash'}}],
    showlegend:false
  },{responsive:true,displaylogo:false});

  table.innerHTML='<table class="metric-table"><thead><tr>'+
    '<th>Variant</th><th>Kommuner</th><th>p-värde</th><th>Δ just. R²</th><th>Holdout ΔR²</th><th>Holdout ΔRMSE</th>'+
    '</tr></thead><tbody>'+
    rows.map(r=>'<tr><td>'+(labelsMap[r.variant]||r.variant)+'</td>'+
      '<td>'+r.n_municipalities+'</td>'+
      '<td>'+fmt(r.p_value,4)+'</td>'+
      '<td>'+fmt(r.delta_adjusted_r2,4)+'</td>'+
      '<td>'+fmt(r.holdout?.delta_r2,4)+'</td>'+
      '<td>'+fmt(r.holdout?.delta_rmse,3)+'</td></tr>').join('')+
    '</tbody></table>';

  if(logText) logText.innerHTML='För 35–49 år testades sex varianter. '+pieces.join(' · ')+'.';
  if(logDecision) logDecision.innerHTML='<strong>Beslut:</strong> '+
    (stable
      ? 'signalen överlever flera robusthetsvarianter, men ligger kvar som åldersspecifik/lokal signal och blir i första hand kandidat för Modell 3 snarare än generell strukturvariabel.'
      : 'signalen är känslig för urval/transformering och får inte generell produktionsstatus. Den kan fortfarande användas som diagnostik för geografiskt avvikande kommuntyper.');
}



function renderHousingTurnoverCandidate(){
  const data=rootModel.housing_turnover_geographic_candidate_tests;
  const summary=document.getElementById('housingTurnoverSummary');
  const chart=document.getElementById('housingTurnoverChart');
  const table=document.getElementById('housingTurnoverTable');
  if(!summary||!chart||!table) return;

  const rows=(data?.rows||[]).filter(r=>r.status==='tested');
  if(!rows.length){
    summary.textContent='Resultatet finns efter nästa slutförda analyskörning.';
    chart.innerHTML='';
    table.innerHTML='';
    return;
  }

  const labelMap={
    lag1_smahusforsaljningar_per_1000_smahus:'Försäljningar / 1 000 småhus',
    lag1_smahusforsaljningar_per_1000_inv:'Försäljningar / 1 000 invånare'
  };
  const score=r=>{
    const d=r.holdout?.delta||{};
    return [d.rmse,d.p90_abs_error,d.p90_p10_abs_error_gap,d.worst_decile_mae]
      .filter(v=>Number.isFinite(Number(v))&&Number(v)>0).length;
  };
  const best=rows.slice().sort((a,b)=>score(b)-score(a))[0];
  const positives=score(best);
  summary.innerHTML='<strong>'+(labelMap[best.feature]||best.feature)+':</strong> '+
    (positives>=3
      ? 'förbättrar minst tre av fyra geografiska huvudmått i 2024-holdout och är därför en lovande kandidat för fortsatt validering.'
      : 'ger inte en tillräckligt bred förbättring av den geografiska felprofilen i 2024-holdout och bör tills vidare stanna som diagnostik.');

  const metrics=[
    {key:'rmse',label:'RMSE'},
    {key:'p90_abs_error',label:'P90 absolutfel'},
    {key:'p90_p10_abs_error_gap',label:'P90–P10'},
    {key:'worst_decile_mae',label:'Sämsta decilens MAE'}
  ];
  Plotly.react(chart,rows.map(r=>({
    x:metrics.map(m=>m.label),
    y:metrics.map(m=>r.holdout?.delta?.[m.key]),
    type:'bar',
    name:labelMap[r.feature]||r.feature,
    hovertemplate:'%{x}<br>Förbättring=%{y:.3f}<extra>%{fullData.name}</extra>'
  })),{
    barmode:'group',
    margin:{t:30,b:75,l:70,r:30},
    yaxis:{title:'Positivt värde = lägre fel än basmodellen'},
    legend:{orientation:'h',y:1.15},
    shapes:[{type:'line',xref:'paper',x0:0,x1:1,y0:0,y1:0,line:{dash:'dash'}}]
  },{responsive:true,displaylogo:false});

  table.innerHTML='<table class="metric-table"><thead><tr>'+
    '<th>Mått</th><th>CV Δ objektiv</th><th>Holdout ΔR²</th><th>ΔRMSE</th>'+
    '<th>ΔP90</th><th>ΔP90–P10</th><th>Δ sämsta decil</th>'+
    '</tr></thead><tbody>'+
    rows.map(r=>{
      const d=r.holdout?.delta||{};
      return '<tr><td>'+(labelMap[r.feature]||r.feature)+'</td>'+
        '<td>'+fmt(r.cv?.delta_objective,3)+'</td>'+
        '<td>'+fmt(d.r2,4)+'</td>'+
        '<td>'+fmt(d.rmse,3)+'</td>'+
        '<td>'+fmt(d.p90_abs_error,3)+'</td>'+
        '<td>'+fmt(d.p90_p10_abs_error_gap,3)+'</td>'+
        '<td>'+fmt(d.worst_decile_mae,3)+'</td></tr>';
    }).join('')+'</tbody></table>';
}



function renderLeisureIntensityCandidate(){
  const data=rootModel.leisure_intensity_geographic_candidate_tests;
  const summary=document.getElementById('leisureIntensitySummary');
  const chart=document.getElementById('leisureIntensityChart');
  const table=document.getElementById('leisureIntensityMunicipalities');
  if(!summary||!chart||!table) return;

  const rows=(data?.rows||[]).filter(r=>r.status==='tested');
  if(!rows.length){
    summary.textContent='Resultatet finns efter nästa slutförda analyskörning.';
    chart.innerHTML='';
    table.innerHTML='';
    return;
  }

  const labelMap={
    lag1_fritidshus_per_1000_inv:'Fritidshus / 1 000 invånare',
    lag1_log_fritidshus_per_1000_inv:'Fritidshus / 1 000 invånare (log)'
  };
  const metricKeys=[
    ['rmse','RMSE'],
    ['p90_abs_error','P90 absolutfel'],
    ['p90_p10_abs_error_gap','P90–P10'],
    ['worst_decile_mae','Sämsta decilens MAE']
  ];
  const score=r=>metricKeys.filter(([k])=>Number(r.holdout?.delta?.[k])>0).length;
  const best=rows.slice().sort((a,b)=>score(b)-score(a))[0];
  const bestDelta=best?.holdout?.delta||{};
  const nPositive=score(best);
  summary.innerHTML='<strong>'+(labelMap[best.feature]||best.feature)+':</strong> '+
    (nPositive>=3
      ? 'förbättrar minst tre av fyra geografiska huvudmått i 2024-holdout. Resultatet bör därefter bedömas tillsammans med kommunmönstret nedan innan eventuell Modell-3-status.'
      : 'ger inte en tillräckligt bred förbättring av den geografiska felprofilen i 2024-holdout och bör därför stanna som diagnostik.');

  Plotly.react(chart,rows.map(r=>({
    x:metricKeys.map(([,label])=>label),
    y:metricKeys.map(([k])=>r.holdout?.delta?.[k]),
    type:'bar',
    name:labelMap[r.feature]||r.feature,
    hovertemplate:'%{x}<br>Förbättring=%{y:.3f}<extra>%{fullData.name}</extra>'
  })),{
    barmode:'group',
    margin:{t:30,b:80,l:70,r:30},
    yaxis:{title:'Positivt värde = lägre fel än basmodellen'},
    legend:{orientation:'h',y:1.15},
    shapes:[{type:'line',xref:'paper',x0:0,x1:1,y0:0,y1:0,line:{dash:'dash'}}]
  },{responsive:true,displaylogo:false});

  const munis=(best?.municipality_errors||[]);
  const improved=munis.slice().sort((a,b)=>Number(b.delta_abs_error)-Number(a.delta_abs_error)).slice(0,10);
  const worsened=munis.slice().sort((a,b)=>Number(a.delta_abs_error)-Number(b.delta_abs_error)).slice(0,10);
  const rowsHtml=[
    ...improved.map(x=>({...x,direction:'Störst förbättring'})),
    ...worsened.map(x=>({...x,direction:'Störst försämring'}))
  ];
  table.innerHTML='<table class="metric-table"><thead><tr>'+
    '<th>Kommun</th><th>Grupp</th><th>Basfel</th><th>Kandidatfel</th><th>Förbättring</th>'+
    '</tr></thead><tbody>'+
    rowsHtml.map(x=>'<tr>'+
      '<td>'+x.kommun+'</td>'+
      '<td>'+x.direction+'</td>'+
      '<td>'+fmt(x.baseline_abs_error,2)+'</td>'+
      '<td>'+fmt(x.candidate_abs_error,2)+'</td>'+
      '<td>'+fmt(x.delta_abs_error,2)+'</td>'+
    '</tr>').join('')+
    '</tbody></table>';

  const rolling=rootModel.leisure_intensity_rolling_holdouts;
  const rollingChart=document.getElementById('leisureRollingChart');
  const rollingTable=document.getElementById('leisureRollingTable');
  if(rollingChart&&rollingTable){
    const candidates=rolling?.candidates||[];
    if(!candidates.length){
      rollingChart.innerHTML='<p class="note">Flerårstestet visas efter nästa slutförda analyskörning.</p>';
      rollingTable.innerHTML='';
    }else{
      const labelsRolling={
        lag1_fritidshus_per_1000_inv:'Fritidshus / 1 000 invånare',
        lag1_log_fritidshus_per_1000_inv:'Log fritidshus / 1 000 invånare'
      };
      const traces=candidates.map(c=>({
        x:(c.years||[]).filter(y=>y.status==='tested').map(y=>String(y.test_year)),
        y:(c.years||[]).filter(y=>y.status==='tested').map(y=>y.holdout?.delta_objective),
        mode:'lines+markers',
        type:'scatter',
        name:labelsRolling[c.feature]||c.feature,
        hovertemplate:'Testår %{x}<br>Förbättring av geografiskt objektiv=%{y:.3f}<extra>%{fullData.name}</extra>'
      }));
      Plotly.react(rollingChart,traces,{
        margin:{t:30,b:60,l:75,r:30},
        xaxis:{title:'Holdoutår'},
        yaxis:{title:'Positivt = bättre geografiskt objektiv'},
        shapes:[{type:'line',xref:'paper',x0:0,x1:1,y0:0,y1:0,line:{dash:'dash'}}],
        legend:{orientation:'h',y:1.15}
      },{responsive:true,displaylogo:false});

      rollingTable.innerHTML='<table class="metric-table"><thead><tr>'+
        '<th>Variant</th><th>Testade år</th><th>Bättre objektiv</th><th>Bättre RMSE</th>'+
        '<th>Bättre P90</th><th>Bättre P90–P10</th><th>Bättre sämsta decil</th>'+
        '</tr></thead><tbody>'+
        candidates.map(c=>{
          const q=c.summary||{};
          return '<tr><td>'+(labelsRolling[c.feature]||c.feature)+'</td>'+
            '<td>'+String(q.n_tested_years??'–')+'</td>'+
            '<td>'+String(q.years_with_better_holdout_objective??'–')+'</td>'+
            '<td>'+String(q.years_with_better_rmse??'–')+'</td>'+
            '<td>'+String(q.years_with_better_p90??'–')+'</td>'+
            '<td>'+String(q.years_with_better_tail_spread??'–')+'</td>'+
            '<td>'+String(q.years_with_better_worst_decile??'–')+'</td></tr>';
        }).join('')+
        '</tbody></table>';
    }
  }
}



function renderStructuralCandidatePanel(data, summaryId, chartId, titleMap){
  const summary=document.getElementById(summaryId);
  const chart=document.getElementById(chartId);
  if(!summary||!chart) return;

  const overall=(data?.overall?.rows||[]).filter(r=>r.status==='tested');
  const geo=(data?.geographic?.rows||[]).filter(r=>r.status==='tested');
  if(!overall.length && !geo.length){
    summary.textContent='Resultatet visas efter nästa slutförda analyskörning.';
    chart.innerHTML='';
    return;
  }

  const byFeature=new Map();
  overall.forEach(r=>byFeature.set(r.feature,{feature:r.feature,overall:r}));
  geo.forEach(r=>{
    const x=byFeature.get(r.feature)||{feature:r.feature};
    x.geo=r; byFeature.set(r.feature,x);
  });
  const rows=[...byFeature.values()];
  const score=r=>{
    const d=r.geo?.holdout?.delta||{};
    return [d.rmse,d.p90_abs_error,d.p90_p10_abs_error_gap,d.worst_decile_mae]
      .filter(v=>Number(v)>0).length;
  };
  const best=rows.slice().sort((a,b)=>score(b)-score(a))[0];
  summary.innerHTML='<strong>'+(titleMap[best.feature]||labels[best.feature]||best.feature)+':</strong> '+
    (score(best)>=3
      ? 'förbättrar minst tre av fyra geografiska huvudmått i 2024-holdout och är därför värd fortsatt validering.'
      : 'ger inte en bred förbättring av den geografiska felprofilen i 2024-holdout och bör tills vidare behandlas som diagnostik.');

  const metrics=[
    ['rmse','ΔRMSE'],
    ['p90_abs_error','ΔP90'],
    ['p90_p10_abs_error_gap','ΔP90–P10'],
    ['worst_decile_mae','Δ sämsta decil']
  ];
  Plotly.react(chart,rows.map(r=>({
    x:metrics.map(([,l])=>l),
    y:metrics.map(([k])=>r.geo?.holdout?.delta?.[k]),
    type:'bar',
    name:titleMap[r.feature]||labels[r.feature]||r.feature,
    customdata:metrics.map(()=>[r.overall?.delta_adjusted_r2,r.overall?.p_value]),
    hovertemplate:'%{x}: %{y:.3f}<br>Δ justerat R²=%{customdata[0]:.4f}<br>p=%{customdata[1]:.4f}<extra>%{fullData.name}</extra>'
  })),{
    barmode:'group',
    margin:{t:30,b:70,l:70,r:30},
    yaxis:{title:'Positivt = lägre geografiskt prognosfel'},
    shapes:[{type:'line',xref:'paper',x0:0,x1:1,y0:0,y1:0,line:{dash:'dash'}}],
    legend:{orientation:'h',y:1.16}
  },{responsive:true,displaylogo:false});
}

function renderQueuedStructuralTests(){
  renderStructuralCandidatePanel(
    rootModel.regional_centre_access_candidate_tests,
    'regionalCentreTestSummary',
    'regionalCentreTestChart',
    {
      lag1_regional_centre_distance_km:'Avstånd till regionalt centrum',
      lag1_log_regional_centre_distance_km:'Log(avstånd till regionalt centrum)'
    }
  );
  renderStructuralCandidatePanel(
    rootModel.gender_gap_candidate_tests,
    'genderGapTestSummary',
    'genderGapTestChart',
    {
      lag1_kvinnors_lonesumma_dagbef_pct:'Kvinnors andel av männens lönesumma',
      lag1_kvinnors_mediannettoinkomst_andel_pct:'Kvinnors mediannettoinkomst / mäns'
    }
  );
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
