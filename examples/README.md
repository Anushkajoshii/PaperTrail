# Example inputs

**These are synthetic.** They were written for testing and demos and imitate common finfluencer
patterns. They are not quotes from any real creator, and the company names are used only as
ticker examples.

| File | Language | What it exercises |
|---|---|---|
| `hinglish_reel.txt` | Hinglish | Guaranteed returns, stock call with target, credential claim, Telegram tip group |
| `english_post.txt` | English | Past performance, market fact, company fact, an opinion that should be skipped |
| `hindi_clip.txt` | Hindi (Devanagari) | Return promise and past-performance claims in Devanagari |

Try one:

```bash
uv run python -m papertrail.agent.extract examples/hinglish_reel.txt
```
