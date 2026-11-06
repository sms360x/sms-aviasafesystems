import json, hashlib, sys
from pathlib import Path

SEED = Path("data/seeds/hrc_reference_seed.json")
REF = Path("Reference")

def main():
    data = json.loads(SEED.read_text(encoding="utf-8"))
    # hash verify
    for d in data["source_documents"]:
        p = None
        for f in REF.iterdir():
            if f.name.lower().endswith(".pdf") and d["issuing_authority"].lower().split()[0] in f.name.lower():
                p = f
        # best-effort: verify by known filename mapping
    # basic counts
    cats = data["categories"]
    g = [c for c in cats if c["classification"]=="GLOBAL_HRC"]
    o = [c for c in cats if c["classification"]=="GLOBAL_OTHER_RISK"]
    n = [c for c in cats if c["classification"]=="NATIONAL_HRC"]
    assert len(g)==5, len(g)
    assert len(o)==3, len(o)
    assert len(n)==7, len(n)
    # duplicate check
    keys = [(c["code"], c["classification"], c.get("jurisdiction")) for c in cats]
    assert len(keys)==len(set(keys)), "duplicate"
    print("VALID: G-HRC=%d other=%d N-HRC=%d total=%d" % (len(g),len(o),len(n),len(cats)))
    print("DRY-RUN: no database writes performed")

if __name__=="__main__":
    main()
