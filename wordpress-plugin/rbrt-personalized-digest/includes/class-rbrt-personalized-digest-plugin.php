<?php

defined('ABSPATH') || exit;

final class RBRT_Personalized_Digest_Plugin {
    private static $instance;
    private $profile_timestamp_guard = false;

    public static function instance() {
        if (!self::$instance) {
            self::$instance = new self();
        }
        return self::$instance;
    }

    private function __construct() {
        add_action('init', array($this, 'register_digest_post_type'));
        add_action('admin_menu', array($this, 'register_admin_page'));
        add_action('admin_post_rbrt_digest_save_ai_settings', array($this, 'handle_save_ai_settings'));
        add_action('admin_post_rbrt_digest_test_ai', array($this, 'handle_test_ai'));
        add_action('admin_post_rbrt_digest_generate_member', array($this, 'handle_generate_member'));
        add_action('rbrt_digest_daily_event', array($this, 'start_daily_batches'));
        add_action('rbrt_digest_process_batch', array($this, 'process_scheduled_batch'));
        add_action('added_user_meta', array($this, 'record_material_profile_meta_change'), 10, 4);
        add_action('updated_user_meta', array($this, 'record_material_profile_meta_change'), 10, 4);
        add_action('deleted_user_meta', array($this, 'record_material_profile_meta_change'), 10, 4);
        add_action('profile_update', array($this, 'record_core_profile_change'), 10, 2);
    }

    public static function activate() {
        self::instance()->register_digest_post_type();
        if (!wp_next_scheduled('rbrt_digest_daily_event')) {
            wp_schedule_event(time() + HOUR_IN_SECONDS, 'daily', 'rbrt_digest_daily_event');
        }
        flush_rewrite_rules(false);
    }

    public static function deactivate() {
        wp_clear_scheduled_hook('rbrt_digest_daily_event');
        wp_clear_scheduled_hook('rbrt_digest_process_batch');
    }

    public function register_digest_post_type() {
        register_post_type('rbrt_digest', array(
            'labels' => array(
                'name' => __('Personalized Digests', 'rbrt-personalized-digest'),
                'singular_name' => __('Personalized Digest', 'rbrt-personalized-digest'),
                'edit_item' => __('Review Personalized Digest', 'rbrt-personalized-digest'),
            ),
            'public' => false,
            'show_ui' => true,
            'show_in_menu' => false,
            'show_in_rest' => false,
            'supports' => array('title', 'editor', 'author'),
            'capability_type' => 'post',
            'map_meta_cap' => true,
        ));
    }

    public function register_admin_page() {
        add_users_page(
            __('Personalized Digests', 'rbrt-personalized-digest'),
            __('Personalized Digests', 'rbrt-personalized-digest'),
            'list_users',
            'rbrt-personalized-digests',
            array($this, 'render_admin_page')
        );
    }

