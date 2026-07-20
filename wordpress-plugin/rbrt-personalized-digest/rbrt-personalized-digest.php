<?php
/**
 * Plugin Name: RBRT Personalized Digest
 * Description: Creates interest-scoped draft digests from unread PWork forum activity and approved directory updates.
 * Version: 1.0.0
 * Author: RBRT
 * Text Domain: rbrt-personalized-digest
 */

defined('ABSPATH') || exit;

define('RBRT_DIGEST_VERSION', '1.0.0');
define('RBRT_DIGEST_FILE', __FILE__);
define('RBRT_DIGEST_DIR', plugin_dir_path(__FILE__));

require_once RBRT_DIGEST_DIR . 'includes/class-rbrt-digest-core.php';
require_once RBRT_DIGEST_DIR . 'includes/class-rbrt-digest-wordpress-repository.php';
require_once RBRT_DIGEST_DIR . 'includes/class-rbrt-digest-ollama-summarizer.php';
require_once RBRT_DIGEST_DIR . 'includes/class-rbrt-digest-service.php';
require_once RBRT_DIGEST_DIR . 'includes/class-rbrt-personalized-digest-plugin.php';

RBRT_Personalized_Digest_Plugin::instance();

register_activation_hook(__FILE__, array('RBRT_Personalized_Digest_Plugin', 'activate'));
register_deactivation_hook(__FILE__, array('RBRT_Personalized_Digest_Plugin', 'deactivate'));
