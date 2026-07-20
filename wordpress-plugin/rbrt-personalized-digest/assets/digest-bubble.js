(function () {
    'use strict';

    var root = document.querySelector('[data-rbrt-digest-bot]');
    if (!root || !window.rbrtDigestBubble) {
        return;
    }

    var launcher = root.querySelector('.rbrt-digest-launcher');
    var panel = root.querySelector('.rbrt-digest-panel');
    var closeButton = root.querySelector('.rbrt-digest-panel__close');
    var refreshButton = root.querySelector('.rbrt-digest-panel__refresh');
    var status = root.querySelector('.rbrt-digest-panel__status');
    var content = root.querySelector('.rbrt-digest-panel__content');
    var loaded = false;
    var busy = false;

    function request(action) {
        var data = new URLSearchParams();
        data.set('action', action);
        data.set('nonce', window.rbrtDigestBubble.nonce);
        return fetch(window.rbrtDigestBubble.ajaxUrl, {
            method: 'POST',
            credentials: 'same-origin',
            headers: {'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8'},
            body: data.toString()
        }).then(function (response) {
            return response.json().then(function (body) {
                if (!response.ok || !body.success) {
                    throw new Error(body && body.data && body.data.message ? body.data.message : window.rbrtDigestBubble.error);
                }
                return body.data;
            });
        });
    }

    function render(data) {
        status.textContent = data.message || data.updated || '';
        content.innerHTML = data.content || '';
        content.hidden = !data.content;
        if (data.empty) {
            content.innerHTML = '<p class="rbrt-digest-panel__empty">' + escapeHtml(data.message || '') + '</p>';
            content.hidden = false;
            status.textContent = '';
        }
    }

    function escapeHtml(value) {
        var element = document.createElement('div');
        element.textContent = value;
        return element.innerHTML;
    }

    function loadLatest() {
        status.textContent = window.rbrtDigestBubble.loading;
        content.hidden = true;
        return request('rbrt_digest_member_latest').then(function (data) {
            render(data);
            loaded = true;
        }).catch(function (error) {
            status.textContent = error.message || window.rbrtDigestBubble.error;
        });
    }

    function setOpen(open) {
        panel.hidden = !open;
        launcher.setAttribute('aria-expanded', open ? 'true' : 'false');
        root.classList.toggle('is-open', open);
        document.body.classList.toggle('rbrt-digest-panel-open', open);
        if (open) {
            closeButton.focus();
            if (!loaded) {
                loadLatest();
            }
        } else {
            launcher.focus();
        }
    }

    launcher.addEventListener('click', function () {
        setOpen(panel.hidden);
    });
    closeButton.addEventListener('click', function () {
        setOpen(false);
    });
    document.addEventListener('keydown', function (event) {
        if (event.key === 'Escape' && !panel.hidden) {
            setOpen(false);
        }
    });
    refreshButton.addEventListener('click', function () {
        if (busy) {
            return;
        }
        busy = true;
        refreshButton.disabled = true;
        status.textContent = window.rbrtDigestBubble.generating;
        request('rbrt_digest_member_generate').then(function (data) {
            render(data);
            loaded = true;
        }).catch(function (error) {
            status.textContent = error.message || window.rbrtDigestBubble.error;
        }).finally(function () {
            busy = false;
            refreshButton.disabled = false;
        });
    });

    window.addEventListener('pagehide', function () {
        document.body.classList.remove('rbrt-digest-panel-open');
    });
}());
