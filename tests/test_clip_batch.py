import copy
import json
from pathlib import Path
import sys
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from clip_batch import Batch, fingerprint, mapped_video_ranges, parse_srt, preserve_partial, probe, sha, status, validate_plan, write
from clip_subtitles import build_cues, timestamp


def plan():
    return {'schema':'media-independent-clips/v1','source':{'path':'source.mp4','duration':10},'fps':25,
            'coverage':[{'start':0,'end':10,'decision':'candidate','reason':'Unique complete answer','evidence':'transcript 0–10'}],
            'clips':[{'id':'one','title':'独立回答','titleLines':['独立回答'],'ranges':[[0,4],[6,10]],
                      'reason':'Useful explanation','standalone_reason':'Contains question and answer',
                      'boundary_evidence':'Complete words and breath at both joins'}]}


class EditorialGuards(unittest.TestCase):
    def test_coverage_is_not_satisfied_by_selected_clips(self):
        p=plan(); p['coverage'][0]['end']=9
        with self.assertRaisesRegex(ValueError,'incomplete'): validate_plan(p)

    def test_unreviewed_region_cannot_be_selected(self):
        p=plan(); p['coverage'][0]['decision']='review'
        with self.assertRaisesRegex(ValueError,'unreviewed'): validate_plan(p)

    def test_duplicate_material_rejected(self):
        p=plan(); p['clips'].append({**p['clips'][0],'id':'two'})
        with self.assertRaisesRegex(ValueError,'Duplicate source'): validate_plan(p)

    def test_already_published_material_rejected(self):
        p=plan(); p['already_published_ranges']=[[2,3]]
        with self.assertRaisesRegex(ValueError,'already published'): validate_plan(p)

    def test_frame_precision(self):
        p=plan(); p['clips'][0]['ranges'][0][1]=4.01
        with self.assertRaisesRegex(ValueError,'frame-aligned'): validate_plan(p)

    def test_keyword_card_needs_evidence_and_content(self):
        p=plan(); p['clips'][0]['presentation']='audio-led'
        with self.assertRaisesRegex(ValueError,'summary beats'): validate_plan(p)

    def test_no_clips_or_nan_or_string_numbers(self):
        for mutation in [lambda p:p.update(clips=[]),lambda p:p['source'].update(duration=float('nan')),lambda p:p.update(fps='25')]:
            p=plan();mutation(p)
            with self.assertRaises(ValueError):validate_plan(p)

    def test_original_time_maps_to_separate_local_clocks(self):
        h={'files':[{'path':'a.mp4','source_start':20,'source_end':30},{'path':'b.mp4','source_start':30,'source_end':50}]}
        self.assertEqual(mapped_video_ranges([[24,35]],h),[('a.mp4',4,10),('b.mp4',0,5)])
        h['files'][1]['source_start']=31
        with self.assertRaisesRegex(ValueError,'gap'):mapped_video_ranges([[24,35]],h)

    def test_missing_boundary_reason(self):
        p=plan();del p['clips'][0]['boundary_evidence']
        with self.assertRaisesRegex(ValueError,'evidence'):validate_plan(p)


