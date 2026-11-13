#!/usr/bin/env python3
"""The walkthrough voice for other skills: spoken lines in, one audio clip and word times out.
The concept skill calls this to narrate a concept page (see ../concept/cx.mjs).

usage: uv run --project <this folder> voice.py < request.json
request:  {"voice": "af_heart", "speed": 1.0, "lexicon": {}, "check": false, "say": false, "cache": true,
           "lines": [{"caption": "...", "say": "...", "cues": ["phrase", ...]}]}
prints one JSON line:
  {"ok", "engine", "mime", "audio" (base64), "seconds",
   "lines": [{"t", "dur", "spoken", "wt": [...], "cues": [...]}], "errors": [...]}
"wt" holds one start time for each word of the caption. "cues" holds the time each cue phrase is spoken.
"check": true makes no audio: it reports how each line is spoken and whether each cue phrase is in the line.
"""
import base64, json, sys

import build as B


def main():
    req = json.load(sys.stdin)
    voice, speed = req.get('voice') or 'af_heart', float(req.get('speed') or 1.0)
    if not B.VOICE_RE.match(voice):
        return {'ok': False, 'errors': [f'voice "{voice}" is not a Kokoro voice name']}
    lex = B.load_lexicon({'lexicon': req.get('lexicon') or {}})
    lines = req.get('lines') or []
    spoken = [B.speakable(ln.get('say') or ln['caption'], lex) for ln in lines]

    def place(words_per_line):
        """-> (one list of word indexes per line, errors). Cue phrases must come in spoken order."""
        rows, errors = [], []
        for i, (ln, words) in enumerate(zip(lines, words_per_line)):
            row, idx = [], 0
            for phrase in ln.get('cues') or []:
                said = B.speakable(str(phrase), lex)
                j = B.find_cue(words, said, idx)
                if j is None:
                    errors.append(f'beat {i + 1}: "{phrase}" (spoken as "{said}") is not in the spoken line '
                                  f'after the previous cue: {spoken[i]!r}')
                else:
                    idx = j + 1
                row.append(j)
            rows.append(row)
        return rows, errors

    if req.get('check'):
        rows, errors = place([[(w, 0, 0) for w in s.split()] for s in spoken])
        return {'ok': not errors, 'engine': None, 'errors': errors, 'lines': [{'spoken': s} for s in spoken]}

    import numpy as np
    if req.get('cache') is False:
        B.CACHE['on'] = False
    if req.get('say'):
        synth, engine = B.fallback_synth(spoken), B.fallback_voice()
    else:
        try:
            synth, engine = B.kokoro_synth(spoken, voice, speed), f'kokoro:{voice}'
        except Exception as ex:
            return {'ok': False, 'errors': [f'Kokoro failed: {ex!r}. Pass --say to use the system voice.']}
    rows, errors = place([w for _, w in synth])
    if errors:
        return {'ok': False, 'errors': errors}
    gap = np.zeros(int(B.GAP_S * B.SR), np.float32)
    chunks, t, out = [], 0.0, []
    for ln, s, (clip, words), row in zip(lines, spoken, synth, rows):
        dur = len(clip) / B.SR
        out.append({'t': round(t, 3), 'dur': round(dur, 3), 'spoken': s,
                    'wt': B.caption_times(ln['caption'], words, t, dur),
                    'cues': [round(t + words[j][1], 3) for j in row]})
        chunks += [clip, gap]; t += (len(clip) + len(gap)) / B.SR
    mime, data = B.encode(np.concatenate(chunks))
    return {'ok': True, 'engine': engine, 'mime': mime, 'audio': base64.b64encode(data).decode(), 'seconds': round(t, 2),
            'cached': B.CACHE['hit'], 'spoken': B.CACHE['made'], 'lines': out, 'errors': []}


if __name__ == '__main__':
    try:
        res = main()
    except Exception as ex:  # every failure still prints one JSON line
        import traceback
        traceback.print_exc()
        res = {'ok': False, 'errors': [f'{type(ex).__name__}: {ex}']}
    print(json.dumps(res))
    sys.exit(0 if res.get('ok') else 2)
