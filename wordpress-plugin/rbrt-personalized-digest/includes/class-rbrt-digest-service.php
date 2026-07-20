<?php

defined('ABSPATH') || exit;

final class RBRT_Digest_Service {
    private $repository;
    private $summarizer;

    public function __construct($repository, $summarizer) {
        $this->repository = $repository;
        $this->summarizer = $summarizer;
    }

    public function generate_for_member($member_id, $options = array()) {
        $member_id = (int) $member_id;
        $member = $this->repository->get_member($member_id);
        if (!$member) {
            return new WP_Error('rbrt_digest_member_not_found', __('Member not found.', 'rbrt-personalized-digest'));
        }

        $end_gmt = !empty($options['end_gmt'])
            ? RBRT_Digest_Core::normalize_datetime($options['end_gmt'])
            : current_time('mysql', true);
        $lookback_days = isset($options['lookback_days']) ? max(1, (int) $options['lookback_days']) : 7;
        $start_gmt = !empty($options['start_gmt'])
            ? RBRT_Digest_Core::normalize_datetime($options['start_gmt'])
            : $this->repository->get_window_start($member_id, $end_gmt, $lookback_days);

        if ($start_gmt === '' || $end_gmt === '' || $start_gmt >= $end_gmt) {
            return new WP_Error('rbrt_digest_invalid_window', __('The digest time window is invalid.', 'rbrt-personalized-digest'));
        }

        $interests = $this->repository->get_member_interests($member_id);
        if (!$interests) {
            $this->repository->set_watermark($member_id, $end_gmt);
            return array('status' => 'no_interests', 'start_gmt' => $start_gmt, 'end_gmt' => $end_gmt, 'draft_id' => 0, 'item_count' => 0);
        }

        $items = array_merge(
            $this->repository->collect_forum_topics($member_id, $start_gmt, $end_gmt),
            $this->repository->collect_forum_replies($member_id, $start_gmt, $end_gmt),
            $this->repository->collect_directory_updates($member_id, $start_gmt, $end_gmt)
        );
        $items = RBRT_Digest_Core::deduplicate_items($items, $this->repository->find_existing_item_keys($member_id));

        if (!$items) {
            $this->repository->set_watermark($member_id, $end_gmt);
            return array('status' => 'no_updates', 'start_gmt' => $start_gmt, 'end_gmt' => $end_gmt, 'draft_id' => 0, 'item_count' => 0);
        }

        $limit = (int) apply_filters('rbrt_digest_max_items', 12, $member_id);
        $ranked = RBRT_Digest_Core::rank_items($items, $interests, $end_gmt, $limit);
        if (!$ranked) {
            $this->repository->set_watermark($member_id, $end_gmt);
            return array('status' => 'no_relevant_updates', 'start_gmt' => $start_gmt, 'end_gmt' => $end_gmt, 'draft_id' => 0, 'item_count' => 0);
        }

        $generation_status = 'ai';
        $summary_result = $this->summarizer->summarize($member, $interests, $ranked);
        if (is_wp_error($summary_result)) {
            $generation_status = 'fallback';
            $summary_result = array(
                'intro' => __('AI summarization was unavailable, so this draft contains concise source excerpts for review.', 'rbrt-personalized-digest'),
                'summaries' => RBRT_Digest_Core::fallback_summaries($ranked),
            );
        }

        $summaries = RBRT_Digest_Core::fallback_summaries($ranked);
        if (!empty($summary_result['summaries']) && is_array($summary_result['summaries'])) {
            $summaries = array_merge($summaries, $summary_result['summaries']);
        }
        $content = RBRT_Digest_Core::render_digest(
            $member,
            $ranked,
            $summaries,
            isset($summary_result['intro']) ? $summary_result['intro'] : ''
        );

        $draft_id = $this->repository->create_draft(
            $member,
            $content,
            $ranked,
            $start_gmt,
            $end_gmt,
            $generation_status,
            $interests
        );
        if (is_wp_error($draft_id) || !$draft_id) {
            return is_wp_error($draft_id)
                ? $draft_id
                : new WP_Error('rbrt_digest_draft_failed', __('The digest draft could not be stored.', 'rbrt-personalized-digest'));
        }

        $this->repository->set_watermark($member_id, $end_gmt);

        return array(
            'status' => $generation_status,
            'start_gmt' => $start_gmt,
            'end_gmt' => $end_gmt,
            'draft_id' => (int) $draft_id,
            'item_count' => count($ranked),
        );
    }
}
