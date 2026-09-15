document.addEventListener('DOMContentLoaded', () => {
    const analyzeBtn = document.getElementById('analyze-btn');
    const tacInput = document.getElementById('tac-input');
    const kInput = document.getElementById('k-input');
    const summaryOutput = document.getElementById('summary-output');
    const graphOutput = document.getElementById('graph-output');

    analyzeBtn.addEventListener('click', async () => {
        const code = tacInput.value;
        if (!code.trim()) return;
        const k = parseInt(kInput.value, 10) || 4;

        // UI Feedback
        analyzeBtn.disabled = true;
        analyzeBtn.textContent = 'Analyzing...';
        summaryOutput.textContent = 'Processing...';
        graphOutput.innerHTML = '';

        try {
            const response = await fetch('/api/analyze', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ code: code, k: k }),
            });

            const data = await response.json();

            if (data.error) {
                summaryOutput.textContent = data.error;
                graphOutput.innerHTML = '<span style="color: red;">Failed to generate graph.</span>';
            } else {
                summaryOutput.textContent = data.summary;
                
                // Render DOT graph using d3-graphviz
                if (data.dot) {
                    // Update DOT to look better in our premium UI
                    let premiumDot = data.dot.replace('fillcolor="#e8e8e8"', 'fillcolor="#ffffff" stroke="#c0c0c0" stroke-width="2"');
                    premiumDot = premiumDot.replace(/node \[shape=circle.*/, 'node [shape=circle, style=filled, fontname="Outfit", fontcolor="#111827", color="#6366f1", penwidth=2]; edge [color="#9ca3af", penwidth=1.5];');
                    
                    d3.select("#graph-output")
                      .graphviz()
                      .transition(function () {
                          return d3.transition("main")
                                   .ease(d3.easeLinear)
                                   .delay(100)
                                   .duration(800);
                      })
                      .renderDot(premiumDot);
                } else {
                    graphOutput.innerHTML = '<span>No graph data returned.</span>';
                }
            }
        } catch (error) {
            summaryOutput.textContent = `Error connecting to API:\n${error.message}`;
            graphOutput.innerHTML = '<span style="color: red;">Connection error.</span>';
        } finally {
            analyzeBtn.disabled = false;
            analyzeBtn.textContent = 'Parse & Analyze';
        }
    });
});
