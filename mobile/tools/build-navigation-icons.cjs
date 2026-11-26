/* Original line icons rasterized from paths; no external icon fonts or SDK. */
const fs = require('node:fs'), path = require('node:path'), zlib = require('node:zlib');
const size = 72;
const circle = (x, y, r) => Array.from({ length: 49 }, (_, i) => [x + r * Math.cos(i / 48 * Math.PI * 2), y + r * Math.sin(i / 48 * Math.PI * 2)]);
const icons = {
  today: [[[3,11],[12,4],[21,11]],[[6,10],[6,20],[10,20],[10,14],[14,14],[14,20],[18,20],[18,10]]],
  training: [[[5,6],[19,6],[20,7],[20,20],[4,20],[4,7],[5,6]],[[8,3],[8,8]],[[16,3],[16,8]],[[4,11],[20,11]],[[8,15],[10,15]],[[14,15],[16,15]]],
  coach: [[[5,4],[19,4],[21,6],[21,16],[19,18],[11,18],[6,21],[6,18],[5,18],[3,16],[3,6],[5,4]],[[8,11],[8.1,11]],[[12,11],[12.1,11]],[[16,11],[16.1,11]]],
  analytics: [[[5,19],[5,12]],[[12,19],[12,4]],[[19,19],[19,8]],[[3,21],[21,21]]],
  tools: [[[4,4],[10,4],[10,10],[4,10],[4,4]],[[14,4],[20,4],[20,10],[14,10],[14,4]],[[4,14],[10,14],[10,20],[4,20],[4,14]],[[14,14],[20,14],[20,20],[14,20],[14,14]]],
  profile: [circle(12,7.5,3.5),[[5,21],[5,19],[7,15],[17,15],[19,19],[19,21]]],
};
function crc32(data) { let c=0xffffffff; for(const b of data){c^=b;for(let i=0;i<8;i++)c=(c>>>1)^(c&1?0xedb88320:0);} return(c^0xffffffff)>>>0; }
function chunk(name,data){const t=Buffer.from(name),n=Buffer.alloc(4),c=Buffer.alloc(4);n.writeUInt32BE(data.length);c.writeUInt32BE(crc32(Buffer.concat([t,data])));return Buffer.concat([n,t,data,c]);}
function distance(x,y,a,b){const dx=b[0]-a[0],dy=b[1]-a[1],t=Math.max(0,Math.min(1,((x-a[0])*dx+(y-a[1])*dy)/(dx*dx+dy*dy||1)));return Math.hypot(x-a[0]-t*dx,y-a[1]-t*dy);}
function png(paths,color){
  const rgb=[0,2,4].map(o=>parseInt(color.slice(o,o+2),16)),raw=Buffer.alloc(size*(size*4+1));
  for(let y=0;y<size;y++)for(let x=0;x<size;x++){
    let coverage=0;
    for(const sy of [.25,.75])for(const sx of [.25,.75])if(paths.some(p=>p.slice(1).some((b,i)=>distance((x+sx)/3,(y+sy)/3,p[i],b)<.85)))coverage++;
    const o=y*(size*4+1)+1+x*4;raw[o]=rgb[0];raw[o+1]=rgb[1];raw[o+2]=rgb[2];raw[o+3]=Math.round(coverage/4*255);
  }
  const h=Buffer.alloc(13);h.writeUInt32BE(size,0);h.writeUInt32BE(size,4);h[8]=8;h[9]=6;
  return Buffer.concat([Buffer.from('89504e470d0a1a0a','hex'),chunk('IHDR',h),chunk('IDAT',zlib.deflateSync(raw)),chunk('IEND',Buffer.alloc(0))]);
}
const directory=path.resolve(__dirname,'../static/navigation');fs.mkdirSync(directory,{recursive:true});
for(const [name,paths] of Object.entries(icons))for(const [suffix,color] of [['','66756f'],['-active','1976d2']])fs.writeFileSync(path.join(directory,name+suffix+'.png'),png(paths,color));
const toolIcons = {cycle:[[[20,9],[17,5],[9,4],[4,9]],[[4,9],[9,9]],[[4,9],[4,4]],[[4,15],[7,19],[15,20],[20,15]],[[20,15],[15,15]],[[20,15],[20,20]]],
spark:[[[12,3],[14,9],[21,12],[14,14],[12,21],[9,14],[3,12],[9,9],[12,3]]],
review:[[[5,4],[19,4],[19,21],[5,21],[5,4]],[[8,12],[11,15],[16,9]]],
pace:[[[3,17],[4,10],[8,6],[16,6],[20,10],[21,17],[3,17]],[[12,15],[16,10]]],
rules:[[[5,4],[5,20]],[[12,4],[12,20]],[[19,4],[19,20]],[[3,8],[7,8]],[[10,15],[14,15]],[[17,10],[21,10]]],
medal:[[[9,12],[6,3],[10,3],[12,8],[14,3],[18,3],[15,12]]],
upload:[[[5,16],[5,21],[19,21],[19,16]],[[12,17],[12,3],[7,8]],[[12,3],[17,8]]],
download:[[[5,16],[5,21],[19,21],[19,16]],[[12,3],[12,16],[7,11]],[[12,16],[17,11]]],
tasks:[[[6,3],[19,3],[19,21],[6,21],[6,3]],[[9,8],[16,8]],[[9,12],[16,12]],[[9,16],[13,16]]],
pulse:[[[2,12],[7,12],[10,5],[14,19],[17,12],[22,12]]],
rest:[[[16,3],[10,4],[5,9],[5,15],[9,20],[15,21],[20,17],[14,16],[10,12],[10,8],[16,3]]],
trend:[[[4,4],[4,20],[21,20]],[[7,15],[11,11],[15,13],[21,6]],[[16,6],[21,6],[21,11]]],
sync:[[[3,8],[20,8],[16,4]],[[21,16],[4,16],[8,20]]],
watch:[[[9,3],[15,3],[17,7],[17,17],[15,21],[9,21],[7,17],[7,7],[9,3]],[[7,8],[17,8]],[[7,16],[17,16]]],
prefs:[[[12,3],[12,21]],[[4,7],[20,7]],[[7,7],[4,15],[10,15],[7,7]],[[17,7],[14,15],[20,15],[17,7]],[[8,21],[16,21]]],
feedback:[[[4,4],[20,4],[20,16],[10,16],[5,21],[5,16],[4,16],[4,4]],[[8,8],[16,8]],[[8,12],[13,12]]], stats: icons.analytics };
toolIcons.medal.push(circle(12,16,4.5));
const toolDirectory=path.resolve(__dirname,'../static/tools');fs.mkdirSync(toolDirectory,{recursive:true});
const toolColors=['1865b5','7053b9','148173','b45a22','455fae'];
Object.entries(toolIcons).forEach(([name, strokes], index) => fs.writeFileSync(path.join(toolDirectory,name+'.png'),png(strokes,toolColors[index%toolColors.length])));
console.log('Generated 12 original 72px navigation icons.');
