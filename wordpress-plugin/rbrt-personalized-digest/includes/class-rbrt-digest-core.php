<?php

defined('ABSPATH') || exit;

final class RBRT_Digest_Core {
    const WATERMARK_META = '_rbrt_digest_watermark_gmt';
    const PROFILE_UPDATED_META = 'rbrt_profile_updated_at';

    public static function normalize_datetime($value) {
        if ($value instanceof DateTimeInterface) {
            return gmdate('Y-m-d H:i:s', $value->getTimestamp());
        }

        $value = trim((string) $value);
        if ($value === '') {
            return '';
        }

        $timestamp = is_numeric($value) ? (int) $value : strtotime($value . ' UTC');
        return $timestamp ? gmdate('Y-m-d H:i:s', $timestamp) : '';
    }

    public static function in_window($value, $start_gmt, $end_gmt) {
        $value = self::normalize_datetime($value);
        $start_gmt = self::normalize_datetime($start_gmt);
        $end_gmt = self::normalize_datetime($end_gmt);

        return $value !== '' && $start_gmt !== '' && $end_gmt !== ''
            && $value > $start_gmt
            && $value <= $end_gmt;
    }

    public static function normalize_terms($value) {
        $value = is_array($value) ? $value : array($value);
        $expanded = array();
        foreach ($value as $entry) {
            $parts = preg_split('/[,;\r\n]+/u', (string) $entry);
            $expanded = array_merge($expanded, is_array($parts) ? $parts : array());
        }

        $terms = array();
        foreach ($expanded as $term) {
            $term = trim(wp_strip_all_tags((string) $term));
            if ($term === '') {
                continue;
            }

            $normal = function_exists('mb_strtolower') ? mb_strtolower($term, 'UTF-8') : strtolower($term);
            $normal = preg_replace('/\s+/u', ' ', $normal);
            if ($normal !== '' && !in_array($normal, $terms, true)) {
                $terms[] = $normal;
            }
        }

        return $terms;
    }

    public static function searchable_text($item) {
        $parts = array(
            isset($item['title']) ? $item['title'] : '',
            isset($item['content']) ? $item['content'] : '',
            isset($item['author']) ? $item['author'] : '',
        );

        if (!empty($item['tags']) && is_array($item['tags'])) {
            $parts[] = implode(' ', $item['tags']);
        }

        $text = wp_strip_all_tags(implode(' ', $parts));
        $text = function_exists('mb_strtolower') ? mb_strtolower($text, 'UTF-8') : strtolower($text);
        return preg_replace('/\s+/u', ' ', $text);
    }

    public static function score_item($item, $interests, $now_gmt = '') {
        $interests = self::normalize_terms($interests);
        if (!$interests) {
            return 0;
        }

        $title = isset($item['title']) ? self::searchable_text(array('title' => $item['title'])) : '';
        $content = isset($item['content']) ? self::searchable_text(array('content' => $item['content'])) : '';
        $item_tags = self::normalize_terms(isset($item['tags']) ? $item['tags'] : array());
        $score = 0;

        foreach ($interests as $interest) {
            if (in_array($interest, $item_tags, true)) {
                $score += 50;
                continue;
            }

            if ($title !== '' && self::contains_term($title, $interest)) {
                $score += 30;
            } elseif ($content !== '' && self::contains_term($content, $interest)) {
                $score += 15;
            }
        }

        if ($score > 0 && !empty($item['occurred_gmt'])) {
            $now = $now_gmt ? strtotime($now_gmt . ' UTC') : time();
            $occurred = strtotime($item['occurred_gmt'] . ' UTC');
            if ($now && $occurred) {
                $age_days = max(0, ($now - $occurred) / DAY_IN_SECONDS);
                $score += max(0, 10 - (int) floor($age_days));
            }
        }

        return min(100, $score);
    }

    private static function contains_term($haystack, $needle) {
        if ($needle === '') {
            return false;
        }

        return (bool) preg_match(
            '/(?<![\p{L}\p{N}])' . preg_quote($needle, '/') . '(?![\p{L}\p{N}])/iu',
            $haystack
        );
    }

    public static function rank_items($items, $interests, $now_gmt, $limit = 12) {
        $ranked = array();
        foreach ($items as $item) {
            $item['score'] = self::score_item($item, $interests, $now_gmt);
            if ($item['score'] > 0) {
                $ranked[] = $item;
            }
        }

        usort($ranked, static function ($left, $right) {
            if ($left['score'] === $right['score']) {
                return strcmp($right['occurred_gmt'], $left['occurred_gmt']);
            }
            return $right['score'] <=> $left['score'];
        });

        return array_slice($ranked, 0, max(1, (int) $limit));
    }

    public static function deduplicate_items($items, $existing_keys = array()) {
        $seen = array_fill_keys(array_map('strval', $existing_keys), true);
        $unique = array();

        foreach ($items as $item) {
            $key = isset($item['key']) ? (string) $item['key'] : '';
            if ($key === '' || isset($seen[$key])) {
                continue;
            }
            $seen[$key] = true;
            $unique[] = $item;
        }

        return $unique;
    }

    public static function source_label($source) {
        $labels = array(
            'forum_topic' => __('Forum topics', 'rbrt-personalized-digest'),
            'forum_reply' => __('Forum replies', 'rbrt-personalized-digest'),
            'directory_profile' => __('Directory updates', 'rbrt-personalized-digest'),
        );

        return isset($labels[$source]) ? $labels[$source] : __('Community updates', 'rbrt-personalized-digest');
    }

    public static function fallback_summaries($items) {
        $summaries = array();
        foreach ($items as $item) {
            $content = isset($item['content']) ? wp_strip_all_tags($item['content']) : '';
            $summaries[$item['key']] = wp_trim_words($content, 28, '…');
            if ($summaries[$item['key']] === '') {
                $summaries[$item['key']] = isset($item['title']) ? $item['title'] : __('New community update', 'rbrt-personalized-digest');
            }
        }
        return $summaries;
    }

    public static function render_digest($member, $items, $summaries, $intro = '') {
        $name = is_object($member) && isset($member->display_name) ? $member->display_name : '';
        $html = '<div class="rbrt-personalized-digest">';
        $html .= '<p>' . esc_html($intro !== '' ? $intro : sprintf(__('Hello %s, here are the community updates most relevant to your interests.', 'rbrt-personalized-digest'), $name)) . '</p>';

        foreach (array('forum_topic', 'forum_reply', 'directory_profile') as $source) {
            $source_items = array_values(array_filter($items, static function ($item) use ($source) {
                return isset($item['source']) && $item['source'] === $source;
            }));
            if (!$source_items) {
                continue;
            }

            $html .= '<h2>' . esc_html(self::source_label($source)) . '</h2><ul>';
            foreach ($source_items as $item) {
                $summary = isset($summaries[$item['key']]) ? $summaries[$item['key']] : '';
                $html .= '<li><strong><a href="' . esc_url($item['url']) . '">' . esc_html($item['title']) . '</a></strong>';
                if ($summary !== '') {
                    $html .= '<br>' . esc_html($summary);
                }
                $html .= '</li>';
            }
            $html .= '</ul>';
        }

        return $html . '</div>';
    }
}
