# Ravenclaw YouTube Demo Video Plan

## 🎯 Video Goal
Drive GitHub stars, clones, and community contributions by showcasing Ravenclaw's value proposition.

---

## 📹 Video Options

### Option A: Short Form (5-7 minutes)
- Quick setup demo
- Fast-paced
- TikTok/Reels/Shorts friendly

### Option B: Long Form (10-15 minutes)
- Detailed walkthrough
- Explain features
- Code walkthrough
- More educational

---

## 📅 Recording Schedule

| Date | Day | Time | Activity |
|------|-----|------|----------|
| **Feb 14, 2026** | Saturday | 4:00 PM - 6:00 PM | **Primary Recording Slot** |
| Feb 15, 2026 | Sunday | 4:00 PM - 6:00 PM | Backup Slot (if needed) |
| Feb 16, 2026 | Monday | 7:00 PM - 9:00 PM | Evening Alternative |

**Recording Duration:** 2 hours (includes breaks, setup, retakes)

---

## 🎬 Script: Short Form (5 Minutes)

### Hook (0:00-0:30)
```
"How would you like to forward emails to Discord for FREE?
No Zapier. No monthly fees. Just open source."
```

### Problem (0:30-1:00)
```
"Zapier costs $50/month for this. IFTTT has limits.
But you can build your own in 5 minutes."
```

### Solution Reveal (1:00-1:30)
```
"Meet Ravenclaw — an email-to-Discord bridge.
POP3 emails → Discord webhooks. Simple."
```

### Setup Demo (1:30-3:00)
```
1. git clone https://github.com/ibrahimq21/ravenclaw.git
2. pip install -r requirements.txt
3. cp .env.example .env
4. Edit config (show screen)
```

### Configuration (3:00-3:30)
```
Add your:
- Email credentials
- Discord webhook URL
- Domain filter
```

### Live Demo (3:30-4:30)
```
1. Run: python ravenclaw.py
2. Send test email
3. Show it appearing in Discord channel
```

### CTA (4:30-5:00)
```
"Star the repo if you found this useful.
Fork it and add Slack/Telegram support.
Contributions welcome!"
```

---

## 🎬 Script: Long Form (10 Minutes)

### Outline (10 minutes total)

| Time | Segment | Details |
|------|---------|---------|
| 0:00-0:45 | Hook | "Free email notifications for Discord" |
| 0:45-1:30 | Problem | "Why paid tools aren't worth it" |
| 1:30-2:30 | Solution | "Ravenclaw architecture overview" |
| 2:30-4:00 | Setup | Terminal walkthrough |
| 4:00-5:00 | Config | .env file explained |
| 5:00-6:30 | Demo | Live email-to-Discord |
| 6:30-7:30 | Features | API, stability, memory management |
| 7:30-8:30 | Roadmap | Slack, Telegram, WhatsApp |
| 8:30-9:30 | Contribution | How to contribute |
| 9:30-10:00 | CTA | Star, fork, subscribe |

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

## 📝 Description Template (Long Form)

```markdown
📧 Forward emails to Discord for FREE with Ravenclaw!

In this tutorial, I show you how to set up Ravenclaw — an open-source email bridge that sends POP3 emails directly to your Discord channels.

⏱️ TIMESTAMPS:
0:00 - Introduction
1:30 - Why Ravenclaw?
2:30 - Architecture Overview
4:00 - Installation
6:00 - Configuration
8:00 - Live Demo
12:00 - Features Deep Dive
15:00 - Roadmap & Contributing
18:00 - Conclusion

🔗 LINKS:
• Ravenclaw Repo: https://github.com/ibrahimq21/ravenclaw
• My GitHub: https://github.com/ibrahimq21
• Connect on Discord: [your server link]

📌 KEYWORDS:
email to discord, discord webhook, email notification, python automation,
pop3 email, smtp, self-hosted, open source, free automation, zapier alternative

🛠️ TOOLS USED:
• OBS Studio (recording)
• Ravenclaw (the tool!)
• Discord (notifications)

💬 QUESTIONS?
Drop a comment below!

---

📺 SUBSCRIBE for more open-source tutorials!
🔔 Hit the bell to never miss an update
```

---

## 🎯 YouTube SEO Tips

### Title (Include Keywords)
- "Forward Emails to Discord — Free Open Source Tool"
- "Email to Discord Bridge in 5 Minutes"
- "Build a Discord Email Notification System [Free]"

### Description (Include Keywords Naturally)
- First 2 lines most important (shown in search)
- Add 10-15 relevant hashtags at bottom
- Include timestamps for engagement

### Tags (Max 15)
```
email to discord, discord webhook, python, pop3, smtp,
email automation, discord bot, open source, self-hosted,
free automation, zapier alternative, email notifications,
github, python automation, webhook tutorial
```

### Thumbnail Text
- "FREE"
- "Email → Discord"
- "5 Minute Setup"
- Raven logo + Discord logo

---

## 📊 Success Metrics

| Metric | Goal (30 days) |
|--------|---------------|
| Views | 1,000 |
| Likes | 100 |
| Comments | 20 |
| Subscribers | 50 |
| GitHub Stars | 50 |
| GitHub Clones | 100 |

---

## 🚀 Promotion Strategy

### Before Launch
- [ ] Post on Reddit r/programming
- [ ] Share on Hacker News (when you have URL)
- [ ] Post on LinkedIn
- [ ] Share in Discord servers (dev communities)
- [ ] Tweet with video link

### After Launch
- [ ] Respond to all comments
- [ ] Add video to README
- [ ] Submit to AlternativeTo (alternativeto.net)
- [ ] Share in Python Discord servers
- [ ] Cross-post on Dev.to

---

## 🎨 Visual Checklist

### Before Recording
- [ ] Clean desktop background
- [ ] Install OBS Studio
- [ ] Test microphone audio
- [ ] Prepare terminal with syntax highlighting
- [ ] Have Discord open in browser
- [ ] Draft email ready to send

### Graphics Needed
- [ ] YouTube thumbnail (1280x720)
- [ ] End screen template
- [ ] Channel subscribe animation
- [ ] Project logo animation

---

**Created by:** Ibrahim Qureshi
**Repository:** https://github.com/ibrahimq21/ravenclaw
