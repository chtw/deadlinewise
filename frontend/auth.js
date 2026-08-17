(function(){
  const KEY='deadlinewise_session';
  function session(){try{return JSON.parse(localStorage.getItem(KEY)||'null')}catch{return null}}
  function payload(token){try{return JSON.parse(atob(token.split('.')[1].replace(/-/g,'+').replace(/_/g,'/')))}catch{return{}}}
  function valid(){const s=session();return !!(s?.idToken&&payload(s.idToken).exp>Date.now()/1000)}
  function requireAuth(){if(!valid()){localStorage.removeItem(KEY);location.href='login.html';return false}return true}
  function token(){return session()?.idToken||''}
  function logout(){localStorage.removeItem(KEY);location.href='login.html'}
  window.DeadlineWiseAuth={session,valid,requireAuth,token,logout,payload};
})();
