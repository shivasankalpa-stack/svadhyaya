(function(){
  var root=document.documentElement;
  function setMode(m){root.dataset.lang=m;try{localStorage.setItem('vm-lang',m)}catch(e){}
    document.querySelectorAll('.lang button').forEach(function(b){b.setAttribute('aria-pressed',String(b.dataset.set===m))});}
  document.querySelectorAll('.lang button').forEach(function(b){b.addEventListener('click',function(){setMode(b.dataset.set)})});
  setMode(root.dataset.lang||'both');

  var form=document.getElementById('search-form'); if(!form) return;
  var q=document.getElementById('q'),out=document.getElementById('results'),st=document.getElementById('search-status'),idx=null;
  function norm(s){return (s||'').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g,'')}
  function esc(s){return String(s).replace(/[&<>"]/g,function(c){return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]})}
  function snip(text,term){var t=text||'',n=norm(t),i=n.indexOf(term);if(i<0)return esc(t.slice(0,140))+(t.length>140?'…':'');
    var a=Math.max(0,i-60),b=Math.min(t.length,i+term.length+80);
    return (a?'…':'')+esc(t.slice(a,i))+'<mark>'+esc(t.slice(i,i+term.length))+'</mark>'+esc(t.slice(i+term.length,b))+(b<t.length?'…':'');}
  function run(){var term=norm(q.value.trim());out.innerHTML='';if(!term){st.textContent='';return}
    var hits=idx.filter(function(e){return norm(e.k).indexOf(term)>=0||norm(e.e).indexOf(term)>=0||norm(e.r).indexOf(term)>=0}).reverse();
    st.textContent=hits.length+(hits.length===1?' match':' matches');
    out.innerHTML=hits.slice(0,80).map(function(e){
      var d=new Date(e.d+'T00:00:00');var ds=d.toLocaleDateString('en-GB',{day:'numeric',month:'short',year:'numeric'});
      return '<li><a href="'+e.u+'"><span class="r-top">'+esc(e.l)+' · '+ds+'</span><span class="r-k">'+snip(e.k,term)+'</span>'+(e.e?'<span class="r-e">'+snip(e.e,term)+'</span>':'')+'</a></li>'}).join('');}
  form.addEventListener('submit',function(ev){ev.preventDefault();run()});
  q.addEventListener('input',function(){if(idx)run()});
  st.textContent='Loading…';
  fetch('search-index.json').then(function(r){return r.json()}).then(function(d){idx=d;st.textContent='';var h=location.hash.slice(1);if(h){q.value=decodeURIComponent(h)}run()})
    .catch(function(){st.textContent='The search index could not be loaded. Try reloading the page.'});
})();
