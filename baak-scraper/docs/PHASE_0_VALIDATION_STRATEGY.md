# Phase 0: BAAK Source Validation & Deployment Strategy

**Status:** Planning  
**Date:** October 25, 2026  
**Blocker Level:** Before Telegram integration or Go API deployment

---

## Current State

### ✅ Completed (baak-scraper/)
- [x] Core parser + converter (40 tests passing)
- [x] Fixture-based testing
- [x] CLI + JSON API contract
- [x] Error handling & graceful degradation

### ❌ Blocking Issues
1. **Cloudflare Bypass** — curl-cffi `impersonate` not configured
2. **Live BAAK Access** — Not tested against actual baak.gunadarma.ac.id
3. **Verified Snapshot** — Need real data from BAAK to bootstrap

### ⚠️ Existing Telegram System (telegram_personal_ai/)
- **Status:** Unchanged ✅
- **Entry:** `main.py` → `TelegramAssistantApp`
- **Handlers:** `telegram_app.py`
  - `on_incoming()` — message received
  - `on_outgoing()` → `service.manual_reply()` — user replied manually
  - `on_edited()`, `on_deleted()` — maintenance
- **Service:** `app/service.py`
  - Auto-reply logic
  - RAG + LLM integration
  - Storage layer

---

## Phase 0 Gate Criteria

Before proceeding to Phase 2 (Go API) or Phase 3 (Telegram integration):

### 1. Cloudflare Bypass Validation
```
Goal: Confirm curl-cffi works from target environment (Termux/VPS)

Task:
  a) From Windows: Test curl-cffi with Chrome 120 fingerprint
  b) From Termux: Install libcurl + test
  c) Capture response headers + HTML structure
  d) Document: What works? What fails? Any Cloudflare blocks?

Success Criteria:
  ✓ GET https://baak.gunadarma.ac.id/ returns 200 (not CF error)
  ✓ HTML contains jadwal table
  ✓ No "Challenge", "cf_clearance" in response

Fallback:
  ✓ If blocked: Use verified_snapshot mode (no live fetch)
```

### 2. HTML Structure Validation
```
Goal: Verify parser extracts correct data from real BAAK

Task:
  a) Save real HTML from baak.gunadarma.ac.id
  b) Run parser against real data
  c) Spot-check 5-10 jadwal entries manually
  d) Compare: fixture vs real (field order, content, format)

Success Criteria:
  ✓ Parser extracts all 7 fields correctly
  ✓ Time conversion matches BAAK notation
  ✓ N/A fields handled properly
  ✓ No parsing errors or crashes

Result: baak_real_sample.html in tests/fixtures/
```

### 3. Snapshot Bootstrap
```
Goal: Create verified snapshot for fallback

Task:
  a) Fetch real jadwal for 1-2 popular classes (e.g., 3KA01, 3KB02)
  b) Save to data/snapshots/PTA_2026_2027.json
  c) Add metadata: source_url, fetched_at, semester
  d) Verify JSON schema matches contract

Success Criteria:
  ✓ Snapshot valid JSON
  ✓ Contains ≥20 jadwal entries
  ✓ Semester & date accurate
  ✓ All 7 fields present

Result: data/snapshots/PTA_2026_2027.json
```

### 4. Documentation
```
Goal: Record findings for future reference

File: docs/baak-source-validation.md

Contents:
  ✓ URL tested + date
  ✓ Cloudflare response (blocked? fingerprint worked?)
  ✓ HTML structure (table format, field order)
  ✓ Parser success rate
  ✓ Known limitations
  ✓ Recommendations for VPS deploy
  ✓ curl-cffi setup steps (if needed)
```

---

## Strategy: No Breaking Changes to Telegram

