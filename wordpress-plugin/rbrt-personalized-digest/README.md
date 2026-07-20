# RBRT Personalized Digest

WordPress implementation of E4-US1. The plugin creates one private WordPress draft per approved member and digest window from:

- new or edited PWork forum topics (`pworkforum` + `pwork_forum_content` + `pworkforumtags`);
- new approved comments and nested replies on PWork topics;
- newly registered or materially updated directory members with `pw_user_status=approved`.

## Personalization and unread state

Member interests come from `rbrt_interest_tags`, with `rbrt_industry` included as a useful profile signal. Items receive deterministic relevance scores before the LLM is called. Zero-score items never leave WordPress.

The exclusive lower/inclusive upper UTC window is stored in user meta `_rbrt_digest_watermark_gmt`. A bounded list of immutable source keys is also stored on every draft in `_rbrt_digest_item_keys`, preventing duplicates at late or repeated boundaries. The watermark advances only after the draft is stored successfully, or when the completed window contains no relevant updates.

On the first run, the default lookback is seven days. Administrators can choose up to 365 days for a member's first manual run.

## Ollama Cloud configuration

Set the key outside the plugin. The plugin accepts the server environment variable `OLLAMA_API_KEY` or a WordPress constant in `wp-config.php`:

```php
define('RBRT_DIGEST_OLLAMA_API_KEY', '...');
```

A local `.env` file is ignored by Git and is useful for deployment tooling, but WordPress must expose the value to PHP as an environment variable or constant; the plugin does not parse repository files at runtime.

The default model is `kimi-k2.6`. Override it without changing plugin code:

```php
define('RBRT_DIGEST_OLLAMA_MODEL', 'your-approved-model');
```

The integration uses `POST https://ollama.com/api/generate` with Bearer authentication, non-streaming responses, and a JSON schema in `format`. Only selected public/community excerpts, declared interests, source type, timestamps, and relevance scores are sent. The member's name and email are not sent.

If the API is missing, unavailable, or returns invalid output, a deterministic source-excerpt draft is created for administrator review. Scheduled generation is skipped until the API key is configured, preventing automated fallback-draft floods.

## Administration and scheduling

- Go to **Users → Personalized Digests** to generate and review member drafts.
- Generated records use the private `rbrt_digest` post type and the real WordPress `draft` status.
- Daily processing uses WordPress Cron and batches ten approved members at a time.
- Drafts are never emailed or published automatically.

Useful filters:

- `rbrt_digest_ollama_api_key`
- `rbrt_digest_ollama_model`
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

The PHP suite covers unread window boundaries, interest filtering, short-term matching, deduplication, all three collectors, LLM failure, watermark safety, and WordPress draft creation. The Node contract suite protects the PWork schema, privacy, Ollama Cloud, and draft-storage integration points.
