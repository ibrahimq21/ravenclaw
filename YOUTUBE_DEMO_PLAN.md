# Ravenclaw YouTube Demo Video Plan

## 🎯 Video Goal
Drive GitHub stars, clones, and community contributions by showcasing Ravenclaw's value proposition.

---

## 📅 Recording Schedule

| Date | Day | Time | Activity |
|------|-----|------|----------|
| **Feb 14, 2026** | Saturday | 4:00 PM - 6:00 PM | **Primary Recording Slot** |
| Feb 15, 2026 | Sunday | 4:00 PM - 6:00 PM | Backup Slot (if needed) |
| Feb 16, 2026 | Monday | 7:00 PM - 9:00 PM | Evening Alternative |

**Recording Duration:** 2 hours (includes breaks, setup, retakes)

---

## 📹 Video Recording Requirements

### Software

| Tool | Purpose | Free/Paid |
|------|---------|-----------|
| **OBS Studio** | Screen recording | Free |
| **Windows 11 Game Bar** | Quick recording | Free (built-in) |
| **Camtasia** | Editing + recording | Paid ($249) |
| **Shotcut** | Editing | Free |

**Recommended:** OBS Studio (free, professional results)

### Hardware

| Item | Recommended | Budget Option |
|------|-------------|---------------|
| **Webcam** | Logitech C920 ($70) | Built-in laptop cam |
| **Microphone** | Audio-Technica AT2020 ($100) | USB mic ($30) |
| **Lighting** | Ring light ($25) | Natural light + window |
| **Tripod/Stand** | Flexible phone stand ($15) | Books/stack |

### OBS Studio Setup Checklist

- [ ] Download OBS Studio from obsproject.com
- [ ] Create "Scene" for full-screen terminal
- [ ] Create "Scene" for browser (Discord)
- [ ] Create "Scene" for picture-in-picture (webcam overlay)
- [ ] Add "Window Capture" source for terminal
- [ ] Add "Window Capture" source for browser
- [ ] Add "Video Capture Device" for webcam
- [ ] Configure audio input (microphone)
- [ ] Set video resolution: 1920x1080 (1080p)
- [ ] Set frame rate: 30 fps
- [ ] Test recording with 30-second clip
- [ ] Check file export settings (.mp4)

### Video Settings Checklist

- [ ] Resolution: 1920x1080 (1080p)
- [ ] Frame rate: 30 FPS
- [ ] Bitrate: 15,000 - 20,000 kbps
- [ ] Encoder: NVENC (NVIDIA) or x264 (CPU)
- [ ] Format: MP4
- [ ] Audio: AAC, 320 kbps

---

## 🎤 Audio Recording Requirements

### Equipment Checklist

| Item | Status | Notes |
|------|--------|-------|
| Microphone | ☐ | USB or XLR |
| Headphones | ☐ | Closed-back (prevent echo) |
| Pop filter | ☐ | Fabric pop filter |
| Mic stand/boom arm | ☐ | Desk mount |
| Acoustic treatment | ☐ | Foam panels (optional) |

### Audio Settings (OBS)

| Setting | Recommended | Your Setting |
|---------|-------------|--------------|
| Sample Rate | 48 kHz | |
| Channels | Stereo | |
| Bitrate | 320 kbps | |

### Pre-Recording Audio Checklist

- [ ] Test microphone levels (speak at normal volume)
- [ ] Check for background noise (fan, AC, traffic)
- [ ] Ensure no echo (use headphones)
- [ ] Record 10-second test clip
- [ ] Listen for:
  - [ ] Clear voice
  - [ ] No popping (P/B sounds)
  - [ ] No background hum
  - [ ] Consistent volume

### Audio Improvement Tips

| Problem | Solution |
|---------|----------|
| Echo | Add blankets/foam to room |
| Popping P/B | Use pop filter, speak slightly off-axis |
| Background noise | Record late night, close windows |
| Low volume | Move closer to mic (6-12 inches) |
| Clipping (distortion) | Lower mic gain, speak softer |

---

## 🖥️ Screen Recording Requirements

### Terminal Setup

| Setting | Value |
|---------|-------|
| Font | Cascadia Code or Fira Code |
| Font Size | 18-24px |
| Theme | Dark ( Dracula, One Dark ) |
| Colors | High contrast (easy to read) |

### Terminal Commands to Prepare

