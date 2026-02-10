# The Fashanus - Tools Research (Safe & Reliable Only)

## Research Summary

**Date:** 2026-02-10
**Updated:** 2026-02-10
**Researcher:** Duro

This document contains vetted, safe tools for producing The Fashanus series.

---

## Safety Criteria

All tools listed here meet these requirements:
- From established sources (Microsoft, Python Foundation, major companies)
- Open source with active communities
- No credential storage in code
- No risky third-party dependencies
- Well-documented and widely used

---

## Approved Tools

### 1. edge-tts (Text-to-Speech)

**Source:** Microsoft Edge TTS (open source wrapper)
**PyPI:** https://pypi.org/project/edge-tts/
**GitHub:** https://github.com/rany2/edge-tts
**Downloads:** 10M+

**What it does:**
- Converts text to speech using Microsoft's public TTS service
- 300+ high-quality voices
- Multiple languages including British and Nigerian English
- Completely free, no API key needed

**Why it's safe:**
- Uses Microsoft's public, legitimate TTS endpoint
- Open source, auditable code
- No authentication required
- No data stored locally beyond the audio files you create

**Installation:**
```bash
pip install edge-tts
```

**Basic Usage:**
```bash
# List voices
edge-tts --list-voices

# Generate speech
edge-tts --voice "en-GB-RyanNeural" --text "Hello" --write-media output.mp3
```

---

### 2. Pillow (Image Processing)

**Source:** Python Pillow (PIL Fork)
**PyPI:** https://pypi.org/project/Pillow/
**Downloads:** 500M+

**What it does:**
- Opens, manipulates, and saves image files
- Industry standard for Python image processing

**Why it's safe:**
- Maintained by Python community for 20+ years
- No network calls
- Processes files locally only

**Installation:**
```bash
pip install Pillow
```

---

### 3. Hugging Face Hub (Optional - For Image Generation)

**Source:** Hugging Face (established AI company)
**PyPI:** https://pypi.org/project/huggingface_hub/

**What it does:**
- Official API client for Hugging Face models
- Can generate images via their Inference API

**Why it's safe:**
- From a legitimate, well-known AI company
- Official SDK, not a wrapper or hack
- Uses proper API authentication
- Free tier available

**Note:** Only use if you want automated image generation. Otherwise, use web interfaces directly.

---

## Recommended Voice Assignments

Based on edge-tts available voices:

| Character | Voice ID | Description |
|-----------|----------|-------------|
| Tunde | en-GB-RyanNeural | British male, warm, authoritative |
| Rachel | en-GB-SoniaNeural | British female, warm, natural |
| Maya | en-GB-MaisieNeural | British female, younger |
| Tayo | en-GB-ThomasNeural | British male, younger |

**Alternative for Tunde (Nigerian accent):**
- en-NG-AbeoNeural (Nigerian English male)
- en-NG-EzinneNeural (Nigerian English female)

---

## Image Generation Approach (Safe)

For image generation, use official web interfaces directly:

| Service | URL | Safety |
|---------|-----|--------|
| Google Gemini | gemini.google.com | Google account, official |
| ChatGPT/DALL-E | chat.openai.com | OpenAI account, official |
| Microsoft Designer | designer.microsoft.com | Microsoft account, official |
| Bing Image Creator | bing.com/create | Microsoft account, official |

**Process:**
1. Use CHARACTER_BIBLE.md for detailed prompts
2. Generate images in browser
3. Save to local folders
4. Use Pillow for any processing needed

---

## Video Generation Approach (Safe)

Use official web interfaces:

| Service | URL | Free Tier |
|---------|-----|-----------|
| LTX Studio | ltx.studio | 3600 seconds/month |
| Kling AI | klingai.com | Free credits on signup |
| Canva | canva.com | Limited free |

---

## What We're NOT Using

| Tool | Reason |
|------|--------|
| Unofficial API wrappers | Could break, unreliable |
| Credential-storing SDKs | Security risk |
| Reverse-engineered services | Unreliable, potentially TOS violation |
| Unknown free APIs | Could disappear, unknown safety |

---

## Production Workflow (Safe Version)

```
[Script/Dialogue]
      ↓
[edge-tts] → Voice files (.mp3)
      ↓
[Web tools - Gemini/DALL-E] → Character images (manual)
      ↓
[Web tools - LTX/Kling] → Video clips (manual)
      ↓
[CapCut] → Final episode (manual)
```

**Automated:** Voice generation only
**Manual:** Image generation, video generation, editing

This is the safest approach while still being productive.

---

*Research by Duro - Safe tools only*
