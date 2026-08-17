(() => {
  const D = window.DASHBOARD_DATA;
  const $ = (s, root=document) => root.querySelector(s);
  const $$ = (s, root=document) => [...root.querySelectorAll(s)];
  const pct = (v, d=1) => `${(v*100).toFixed(d)}%`;
  const nfmt = new Intl.NumberFormat('en-IN');
  const fmtInt = v => nfmt.format(Math.round(v));
  const compact = (v, d=1) => {
    const a=Math.abs(v); const sign=v<0?'-':'';
    if(a>=1e12) return sign+(a/1e12).toFixed(d)+'T';
    if(a>=1e9) return sign+(a/1e9).toFixed(d)+'B';
    if(a>=1e6) return sign+(a/1e6).toFixed(d)+'M';
    if(a>=1e3) return sign+(a/1e3).toFixed(d)+'K';
    return sign+Math.round(a);
  };
  const su = v => `${compact(v)} SU`;
  const escapeHtml = s => String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

  // Hero
  const hero = [
    ['Journey sessions', compact(D.core.journey_sessions)],
    ['Successful buyers', compact(D.core.successful_buyers)],
    ['Successful order value', su(D.core.gmv_source_units)],
    ['Payment success', pct(D.core.payment_success_rate)],
  ];
  $('#heroKpis').innerHTML = hero.map(([l,v])=>`<div class="hero-kpi"><span>${l}</span><strong>${v}</strong></div>`).join('');
  const d30Rows = D.retention_curve.filter(x=>x.window_days===30);
  const d30All = d30Rows.reduce((a,x)=>a+x.retained,0)/d30Rows.reduce((a,x)=>a+x.buyers,0);
  $('#d30All').textContent=pct(d30All);
  $('#d30Meter').style.width=`${Math.min(100,d30All*100)}%`;

  // AARRR
  const cards = [
    {l:'A',name:'Acquisition',value:compact(D.core.registered_customers),copy:'registered customers in the source customer table',accent:'#ff905a'},
    {l:'A',name:'Activation',value:pct(D.core.registered_to_successful_buyer_rate),copy:'registered → at least one successful purchase',accent:'#ff3f6c'},
    {l:'R',name:'Retention',value:pct(d30All),copy:'repeat purchase by D30 among mature first-purchase cohorts',accent:'#6b4eff'},
    {l:'R',name:'Revenue',value:su(D.core.aov_source_units),copy:'average successful order value (source units)',accent:'#03a685'},
    {l:'R',name:'Referral',value:'Not captured',copy:'invite/referrer linkage does not exist in this dataset',accent:'#94969f',missing:true}
  ];
  $('#aarrrGrid').innerHTML=cards.map(c=>`<article class="aarrr-card ${c.missing?'missing':''}" style="--accent:${c.accent}"><div class="letter">${c.l}</div><h3>${c.name}</h3><strong>${c.value}</strong><p>${c.copy}</p></article>`).join('');
  $('#activationLag').textContent=`${D.activation_lag.median_days.toFixed(1)} days`;
  const mobile = D.traffic.find(x=>x.traffic_source==='MOBILE');
  $('#mobileShare').textContent=pct(mobile.sessions/D.core.journey_sessions);
  $('#promoShare').textContent=pct(D.core.promo_order_share);
  $('#repeatShare').textContent=pct(D.core.repeat_buyer_rate);

  // Funnel
  const maxF = D.funnel[0].sessions;
  $('#funnelChart').innerHTML=D.funnel.map((x,i)=>`<div class="funnel-row"><div class="funnel-label">${escapeHtml(x.stage)}</div><div class="funnel-track"><div class="funnel-fill" style="width:${Math.max(3,x.sessions/maxF*100)}%;opacity:${1-i*.1}"><span>${pct(x.rate)}</span></div></div><div class="funnel-count">${compact(x.sessions)}</div></div>`).join('');
  $('#behaviorBars').innerHTML=D.behavior.map(x=>`<div><div class="metric-bar-head"><span>${escapeHtml(x.event)}</span><strong>${pct(x.rate)}</strong></div><div class="bar-track"><div class="bar-fill" style="width:${x.rate*100}%"></div></div></div>`).join('');

  // Traffic
  const web=D.traffic.find(x=>x.traffic_source==='WEB'); const mobileShare=mobile.sessions/D.core.journey_sessions;
  $('#trafficDonut').innerHTML=`<div class="donut" style="background:conic-gradient(#ff3f6c 0 ${mobileShare*360}deg,#6b4eff ${mobileShare*360}deg 360deg)"><div class="donut-center"><strong>${pct(mobileShare,0)}</strong><span>Mobile</span></div></div><div class="legend"><div class="legend-row"><i class="legend-dot" style="background:#ff3f6c"></i><span>Mobile · ${compact(mobile.sessions)}</span></div><div class="legend-row"><i class="legend-dot" style="background:#6b4eff"></i><span>Web · ${compact(web.sessions)}</span></div><div class="legend-row" style="margin-top:10px;color:#94969f">Volume differs. Quality barely does.</div></div>`;
  $('#trafficTable').innerHTML=D.traffic.map(x=>`<tr><td>${x.traffic_source}</td><td>${compact(x.sessions)}</td><td class="good">${pct(x.payment_success_rate)}</td><td>${su(x.aov_source_units)}</td></tr>`).join('');

  // Promo comparison toggles
  const P=D.promo_comparison;
  function renderPromo(mode){
    const raw=mode==='raw'; const no=raw?P.raw_no_promo_rate:P.adjusted_no_promo_rate; const yes=raw?P.raw_promo_rate:P.adjusted_promo_rate; const gap=(no-yes)*100;
    $('#noPromoRate').textContent=pct(no); $('#promoRate').textContent=pct(yes); $('#gapLabel').textContent=raw?'Raw gap':'Adjusted gap'; $('#gapValue').textContent=`${gap.toFixed(1)} pp`;
    $('#gapText').textContent=raw?`A naive comparison implies promo-acquired buyers retain ${Math.abs(P.raw_relative_gap*100).toFixed(1)}% worse on a relative basis.`:'After comparing within acquisition month, most of the raw difference disappears.';
    $$('.toggle [data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));
  }
  $$('.toggle [data-mode]').forEach(b=>b.addEventListener('click',()=>renderPromo(b.dataset.mode))); renderPromo('raw');
  $('#rawGapText').textContent=`${P.raw_gap_pp.toFixed(1)} pp (${(P.raw_relative_gap*100).toFixed(1)}% relative)`;
  $('#adjustedGapText').textContent=`${P.adjusted_gap_pp.toFixed(1)} pp`;

  // SVG line chart util
  function lineChart(el, labels, series, opts={}){
    const W=760,H=300,m={l:48,r:20,t:22,b:44}, iw=W-m.l-m.r, ih=H-m.t-m.b;
    const all=series.flatMap(s=>s.values.filter(v=>v!=null)); const ymin=opts.ymin ?? 0; const ymax=opts.ymax ?? Math.max(...all)*1.08;
    const x=i=>m.l+(labels.length===1?iw/2:i*iw/(labels.length-1)); const y=v=>m.t+ih-(v-ymin)/(ymax-ymin)*ih;
    let svg=`<svg viewBox="0 0 ${W} ${H}" role="img"><g>`;
    for(let i=0;i<=4;i++){const val=ymin+(ymax-ymin)*i/4, yy=y(val); svg+=`<line class="grid" x1="${m.l}" y1="${yy}" x2="${W-m.r}" y2="${yy}"/><text class="axis" x="${m.l-8}" y="${yy+3}" text-anchor="end">${opts.yfmt?opts.yfmt(val):Math.round(val)}</text>`}
    labels.forEach((lab,i)=>{ if(i===0||i===labels.length-1||labels.length<=8||i%Math.ceil(labels.length/6)===0) svg+=`<text class="axis" x="${x(i)}" y="${H-14}" text-anchor="middle">${lab}</text>`; });
    const colors=['#ff3f6c','#6b4eff','#03a685','#ff905a'];
    series.forEach((s,si)=>{
      const pts=s.values.map((v,i)=>v==null?null:[x(i),y(v)]).filter(Boolean); const path=pts.map((p,i)=>(i?'L':'M')+p[0].toFixed(1)+','+p[1].toFixed(1)).join(' '); svg+=`<path class="line" d="${path}" stroke="${s.color||colors[si]}"/>`;
      pts.forEach((p,i)=>svg+=`<circle class="point" cx="${p[0]}" cy="${p[1]}" r="4" fill="${s.color||colors[si]}"><title>${s.name}: ${opts.tooltip?opts.tooltip(s.values[i]):s.values[i]}</title></circle>`);
    });
    svg+='</g></svg><div class="chart-legend">'+series.map((s,i)=>`<span><i style="background:${s.color||colors[i]}"></i>${s.name}</span>`).join('')+'</div>'; el.innerHTML=svg;
  }
  const windows=[7,30,60,90];
  const noVals=windows.map(w=>D.retention_curve.find(x=>x.window_days===w&&x.segment==='No promo').rate);
  const prVals=windows.map(w=>D.retention_curve.find(x=>x.window_days===w&&x.segment==='Promo').rate);
  lineChart($('#retentionChart'),windows.map(x=>'D'+x),[{name:'No promo',values:noVals,color:'#282c3f'},{name:'Promo',values:prVals,color:'#ff3f6c'}],{ymin:0,ymax:.5,yfmt:v=>`${Math.round(v*100)}%`,tooltip:v=>pct(v)});

  // Simulator
  const slider=$('#liftSlider');
  function renderSim(){const lift=+slider.value/100; const rate=P.raw_promo_rate*(1+lift); const inc=P.mature_promo_buyers*P.raw_promo_rate*lift; const value=inc*P.promo_second_order_aov_source_units; $('#liftValue').textContent=`${slider.value}%`; $('#simRate').textContent=pct(rate); $('#simBuyers').textContent=`+${fmtInt(inc)}`; $('#simValue').textContent=`+${su(value)}`;}
  slider.addEventListener('input',renderSim); renderSim();

  // Heatmap
  const heat=D.cohort_heatmap; let heatHtml='<div class="heatmap"><div></div>'+[0,1,2,3,4,5,6].map(i=>`<div class="heat-head">M${i}</div>`).join('');
  heat.forEach(r=>{heatHtml+=`<div class="heat-label">${r.cohort}<br><span style="font-size:9px;color:#94969f">n=${fmtInt(r.size)}</span></div>`; for(let i=0;i<=6;i++){const v=r['m'+i]; const alpha=.08+Math.min(.88,v*.82); const text=v>.55?'#fff':'#282c3f'; heatHtml+=`<div class="heat-cell" title="${r.cohort} · M${i}: ${pct(v)}" style="background:rgba(255,63,108,${alpha});color:${text}">${pct(v,0)}</div>`;}}); heatHtml+='</div>'; $('#cohortHeatmap').innerHTML=heatHtml;

  // Monthly trend toggle
  const last24=D.monthly.slice(-24);
  function renderTrend(kind){
    if(kind==='gmv') lineChart($('#monthlyChart'),last24.map(x=>x.month),[{name:'Successful order value',values:last24.map(x=>x.gmv_source_units),color:'#ff3f6c'}],{ymin:0,yfmt:v=>compact(v),tooltip:v=>su(v)});
    else lineChart($('#monthlyChart'),last24.map(x=>x.month),[{name:'Returning buyer value share',values:last24.map(x=>x.returning_gmv_share),color:'#6b4eff'}],{ymin:.7,ymax:1,yfmt:v=>pct(v,0),tooltip:v=>pct(v)});
    $$('[data-trend]').forEach(b=>b.classList.toggle('active',b.dataset.trend===kind));
  }
  $$('[data-trend]').forEach(b=>b.addEventListener('click',()=>renderTrend(b.dataset.trend))); renderTrend('gmv');

  // Category bars
  const cats=D.category_sales.slice(0,6); $('#categoryBars').innerHTML=cats.map(x=>`<div><div class="metric-bar-head"><span>${escapeHtml(x.category)}</span><strong>${pct(x.share)}</strong></div><div class="bar-track"><div class="bar-fill" style="width:${x.share*100}%"></div></div></div>`).join('');

  // Tables
  $('#promoTable').innerHTML=D.promo_codes.slice(0,8).map(x=>`<tr><td class="hot-text">${escapeHtml(x.first_promo_code)}</td><td>${fmtInt(x.buyers)}</td><td>${pct(x.retention30)}</td><td>${su(x.first_aov)}</td></tr>`).join('');
  $('#paymentTable').innerHTML=D.payment_methods.map(x=>`<tr><td>${escapeHtml(x.payment_method)}</td><td>${compact(x.transactions)}</td><td class="good">${pct(x.success_rate)}</td></tr>`).join('');

  // Data quality
  const q=D.quality; const qs=[['Session ↔ transaction mismatch',`${q.transaction_sessions_missing_clickstream}`],['Customer FK misses',`${q.transaction_customer_ids_missing_customer_table}`],['Product IDs matched',pct(q.successful_line_item_product_match_rate)],['Successful line items',compact(q.successful_line_items_parsed)]];
  $('#qualityStats').innerHTML=qs.map(([l,v])=>`<div class="quality-stat"><strong>${v}</strong><span>${l}</span></div>`).join('');

  // Smooth nav section highlighting (small progressive enhancement)
  const navLinks=$$('.nav-links a'); const sections=navLinks.map(a=>document.querySelector(a.getAttribute('href'))).filter(Boolean);
  const obs=new IntersectionObserver(entries=>{entries.forEach(e=>{if(e.isIntersecting){navLinks.forEach(a=>a.style.color=''); const a=navLinks.find(x=>x.getAttribute('href')==='#'+e.target.id); if(a)a.style.color='#ff3f6c';}})},{rootMargin:'-35% 0px -55% 0px'}); sections.forEach(s=>obs.observe(s));
})();
