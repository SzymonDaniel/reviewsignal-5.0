# DOMAIN CONFIGURATION GUIDE
**Configuring reviewsignal.ai domains for Framer + n8n**

---

## 🎯 GOAL

**Current situation:**
- `reviewsignal.ai` → points to n8n (WRONG!)
- `n8n.reviewsignal.ai` → points to n8n (CORRECT!)

**Target situation:**
- `reviewsignal.ai` → Framer landing page ✅
- `n8n.reviewsignal.ai` → n8n workflow (stays as-is) ✅

---

## 📋 PREREQUISITES

Before starting, you need:
- [x] Framer project "Feature (copy)" ready
- [x] Framer project published (at least once)
- [x] Access to Cloudflare DNS (for reviewsignal.ai)
- [x] SSH access to server (35.246.214.156)

---

## 🚀 STEP-BY-STEP GUIDE

---

### PART 1: PUBLISH FRAMER TO CUSTOM DOMAIN

#### Step 1.1: Get Framer CNAME target

1. Open your Framer project "Feature (copy)"
2. Click **"Publish"** button (top-right)
3. Click **"Add Custom Domain"**
4. Enter domain: `reviewsignal.ai`
5. Framer will show you a **CNAME target** like:
   ```
   Target: cname.framer.app
   ```
   or something similar (e.g., `d3e81b1c.framerio.com`)

6. **COPY THIS CNAME TARGET** - you'll need it next!

**Screenshot help:** Look for text like "Point your DNS to: _______"

---

#### Step 1.2: Update Cloudflare DNS

1. Go to **Cloudflare dashboard**: https://dash.cloudflare.com
2. Select domain: **reviewsignal.ai**
3. Go to **DNS** tab (left sidebar)

4. **Find existing record for `reviewsignal.ai` (@ record):**
   - Type: A or CNAME
   - Name: @ (or reviewsignal.ai)
   - Delete it or modify it

5. **Add/Update CNAME record:**
   ```
   Type:    CNAME
   Name:    @
   Target:  [paste CNAME from Framer - e.g., cname.framer.app]
   Proxy:   ✅ Proxied (orange cloud)
   TTL:     Auto
   ```

6. **Click "Save"**

7. **Repeat for www subdomain:**
   ```
   Type:    CNAME
   Name:    www
   Target:  [same CNAME from Framer]
   Proxy:   ✅ Proxied (orange cloud)
   TTL:     Auto
   ```

8. **Click "Save"**

---

#### Step 1.3: Verify DNS propagation

Wait 2-5 minutes, then test:

```bash
# Check @ record
dig reviewsignal.ai CNAME +short

# Check www record
dig www.reviewsignal.ai CNAME +short
```

Should show Framer's CNAME target.

**Or use online tool:** https://dnschecker.org

---

#### Step 1.4: Confirm in Framer

1. Go back to Framer
2. In "Custom Domain" settings, it should show:
   ```
   ✅ reviewsignal.ai - Connected
   ```

3. Click **"Publish"** one more time
4. Visit https://reviewsignal.ai
5. **Your Framer landing page should load!** 🎉

---

### PART 2: DISABLE NGINX CONFIG FOR reviewsignal.ai

Since reviewsignal.ai now points to Framer (external), we don't need nginx on the server to handle it anymore.

#### Step 2.1: SSH to server

```bash
ssh info_betsim@35.246.214.156
cd ~
```

#### Step 2.2: Disable nginx config for reviewsignal.ai

```bash
# Disable the config (remove symlink)
sudo rm /etc/nginx/sites-enabled/reviewsignal
sudo rm /etc/nginx/sites-enabled/02-reviewsignal

# Test nginx config
sudo nginx -t

# If OK, reload nginx
sudo systemctl reload nginx
```

**What this does:**
- Removes nginx routing for reviewsignal.ai
- n8n.reviewsignal.ai still works (different config file)
- Server no longer handles reviewsignal.ai requests

---

### PART 3: VERIFY n8n.reviewsignal.ai STILL WORKS

#### Step 3.1: Test n8n subdomain

```bash
# Test from server
curl -I https://n8n.reviewsignal.ai

# Or visit in browser:
# https://n8n.reviewsignal.ai
```

**Should work!** n8n interface loads.

#### Step 3.2: If n8n.reviewsignal.ai doesn't work

Check DNS:
```bash
dig n8n.reviewsignal.ai A +short
```

Should show Cloudflare IPs (188.114.x.x) or server IP (34.159.18.55).

**If not working:**

