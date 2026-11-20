import re,sys
def parse(s):
    """returns nested lists; atoms are str (quoted keep quotes). Each list gets span via parallel structure."""
    i=0;n=len(s)
    def rd():
        nonlocal i
        assert s[i]=='('; st=i; i+=1; out=[]
        while True:
            while s[i].isspace(): i+=1
            c=s[i]
            if c==')': i+=1; break
            if c=='(': out.append(rd())
            elif c=='"':
                j=i+1
                while s[j]!='"':
                    if s[j]=='\\': j+=1
                    j+=1
                out.append(s[i:j+1]); i=j+1
            else:
                j=i
                while not s[j].isspace() and s[j] not in '()': j+=1
                out.append(s[i:j]); i=j
        L=SL(out); L.span=(st,i); return L
    while s[i]!='(': i+=1
    return rd()
class SL(list): pass
def find(l,k): return [c for c in l if isinstance(c,list) and c and c[0]==k]
def one(l,k):
    r=find(l,k); return r[0] if r else None
