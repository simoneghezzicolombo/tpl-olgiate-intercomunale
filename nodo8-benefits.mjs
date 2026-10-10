import { validateCoverageComparison, coverageChangeLabel } from "./nodo8-coverage.mjs?v=20261010b";
const fmt = n => new Intl.NumberFormat("it-IT",{maximumFractionDigits:2}).format(n);
const maxGap = times => Math.max(...times.slice(1).map((t,i)=>t-times[i]));
const duration = m => m >= 60 ? `${Math.floor(m/60)} h${m%60 ? ` ${m%60} min` : ""}` : `${m} min`;
const node = (tag,cls,text) => {const e=document.createElement(tag);if(cls)e.className=cls;if(text!==undefined)e.textContent=text;return e;};

export function validateBenefits(proposal, coverage, service, diagnostic) {
  validateCoverageComparison(coverage,proposal);
  if (proposal.contract!=="nodo8_showcase_v1" || proposal.authority.public_operating_timetable_authorised!==false || proposal.authority.primary_selection_authorised!==false || proposal.authority.runner_up_selection_authorised!==false) throw new Error("Proposal authority changed");
  if (service.contract !== "nodo8_station_service_comparison_v1" || service.scope !== "DEPARTURES_FROM_OLGIATE_FS_NOT_EVERY_STOP_OR_RESIDENT" ||
      service.annual_service_count_inferred !== false || service.combined_frequency_accessibility_score_inferred !== false ||
      service.pdb.automatic_km_entitlement_certified !== false || service.pdb.automatic_funding_transfer_certified !== false ||
      service.pdb.proposed_terminal!=="Cisano Bergamasco FS" || service.pdb.source_page!==10 || service.pdb.year!==2018)
    throw new Error("Unsupported service comparison");
  for (const [key,count,gap] of [["west",8,377],["east",5,380]]) {
    const times=service[key].current_departures_min;
    if (times.length!==count || times.some((t,i)=>!Number.isFinite(t) || (i && t<=times[i-1])) || maxGap(times)!==gap)
      throw new Error("Published station clock inventory inconsistent");
  }
  if (diagnostic.contract !== "nodo8_five_minute_loss_diagnostic_v1" || diagnostic.proposal_coverage_reproduced !== true || diagnostic.additional_resident_count_inferred !== false)
    throw new Error("Unsupported loss diagnostic");
  for (const code of ["TOTAL",...proposal.municipalities.map(m=>m.code)]) {
    const d=diagnostic.municipality_details[code];
    if (!d || ![d.lost_pp,d.gained_pp,d.net_delta_pp].every(Number.isFinite) || d.lost_pp<0 || d.gained_pp<0 ||
        !Array.isArray(d.old_closest_groups_for_lost_units) || d.old_closest_groups_for_lost_units.some(r=>!Number.isFinite(r.loss_share_pp) || r.loss_share_pp<0 || !r.member_stop_ids?.length) ||
        Math.abs(d.gained_pp-d.lost_pp-coverage.delta_percentage_points[code]["5"])>1e-7 ||
        Math.abs(d.old_closest_groups_for_lost_units.reduce((n,r)=>n+r.loss_share_pp,0)-d.lost_pp)>1e-7)
      throw new Error("Five-minute changes do not reconcile");
  }
  for(const key of Object.keys(coverage.sources)) if(diagnostic.sources[key]?.sha256!==coverage.sources[key].sha256) throw new Error("Diagnostic substrate differs from comparison");
  return {proposal,coverage,service,diagnostic};
}

export function benefitsView(model,code="TOTAL",threshold="10",direction="west") {
  if (!["TOTAL",...model.proposal.municipalities.map(m=>m.code)].includes(code) || !["5","8","10"].includes(threshold) || !["west","east"].includes(direction)) throw new Error("Invalid comparison selection");
  const axis=model.service[direction];
  const proposalTimes=model.proposal.trips.map(t=>direction==="east"?t.first_fs_min:t.second_fs_min);
  return {before:model.coverage.baseline_percent[code][threshold],after:model.coverage.proposal_percent[code][threshold],
    delta:model.coverage.delta_percentage_points[code][threshold], currentCount:axis.current_departures_min.length,
    proposalCount:proposalTimes.length,currentGap:maxGap(axis.current_departures_min),proposalGap:maxGap(proposalTimes),
    route:axis.route,loss:model.diagnostic.municipality_details[code]};
}

