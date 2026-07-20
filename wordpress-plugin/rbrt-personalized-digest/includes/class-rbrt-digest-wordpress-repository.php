<?php

defined('ABSPATH') || exit;

final class RBRT_Digest_WordPress_Repository {
    public function get_member($member_id) {
        return get_userdata((int) $member_id);
    }

    public function get_approved_member_ids() {
        return get_users(array(
            'fields' => 'ids',
            'orderby' => 'ID',
            'order' => 'ASC',
            'meta_key' => 'pw_user_status',
            'meta_value' => 'approved',
        ));
    }

    public function get_member_interests($member_id) {
        $values = array(
            get_user_meta($member_id, 'rbrt_interest_tags', true),
            get_user_meta($member_id, 'rbrt_industry', true),
        );

        return RBRT_Digest_Core::normalize_terms(implode(', ', array_filter($values)));
    }

    public function get_window_start($member_id, $end_gmt, $lookback_days = 7) {
        $watermark = get_user_meta($member_id, RBRT_Digest_Core::WATERMARK_META, true);
        if ($watermark !== '') {
            return RBRT_Digest_Core::normalize_datetime($watermark);
        }

        $lookback_days = max(1, (int) $lookback_days);
        return gmdate('Y-m-d H:i:s', strtotime($end_gmt . ' UTC') - ($lookback_days * DAY_IN_SECONDS));
    }

    public function set_watermark($member_id, $end_gmt) {
        return update_user_meta($member_id, RBRT_Digest_Core::WATERMARK_META, RBRT_Digest_Core::normalize_datetime($end_gmt));
    }

    public function collect_forum_topics($member_id, $start_gmt, $end_gmt) {
        $query = new WP_Query(array(
            'post_type' => 'pworkforum',
            'post_status' => 'publish',
            'posts_per_page' => 100,
            'orderby' => 'modified',
            'order' => 'DESC',
            'no_found_rows' => true,
            'date_query' => $this->changed_date_query($start_gmt, $end_gmt),
        ));

        $items = array();
        foreach ($query->posts as $post) {
            if ((int) $post->post_author === (int) $member_id) {
                continue;
            }

            $occurred = max(
                strtotime($post->post_date_gmt . ' UTC'),
                strtotime($post->post_modified_gmt . ' UTC')
            );
            $terms = wp_get_post_terms($post->ID, 'pworkforumtags', array('fields' => 'names'));
            $items[] = array(
                'key' => 'forum_topic:' . $post->ID . ':' . $occurred,
                'source' => 'forum_topic',
                'object_id' => (int) $post->ID,
                'title' => get_the_title($post),
                'content' => get_post_meta($post->ID, 'pwork_forum_content', true),
                'author' => get_the_author_meta('display_name', $post->post_author),
                'tags' => is_wp_error($terms) ? array() : $terms,
                'url' => home_url('/page/forum?topicID=' . $post->ID),
                'occurred_gmt' => gmdate('Y-m-d H:i:s', $occurred),
            );
        }

        return apply_filters('rbrt_digest_forum_topic_items', $items, $member_id, $start_gmt, $end_gmt);
    }

    public function collect_forum_replies($member_id, $start_gmt, $end_gmt) {
        $comments = get_comments(array(
            'status' => 'approve',
            'post_type' => 'pworkforum',
            'number' => 200,
            'orderby' => 'comment_date_gmt',
            'order' => 'DESC',
            'date_query' => $this->comment_date_query($start_gmt, $end_gmt),
        ));

        $items = array();
        foreach ($comments as $comment) {
            if ((int) $comment->user_id === (int) $member_id) {
                continue;
            }

            $topic = get_post($comment->comment_post_ID);
            if (!$topic || $topic->post_type !== 'pworkforum' || $topic->post_status !== 'publish') {
                continue;
            }

            $terms = wp_get_post_terms($topic->ID, 'pworkforumtags', array('fields' => 'names'));
            $items[] = array(
                'key' => 'forum_reply:' . $comment->comment_ID,
                'source' => 'forum_reply',
                'object_id' => (int) $comment->comment_ID,
                'parent_id' => (int) $topic->ID,
                'title' => sprintf(__('Reply in “%s”', 'rbrt-personalized-digest'), get_the_title($topic)),
                'content' => $comment->comment_content,
                'author' => get_comment_author($comment),
                'tags' => is_wp_error($terms) ? array() : $terms,
                'url' => home_url('/page/forum?topicID=' . $topic->ID) . '#comment-' . $comment->comment_ID,
                'occurred_gmt' => RBRT_Digest_Core::normalize_datetime($comment->comment_date_gmt),
            );
        }

        return apply_filters('rbrt_digest_forum_reply_items', $items, $member_id, $start_gmt, $end_gmt);
    }

