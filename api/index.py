from fastapi import FastAPI
from pydantic import BaseModel
from src.frontend.parser import parse, ParseError
from src.analysis.interference import build_graph
import traceback

app = FastAPI()

class CodeRequest(BaseModel):
    code: str

@app.post("/api/analyze")
def analyze(req: CodeRequest):
    try:
        # Step 1: Parse
        fn = parse(req.code)
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
        except Exception as e:
            dot_code = f"Error building graph: {str(e)}\n\n{traceback.format_exc()}"
            
        return {"summary": summary, "dot": dot_code, "error": None}

    except ParseError as e:
        return {"summary": "", "dot": "", "error": f"Parse Error: {str(e)}"}
    except Exception as e:
        return {"summary": "", "dot": "", "error": f"Unexpected Error: {str(e)}\n\n{traceback.format_exc()}"}
