#!/usr/bin/env node
/* Prueba de humo del sitio construido. Arranca un servidor estatico sobre
 * site/, carga las dos paginas interactivas en los dos idiomas con jsdom y
 * ejercita el recorrido completo: elegir examen, responder, teclado, tandas de
 * tarjetas y persistencia. Falla con codigo 1 si algo no se comporta.
 *
 *   npm install jsdom && node tools/smoke.cjs        (usa el puerto 8899)
 *
 * Existe porque el build valida los datos pero no puede saber si la interfaz
 * sigue funcionando despues de tocar el i18n o el fetch de datos.
 */
const {JSDOM}=require("jsdom");
const {spawn}=require("child_process");
const PUERTO=process.env.PUERTO||8899;
const B=`http://127.0.0.1:${PUERTO}`;
let fallos=0;
const dormir=ms=>new Promise(r=>setTimeout(r,ms));
const ok=(n,cond,x="")=>{ if(!cond){fallos++;console.log(`  x ${n} ${x}`)} else console.log(`  ok ${n}`) };
async function abrir(url){
  const dom=await JSDOM.fromURL(B+url,{runScripts:"dangerously",resources:"usable",pretendToBeVisual:true,
    beforeParse(w){ w.fetch=(u,o)=>fetch(new URL(u,B+url).href,o); }});
  await dormir(2500); return dom;
}

