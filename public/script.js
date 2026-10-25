'use strict';

// Native SVG graphs are deliberately self-contained: no CDN, Graphviz, or WASM.
const $ = id => document.getElementById(id);
const NS = 'http://www.w3.org/2000/svg';
const colors = ['#4769af','#38917a','#ba7955','#8a69ac','#cc607e','#849a50','#517d9c','#ad873e'];
const examples = [
  ['simple','Simple'], ['diamond','Branch / diamond'], ['loop','Loop'],
  ['nested_loop','Nested loops'], ['briggs_example','Briggs example'],
  ['high_pressure','High pressure'], ['copy_heavy','Copy heavy']
];
const stageInstructions = {
  graph:'Connected nodes must receive different physical registers. Click a node to inspect neighbors and its assigned register. Isolated nodes are displayed separately.',
  cfg:'Each box represents one basic block. Arrows indicate possible execution paths, including branches and loops.',
  live:'Liveness is calculated from variable uses and control flow. K only changes these sets when a spill rewrite changes the instructions in a later round.',
  color:'The simplification stack is built by removing low-degree nodes (or optimistic candidates); the allocator colors in reverse order.',
  spill:'When the graph cannot be colored with K registers, some values are stored in spill slots and reloaded when needed.',
  output:'This section reports the final rewritten TAC and the scope of its verification.'
};
const state = {data:null, stage:'graph', round:0, view:'explorer', experiment:null, scale:null, pending:0};
const html = text => String(text ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
function svg(tag, attrs={}, parent=null) {
  const el = document.createElementNS(NS,tag);
  for(const [key,value] of Object.entries(attrs)) el.setAttribute(key,String(value));
  if(parent) parent.append(el);
  return el;
}
function label(parent,x,y,value,attrs={}) {
  const el=svg('text',{x,y,'text-anchor':'middle','font-family':'system-ui, sans-serif','font-size':13,fill:'#263b53',...attrs},parent);
  el.textContent=String(value);return el;
}
function title(root,heading,description) {
  const wrapper=document.createElement('div');wrapper.innerHTML=`<h3 class="section-title">${html(heading)}</h3><p class="minor">${html(description)}</p>`;root.append(wrapper);
}
function download(name,content,mime) {
  const url=URL.createObjectURL(new Blob([content],{type:mime}));
  const a=document.createElement('a');a.href=url;a.download=name;document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),800);
}
function table(columns,rows) {
  return `<div class="table-scroll"><table class="data-table"><thead><tr>${columns.map(c=>`<th scope="col">${html(c)}</th>`).join('')}</tr></thead><tbody>${rows.map(row=>`<tr>${row.map(cell=>`<td>${html(cell)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function chooseRound(){return state.data?.stages?.iterations?.[state.round];}
function status(message,isError=false){$('request-status').textContent=message;$('request-status').classList.toggle('error',isError);}
function svgExport(graph,file) {
  if(!graph)return;
  const clone=graph.cloneNode(true);clone.setAttribute('xmlns',NS);
  const markup=new XMLSerializer().serializeToString(clone);
  download(file,markup,'image/svg+xml;charset=utf-8');
}
function toolbar(root,file) {
  const wrap=document.createElement('div');wrap.className='graph-toolbar';
  const note=document.createElement('span');note.textContent='Select nodes to examine their neighbors.';
  const button=document.createElement('button');button.className='secondary-button compact';button.textContent='Save SVG ↓';
  wrap.append(note,button);root.append(wrap);
  button.addEventListener('click',()=>svgExport(root.querySelector('svg'),file));
}
function components(nodes,edges) {
  const adjacency=new Map(nodes.map(n=>[n,new Set()]));
  edges.forEach(([a,b])=>{adjacency.get(a)?.add(b);adjacency.get(b)?.add(a);});
  const remaining=new Set(nodes),out=[];
  while(remaining.size){
    const start=remaining.values().next().value,stack=[start],component=[];remaining.delete(start);
    while(stack.length){const n=stack.pop();component.push(n);for(const v of adjacency.get(n)||[])if(remaining.has(v)){remaining.delete(v);stack.push(v);}}
    out.push(component.sort((a,b)=>a.localeCompare(b,undefined,{numeric:true})));
  }
  out.sort((a,b)=>b.length-a.length||a[0].localeCompare(b[0]));
  return {groups:out,adjacency};
}
// Deterministic force relaxation puts highly connected vertices closer while
// retaining the whole graph in the viewBox. Seed positions never use randomness.
function networkPositions(nodes,edges,width,height){
  const n=nodes.length,point=new Map(),cx=width/2,cy=height/2;
  nodes.forEach((v,i)=>{
    const angle=i*2.399963229728653;const r=Math.min(width,height)*.33*Math.sqrt((i+.5)/n);
    point.set(v,{x:cx+r*Math.cos(angle),y:cy+r*Math.sin(angle)});
  });
  const repel=4600,optimal=Math.min(140,Math.max(75,500/Math.sqrt(n)));
  for(let t=0;t<Math.min(190,70+n*4);t++){
    const force=new Map(nodes.map(v=>[v,{x:0,y:0}]));
    for(let i=0;i<n;i++)for(let j=i+1;j<n;j++){
      const a=nodes[i],b=nodes[j],p=point.get(a),q=point.get(b),dx=p.x-q.x,dy=p.y-q.y,d2=Math.max(80,dx*dx+dy*dy);
      const magnitude=repel/d2,dist=Math.sqrt(d2),fx=dx/dist*magnitude,fy=dy/dist*magnitude;
      force.get(a).x+=fx;force.get(a).y+=fy;force.get(b).x-=fx;force.get(b).y-=fy;
    }
    for(const [a,b] of edges){if(a===b)continue;const p=point.get(a),q=point.get(b),dx=q.x-p.x,dy=q.y-p.y,dist=Math.max(1,Math.hypot(dx,dy)),f=(dist-optimal)*.025;
      force.get(a).x+=dx/dist*f;force.get(a).y+=dy/dist*f;force.get(b).x-=dx/dist*f;force.get(b).y-=dy/dist*f;
    }
    const cooling=1-t/(Math.min(190,70+n*4)+1);
    nodes.forEach(v=>{const p=point.get(v),f=force.get(v);p.x=Math.max(43,Math.min(width-43,p.x+Math.max(-11,Math.min(11,f.x))*cooling));p.y=Math.max(45,Math.min(height-45,p.y+Math.max(-11,Math.min(11,f.y))*cooling));});
  }
  return point;
}
function drawInterference(root,it){
  const fullNames=it.interference.nodes,fullEdges=it.interference.edges,col=it.coloring||{};
  const names=fullNames.slice(0,80),shown=new Set(names),edges=fullEdges.filter(([a,b])=>shown.has(a)&&shown.has(b));
  if(fullNames.length>80){const warning=document.createElement('p');warning.className='minor warning-note';warning.textContent=`Large graph: showing ${names.length} of ${fullNames.length} nodes for responsive rendering. Export JSON for every node and edge.`;root.append(warning);}
  const groups=components(names,edges);const isolated=groups.groups.filter(g=>g.length===1&&!groups.adjacency.get(g[0]).size).flat();
  const connected=groups.groups.filter(g=>g.length>1);
  title(root,'Interference graph',`${fullNames.length} virtual registers · ${fullEdges.length} interference edges · ${connected.length} displayed connected component(s).`);
  if(!connected.length){
    const p=document.createElement('p');p.className='minor';p.textContent='No interference edges: values can reuse physical registers because their live ranges do not overlap.';root.append(p);
    // Still render an actual SVG diagram, rather than an empty white area.
    const frame=document.createElement('div');frame.className='network-frame';root.append(frame);
    const compact=window.innerWidth<650,width=compact?440:660,cols=Math.min(5,Math.max(1,names.length));
    const height=Math.max(160,Math.ceil(names.length/cols)*96+50);
    const graph=svg('svg',{viewBox:`0 0 ${width} ${height}`,class:'graph-svg',role:'img','aria-label':`Interference graph with ${names.length} isolated nodes and no edges`},frame);
    names.forEach((name,i)=>{const row=Math.floor(i/cols),colIndex=i%cols,count=Math.min(cols,names.length-row*cols),x=width/2+(colIndex-(count-1)/2)*Math.min(94,(width-70)/Math.max(1,cols-1)),y=72+row*96,reg=col[name];
      svg('circle',{cx:x,cy:y,r:26,fill:Number.isInteger(reg)?colors[reg%colors.length]:'#e0e6ed',stroke:'#fff','stroke-width':3},graph);
      label(graph,x,y+5,name,{'font-size':14,'font-weight':750,fill:Number.isInteger(reg)?'#fff':'#24384c'});
      if(Number.isInteger(reg))label(graph,x,y+43,`R${reg}`,{'font-size':11,fill:'#576d83'});
    });
    toolbar(root,'interference-graph.svg');
  }
  connected.forEach((group,index)=>{
    const links=edges.filter(([a,b])=>group.includes(a)&&group.includes(b));
    const compact=window.innerWidth<650;
    const height=group.length<=4?225:Math.max(290,Math.min(680,group.length*33+130));
    const width=compact?440:660;
    const frame=document.createElement('div');frame.className='network-frame';root.append(frame);
    const graph=svg('svg',{viewBox:`0 0 ${width} ${height}`,class:'graph-svg',role:'img','aria-label':`Interference component ${index+1}, ${group.length} nodes and ${links.length} edges`},frame);
    const positions=networkPositions(group,links,width,height);
    const neighbors=new Map(group.map(v=>[v,new Set()]));
    links.forEach(([a,b])=>{neighbors.get(a).add(b);neighbors.get(b).add(a);const p=positions.get(a),q=positions.get(b);svg('line',{x1:p.x,y1:p.y,x2:q.x,y2:q.y,class:'graph-line'},graph);});
    const inspector=document.createElement('div');inspector.className='node-inspector';inspector.textContent=`Component ${index+1}: click any node to inspect its allocation.`;root.append(inspector);
    group.forEach(name=>{
      const p=positions.get(name),reg=col[name],assigned=Number.isInteger(reg);
      const g=svg('g',{class:'graph-node',role:'button',tabindex:0,'aria-label':`${name}; ${neighbors.get(name).size} neighbors; ${assigned?'R'+reg:'unassigned'}`},graph);
      svg('circle',{cx:p.x,cy:p.y,r:27,fill:assigned?colors[reg%colors.length]:'#e0e6ed',stroke:'#fff','stroke-width':3},g);
      label(g,p.x,p.y+5,name,{fill:assigned?'#fff':'#24384c','font-size':14,'font-weight':750});
      if(assigned)label(g,p.x,p.y+42,`R${reg}`,{'font-size':11,fill:'#576d83'});
      const inspect=()=>{
        graph.querySelectorAll('.graph-node').forEach(node=>node.classList.remove('selected'));g.classList.add('selected');
        const adjacent=[...neighbors.get(name)].sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
        inspector.textContent=`${name} · degree ${adjacent.length} · ${assigned?'assigned R'+reg:'spill candidate / unassigned'} · neighbors: ${adjacent.join(', ')||'none'}`;
      };
      g.addEventListener('click',inspect);g.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();inspect();}});
    });
    toolbar(root,`interference-component-${index+1}.svg`);
  });
  if(isolated.length&&connected.length){
    const wrap=document.createElement('div');wrap.className='isolates';wrap.innerHTML=`<p>ISOLATED VIRTUAL REGISTERS (${isolated.length}) — can reuse a register</p>`;
    isolated.forEach(n=>{const tag=document.createElement('span');tag.className='isolated-tag';tag.textContent=n+(Number.isInteger(col[n])?` · R${col[n]}`:'');wrap.append(tag);});root.append(wrap);
  }
  const used=[...new Set(Object.values(col))].filter(Number.isInteger).sort((a,b)=>a-b);
  if(used.length){const leg=document.createElement('div');leg.className='graph-legend';used.forEach(k=>{const item=document.createElement('span');item.innerHTML=`<i class="dot" style="background:${colors[k%colors.length]}"></i> R${k}`;leg.append(item);});root.append(leg);}
}
function drawCFG(root,it){
  const allBlocks=it.cfg,blocks=allBlocks.slice(0,50);
  title(root,'Control-flow graph',`${allBlocks.length} basic block(s). Flow goes from top to bottom. Back edges indicate loops.`);
  if(allBlocks.length>50){const warn=document.createElement('p');warn.className='minor warning-note';warn.textContent='Showing the first 50 basic blocks in the graph to avoid oversized SVGs. Export JSON for complete details.';root.append(warn);}
  const width=window.innerWidth<650?440:720,height=Math.max(225,blocks.length*118+65),boxW=window.innerWidth<650?315:330,boxH=79;
  const frame=document.createElement('div');frame.className='network-frame';root.append(frame);
  const graph=svg('svg',{viewBox:`0 0 ${width} ${height}`,class:'graph-svg',role:'img','aria-label':'Control-flow graph showing basic blocks and directed edges'},frame);
  const defs=svg('defs',{},graph);const arrow=svg('marker',{id:'cfg-arrow',markerWidth:9,markerHeight:9,refX:8,refY:4,orient:'auto',viewBox:'0 0 9 8'},defs);svg('path',{d:'M0 0 L9 4 L0 8 z',fill:'#7189a3'},arrow);
  const coords=new Map(blocks.map((block,i)=>[block.name,{x:(width-boxW)/2,y:35+i*118}]));
  blocks.forEach((b,i)=>{const p=coords.get(b.name);for(const s of b.succs){const dest=coords.get(s);if(!dest)continue;const target=blocks.findIndex(v=>v.name===s);let path;
    if(target===i+1){path=`M${width/2} ${p.y+boxH} L${width/2} ${dest.y-5}`;}
    else if(target>i){const bend=width*.83+((target-i)%3)*10;path=`M${p.x+boxW} ${p.y+boxH/2} Q${bend} ${p.y+boxH/2},${bend} ${(p.y+dest.y)/2} T${dest.x+boxW} ${dest.y+boxH/2}`;}
    else {const bend=width*.13-((i-target)%3)*9;path=`M${p.x} ${p.y+boxH/2} Q${bend} ${p.y+boxH/2},${bend} ${(p.y+dest.y)/2} T${dest.x} ${dest.y+boxH/2}`;}
    svg('path',{d:path,fill:'none',stroke:target<=i?'#ba7955':'#7189a3','stroke-width':2,'marker-end':'url(#cfg-arrow)'},graph);
  }});
  blocks.forEach(b=>{const p=coords.get(b.name);svg('rect',{x:p.x,y:p.y,width:boxW,height:boxH,rx:8,fill:b.entry?'#e6eef8':'#f3f7fa',stroke:b.entry?'#5d85b6':'#a9bdce','stroke-width':2},graph);label(graph,width/2,p.y+25,`${b.name}${b.entry?' · ENTRY':''}`,{'font-weight':750,'font-size':15});label(graph,width/2,p.y+45,`${b.instrs.length} instructions · loop depth ${b.loop_depth}`,{'font-size':11,fill:'#607990'});label(graph,width/2,p.y+62,b.instrs.slice(0,1).join('').substring(0,44),{'font-size':11,fill:'#456078'});});
  toolbar(root,'control-flow-graph.svg');
  root.insertAdjacentHTML('beforeend',table(['Block','Depth','Predecessors','Successors','Instructions'],blocks.map(b=>[b.name,b.loop_depth,b.preds.join(', ')||'—',b.succs.join(', ')||'—',b.instrs.join(' | ')])));
}
function renderLiveness(root,it){
  title(root,'Instruction-level liveness','These sets show which values are needed before and after each instruction. ∅ means no live values.');
  it.liveness.forEach(block=>{
    const wrap=document.createElement('section');wrap.className='instruction-block';
    wrap.innerHTML=`<h4>${html(block.block)} · ${block.instructions.length} instructions</h4>`;
    wrap.insertAdjacentHTML('beforeend',table(['Instruction','LIVE before','LIVE after'],block.instructions.map(row=>[row.text,row.before.join(', ')||'∅',row.after.join(', ')||'∅'])));
    root.append(wrap);
  });
  title(root,'Block-level summary','LIVE IN and LIVE OUT represent values at block boundaries, not between every pair of instructions.');
  root.insertAdjacentHTML('beforeend',table(['Block','USE','DEF','LIVE IN','LIVE OUT'],it.liveness.map(b=>[b.block,b.use.join(', ')||'∅',b.def.join(', ')||'∅',b.in.join(', ')||'∅',b.out.join(', ')||'∅'])));
}
function renderColoring(root,it){
  title(root,'Physical-register assignments',`Coloring method: ${it.coloring_method==='bounded_exact_fallback'?'bounded exact search for this small graph':'Chaitin–Briggs simplify / select'}.`);
  root.insertAdjacentHTML('beforeend',table(['Virtual register','Physical register','Note'],Object.entries(it.coloring).sort(([a],[b])=>a.localeCompare(b,undefined,{numeric:true})).map(([name,reg])=>[name,`R${reg}`,it.coalesced_map?.[name]?`Coalesced into ${it.coalesced_map[name]}`:''])));
  title(root,'Simplification stack','Pushed left to right; colors are selected by popping the stack in reverse order.');
  const stack=it.simplify_stack||[];const area=document.createElement('div');area.innerHTML=stack.map((name,i)=>`<span class="chip">${html(name)}${it.optimistic_nodes.includes(name)?' · optimistic':''}</span>`).join('')||'<p class="muted">No simplify steps recorded.</p>';root.append(area);
  title(root,'Copy coalescing','Safe copy pairs can share a physical register without interference.');
  const stats=it.coalescing_stats||{};const p=document.createElement('p');p.className='minor';p.textContent=`Candidate pairs: ${stats.candidates??0} · merged: ${stats.merged??0} · refused: ${stats.refused??0}`;root.append(p);
  if(it.coalescing_trace?.length)root.insertAdjacentHTML('beforeend',table(['Move pair','Outcome','Reason'],it.coalescing_trace.map(x=>[x.pair.join(' / '),x.accepted?'Merged':'Refused',x.reason])));
}
function renderSpills(root,it){
  const s=it.spilling;if(!s.needed){root.innerHTML='<div class="empty-state"><div class="empty-mark">✓</div><h3>No additional spills</h3><p>All virtual registers were assigned in this iteration. Use another iteration to see earlier spill transformations.</p></div>';return;}
  title(root,'Spill candidates',`${s.spilled.length} values did not receive a register in this round.`);
  const span=document.createElement('p');span.innerHTML=s.spilled.map(n=>`<span class="chip">${html(n)}</span>`).join('');root.append(span);
  title(root,'Before spill rewrite','Original instructions in this allocation iteration.');
  const before=document.createElement('pre');before.className='code-block';before.textContent=s.before.join('\n');root.append(before);
  title(root,'After spill rewrite','Loads and stores use memory slots. The next iteration runs on the rewritten program.');
  const after=document.createElement('pre');after.className='code-block';after.textContent=s.after.join('\n');root.append(after);
}
function renderOutput(root){
  const data=state.data,v=data.verification,sem=v.semantic;
  title(root,'Final rewritten TAC',`Outcome: ${data.stages.stop_reason.replaceAll('_',' ')}.`);
  const pre=document.createElement('pre');pre.className='code-block';pre.textContent=data.stages.final.map(ins=>ins.text+(ins.register===null?'':`    // R${ins.register}`)).join('\n');root.append(pre);
  title(root,'Verification status','Interference consistency and bounded TAC interpreter comparison.');
  const note=document.createElement('p');note.className=v.passed?'success-note':'warning-note';
  note.textContent=v.passed?'✓ Interference and interpreter return-value checks passed.':'! Full verification is not confirmed for this input.';root.append(note);
  const details=document.createElement('p');details.className='minor';
  details.textContent=sem.checked?`Interpreter returned ${sem.original_return} before rewriting and ${sem.rewritten_return} afterward.`:`Interpreter check unavailable: ${sem.reason||'unknown cause'}`;root.append(details);
  if(data.stages.stop_reason==='conservative_spill_fallback'){
    const warn=document.createElement('p');warn.className='minor';warn.textContent='The normal heuristic exhausted its retry budget; a conservative full live-range spill pass succeeded. It uses more memory operations, and is not optimal code generation.';root.append(warn);
  }
}
function refreshSummary(){
  if(!state.data)return;const d=state.data,first=d.stages.iterations[0],last=chooseRound();
  const values=[['Virtual registers',first.interference.nodes.length],['Physical registers',d.k],['Spill operations',(d.metrics.num_spill_loads||0)+(d.metrics.num_spill_stores||0)],['Iterations',d.stages.iterations.length]];
  $('metrics-strip').innerHTML=values.map(([name,value])=>`<div><small>${html(name)}</small><b>${html(value)}</b></div>`).join('');
  $('result-note').textContent=`Viewing round ${last.iteration} of ${d.stages.iterations.length} · ${d.stages.stop_reason.replaceAll('_',' ')}`;
}
function renderStage(){
  if(!state.data)return;const iteration=chooseRound();if(!iteration)return;
  refreshSummary();$('stage-help').textContent=stageInstructions[state.stage];const root=$('stage-content');root.replaceChildren();
  try{
    if(state.stage==='graph')drawInterference(root,iteration);
    else if(state.stage==='cfg')drawCFG(root,iteration);
    else if(state.stage==='live')renderLiveness(root,iteration);
    else if(state.stage==='color')renderColoring(root,iteration);
    else if(state.stage==='spill')renderSpills(root,iteration);
    else renderOutput(root);
  }catch(error){root.innerHTML=`<div class="alert">Unable to render this stage: ${html(error.message)}. The compiler result is still available as JSON.</div>`;console.error(error);}
}
async function analyze(){
  const button=$('analyze-btn'),requestId=++state.pending,k=Number($('k-input').value);
  if(!Number.isInteger(k)||k<1||k>32){status('K must be an integer between 1 and 32.',true);return;}
  button.disabled=true;status('Running the Python compiler…');
  try{
    const response=await fetch('/api/analyze',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:$('tac-input').value,k,coalescing:$('coalesce-input').checked})});
    const payload=await response.json();if(requestId!==state.pending)return;
    if(!response.ok||payload.error)throw Error(payload.error||JSON.stringify(payload.detail)||`HTTP ${response.status}`);
    state.data=payload;state.round=0;const select=$('iteration-select');
    select.innerHTML=payload.stages.iterations.map((it,index)=>`<option value="${index}">Round ${it.iteration}${index===0?' · original':''}${index===payload.stages.iterations.length-1&&index!==0?' · final':''}</option>`).join('');
    select.value='0';select.disabled=false;$('export-json').disabled=false;
    const ok=payload.verification.passed,badge=$('result-badge');badge.className=`status-badge ${ok?'success':'failure'}`;
    badge.textContent=ok?'VERIFIED':payload.stages.stop_reason==='iteration_limit'?'RETRY LIMIT':'CHECK REQUIRED';
    renderStage();status(ok?'Analysis complete. Use the stage tabs to explore.':'Analysis complete, but full verification needs attention.');
    if(state.view==='banks')renderBanks();
  }catch(error){state.data=null;$('iteration-select').disabled=true;$('export-json').disabled=true;$('result-badge').textContent='ERROR';$('result-badge').className='status-badge failure';status('Analysis failed: '+error.message,true);$('stage-content').innerHTML=`<div class="alert">${html(error.message)}</div>`;}
  finally{if(requestId===state.pending)button.disabled=false;}
}
function chart(root,samples,key,xkey,xlabel,unit){
  root.replaceChildren();if(!samples?.length){root.innerHTML='<p class="muted">Run an experiment to see measured results.</p>';return;}
  const w=640,h=300,l=73,r=24,top=30,bottom=57,max=Math.max(.000001,...samples.map(s=>s[key]))*1.16;
  const graph=svg('svg',{class:'chart-svg',viewBox:`0 0 ${w} ${h}`,role:'img','aria-label':`${unit} plotted against ${xlabel}`},root);
  for(let i=0;i<=4;i++){const y=top+(h-top-bottom)*i/4;svg('line',{x1:l,y1:y,x2:w-r,y2:y,stroke:'#e2e9ef'},graph);label(graph,l-12,y+4,(max*(1-i/4)).toFixed(key==='runtime_ms'?2:1),{'text-anchor':'end','font-size':11,fill:'#7f91a2'});}
  const bw=(w-l-r)/samples.length;
  samples.forEach((sample,index)=>{const v=sample[key],barH=v/max*(h-top-bottom),x=l+bw*index+bw*.22,y=h-bottom-barH;
    svg('rect',{x,y,width:bw*.56,height:Math.max(barH,.5),rx:3,fill:key==='runtime_ms'?'#4769af':'#38917a'},graph);
    label(graph,x+bw*.28,y-10,Number(v).toFixed(2),{'font-size':11,'font-weight':700});
    label(graph,x+bw*.28,h-bottom+23,`${xkey==='k'?'K=':''}${sample[xkey]}`,{'font-size':12});
  });
}
async function requestExperiment(endpoint,payload,statusId,buttonId){
  const button=$(buttonId);button.disabled=true;$(statusId).textContent='Running repeated measurements…';
  try{const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});
    const data=await response.json();if(!response.ok)throw Error(typeof data.detail==='string'?data.detail:JSON.stringify(data.detail));
    $(statusId).textContent=`Measured ${data.samples.length} configurations successfully.`;return data;
  }catch(error){$(statusId).textContent=`Measurement failed: ${error.message}`;return null;}finally{button.disabled=false;}
}
function readIntegerList(id,min,max,limit){
  const tokens=$(id).value.split(',').map(v=>v.trim()),values=tokens.map(Number);
  if(!values.length||values.length>limit||values.some(v=>!Number.isInteger(v)||v<min||v>max)||new Set(values).size!==values.length)throw Error(`Enter at most ${limit} unique numbers between ${min} and ${max}.`);
  return values;
}
async function runBudget(){
  let ks;try{ks=readIntegerList('experiment-k',1,32,8);}catch(e){$('experiment-status').textContent=e.message;return;}
  const data=await requestExperiment('/api/experiment',{code:$('tac-input').value,register_counts:ks,repeats:Number($('experiment-repeats').value),coalescing:$('coalesce-input').checked},'experiment-status','experiment-run');
  if(!data)return;state.experiment=data;
  chart($('time-chart'),data.samples,'runtime_ms','k','physical registers','runtime');chart($('memory-chart'),data.samples,'peak_memory_kib','k','physical registers','memory');
  $('experiment-table').innerHTML=table(['K','Median ms','Peak KiB','Iterations','Spill ops','Allocated'],data.samples.map(s=>[s.k,s.runtime_ms,s.peak_memory_kib,s.iterations,s.spill_operations,s.success?'Yes':'No']));$('experiment-export').disabled=false;
}
async function runScale(){
  let sizes;try{sizes=readIntegerList('scale-sizes',4,180,7);if(sizes.length<2)throw Error('Provide at least two input sizes.');}catch(e){$('scale-status').textContent=e.message;return;}
  const k=Number($('scale-k').value);if(!Number.isInteger(k)||k<2||k>16){$('scale-status').textContent='K must be 2–16.';return;}
  const data=await requestExperiment('/api/scale-study',{sizes,k,repeats:2},'scale-status','scale-run');if(!data)return;state.scale=data;
  chart($('scale-time-chart'),data.samples,'runtime_ms','size','input instructions','runtime');chart($('scale-memory-chart'),data.samples,'peak_memory_kib','size','input instructions','memory');
}
function renderBanks(){
  const root=$('bank-groups');root.replaceChildren();const k=state.data?.k??Number($('k-input').value),size=Number($('bank-size').value);
  if(!Number.isInteger(k)||k<1||k>32){root.textContent='Select a valid K between 1 and 32.';return;}
  if(!state.data){const p=document.createElement('p');p.className='muted';p.textContent='Run allocation in the explorer to see which virtual registers belong to each physical register.';root.append(p);}
  const mapping=chooseRound()?.coloring||{};
  for(let start=0;start<k;start+=size){const end=Math.min(k,start+size),card=document.createElement('div');card.className='bank-card';
    card.innerHTML=`<h3>Group ${Math.floor(start/size)+1}</h3><p>Physical registers R${start}–R${end-1}</p>`;
    for(let r=start;r<end;r++){
      const names=Object.entries(mapping).filter(([,n])=>n===r).map(([n])=>n).sort((a,b)=>a.localeCompare(b,undefined,{numeric:true}));
      const slot=document.createElement('div');slot.className='register-slot';slot.innerHTML=`<strong><i class="dot" style="background:${colors[r%colors.length]}"></i> R${r}</strong><span>${names.length?names.map(html).join(', '):'No assignment'}</span>`;card.append(slot);
    }root.append(card);
  }
}
function navigate(view){
  state.view=view;for(const button of document.querySelectorAll('.nav-item')){const active=button.dataset.view===view;button.classList.toggle('active',active);if(active)button.setAttribute('aria-current','page');else button.removeAttribute('aria-current');}
  for(const name of ['explorer','complexity','banks','guide'])$(name+'-view').hidden=name!==view;
  const texts={explorer:['Allocation explorer','Trace how virtual registers become physical registers, one compiler stage at a time.'],complexity:['Complexity analysis','Measure how allocator runtime and memory vary with K and input size.'],banks:['Register banks','Inspect physical-register groups and the virtual values mapped to each one.'],guide:['Learning guide','A practical walkthrough of TAC, control flow, liveness, graph coloring and spilling.']};
  $('page-title').textContent=texts[view][0];$('page-description').textContent=texts[view][1];$('breadcrumb').textContent=texts[view][0];
  if(view==='banks')renderBanks();document.querySelector('.sidebar').classList.remove('open');$('menu-toggle').setAttribute('aria-expanded','false');window.scrollTo({top:0,behavior:'auto'});
}
function markStale(){if(state.data){status('Source or settings changed. Run analysis to refresh the results.');$('result-badge').textContent='STALE';$('result-badge').className='status-badge neutral';}}
function addExampleButtons(){
  for(const [name,titleText] of examples){const b=document.createElement('button');b.type='button';b.className='example-button';b.textContent=titleText;
    b.addEventListener('click',async()=>{try{const response=await fetch(`/examples/${name}.tac`);if(!response.ok)throw Error('Example unavailable');$('tac-input').value=await response.text();markStale();status(`Loaded ${titleText}. Select Run analysis to continue.`);document.querySelectorAll('.example-button').forEach(item=>item.classList.toggle('active',item===b));}catch(error){status(error.message,true);}});
    $('bench-buttons').append(b);
  }
}
window.addEventListener('DOMContentLoaded',()=>{
  addExampleButtons();navigate('explorer');$('analyze-btn').addEventListener('click',analyze);
  $('reset-btn').addEventListener('click',()=>{$('tac-input').value='func main\n  t1 = 1\n  t2 = 2\n  t3 = t1 + t2\n  t4 = t3\n  t5 = t4 * 2\n  ret t5\nend';$('k-input').value=4;$('coalesce-input').checked=true;markStale();status('Default example restored. Run analysis to update results.');});
  $('tac-input').addEventListener('input',markStale);
  for(const id of ['k-input','coalesce-input'])$(id).addEventListener('change',()=>{markStale();});
  $('iteration-select').addEventListener('change',event=>{state.round=Number(event.target.value);renderStage();if(state.view==='banks')renderBanks();});
  document.querySelectorAll('.stage-tab').forEach(button=>button.addEventListener('click',()=>{state.stage=button.dataset.stage;for(const tab of document.querySelectorAll('.stage-tab')){const selected=tab===button;tab.classList.toggle('active',selected);tab.setAttribute('aria-selected',selected?'true':'false');}renderStage();}));
  document.querySelectorAll('.nav-item').forEach(button=>button.addEventListener('click',()=>navigate(button.dataset.view)));
  $('help-open').addEventListener('click',()=>navigate('guide'));$('guide-start').addEventListener('click',()=>navigate('explorer'));
  $('experiment-run').addEventListener('click',runBudget);$('scale-run').addEventListener('click',runScale);
  $('bank-size').addEventListener('change',renderBanks);$('banks-refresh').addEventListener('click',renderBanks);
  $('export-json').addEventListener('click',()=>state.data&&download('allocation-results.json',JSON.stringify(state.data,null,2),'application/json'));
  $('experiment-export').addEventListener('click',()=>{if(!state.experiment)return;const rows=['k,runtime_ms,peak_memory_kib,iterations,spill_operations,success',...state.experiment.samples.map(d=>[d.k,d.runtime_ms,d.peak_memory_kib,d.iterations,d.spill_operations,d.success].join(','))];download('allocation-complexity.csv',rows.join('\n'),'text/csv');});
  $('menu-toggle').addEventListener('click',()=>{const sidebar=document.querySelector('.sidebar');const open=sidebar.classList.toggle('open');$('menu-toggle').setAttribute('aria-expanded',String(open));});
  chart($('time-chart'),[],'runtime_ms','k','register budget','runtime');chart($('memory-chart'),[],'peak_memory_kib','k','register budget','memory');chart($('scale-time-chart'),[],'runtime_ms','size','input instructions','runtime');chart($('scale-memory-chart'),[],'peak_memory_kib','size','input instructions','memory');
});
