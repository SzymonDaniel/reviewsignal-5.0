# CLOUDFLARE DNS - DOKŁADNE WARTOŚCI DO WPISANIA
**Ostatnia aktualizacja:** 2026-01-31 11:35 UTC

---

## ✅ CO JUŻ ZROBIŁEM (SERWER):

✅ **Nginx config wyczyszczony:**
- Usunięto: `/etc/nginx/sites-enabled/reviewsignal`
- Usunięto: `/etc/nginx/sites-enabled/02-reviewsignal`
- Usunięto duplikaty: `01-n8n`, `n8n`
- **Zostało:** tylko `n8n.reviewsignal.ai` (poprawne)

✅ **Nginx przeładowany i działa:**
```
nginx: configuration file /etc/nginx/nginx.conf test is successful
Active: active (running)
```

✅ **n8n działa poprawnie:**
- Container: Up 16 hours
- Port 5678: Responding OK
- Config: `/etc/nginx/sites-enabled/n8n.reviewsignal.ai`

---

## 📋 CO MUSISZ ZROBIĆ W CLOUDFLARE:

### KROK 1: Przygotuj CNAME z Framer

**NAJPIERW:** Otwórz Framer i opublikuj projekt:
1. Otwórz "Feature (copy)" w Framer
2. Kliknij **"Publish"**
3. Kliknij **"Add Custom Domain"**
4. Wpisz: `reviewsignal.ai`
5. **Skopiuj CNAME target** (będzie coś jak `cname.framer.app` lub `xyz.framer.site`)

**⚠️ ZATRZYMAJ SIĘ TUTAJ!** Skopiuj ten CNAME - będzie potrzebny w następnym kroku.

---

### KROK 2: Zaloguj się do Cloudflare

1. Idź do: https://dash.cloudflare.com
2. Zaloguj się
3. Wybierz domenę: **reviewsignal.ai**
4. Kliknij **DNS** w menu bocznym (po lewej)

---

### KROK 3: Zaktualizuj rekordy DNS

**UWAGA:** Obecne recordy wskazują na Cloudflare proxy (188.114.x.x). Zmienimy je na CNAME do Frameru.

#### 3.1 Record dla @ (główna domena)

**Znajdź rekord:**
- Type: A lub AAAA
- Name: `@` (lub `reviewsignal.ai`)

**Usuń lub edytuj na:**
```
Type:    CNAME
Name:    @
Target:  [WKLEJ TUTAJ CNAME Z FRAMER - np. cname.framer.app]
Proxy:   ✅ Proxied (pomarańczowa chmurka)
TTL:     Auto
```

**Kliknij "Save"**

---

#### 3.2 Record dla www

**Znajdź rekord:**
- Type: A lub AAAA lub CNAME
- Name: `www`

**Usuń lub edytuj na:**
```
Type:    CNAME
Name:    www
Target:  [TEN SAM CNAME Z FRAMER]
Proxy:   ✅ Proxied (pomarańczowa chmurka)
TTL:     Auto
```

**Kliknij "Save"**

---

#### 3.3 Record dla n8n (NIE ZMIENIAJ!)

**Sprawdź że istnieje:**
```
Type:    A
Name:    n8n
Target:  34.159.18.55
Proxy:   ✅ Proxied (pomarańczowa) LUB ❌ DNS only (szara) - oba działają
TTL:     Auto
```

**⚠️ NIE RUSZAJ tego rekordu!** n8n.reviewsignal.ai już działa poprawnie.

---

### KROK 4: Sprawdź SSL/TLS settings (opcjonalnie)

1. W Cloudflare, kliknij **SSL/TLS** (menu boczne)
2. Sprawdź że mode to: **Full** lub **Full (strict)**
3. Jeśli nie, zmień na **Full**

---

## 🧪 TEST PO ZMIANACH

Poczekaj **5-10 minut** na propagację DNS, potem sprawdź:

### Test 1: reviewsignal.ai (Framer)
```bash
# Terminal
curl -I https://reviewsignal.ai

# Lub otwórz w przeglądarce:
https://reviewsignal.ai
```

**Oczekiwany rezultat:**
- Ładuje się Framer landing page
- Widzisz "ReviewSignal" jako nagłówek
- NIE widzisz n8n interface

**Jeśli widzisz stary n8n:**
- Hard refresh: Cmd+Shift+R (Mac) lub Ctrl+Shift+R (Windows)
- Poczekaj jeszcze 5 minut (DNS propagacja)
- Spróbuj w trybie incognito

---