async function simulador(){
 const casos=[
 {url:"/ccar-f/test/",    lang:"es", doms:5, examen:60, esperado:{modo:"Simulacro ponderado (20)", comprobar:"Comprobar"}},
 {url:"/en/ccar-f/test/", lang:"en", doms:5, examen:60, esperado:{modo:"Weighted mock (20)",       comprobar:"Check"}},
 {url:"/ccao-f/test/",    lang:"es", doms:7, examen:60, esperado:{modo:"Simulacro ponderado (20)", comprobar:"Comprobar"}},
];


 for(const c of casos){
  const dom=await abrir(c.url);
  const w=dom.window, d=w.document;
    const $=s=>d.querySelector(s);
  console.log(`\n${c.url}  (lang=${d.documentElement.lang})`);
  ok("html lang", d.documentElement.lang===c.lang);
  ok("sin conmutador de examen", !$("#examChips") && !/CCDV-F|CCAR-P/.test(d.body.innerHTML.replace(/<script[\s\S]*?<\/script>/g,"")));
  ok("botón de modo traducido", $("#mFull").textContent===c.esperado.modo, `-> "${$("#mFull").textContent}"`);
  ok(`${c.doms} barras de dominio`, $("#bars").children.length===c.doms, `hay ${$("#bars").children.length}`);
  // lanzar un simulacro y responder mal a propósito, luego bien
  $("#mFull").dispatchEvent(new w.MouseEvent("click"));
  await dormir(300);
  const opts=[...d.querySelectorAll("#opts .opt")];
  ok("pinta 4 opciones", opts.length===4, `hay ${opts.length}`);
  ok("botón comprobar", $("#act")&&$("#act").textContent===c.esperado.comprobar, `-> "${$("#act")&&$("#act").textContent}"`);
  ok("enunciado no vacío", $(".stem").textContent.trim().length>40);
  ok("sin placeholder sin resolver", !d.body.innerHTML.includes("{{"));
  opts[0].dispatchEvent(new w.MouseEvent("click"));
  ok("aria-pressed al seleccionar", opts[0].getAttribute("aria-pressed")==="true");
  $("#act").dispatchEvent(new w.MouseEvent("click"));
  await dormir(200);
  const rat=$("#rat").textContent;
  ok("muestra veredicto", /Correcto|Incorrecto|Correct|Incorrect/.test(rat), `-> "${rat.slice(0,40)}"`);
  ok("enlaza la fuente", /^https?:/.test($("#rat a").getAttribute("href")));
  ok("marca correcta/incorrecta", [...d.querySelectorAll("#opts .opt")].some(b=>b.dataset.state==="correct"));
  ok("con una respuesta no proyecta score", $("#score").textContent==="—"&&/1 (de|of) 30/.test($("#verdict").textContent), `-> ${$("#score").textContent} · ${$("#verdict").textContent.slice(0,50)}`);
  ok("correcta marcada con texto", !!d.querySelector('#opts .opt[data-state="correct"] .mark'));
  // teclado
  $("#act").dispatchEvent(new w.MouseEvent("click"));
  await dormir(200);
  d.dispatchEvent(new w.KeyboardEvent("keydown",{key:"2",bubbles:true}));
  ok("tecla 2 selecciona", [...d.querySelectorAll("#opts .opt")][1].getAttribute("aria-pressed")==="true");
  d.dispatchEvent(new w.KeyboardEvent("keydown",{key:"Enter",bubbles:true}));
  await dormir(200);
  ok("Enter comprueba", $("#rat").textContent.length>20);
  // Enter sobre un enlace enfocado es del enlace, no del simulador
  const antes=$(".count").textContent, enlace=d.querySelector(".note a");
  enlace.dispatchEvent(new w.KeyboardEvent("keydown",{key:"Enter",bubbles:true}));
  ok("Enter en un enlace no avanza", $(".count").textContent===antes);

  // cola de fallos: un fallo es repasable al momento y no se gradúa con un acierto
  const click=el=>el.dispatchEvent(new w.MouseEvent("click"));
  const responde=async bien=>{
    const st=w.eval("S.qs[S.i]"), k=bien?st.ans[0]:[0,1,2,3].find(x=>!st.ans.includes(x));
    click(d.querySelector(`#opts .opt[data-k="${k}"]`)); click($("#act")); await dormir(60);
  };
  w.eval("ST={__migrado:1};save();render()");
  click($("#mFull")); await dormir(100);
  await responde(false);
  click($("#mFail")); await dormir(100);
  ok("fallo repasable al momento", !!$("#opts")&&/1\/1/.test($(".count").textContent), `-> "${$("#stage").textContent.trim().slice(0,50)}"`);
  await responde(true); click($("#act")); await dormir(100);
  ok("informe de bloque", !!$(".rep-num")&&$(".rep-num").textContent==="1/1");
  click($("#mFail")); await dormir(100);
  ok("un acierto no gradúa: queda en espera", !$("#opts")&&/1/.test($("#stage").textContent), `-> "${$("#stage").textContent.trim().slice(0,60)}"`);

  // examen completo: corrige al final, deja volver y marcar
  w.confirm=()=>true;
  click($("#mExam")); await dormir(150);
  const total=w.eval("S.qs.length");
  ok("examen con el tamaño real", total===Math.min(c.examen,w.eval("ITEMS.length")), `hay ${total}`);
  ok("reloj y navegador", !!$("#tm")&&d.querySelectorAll(".navq button").length===total);
  click(d.querySelector('#opts .opt[data-k="0"]'));
  ok("sin corrección inmediata", $("#rat").textContent===""&&!d.querySelector("#opts .opt[data-state]"));
  click($("#flag")); ok("marca la pregunta", d.querySelector('.navq [data-go="0"]').dataset.flag==="1");
  click($("#act")); await dormir(50);
  click($("#prev")); await dormir(50);
  ok("vuelve y conserva la respuesta", d.querySelector('#opts .opt[data-k="0"]').getAttribute("aria-pressed")==="true");
  w.eval("S.qs.forEach(q=>{q.picked=[q.ans[0]]})");
  click(d.querySelector(`.navq [data-go="${total-1}"]`)); await dormir(50);
  click($("#act")); await dormir(150);
  ok("informe del examen", !!$(".rep-num")&&/^\d+\/\d+$/.test($(".rep-num").textContent), `-> ${$(".rep-num")&&$(".rep-num").textContent}`);
  ok("historial guardado", w.eval("ST.__log.length")>=2);
  ok("proyecta con intervalo", /^\d{3,4}$/.test($("#score").textContent)&&/\d+–\d+/.test($("#range").textContent), `-> ${$("#score").textContent} · ${$("#range").textContent}`);
  // tiempo agotado: cierra el bloque
  click($("#mFull")); await dormir(100);
  w.eval("S.end=Date.now()-1"); await dormir(700);
  ok("el tiempo agotado cierra el bloque", !$("#opts")&&!!$(".rep"));
  dom.window.close();

  // la portada de la certificación usa la misma proyección
  const h=await abrir(c.url.replace(/test\/$/,""));
  ok("portada sin datos: sin score", h.window.document.querySelector("#score").textContent==="—");
  h.window.close();
 }

}