    public function render_admin_page() {
        if (!current_user_can('list_users')) {
            wp_die(esc_html__('You do not have permission to view personalized digests.', 'rbrt-personalized-digest'));
        }

        $repository = new RBRT_Digest_WordPress_Repository();
        $member_ids = $repository->get_approved_member_ids();
        $members = array_filter(array_map('get_userdata', $member_ids));
        $summarizer = new RBRT_Digest_AI_Summarizer();
        $ai_settings = $summarizer->settings();
        $providers = RBRT_Digest_AI_Summarizer::providers();
        $protocols = RBRT_Digest_AI_Summarizer::protocols();
        $notice = isset($_GET['rbrt_digest_notice']) ? sanitize_key(wp_unslash($_GET['rbrt_digest_notice'])) : '';
        ?>
        <div class="wrap">
            <h1><?php echo esc_html__('Personalized Digests', 'rbrt-personalized-digest'); ?></h1>
            <p><?php echo esc_html__('Generate one interest-scoped draft from unread PWork forum topics, replies, and approved directory profile updates.', 'rbrt-personalized-digest'); ?></p>

            <?php if ($notice !== '') : ?>
                <div class="notice notice-info"><p><?php echo esc_html($this->notice_text($notice)); ?></p></div>
            <?php endif; ?>

            <h2><?php echo esc_html__('AI provider settings', 'rbrt-personalized-digest'); ?></h2>
            <?php if (current_user_can('manage_options')) : ?>
                <form method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>" style="max-width:900px;">
                    <input type="hidden" name="action" value="rbrt_digest_save_ai_settings">
                    <?php wp_nonce_field('rbrt_digest_save_ai_settings'); ?>
                    <table class="form-table" role="presentation">
                        <tr><th><label for="rbrt-digest-provider"><?php echo esc_html__('Provider', 'rbrt-personalized-digest'); ?></label></th><td><select id="rbrt-digest-provider" name="provider"><?php foreach ($providers as $key => $provider) : ?><option value="<?php echo esc_attr($key); ?>" data-model="<?php echo esc_attr($provider['model']); ?>" data-endpoint="<?php echo esc_attr($provider['endpoint']); ?>" data-protocol="<?php echo esc_attr($provider['protocol']); ?>" <?php selected($ai_settings['provider'], $key); ?>><?php echo esc_html($provider['label']); ?></option><?php endforeach; ?></select></td></tr>
                        <tr><th><label for="rbrt-digest-model"><?php echo esc_html__('Model', 'rbrt-personalized-digest'); ?></label></th><td><input class="regular-text" id="rbrt-digest-model" name="model" value="<?php echo esc_attr($ai_settings['model']); ?>" required><p class="description"><?php echo esc_html__('Editable model identifier supplied by your provider.', 'rbrt-personalized-digest'); ?></p></td></tr>
                        <tr><th><label for="rbrt-digest-endpoint"><?php echo esc_html__('Endpoint', 'rbrt-personalized-digest'); ?></label></th><td><input class="large-text code" id="rbrt-digest-endpoint" name="endpoint" type="url" value="<?php echo esc_attr($ai_settings['endpoint']); ?>" required><p class="description"><?php echo esc_html__('HTTPS endpoints only. Gemini endpoints may contain the {model} placeholder.', 'rbrt-personalized-digest'); ?></p></td></tr>
                        <tr><th><label for="rbrt-digest-protocol"><?php echo esc_html__('Request format', 'rbrt-personalized-digest'); ?></label></th><td><select id="rbrt-digest-protocol" name="protocol"><?php foreach ($protocols as $key => $label) : ?><option value="<?php echo esc_attr($key); ?>" <?php selected($ai_settings['protocol'], $key); ?>><?php echo esc_html($label); ?></option><?php endforeach; ?></select><p class="description"><?php echo esc_html__('Choose the API format implemented by the endpoint, especially for custom gateways.', 'rbrt-personalized-digest'); ?></p></td></tr>
                        <tr><th><label for="rbrt-digest-api-key"><?php echo esc_html__('API key', 'rbrt-personalized-digest'); ?></label></th><td><input class="regular-text" id="rbrt-digest-api-key" name="api_key" type="password" value="" autocomplete="new-password" placeholder="<?php echo esc_attr($summarizer->has_stored_api_key() ? __('Stored securely — leave blank to keep', 'rbrt-personalized-digest') : __('Enter API key', 'rbrt-personalized-digest')); ?>"><p class="description"><?php echo esc_html__('The saved key is encrypted using this WordPress site’s secret salts and is never displayed again.', 'rbrt-personalized-digest'); ?></p><?php if ($summarizer->has_stored_api_key()) : ?><label><input type="checkbox" name="remove_api_key" value="1"> <?php echo esc_html__('Remove the stored API key', 'rbrt-personalized-digest'); ?></label><?php endif; ?></td></tr>
                    </table>
                    <?php submit_button(__('Save AI settings', 'rbrt-personalized-digest')); ?>
                </form>
                <form method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>">
                    <input type="hidden" name="action" value="rbrt_digest_test_ai">
                    <?php wp_nonce_field('rbrt_digest_test_ai'); ?>
                    <?php submit_button(__('Test saved connection', 'rbrt-personalized-digest'), 'secondary', 'submit', false); ?>
                    <span style="margin-left:8px;"><?php echo $summarizer->is_configured() ? esc_html__('Configured', 'rbrt-personalized-digest') : esc_html__('Not configured — manual runs use a deterministic fallback draft', 'rbrt-personalized-digest'); ?></span>
                </form>
                <script>(function(){var p=document.getElementById('rbrt-digest-provider');p.addEventListener('change',function(){var o=p.options[p.selectedIndex];document.getElementById('rbrt-digest-model').value=o.dataset.model||'';document.getElementById('rbrt-digest-endpoint').value=o.dataset.endpoint||'';document.getElementById('rbrt-digest-protocol').value=o.dataset.protocol||'openai_chat';});}());</script>
            <?php else : ?>
                <p><?php echo esc_html__('Only a site administrator can view or change AI provider credentials.', 'rbrt-personalized-digest'); ?></p>
            <?php endif; ?>
            <table class="widefat striped" style="max-width:760px;margin:18px 0;"><tbody>
                <tr><th><?php echo esc_html__('Active provider', 'rbrt-personalized-digest'); ?></th><td><?php echo esc_html($providers[$ai_settings['provider']]['label'] . ' / ' . $ai_settings['model']); ?></td></tr>
                <tr><th><?php echo esc_html__('Scheduled processing', 'rbrt-personalized-digest'); ?></th><td><?php echo esc_html__('Daily, in small batches; skipped until the provider is configured.', 'rbrt-personalized-digest'); ?></td></tr>
            </tbody></table>

            <h2><?php echo esc_html__('Generate a member draft', 'rbrt-personalized-digest'); ?></h2>
            <form method="post" action="<?php echo esc_url(admin_url('admin-post.php')); ?>">
                <input type="hidden" name="action" value="rbrt_digest_generate_member">
                <?php wp_nonce_field('rbrt_digest_generate_member'); ?>
                <table class="form-table" role="presentation">
                    <tr>
                        <th><label for="rbrt-digest-member"><?php echo esc_html__('Approved member', 'rbrt-personalized-digest'); ?></label></th>
                        <td><select id="rbrt-digest-member" name="member_id" required>
                            <?php foreach ($members as $member) : ?>
                                <option value="<?php echo esc_attr($member->ID); ?>"><?php echo esc_html($member->display_name . ' (#' . $member->ID . ')'); ?></option>
                            <?php endforeach; ?>
                        </select></td>
                    </tr>
                    <tr>
                        <th><label for="rbrt-digest-lookback"><?php echo esc_html__('Initial lookback', 'rbrt-personalized-digest'); ?></label></th>
                        <td><input id="rbrt-digest-lookback" name="lookback_days" type="number" min="1" max="365" value="7"> <?php echo esc_html__('days (used only when the member has no watermark)', 'rbrt-personalized-digest'); ?></td>
                    </tr>
                </table>
                <?php submit_button(__('Generate draft', 'rbrt-personalized-digest')); ?>
            </form>

            <h2><?php echo esc_html__('Recent drafts', 'rbrt-personalized-digest'); ?></h2>
            <?php $this->render_recent_drafts(); ?>
        </div>
        <?php
    }

