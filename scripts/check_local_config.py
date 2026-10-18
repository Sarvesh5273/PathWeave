"""Local credential portability check. Prints presence/source only, never values."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

from dotenv import dotenv_values


ROOT=Path(__file__).resolve().parents[1]


def main():
    values=dotenv_values(ROOT/".env")
    report={"env_exists":(ROOT/".env").exists(),"keys":{
        name:{"nonempty_in_env":bool(values.get(name)),"inherited_in_this_process":bool(os.environ.get(name))}
        for name in ("GROQ_API_KEY","TINYFISH_API_KEY")}}
    clean=os.environ.copy()
    for name in ("GROQ_API_KEY","TINYFISH_API_KEY"):clean.pop(name,None)
    process=subprocess.run([sys.executable,"-c","from app.config import settings; import json; print(json.dumps({'groq':bool(settings.groq_key),'tinyfish':bool(settings.tinyfish_key)}))"],
                           cwd=ROOT,env=clean,capture_output=True,text=True,check=True)
    report["file_only_loading"]=json.loads(process.stdout)
    report["ready"]=all(report["file_only_loading"].values())
    print(json.dumps(report,indent=2))
    if not report["ready"]:raise SystemExit(1)


if __name__=="__main__":main()