async function tarjetas(){
 const casos=[
 {url:"/ccar-f/tarjetas/", lang:"es", ver:"Ver respuesta", tema:"Bucle y tools", temas:16},
 {url:"/en/ccar-f/cards/", lang:"en", ver:"Show answer",   tema:"Loop and tools", temas:16},
 {url:"/ccao-f/tarjetas/", lang:"es", ver:"Ver respuesta", tema:"Patrones",      temas:12},
];


 for(const c of casos){
  const dom=await abrir(c.url);
  const w=dom.window,d=w.document,$=s=>d.querySelector(s);
  const click=el=>el.dispatchEvent(new w.MouseEvent("click"));
  console.log(`\n${c.url}  (lang=${d.documentElement.lang})`);
  ok("html lang", d.documentElement.lang===c.lang);
  ok("mazo cargado", !/Cargando|Loading|cargar|load/.test($("#home").textContent.slice(0,60)), `-> "${$("#home").textContent.trim().slice(0,50)}"`);
  const temas=[...d.querySelectorAll(".tema")].filter(t=>!t.closest(".cc-fuera"));
  const temasFuera=[...d.querySelectorAll(".cc-fuera .tema")];
  ok(`${c.temas} temas en alcance`, temas.length===c.temas, `hay ${temas.length}`);
  ok("primer tema traducido", temas[0].querySelector(".t1").textContent===c.tema, `-> "${temas[0].querySelector(".t1").textContent}"`);
  ok("sin placeholder", !d.body.innerHTML.includes("{{"));
  ok("ningún tema vacío", temas.every(t=>t.querySelector(".t1").textContent.trim()));
  // una tanda
  click($("#go"));
  await dormir(300);
  ok("sesión abierta", $("#sesion").classList.contains("on"));
  ok("progreso de 10", $("#pbar").children.length===10, `hay ${$("#pbar").children.length}`);
  ok("temas fuera, plegados", temasFuera.length===28-c.temas, `hay ${temasFuera.length}, esperaba ${28-c.temas}`);
  ok("pregunta pintada", $(".q").textContent.trim().length>10);
  ok("botón ver respuesta", $("#bShow").textContent===c.ver, `-> "${$("#bShow").textContent}"`);
  ok("nivel traducido", $("#lvlLbl").textContent.length>0, `-> "${$("#lvlLbl").textContent}"`);
  ok("contador 1 de 10", /1\s*(de|of)\s*10/.test($("#temaLbl").textContent), `-> "${$("#temaLbl").textContent}"`);
  click($("#bShow"));
  await dormir(150);
  ok("respuesta revelada", $(".a")&&$(".a").textContent.trim().length>5);
  ok("botones de calificación", $("#bYes")&&$("#bNo"));
  // completar la tanda
  for(let i=0;i<10;i++){
    if($("#bShow")) click($("#bShow"));
    await dormir(60);
    if($("#bYes")) click($("#bYes"));
    await dormir(220);
  }
  ok("resumen final", $("#finBox")&&/\d+\/10/.test($("#finBox").textContent), `-> "${($("#finBox")||{textContent:"(sin resumen)"}).textContent.trim().slice(0,40)}"`);
  ok("racha registrada", /1|streak|racha/.test($("#finBox").textContent));
  ok("progreso persistido", Object.keys(JSON.parse(w.localStorage.getItem("claude-certs-cards-v2")||"{}")).length>5);
  dom.window.close();
 }

}

(async()=>{
  const srv=spawn("python3",["-m","http.server",String(PUERTO)],{cwd:"site",stdio:"ignore"});
  await dormir(1500);
  try{
    console.log("SIMULADOR"); await simulador();
    console.log("\nTARJETAS"); await tarjetas();
  } finally { srv.kill(); }
  console.log(fallos?`\n${fallos} FALLOS`:"\nTodo correcto en es y en.");
  process.exit(fallos?1:0);
})();
