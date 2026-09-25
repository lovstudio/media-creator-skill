import fs from 'node:fs';
import path from 'node:path';
import crypto from 'node:crypto';
import {execFileSync} from 'node:child_process';
import {fileURLToPath} from 'node:url';
import {bundle} from '@remotion/bundler';
import {getCompositions, openBrowser, renderMedia, renderStill} from '@remotion/renderer';

const root=path.dirname(fileURLToPath(import.meta.url));
const [id,mode='video']=process.argv.slice(2);
if (!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(id??'') || !['covers','video','canary'].includes(mode)) throw Error('Usage: node render.mjs CLIP_ID covers|video|canary');
const out=path.join(path.dirname(root),'clips',id);
const digest=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
const lockFile=path.join(out,'lock.json');
const lock=JSON.parse(fs.readFileSync(lockFile,'utf8'));
const lockHash=digest(lockFile);
for (const [name,hash] of Object.entries(lock.template)) if(digest(path.join(root,name))!==hash) throw Error('Locked template changed: '+name);
for (const [p,hash] of [[`public/body/${id}.mp4`,lock.body_sha256],[`public/audio/${id}.m4a`,lock.audio_sha256],[`public/photos/${id}.jpg`,lock.cover_photo_sha256]]) if(digest(path.join(root,p))!==hash) throw Error('Stale render input: '+p);
const current=JSON.parse(fs.readFileSync(path.join(root,'src/clips.json'),'utf8'));
if(JSON.stringify(current)!==JSON.stringify([lock.clip_data])) throw Error('Render data differs from lock');
const recordPath=path.join(out,mode==='video'?'render.json':mode+'.json');
if(fs.existsSync(recordPath)) {
  const old=JSON.parse(fs.readFileSync(recordPath,'utf8'));
  if(old.lock_sha256!==lockHash || Object.entries(old.artifacts).some(([name,hash])=>!fs.existsSync(path.join(out,name))||digest(path.join(out,name))!==hash)) throw Error('Stale render cache; start a new revision');
  console.log('Cached',id,mode);process.exit(0);
}
const preserve=p=>{if(fs.existsSync(p)) fs.renameSync(p,p+'.interrupted-'+Date.now());};
const serveUrl=await bundle({entryPoint:path.join(root,'src/index.tsx'),rootDir:root,publicDir:path.join(root,'public'),symlinkPublicDir:true});
const browser=await openBrowser('chrome',{logLevel:'warn'});
const began=Date.now();
const artifacts={};
try {
  const compositions=await getCompositions(serveUrl,{puppeteerInstance:browser});
  const shared={serveUrl,puppeteerInstance:browser,logLevel:'warn',timeoutInMilliseconds:120000};
  if(mode==='covers') {
    for(const ratio of ['3x4','4x3']) {
      const name='cover-'+ratio+'.png',output=path.join(out,name);preserve(output);
      await renderStill({...shared,composition:compositions.find(c=>c.id===id+'-cover-'+ratio),output,imageFormat:'png'});
      artifacts[name]=digest(output);
    }
  } else {
    const composition=compositions.find(c=>c.id===id+'-vertical');
    const name=mode==='video'?'muted.mp4':'canary-muted.mp4';
    const outputLocation=path.join(out,name);preserve(outputLocation);
    const frames=mode==='canary'?Math.min(composition.durationInFrames,10*composition.fps):composition.durationInFrames;
    await renderMedia({...shared,composition,outputLocation,codec:'h264',crf:21,encodingMaxRate:'8M',encodingBufferSize:'16M',pixelFormat:'yuv420p',colorSpace:'bt709',muted:true,frameRange:[0,frames-1],concurrency:4,offthreadVideoThreads:2,x264Preset:'fast'});
    artifacts[name]=digest(outputLocation);
    if(mode==='canary') {
      const canary=path.join(out,'canary.mp4');preserve(canary);
      execFileSync('ffmpeg',['-v','error','-nostdin','-n','-i',outputLocation,'-i',path.join(out,'mix.m4a'),'-map','0:v:0','-map','1:a:0','-c','copy','-t',String(frames/composition.fps),'-movflags','+faststart',canary]);
      artifacts['canary.mp4']=digest(canary);
    }
  }
  fs.writeFileSync(recordPath,JSON.stringify({status:mode==='canary'?'preview-only':'rendered',lock_sha256:lockHash,artifacts,sha256:artifacts['muted.mp4']??null,wall_seconds:(Date.now()-began)/1000},null,2)+'\n');
} finally {await browser.close({silent:true});}