    public function handle_save_ai_settings() {
        if (!current_user_can('manage_options')) {
            wp_die(esc_html__('You do not have permission to change AI settings.', 'rbrt-personalized-digest'));
        }
        check_admin_referer('rbrt_digest_save_ai_settings');

        $providers = RBRT_Digest_AI_Summarizer::providers();
        $protocols = RBRT_Digest_AI_Summarizer::protocols();
        $provider = isset($_POST['provider']) ? sanitize_key(wp_unslash($_POST['provider'])) : '';
        $protocol = isset($_POST['protocol']) ? sanitize_key(wp_unslash($_POST['protocol'])) : '';
        $model = isset($_POST['model']) ? sanitize_text_field(wp_unslash($_POST['model'])) : '';
        $endpoint = isset($_POST['endpoint']) ? esc_url_raw(wp_unslash($_POST['endpoint'])) : '';
        $scheme = strtolower((string) wp_parse_url($endpoint, PHP_URL_SCHEME));

        if (!isset($providers[$provider]) || !isset($protocols[$protocol]) || $model === '' || $endpoint === '' || ($scheme !== 'https' && !apply_filters('rbrt_digest_allow_insecure_ai_endpoint', false, $endpoint))) {
            $this->redirect_with_notice('settings_invalid');
        }

        update_option(RBRT_Digest_AI_Summarizer::OPTION_PROVIDER, $provider, false);
        update_option(RBRT_Digest_AI_Summarizer::OPTION_MODEL, $model, false);
        update_option(RBRT_Digest_AI_Summarizer::OPTION_ENDPOINT, $endpoint, false);
        update_option(RBRT_Digest_AI_Summarizer::OPTION_PROTOCOL, $protocol, false);

        $summarizer = new RBRT_Digest_AI_Summarizer();
        if (!empty($_POST['remove_api_key'])) {
            $summarizer->delete_api_key();
        } elseif (isset($_POST['api_key']) && trim((string) wp_unslash($_POST['api_key'])) !== '') {
            $stored = $summarizer->store_api_key(wp_unslash($_POST['api_key']));
            if (is_wp_error($stored)) {
                $this->redirect_with_notice('settings_error');
            }
        }
        $this->redirect_with_notice('settings_saved');
    }

