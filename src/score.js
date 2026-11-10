/* Proyección compartida por el simulador y la portada de cada certificación.
   build.py la incrusta en las dos páginas: una sola definición de «cómo vas».

   Tres decisiones, las tres para que el número no prometa más de lo que sabe:
   - cuenta ÍTEMS DISTINTOS y solo el último intento de cada uno. Antes sumaba
     todos los intentos, así que repetir un ítem ya explicado subía la nota;
   - no proyecta por debajo de CC_MIN ítems: con una respuesta salía un score;
   - da un intervalo además del punto. La conversión a 100-1000 es lineal y
     aproximada, porque la escala real del examen no es pública. */
const CC_MIN=30, CC_CORTE=720;
function ccVal(r){return r.last===0||r.last===1?r.last:(r.seen?r.ok/r.seen:0)}
function ccScore(items,w,ST){
  const dom={}; for(const d in w) dom[d]={n:0,ok:0,w:w[d]};
  let n=0,ok=0;
  items.forEach(it=>{
    const r=ST[it.i]; if(!r||!r.seen||!dom[it.d]) return;
    const v=ccVal(r); dom[it.d].n++; dom[it.d].ok+=v; n++; ok+=v;
  });
  let num=0,den=0,vr=0;
  for(const d in dom){const o=dom[d]; if(o.n){num+=(o.ok/o.n)*o.w; den+=o.w}}
  if(!den) return {dom,n:0,ok:0,min:CC_MIN,enough:false};
  for(const d in dom){
    const o=dom[d]; if(!o.n) continue;
    const p=(o.ok+1)/(o.n+2);            // suavizado: 3 de 3 no es certeza
    vr+=Math.pow(o.w/den,2)*p*(1-p)/o.n;
  }
  const pct=num/den, e=1.96*Math.sqrt(vr);
  const sc=p=>Math.round(100+Math.max(0,Math.min(1,p))*900);
  return {dom,n,ok,min:CC_MIN,enough:n>=CC_MIN,pct,
          scaled:sc(pct),lo:sc(pct-e),hi:sc(pct+e),coverage:den/100};
}