1. Go to Cloudflare DNS
2. Make sure n8n.reviewsignal.ai has a record:
   ```
   Type:    A
   Name:    n8n
   Target:  34.159.18.55 (server IP)
   Proxy:   ❌ DNS only (gray cloud) - or ✅ Proxied (orange) both work
   TTL:     Auto
   ```

3. Nginx config on server handles the routing (already set up)

---

## ✅ VERIFICATION CHECKLIST

After completing all steps:

### Test reviewsignal.ai (Framer landing page)
- [ ] Visit https://reviewsignal.ai - loads Framer page
- [ ] Visit https://www.reviewsignal.ai - loads Framer page
- [ ] Test on mobile
- [ ] All buttons work
- [ ] No errors in browser console

### Test n8n.reviewsignal.ai (n8n workflow)
- [ ] Visit https://n8n.reviewsignal.ai - loads n8n
- [ ] Can log in to n8n
- [ ] Workflows still run
- [ ] Webhooks still work

### Test other services (should be unaffected)
- [ ] Lead Receiver API: http://35.246.214.156:8001/health
- [ ] Echo Engine API: http://35.246.214.156:8002/health
- [ ] ReviewSignal API: http://35.246.214.156:8000/docs

---

## 🚨 TROUBLESHOOTING

### Problem: reviewsignal.ai shows "This site can't be reached"
**Cause:** DNS not updated yet or wrong CNAME
**Solution:**
1. Check Cloudflare DNS - CNAME correct?
2. Wait 5-10 minutes for propagation
3. Clear browser cache (Cmd+Shift+R / Ctrl+Shift+R)

### Problem: reviewsignal.ai shows "Error 1000" or "Error 1001"
**Cause:** Cloudflare can't reach Framer's servers
**Solution:**
1. In Cloudflare, make sure Proxy is ON (orange cloud) for @ and www
2. In Framer, make sure domain is verified
3. Wait a few minutes and try again

### Problem: n8n.reviewsignal.ai stopped working
**Cause:** You accidentally disabled wrong nginx config
**Solution:**
```bash
# Re-enable n8n config
sudo ln -s /etc/nginx/sites-available/n8n.reviewsignal.ai /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Problem: reviewsignal.ai shows old n8n interface
**Cause:** Browser cache or DNS cache
**Solution:**
1. Hard refresh: Cmd+Shift+R (Mac) or Ctrl+Shift+R (Windows)
2. Clear browser cache completely
3. Try incognito/private window
4. Try different browser
5. Wait 10-15 minutes for DNS propagation

### Problem: SSL certificate errors
**Cause:** Cloudflare or Framer SSL not ready
**Solution:**
1. In Cloudflare, SSL/TLS mode should be "Full" or "Full (strict)"
2. Wait 10-15 minutes for SSL to provision
3. In Framer, SSL is automatic - just wait

---

## 📊 FINAL ARCHITECTURE

After all changes:

```
┌─────────────────────────────────────────────────────────────┐
│                     CLOUDFLARE DNS                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  reviewsignal.ai (@)     ──► CNAME ──► Framer Hosting     │
│  www.reviewsignal.ai     ──► CNAME ──► Framer Hosting     │
│                                                             │
│  n8n.reviewsignal.ai     ──► A ──► 34.159.18.55 (Server)  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                              ┌──────────────┐
                              │    SERVER    │
                              │ (GCP VM)     │
                              ├──────────────┤
                              │              │
                              │ NGINX        │
                              │   ├─► n8n (5678)
                              │   ├─► API (8000)
                              │   └─► Lead (8001)
                              │              │
                              └──────────────┘
```

**Traffic flow:**
1. User visits `reviewsignal.ai` → Cloudflare → Framer servers (landing page)
2. User visits `n8n.reviewsignal.ai` → Cloudflare → Server → nginx → n8n container

---

## 📝 SUMMARY

**What changed:**
- ✅ reviewsignal.ai DNS now points to Framer (CNAME)
- ✅ Server nginx no longer handles reviewsignal.ai
- ✅ n8n.reviewsignal.ai still works (unchanged)

**What stayed the same:**
- ✅ n8n.reviewsignal.ai routing (nginx + docker)
- ✅ All API services (8000, 8001, 8002)
- ✅ PostgreSQL, Redis, all backend services

**Result:**
- Professional Framer landing page on main domain
- n8n workflow automation on subdomain
- Clean separation of concerns

---

## 🎉 YOU'RE DONE!

Once all checks pass:
- Main site: https://reviewsignal.ai (Framer landing)
- Workflows: https://n8n.reviewsignal.ai (n8n interface)
- Everything works beautifully! 🚀

---

**Need help?** Check Framer docs: https://www.framer.com/docs/custom-domains/
**Last updated:** 2026-01-31
