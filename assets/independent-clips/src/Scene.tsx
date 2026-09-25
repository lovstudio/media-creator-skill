import React, {useEffect, useState} from 'react';
import settings from './settings.json';
import {AbsoluteFill, Audio, Img, OffthreadVideo, cancelRender, continueRender, delayRender, staticFile, useCurrentFrame, useVideoConfig, interpolate} from 'remotion';

export type Cue={start:number;end:number;text:string};
export type ClipData={id:string;brand:string;fps:number;title:string;titleLines:string[];duration:number;role:string;cropX:number;cropY:number;cues:Cue[];chapters:{start:number;label:string}[];audio:string;presentation?:string;beats?:{start:number;heading:string;detail:string}[];waveform?:number[];showInset?:boolean;coverKeywords?:string[]};
const palette={paper:'#F9F9F7',ink:'#181818',muted:'#746B64',accent:'#CC785C',line:'#DAD4CC'};

const Paper:React.FC=()=>settings.paper?<Img src={staticFile('cover-paper.png')} style={{position:'absolute',width:'100%',height:'100%',objectFit:'fill'}}/>:<div style={{position:'absolute',bottom:0,width:'100%',height:'16%',background:palette.accent}}/>;

const Fonts:React.FC=()=>{
  const [handle]=useState(()=>delayRender('Load local Chinese fonts'));
  useEffect(()=>{
    const a=new FontFace('NotoLocal',`url(${staticFile('fonts/NotoSansSC-VariableFont_wght.ttf')})`,{weight:'100 900'});
    const b=new FontFace('SmileyLocal',`url(${staticFile('fonts/SmileySans-Oblique.ttf')})`);
    Promise.all([a.load(),b.load()]).then(fs=>{fs.forEach(f=>document.fonts.add(f));continueRender(handle);}).catch(cancelRender);
  },[handle]);return null;
};

const VideoPanel:React.FC<{clip:ClipData;style:React.CSSProperties;crop?:boolean}>=({clip,style,crop})=>{
  const scale=crop?Number(style.width)/400:undefined;
  return <div style={{position:'absolute',overflow:'hidden',...style}}>
    <OffthreadVideo muted src={staticFile('body/'+clip.id+'.mp4')} style={crop?{position:'absolute',width:1920*scale!,height:1080*scale!,maxWidth:'none',left:-clip.cropX*scale!,top:-clip.cropY*scale!}:{width:'100%',height:'100%',objectFit:'contain'}} />

  </div>;
};

const SourcePhoto:React.FC<{clip:ClipData;vertical:boolean}>=({clip,vertical})=>{
  const w=vertical?980:660,h=vertical?596:610;const scale=Math.max(w/1920,h/1080);const left=(w-1920*scale)*(vertical?.5:.63),top=(h-1080*scale)*(vertical?.5:.55);
  return <><Img src={staticFile('photos/'+clip.id+'.jpg')} style={{position:'absolute',width:1920*scale,height:1080*scale,maxWidth:'none',left,top}}/></>;
};

