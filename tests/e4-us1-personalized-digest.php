<?php

define('ABSPATH', __DIR__ . '/');
define('DAY_IN_SECONDS', 86400);

class WP_Error {
    public $code;
    public $message;
    public function __construct($code = '', $message = '') {
        $this->code = $code;
        $this->message = $message;
    }
}

function is_wp_error($value) { return $value instanceof WP_Error; }
function __($text, $domain = null) { return $text; }
function wp_strip_all_tags($text) { return trim(strip_tags((string) $text)); }
function wp_trim_words($text, $count, $more = null) {
    $words = preg_split('/\s+/', trim((string) $text));
    if (count($words) <= $count) { return implode(' ', $words); }
    return implode(' ', array_slice($words, 0, $count)) . ($more === null ? '…' : $more);
}
function esc_html($text) { return htmlspecialchars((string) $text, ENT_QUOTES, 'UTF-8'); }
function esc_url($url) { return (string) $url; }
function wp_kses_post($html) { return (string) $html; }
function sanitize_key($key) { return preg_replace('/[^a-z0-9_\-]/', '', strtolower((string) $key)); }
function apply_filters($hook, $value) { return $value; }
function current_time($type, $gmt = false) { return '2026-07-20 12:00:00'; }
function get_date_from_gmt($date, $format) { return substr($date, 0, 10); }
function get_option($key, $default = false) { return $key === 'date_format' ? 'Y-m-d' : $default; }
function wp_insert_post($postarr, $wp_error = false) {
    $GLOBALS['rbrt_test_inserted_post'] = $postarr;
    return 321;
}

require_once __DIR__ . '/../wordpress-plugin/rbrt-personalized-digest/includes/class-rbrt-digest-core.php';
require_once __DIR__ . '/../wordpress-plugin/rbrt-personalized-digest/includes/class-rbrt-digest-wordpress-repository.php';
require_once __DIR__ . '/../wordpress-plugin/rbrt-personalized-digest/includes/class-rbrt-digest-service.php';
require_once __DIR__ . '/../wordpress-plugin/rbrt-personalized-digest/includes/class-rbrt-digest-ollama-summarizer.php';

function assert_true($condition, $message) {
    if (!$condition) {
        throw new RuntimeException($message);
    }
}

function item($key, $source, $title, $content, $occurred = '2026-07-20 11:00:00', $tags = array('Technology')) {
    return array(
        'key' => $key,
        'source' => $source,
        'object_id' => 1,
        'title' => $title,
        'content' => $content,
        'author' => 'Test Member',
        'tags' => $tags,
        'url' => 'https://example.test/' . rawurlencode($key),
        'occurred_gmt' => $occurred,
    );
}

assert_true(!RBRT_Digest_Core::in_window('2026-07-20 10:00:00', '2026-07-20 10:00:00', '2026-07-20 12:00:00'), 'window start must be exclusive');
assert_true(RBRT_Digest_Core::in_window('2026-07-20 12:00:00', '2026-07-20 10:00:00', '2026-07-20 12:00:00'), 'window end must be inclusive');
assert_true(!RBRT_Digest_Core::in_window('2026-07-20 12:00:01', '2026-07-20 10:00:00', '2026-07-20 12:00:00'), 'items after window end must be excluded');
assert_true(RBRT_Digest_Core::normalize_datetime('') === '', 'missing profile timestamps must remain empty rather than becoming the current time');

$ollama = new RBRT_Digest_Ollama_Summarizer();
$clean_json = new ReflectionMethod($ollama, 'clean_json_output');
$clean_json->setAccessible(true);
assert_true(
    $clean_json->invoke($ollama, "```json\n{\"status\":\"connected\"}\n```") === '{"status":"connected"}',
    'Kimi JSON code fences must be removed before strict decoding'
);

$terms = RBRT_Digest_Core::normalize_terms(array('AI, Technology', 'Business; AI'));
assert_true($terms === array('ai', 'technology', 'business'), 'interest terms must split, normalize, and deduplicate');

$ranked = RBRT_Digest_Core::rank_items(array(
    item('relevant', 'forum_topic', 'Technology meetup', 'A local meetup'),
    item('irrelevant', 'forum_topic', 'Gardening club', 'Seed exchange', '2026-07-20 11:30:00', array('Gardening')),
), array('Technology'), '2026-07-20 12:00:00', 12);
assert_true(count($ranked) === 1 && $ranked[0]['key'] === 'relevant', 'only interest-matching items should reach the LLM');
assert_true(RBRT_Digest_Core::score_item(item('short-term', 'forum_topic', 'Said plainly', 'A normal sentence', '2026-07-20 11:00:00', array()), array('AI'), '2026-07-20 12:00:00') === 0, 'short interests must match whole terms rather than substrings');

$deduplicated = RBRT_Digest_Core::deduplicate_items(array(
    item('same', 'forum_topic', 'Technology', 'One'),
    item('same', 'forum_topic', 'Technology', 'Two'),
    item('already-drafted', 'forum_reply', 'Technology', 'Three'),
), array('already-drafted'));
assert_true(count($deduplicated) === 1 && $deduplicated[0]['key'] === 'same', 'item keys must deduplicate current and prior digest items');

