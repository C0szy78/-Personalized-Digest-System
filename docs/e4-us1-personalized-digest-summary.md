# E4-US1 Personalized Digest — Implementation and Verification

Date: 2026-07-20
Plugin: `RBRT Personalized Digest` v1.3.2
Master source: `wordpress-plugin/rbrt-personalized-digest/`

## Outcome

E4-US1 is implemented as a native RBRT WordPress pipeline rather than as a separate member database or Streamlit application. It uses the existing WordPress users, PWork forum records, approved directory membership, and `rbrt_interest_tags` profile data.

## WordPress data contract

| Source | RBRT/PWork storage | Unread/change boundary |
|---|---|---|
| Forum topics | Published `pworkforum` posts, `pwork_forum_content` meta, `pworkforumtags` taxonomy | `post_date_gmt` or `post_modified_gmt` after the member watermark and at/before the run boundary |
| Forum replies | Approved WordPress comments whose parent post type is `pworkforum` | `comment_date_gmt` after the member watermark and at/before the run boundary |
| Directory updates | WordPress users with `pw_user_status=approved` | `user_registered` or `rbrt_profile_updated_at` after the member watermark and at/before the run boundary |

The lower boundary is exclusive and the upper boundary inclusive. Each selected item also receives an immutable key (`forum_topic:*`, `forum_reply:*`, or `directory_profile:*`). Item keys from prior drafts are removed before ranking, protecting against reruns and late boundary overlap.

`rbrt_profile_updated_at` remains compatible with Profile Meter's Unix timestamp convention. The digest plugin also records this timestamp for relevant profile metadata, core profile edits, and future directory approval changes.

## Personalization

1. Read and normalize the member's comma/semicolon/newline-separated `rbrt_interest_tags` plus `rbrt_industry`.
2. Match whole terms against PWork taxonomy tags, titles, profile fields, and excerpts.
3. Score exact tags above title and excerpt matches, then add a small recency bonus.
4. Remove zero-score items and keep the top 12 before any external API request.
5. Ask the LLM for one concise summary per immutable item key.

Members with no declared interests do not receive a generic information dump. Their completed window is acknowledged by advancing the watermark without creating a draft.

## LLM and privacy behavior

- Administrator-managed settings support Ollama Cloud, OpenAI, Anthropic, Google Gemini, xAI/Grok, and custom HTTPS endpoints.
- Provider, model, endpoint, and request format are editable without changing plugin source. Built-in request formats cover Ollama generate, OpenAI Responses, OpenAI-compatible Chat Completions, Anthropic Messages, and Gemini generateContent.
- API keys can be added, replaced, retained by leaving the password field blank, or removed. A saved key is authenticated-encrypted using the WordPress site's secret salts, stored in a non-autoloaded WordPress option, and never rendered back into the admin page.
- Provider-specific environment variables remain optional overrides, but no key is committed or stored in plugin source.
- Ollama Cloud defaults to `kimi-k2.6` and `https://ollama.com/api/generate`; every default can be changed in WordPress settings.
- Authenticated local smoke verification passed with `kimi-k2.6`. Because this thinking-capable model wraps otherwise valid structured output in a JSON code fence, the request disables thinking and the parser removes only the outer fence before strict JSON and item-key validation.
- Member names and email addresses are not included in the request.
- Community content is explicitly treated as untrusted data, not model instructions.
- Invalid, missing, rate-limited, or failed responses produce a deterministic source-excerpt fallback draft.

The plugin renders final HTML itself. This guarantees the three source headings and uses only WordPress-generated URLs, even if model output is incomplete.

## Draft and review behavior

- Private custom post type: `rbrt_digest`.
- Every generated digest is inserted with WordPress `post_status=draft`.
- Stored metadata records member, UTC window, source counts, item keys, interests, and `ai`/`fallback` generation status.
- The watermark advances only after successful draft storage. A failed `wp_insert_post` leaves it unchanged for retry.
- Drafts are never emailed or published automatically.
- Users → Personalized Digests provides a protected manual generator and recent-draft review table.

## Member-facing digest bot

- Approved signed-in members receive a floating **My Digest** bubble on frontend pages; signed-out and unapproved accounts do not receive its markup or assets.
- Opening the accessible panel loads only the current member's latest digest through a nonce-protected authenticated WordPress AJAX request.
- **Check for new updates** runs the same unread, interest-ranked, deduplicated pipeline for the current member and refreshes the panel without exposing another member ID to the browser.
- A short per-member lock prevents concurrent generation requests. The close control, Escape key, keyboard focus styles, live status updates, constrained scrolling, and compact mobile layout are included.
- Draft HTML is sanitised by WordPress before storage and again before it is returned to the intended member.

## Automation

A daily WordPress Cron event starts batched processing for approved PWork members. Batches default to ten members and continue through single follow-up events. Automated runs are skipped until the selected provider, model, endpoint, and key are configured.

