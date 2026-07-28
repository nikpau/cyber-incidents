(function () {
    function installInspectorScrollReset() {
        const card = document.querySelector('.floating-inspector-card');
        const content = document.getElementById('inspector-card-content');

        if (!card || !content) {
            return false;
        }

        // Reset scroll whenever Dash updates the inspector content subtree.
        const observer = new MutationObserver(function () {
            card.scrollTop = 0;
        });

        observer.observe(content, {
            childList: true,
            subtree: true,
        });

        return true;
    }

    function bootstrap() {
        if (installInspectorScrollReset()) {
            return;
        }

        // Dash may render asynchronously; retry briefly until elements exist.
        let retries = 0;
        const maxRetries = 50;
        const timer = setInterval(function () {
            retries += 1;
            if (installInspectorScrollReset() || retries >= maxRetries) {
                clearInterval(timer);
            }
        }, 100);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bootstrap);
    } else {
        bootstrap();
    }
})();