function lossExplanation(model,code,rootHref) {
  const d=model.diagnostic.municipality_details[code];
  const box=node("details","benefits-loss"), summary=node("summary","","Perché a 5 minuti qualcuno perde vicinanza?");
  box.append(summary,node("p","","Nel totale si passa dal 38,95% al 46,06%. Ma Brivio perde 6,39 punti e Santa Maria Hoè 6,38: una fermata a sei minuti non conta più nella soglia di cinque, anche se resta raggiungibile."));
  const list=node("ul");
  const textByCluster={
    EX_036:"Brivio: la palina L00063 di capolinea non coincide con il punto di Via Bergamo / Scuola Materna scelto in Nodo8.",
    EX_028:"Santa Maria Hoè: la fermata della località Hoè (300873/L00873) non è inclusa. Non è la fermata di Santa Maria Hoè centro, che rimane.",
    EX_032:"Alpino / Via Como (300902/L00902) non è incluso, come nel compromesso con la nuova fermata Calco Centro.",
  };
  const rows=code==="TOTAL" ? [...model.diagnostic.municipality_details["97010"].old_closest_groups_for_lost_units,
    ...model.diagnostic.municipality_details["97074"].old_closest_groups_for_lost_units].filter(r=>textByCluster[r.cluster_id]) : d.old_closest_groups_for_lost_units.slice(0,3);
  for (const r of rows) list.append(node("li","",textByCluster[r.cluster_id] || `${r.name}: nei punti che escono dalla soglia era il gruppo di fermate attuali più vicino. Non significa che la località sia stata eliminata.`));
  box.append(list,node("p","","Contano anche le coordinate e le paline dei due versi: Beverate, Vaccarezza e Tremonte restano nel giro, ma alcuni punti passano poco oltre 5 minuti. Le perdite sono lorde: nuovi punti raggiunti ne compensano una parte. Non sono passeggeri persi."));
  if(code!=="TOTAL") box.append(node("p","",`Nel modello del comune: ${fmt(d.lost_pp)} punti di copertura persi, ${fmt(d.gained_pp)} guadagnati; saldo ${coverageChangeLabel(d.net_delta_pp)} a 5 minuti.`));
  const a=node("a","","Vedi fermate e percorso →");a.href=rootHref+"#percorso";box.append(a);
  return box;
}

export function mountBenefits(host,model,{prefix="benefits",rootHref="index.html"}={}) {
  const controls=node("div","benefits-controls");
  function select(label,id,options,value) {const wrap=node("div"),l=node("label","",label),s=node("select");s.id=prefix+id;l.htmlFor=s.id;
    for(const [v,t] of options){const o=node("option","",t);o.value=v;s.append(o);}s.value=value;wrap.append(l,s);controls.append(wrap);return s;}
  const municipality=select("Dove abiti?","-municipality",[["TOTAL","Tutti i cinque comuni"],...model.proposal.municipalities.map(m=>[m.code,m.name])],"TOTAL");
  const threshold=select("Quanto cammini?","-threshold",[["5","Entro 5 minuti"],["8","Entro 8 minuti"],["10","Entro 10 minuti"]],"10");
  const direction=select("Partenze da Olgiate FS","-direction",[["west","Verso ovest · oggi D184"],["east","Verso est · oggi D185"]],"west");
  const cards=node("div","benefits-cards"),delta=node("p","benefits-delta"),loss=node("div"),note=node("p","benefits-note",
    "Vicinanza nel modello delle fermate, non passeggeri. Corse da FS nel feriale scolastico 2026/27 contro la proposta 2027, non corse sotto casa. Sono due misure affiancate, non un indice. Nodo8: banche di punta ogni 30 minuti, sfalsate; fuori punta fino a 120 minuti.");
  host.replaceChildren(controls,cards,delta,note,loss);
  const sources=node("details","benefits-sources"),s=node("summary","","Fonti, date e limiti");
  sources.append(s,node("p","","Vicinanza: stesso modello pedonale RT028, fermate strutturali D184/D185 dal GTFS 2025/26 e siti di progetto Nodo8. Non sono passeggeri o percorsi accessibili certificati. Frequenza a FS: feriale scolastico degli orari ufficiali 2026/27 contro un feriale della proposta 2027, non un confronto annuale. 16 giri completi producono 16 ripartenze per ciascun anello, non 32 corse distinte. In mappa, D184 e D185 rappresentano il 28 aprile 2026, prima della deviazione di Brivio, con i tempi intermedi stimati descritti in Dati e metodo."));
  for(const key of ["west","east"]){const a=node("a","",`Orario attuale ${model.service[key].route} ↗`);a.href=model.service[key].source_url;sources.append(a);}
  host.append(sources);
  const update=()=>{const v=benefitsView(model,municipality.value,threshold.value,direction.value);cards.replaceChildren();
    for(const [isProposal,label,coverage,count,gap] of [[false,"Oggi · D184/D185",v.before,v.currentCount,v.currentGap],[true,"Con Nodo8 · proposta",v.after,v.proposalCount,v.proposalGap]]) {
      const card=node("article",`benefits-card${isProposal?" benefits-card--proposal":""}`);
      card.append(node("h3","",label),node("strong","benefits-coverage",`${fmt(coverage)}%`),node("p","",`potenzialmente entro ${threshold.value} minuti a piedi`));
      card.append(node("small","",isProposal?"Siti di progetto Nodo8":"Fermate strutturali · GTFS 2025/26"));
      const track=node("div","benefits-track"),fill=node("span");track.setAttribute("aria-hidden","true");fill.style.width=coverage+"%";track.append(fill);card.append(track);
      card.append(node("strong","benefits-frequency",`${count} partenze da FS`),node("p","",`${direction.value==="west"?"Verso ovest":"Verso est"}${isProposal?"":` · ${v.route}`}`),node("small","",`Intervallo massimo nel quadro: ${duration(gap)}`));cards.append(card);
    }
    delta.textContent=`${coverageChangeLabel(v.delta)} di vicinanza nel modello · ${v.proposalCount-v.currentCount} partenze da FS in più nella direzione scelta`;
    delta.classList.toggle("is-loss",v.delta<0);loss.replaceChildren(lossExplanation(model,municipality.value,rootHref));
    host.dataset.municipality=municipality.value;host.dataset.threshold=threshold.value;host.dataset.direction=direction.value;
  };
  [municipality,threshold,direction].forEach(s=>s.addEventListener("change",update));update();host.dataset.residentReady="true";
}

