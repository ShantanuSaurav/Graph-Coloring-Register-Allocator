document.addEventListener('DOMContentLoaded', () => {
    const analyzeBtn = document.getElementById('analyze-btn');
    const tacInput = document.getElementById('tac-input');
    const kInput = document.getElementById('k-input');
    const coalesceInput = document.getElementById('coalesce-input');
    const headline = document.getElementById('result-headline');
    const tabBar = document.getElementById('tab-bar');
    const tabContent = document.getElementById('tab-content');
    const benchButtons = document.getElementById('bench-buttons');

    const BENCHMARKS = ['simple', 'diamond', 'loop', 'nested_loop', 'briggs_example',
                         'high_pressure', 'copy_heavy'];

    const TABS = [
        { id: 'summary', label: 'Input' },
        { id: 'cfg', label: 'CFG' },
        { id: 'liveness', label: 'Liveness' },
        { id: 'interference', label: 'Interference Graph' },
        { id: 'coalescing', label: 'Coalescing' },
        { id: 'registers', label: 'Registers' },
        { id: 'spills', label: 'Spills' },
        { id: 'metrics', label: 'Metrics' },
        { id: 'final', label: 'Final Output' },
        { id: 'verify', label: 'Verification' },
    ];

    let lastData = null;

    // ---- benchmark quick-load buttons -------------------------------------
    BENCHMARKS.forEach((name) => {
        const btn = document.createElement('button');
        btn.className = 'bench-btn';
        btn.textContent = name;
        btn.addEventListener('click', async () => {
            try {
                const resp = await fetch(`benchmarks/${name}.tac`);
                if (resp.ok) {
                    tacInput.value = await resp.text();
                }
            } catch (e) {
                // benchmarks/ isn't always served statically (e.g. plain `python -m http.server`
                // without the vercel rewrite) -- fail quietly, the button is a convenience only.
            }
        });
        benchButtons.appendChild(btn);
    });

    // ---- tab scaffolding ----------------------------------------------------
    function buildTabs() {
        tabBar.innerHTML = '';
        tabContent.innerHTML = '';
        TABS.forEach((tab, i) => {
            const btn = document.createElement('button');
            btn.className = 'tab-btn' + (i === 0 ? ' active' : '');
            btn.textContent = tab.label;
            btn.dataset.tab = tab.id;
            btn.addEventListener('click', () => selectTab(tab.id));
            tabBar.appendChild(btn);

            const pane = document.createElement('div');
            pane.className = 'tab-pane' + (i === 0 ? ' active' : '');
            pane.id = `pane-${tab.id}`;
            tabContent.appendChild(pane);
        });
    }

    function selectTab(id) {
        document.querySelectorAll('.tab-btn').forEach((b) => b.classList.toggle('active', b.dataset.tab === id));
        document.querySelectorAll('.tab-pane').forEach((p) => p.classList.toggle('active', p.id === `pane-${id}`));
        if (id === 'interference') renderInterferenceGraph();
        if (id === 'cfg') renderCfgGraph();
    }

    function esc(s) {
        const div = document.createElement('div');
        div.textContent = String(s);
        return div.innerHTML;
    }

    // ---- per-tab renderers ---------------------------------------------------
    function renderSummary(data) {
        document.getElementById('pane-summary').innerHTML =
            `<pre class="output-box">${esc(data.summary)}</pre>`;
    }

    function renderCfgFlow(cfg) {
        // A dependency-free fallback/companion view (Feature 8 allows "a simple
        // HTML/SVG/DOM representation"): every block as a box, with its successors
        // listed as arrows -- built straight from the backend's succs/preds, not
        // reconstructed structure. Always renders, regardless of whether the
        // Graphviz/WASM CDN scripts loaded.
        return `<div class="cfg-flow">${cfg.map((b) => `
            <div class="cfg-flow-node">
                <div class="cfg-flow-box">${esc(b.name)}${b.entry ? ' &#9733;' : ''}<br><small>depth ${b.loop_depth}</small></div>
                ${b.succs.length ? `<div class="cfg-flow-arrow">&rarr; ${b.succs.map(esc).join(', ')}</div>` : '<div class="cfg-flow-arrow">(exit)</div>'}
            </div>`).join('')}</div>`;
    }

    function renderCfg(data) {
        const last = data.stages.iterations[data.stages.iterations.length - 1];
        let html = renderCfgFlow(last.cfg);
        html += '<div id="cfg-graph" class="output-box graph-container" style="min-height:220px;margin:1rem 0;"></div>';
        html += last.cfg.map((b) => `
            <div class="block-card">
                <h3>${esc(b.name)}${b.entry ? ' (entry)' : ''}</h3>
                <div class="meta">loop_depth=${b.loop_depth} &nbsp; preds=${JSON.stringify(b.preds)} &nbsp; succs=${JSON.stringify(b.succs)}</div>
                ${b.instrs.map((i) => `<div>${esc(i)}</div>`).join('')}
            </div>`).join('');
        document.getElementById('pane-cfg').innerHTML = html;
    }

    function renderCfgGraph() {
        if (!lastData) return;
        const last = lastData.stages.iterations[lastData.stages.iterations.length - 1];
        const target = document.getElementById('cfg-graph');
        if (!target || !last.cfg_dot) return;
        d3.select('#cfg-graph').graphviz().renderDot(last.cfg_dot);
    }

    function renderLiveness(data) {
        const last = data.stages.iterations[data.stages.iterations.length - 1];
        const html = last.liveness.map((b) => `
            <div class="block-card">
                <h3>${esc(b.block)}</h3>
                <div class="live-row">USE = <span class="live-tag">{${b.use.join(', ')}}</span></div>
                <div class="live-row">DEF = <span class="live-tag">{${b.def.join(', ')}}</span></div>
                <div class="live-row">IN&nbsp;&nbsp; = <span class="live-tag">{${b.in.join(', ')}}</span></div>
                <div class="live-row">OUT = <span class="live-tag">{${b.out.join(', ')}}</span></div>
            </div>`).join('');
        document.getElementById('pane-liveness').innerHTML = html || '<p>No blocks.</p>';
    }

    function renderInterference(data) {
        document.getElementById('pane-interference').innerHTML =
            '<div id="interference-graph" class="output-box graph-container"></div>';
    }

    function renderInterferenceGraph() {
        if (!lastData || !lastData.dot) return;
        let premiumDot = lastData.dot.replace('fillcolor="#e8e8e8"', 'fillcolor="#ffffff" stroke="#c0c0c0" stroke-width="2"');
        premiumDot = premiumDot.replace(/node \[shape=circle.*/, 'node [shape=circle, style=filled, fontname="Outfit", fontcolor="#111827", color="#6366f1", penwidth=2]; edge [color="#9ca3af", penwidth=1.5];');
        d3.select('#interference-graph').graphviz().renderDot(premiumDot);
    }

    function renderCoalescing(data) {
        let html = '';
        data.stages.iterations.forEach((it) => {
            html += `<div class="iteration-block"><h4>Iteration ${it.iteration}</h4>`;
            const s = it.coalescing_stats;
            html += `<p>${s.candidates} candidate(s) &middot; ${s.merged} merged &middot; ${s.refused} refused</p>`;
            if (it.coalescing_trace.length === 0) {
                html += '<p style="color:var(--text-secondary)">No candidates in this iteration.</p>';
            }
            it.coalescing_trace.forEach((entry) => {
                const cls = entry.accepted ? 'accepted' : 'refused';
                const verdict = entry.accepted ? 'ACCEPTED' : 'REFUSED';
                html += `<div class="coalesce-row ${cls}"><span>${esc(entry.pair[0])} &harr; ${esc(entry.pair[1])}</span><span>${verdict} &mdash; ${esc(entry.reason)}</span></div>`;
            });
            html += '</div>';
        });
        document.getElementById('pane-coalescing').innerHTML = html;
    }

    function renderRegisters(data) {
        const last = data.stages.iterations[data.stages.iterations.length - 1];
        let html = '<div class="block-card">';
        const entries = Object.entries(last.coloring);
        if (entries.length === 0) {
            html += '<p>No colouring available.</p>';
        } else {
            entries.forEach(([v, r]) => { html += `<div>${esc(v)} &rarr; R${r}</div>`; });
        }
        html += '</div>';
        document.getElementById('pane-registers').innerHTML = html;
    }

    function renderSpills(data) {
        let html = '';
        data.stages.iterations.forEach((it) => {
            html += `<div class="iteration-block"><h4>Iteration ${it.iteration}</h4>`;
            if (!it.spilling.needed) {
                html += '<p style="color:var(--text-secondary)">No spilling needed this iteration.</p>';
            } else {
                html += `<p>Spilled: ${it.spilling.spilled.join(', ')}</p>`;
                html += '<div class="spill-columns">';
                html += `<div><strong>BEFORE</strong><pre>${esc(it.spilling.before.join('\n'))}</pre></div>`;
                html += `<div><strong>AFTER</strong><pre>${esc(it.spilling.after.join('\n'))}</pre></div>`;
                html += '</div>';
            }
            html += '</div>';
        });
        document.getElementById('pane-spills').innerHTML = html;
    }

    function renderMetrics(data) {
        const m = data.metrics;
        const labels = {
            k: 'K', num_input_instructions: 'Input instructions', num_virtual_registers: 'Virtual registers',
            num_cfg_blocks: 'CFG blocks', num_cfg_edges: 'CFG edges',
            num_interference_nodes: 'Graph nodes', num_interference_edges: 'Graph edges',
            max_interference_degree: 'Max degree', num_move_instructions: 'Move instructions',
            num_coalescing_candidates: 'Coalesce candidates', num_coalescing_merges: 'Coalesce merges',
            num_coalescing_refused: 'Coalesce refused', num_redundant_move_instructions: 'Redundant moves',
            num_spilled_vregs: 'Spilled vregs', num_spill_loads: 'Spill loads', num_spill_stores: 'Spill stores',
            num_retry_iterations: 'Retry iterations', num_final_physical_registers: 'Physical registers used',
            num_final_instructions: 'Final instructions',
        };
        let html = '<div class="metrics-grid">';
        Object.entries(labels).forEach(([key, label]) => {
            html += `<div class="metric-tile"><div class="value">${esc(m[key])}</div><div class="label">${esc(label)}</div></div>`;
        });
        html += `<div class="metric-tile"><div class="value">${m.success ? 'SUCCESS' : 'FAILED'}</div><div class="label">Allocation result</div></div>`;
        html += '</div>';
        document.getElementById('pane-metrics').innerHTML = html;
    }

    function renderFinal(data) {
        const html = data.stages.final.map((line) =>
            `<div>${esc(line.text)}${line.register !== null && line.register !== undefined ? `    <span style="color:var(--accent-color)"># R${line.register}</span>` : ''}</div>`
        ).join('');
        document.getElementById('pane-final').innerHTML = `<div class="block-card">${html}</div>`;
    }

    function renderVerify(data) {
        const v = data.verification;
        const item = (ok, label) => `<li class="${ok ? 'verify-ok' : 'verify-bad'}">${ok ? '✓' : '✗'} ${esc(label)}</li>`;
        let html = '<ul class="verify-list">';
        html += item(v.all_registers_handled, 'All virtual registers handled');
        html += item(v.no_interfering_share_a_register, 'No interfering nodes share a register');
        html += item(v.spill_rewrite_completed, 'Spill rewrite completed');
        html += item(v.no_unresolved_spill, 'No unresolved spill');
        html += item(v.pipeline_converged, 'Pipeline converged');
        html += '</ul>';
        if (v.problems && v.problems.length) {
            html += `<div class="block-card"><strong>Problems:</strong><br>${v.problems.map(esc).join('<br>')}</div>`;
        }
        html += `<h3 style="margin-top:1rem;color:${v.passed ? '#3aa76d' : '#e15759'}">RESULT: ${v.passed ? 'SUCCESS' : 'FAILURE'}</h3>`;
        document.getElementById('pane-verify').innerHTML = html;
    }

    function renderAll(data) {
        lastData = data;
        buildTabs();
        renderSummary(data);
        renderCfg(data);
        renderLiveness(data);
        renderInterference(data);
        renderCoalescing(data);
        renderRegisters(data);
        renderSpills(data);
        renderMetrics(data);
        renderFinal(data);
        renderVerify(data);
        selectTab('summary');
        headline.textContent = `Results — ${data.metrics.success ? 'SUCCESS' : 'FAILED'} (K=${data.k}, coalescing ${data.coalescing ? 'on' : 'off'})`;
    }

    analyzeBtn.addEventListener('click', async () => {
        const code = tacInput.value;
        if (!code.trim()) return;
        const k = parseInt(kInput.value, 10) || 4;
        const coalescing = coalesceInput.checked;

        analyzeBtn.disabled = true;
        analyzeBtn.textContent = 'Analyzing...';
        headline.textContent = 'Analyzing...';

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code, k, coalescing }),
            });

            if (!response.ok) {
                const text = await response.text();
                throw new Error(`API returned HTTP ${response.status}: ${text.slice(0, 300)}`);
            }

            const data = await response.json();

            if (data.error) {
                buildTabs();
                document.getElementById('pane-summary').innerHTML = `<pre class="output-box" style="color:#e15759">${esc(data.error)}</pre>`;
                selectTab('summary');
                headline.textContent = 'Error';
            } else if (!data.stages || !data.metrics || !data.verification) {
                // Defensive: an API response that isn't an error but also doesn't have
                // the shape this dashboard expects (e.g. a stale/mismatched deployment)
                // should say so clearly rather than throwing deep inside a renderer.
                throw new Error('API response is missing expected fields (stages/metrics/verification). '
                    + 'The deployed backend may be out of date.');
            } else {
                renderAll(data);
            }
        } catch (error) {
            buildTabs();
            document.getElementById('pane-summary').innerHTML = `<pre class="output-box" style="color:#e15759">Error connecting to API:\n${esc(error.message)}</pre>`;
            selectTab('summary');
            headline.textContent = 'Connection error';
        } finally {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = 'Parse & Analyze';
        }
    });

    buildTabs();
});
