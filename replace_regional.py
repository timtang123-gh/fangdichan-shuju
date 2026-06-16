#!/usr/bin/env python3
"""Replace regional JS section in index.html with city-based module."""
import json

with open("index.html", encoding="utf-8") as f:
    lines = f.readlines()

# Find the REGIONAL section start and INIT section start
regional_start = None
init_start = None
for i, line in enumerate(lines):
    if '// ===== REGIONAL - 70 City Level =====' in line:
        regional_start = i
    if '// ===== REGIONAL DATA EMBEDDED (no fetch needed) =====' in line:
        init_start = i
        break

print(f"REGIONAL start: line {regional_start+1}")
print(f"INIT start: line {init_start+1}")

# Build new regional JS
new_regional = '''// ===== CITY DATA PROCESSING =====
// CITY_DATA = {m:[months...], c:{city:{nm:{o:offset,v:[...]}, ny:..., sm:..., sy:...}}}
let _selected=[], _cityTab='new', _cc=null;

// Populate city chips on init
(function initCities(){
    if(typeof CITY_DATA==='undefined')return;
    _selected=['北京','上海','深圳','广州'].filter(c=>CITY_DATA.c[c]);
    renderCityChips();
    renderCityDdAll();
    document.getElementById('rtbs').querySelectorAll('.tbtn').forEach(b=>{
        b.onclick=function(){
            document.getElementById('rtbs').querySelectorAll('.tbtn').forEach(x=>x.classList.remove('active'));
            this.classList.add('active');
            _cityTab=this.dataset.rt;
            applyCity();
        };
    });
})();

function renderCityChips(){
    let html=_selected.map(c=>`<span class="ccity active" onclick="removeCity('${c}')">${c}<span class="cx">×</span></span>`).join(' ');
    document.getElementById('cityChips').innerHTML=html;
}

function renderCityDdAll(){
    let av=Object.keys(CITY_DATA.c).filter(c=>!_selected.includes(c));
    document.getElementById('cdd').innerHTML=av.map(c=>`<div class="dd-item" onmousedown="addCity('${c}')">${c}</div>`).join('');
}

function showCityDd(){document.getElementById('cdd').classList.add('show');}
function hideCityDd(){document.getElementById('cdd').classList.remove('show');}

function filterCityDd(){
    let q=document.getElementById('csch').value.trim().toLowerCase();
    let av=Object.keys(CITY_DATA.c).filter(c=>!_selected.includes(c));
    if(q)av=av.filter(c=>c.toLowerCase().includes(q)||c.includes(q));
    document.getElementById('cdd').innerHTML=av.map(c=>`<div class="dd-item" onmousedown="addCity('${c}')">${c}</div>`).join('');
    document.getElementById('cdd').classList.add('show');
}

function addCity(c){
    if(!_selected.includes(c)&&_selected.length<10){
        _selected.push(c);
        renderCityChips();
        renderCityDdAll();
        document.getElementById('csch').value='';
        applyCity();
    }
}

function removeCity(c){
    if(_selected.length<=1)return;
    _selected=_selected.filter(x=>x!==c);
    renderCityChips();
    renderCityDdAll();
    applyCity();
}

function applyCity(){
    if(_selected.length===0)return;
    let months=CITY_DATA.m;
    let type=_cityTab==='new'?'nm':'sm';
    let indices={};
    
    for(let city of _selected){
        let cd=CITY_DATA.c[city];
        if(!cd)continue;
        let raw=cd[type];
        if(!raw||!raw.v||raw.v.length===0)continue;
        let vals=new Array(months.length).fill(null);
        for(let i=0;i<raw.v.length;i++){
            if(raw.v[i]!==null)vals[raw.o+i]=raw.v[i];
        }
        indices[city]=calcCityIdx(vals);
    }
    
    // Stats cards
    let bv=vals=>{let v=vals.filter(x=>x!==null);return v.length?v[v.length-1]:null;};
    let colors=['#e74c3c','#2c3e50','#3498db','#f39c12','#2ecc71','#9b59b6','#1abc9c','#e67e22','#e91e63','#00bcd4'];
    document.getElementById('rs').innerHTML=_selected.map((c,i)=>{
        let v=bv(indices[c]);
        return `<div class="sc" style="border-color:${colors[i%colors.length]}"><div class="lbl">${c}</div><div class="val">${typeof v==='number'?v.toFixed(1):'-'}</div></div>`;
    }).join('');
    
    renderCityChart(months,indices,colors);
    renderCityTbl(months,indices);
}

function calcCityIdx(vals){
    let mult=Array(vals.length).fill(null);
    let bi=0;
    for(let i=bi;i<vals.length;i++){if(vals[i]!==null){mult[i]=100;break;}}
    for(let i=bi+1;i<vals.length;i++){
        if(mult[i]!==null)continue;
        if(vals[i]!==null&&mult[i-1]!==null)mult[i]=mult[i-1]*(1+vals[i]/100);
        else if(mult[i-1]!==null)mult[i]=mult[i-1];
    }
    for(let i=bi-1;i>=0;i--){
        if(mult[i]!==null)continue;
        if(vals[i+1]!==null&&mult[i+1]!==null)mult[i]=mult[i+1]/(1+vals[i+1]/100);
        else if(mult[i+1]!==null)mult[i]=mult[i+1];
    }
    return mult;
}

function renderCityChart(months,indices,colors){
    if(_cc){_cc.dispose();_cc=null;}
    let el=document.getElementById('rc');
    if(!el||el.offsetParent===null)return;
    _cc=echarts.init(el);
    let intv=Math.max(1,Math.floor(months.length/25));
    let seriesData=[];
    for(let i=0;i<_selected.length;i++){
        let c=_selected[i];
        if(indices[c])seriesData.push({name:c,type:'line',data:indices[c],lineStyle:{color:colors[i%colors.length],width:2},symbol:'none'});
    }
    let title=_cityTab==='new'?'新建商品住宅定基指数(2011.01=100)':'二手住宅定基指数(2011.01=100)';
    document.getElementById('rct').textContent=title;
    _cc.setOption({
        tooltip:{trigger:'axis'},
        legend:{data:_selected.filter(c=>indices[c]),bottom:0,type:'scroll'},
        grid:{left:65,right:30,top:15,bottom:50},
        xAxis:{type:'category',data:months,axisLabel:{rotate:45,fontSize:9,interval:intv}},
        yAxis:{type:'value',name:'指数',min:v=>Math.floor(Math.min(v.min,95)/5)*5},
        series:seriesData
    });
}

function renderCityTbl(months,indices){
    let h=['月份',..._selected];
    let rows=months.map((m,i)=>{
        let r=[m];
        for(let c of _selected){
            let v=indices[c]?.[i];
            r.push(v!==null&&v!==undefined?v.toFixed(1):'-');
        }
        return r;
    });
    document.getElementById('rtt').innerHTML=`<table><thead><tr>${h.map(x=>`<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')}</tbody></table>`;
    document.getElementById('rti').textContent=`${_cityTab==='new'?'新建':'二手'}住宅 · 基期:2011.01=100 · ${months.length}条`;
}

function exportCity(){
    if(_selected.length===0)return;
    let months=CITY_DATA.m;
    let type=_cityTab==='new'?'nm':'sm';
    let indices={};
    for(let city of _selected){
        let cd=CITY_DATA.c[city];
        if(!cd)continue;
        let raw=cd[type];
        if(!raw||!raw.v||raw.v.length===0)continue;
        let vals=new Array(months.length).fill(null);
        for(let i=0;i<raw.v.length;i++){
            if(raw.v[i]!==null)vals[raw.o+i]=raw.v[i];
        }
        indices[city]=calcCityIdx(vals);
    }
    let h=['月份',..._selected];
    let rows=[h];
    months.forEach((m,i)=>{
        let r=[m];
        for(let c of _selected)r.push(indices[c]?.[i]?.toFixed(1)||'');
        rows.push(r);
    });
    let ws=XLSX.utils.aoa_to_sheet(rows);ws['!cols']=h.map(()=>({wch:14}));
    let wb=XLSX.utils.book_new();XLSX.utils.book_append_sheet(wb,ws,'城市对比');
    XLSX.writeFile(wb,'70城房价对比.xlsx');
}

// ===== VIEW SWITCH =====
function switchView(v){
    document.querySelectorAll('.top-tab').forEach(t=>t.classList.remove('active'));
    if(v==='natl') document.querySelector('.top-tab:first-child').classList.add('active');
    else document.querySelector('.top-tab:last-child').classList.add('active');
    document.getElementById('vn').style.display=v==='natl'?'':'none';
    document.getElementById('vr').style.display=v==='reg'?'':'none';
    if(v==='reg'){
        requestAnimationFrame(()=>{
            requestAnimationFrame(()=>{
                if(_cc){_cc.dispose();_cc=null;}
                applyCity();
                if(_cc)_cc.resize();
            });
        });
    }else{
        setTimeout(()=>{if(_mc)_mc.resize();if(_yc)_yc.resize();},200);
    }
}

// ===== RESIZE =====
window.addEventListener('resize',()=>{
    if(_mc)_mc.resize();if(_yc)_yc.resize();
    if(_cc)_cc.resize();
});

// ===== CITY DATA =====
'''

# Replace lines
new_lines = lines[:regional_start] + [new_regional] + lines[init_start:]
with open("index.html", "w", encoding="utf-8") as f:
    f.writelines(new_lines)

print("Replacement done!")