export function mountPdbNote(host,service) {
  const p=node("p","","D185 prosegue oltre Brivio verso Cisano, Caprino e Celana: una parte dell’offerta serve territori bergamaschi. Nel 2018 l’Agenzia proponeva già Cisano FS come capolinea della E03 e la prosecuzione per Celana con le linee del bacino di Bergamo.");
  const a=node("a","","Piano di Bacino 2018 · LC-INT-008, pagina 10 ↗");a.href=service.pdb.source_url;
  const detail=node("details"),summary=node("summary","","Che cosa dimostra, e cosa no");detail.append(summary,node("p","","È un precedente di razionalizzazione tra bacini, non una condanna del servizio. Manteneva Cisano FS: non proponeva di fermarsi già a Brivio. Non certifica chilometri ‘di proprietà’ dei cinque comuni, risparmi odierni o fondi automaticamente trasferibili a Nodo8. Concentrare l’offerta sui cinque comuni è la scelta politica proposta, da concordare con Agenzie e operatore."));
  host.replaceChildren(p,a,detail);
}

export async function initBenefits({base="",rootHref="index.html",proposal=null,coverage=null}={}) {
  try {
    const load=async name=>{const r=await fetch(base+"assets/"+name+"?v=20261010b");if(!r.ok)throw new Error(name+" unavailable");return r.json();};
    const [p,c,s,d]=await Promise.all([proposal||load("nodo8-proposal.json"),coverage||load("nodo8-coverage-comparison.json"),load("nodo8-service-comparison.json"),load("nodo8-coverage-diagnostic.json")]);
    const model=validateBenefits(p,c,s,d);
    document.querySelectorAll("[data-resident-comparison]").forEach((host,i)=>mountBenefits(host,model,{prefix:`resident-${base?"story":"home"}-${i}`,rootHref}));
    document.querySelectorAll("[data-pdb-note]").forEach(host=>mountPdbNote(host,s));
    document.querySelectorAll("[data-hero-coverage]").forEach(host=>{host.textContent=fmt(c.baseline_percent.TOTAL["10"])+"% → "+fmt(c.proposal_percent.TOTAL["10"])+"%";});
    document.querySelectorAll("[data-benefits-link]").forEach(a=>a.addEventListener("click",event=>{
      const target=document.querySelector(a.hash);if(!target)return;
      event.preventDefault();if(target.tagName==="DETAILS")target.open=true;
      if(a.dataset.benefitsThreshold) {const select=target.querySelector('[id$="-threshold"]');if(select){select.value=a.dataset.benefitsThreshold;select.dispatchEvent(new Event("change"));}}
      target.scrollIntoView({behavior:"instant",block:"center"});window.ScrollTrigger?.refresh();
    }));
    return model;
  } catch(error) {
    document.querySelectorAll("[data-hero-coverage]").forEach(host=>{host.textContent="Confronto non disponibile";});
    document.querySelectorAll("[data-resident-comparison]").forEach(host=>{host.textContent="Confronto non disponibile: nessun miglioramento viene stimato senza le fonti.";host.dataset.residentReady="error";});
    console.warn("Benefits comparison unavailable",error);return null;
  }
}
