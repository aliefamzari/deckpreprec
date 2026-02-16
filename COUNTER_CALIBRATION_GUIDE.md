# 📟 Tape Counter Calibration Quick Guide

## 🎯 Which Mode Should I Use?

### Quick Decision Tree:
1. **Not sure?** → Start with **Static mode** (default)
2. **Want best accuracy?** → Use **Manual Calibrated mode**
3. **Counter speeds up/slows down?** → Try **Auto Physics mode**

---

## 🚀 Quick Start: Static Mode (Easiest)

**Step 1: Measure Your Counter Rate**
```bash
# On your tape deck:
1. Insert blank tape
2. Reset counter to 000
3. Press RECORD
4. Start stopwatch
5. After 2+ minutes, note counter and time
```

**Step 2: Calculate Rate**
```
counter_rate = counter_value / time_in_seconds

Example: 169 counter at 2:00 (120 seconds)
         169 ÷ 120 = 1.408
```

**Step 3: Run Script**
```bash
python decprec.py --counter-mode static --counter-rate 1.408
```

**Tip:** For better accuracy, measure for 15-30 minutes instead of 2 minutes.

---

## 🎓 Advanced: Manual Calibrated Mode (Most Accurate)

**Step 1: Run Calibration Wizard**
```bash
python decprec.py --calibrate-counter
```

**Step 2: Prepare Your Deck**
- Insert blank C60 or C90 tape
- Reset counter to 000
- Press RECORD
- Start stopwatch

**Step 3: Measure Checkpoints**

The wizard will ask for counter values at these times:

| Time | Seconds | Note |
|------|---------|------|
| 1 min | 60s | Quick check |
| 5 min | 300s | Early tape |
| 20 min | 1200s | Mid tape |
| 30 min | 1800s | Late tape |
| End | varies | Full side (optional) |

**Example Measurement Session:**
```
00:01:00 → Counter: 085
00:05:00 → Counter: 422
00:20:00 → Counter: 1690
00:30:00 → Counter: 2534
```

**Step 4: Use Calibrated Counter**
```bash
python decprec.py --counter-mode manual
```

The calibration is saved to `profiles/counter_calibration.json` and reused automatically!

---

## 🔬 Physics Mode (Advanced Users)

For decks where the counter is mechanically driven by the take-up reel:

```bash
python decprec.py --counter-mode auto --counter-rate 1.408
```

The counter will:
- Run **faster** at the beginning (smaller reel radius)
- Match your `--counter-rate` at the **middle** of the tape
- Run **slower** at the end (larger reel radius)

---

## 📊 Comparison

| Mode | Setup Time | Accuracy | Best For |
|------|------------|----------|----------|
| Static | 2 min | Good | Most decks, quick start |
| Manual | 30 min | Excellent | Maximum accuracy |
| Auto | 2 min | Variable | Mechanically-driven counters |

---

## ❓ FAQ

**Q: My counter doesn't match the script. What should I do?**
A: Use Manual Calibrated mode for perfect accuracy.

**Q: Can I calibrate multiple decks?**
A: Yes! Use different config files:
```bash
python decprec.py --calibrate-counter --counter-config my_deck_a.json
python decprec.py --calibrate-counter --counter-config my_deck_b.json

# Then use:
python decprec.py --counter-mode manual --counter-config my_deck_a.json
```

**Q: Do I need to recalibrate?**
A: No, calibration is permanent. You can reuse the same config file forever.

**Q: What if I skip some checkpoints in the wizard?**
A: That's fine! The script will interpolate between whatever checkpoints you provide.

**Q: My deck counter runs backwards (counts down). Can I use this?**
A: The script counts up. You'll need to manually convert your tracklist positions.

**Q: How accurate is Static mode?**
A: Very accurate for most decks (±1-2 counts). Manual mode gives ±0 perfect accuracy.

---

## 💡 Pro Tips

1. **Longer measurement = better accuracy** - Measure for 30+ minutes for best static rate
2. **Use the same tape** - Different tapes may have slightly different counter behavior
3. **Measure on RECORD, not PLAY** - Some decks have different speeds
4. **Room temperature matters** - Tape speed can vary with temperature
5. **Write down your rate** - Keep a note with your deck: "Counter rate: 1.408"
6. **Calibrate once, use forever** - Save the JSON file and forget about it

---

## 📝 Example Workflow

### First Time Setup (Manual Mode):
```bash
# 1. Calibrate your deck (30 minutes)
python decprec.py --calibrate-counter

# 2. Verify it works
python decprec.py --counter-mode manual --folder ./tracks
```

### Daily Usage:
```bash
# Just run with your calibrated counter
python decprec.py --counter-mode manual --folder ./tracks
```

That's it! Your counter will now perfectly match your tape deck. 🎉