const VoiceCard:React.FC<{clip:ClipData;sec:number}>=({clip,sec})=>{
  const beat=(clip.beats??[]).reduce((chosen,b)=>sec>=b.start?b:chosen,clip.beats?.[0]);
  const age=sec-(beat?.start??0);
  const opacity=interpolate(age,[0,.2],[.5,1],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  return <div style={{position:'absolute',left:64,top:510,width:952,height:585,borderRadius:16,background:'rgba(255,255,255,.83)',border:'1px solid #E7DFD6',boxShadow:'0 8px 28px rgba(82,57,36,.05)'}}>
    <div style={{position:'absolute',left:40,top:34,width:42,height:5,background:palette.accent}}/>
    <div style={{position:'absolute',left:106,top:20,fontSize:25,letterSpacing:3,color:palette.muted}}>现场原声 · 观点摘要</div>
    <div style={{position:'absolute',left:42,right:40,top:124,opacity,transform:`translateY(${(1-opacity)*9}px)`}}>
      <div style={{fontFamily:'SmileyLocal',fontSize:68,lineHeight:1.3,color:palette.ink}}>{beat?.heading}</div>
      <div style={{marginTop:36,fontSize:42,lineHeight:1.65,color:palette.muted}}>{beat?.detail}</div>
    </div>
    <div style={{position:'absolute',left:44,right:44,bottom:39,height:64,display:'flex',alignItems:'center',gap:9}}>
      {Array.from({length:45},(_,i)=>{const ix=Math.round(sec*20)+i-22;const level=clip.waveform?.[Math.max(0,ix)]??0;return <div key={i} style={{width:10,height:5+Math.pow(level,.65)*57,borderRadius:3,background:palette.accent,opacity:.38+level*.5}}/>;})}
    </div>
  </div>;
};

export const Clip:React.FC<{clip:ClipData;vertical:boolean}>=({clip,vertical})=>{
  const frame=useCurrentFrame();const {fps,durationInFrames}=useVideoConfig();const sec=frame/fps;
  const cue=clip.cues.find(c=>sec>=c.start&&sec<c.end);
  const fade=interpolate(frame,[0,8,durationInFrames-7,durationInFrames-1],[1,1,1,0],{extrapolateLeft:'clamp',extrapolateRight:'clamp'});
  return <AbsoluteFill style={{background:palette.paper,color:palette.ink,fontFamily:'NotoLocal',opacity:fade}}>
    <Fonts/>
    <Paper/>
    <Audio src={staticFile(clip.audio)}/>
    {vertical?<>
      <div style={{position:'absolute',left:64,top:174,fontSize:29,fontWeight:600,color:palette.muted,letterSpacing:3}}>{clip.brand}</div>
      <div style={{position:'absolute',left:62,top:246,right:56,fontSize:90,lineHeight:1.16,fontFamily:'SmileyLocal'}}>{clip.titleLines.map((line,i)=><div key={line} style={{color:i===clip.titleLines.length-1?palette.accent:palette.ink}}>{line}</div>)}</div>
      {clip.presentation==='audio-led'?<VoiceCard clip={clip} sec={sec}/>:<VideoPanel clip={clip} style={{left:0,top:492,width:1080,height:607.5,background:'#171717'}}/>}
      <div style={{position:'absolute',left:0,top:1099.5,height:5,width:1080*frame/(durationInFrames-1),background:palette.accent}}/>
      <VideoPanel clip={clip} crop={clip.presentation!=='audio-led'} style={{left:64,top:clip.presentation==='audio-led'?1190:1154,width:278,height:clip.presentation==='audio-led'?156.375:280,borderRadius:14}}/>
      <div style={{position:'absolute',left:384,top:1150,fontSize:25,color:palette.muted,letterSpacing:2}}>{clip.role}</div>
      <div style={{position:'absolute',left:384,right:70,top:1206,fontSize:47,fontWeight:650,lineHeight:1.5,whiteSpace:'pre-line',minHeight:180}}>{cue?.text}</div>
      <div style={{position:'absolute',left:64,right:68,top:1515,display:'flex',gap:24,borderTop:`1px solid ${palette.line}`,paddingTop:24}}>{clip.chapters.map((c,i)=><div key={c.label} style={{flex:1,color:palette.muted,fontSize:27,fontWeight:500,lineHeight:1.4}}><div style={{width:26,height:3,background:palette.accent,marginBottom:12}}/>{c.label}</div>)}</div>
    </>:<>
      <VideoPanel clip={clip} style={{left:0,top:0,width:1920,height:1080}}/>
      <div style={{position:'absolute',left:38,top:28,padding:'10px 22px',background:'rgba(249,249,247,.94)',borderLeft:`5px solid ${palette.accent}`,fontSize:31,fontWeight:700}}>{clip.title}</div>
      <div style={{position:'absolute',bottom:50,left:180,right:180,textAlign:'center',fontSize:49,lineHeight:1.42,fontWeight:700,color:'white',textShadow:'0 2px 6px #000',whiteSpace:'pre-line'}}>{cue?.text.split('\n').join(' ')}</div>
      <div style={{position:'absolute',bottom:0,left:0,height:5,width:1920*frame/(durationInFrames-1),background:palette.accent}}/>
    </>}
  </AbsoluteFill>;
};

export const Cover:React.FC<{clip:ClipData;vertical:boolean}>=({clip,vertical})=>{
  const units=(s:string)=>Array.from(s).reduce((n,c)=>n+(c.charCodeAt(0)<128?.56:1),0);
  const titleSize=Math.min(vertical?136:104,Math.floor((vertical?930:620)/Math.max(...clip.titleLines.map(units))));
  return <AbsoluteFill style={{fontFamily:'NotoLocal',background:palette.paper,color:palette.ink}}><Fonts/>
    <Paper/>
    <div style={{position:'absolute',left:76,top:78,fontSize:30,fontWeight:650,color:palette.muted,letterSpacing:3}}>{clip.brand}</div>
    <div style={{position:'absolute',left:70,top:vertical?176:170,right:vertical?62:748,fontFamily:'SmileyLocal',fontSize:titleSize,lineHeight:1.2}}>{clip.titleLines.map((l,i)=><div key={l} style={{color:i===clip.titleLines.length-1?palette.accent:palette.ink}}>{l}</div>)}</div>
    <div style={{position:'absolute',left:vertical?50:710,top:vertical?588:170,width:vertical?980:660,height:vertical?596:610,overflow:'hidden',borderRadius:6,boxShadow:'0 12px 28px rgba(50,32,20,.16)',transform:vertical?'rotate(-1deg)':'rotate(1deg)'}}>
      {clip.presentation==='audio-led'?<div style={{height:'100%',background:'#F0EAE1',padding:'65px 58px',boxSizing:'border-box',display:'flex',flexDirection:'column',justifyContent:'center',gap:38}}>
        {(clip.coverKeywords??[]).map((word,i)=><div key={word} style={{fontSize:vertical?76:58,fontFamily:'SmileyLocal',color:i===1?palette.accent:palette.ink,borderBottom:'1px solid #D4C6B6',paddingBottom:20}}>{word}</div>)}
      </div>:<SourcePhoto clip={clip} vertical={vertical}/>}
    </div>
    <div style={{position:'absolute',left:78,bottom:vertical?80:60,fontSize:32,fontWeight:550,color:'white',letterSpacing:5}}>{clip.role}</div>
  </AbsoluteFill>;
};