    public function collect_directory_updates($member_id, $start_gmt, $end_gmt) {
        $users = get_users(array(
            'meta_key' => 'pw_user_status',
            'meta_value' => 'approved',
            'orderby' => 'ID',
            'order' => 'ASC',
        ));
        $items = array();

        foreach ($users as $user) {
            if ((int) $user->ID === (int) $member_id) {
                continue;
            }

            $registered = RBRT_Digest_Core::normalize_datetime($user->user_registered);
            $updated = RBRT_Digest_Core::normalize_datetime(get_user_meta($user->ID, RBRT_Digest_Core::PROFILE_UPDATED_META, true));
            $occurred = '';

            if (RBRT_Digest_Core::in_window($registered, $start_gmt, $end_gmt)) {
                $occurred = $registered;
            }
            if (RBRT_Digest_Core::in_window($updated, $start_gmt, $end_gmt) && ($occurred === '' || $updated > $occurred)) {
                $occurred = $updated;
            }
            if ($occurred === '') {
                continue;
            }

            $company = $this->first_user_meta($user->ID, array('pwork_company', 'company', 'business_name'));
            $job = $this->first_user_meta($user->ID, array('pwork_job', 'job_title'));
            $industry = $this->first_user_meta($user->ID, array('rbrt_industry', 'industry', 'sector'));
            $location = $this->first_user_meta($user->ID, array('pwork_location', 'location', 'city'));
            $interests = get_user_meta($user->ID, 'rbrt_interest_tags', true);
            $description = get_user_meta($user->ID, 'description', true);
            $profile_bits = array_filter(array($job, $company, $industry, $location, $interests, $description));

            $items[] = array(
                'key' => 'directory_profile:' . $user->ID . ':' . strtotime($occurred . ' UTC'),
                'source' => 'directory_profile',
                'object_id' => (int) $user->ID,
                'title' => sprintf(__('%s updated their directory profile', 'rbrt-personalized-digest'), $user->display_name),
                'content' => implode('. ', $profile_bits),
                'author' => $user->display_name,
                'tags' => RBRT_Digest_Core::normalize_terms(array($industry, $location, $interests)),
                'url' => home_url('/page/profile?userID=' . $user->ID),
                'occurred_gmt' => $occurred,
            );
        }

        return apply_filters('rbrt_digest_directory_items', $items, $member_id, $start_gmt, $end_gmt);
    }

    public function find_existing_item_keys($member_id) {
        $digest_ids = get_posts(array(
            'post_type' => 'rbrt_digest',
            'post_status' => array('draft', 'pending', 'private', 'publish', 'future'),
            'posts_per_page' => 100,
            'fields' => 'ids',
            'meta_key' => '_rbrt_digest_member_id',
            'meta_value' => (int) $member_id,
            'orderby' => 'date',
            'order' => 'DESC',
        ));

        $keys = array();
        foreach ($digest_ids as $digest_id) {
            $stored = get_post_meta($digest_id, '_rbrt_digest_item_keys', true);
            if (is_array($stored)) {
                $keys = array_merge($keys, $stored);
            }
        }

        return array_values(array_unique(array_map('strval', $keys)));
    }

    public function create_draft($member, $content, $items, $start_gmt, $end_gmt, $generation_status, $interests) {
        $item_keys = array_values(array_map(static function ($item) {
            return $item['key'];
        }, $items));

        $post_id = wp_insert_post(array(
            'post_type' => 'rbrt_digest',
            'post_status' => 'draft',
            'post_author' => (int) $member->ID,
            'post_title' => sprintf(__('Personalized digest for %1$s — %2$s', 'rbrt-personalized-digest'), $member->display_name, get_date_from_gmt($end_gmt, get_option('date_format'))),
            'post_content' => wp_kses_post($content),
            'meta_input' => array(
                '_rbrt_digest_member_id' => (int) $member->ID,
                '_rbrt_digest_window_start_gmt' => $start_gmt,
                '_rbrt_digest_window_end_gmt' => $end_gmt,
                '_rbrt_digest_item_keys' => $item_keys,
                '_rbrt_digest_generation_status' => sanitize_key($generation_status),
                '_rbrt_digest_interests' => array_values($interests),
                '_rbrt_digest_source_counts' => $this->source_counts($items),
            ),
        ), true);

        return $post_id;
    }

    private function changed_date_query($start_gmt, $end_gmt) {
        $before = gmdate('Y-m-d H:i:s', strtotime($end_gmt . ' UTC') + 1);
        return array(
            'relation' => 'OR',
            array('column' => 'post_date_gmt', 'after' => $start_gmt, 'before' => $before, 'inclusive' => false),
            array('column' => 'post_modified_gmt', 'after' => $start_gmt, 'before' => $before, 'inclusive' => false),
        );
    }

    private function comment_date_query($start_gmt, $end_gmt) {
        return array(array(
            'column' => 'comment_date_gmt',
            'after' => $start_gmt,
            'before' => gmdate('Y-m-d H:i:s', strtotime($end_gmt . ' UTC') + 1),
            'inclusive' => false,
        ));
    }

    private function first_user_meta($user_id, $keys) {
        foreach ($keys as $key) {
            $value = trim((string) get_user_meta($user_id, $key, true));
            if ($value !== '') {
                return $value;
            }
        }
        return '';
    }

    private function source_counts($items) {
        $counts = array('forum_topic' => 0, 'forum_reply' => 0, 'directory_profile' => 0);
        foreach ($items as $item) {
            if (isset($counts[$item['source']])) {
                $counts[$item['source']]++;
            }
        }
        return $counts;
    }
}