## Automated verification

`tests/e4-us1-personalized-digest.php` verifies:

- start-exclusive/end-inclusive unread boundaries;
- empty legacy profile-update timestamps remaining empty rather than being interpreted as the current time;
- interest normalization and whole-term matching;
- irrelevant-item removal before summarization;
- in-run and prior-draft deduplication;
- invocation of all three source collectors;
- one source-labelled digest draft;
- LLM failure fallback;
- watermark advancement after success;
- no watermark advancement after draft insertion failure;
- real `rbrt_digest` + `post_status=draft` insertion arguments.

`tests/e4-us1-personalized-digest.test.js` protects the WordPress/PWork/provider integration contract, administrator/nonce controls, supported provider adapters, encrypted non-autoloaded secret storage, key replacement/removal, and connection testing. On 2026-07-20 both E4 suites passed and PHP 8.3 lint passed for every plugin and E4 test file.

## Staging verification

The current branch was packaged as the unique-folder v1.3.2 build and activated on `https://domain1.badev.tools` on 2026-07-20. The prior verification copies are inactive, exactly one Personalized Digest copy is active, and production was not touched.

Authenticated frontend verification on the real PWork dashboard confirmed one bubble container, one launcher, one panel, one JavaScript asset, and one stylesheet. The PWork theme fires `wp_footer` twice, so v1.3.1 added a one-per-request render guard after the first staging build revealed duplicate containers. The panel loaded Cosmin-Gabriel's existing 12-item digest with all three source headings, a valid `Updated July 20, 2026 9:37 am` boundary, working source links, and no other member's digest. The on-demand action returned `You are all caught up. There are no unread updates.`, re-enabled its button, and did not create a duplicate digest. The close button hid the panel and restored the launcher's collapsed accessibility state. v1.3.2 uses the stored digest-window boundary instead of WordPress's zero draft date, fixing the invalid date found during live verification.

The live **Users → Personalized Digests** page now provides:

- provider choices for Ollama Cloud, OpenAI, Anthropic, Google Gemini, xAI/Grok, and a custom endpoint;
- editable model, HTTPS endpoint, and request-format controls;
- a blank password field that retains the existing encrypted key, replaces it when a new value is entered, or removes it through an explicit checkbox;
- a saved-connection test protected by administrator capability and a WordPress nonce.

The locally ignored `.env` Ollama key was entered through the staging settings form rather than added to source. After saving, staging reported `Configured`, the password field value remained empty, the placeholder reported that a key was stored, and the removal control was available. The built-in live connection test completed successfully with Ollama Cloud and `kimi-k2.6`.

The first v1.2.0 connection test revealed that Kimi can return otherwise valid keyed results under a top-level `summaries` array even when the supplied schema names the array `items`. A direct authenticated request reproduced this response shape without exposing the credential. v1.2.1 normalizes that alias before the existing strict item-key validation; automated tests protect this compatibility behavior.

The earlier v1.0.0 staging pass established the WordPress/PWork collection and fallback behavior below:

- Users → Personalized Digests loaded for the staging administrator and showed approved RBRT accounts.
- A controlled 365-day first run for Cosmin-Gabriel (user 679) queried live RBRT data and created WordPress draft 463. Its stored window was `2025-07-20 09:37:38` through `2026-07-20 09:37:38` UTC.
- The interest-ranked draft contained 12 items: 3 forum topics, 3 forum replies, and 6 approved directory updates. The editor showed the required `Forum topics`, `Forum replies`, and `Directory updates` headings with staging links.
- The draft remained in WordPress `draft` status and recorded 12 immutable item keys, the source counts, UTC window, member, interests, and `fallback` generation status. Nothing was published or sent.
- The first immediate repeat exposed a legacy-data defect: an empty `rbrt_profile_updated_at` value was parsed as the current time, allowing six profiles to recur. `normalize_datetime()` now returns an empty value for empty input, and an automated regression test protects this case.
- The corrected package was installed over the staging copy while keeping the plugin active. A repeat run then returned `No unread updates were found`, created no additional draft, and advanced the watermark to close the checked window. The invalid repeat test draft was moved to the WordPress Bin (recoverable), leaving one valid staging draft.
- Live Ollama Cloud connectivity from staging WordPress is verified. Automated tests cover both model success and LLM failure; the earlier deterministic fallback draft remains as evidence of the safe failure path.

Staging package: `rbrt-personalized-digest-v1.3.2.zip`
SHA-256: `E53F050F64235C7C66CAC96A34B6E032C2E1F4DCD43079EC91ED74E9CCCBB13B`

## Pull-request status

The work is on branch `agent/e4-us1-wordpress-digest` and the draft pull request is [afsana0123/-Personalized-Digest-System#1](https://github.com/afsana0123/-Personalized-Digest-System/pull/1). Staging evidence and final automated verification are documented here for review.