### Test 2: n8n.reviewsignal.ai (bez zmian)
```bash
# Terminal
curl -I https://n8n.reviewsignal.ai

# Lub otwórz w przeglądarce:
https://n8n.reviewsignal.ai
```

**Oczekiwany rezultat:**
- Ładuje się n8n interface (jak zawsze)
- Możesz się zalogować
- Workflows działają

**Jeśli NIE działa:**
- Sprawdź DNS: `dig n8n.reviewsignal.ai +short`
- Powinno pokazać: 188.114.x.x (Cloudflare) lub 34.159.18.55 (serwer)

---

## 📊 PODSUMOWANIE ZMIAN DNS

### PRZED:
```
reviewsignal.ai       → Cloudflare proxy → Serwer → nginx → n8n (BŁĄD!)
www.reviewsignal.ai   → Cloudflare proxy → Serwer → nginx → n8n (BŁĄD!)
n8n.reviewsignal.ai   → Cloudflare proxy → Serwer → nginx → n8n (OK)
```

### PO:
```
reviewsignal.ai       → Cloudflare proxy → Framer hosting (OK!)
www.reviewsignal.ai   → Cloudflare proxy → Framer hosting (OK!)
n8n.reviewsignal.ai   → Cloudflare proxy → Serwer → nginx → n8n (OK!)
```

---

## 🎯 CHECKLIST

- [ ] Framer: Opublikowano "Feature (copy)"
- [ ] Framer: Dodano custom domain "reviewsignal.ai"
- [ ] Framer: Skopiowano CNAME target
- [ ] Cloudflare: Zalogowano
- [ ] Cloudflare: Zaktualizowano @ record (CNAME → Framer)
- [ ] Cloudflare: Zaktualizowano www record (CNAME → Framer)
- [ ] Cloudflare: Zostawiono n8n record bez zmian
- [ ] Poczekano 5-10 minut
- [ ] Test: reviewsignal.ai ładuje Framer ✅
- [ ] Test: n8n.reviewsignal.ai działa ✅
- [ ] Test: Mobile responsive ✅

---

## 🚨 TROUBLESHOOTING

### Problem: "This site can't be reached"
**Przyczyna:** DNS nie zaktualizował się jeszcze
**Rozwiązanie:**
- Poczekaj 10-15 minut
- Clear browser cache
- Użyj https://dnschecker.org aby sprawdzić propagację

### Problem: Widzę stary n8n zamiast Framer na reviewsignal.ai
**Przyczyna:** Browser cache lub DNS cache
**Rozwiązanie:**
```bash
# 1. Hard refresh
Cmd+Shift+R (Mac) lub Ctrl+Shift+R (Windows)

# 2. Clear DNS cache (Mac)
sudo dscacheutil -flushcache

# 3. Clear DNS cache (Windows)
ipconfig /flushdns

# 4. Sprawdź DNS
dig reviewsignal.ai CNAME +short
# Powinno pokazać: Framer CNAME target
```

### Problem: n8n.reviewsignal.ai przestał działać
**Przyczyna:** Przypadkowo zmieniłeś zły rekord
**Rozwiązanie:**
```
Cloudflare DNS → Sprawdź rekord dla "n8n":
Type:    A
Name:    n8n
Target:  34.159.18.55
Save
```

### Problem: SSL certificate error
**Przyczyna:** Cloudflare SSL mode niepoprawny
**Rozwiązanie:**
- Cloudflare → SSL/TLS → Mode: **Full** (nie Flexible!)
- Poczekaj 5 minut

---

## 📞 POTRZEBUJESZ POMOCY?

**Sprawdź obecne DNS:**
```bash
dig reviewsignal.ai +short
dig www.reviewsignal.ai +short
dig n8n.reviewsignal.ai +short
```

**Test nginx na serwerze:**
```bash
ssh info_betsim@34.159.18.55
sudo nginx -t
sudo systemctl status nginx
```

**Test n8n:**
```bash
curl -I http://localhost:5678
docker ps | grep n8n
```

---

## ✅ GOTOWE!

Po wykonaniu tych kroków:
- ✅ https://reviewsignal.ai → Profesjonalna landing page (Framer)
- ✅ https://n8n.reviewsignal.ai → n8n workflows (bez zmian)
- ✅ Serwer nginx skonfigurowany poprawnie
- ✅ Wszystko działa! 🚀

---

**Serwer:** Skonfigurowany ✅
**DNS:** Czeka na Twoje zmiany w Cloudflare (5 minut)
**Status:** Gotowe do uruchomienia!