### Isolation Principle
- **baak-scraper/** remains **standalone Python package**
- **telegram_personal_ai/** unchanged in this phase
- **No imports** from one to other (yet)

### Integration Point (Phase 3)
When ready to add `/jadwal` to Telegram:
```python
# app/baak_client.py (NEW)
from baak_scraper.scraper.parser import BAAKParser
from baak_scraper.scraper.client import BAAKClient

# telegram_app.py: Add handler (after validation passes)
async def on_message_jadwal(event):
    # Only process owner messages in Saved Messages
    # Call BAAKClient → parse → respond
```

**Key:** This is deferred to Phase 3 after Phase 0 validation passes.

---

## Recommended Execution Order

### Step 1: Setup curl-cffi (Termux/local)
```bash
# Termux
pkg install libcurl openssl

# Windows / development
# Usually works out-of-box; if not:
pip install --force-reinstall --no-cache-dir curl-cffi
```

### Step 2: Test Live Access
```bash
cd baak-scraper
python -c "
from scraper.client import BAAKClient
client = BAAKClient(use_curl_cffi=True)
html = client.get('/')
print(f'Status: {len(html)} bytes received')
print('Cloudflare blocked?' in html)
"
```

### Step 3: Validate Parser
```bash
# Save real HTML
python -c "
from scraper.client import BAAKClient
client = BAAKClient()
html = client.get('/')
with open('tests/fixtures/baak_real_sample.html', 'w') as f:
    f.write(html)
"

# Run parser test
pytest tests/test_parser.py::TestBAAKParser::test_parse_sample_html -v
```

### Step 4: Bootstrap Snapshot
```bash
python main.py --class 3KA01 --force-refresh --save-snapshot
python main.py --class 3KB02 --force-refresh --save-snapshot
python main.py --validate-snapshots
```

### Step 5: Document Findings
```markdown
# docs/baak-source-validation.md
- Cloudflare status: [OK/BLOCKED]
- curl-cffi setup: [REQUIRED/NOT NEEDED]
- HTML structure: [COMPATIBLE/CHANGED]
- Snapshots available: [YES/MANUAL]
- Ready for Phase 2? [YES/NO]
```

---

## Risk Assessment

### 🟢 Low Risk (Can proceed now)
- [ ] baak-scraper standalone package
- [ ] No changes to telegram_personal_ai
- [ ] Fixture-based tests working
- [ ] CLI working with fixtures

### 🟡 Medium Risk (Need Phase 0)
- [ ] Live BAAK access (unknown)
- [ ] Cloudflare bypass (untested)
- [ ] HTML parser against real data (different format?)

### 🔴 High Risk (Cannot proceed)
- [ ] Breaking changes to telegram_personal_ai
- [ ] Race conditions with manual_reply()
- [ ] Cache interference

**Current Status:** 🟡 Medium — Phase 0 required before production

---

## Success Criteria (MVP Readiness)

After Phase 0 complete:

```
[ ] Cloudflare bypass confirmed or workaround documented
[ ] Parser validated against real BAAK HTML
[ ] Snapshot bootstrap successful (≥2 classes, ≥20 entries)
[ ] Phase 0 documentation complete
[ ] telegram_personal_ai tests still passing (no regression)
[ ] Go API contract ready for Phase 2
```

---

## Commit Message for Phase 0 Start

```
Phase 0: BAAK source validation and curl-cffi setup

- Add curl-cffi configuration guide to README_SETUP.md
- Create Phase 0 validation checklist (docs/baak-source-validation.md)
- Add deployment strategy document
- Ensure baak-scraper remains isolated from telegram_personal_ai
- Ready for live testing when environment is prepared

Gate: Validation must pass before Phase 2 (Go API) deployment
```

---

## Timeline Estimate

| Phase | Task | Estimate | Blocker |
|-------|------|----------|---------|
| 0a | Setup curl-cffi | 30 min | Network/env |
| 0b | Test live access | 15 min | Cloudflare |
| 0c | Validate parser | 15 min | HTML format |
| 0d | Bootstrap snapshot | 10 min | Data availability |
| 0e | Document findings | 20 min | None |
| **Total** | **Phase 0** | **~90 min** | **Cloudflare** |

Phase 2 (Go API) can start in parallel with Phase 0 testing.

---

## Next Actions

1. **Choose environment** (Termux? Windows? VPS?)
2. **Setup curl-cffi** per README_SETUP.md
3. **Run Phase 0 validation** following checklist above
4. **Document blockers** in `baak-source-validation.md`
5. **Report findings** → decide Phase 2 path (live vs snapshot-only)

**No Telegram changes until Phase 0 passes ✅**

