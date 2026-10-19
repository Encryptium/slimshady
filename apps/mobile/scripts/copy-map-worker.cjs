// Metro does not emit MapLibre 6's separate module-worker entry automatically.
const fs=require('node:fs');const path=require('node:path');
const dest=path.resolve(__dirname,'../public/maplibre');fs.mkdirSync(dest,{recursive:true});
for(const file of ['maplibre-gl-worker.mjs','maplibre-gl-shared.mjs']){
  fs.copyFileSync(path.resolve(__dirname,'../node_modules/maplibre-gl/dist',file),path.join(dest,file));
}
fs.copyFileSync(path.resolve(__dirname,'../node_modules/maplibre-gl/LICENSE.txt'),path.join(dest,'LICENSE.txt'));
