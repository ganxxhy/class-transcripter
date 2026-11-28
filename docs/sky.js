/* Sky engine: independent live root and simulated chapter palettes
   from the sun's altitude at the viewer's local time and (approximate) location. */
(function(){
const CITIES={
 'auto':null,
 'Madrid':[40.42,-3.70],'Barcelona':[41.39,2.17],'Zaragoza':[41.65,-0.88],'Valencia':[39.47,-0.38],'Sevilla':[37.39,-5.98],'Bilbao':[43.26,-2.93],'Las Palmas':[28.12,-15.43],
 'Lisboa':[38.72,-9.14],'Londres':[51.51,-0.13],'París':[48.86,2.35],'Berlín':[52.52,13.40],'Roma':[41.90,12.50],
 'Ciudad de México':[19.43,-99.13],'Bogotá':[4.71,-74.07],'Lima':[-12.05,-77.04],'Santiago':[-33.45,-70.66],'Buenos Aires':[-34.60,-58.38],'Nueva York':[40.71,-74.01],'Los Ángeles':[34.05,-118.24],'Tokio':[35.68,139.69],'Sídney':[-33.87,151.21]};
const TZ={'Europe/Madrid':'Madrid','Atlantic/Canary':'Las Palmas','Europe/Lisbon':'Lisboa','Europe/London':'Londres','Europe/Paris':'París','Europe/Berlin':'Berlín','Europe/Rome':'Roma','America/Mexico_City':'Ciudad de México','America/Bogota':'Bogotá','America/Lima':'Lima','America/Santiago':'Santiago','America/Argentina/Buenos_Aires':'Buenos Aires','America/New_York':'Nueva York','America/Los_Angeles':'Los Ángeles','Asia/Tokyo':'Tokio','Australia/Sydney':'Sídney'};
const tz=(()=>{try{return Intl.DateTimeFormat().resolvedOptions().timeZone||''}catch(e){return''}})();
function autoPlace(){
 if(TZ[tz]) return {name:TZ[tz], ll:CITIES[TZ[tz]], how:'zona horaria '+tz};
 const off=-new Date().getTimezoneOffset(); // minutes east of UTC
 return {name:'tu zona horaria', ll:[40, off/4], how:'desfase UTC'+(off>=0?'+':'')+(off/60)};
}
function sunAlt(ms,lat,lon){
 const r=Math.PI/180,d=ms/864e5-10957.5,g=(357.529+.98560028*d)*r,q=280.459+.98564736*d;
 const L=(q+1.915*Math.sin(g)+.02*Math.sin(2*g))*r,e=(23.439-3.6e-7*d)*r;
 const dec=Math.asin(Math.sin(e)*Math.sin(L)),ra=Math.atan2(Math.cos(e)*Math.sin(L),Math.cos(L));
 const gmst=((18.697374558+24.06570982441908*d)%24+24)%24,H=(gmst*15+lon)*r-ra;
 return Math.asin(Math.sin(lat*r)*Math.sin(dec)+Math.cos(lat*r)*Math.cos(dec)*Math.cos(H))/r;
}
// [altitude, top, middle, bottom]
const K=[[-90,'#060B1A','#0B1530','#14223F'],[-14,'#08122A','#11204A','#1D2F5C'],[-7,'#0E1F4A','#25407A','#4A64A0'],[-2.5,'#1E3F7A','#4F6FA8','#E9946A'],[2,'#4F84C8','#E9AE86','#FFD0A6'],[8,'#74AEEB','#BFD7F2','#F8E5CF'],[20,'#8EC5FF','#CFE6FF','#F3F8FF'],[90,'#86C0FF','#CBE4FF','#F3F8FF']];
const hx=h=>[1,3,5].map(i=>parseInt(h.slice(i,i+2),16)),mix=(a,b,t)=>'#'+hx(a).map((v,i)=>Math.round(v+(hx(b)[i]-v)*t).toString(16).padStart(2,'0')).join('');
function colors(alt){let i=0;while(i<K.length-2&&alt>K[i+1][0])i++;const a=K[i],b=K[i+1],t=Math.max(0,Math.min(1,(alt-a[0])/(b[0]-a[0])));return[1,2,3].map(j=>mix(a[j],b[j],t))}
const load=k=>{try{return localStorage.getItem(k)}catch(e){return null}},store=(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}};
const S={city:load('sky-city')||'auto',preview:6};
function place(){return S.city!=='auto'&&CITIES[S.city]?{name:S.city,ll:CITIES[S.city],how:'elegida por ti'}:autoPlace()}
// Choose the smallest palette correction that keeps both text colors readable.
function luminance(rgb){
 return rgb.map(v=>{const s=v/255;return s<=.04045?s/12.92:((s+.055)/1.055)**2.4})
  .reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
}
function accessiblePalette(palette){
 const options=[{dark:false,ink:'#0D2340',muted:'#3F5068',target:'#FFFFFF'},
                {dark:true,ink:'#F2F5FA',muted:'#DCE6F4',target:'#000000'}];
 return options.map(option=>{
  const foreground=luminance(hx(option.muted));
  for(let step=0;step<=100;step++){
   const stops=palette.map(color=>mix(color,option.target,step/100));
   const channels=stops.map(hx);
   // Channel bounds cover every interpolated gradient color, not only its stops.
   const bound=[0,1,2].map(i=>(option.dark?Math.max:Math.min)(...channels.map(rgb=>rgb[i])));
   const background=luminance(bound);
   const ratio=(Math.max(background,foreground)+.05)/(Math.min(background,foreground)+.05);
   if(ratio>=4.6 && (option.dark?background<foreground:background>foreground))
    return {...option,stops,step};
  }
  throw new Error('No accessible sky palette');
 }).sort((a,b)=>a.step-b.step)[0];
}
function paint(el,alt){
 const {stops:[a,b,c],dark,ink,muted}=accessiblePalette(colors(alt)),root=el.style;
 root.setProperty('--bg-a',a);root.setProperty('--bg-b',b);root.setProperty('--bg-c',c);
 root.setProperty('--on-sky',ink);root.setProperty('--on-sky-mute',muted);
 root.setProperty('--stars',String(Math.max(0,Math.min(1,(-alt-4)/10))));
 el.dataset.sky=dark?'night':alt<8?'golden':'day';
}
function apply(){
 const p=place(),now=new Date(),altAt=t=>sunAlt(t.getTime(),p.ll[0],p.ll[1]);
 paint(document.documentElement,altAt(now));
 const chapter=document.getElementById('cielo');if(!chapter)return;
 const t=new Date(now);t.setHours(Math.floor(S.preview),Math.floor(S.preview%1*60),0,0);
 const alt=altAt(t);paint(chapter,alt);
 const hh=t.toLocaleTimeString('es-ES',{hour:'2-digit',minute:'2-digit'});
 const phase=alt<-12?'Noche':alt<-1?(t.getHours()<12?'Amanecer':'Anochecer'):alt<8?(t.getHours()<12?'Mañana temprana':'Atardecer'):'Día';
 chapter.querySelectorAll('[data-sky-label]').forEach(el=>el.textContent=`${phase} · ${hh} · ${p.name}`);
 chapter.querySelectorAll('[data-sky-how]').forEach(el=>el.textContent=`Vista previa a las ${hh} en ${p.name}.`);
}
window.Sky={cities:Object.keys(CITIES),get city(){return S.city},
 setCity(c){S.city=c;store('sky-city',c);apply()},
 preview(h){S.preview=h;apply()},live(){S.preview=6;apply()},apply};
apply();setInterval(apply,60000);
})();
