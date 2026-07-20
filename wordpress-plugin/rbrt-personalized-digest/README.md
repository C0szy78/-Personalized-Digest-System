# RBRT Personalized Digest

WordPress implementation of E4-US1. The plugin creates one private WordPress draft per approved member and digest window from:

- new or edited PWork forum topics (`pworkforum` + `pwork_forum_content` + `pworkforumtags`);
- new approved comments and nested replies on PWork topics;
- newly registered or materially updated directory members with `pw_user_status=approved`.

## Personalization and unread state

Member interests come from `rbrt_interest_tags`, with `rbrt_industry` included as a useful profile signal. Items receive deterministic relevance scores before the LLM is called. Zero-score items never leave WordPress.

The exclusive lower/inclusive upper UTC window is stored in user meta `_rbrt_digest_watermark_gmt`. A bounded list of immutable source keys is also stored on every draft in `_rbrt_digest_item_keys`, preventing duplicates at late or repeated boundaries. The watermark advances only after the draft is stored successfully, or when the completed window contains no relevant updates.

On the first run, the default lookback is seven days. Administrators can choose up to 365 days for a member's first manual run.

## AI provider configuration

Go to **Users → Personalized Digests** as a site administrator. Select Ollama Cloud, OpenAI, Anthropic, Google Gemini, xAI/Grok, or Custom endpoint, then edit the model, HTTPS endpoint, and request format as needed.

The password field never displays the current key. Leave it blank to retain the saved key, enter a value to replace it, or select the removal checkbox to delete it. Saved keys are authenticated-encrypted using the WordPress site's secret salts and stored in a non-autoloaded option. Changing the site's salts requires the key to be entered again.

Provider-specific environment variables (`OLLAMA_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, and `XAI_API_KEY`) are optional deployment overrides. The plugin does not read repository `.env` files and no credentials belong in source or Git.

Only selected public/community excerpts, declared interests, source type, timestamps, and relevance scores are sent. The member's name and email are not sent.

If the API is missing, unavailable, or returns invalid output, a deterministic source-excerpt draft is created for administrator review. Scheduled generation is skipped until the API key is configured, preventing automated fallback-draft floods.

## Administration and scheduling

- Go to **Users → Personalized Digests** to generate and review member drafts.
- Approved signed-in members see a floating **My Digest** button on frontend pages. It loads only that member's latest digest and can securely trigger a new unread-window check.
- On Romanian routes, the bubble controls, statuses, dates, source headings, and plugin-generated item labels are translated while member-authored community content is preserved.
- Generated records use the private `rbrt_digest` post type and the real WordPress `draft` status.
- Daily processing uses WordPress Cron and batches ten approved members at a time.
- Drafts are never emailed or published automatically.

Useful filters:

- `rbrt_digest_ai_api_key`
- `rbrt_digest_allow_insecure_ai_endpoint` (disabled by default; intended only for controlled local development)
- `rbrt_digest_max_items`
- `rbrt_digest_batch_size`
- `rbrt_digest_material_profile_meta_keys`
- `rbrt_digest_forum_topic_items`
- `rbrt_digest_forum_reply_items`
- `rbrt_digest_directory_items`

## Tests

```powershell
php tests/e4-us1-personalized-digest.php
node tests/e4-us1-personalized-digest.test.js
```

The PHP suite covers unread window boundaries, interest filtering, short-term matching, deduplication, all three collectors, LLM failure, watermark safety, WordPress draft creation, and secret-setting behavior. The Node contract suite protects the PWork schema, privacy, provider adapters, administrator controls, encrypted secret storage, and draft-storage integration points.