```bash
# Clear old data
cd ravenclaw
rm -f ravenclaw.log ravenclaw_inbox.json

# Fresh clone (for demo)
git clone https://github.com/ibrahimq21/ravenclaw.git demo-ravendemo
cd demo-ravendemo

# Prepare test email (for live demo)
echo "Test email content" > /tmp/test-email.txt
```

### Browser Setup

- [ ] Install OneTab extension (clean tabs)
- [ ] Open Discord in browser
- [ ] Create test channel: #ravenclaw-demo
- [ ] Prepare webhook URL in clipboard
- [ ] Clear browser bookmarks/history

---

## 🎬 Recording Day Checklist

### Morning Of (Feb 14)

- [ ] Restart computer (free RAM)
- [ ] Close unnecessary applications
  - [ ] Discord (unless using)
  - [ ] Slack
  - [ ] Spotify/music apps
  - [ ] Downloads folder
- [ ] Clear desktop (remove icons)
- [ ] Set phone to Do Not Disturb
- [ ] Inform family/roommates (1-2 hours quiet)

### 1 Hour Before Recording

- [ ] Set up microphone
- [ ] Put on headphones
- [ ] Test audio levels
- [ ] Open OBS Studio
- [ ] Load scenes
- [ ] Start recording
- [ ] Record 30-second test
- [ ] Review test recording
- [ ] Make adjustments

### During Recording

- [ ] Keep water nearby
- [ ] Speak slowly and clearly
- [ ] Pause between sections
- [ ] Don't rush
- [ ] If mistake: pause, take breath, restart sentence

### After Recording

- [ ] Save recording immediately
- [ ] Make backup copy
- [ ] Review key sections
- [ ] Note timestamps for editing

---

## 📝 Script Prompts (Printed Guide)

### Short Version (Print This)

```
[0:00] HOOK: "Forward emails to Discord for FREE"
[0:30] PROBLEM: "Zapier costs $50/month"
[1:00] SOLUTION: "Meet Ravenclaw"
[1:30] SETUP: Terminal commands
[3:00] CONFIG: .env file
[3:30] DEMO: Send test email
[4:30] CTA: "Star the repo!"
```

### Long Version (Print This)

```
[0:00] INTRO: Who I am, what this channel is about
[0:45] PROBLEM: Why paid tools aren't worth it
[1:30] SOLUTION: Ravenclaw architecture
[2:30] SETUP: Clone + install
[4:00] CONFIG: Environment variables explained
[5:00] LIVE DEMO: Full workflow
[8:00] FEATURES: API, stability, memory management
[9:30] ROADMAP: What's coming next
[10:00] CONTRIBUTE: How to help
[10:30] CTA: Star, fork, subscribe
```

---

## 📦 Equipment Recommendations (Pakistan)

| Item | Where to Buy | Approx. Price |
|------|--------------|---------------|
| **Webcam Logitech C920** | Daraz, Amazon | PKR 8,000-10,000 |
| **USB Microphone** | Daraz, Local shops | PKR 2,000-5,000 |
| **Ring Light 12"** | Daraz, Amazon | PKR 1,500-3,000 |
| **Pop Filter** | Daraz | PKR 500-1,000 |
| **Boom Arm** | Daraz | PKR 1,000-2,000 |
| **Headphones (Audio-Technica)** | Amazon | PKR 5,000-8,000 |

---

## ✅ Final Checklist (Recording Day)

### Technical

- [ ] Computer restarted
- [ ] OBS Studio launched
- [ ] All scenes configured
- [ ] Audio tested
- [ ] Recording test passed
- [ ] 10GB+ free disk space
- [ ] Backup drive connected (optional)

### Environment

- [ ] Room quiet
- [ ] Phone on DND
- [ ] No interruptions planned
- [ ] Lighting set up
- [ ] Webcam positioned

### Personal

- [ ] Hydrated
- [ ] Good posture
- [ ] Script printed/read
- [ ] Water nearby
- [ ] Not hungry (eat before)

---

## 🎯 Post-Recording To-Do

1. **Upload to YouTube** (unlisted first)
2. **Add chapters** with timestamps
3. **Write description** with keywords
4. **Design thumbnail**
5. **Schedule publish** (Saturday 7 PM?)
6. **Share on social media**

---

**Created by:** Ibrahim Qureshi
**Repository:** https://github.com/ibrahimq21/ravenclaw