class Fake_Repository {
    public $calls = array();
    public $drafts = array();
    public $watermark = '';
    public function get_member($id) { return (object) array('ID' => $id, 'display_name' => 'Ana'); }
    public function get_member_interests($id) { return array('technology'); }
    public function get_window_start($id, $end, $days) { return '2026-07-20 10:00:00'; }
    public function set_watermark($id, $end) { $this->watermark = $end; return true; }
    public function collect_forum_topics($id, $start, $end) { $this->calls[] = array('topics', $start, $end); return array(item('topic:1', 'forum_topic', 'Technology topic', 'New AI event')); }
    public function collect_forum_replies($id, $start, $end) { $this->calls[] = array('replies', $start, $end); return array(item('reply:1', 'forum_reply', 'Technology reply', 'AI course details')); }
    public function collect_directory_updates($id, $start, $end) { $this->calls[] = array('directory', $start, $end); return array(item('profile:1', 'directory_profile', 'Technology founder', 'AI Birmingham')); }
    public function find_existing_item_keys($id) { return array('reply:1'); }
    public function create_draft($member, $content, $items, $start, $end, $status, $interests) {
        $this->drafts[] = compact('member', 'content', 'items', 'start', 'end', 'status', 'interests');
        return 99;
    }
}

class Fake_Summarizer {
    private $fail;
    public function __construct($fail = false) { $this->fail = $fail; }
    public function summarize($member, $interests, $items) {
        if ($this->fail) { return new WP_Error('api_down', 'down'); }
        $summaries = array();
        foreach ($items as $item) { $summaries[$item['key']] = 'Personalized ' . $item['source']; }
        return array('intro' => 'Your relevant updates.', 'summaries' => $summaries);
    }
}

$repository = new Fake_Repository();
$service = new RBRT_Digest_Service($repository, new Fake_Summarizer());
$result = $service->generate_for_member(7, array('end_gmt' => '2026-07-20 12:00:00'));
assert_true(array_column($repository->calls, 0) === array('topics', 'replies', 'directory'), 'all three WordPress sources must be queried');
assert_true($result['status'] === 'ai' && $result['draft_id'] === 99, 'successful generation must create one AI draft');
assert_true(count($repository->drafts) === 1 && count($repository->drafts[0]['items']) === 2, 'prior item keys must be removed before generation');
assert_true(strpos($repository->drafts[0]['content'], 'Forum topics') !== false, 'draft must label forum topic sources');
assert_true(strpos($repository->drafts[0]['content'], 'Directory updates') !== false, 'draft must label directory sources');
assert_true($repository->watermark === '2026-07-20 12:00:00', 'watermark must advance after draft storage');

$fallback_repository = new Fake_Repository();
$fallback_service = new RBRT_Digest_Service($fallback_repository, new Fake_Summarizer(true));
$fallback = $fallback_service->generate_for_member(7, array('end_gmt' => '2026-07-20 12:00:00'));
assert_true($fallback['status'] === 'fallback', 'LLM failure must create a deterministic fallback draft');
assert_true($fallback_repository->drafts[0]['status'] === 'fallback', 'fallback state must be stored on the draft');

class Failing_Draft_Repository extends Fake_Repository {
    public function create_draft($member, $content, $items, $start, $end, $status, $interests) {
        return new WP_Error('insert_failed', 'failed');
    }
}
$failed_repository = new Failing_Draft_Repository();
$failed_service = new RBRT_Digest_Service($failed_repository, new Fake_Summarizer());
$failed = $failed_service->generate_for_member(7, array('end_gmt' => '2026-07-20 12:00:00'));
assert_true(is_wp_error($failed), 'draft insertion failure must be returned to the caller');
assert_true($failed_repository->watermark === '', 'watermark must not advance when draft storage fails');

$wp_repository = new RBRT_Digest_WordPress_Repository();
$draft_id = $wp_repository->create_draft(
    (object) array('ID' => 7, 'display_name' => 'Ana'),
    '<p>Digest</p>',
    array(item('topic:2', 'forum_topic', 'Technology', 'AI')),
    '2026-07-20 10:00:00',
    '2026-07-20 12:00:00',
    'ai',
    array('technology')
);
assert_true($draft_id === 321, 'WordPress draft insertion should return its post ID');
assert_true($GLOBALS['rbrt_test_inserted_post']['post_type'] === 'rbrt_digest', 'digest must use the WordPress-backed digest post type');
assert_true($GLOBALS['rbrt_test_inserted_post']['post_status'] === 'draft', 'generated digest must be an actual WordPress draft');
assert_true($GLOBALS['rbrt_test_inserted_post']['meta_input']['_rbrt_digest_item_keys'] === array('topic:2'), 'draft must persist immutable item keys');

echo "E4-US1 personalized digest tests: PASS\n";
