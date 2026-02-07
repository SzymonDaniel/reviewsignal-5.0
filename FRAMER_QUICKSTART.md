# FRAMER + DOMAINS - QUICK START
**TL;DR: Fast track to get ReviewSignal landing page live**

---

## ⚡ 15-MINUTE CHECKLIST

### 1. Edit Framer (10 min)
- [ ] Open "Feature (copy)" in Framer
- [ ] Replace hero: "ReviewSignal" + "AI-Powered Review Intelligence"
- [ ] Update 6 features (copy from FRAMER_CONTENT_PACK.md)
- [ ] Update 4 pricing plans (Trial, Starter, Pro, Enterprise)
- [ ] Update footer
- [ ] Preview & test

### 2. Publish to Domain (3 min)
- [ ] Click "Publish" in Framer
- [ ] Add custom domain: `reviewsignal.ai`
- [ ] Copy CNAME target (e.g., `cname.framer.app`)

### 3. Update DNS (2 min)
- [ ] Cloudflare → DNS tab
- [ ] Update `@` record: CNAME → [Framer target]
- [ ] Update `www` record: CNAME → [Framer target]
- [ ] Save

### 4. Disable Server Routing (1 min)
```bash
ssh info_betsim@35.246.214.156
sudo rm /etc/nginx/sites-enabled/reviewsignal
sudo rm /etc/nginx/sites-enabled/02-reviewsignal
sudo nginx -t && sudo systemctl reload nginx
```

### 5. Test Everything (2 min)
- [ ] Visit https://reviewsignal.ai (Framer page loads)
- [ ] Visit https://n8n.reviewsignal.ai (n8n still works)
- [ ] Test on mobile

**DONE!** 🎉

---

## 📁 FILES YOU NEED

| File | Purpose |
|------|---------|
| **FRAMER_CONTENT_PACK.md** | All text for Framer (copy-paste ready) |
| **FRAMER_INSTRUCTIONS.md** | Step-by-step Framer editing guide |
| **DOMAIN_CONFIGURATION.md** | Complete domain setup guide |
| **FRAMER_QUICKSTART.md** | This file (quick reference) |

---

## 🎯 KEY POINTS

### DO:
- ✅ Keep template colors (don't change!)
- ✅ Update ALL text to ReviewSignal branding
- ✅ Test on mobile AND desktop
- ✅ Verify n8n.reviewsignal.ai still works after DNS change

### DON'T:
- ❌ Change template colors
- ❌ Skip mobile testing
- ❌ Forget to disable nginx config on server
- ❌ Touch n8n.reviewsignal.ai DNS (it's correct!)

---

## 🚨 COMMON MISTAKES

1. **Forgetting to publish in Framer first**
   → Always publish BEFORE adding custom domain

2. **Wrong CNAME in Cloudflare**
   → Copy exact CNAME from Framer, don't guess

3. **Keeping nginx config active**
   → Must disable reviewsignal.ai nginx config on server

4. **Not waiting for DNS propagation**
   → Wait 5-10 minutes after DNS changes

5. **Breaking n8n.reviewsignal.ai**
   → ONLY disable reviewsignal.ai nginx config
   → KEEP n8n.reviewsignal.ai config enabled

---

## 📞 QUICK HELP

**Framer not publishing?**
→ Make sure you clicked "Publish" button (top-right)

**DNS not updating?**
→ Wait 10 minutes, clear browser cache, try incognito

**n8n.reviewsignal.ai broken?**
→ You disabled wrong config - re-enable it:
```bash
sudo ln -s /etc/nginx/sites-available/n8n.reviewsignal.ai /etc/nginx/sites-enabled/
sudo systemctl reload nginx
```

**reviewsignal.ai shows old n8n?**
→ DNS not updated yet OR browser cache - hard refresh (Cmd+Shift+R)

---

## ✅ SUCCESS CRITERIA

You're done when:
- ✅ https://reviewsignal.ai loads Framer landing page
- ✅ Page looks professional (no placeholder text)
- ✅ All buttons work
- ✅ Mobile responsive
- ✅ https://n8n.reviewsignal.ai still loads n8n
- ✅ No SSL errors
- ✅ Page loads in <2 seconds

---

**Total time:** ~20 minutes
**Difficulty:** Easy
**Result:** Professional landing page live! 🚀