    public function handle_test_ai() {
        if (!current_user_can('manage_options')) {
            wp_die(esc_html__('You do not have permission to test AI settings.', 'rbrt-personalized-digest'));
        }
        check_admin_referer('rbrt_digest_test_ai');
        $item = array(
            'key' => 'connection-test',
            'source' => 'forum_topic',
            'score' => 100,
            'title' => 'RBRT connection test',
            'author' => 'RBRT',
            'occurred_gmt' => gmdate('Y-m-d H:i:s'),
            'content' => 'A short community technology update used only to verify the configured AI provider.',
        );
        $result = (new RBRT_Digest_AI_Summarizer())->summarize((object) array('ID' => get_current_user_id(), 'display_name' => 'RBRT administrator'), array('technology'), array($item));
        $this->redirect_with_notice(is_wp_error($result) ? 'connection_error' : 'connection_ok');
    }

    public function handle_generate_member() {
        if (!current_user_can('list_users')) {
            wp_die(esc_html__('You do not have permission to generate personalized digests.', 'rbrt-personalized-digest'));
        }
        check_admin_referer('rbrt_digest_generate_member');

        $member_id = isset($_POST['member_id']) ? absint($_POST['member_id']) : 0;
        $lookback_days = isset($_POST['lookback_days']) ? min(365, max(1, absint($_POST['lookback_days']))) : 7;
        if (get_user_meta($member_id, 'pw_user_status', true) !== 'approved') {
            wp_die(esc_html__('The selected account is not an approved directory member.', 'rbrt-personalized-digest'));
        }

        $result = $this->service()->generate_for_member($member_id, array('lookback_days' => $lookback_days));
        $notice = is_wp_error($result) ? 'error' : sanitize_key($result['status']);
        $url = add_query_arg('rbrt_digest_notice', $notice, admin_url('users.php?page=rbrt-personalized-digests'));
        wp_safe_redirect($url);
        exit;
    }

    public function start_daily_batches() {
        $summarizer = new RBRT_Digest_AI_Summarizer();
        if (!$summarizer->is_configured()) {
            return;
        }

        update_option('_rbrt_digest_batch_offset', 0, false);
        if (!wp_next_scheduled('rbrt_digest_process_batch')) {
            wp_schedule_single_event(time() + 5, 'rbrt_digest_process_batch');
        }
    }

    public function process_scheduled_batch() {
        if (get_transient('_rbrt_digest_batch_lock')) {
            return;
        }
        set_transient('_rbrt_digest_batch_lock', 1, 5 * MINUTE_IN_SECONDS);

        $summarizer = new RBRT_Digest_AI_Summarizer();
        if (!$summarizer->is_configured()) {
            delete_transient('_rbrt_digest_batch_lock');
            return;
        }

        $repository = new RBRT_Digest_WordPress_Repository();
        $member_ids = $repository->get_approved_member_ids();
        $offset = max(0, (int) get_option('_rbrt_digest_batch_offset', 0));
        $batch_size = max(1, (int) apply_filters('rbrt_digest_batch_size', 10));
        $batch = array_slice($member_ids, $offset, $batch_size);
        $service = new RBRT_Digest_Service($repository, $summarizer);

        foreach ($batch as $member_id) {
            $service->generate_for_member($member_id);
        }

        $offset += count($batch);
        if ($offset < count($member_ids) && $batch) {
            update_option('_rbrt_digest_batch_offset', $offset, false);
            wp_schedule_single_event(time() + MINUTE_IN_SECONDS, 'rbrt_digest_process_batch');
        } else {
            delete_option('_rbrt_digest_batch_offset');
        }

        delete_transient('_rbrt_digest_batch_lock');
    }

    public function record_material_profile_meta_change($meta_id, $user_id, $meta_key, $meta_value) {
        if ($this->profile_timestamp_guard || !in_array($meta_key, $this->material_profile_meta_keys(), true)) {
            return;
        }
        $this->touch_profile_updated_at($user_id);
    }

    public function record_core_profile_change($user_id, $old_user_data) {
        $user = get_userdata($user_id);
        if (!$user) {
            return;
        }

        if ($user->display_name !== $old_user_data->display_name || $user->description !== $old_user_data->description) {
            $this->touch_profile_updated_at($user_id);
        }
    }

    private function touch_profile_updated_at($user_id) {
        $this->profile_timestamp_guard = true;
        update_user_meta((int) $user_id, RBRT_Digest_Core::PROFILE_UPDATED_META, (string) current_time('timestamp', true));
        $this->profile_timestamp_guard = false;
    }

    private function material_profile_meta_keys() {
        return apply_filters('rbrt_digest_material_profile_meta_keys', array(
            'rbrt_interest_tags', 'rbrt_industry', 'pwork_company', 'pwork_job', 'pwork_location',
            'company', 'business_name', 'industry', 'sector', 'location', 'city', 'description', 'pw_user_status',
        ));
    }

    private function service() {
        return new RBRT_Digest_Service(new RBRT_Digest_WordPress_Repository(), new RBRT_Digest_AI_Summarizer());
    }