class ArtifactGuards(unittest.TestCase):
    @unittest.skipUnless(shutil.which('ffmpeg') and shutil.which('ffprobe'), 'requires FFmpeg/FFprobe')
    def test_real_discontinuous_cut_preserves_frame_and_sample_counts(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);src=root/'source.mp4'
            subprocess.run(['ffmpeg','-v','error','-nostdin','-f','lavfi','-i','testsrc2=size=320x180:rate=25:duration=4',
                            '-f','lavfi','-i','sine=frequency=440:sample_rate=48000:duration=4',
                            '-c:v','libx264','-c:a','aac',str(src)],check=True)
            p=plan();p['source']={'path':str(src),'duration':4};p['coverage'][0]['end']=4
            p['clips'][0]['ranges']=[[.2,1.4],[2,3.2]]
            write(root/'plan.json',p);write(root/'source-identity.json',fingerprint(src))
            batch=Batch(root);clip=batch.plan['clips'][0];batch.prepare(clip)
            self.assertEqual(int(probe(batch.path('one','body.mp4'))['streams'][0]['nb_frames']),60)
            def pcm(path):
                return subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-ac','1','-ar','48000','-f','s16le','pipe:1'])
            before,after=pcm(root/'source-48k.wav'),pcm(batch.path('one','source.wav'))
            self.assertEqual(len(after),115200*2)
            # Compare actual retained PCM outside the deliberate six-ms edge fades.
            for index,(a,b) in enumerate(clip['ranges']):
                original=before[(round(a*48000)+500)*2:(round(b*48000)-500)*2]
                output=after[(index*57600+500)*2:((index+1)*57600-500)*2]
                self.assertEqual(original,output)
            before_mtime=batch.path('one','body.mp4').stat().st_mtime_ns
            batch.prepare(clip)
            self.assertEqual(batch.path('one','body.mp4').stat().st_mtime_ns,before_mtime)
            clip['privacyMasks']=[{'x':0,'y':0,'w':40,'h':40}]
            with self.assertRaisesRegex(ValueError,'inputs changed'):batch.prepared(clip)

    def test_subtitle_overflow_overlap_and_bounds(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.srt'
            for content in ['1\n00:00:00,000 --> 00:00:02,000\n'+'字'*14,
                            '1\n00:00:00,000 --> 00:00:11,000\n字幕',
                            '1\n00:00:00,000 --> 00:00:02,000\n字幕\n\n2\n00:00:01,000 --> 00:00:03,000\n重叠']:
                p.write_text(content)
                with self.assertRaises(ValueError):parse_srt(p,10)

    def test_english_tokens_and_two_lines(self):
        transcript={'segments':[{'words':[{'word':'从一个具体的 Remotion 场景开始逐步调整，保留真实内容。','start':0,'end':5}]}]}
        cues=build_cues(transcript,5)
        self.assertIn('Remotion',''.join(c['text'] for c in cues))
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'draft.srt'
            path.write_text('\n\n'.join(f'{i+1}\n{timestamp(c["start"])} --> {timestamp(c["end"])}\n{c["text"]}' for i,c in enumerate(cues)))
            self.assertEqual(len(parse_srt(path,5)),len(cues))

    def test_interrupted_output_is_preserved(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'body.mp4';p.write_bytes(b'partial')
            preserve_partial([p])
            self.assertFalse(p.exists());self.assertEqual(next(Path(d).iterdir()).read_bytes(),b'partial')

    def test_hash_cache_refuses_modified_artifacts_and_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            b=object.__new__(Batch);b.root=Path(d)
            p=b.path('one','body.mp4');p.write_bytes(b'complete')
            b.stamp('one','prepare',{'ranges':[1,2]},[p])
            self.assertIsNotNone(b.cached('one','prepare',{'ranges':[1,2]}))
            with self.assertRaisesRegex(ValueError,'inputs changed'):b.cached('one','prepare',{'ranges':[2,3]})
            p.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'artifact changed'):b.cached('one','prepare',{'ranges':[1,2]})

    def test_rendered_does_not_mean_platform_ready_or_published(self):
        with tempfile.TemporaryDirectory() as d:
            b=object.__new__(Batch);b.root=Path(d);b.plan=validate_plan(plan())
            b.check_lock=lambda c:{}
            for f in ['final.mp4','cover-3x4.png','cover-4x3.png']:b.path('one',f).write_bytes(f.encode())
            write(b.path('one','final-qc.json'),{'sha256':sha(b.path('one','final.mp4'))})
            self.assertEqual(status(b)['platform_ready'],0)
            review={'status':'passed','reviewer':'delegated-agent','evidence':'Actual final head/mid/tail and two covers viewed',
                    'video_sha256':sha(b.path('one','final.mp4')),
                    **{n+'_sha256':sha(b.path('one',n+'.png')) for n in ['cover-3x4','cover-4x3']}}
            write(b.path('one','visual-review.json'),review)
            self.assertEqual(status(b)['platform_ready'],1)
            self.assertEqual(status(b)['publication'],'not-published')
            b.path('one','cover-4x3.png').write_bytes(b'changed')
            self.assertEqual(status(b)['platform_ready'],0)

    def test_unapproved_review_cannot_lock(self):
        with tempfile.TemporaryDirectory() as d:
            b=object.__new__(Batch);b.root=Path(d)
            review=Path(d)/'review.json';write(review,{'reviewer':'delegated-agent','authorization_evidence':'Current task','content':'passed'})
            with self.assertRaisesRegex(ValueError,'Missing actual review'):b.lock(plan()['clips'][0],review)


if __name__=='__main__':unittest.main()
