import json,sys,os
P,out=sys.argv[1],sys.argv[2]
def load(kind,name):
    j=json.load(open(os.path.join(P,kind,name+'.json')))
    base={}
    if j.get('inherits'): base=load(kind,j['inherits'])
    for inc in j.get('include',[]) or []:
        base.update({k:v for k,v in load(kind,inc).items() if k not in('name','type','from','instantiation','setting_id','inherits','include')})
    base.update(j); return base
for kind,name,fn in (('machine','Bambu Lab P2S 0.4 nozzle','machine.json'),('process','0.20mm Standard @BBL P2S','process.json'),('filament','Bambu PLA Basic @BBL P2S','filament_pla.json'),('filament','Bambu PETG HF @BBL P2S 0.4 nozzle','filament_petg.json')):
    try: j=load(kind,name)
    except Exception as e: print('실패',name,e); continue
    inc=j.pop('include',None); j['name']=name; j['from']='system'; j['inherits']=''
    json.dump(j,open(os.path.join(out,fn),'w'),indent=1,ensure_ascii=False)
    print(fn,len(j),'include=',inc,{k:j.get(k) for k in ('printable_area','printable_height','layer_height','wall_loops','sparse_infill_density','nozzle_temperature','filament_type','machine_start_gcode') if k in j and k!='machine_start_gcode'}, 'start_gcode' , len(j.get('machine_start_gcode','')) if 'machine_start_gcode' in j else None)