    private function redirect_with_notice($notice) {
        $url = add_query_arg('rbrt_digest_notice', sanitize_key($notice), admin_url('users.php?page=rbrt-personalized-digests'));
        wp_safe_redirect($url);
        exit;
    }

    private function notice_text($notice) {
        $messages = array(
            'ai' => __('An AI-generated WordPress draft was created and the member watermark advanced.', 'rbrt-personalized-digest'),
            'fallback' => __('The AI request was unavailable; a source-based fallback draft was created and the member watermark advanced.', 'rbrt-personalized-digest'),
            'no_interests' => __('No draft was created because this member has no declared interests. The watermark advanced.', 'rbrt-personalized-digest'),
            'no_updates' => __('No unread updates were found. The watermark advanced.', 'rbrt-personalized-digest'),
            'no_relevant_updates' => __('Unread updates were found but none matched the member interests. The watermark advanced.', 'rbrt-personalized-digest'),
            'error' => __('The digest could not be created. The watermark was not advanced.', 'rbrt-personalized-digest'),
            'settings_saved' => __('AI provider settings were saved. A blank key field kept the existing key.', 'rbrt-personalized-digest'),
            'settings_invalid' => __('The AI settings were not saved. Choose a supported provider and request format, enter a model, and use an HTTPS endpoint.', 'rbrt-personalized-digest'),
            'settings_error' => __('The settings were saved, but the API key could not be encrypted. The existing key was not exposed.', 'rbrt-personalized-digest'),
            'connection_ok' => __('The saved AI provider connection completed successfully.', 'rbrt-personalized-digest'),
            'connection_error' => __('The saved AI provider connection test failed. Check the provider, model, endpoint, request format, and key.', 'rbrt-personalized-digest'),
        );
        return isset($messages[$notice]) ? $messages[$notice] : __('Digest generation finished.', 'rbrt-personalized-digest');
    }

    private function render_recent_drafts() {
        $drafts = get_posts(array(
            'post_type' => 'rbrt_digest',
            'post_status' => 'draft',
            'posts_per_page' => 20,
            'orderby' => 'date',
            'order' => 'DESC',
        ));
        if (!$drafts) {
            echo '<p>' . esc_html__('No personalized digest drafts yet.', 'rbrt-personalized-digest') . '</p>';
            return;
        }

        echo '<table class="widefat striped"><thead><tr><th>' . esc_html__('Draft', 'rbrt-personalized-digest') . '</th><th>' . esc_html__('Member', 'rbrt-personalized-digest') . '</th><th>' . esc_html__('Window (UTC)', 'rbrt-personalized-digest') . '</th><th>' . esc_html__('Sources', 'rbrt-personalized-digest') . '</th><th>' . esc_html__('Items', 'rbrt-personalized-digest') . '</th><th>' . esc_html__('Generation', 'rbrt-personalized-digest') . '</th></tr></thead><tbody>';
        foreach ($drafts as $draft) {
            $member = get_userdata((int) get_post_meta($draft->ID, '_rbrt_digest_member_id', true));
            $counts = get_post_meta($draft->ID, '_rbrt_digest_source_counts', true);
            $counts = is_array($counts) ? $counts : array();
            $window_start = (string) get_post_meta($draft->ID, '_rbrt_digest_window_start_gmt', true);
            $window_end = (string) get_post_meta($draft->ID, '_rbrt_digest_window_end_gmt', true);
            $item_keys = get_post_meta($draft->ID, '_rbrt_digest_item_keys', true);
            $item_keys = is_array($item_keys) ? $item_keys : array();
            $count_text = sprintf(
                __('%1$d topics, %2$d replies, %3$d profiles', 'rbrt-personalized-digest'),
                isset($counts['forum_topic']) ? $counts['forum_topic'] : 0,
                isset($counts['forum_reply']) ? $counts['forum_reply'] : 0,
                isset($counts['directory_profile']) ? $counts['directory_profile'] : 0
            );
            echo '<tr><td><a href="' . esc_url(get_edit_post_link($draft->ID)) . '">' . esc_html($draft->post_title) . '</a></td><td>' . esc_html($member ? $member->display_name : __('Unknown member', 'rbrt-personalized-digest')) . '</td><td>' . esc_html($window_start . ' → ' . $window_end) . '</td><td>' . esc_html($count_text) . '</td><td>' . esc_html((string) count($item_keys)) . '</td><td>' . esc_html(get_post_meta($draft->ID, '_rbrt_digest_generation_status', true)) . '</td></tr>';
        }
        echo '</tbody></table>';
    }
}
