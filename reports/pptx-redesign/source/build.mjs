import fs from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';
import { Presentation, PresentationFile } from '@oai/artifact-tool';

process.on('uncaughtException', error => { console.error(error.stack?.split('\n').slice(0,3).join('\n') || error.message); process.exit(1); });
const ROOT = path.resolve(process.argv[2] || '.');
const BUILD = path.join(ROOT, 'build/pptx_redesign');
const SKILL = 'C:/Users/dmytr/.codex/plugins/cache/openai-primary-runtime/presentations/26.1105.12137/skills/presentations';
const { applyPresentationChartFont } = await import(pathToFileURL(path.join(SKILL,'container_tools/artifact_tool_utils.mjs')).href);
const D = JSON.parse(await fs.readFile(path.join(BUILD,'data.json'),'utf8'));
const P = Presentation.create({slideSize:{width:1280,height:720}});
const C = {bg:'#F5F4EF',ink:'#172D28',green:'#14735B',muted:'#66736E',rule:'#D4DCD5',light:'#E1EAE4',white:'#FFFFFF',gray:'#89958F'};
const FONT = 'Arial';
let current = 0;
const f = (v,n=2)=>Number(v).toFixed(n).replace('.',',');
const chartNumber = n => Number(Number(n).toPrecision(12));
const subject = s=>s==='mat'?'Математика':'Португальська';
const pos=(left,top,width,height)=>({left,top,width,height});
function text(s,value,x,y,w,h,size=28,color=C.ink,bold=false,extra={}) {
 const sh=s.shapes.add({geometry:'textbox',name:`text-${current}-${s.shapes.items.length}`,position:pos(x,y,w,h),fill:'none',line:{fill:'none',width:0}});
 sh.text=value;sh.text.style={fontFamily:FONT,fontSize:size,color,bold,verticalAlignment:'top',alignment:'left',autoFit:'none',wrap:'square',insets:0,lineSpacing:1.12,...extra};return sh;
}
function line(s,x1,y1,x2,y2,color=C.rule,width=1) {
 return s.shapes.add({geometry:'line',name:`rule-${current}-${s.shapes.items.length}`,position:pos(x1,y1,x2-x1,y2-y1),fill:'none',line:{fill:color,width,style:'solid'}});
}
function arrow(s,x,y,w,color=C.gray) {
 return s.shapes.add({geometry:'rightArrow',name:'editable-process-arrow',position:pos(x,y,w,18),fill:color,line:{fill:'none',width:0}});
}
function slide(title,{dark=false,source='',size=44}={}) {
 current++;const s=P.slides.add();if(current>11)s.hidden=true;s.background.fill=dark?C.green:C.bg;
 if(title)text(s,title,76,64,1128,116,size,dark?C.white:C.ink,true);
 if(source)text(s,source,76,652,1085,52,20,dark?'#D8EBE2':C.muted);
 text(s,String(current).padStart(2,'0'),1195,665,40,28,18,dark?'#D8EBE2':C.muted,false,{alignment:'right'});
 return s;
}
function forest(s,rows,box,{min=0,max=6,ymax=rows.length+1,unit=1}={}) {
 const series=[];
 rows.forEach((r,i)=>{
  const yy=r.y??rows.length-i;
  if(r.estimate==null)return;
  const color=r.color||C.green;
  series.push({name:`95% CI ${r.label||i}`,xValues:[chartNumber(r.ci_low),chartNumber(r.ci_high)],values:[yy,yy],line:{fill:color,width:3.5},marker:{symbol:'none',size:2},fill:color});
  series.push({name:r.label||`Оцінка ${i}`,xValues:[chartNumber(r.estimate)],values:[yy],line:{fill:'none',width:0},marker:{symbol:'circle',size:11,fill:color},fill:color});
 });
 series.push({name:'Нуль',xValues:[0,0],values:[0,ymax],line:{fill:C.gray,width:1.4,style:'dashed'},marker:{symbol:'none',size:2},fill:C.gray});
 const chart=s.charts.add('scatter',{position:box,series,hasLegend:false,scatterOptions:{style:'lineWithMarkers'},
  chartFill:'none',chartLine:{fill:'none',width:0},plotAreaFill:'none',plotAreaLine:{fill:'none',width:0},
  xAxis:{visible:true,min,max,majorUnit:unit,position:'bottom',tickLabelPosition:'low',numberFormatCode:unit<1?'0.0':'0',textStyle:{fontSize:22,fontFamily:FONT,fill:C.muted},line:{fill:C.rule,width:1},majorGridlines:{fill:C.rule,width:0.7}},
  yAxis:{visible:false,min:0,max:ymax,majorUnit:1,tickLabelPosition:'none',line:{fill:'none',width:0},majorGridlines:null},
  dataLabels:{showValue:false}});
 applyPresentationChartFont(chart,{fontFamily:FONT});
 chart.xAxis={textStyle:{fontSize:22,fontFamily:FONT,fill:C.muted}};
 return chart;
}
// 01 — cover
{
 const s=slide('',{source:'Реплікація результатів T. Da (2025) · UCI Student Performance'});
 s.images.add({blob:new Uint8Array(await fs.readFile(path.join(BUILD,'assets/study.jpg'))),contentType:'image/jpeg',alt:'Ілюстративне фото відкритої книги на столі біля вікна; Jessica Fadel / Unsplash',position:pos(860,0,420,720),fit:'cover'});
 text(s,'Освіта батьків\nі оцінки учнів',76,140,770,190,66,C.ink,true);
 text(s,'Що вдалося відтворити\nі наскільки переконливі докази',80,365,700,100,32,C.muted);
 text(s,'Дмитро Степанюк · МУП-1',80,562,740,42,25,C.ink);
 text(s,'Фото: Jessica Fadel / Unsplash',80,615,700,28,18,C.muted).hyperlink={uri:'https://unsplash.com/photos/ANexOmTOzmY',isExternal:true};
}
// 02 — possible explanations, conceptual editable diagram
{
 const s=slide('Чому цей зв’язок варто перевіряти?',{source:'Можливі пояснення за Davis-Kean (2005), Dubow та ін. (2009), Waters та ін. (2025)'});
 text(s,'Освіта\nбатьків',80,280,235,120,43,C.green,true);
 text(s,'Сімейні ресурси\nОчікування\nСередовище навчання',430,235,390,190,31,C.ink);
 text(s,'Оцінки\nучня',980,280,230,120,43,C.green,true);
 arrow(s,310,325,75);arrow(s,850,325,75);
 text(s,'Можливі пояснення',430,192,390,34,21,C.muted);
 text(s,'Сам зв’язок ще не показує, що саме його пояснює.',80,515,1110,85,34,C.ink,true);
 text(s,'Схема окреслює гіпотези; наш аналіз не встановлює ці причинні шляхи.',80,605,1100,38,23,C.muted);
}
// 03 — target and research sequence
{
 const s=slide('Мішень — результат конкретної статті',{source:'T. Da (2025), Scientific Reports 15, 11521 · таблиця 8 · DOI: 10.1038/s41598-025-89394-2'});
 text(s,'Чи відтвориться материнський зв’язок,\nякщо одночасно врахувати освіту батька?',80,190,1090,100,35,C.green,true);
 const xs=[80,480,880];
 const heads=['Оригінал','Реплікація','Стійкість'];
 const bodies=['Фінальні моделі OLS\nT. Da (2025)','Ті самі дані,\nвибірки й контролі','Наперед визначені\nзміни умов аналізу'];
 xs.forEach((x,i)=>{text(s,heads[i],x,380,325,55,35,C.ink,true);text(s,bodies[i],x,445,330,110,27,C.muted);});
 arrow(s,405,402,42);arrow(s,805,402,42);
 text(s,'Перевіряємо підсумкові регресії, а не весь авторський ML-пайплайн.',80,592,1090,40,24,C.muted);
}
// 04 — sample portrait
{
 const s=slide('Дані учнів двох шкіл Португалії',{source:'UCI Student Performance · G3: 0–20 балів; нульові оцінки збережено'});
 text(s,'Математика',80,200,480,50,32,C.muted);
 text(s,'Португальська',690,200,500,50,32,C.muted);
 const a=D.sample_flow.find(r=>r.subject==='mat'),b=D.sample_flow.find(r=>r.subject==='por');
 text(s,String(a.n_after),76,265,500,145,118,C.green,true);
 text(s,String(b.n_after),686,265,500,145,118,C.green,true);
 text(s,`із ${a.n_before} записів після фільтра освіти`,80,425,500,80,28,C.ink);
 text(s,`із ${b.n_before} записів після фільтра освіти`,690,425,500,80,28,C.ink);
 line(s,630,220,630,495);
 text(s,'Один запис — учень × предмет.',80,555,1100,42,31,C.ink,true);
 text(s,'Учні між файлами можуть перетинатися: ці N не додаємо як різних людей.',80,605,1120,38,23,C.muted);
}
// 05 — model as a comparison
{
 const s=slide('Яке порівняння робить модель?',{source:'M4 / M10 · категоріальні Medu і Fedu, база = початкова освіта · OLS, HC3, 95% CI'});
 text(s,'Вища освіта\nматері',80,205,490,125,46,C.green,true);
 text(s,'Початкова освіта\nматері',745,205,470,125,46,C.ink,true);
 text(s,'порівнюємо',548,250,180,45,25,C.muted,false,{alignment:'center'});
 line(s,80,365,1200,365);
 text(s,'За однакових включених характеристик',80,398,1100,48,32,C.ink,true);
 text(s,'Освіта батька · вік · стать · школа · опікун',80,470,1100,50,29,C.muted);
 text(s,'Коефіцієнт показує різницю балів G3 у заданій моделі.',80,576,1120,55,29,C.ink);
}
// 06 — H1
{
 const s=slide('Материнський зв’язок додатний\nв обох предметах',{source:'UCI · M4: N=390; M10: N=637 · вища vs початкова освіта матері · HC3; звичайні 95% CI'});
 D.H1.forEach((r,i)=>{text(s,subject(r.subject),80,205+i*170,335,42,27,C.muted);text(s,'+'+f(r.estimate),76,239+i*170,340,100,70,C.green,true);});
 forest(s,D.H1.map((r,i)=>({...r,label:subject(r.subject),y:i===0?2.3:0.7})),pos(420,205,785,360),{min:0,max:5,ymax:3});
 text(s,'Бали G3 · точка — оцінка, відрізок — 95% CI',435,570,775,40,24,C.muted);
 text(s,'Обидва результати значущі після поправки Holm.',80,613,1120,40,25,C.ink,true);
}
// 07 — H2
{
 const s=slide('Чи сильніший зв’язок з освітою матері?',{source:'M4 / M10 · N=390 / 637 · прямий контраст Medu₄ − Fedu₄; HC3, 95% CI · окрема сім’я Holm'});
 text(s,'Доказів\nпереваги\nнедостатньо',80,225,430,180,43,C.green,true);
 forest(s,D.H2.map(r=>({...r,label:subject(r.subject)})),pos(480,215,725,315),{min:-1,max:7,ymax:3,unit:2});
 text(s,'Математика',520,250,650,32,23,C.muted);
 text(s,'Португальська',520,343,650,32,23,C.muted);
 text(s,'Обидва інтервали охоплюють нульову різницю.',80,552,1120,48,31,C.ink,true);
 text(s,'Це не доводить рівності зв’язків або відсутності батьківського зв’язку.',80,610,1120,36,23,C.muted);
}
// 08 — all comparable sensitivity variants
{
 const s=slide('Знак зберігається, точність змінюється',{source:'Medu₄ · R1/R2/R4/R5 · HC3, звичайні 95% CI; інтервали не одночасні · robustness_summary.csv'});
 text(s,'Математика',80,178,510,45,30,C.ink,true);text(s,'Португальська',690,178,510,45,30,C.ink,true);
 for(const [sub,x] of [['mat',80],['por',690]]){
  const rows=D.robustness_medu.filter(r=>r.subject===sub&&['R1','R2','R4','R5'].includes(r.variant));
  const order=['R1','R2','MS','GP','R5'];rows.sort((a,b)=>order.indexOf(a.variant==='R4'?a.school:a.variant)-order.indexOf(b.variant==='R4'?b.school:b.variant));
  rows.forEach((r,i)=>{const short=r.variant==='R4'?r.school:r.variant;text(s,`${short} · N=${r.nobs}`,x,265+i*51,150,36,22,C.muted);if(r.estimate==null)text(s,'Не оцінено',x+163,265+i*51,270,36,22,C.muted);});
  forest(s,rows.map(r=>({...r,label:r.variant})),pos(x+155,228,365,350),{min:-3,max:6,ymax:6,unit:3});
 }
 text(s,'9 із 9 оцінюваних материнських контрастів додатні.',80,583,1120,40,29,C.green,true);
 text(s,'R1: освіта 0 · R2: без G3=0 · MS/GP: школи окремо · R5: +час навчання',80,626,1120,30,21,C.muted);
}
// 09 — study time, descriptive
{
 const s=slide('Після врахування часу навчання\nоцінка дещо менша',{source:'R5: категоріальний studytime · N=390 / 637 · HC3; CI окремих оцінок, не їх різниці · robustness_h3.csv'});
 D.H3.forEach((r,i)=>{text(s,subject(r.subject),80,235+i*160,440,37,27,C.muted);text(s,`${f(r.beta_base)} → ${f(r.beta_augmented)}`,76,280+i*160,520,75,55,C.green,true);});
 const rows=D.H3.flatMap(r=>[{estimate:r.beta_base,ci_low:r.base_ci_low,ci_high:r.base_ci_high,color:C.gray,label:'База'}, {estimate:r.beta_augmented,ci_low:r.augmented_ci_low,ci_high:r.augmented_ci_high,label:'+час'}]);
 forest(s,rows,pos(645,212,560,355),{min:0,max:5,ymax:5});
 ['База','+час','База','+час'].forEach((t,i)=>text(s,t,558,263+i*64,85,32,21,C.muted));
 text(s,'Зменшення коефіцієнта ще не встановлює механізм цього зв’язку.',80,600,1120,50,29,C.ink,true);
}
// 10 — replication and limits
{
 const s=slide('Реплікація часткова: дві числові розбіжності',{source:'Власна реплікація таблиці 8 T. Da (2025) · числовий збіг не включає SE'});
 const g=D.replication.global;
 text(s,`${g.matched_cells}/${g.total_cells}`,76,228,520,135,106,C.green,true);
 text(s,'числових перевірок збігаються',80,380,510,80,30,C.ink);
 text(s,'Дві розбіжності стосуються опікуна\nв моделі португальської.',80,490,510,105,27,C.muted);
 text(s,'Що залишається невідомим',700,226,500,85,33,C.ink,true);
 text(s,'Конкретний метод авторських\nстандартних похибок.',700,333,500,95,29,C.muted);
 text(s,'Невиміряні сімейні чинники\nта межі даних двох шкіл.',700,465,500,95,29,C.muted);
}
// 11 — clear ending
{
 const s=slide('Що можемо сказати впевнено?',{dark:true,source:'Висновок для цих даних і заданих моделей · final_hypotheses.csv / final_claims.csv'});
 text(s,'Вища освіта матері пов’язана\nз вищими оцінками в цих даних.',80,225,1120,150,49,C.white,true);
 text(s,'Перевагу над батьківським зв’язком не встановлено.',80,432,1110,70,30,'#D8EBE2');
 text(s,'Причинного висновку цей дизайн не дозволяє.',80,533,1110,70,30,'#D8EBE2');
}
// 12 — backup: fixed noise and diagnostic interpretation
{
 const s=slide('Плацебо й діагностика',{source:'Резерв · базові M4/M10 + один fixed noise на предмет · N=390/637 · HC3, 95% CI; raw p'});
 text(s,'Фіксований випадковий шум',80,190,750,48,31,C.ink,true);
 forest(s,D.placebo.map(r=>({...r,label:subject(r.subject),color:C.gray})),pos(260,235,535,300),{min:-1,max:1,ymax:3,unit:0.5});
 D.placebo.forEach((r,i)=>{text(s,subject(r.subject),80,300+i*110,180,55,23,C.muted);});
 text(s,`raw p: mat ${f(D.placebo[0].p_value,3)} · por ${f(D.placebo[1].p_value,3)}`,80,556,730,42,26,C.ink);
 text(s,'Що це означає',870,195,340,45,30,C.green,true);
 text(s,'У цих двох запусках шум\nне має виразного зв’язку\nз оцінками.',870,265,340,125,27,C.ink);
 text(s,'Це не доводить відсутності\nневиміряних чинників.\nПороги діагностики —\nпідстава для огляду.',870,420,340,165,24,C.muted);
}
// 13 — backup: native evidence table
{
 const s=slide('Незбіги M10 і невідомі авторські SE',{source:'Резерв · M10: португальська, N=637 · replication_comparison.csv / replication_se_comparison.csv'});
 const mis=D.replication.mismatches;
 const values=[['Коефіцієнт опікуна','У статті','Наша оцінка'],...mis.map(r=>[r.term==='guardian_mother'?'Мати проти «іншого»':'Батько проти «іншого»',f(r.original_value,3),f(r.replicated_value,3)])];
 const table=s.tables.add({rows:values.length,columns:3,left:80,top:210,width:1120,height:230,columnWidths:[480,320,320],values});
 table.borders.assign({fill:C.rule,width:1});
 for(let r=0;r<values.length;r++)for(let c=0;c<3;c++){const cell=table.getCell(r,c);cell.fill=r===0?C.light:C.bg;cell.text.style={fontFamily:FONT,fontSize:27,color:c===2?C.green:C.ink,bold:r===0};}
 text(s,'Можлива перестановка підписів не підтверджена.',80,485,1120,48,30,C.ink,true);
 const se=D.replication.se_counts;const get=k=>se.find(r=>r.covariance_type===k);
 text(s,`Числові збіги SE: HC1 ${get('HC1').matched_cells}/68 · HC3 ${get('HC3').matched_cells}/68 · звичайні ${get('nonrobust').matched_cells}/68`,80,558,1120,40,26,C.muted);
 text(s,'Навіть близький збіг SE не встановлює метод автора.',80,610,1120,37,25,C.green,true);
}
// 14 — backup: references and honest open requirement
{
 const s=slide('Література та межі пошуку',{source:'Резерв · перевірені джерела: references.bib, literature.csv, literature_followup.md'});
 const refs=[
 ['T. Da (2025)','Scientific Reports 15, 11521\nDOI: 10.1038/s41598-025-89394-2'],
 ['P. E. Davis-Kean (2005)','Journal of Family Psychology 19(2), 294–304\nDOI: 10.1037/0893-3200.19.2.294'],
 ['E. F. Dubow та ін. (2009)','Merrill-Palmer Quarterly 55(3), 224–249\nDOI: 10.1353/mpq.0.0030'],
 ['N. E. Waters та ін. (2025)','Journal of Experimental Child Psychology 260, 106335\nDOI: 10.1016/j.jecp.2025.106335']];
 refs.forEach(([author,title],i)=>{text(s,author,80,183+i*78,385,35,25,C.green,true);text(s,title,450,183+i*78,750,66,22,C.ink);});
 text(s,'Вимога 3–5 citing/checking робіт залишається відкритою.',80,531,1120,52,29,C.ink,true);
 text(s,'1 цитування підтверджене текстом; ще 1 — лише метаданими.\nЗмістовних перевірок таблиці 8 не підтверджено.',80,593,1120,61,23,C.muted);
}
await fs.mkdir(path.join(BUILD,'renders'),{recursive:true});
for(let i=0;i<P.slides.items.length;i++){
 const blob=await P.export({slide:P.slides.items[i],format:'png',scale:1});
 await fs.writeFile(path.join(BUILD,'renders',`slide-${String(i+1).padStart(2,'0')}.png`),new Uint8Array(await blob.arrayBuffer()));
 const layout=await P.slides.items[i].export({format:'layout'});
 await fs.writeFile(path.join(BUILD,'renders',`slide-${String(i+1).padStart(2,'0')}.layout.json`),new Uint8Array(await layout.arrayBuffer()));
}
await (await PresentationFile.exportPptx(P)).save(path.join(BUILD,'candidate.pptx'));
await fs.writeFile(path.join(BUILD,'presentation.json'),JSON.stringify(P.toProto()));
console.log('Created 14 slides and native editable evidence');
