import React from 'react';
import {registerRoot, Composition} from 'remotion';
import {Clip, Cover, type ClipData} from './Scene';
import clips from './clips.json';

const Root: React.FC = () => <>
  {(clips as ClipData[]).map(clip => <React.Fragment key={clip.id}>
    <Composition id={clip.id+'-vertical'} component={Clip} durationInFrames={Math.round(clip.duration*clip.fps)} fps={clip.fps} width={1080} height={1920} defaultProps={{clip,vertical:true}} />
    <Composition id={clip.id+'-cover-3x4'} component={Cover} durationInFrames={1} fps={clip.fps} width={1080} height={1440} defaultProps={{clip,vertical:true}} />
    <Composition id={clip.id+'-cover-4x3'} component={Cover} durationInFrames={1} fps={clip.fps} width={1440} height={1080} defaultProps={{clip,vertical:false}} />
  </React.Fragment>)}
</>;
registerRoot(Root);
