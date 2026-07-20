# E4-US1 Personalized Digest — Implementation and Verification

Date: 2026-07-20
Plugin: `RBRT Personalized Digest` v1.1.0
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

- Ollama Cloud generate API with a strict JSON schema and non-streaming output.
- Configured through `OLLAMA_API_KEY` or `RBRT_DIGEST_OLLAMA_API_KEY`; no key is committed or stored in plugin source.
- Default model `kimi-k2.6`, overridable through `OLLAMA_MODEL`, `RBRT_DIGEST_OLLAMA_MODEL`, or filters.
- Bearer-authenticated direct access to `https://ollama.com/api/generate`.
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

## Automation

A daily WordPress Cron event starts batched processing for approved PWork members. Batches default to ten members and continue through single follow-up events. Automated runs are skipped until an Ollama Cloud key is configured.

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

`tests/e4-us1-personalized-digest.test.js` protects the WordPress/PWork/Ollama Cloud integration contract. On 2026-07-20 both E4 suites and all existing E3/dashboard/event regression suites passed. PHP 8.3 lint passed for every plugin and E4 test file.

## Staging verification

The current branch was packaged as the unique-folder v1.1.0 build and activated on `https://domain1.badev.tools` on 2026-07-20. The earlier v1.0.0 copy is inactive, exactly one Personalized Digest copy is active, and production was not touched. The live Users → Personalized Digests page shows the Ollama Cloud configuration contract (`OLLAMA_API_KEY` / `RBRT_DIGEST_OLLAMA_API_KEY`), the existing source-count and item metadata, and no PHP or activation error. Staging PHP does not yet expose the Ollama secret, so the live page correctly reports Not configured and scheduled model generation remains disabled.

The earlier v1.0.0 staging pass established the WordPress/PWork collection and fallback behavior below:

- Users → Personalized Digests loaded for the staging administrator, showed approved RBRT accounts, and reported that the previous OpenAI configuration was not present. The pending Ollama build will report `OLLAMA_API_KEY`/`RBRT_DIGEST_OLLAMA_API_KEY` instead.
- A controlled 365-day first run for Cosmin-Gabriel (user 679) queried live RBRT data and created WordPress draft 463. Its stored window was `2025-07-20 09:37:38` through `2026-07-20 09:37:38` UTC.
- The interest-ranked draft contained 12 items: 3 forum topics, 3 forum replies, and 6 approved directory updates. The editor showed the required `Forum topics`, `Forum replies`, and `Directory updates` headings with staging links.
- The draft remained in WordPress `draft` status and recorded 12 immutable item keys, the source counts, UTC window, member, interests, and `fallback` generation status. Nothing was published or sent.
- The first immediate repeat exposed a legacy-data defect: an empty `rbrt_profile_updated_at` value was parsed as the current time, allowing six profiles to recur. `normalize_datetime()` now returns an empty value for empty input, and an automated regression test protects this case.
- The corrected package was installed over the staging copy while keeping the plugin active. A repeat run then returned `No unread updates were found`, created no additional draft, and advanced the watermark to close the checked window. The invalid repeat test draft was moved to the WordPress Bin (recoverable), leaving one valid staging draft.
- Live Ollama Cloud generation inside staging WordPress remains pending until its key is securely exposed to staging PHP. Direct authenticated `kimi-k2.6` generation and structured-output parsing were verified locally; the live WordPress behavior verified so far is the deterministic fallback path. Automated tests cover both model success and LLM failure.

Staging package: `rbrt-personalized-digest-v1.1.0.zip`
SHA-256: `7163F9CBC3FFEC6159E67826DA308C7EEE6DE052760F9E4D713E1D0FF30BCF74`

## Pull-request status

The workspace's `.git` directory is empty, so there is currently no local history, branch, or remote from which to create a truthful reviewed pull request. Source, tests, package, and staging evidence can be completed here; PR creation requires reconnecting this workspace to the intended Git repository or supplying a writable GitHub target.
