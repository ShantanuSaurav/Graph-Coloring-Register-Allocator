import gradio as gr
from src.frontend.parser import parse, ParseError
from src.analysis.interference import build_graph
import traceback

def process_tac(tac_code):
    try:
        # Step 1: Parse
        fn = parse(tac_code)
        instrs = getattr(fn, "_parsed_instrs", [])
        
        # Build CFG / Parse summary
        summary = f"Parsed function {fn.name!r}: {len(instrs)} instructions\n\n"
        summary += "Instructions:\n"
        for i, ins in enumerate(instrs):
            summary += f"  {i:3d}  {ins}\n"
        
        vregs = sorted({v for ins in instrs for v in (ins.defs() | ins.uses())},
                       key=lambda s: int(s[1:]))
        summary += f"\nVirtual registers ({len(vregs)}): {', '.join(vregs)}\n"

        # Step 2: Build Interference Graph
        try:
            g = build_graph(fn)
            dot_code = g.to_dot()
            # Wrap dot_code in markdown graphviz format or just return it as str
        except Exception as e:
            dot_code = f"Error building graph: {str(e)}\n\n{traceback.format_exc()}"
            
        return summary, dot_code

    except ParseError as e:
        return f"Parse Error: {str(e)}", ""
    except Exception as e:
        return f"Unexpected Error: {str(e)}\n\n{traceback.format_exc()}", ""


default_tac = """func main
  t1 = 1
  t2 = 2
  t3 = t1 + t2
  t4 = t3
  t5 = t4 * 2
  ret t5
end
"""

with gr.Blocks(title="Regalloc A5 - Graph-Coloring Register Allocator") as demo:
    gr.Markdown("# 🚀 Graph-Coloring Register Allocator (M1 & M2)")
    gr.Markdown("Visualize the frontend parsing and interference graph generation (M2).")
    
    with gr.Row():
        with gr.Column():
            tac_input = gr.Code(label="Three-Address Code (TAC)", value=default_tac, language="python", lines=15)
            btn = gr.Button("Parse & Analyze", variant="primary")
            
        with gr.Column():
            parse_output = gr.Textbox(label="Parser Output", lines=10)
            graph_output = gr.Textbox(label="Interference Graph (Graphviz DOT)", lines=10)

    btn.click(fn=process_tac, inputs=[tac_input], outputs=[parse_output, graph_output])

if __name__ == "__main__":
    demo.launch()
