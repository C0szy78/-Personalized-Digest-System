# RBRT Personalized Digest

Native WordPress implementation of E4-US1 for the RBRT community platform.

The deliverable is the plugin in `wordpress-plugin/rbrt-personalized-digest/`. It operates on RBRT's existing WordPress users and PWork data instead of maintaining separate member, content, or digest databases.

## What the plugin does

- Reads declared member interests from `rbrt_interest_tags` and `rbrt_industry`.
- Collects unread or changed PWork forum topics, approved forum replies, and approved directory profile updates.
- Uses per-member UTC watermarks and immutable source keys to prevent repeated items.
- Filters and ranks updates by interest before any LLM request.
- Calls the selected AI provider for one concise, source-labelled digest.
- Stores the result as a private `rbrt_digest` WordPress post with `post_status=draft`.
- Creates a deterministic reviewable fallback draft if the LLM is unavailable.
- Supports protected manual generation and batched daily WordPress Cron processing.

Generated drafts are never automatically published or emailed.

## Installation

1. Create a ZIP whose root folder is `rbrt-personalized-digest/`.
2. Upload it through WordPress Admin → Plugins → Add Plugin → Upload Plugin.
3. Activate **RBRT Personalized Digest**.
4. Open Users → Personalized Digests.

Under **Users → Personalized Digests → AI provider settings**, choose Ollama Cloud, OpenAI, Anthropic, Google Gemini, xAI/Grok, or Custom endpoint. The model, HTTPS endpoint, and request format are editable. Entering a key replaces the existing key; leaving it blank keeps the existing key; the removal checkbox deletes it.

The key is encrypted with the WordPress site's secret salts, saved as a non-autoloaded WordPress option, and never displayed after saving. Provider-specific PHP environment variables (`OLLAMA_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, or `XAI_API_KEY`) remain optional deployment overrides. Do not place credentials in plugin source or Git.

## Tests

```powershell
php tests/e4-us1-personalized-digest.php
node --test tests/e4-us1-personalized-digest.test.js
```

The suites cover all three sources, unread boundaries, legacy empty timestamps, interest filtering, short-term whole-word matching, deduplication, LLM failure, watermark safety, and actual WordPress draft arguments.

See `docs/e4-us1-personalized-digest-summary.md` for the implementation contract and staging evidence.

## Legacy prototype

The existing `src/` Streamlit/SQLite/Groq application is retained temporarily for review history. It is not the E4-US1 RBRT integration because it creates separate members and documents, fetches generic WordPress posts, and does not use RBRT's PWork unread state or WordPress draft records.
